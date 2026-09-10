#!/usr/bin/env python3
"""
ShotBench harness - compare cinematic-understanding VLMs for the reel editor.

Runs local HF vision models and the Gemini API against the ShotBench test set
(3,572 MCQ items over 8 cinematography dimensions) and reports per-dimension
accuracy, latency and cost.

Why this exists: the published ShotBench leaderboard's newest commercial entry is
Gemini-2.5-flash-preview (April 2025) and ShotVL-7B has not been updated since
September 2025. Whether a specialist model on a stale base still beats a modern
generalist is unmeasured. This measures it.

Design notes:
  - Results are appended to JSONL per model, one line per item. Re-running skips
    completed items, so a spot-instance eviction costs only the in-flight item.
  - Prompting matches VLMEvalKit's MCQ convention (the format ShotBench ships in)
    so the ShotVL-7B number is directly comparable to the published 70.1%.
  - Models are loaded one at a time and freed, so a 24GB card is enough.

Usage:
    python run_benchmark.py --list-gemini-models     # discover the exact API id
    python run_benchmark.py --models shotvl-7b
    python run_benchmark.py --models all --limit 200 # quick smoke run
    python run_benchmark.py --report                 # score whatever is done
"""

from __future__ import annotations

import argparse
import ast
import gc
import json
import os
import re
import sys
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

HF_DATASET = "Vchitect/ShotBench"

# The two dimensions the reel-editor template actually depends on. Overall
# average is the wrong metric for us -- lens size and lighting don't feed the
# template, shot size and framing do.
KEY_CATEGORIES = ("shot size", "shot framing")

# USD per million tokens, verified against ai.google.dev/gemini-api/docs/pricing
# on 2026-09-10. The 3.6/3.7/3.8 Flash rates are INTRODUCTORY through 2026-12-31
# and double on 2027-01-01. Flash-Lite is not introductory, so it does not move.
#
# Thinking tokens bill as output. On gemini-3.8-flash they are ~473 of 474 output
# tokens for a one-letter MCQ answer, so they dominate cost -- measured, not
# assumed. Flash-Lite emits none.
GEMINI_PRICING: dict[str, dict[str, float]] = {
    "gemini-3.8-flash":      {"in": 0.75, "out": 3.75, "doubles_2027": 1},
    "gemini-3.7-flash":      {"in": 0.75, "out": 3.75, "doubles_2027": 1},
    "gemini-3.6-flash":      {"in": 0.75, "out": 3.75, "doubles_2027": 1},
    "gemini-3.5-flash":      {"in": 1.50, "out": 9.00, "doubles_2027": 0},
    "gemini-3.5-flash-lite": {"in": 0.30, "out": 2.50, "doubles_2027": 0},
    "gemini-2.5-flash":      {"in": 0.30, "out": 2.50, "doubles_2027": 0},
    "gemini-2.5-flash-lite": {"in": 0.10, "out": 0.40, "doubles_2027": 0},
}
DEFAULT_PRICING = {"in": 0.75, "out": 3.75, "doubles_2027": 1}


def pricing_for(model_id: str) -> dict[str, float]:
    if model_id in GEMINI_PRICING:
        return GEMINI_PRICING[model_id]
    for known, rates in GEMINI_PRICING.items():  # tolerate -preview / date suffixes
        if model_id.startswith(known):
            return rates
    return DEFAULT_PRICING


def load_env_file(path: Path) -> None:
    """Read KEY=value lines into the environment if not already set.

    Keeps the API key out of shell history and out of the process command line.
    Existing environment variables win, so an explicit export always overrides
    the file."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


@dataclass
class ModelSpec:
    key: str
    kind: str  # "hf" | "gemini"
    model_id: str
    note: str = ""
    # Approximate BF16 weight footprint in GB, for the preflight VRAM check.
    approx_vram_gb: float = 0.0


MODELS: dict[str, ModelSpec] = {
    "shotvl-3b": ModelSpec(
        "shotvl-3b", "hf", "Vchitect/ShotVL-3B",
        "Cinematic specialist, 3.75B. Published ShotBench avg 65.1.", 7.5,
    ),
    "shotvl-7b": ModelSpec(
        "shotvl-7b", "hf", "Vchitect/ShotVL-7B",
        "Cinematic specialist, 8.29B. Published ShotBench avg 70.1.", 16.6,
    ),
    "qwen3-vl-8b": ModelSpec(
        "qwen3-vl-8b", "hf", "Qwen/Qwen3-VL-8B-Instruct",
        "Generalist baseline, the generation after ShotVL's base.", 17.5,
    ),
    "qwen3.5-9b": ModelSpec(
        "qwen3.5-9b", "hf", "Qwen/Qwen3.5-9B",
        "Modern generalist (2026-03). The real test of specialist vs. base progress.", 19.3,
    ),
    "gemini": ModelSpec(
        "gemini", "gemini", "gemini-3.8-flash",
        "Commercial incumbent. Thinks by default; thinking bills as output.", 0.0,
    ),
    "gemini-lite": ModelSpec(
        "gemini-lite", "gemini", "gemini-3.5-flash-lite",
        "Cheaper, emits no thinking tokens, and is NOT on introductory pricing "
        "so it does not double on 2027-01-01.", 0.0,
    ),
}

DEFAULT_SET = ["shotvl-7b", "shotvl-3b", "qwen3-vl-8b", "qwen3.5-9b",
               "gemini", "gemini-lite"]


# --------------------------------------------------------------------------
# Dataset
# --------------------------------------------------------------------------

def _parse_listish(raw: str) -> list[str]:
    """test.tsv stores lists inconsistently: JSON for `type`, Python literals
    for `path`. Try both before giving up."""
    if raw is None:
        return []
    raw = raw.strip()
    if not raw:
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            val = parser(raw)
            if isinstance(val, list):
                return [str(v) for v in val]
            return [str(val)]
        except Exception:
            continue
    return [raw]


@dataclass
class Item:
    index: int
    media_type: str
    paths: list[str]
    question: str
    options: dict[str, str]
    answer: str
    category: str


def ensure_dataset(data_dir: Path, want_videos: bool) -> Path:
    """Download and extract ShotBench. images.tar is 2.2GB, videos.tar 1.2GB."""
    from huggingface_hub import hf_hub_download

    data_dir.mkdir(parents=True, exist_ok=True)
    tsv = data_dir / "test.tsv"
    if not tsv.exists():
        print("  downloading test.tsv ...")
        src = hf_hub_download(HF_DATASET, "test.tsv", repo_type="dataset")
        tsv.write_bytes(Path(src).read_bytes())

    wanted = [("images.tar", "image")]
    if want_videos:
        wanted.append(("videos.tar", "video"))

    for archive, marker in wanted:
        # The tars expand to image/ and video/ directories.
        if (data_dir / marker).exists():
            continue
        print(f"  downloading {archive} (this is the slow part) ...")
        src = hf_hub_download(HF_DATASET, archive, repo_type="dataset")
        print(f"  extracting {archive} ...")
        with tarfile.open(src) as tf:
            tf.extractall(data_dir)
    return tsv


def load_items(tsv: Path, categories: list[str] | None, limit: int | None,
               skip_video: bool) -> list[Item]:
    import csv

    items: list[Item] = []
    with tsv.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            types = _parse_listish(row.get("type", ""))
            media_type = (types[0] if types else "image").lower()
            if skip_video and media_type == "video":
                continue
            category = (row.get("category") or "").strip()
            if categories and category not in categories:
                continue
            try:
                options = json.loads(row["options"])
            except Exception:
                options = ast.literal_eval(row["options"])
            items.append(Item(
                index=int(row["index"]),
                media_type=media_type,
                paths=_parse_listish(row.get("path", "")),
                question=(row.get("question") or "").strip(),
                options={k: str(v) for k, v in options.items()},
                answer=(row.get("answer") or "").strip().upper(),
                category=category,
            ))
            if limit and len(items) >= limit:
                break
    return items


# --------------------------------------------------------------------------
# Prompting and answer extraction
# --------------------------------------------------------------------------

def build_prompt(item: Item) -> str:
    """VLMEvalKit MCQ convention -- matches how ShotBench was scored, so our
    ShotVL-7B number is comparable to the published one."""
    lines = [item.question]
    for letter in sorted(item.options):
        lines.append(f"{letter}. {item.options[letter]}")
    lines.append("Answer with the option's letter from the given choices directly.")
    return "\n".join(lines)


def extract_answer(text: str, options: dict[str, str]) -> str | None:
    """Models don't reliably obey 'letter only'.

    Order matters here. Matching option *text* has to come before the loose
    bare-letter scan, otherwise the English article "a" in a sentence like
    "This is a Close Up shot" is read as option A. And option-text matching has
    to prefer the longest hit, or "Extreme Close Up" is shadowed by the "Close
    Up" substring and the item is scored as unparsed."""
    if not text:
        return None
    text = text.strip()
    valid = set(options)

    # 1. The expected case: the whole reply is a letter.
    m = re.match(r"^\s*\(?([A-Da-d])\)?\s*[\.\):,]?\s*$", text)
    if m and m.group(1).upper() in valid:
        return m.group(1).upper()

    # 2. "Answer: C" / "the answer is B" / "option D".
    m = re.search(r"\b(?:answer|option)\b\W{0,12}([A-Da-d])\b", text, re.I)
    if m and m.group(1).upper() in valid:
        return m.group(1).upper()

    # 3. Leading "C) Close Up" or "C. Close Up".
    m = re.match(r"^\s*\(?([A-Da-d])[\.\):,\-]\s+\S", text)
    if m and m.group(1).upper() in valid:
        return m.group(1).upper()

    # 4. The option text appears verbatim; longest wins.
    low = text.lower()
    hits = sorted(
        ((len(v.strip()), k) for k, v in options.items() if v.strip().lower() in low),
        reverse=True,
    )
    if hits and (len(hits) == 1 or hits[0][0] > hits[1][0]):
        return hits[0][1]

    # 5. Last resort: a standalone capital letter. Lowercase is excluded to
    #    avoid the article "a"; ambiguity ("A or B") scores as unparsed.
    found = {c for c in re.findall(r"(?<![A-Za-z])([A-D])(?![A-Za-z])", text)}
    found &= valid
    if len(found) == 1:
        return found.pop()
    return None


# --------------------------------------------------------------------------
# Media loading
# --------------------------------------------------------------------------

def load_media(item: Item, data_dir: Path, video_frames: int) -> list[Any]:
    """Return a list of PIL images. Video items are uniformly frame-sampled --
    an approximation that will understate camera-movement scores relative to
    native video input. Documented, not hidden."""
    from PIL import Image

    out: list[Any] = []
    for rel in item.paths:
        path = data_dir / rel
        if not path.exists():
            alt = list(data_dir.rglob(Path(rel).name))
            if not alt:
                raise FileNotFoundError(f"missing media: {rel}")
            path = alt[0]

        if item.media_type == "video":
            out.extend(_sample_video_frames(path, video_frames))
        else:
            out.append(Image.open(path).convert("RGB"))
    return out


def _sample_video_frames(path: Path, n: int) -> list[Any]:
    import cv2
    from PIL import Image

    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    if total <= 0:
        cap.release()
        raise RuntimeError(f"unreadable video: {path}")
    idxs = [int(round(i * (total - 1) / max(n - 1, 1))) for i in range(n)]
    frames = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if ok:
            frames.append(Image.fromarray(frame[:, :, ::-1]))
    cap.release()
    if not frames:
        raise RuntimeError(f"no frames decoded: {path}")
    return frames


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------

class HFBackend:
    """Local transformers VLM. Uses the unified image-text-to-text API, which
    covers Qwen2.5-VL (ShotVL's base), Qwen3-VL and Qwen3.5."""

    def __init__(self, model_id: str, max_new_tokens: int = 16):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.torch = torch
        self.max_new_tokens = max_new_tokens
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

        print(f"  loading {model_id} ...")
        self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_id,
            dtype=dtype,
            device_map="auto" if torch.cuda.is_available() else None,
            trust_remote_code=True,
        )
        self.model.eval()

    def generate(self, images: list[Any], prompt: str) -> tuple[str, dict]:
        content = [{"type": "image", "image": im} for im in images]
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]

        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        )
        inputs = {k: (v.to(self.model.device) if hasattr(v, "to") else v)
                  for k, v in inputs.items()}

        with self.torch.inference_mode():
            out = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )
        trimmed = out[0][inputs["input_ids"].shape[1]:]
        text = self.processor.decode(trimmed, skip_special_tokens=True)
        return text.strip(), {}

    def close(self):
        del self.model
        gc.collect()
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()


API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY is not set. Put it in .env beside this script, "
                 "or export it, then re-run.")
    return key


def _post_json(url: str, payload: dict, key: str, timeout: int = 180) -> dict:
    import urllib.request

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


class GeminiBackend:
    """Gemini via plain REST.

    Deliberately not using the google-genai SDK: version 2.22.0 raises
    "Cannot send a request, as the client has been closed" against httpx 0.28,
    and a benchmark that runs unattended on a rented GPU box should not carry a
    dependency that can break like that. urllib is in the standard library.

    max_output_tokens defaults high on purpose. Gemini 3 models think by default,
    and thinking spends the output budget before any answer is emitted -- at 16
    tokens every reply comes back empty with finishReason=MAX_TOKENS, which
    scores as 0% and looks like a model failure rather than a harness bug."""

    def __init__(self, model_id: str, media_resolution: str | None = None,
                 thinking_level: str | None = None, max_output_tokens: int = 512):
        self.key = _api_key()
        self.model_id = model_id
        self.media_resolution = media_resolution
        self.thinking_level = thinking_level
        self.max_output_tokens = max_output_tokens
        self.rates = pricing_for(model_id)
        self.in_tokens = 0
        self.out_tokens = 0      # billable output: answer + thinking
        self.think_tokens = 0    # tracked separately so its share is visible
        self.truncated = 0

    def generate(self, images: list[Any], prompt: str) -> tuple[str, dict]:
        import base64
        import io
        import urllib.error

        parts: list[dict] = []
        for im in images:
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=90)
            parts.append({"inline_data": {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(buf.getvalue()).decode("ascii"),
            }})
        parts.append({"text": prompt})

        gen_cfg: dict[str, Any] = {
            "temperature": 0.0,
            "maxOutputTokens": self.max_output_tokens,
        }
        if self.media_resolution:
            gen_cfg["mediaResolution"] = self.media_resolution
        if self.thinking_level:
            gen_cfg["thinkingConfig"] = {"thinkingLevel": self.thinking_level}

        payload = {"contents": [{"role": "user", "parts": parts}],
                   "generationConfig": gen_cfg}
        url = f"{API_ROOT}/models/{self.model_id}:generateContent"

        last_err: Exception | None = None
        for attempt in range(6):
            try:
                data = _post_json(url, payload, self.key)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")[:200]
                last_err = RuntimeError(f"HTTP {exc.code}: {body}")
                # 503 is common on gemini-3.8-flash under load; 429 is quota.
                if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                    time.sleep(min(2 ** attempt * 2, 45))
                    continue
                raise last_err
            except Exception as exc:
                last_err = exc
                if attempt < 5:
                    time.sleep(min(2 ** attempt * 2, 45))
                    continue
                raise

            usage = data.get("usageMetadata", {}) or {}
            pt = usage.get("promptTokenCount", 0) or 0
            ct = usage.get("candidatesTokenCount", 0) or 0
            th = usage.get("thoughtsTokenCount", 0) or 0
            self.in_tokens += pt
            self.out_tokens += ct + th
            self.think_tokens += th

            cand = (data.get("candidates") or [{}])[0]
            finish = cand.get("finishReason")
            text = "".join(
                p.get("text", "")
                for p in ((cand.get("content") or {}).get("parts") or [])
            )
            if finish == "MAX_TOKENS" and not text.strip():
                self.truncated += 1
            return text.strip(), {
                "in_tokens": pt, "out_tokens": ct, "think_tokens": th,
                "finish": finish,
            }
        raise RuntimeError(f"gemini failed after retries: {last_err}")

    def cost_usd(self) -> float:
        return (self.in_tokens / 1e6 * self.rates["in"]
                + self.out_tokens / 1e6 * self.rates["out"])

    def close(self):
        pass


def list_gemini_models() -> list[str]:
    import urllib.request

    req = urllib.request.Request(f"{API_ROOT}/models",
                                 headers={"x-goog-api-key": _api_key()})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    out = []
    for m in data.get("models", []):
        name = (m.get("name") or "").replace("models/", "")
        methods = m.get("supportedGenerationMethods") or []
        if not methods or "generateContent" in methods:
            out.append(name)
    return sorted(out)


def resolve_gemini_model(preferred: str | None) -> str:
    """Model ids move. Discover from the API rather than hardcoding a guess."""
    names = list_gemini_models()
    if preferred:
        if preferred in names:
            return preferred
        sys.exit(f"model '{preferred}' not available. Choices:\n  "
                 + "\n  ".join(names))
    for pat in ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3"):
        hits = [n for n in names
                if n.startswith(pat) and not any(
                    x in n for x in ("image", "tts", "audio", "transcribe"))]
        if hits:
            return hits[0]
    sys.exit("could not auto-pick a Gemini model. Run --list-gemini-models.")


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def completed_indices(path: Path) -> set[int]:
    done: set[int] = set()
    if not path.exists():
        return done
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                done.add(json.loads(line)["index"])
            except Exception:
                continue  # tolerate a torn final line from an eviction
    return done


def run_model(spec: ModelSpec, items: list[Item], data_dir: Path,
              out_dir: Path, args) -> None:
    out_path = out_dir / f"{spec.key}.jsonl"
    done = completed_indices(out_path)
    todo = [it for it in items if it.index not in done]

    print(f"\n=== {spec.key} ===")
    print(f"  {spec.note}")
    if done:
        print(f"  resuming: {len(done)} done, {len(todo)} remaining")
    if not todo:
        print("  nothing to do")
        return

    if spec.kind == "gemini":
        model_id = resolve_gemini_model(spec.model_id or args.gemini_model)
        effective_model_id = model_id
        print(f"  api model: {model_id}")
        backend: Any = GeminiBackend(
            model_id,
            media_resolution=args.media_resolution,
            thinking_level=args.thinking_level,
            max_output_tokens=args.max_output_tokens,
        )
        rates = pricing_for(model_id)
        print(f"  pricing: ${rates['in']}/M in, ${rates['out']}/M out"
              + ("  (introductory - doubles 2027-01-01)"
                 if rates.get("doubles_2027") else ""))
    else:
        preflight_vram(spec)
        effective_model_id = spec.model_id
        backend = HFBackend(spec.model_id, max_new_tokens=args.max_new_tokens)

    t_start = time.time()
    errors = 0
    with out_path.open("a", encoding="utf-8") as fh:
        for n, item in enumerate(todo, 1):
            try:
                images = load_media(item, data_dir, args.video_frames)
                prompt = build_prompt(item)
                t0 = time.time()
                text, meta = backend.generate(images, prompt)
                latency = time.time() - t0
                pred = extract_answer(text, item.options)
                rec = {
                    "index": item.index,
                    "model_id": effective_model_id,
                    "category": item.category,
                    "media_type": item.media_type,
                    "gold": item.answer,
                    "pred": pred,
                    "raw": text[:200],
                    "correct": bool(pred and pred == item.answer),
                    "unparsed": pred is None,
                    "latency_s": round(latency, 3),
                    **meta,
                }
            except Exception as exc:
                errors += 1
                rec = {
                    "index": item.index,
                    "category": item.category,
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                    "correct": False,
                    "unparsed": True,
                }
            fh.write(json.dumps(rec) + "\n")
            fh.flush()  # durable against eviction

            if n % 25 == 0 or n == len(todo):
                rate = n / max(time.time() - t_start, 1e-6)
                eta = (len(todo) - n) / max(rate, 1e-9)
                print(f"  {n}/{len(todo)}  {rate:.2f} it/s  eta {eta/60:.1f}m"
                      + (f"  errors={errors}" if errors else ""))

    if isinstance(backend, GeminiBackend):
        share = (100 * backend.think_tokens / backend.out_tokens
                 if backend.out_tokens else 0.0)
        print(f"  tokens in={backend.in_tokens} out={backend.out_tokens} "
              f"(thinking={backend.think_tokens}, {share:.0f}% of output) "
              f"cost=${backend.cost_usd():.4f}")
        if backend.truncated:
            print(f"  WARNING: {backend.truncated} replies hit MAX_TOKENS with no "
                  f"text. Raise --max-output-tokens; thinking is eating the budget.")
    backend.close()


def preflight_vram(spec: ModelSpec) -> None:
    try:
        import torch
    except ImportError:
        return
    if not torch.cuda.is_available():
        print("  WARNING: no CUDA device -- this will be extremely slow on CPU.")
        return
    total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    name = torch.cuda.get_device_name(0)
    print(f"  gpu: {name} ({total:.1f} GB)")
    if spec.approx_vram_gb and spec.approx_vram_gb > total * 0.92:
        print(f"  WARNING: {spec.key} needs ~{spec.approx_vram_gb} GB at BF16 but "
              f"only {total:.1f} GB is present. Expect OOM; quantise or pick a "
              f"smaller model.")


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def report(out_dir: Path) -> None:
    files = sorted(out_dir.glob("*.jsonl"))
    if not files:
        print("no results yet")
        return

    table: dict[str, dict[str, Any]] = {}
    categories: set[str] = set()

    for path in files:
        key = path.stem
        by_cat: dict[str, list[bool]] = {}
        lat: list[float] = []
        unparsed = errs = 0
        tin = tout = tthink = 0
        model_id = ""
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if "error" in r:
                    errs += 1
                cat = r.get("category", "?")
                by_cat.setdefault(cat, []).append(bool(r.get("correct")))
                categories.add(cat)
                if r.get("latency_s"):
                    lat.append(r["latency_s"])
                if r.get("unparsed"):
                    unparsed += 1
                tin += r.get("in_tokens", 0)
                # Thinking bills as output; fold it in so cost is not understated.
                tout += r.get("out_tokens", 0) + r.get("think_tokens", 0)
                tthink += r.get("think_tokens", 0)
                if not model_id:
                    model_id = r.get("model_id", "")
        table[key] = {
            "by_cat": by_cat, "lat": lat, "unparsed": unparsed,
            "errors": errs, "in": tin, "out": tout, "think": tthink,
            "model_id": model_id,
        }

    ordered = sorted(categories)
    width = max(len(k) for k in table) + 2

    print("\n" + "=" * 100)
    print("ACCURACY BY DIMENSION (%)")
    print("=" * 100)
    header = "model".ljust(width) + "".join(c[:13].rjust(15) for c in ordered) + "overall".rjust(11) + "n".rjust(8)
    print(header)
    print("-" * len(header))

    for key, d in sorted(table.items()):
        cells = ""
        total_ok = total_n = 0
        for cat in ordered:
            vals = d["by_cat"].get(cat, [])
            if vals:
                acc = 100 * sum(vals) / len(vals)
                cells += f"{acc:14.1f} "
                total_ok += sum(vals)
                total_n += len(vals)
            else:
                cells += " " * 15
        overall = 100 * total_ok / total_n if total_n else 0
        print(key.ljust(width) + cells + f"{overall:10.1f} " + f"{total_n:7d}")

    # The metric that actually decides the architecture.
    print("\n" + "=" * 100)
    print(f"DECISION METRIC - {' + '.join(KEY_CATEGORIES)} only")
    print("(the two fields the template depends on; overall average is not the right metric here)")
    print("=" * 100)
    rows = []
    for key, d in table.items():
        ok = n = 0
        for cat in KEY_CATEGORIES:
            vals = d["by_cat"].get(cat, [])
            ok += sum(vals)
            n += len(vals)
        if n:
            rows.append((100 * ok / n, key, n))
    for acc, key, n in sorted(rows, reverse=True):
        print(f"  {key.ljust(width)} {acc:6.1f}%   (n={n})")

    print("\n" + "=" * 100)
    print("OPERATIONS")
    print("=" * 100)
    print("model".ljust(width) + "med latency".rjust(13) + "unparsed".rjust(10)
          + "errors".rjust(8) + "tok in".rjust(10) + "tok out".rjust(10)
          + "think%".rjust(8) + "$/item".rjust(10) + "$/50 imgs".rjust(11))
    for key, d in sorted(table.items()):
        lat = sorted(d["lat"])
        med = lat[len(lat) // 2] if lat else 0.0
        rates = pricing_for(d.get("model_id") or "")
        n_items = sum(len(v) for v in d["by_cat"].values()) or 1
        if d["in"]:
            cost = d["in"] / 1e6 * rates["in"] + d["out"] / 1e6 * rates["out"]
            per_item = cost / n_items
            think_pct = 100 * d["think"] / d["out"] if d["out"] else 0.0
            tail = (f"{think_pct:7.0f}%" + f"${per_item:9.5f}"
                    + f"${per_item * 50:10.3f}")
        else:
            tail = "      -" + "     local" + "      local"
        print(key.ljust(width) + f"{med:12.2f}s" + f"{d['unparsed']:10d}"
              + f"{d['errors']:8d}" + f"{d['in']:10d}" + f"{d['out']:10d}" + tail)

    print("\n'$/50 imgs' projects one reference-reel analysis (SPEC assumes 40-60")
    print("images per reference). Thinking tokens bill as output and are included.")
    print("\nReference - published ShotBench: ShotVL-7B 70.1 | ShotVL-3B 65.1 | "
          "GPT-4o 59.3 | Gemini-2.5-flash 54.5")
    print("If shotvl-7b lands near 70.1 overall, the harness is calibrated.\n")


# --------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--models", nargs="+", default=None,
                   help=f"model keys, or 'all'. choices: {', '.join(MODELS)}")
    p.add_argument("--data-dir", default="./shotbench_data")
    p.add_argument("--out-dir", default="./results")
    p.add_argument("--limit", type=int, default=None, help="cap items (smoke test)")
    p.add_argument("--categories", nargs="+", default=None,
                   help="restrict to dimensions, e.g. --categories 'shot size' 'shot framing'")
    p.add_argument("--key-only", action="store_true",
                   help=f"shorthand for --categories {KEY_CATEGORIES}")
    p.add_argument("--skip-video", action="store_true",
                   help="images only; skips the 1.2GB videos.tar download")
    p.add_argument("--video-frames", type=int, default=8)
    p.add_argument("--max-new-tokens", type=int, default=16,
                   help="local HF models only; they don't emit thinking tokens")
    p.add_argument("--max-output-tokens", type=int, default=512,
                   help="Gemini only. Must leave room for thinking: at 16 the "
                        "reply comes back empty and every item scores 0.")
    p.add_argument("--thinking-level", default=None, choices=["low", "high"],
                   help="Gemini 3 thinking budget; 'low' cuts output tokens")
    p.add_argument("--gemini-model", default=None, help="exact API model id")
    p.add_argument("--media-resolution", default=None,
                   choices=["MEDIA_RESOLUTION_LOW", "MEDIA_RESOLUTION_MEDIUM",
                            "MEDIA_RESOLUTION_HIGH"],
                   help="Gemini token-per-image cap; LOW is the ~6x cost lever")
    p.add_argument("--list-gemini-models", action="store_true")
    p.add_argument("--report", action="store_true", help="score existing results and exit")
    p.add_argument("--env-file", default=None,
                   help="file of KEY=value lines (default: .env beside this script)")
    p.add_argument("--tsv", default=None,
                   help="override the test.tsv path (for running a prepared subset)")
    args = p.parse_args()

    load_env_file(Path(args.env_file) if args.env_file
                  else Path(__file__).resolve().parent / ".env")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.list_gemini_models:
        for name in list_gemini_models():
            rates = pricing_for(name)
            flag = " (introductory - doubles 2027-01-01)" if rates.get("doubles_2027") else ""
            known = name in GEMINI_PRICING or any(
                name.startswith(k) for k in GEMINI_PRICING)
            price = f"  ${rates['in']}/M in, ${rates['out']}/M out{flag}" if known else ""
            print(f"  {name}{price}")
        return

    if args.report:
        report(out_dir)
        return

    if args.key_only:
        args.categories = list(KEY_CATEGORIES)

    keys = args.models or DEFAULT_SET
    if keys == ["all"]:
        keys = DEFAULT_SET
    unknown = [k for k in keys if k not in MODELS]
    if unknown:
        sys.exit(f"unknown model(s): {unknown}. choices: {list(MODELS)}")

    data_dir = Path(args.data_dir)
    if args.tsv:
        # A prepared subset: media is assumed already extracted under data_dir.
        tsv = Path(args.tsv)
        if not tsv.exists():
            sys.exit(f"--tsv not found: {tsv}")
        print(f"Using prepared item list: {tsv}")
    else:
        print("Preparing ShotBench ...")
        tsv = ensure_dataset(data_dir, want_videos=not args.skip_video)
    items = load_items(tsv, args.categories, args.limit, args.skip_video)
    print(f"  {len(items)} items"
          + (f" in {args.categories}" if args.categories else "")
          + (" (images only)" if args.skip_video else ""))
    if not items:
        sys.exit("no items matched the filters")

    for key in keys:
        try:
            run_model(MODELS[key], items, data_dir, out_dir, args)
        except KeyboardInterrupt:
            print("\ninterrupted; progress is saved, re-run to resume")
            break
        except SystemExit:
            raise
        except Exception as exc:
            print(f"  {key} FAILED: {type(exc).__name__}: {exc}")
            print("  continuing with the next model")

    report(out_dir)


if __name__ == "__main__":
    main()
