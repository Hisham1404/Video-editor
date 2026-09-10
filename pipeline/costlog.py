"""Metered-call accounting.

CLAUDE.md: "Every metered call gets logged with token count and cost. Cost per
job is a tracked metric, not an afterthought." So this is wired in from the
first call rather than retrofitted -- retrofitted cost tracking always
undercounts, because the calls you forgot to instrument are invisible.

Measured on 2026-09-10 against gemini-3.8-flash, and the reason this module
tracks thinking tokens separately:

    A one-letter multiple-choice answer cost 1,116 input tokens, 1 answer token
    and 473 THINKING tokens. Thinking bills as output at the output rate, so it
    was ~100% of the output cost. PROJECT_DECISION_LOG.md estimated $0.06 per
    reference by counting input tokens only; the real figure for that model is
    ~$0.114. Any cost model that ignores thinking tokens is wrong by ~2x.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterator

# USD per million tokens. Verified against ai.google.dev/gemini-api/docs/pricing
# on 2026-09-10. Rates marked intro=True double on 2027-01-01.
PRICING: dict[str, dict[str, Any]] = {
    "gemini-3.8-flash":      {"in": 0.75, "out": 3.75, "intro": True},
    "gemini-3.7-flash":      {"in": 0.75, "out": 3.75, "intro": True},
    "gemini-3.6-flash":      {"in": 0.75, "out": 3.75, "intro": True},
    "gemini-3.5-flash":      {"in": 1.50, "out": 9.00, "intro": False},
    "gemini-3.5-flash-lite": {"in": 0.30, "out": 2.50, "intro": False},
    # Local models: no marginal token cost. GPU time is tracked instead, since
    # a rented 4090 at $0.46/hr is ~$336/mo if left idle -- see SPEC.md hosting.
    "local": {"in": 0.0, "out": 0.0, "intro": False},
}

GPU_USD_PER_HOUR = float(os.environ.get("GPU_USD_PER_HOUR", "0.46"))


def rates_for(model: str) -> dict[str, Any]:
    if model in PRICING:
        return PRICING[model]
    for known, r in PRICING.items():
        if model.startswith(known):
            return r
    return {"in": 0.0, "out": 0.0, "intro": False, "unknown": True}


@dataclass
class Call:
    """One metered unit of work."""

    stage: str
    model: str
    in_tokens: int = 0
    out_tokens: int = 0          # answer tokens only
    thinking_tokens: int = 0     # billed as output; tracked apart so it's visible
    latency_s: float = 0.0
    gpu_seconds: float = 0.0
    ok: bool = True
    error: str = ""
    ts: float = field(default_factory=time.time)

    @property
    def billed_out(self) -> int:
        return self.out_tokens + self.thinking_tokens

    @property
    def cost_usd(self) -> float:
        r = rates_for(self.model)
        token_cost = (self.in_tokens / 1e6 * r["in"]
                      + self.billed_out / 1e6 * r["out"])
        return token_cost + self.gpu_seconds / 3600.0 * GPU_USD_PER_HOUR


class CostLog:
    """Append-only ledger for one job.

    Usage:
        log = CostLog(job_id="abc", path="runs/abc/costs.jsonl")
        with log.record("describe", "gemini-3.5-flash-lite") as call:
            resp = api(...)
            call.in_tokens = resp.usage.prompt_tokens
            call.out_tokens = resp.usage.answer_tokens
            call.thinking_tokens = resp.usage.thinking_tokens
        print(log.summary())

    The context manager records the call even when the body raises, so failed
    calls still show up. A failure that burned tokens is still a cost, and a
    failure rate is itself a metric -- gemini-3.8-flash was returning 503 on
    ~83% of requests when this was written.
    """

    def __init__(self, job_id: str | None = None, path: str | Path | None = None):
        self.job_id = job_id or uuid.uuid4().hex[:12]
        self.path = Path(path) if path else None
        self.calls: list[Call] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def record(self, stage: str, model: str, **kw: Any) -> Iterator[Call]:
        call = Call(stage=stage, model=model, **kw)
        t0 = time.perf_counter()
        try:
            yield call
        except Exception as exc:
            call.ok = False
            call.error = f"{type(exc).__name__}: {exc}"[:300]
            raise
        finally:
            call.latency_s = time.perf_counter() - t0
            self._append(call)

    def _append(self, call: Call) -> None:
        self.calls.append(call)
        if self.path:
            rec = asdict(call)
            rec["cost_usd"] = round(call.cost_usd, 8)
            rec["job_id"] = self.job_id
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")

    # ---- reporting ------------------------------------------------------

    def total_cost(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    def summary(self) -> dict[str, Any]:
        by_stage: dict[str, dict[str, Any]] = {}
        for c in self.calls:
            s = by_stage.setdefault(c.stage, {
                "calls": 0, "failed": 0, "in": 0, "out": 0,
                "thinking": 0, "cost": 0.0, "latency": 0.0,
            })
            s["calls"] += 1
            s["failed"] += 0 if c.ok else 1
            s["in"] += c.in_tokens
            s["out"] += c.out_tokens
            s["thinking"] += c.thinking_tokens
            s["cost"] += c.cost_usd
            s["latency"] += c.latency_s

        billed_out = sum(c.billed_out for c in self.calls)
        thinking = sum(c.thinking_tokens for c in self.calls)
        return {
            "job_id": self.job_id,
            "calls": len(self.calls),
            "failed": sum(1 for c in self.calls if not c.ok),
            "total_cost_usd": round(self.total_cost(), 6),
            "in_tokens": sum(c.in_tokens for c in self.calls),
            "billed_out_tokens": billed_out,
            "thinking_tokens": thinking,
            "thinking_pct_of_output": (
                round(100 * thinking / billed_out, 1) if billed_out else 0.0),
            "p95_latency_s": _p95([c.latency_s for c in self.calls]),
            "by_stage": by_stage,
        }

    def render(self) -> str:
        s = self.summary()
        lines = [
            f"job {s['job_id']}: ${s['total_cost_usd']:.4f}  "
            f"({s['calls']} calls, {s['failed']} failed, "
            f"p95 {s['p95_latency_s']:.2f}s)",
            f"  tokens in={s['in_tokens']} billed_out={s['billed_out_tokens']} "
            f"(thinking {s['thinking_pct_of_output']}% of output)",
        ]
        for stage, d in s["by_stage"].items():
            lines.append(f"  {stage:14s} {d['calls']:4d} calls  ${d['cost']:.5f}")
        return "\n".join(lines)


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return round(ordered[idx], 4)
