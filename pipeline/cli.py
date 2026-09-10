"""Pipeline entry point.

Wires the eight stages together and prints the cost/latency summary that
CLAUDE.md requires per job. The stages are stubs, so this currently fails at
stage 1 by design -- the plumbing, the cost ledger and the template contract are
what exist today.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.config import load_env_file, settings
from pipeline.costlog import CostLog


def run(reference: Path, assets: Path, music: Path, out: Path,
        cost: CostLog) -> Path:
    from pipeline.stages import (s1_segment, s2_rhythm, s3_describe,
                                 s4_assemble, s5_ingest, s6_match,
                                 s7_gaps, s8_render)

    shots = s1_segment.segment(reference)
    shots = s1_segment.flag_suspected_transitions(reference, shots)

    ref_rhythm = s2_rhythm.extract(reference)
    descriptions = [
        s3_describe.describe(frames=[], cost=cost, model=settings.vision_model)
        for _ in shots
    ]

    template = s4_assemble.assemble(shots, ref_rhythm, descriptions, fps=30.0)
    template.validate()

    user_assets = s5_ingest.ingest(sorted(assets.iterdir()))
    template = s6_match.match(template, user_assets)
    template = s7_gaps.emit_prompts(template)

    # The user's track, not the reference's. This is the whole point of storing
    # rhythm instead of seconds.
    user_rhythm = s2_rhythm.extract(music)
    return s8_render.render(template, user_rhythm, music, out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference", required=True, type=Path)
    p.add_argument("--assets", required=True, type=Path)
    p.add_argument("--music", required=True, type=Path)
    p.add_argument("--out", type=Path, default=Path("out.mp4"))
    p.add_argument("--job-id", default=None)
    args = p.parse_args()

    load_env_file()
    cost = CostLog(job_id=args.job_id)
    ledger = settings.runs_dir / cost.job_id / "costs.jsonl"
    cost.path = ledger
    ledger.parent.mkdir(parents=True, exist_ok=True)

    try:
        out = run(args.reference, args.assets, args.music, args.out, cost)
        print(f"rendered -> {out}")
    except NotImplementedError as exc:
        print(f"pipeline stopped: {exc} is not implemented yet", file=sys.stderr)
    finally:
        # Always report cost, including on failure. A job that burned tokens and
        # then crashed still cost money, and the failure rate is itself a metric.
        print(cost.render(), file=sys.stderr)


if __name__ == "__main__":
    main()
