#!/usr/bin/env python3
"""Take whatever the review page produced and turn it into the harness TSV.

    python import_labels.py --input <file> [--frames frames_pexels]

Accepts three shapes, because the page has written two of them and a console
paste is the third:

    {"px123.jpg": "closeUp", ...}                      flat map, first version
    {"labels": {...}, "changed": {...},
     "dropped": {...}}                                 combined, current version
    anything above wrapped in whitespace/newlines       a clipboard paste

Being liberal here is deliberate. The first review session was lost to a save
that silently produced a stale file, and the recovery path was pasting JSON out
of a browser console. A loader that only accepts one exact shape would have
turned that recovery into another dead end.

Reports the agreement rate against my pre-fill, which is a result in its own
right -- see review_page.py.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="labels.json, or a pasted file")
    ap.add_argument("--frames", default="frames_pexels")
    ap.add_argument("--out", default="reels_test.tsv")
    a = ap.parse_args()

    raw = Path(a.input).read_text(encoding="utf-8").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"not valid JSON: {exc}")

    if isinstance(data, dict) and "labels" in data and isinstance(data["labels"], dict):
        labels = data["labels"]
        changed = data.get("changed", {}) or {}
        dropped = data.get("dropped", {}) or {}
    elif isinstance(data, dict):
        labels, changed, dropped = data, {}, {}
    else:
        sys.exit("expected a JSON object")

    labels = {k: v for k, v in labels.items() if v}      # drop any null/undefined
    fdir = Path(a.frames)
    prefill_path = fdir / "prefill.json"
    prefill = (json.loads(prefill_path.read_text(encoding="utf-8"))
               if prefill_path.exists() else {})

    missing = [f for f in labels if not (fdir / f).exists()]
    if missing:
        print(f"  WARNING: {len(missing)} labelled frames not on disk, e.g. {missing[:3]}")

    total_frames = len(prefill) or len(labels)
    print(f"labelled      {len(labels)} of {total_frames}")
    print(f"dropped       {len(dropped)}")
    unreviewed = total_frames - len(labels) - len(dropped)
    if unreviewed > 0:
        print(f"  {unreviewed} frames never reviewed — the set is partial")

    if prefill:
        # Recompute rather than trusting the page's `changed` map: this is the
        # number the VLM-bias argument rests on, and it is cheap to derive from
        # the two label sets directly.
        overlap = [f for f in labels if f in prefill]
        agree = sum(1 for f in overlap if labels[f] == prefill[f])
        if overlap:
            print(f"\nagreement with my pre-fill: {agree}/{len(overlap)} "
                  f"= {agree / len(overlap) * 100:.1f}%")
            diffs = collections.Counter(
                (prefill[f], labels[f]) for f in overlap if labels[f] != prefill[f])
            if diffs:
                print("  most common corrections (mine -> yours):")
                for (mine, yours), n in diffs.most_common(8):
                    print(f"    {mine:18} -> {yours:18} {n:3}")

    dist = collections.Counter(labels.values())
    print("\nclass distribution:")
    for cls, n in dist.most_common():
        print(f"  {cls:18} {n:4}  {n / len(labels) * 100:5.1f}%")
    thin = sorted(c for c, n in dist.items() if n < 10)
    if thin:
        print(f"\n  under 10 examples of {thin} — per-class accuracy on those is\n"
              f"  not measurable; read only the overall and balanced numbers.")

    out = Path(a.out)
    out.write_text("".join(f"{fdir.name}/{f}\t{c}\n"
                           for f, c in sorted(labels.items())), encoding="utf-8")
    print(f"\nwrote {out} ({len(labels)} rows)")
    print(f"next:  cd ../shotbench && python run_benchmark.py --dataset reels \\\n"
          f"           --reels-tsv ../reels/{out.name} --models <model>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
