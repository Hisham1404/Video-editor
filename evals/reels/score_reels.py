#!/usr/bin/env python3
"""Score the reels set, with the label-source bias measured rather than assumed.

    python score_reels.py

THE PROBLEM THIS FILE EXISTS TO HANDLE
--------------------------------------
The gold labels for this set were written by a vision-language model (me), with
seven human corrections. The headline comparison is a DINOv2 classifier against
gemini-3.5-flash-lite, which are 0.2 points apart on human-labelled film-grab.
Gemini and I are the same kind of model: where I misread a frame, Gemini plausibly
misreads it the same way and scores as correct against my label. A few points of
that decides the comparison.

So no single number here is reported alone. Three things bound it:

1. PAIRED, SAME ITEMS. Gemini's run was cut short by a daily quota, and the TSV
   is sorted by Pexels id, which tracks upload date -- older stock skews wide,
   newer skews close. Measured on the first 140 vs the rest: extreme-long 19% vs
   2%, close-up 6% vs 18%. A truncated run is therefore NOT a random sample, and
   comparing a partial score against a full one would be meaningless. Everything
   comparative here runs on the exact items both models answered.

2. HELD-OUT UNCERTAINTY. The 25 frames flagged as genuinely arguable at label
   time are reported separately. If the gap moves when they are removed, the
   result is resting on labels their author did not trust.

3. DRIFT AGAINST HUMAN-LABELLED DATA. Both models have film-grab scores, and
   film-grab's labels are human. If my labels flatter Gemini, Gemini should gain
   ground here relative to there. That shift is computed and printed whichever
   way it falls.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

SB = Path(__file__).resolve().parents[1] / "shotbench"
_spec = importlib.util.spec_from_file_location("rb", SB / "run_benchmark.py")
rb = importlib.util.module_from_spec(_spec)
sys.modules["rb"] = rb
_spec.loader.exec_module(rb)

C5 = rb.COLLAPSE_5
CLASSES_5 = set(C5.values())
LETTERS = "ABCDEFG"
KEYS = list(rb.FILMSHOTS_OPTIONS)


def options_for(index: int) -> dict[str, str]:
    """Must match load_reels exactly: seeded on the row index."""
    order = KEYS[:]
    random.Random(index).shuffle(order)
    return {LETTERS[j]: k for j, k in enumerate(order)}


def load(run: str, dataset: str) -> dict[int, tuple[str, str]]:
    p = SB / "results" / f"{run}.{dataset}.jsonl"
    out: dict[int, tuple[str, str]] = {}
    if not p.exists():
        return out
    for line in p.open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("error"):
            continue
        opts = options_for(r["index"])
        gold = C5.get(opts.get(r.get("gold")))
        raw = (r.get("raw") or "").strip()
        pred = raw if raw in CLASSES_5 else (
            C5.get(opts.get(r["pred"])) if r.get("pred") else None)
        if gold:
            out[r["index"]] = (pred, gold)
    return out


def acc(d: dict, keys=None) -> tuple[float, int]:
    ks = list(d) if keys is None else [k for k in keys if k in d]
    if not ks:
        return 0.0, 0
    return sum(d[k][0] == d[k][1] for k in ks) / len(ks) * 100, len(ks)


def balanced(d: dict, keys=None) -> float:
    ks = list(d) if keys is None else [k for k in keys if k in d]
    per = []
    for c in {d[k][1] for k in ks}:
        sub = [k for k in ks if d[k][1] == c]
        per.append(sum(d[k][0] == c for k in sub) / len(sub) * 100)
    return sum(per) / len(per) if per else 0.0


def mcnemar(a: dict, b: dict, keys) -> tuple[int, int, float]:
    ks = [k for k in keys if k in a and k in b and a[k][0] and b[k][0]]
    a1 = sum(1 for k in ks if a[k][0] == a[k][1] and b[k][0] != b[k][1])
    b1 = sum(1 for k in ks if b[k][0] == b[k][1] and a[k][0] != a[k][1])
    n = a1 + b1
    if n == 0:
        return a1, b1, 1.0
    chi = (abs(a1 - b1) - 1) ** 2 / n
    return a1, b1, math.erfc(math.sqrt(chi / 2))


def main() -> int:
    cls = load("dinov2-shotscale", "reels")
    gem = load("gemini-lite", "reels")
    if not cls:
        sys.exit("no classifier result yet")

    tsv = [l.split("\t") for l in
           (Path(__file__).parent / "reels_test.tsv").read_text(encoding="utf-8").splitlines() if l.strip()]
    hard_names = set(json.loads(
        (Path(__file__).parent / "frames_pexels" / "uncertain.json").read_text(encoding="utf-8")))
    hard_idx = {i for i, r in enumerate(tsv) if Path(r[0]).name in hard_names}
    human = json.loads((Path(__file__).parent / "frames_pexels" / "human_anchor.json")
                       .read_text(encoding="utf-8"))
    human_idx = {i for i, r in enumerate(tsv) if Path(r[0]).name in human}

    print("=" * 78)
    print("REELS — vertical phone-style footage, 267 frames")
    print("=" * 78)
    a, n = acc(cls)
    print(f"  classifier, full set          {a:5.1f}%   n={n}   balanced {balanced(cls):.1f}%")
    if gem:
        a, n = acc(gem)
        print(f"  gemini, what it completed     {a:5.1f}%   n={n}   balanced {balanced(gem):.1f}%")
        print("     ^ NOT comparable to the line above: different items, and the")
        print("       truncation is class-skewed. Use the paired block below.")

    if gem:
        shared = sorted(set(cls) & set(gem))
        print(f"\n{'-' * 78}\nPAIRED — the {len(shared)} frames both answered\n{'-' * 78}")
        for name, d in (("classifier", cls), ("gemini-lite", gem)):
            a, n = acc(d, shared)
            print(f"  {name:14} {a:5.1f}%   balanced {balanced(d, shared):5.1f}%")
        w1, w2, p = mcnemar(cls, gem, shared)
        verdict = "SIGNIFICANT" if p < 0.05 else "not significant"
        print(f"  McNemar: classifier {w1} / gemini {w2}   p={p:.3f}   {verdict}")

        easy = [k for k in shared if k not in hard_idx]
        print(f"\n  with my {len(shared) - len(easy)} self-flagged frames removed (n={len(easy)}):")
        for name, d in (("classifier", cls), ("gemini-lite", gem)):
            a, _ = acc(d, easy)
            print(f"    {name:14} {a:5.1f}%")
        w1, w2, p = mcnemar(cls, gem, easy)
        print(f"    McNemar: {w1} / {w2}   p={p:.3f}")

        print(f"\n{'-' * 78}\nBIAS CHECK — drift against human-labelled film-grab\n{'-' * 78}")
        fc, fg = load("dinov2-shotscale", "filmshots"), load("gemini-lite", "filmshots")
        if fc and fg:
            ca, _ = acc(fc); ga, _ = acc(fg)
            cr, _ = acc(cls, shared); gr, _ = acc(gem, shared)
            print(f"  film-grab (human labels):  classifier {ca:.1f}%   gemini {ga:.1f}%   gap {ca - ga:+.1f}")
            print(f"  reels     (my labels)   :  classifier {cr:.1f}%   gemini {gr:.1f}%   gap {cr - gr:+.1f}")
            drift = (cr - gr) - (ca - ga)
            print(f"\n  gap moved {drift:+.1f} points toward "
                  f"{'the classifier' if drift > 0 else 'gemini'}.")
            if drift < -3:
                print("  Gemini gains ground on my labels. That is the direction VLM-author")
                print("  bias predicts, and the size is large enough to matter. Treat the")
                print("  reels comparison as unreliable until a human relabels it.")
            elif drift > 0:
                print("  Gemini LOSES ground on my labels -- the opposite of what author")
                print("  bias predicts. The classifier's result here survived a thumb on")
                print("  the other side of the scale.")
            else:
                print("  Small drift in gemini's favour, within what noise at this n allows.")

    if human_idx & set(cls):
        print(f"\n{'-' * 78}\nHUMAN ANCHOR — the {len(human_idx)} frames a person decided\n{'-' * 78}")
        for name, d in (("classifier", cls), ("gemini-lite", gem)):
            if d:
                a, n = acc(d, sorted(human_idx))
                if n:
                    print(f"  {name:14} {a:5.1f}%   n={n}")
        print("  Far too few to conclude anything. Recorded because it is the only")
        print("  part of this set whose labels are not mine.")

    print(f"\n{'-' * 78}\nGOLD DISTRIBUTION\n{'-' * 78}")
    dist = collections.Counter(v[1] for v in cls.values())
    for c, k in dist.most_common():
        print(f"  {c:18} {k:4}  {k / len(cls) * 100:5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
