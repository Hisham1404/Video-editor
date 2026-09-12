"""Cross-model analysis of the film-grab results. Read-only: mutates nothing.

    python analyze.py

Three things `--report` cannot do, and which the conclusions in
`evals/FINDINGS.md` rest on:

1. **5-class scoring.** aslakey/shot_scale knows five shot sizes; the benchmark
   asks seven. Scoring it against 7-class gold measures the taxonomy mismatch,
   not the model -- it reads 0.0% because it never emits a letter at all. Both
   gold and prediction collapse into the coarser space for every model alike,
   which is the only direction that is honest: five cannot be split into seven.

2. **Paired significance.** Every model answered the same 859 questions, so the
   accuracy differences are not independent samples and a two-proportion test
   overstates them. McNemar looks only at items where two models disagree,
   which is the question actually being asked: is A better than B *here*.

3. **Agreement as a confidence signal.** The numbers wired into
   `s5_ingest.AGREE_CONFIDENCE` and friends. Re-run this before changing them.

4. **Balanced accuracy and per-class recall.** film-grab is sorted by class and
   42% `medium`, so plain accuracy partly rewards whichever model leans that
   way, and a run cut short by a quota gets a slice of entirely the wrong
   difficulty. Balanced accuracy weights the five classes equally.
"""
from __future__ import annotations

import glob
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "rb", Path(__file__).with_name("run_benchmark.py"))
rb = importlib.util.module_from_spec(_spec)
sys.modules["rb"] = rb
_spec.loader.exec_module(rb)

LETTERS = "ABCDEFG"
KEYS = list(rb.FILMSHOTS_OPTIONS)
C5 = rb.COLLAPSE_5
CLASSES_5 = set(C5.values())


def options_for(index: int) -> dict[str, str]:
    """Letter -> raw option key, for one item.

    The option order is a seeded shuffle of the item index, so it is
    reconstructible from the stored row without re-running anything. That is
    what makes a parser or taxonomy fix cost zero GPU time.
    """
    order = KEYS[:]
    random.Random(index).shuffle(order)
    return {LETTERS[j]: k for j, k in enumerate(order)}


def load(run: str, keep_declines: bool = False) -> dict[int, tuple[str, str]]:
    """index -> (predicted 5-class, gold 5-class), skipping errored items.

    Errors are dropped rather than counted wrong: an API failure is a fact about
    the provider, not about the model's grasp of shot scale, and mixing the two
    is how a 19% error rate turns into an apparent accuracy gap.

    A DECLINE IS NOT AN ERROR. `keep_declines` decides which question is being
    asked, and the two callers want opposite answers:

    - McNemar compares two models head to head, so an item neither answered
      carries no signal and an item one model declined is not a *loss* by that
      model's reasoning -- default False drops them.
    - Per-class recall asks "of the real close-ups, how many did it find", and a
      model that answered nothing found nothing. Dropping declines there pays a
      model for staying silent: ShotVL-7B emits an empty string on 85 of 859
      images, and excluding those lifted it from 8th to 2nd on balanced
      accuracy. That empty string is a defect, not an abstention from a model
      that knows better -- pass True and score it as a miss.
    """
    out: dict[int, tuple[str, str]] = {}
    path = Path(__file__).parent / "results" / f"{run}.filmshots.jsonl"
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("error"):
            continue
        opts = options_for(r["index"])
        gold = C5.get(opts.get(r.get("gold")))
        raw = (r.get("raw") or "").strip()
        # The classifier emits a class name; the VLMs emit a letter.
        pred = raw if raw in CLASSES_5 else (
            C5.get(opts.get(r["pred"])) if r.get("pred") else None)
        if gold and (pred or keep_declines):
            out[r["index"]] = (pred, gold)
    return out


def mcnemar(a: dict, b: dict) -> tuple[int, int, float, float]:
    """Returns (a-only wins, b-only wins, chi-squared, p). Yates-corrected."""
    keys = set(a) & set(b)
    a01 = sum(1 for k in keys if a[k][0] == a[k][1] and b[k][0] != b[k][1])
    b01 = sum(1 for k in keys if b[k][0] == b[k][1] and a[k][0] != a[k][1])
    n = a01 + b01
    if n == 0:
        return a01, b01, 0.0, 1.0
    chi = (abs(a01 - b01) - 1) ** 2 / n
    return a01, b01, chi, math.erfc(math.sqrt(chi / 2))


def main() -> None:
    results = Path(__file__).parent / "results"

    print("=" * 92)
    print("5-CLASS ACCURACY -- every model on the same taxonomy")
    print("=" * 92)
    print(f"{'run':46} {'n':>5} {'5-class':>8} {'delivered':>9} "
          f"{'no answer':>10} {'errors':>7}")
    rows = []
    for path in sorted(glob.glob(str(results / "*filmshots*.jsonl"))):
        name = Path(path).name[:-len(".jsonl")]
        n = ok = declined = errored = 0
        for line in Path(path).open(encoding="utf-8"):
            r = json.loads(line)
            n += 1
            if r.get("error"):
                errored += 1
                continue
            opts = options_for(r["index"])
            gold = C5.get(opts.get(r.get("gold")))
            raw = (r.get("raw") or "").strip()
            pred = raw if raw in CLASSES_5 else (
                C5.get(opts.get(r["pred"])) if r.get("pred") else None)
            if pred is None:
                declined += 1
            elif pred == gold:
                ok += 1
        rows.append((name, n, ok, n - errored, declined, errored))
    # Accuracy divides by what the PROVIDER delivered, not by rows attempted.
    # An HTTP 429 is a fact about a billing quota, not about the model's
    # eyesight; dividing by it turned "ran out of free tier at item 498" into
    # "gets a fifth of them wrong", which is the same class of mistake as every
    # fake zero in FINDINGS.md section 7 -- an infrastructure failure read as a
    # model result. An unparseable or refused answer IS counted wrong, since
    # that is the model's own behaviour, but it is broken out separately because
    # a run that is nothing but refusals measured nothing at all.
    for name, n, ok, delivered, declined, errored in sorted(
            rows, key=lambda r: -(r[2] / r[3] if r[3] else 0)):
        acc = ok / delivered * 100 if delivered else 0.0
        flag = "  <- truncated" if errored and errored / n > 0.05 else ""
        print(f"{name:46} {n:5} {acc:7.1f}% {delivered:7} {declined:10} "
              f"{errored:7}{flag}")
    print("\n  '5-class' is scored over delivered items: provider errors are out of\n"
          "  the denominator, refusals are not. A run whose rows are all in the\n"
          "  'no answer' column measured nothing -- see FINDINGS.md section 4.")

    available = {p.name[:-len(".filmshots.jsonl")]
                 for p in results.glob("*.filmshots.jsonl")}

    print()
    print("=" * 92)
    print("BALANCED ACCURACY -- is the leaderboard just measuring class bias?")
    print("=" * 92)
    # film-grab gold is 42% `medium`, and the file is SORTED BY CLASS: every
    # item from 498 on is `medium`. Two consequences. Plain accuracy pays a
    # model for guessing the majority class, and any run that stops early gets a
    # contiguous slice rather than a sample -- gemini-lite's quota cut at 498
    # handed it the four minority classes and none of the easy block.
    full = [r[0][:-len(".filmshots")] for r in rows
            if r[0].endswith(".filmshots") and r[1] >= 859]
    dist: dict[str, int] = {}
    ref = load("dinov2-shotscale") if "dinov2-shotscale" in available else {}
    for _, gold in ref.values():
        dist[gold] = dist.get(gold, 0) + 1
    if dist:
        tot = sum(dist.values())
        print("  gold balance: " + "  ".join(
            f"{c} {n} ({n / tot * 100:.0f}%)" for c, n in sorted(dist.items())))
    print()
    print(f"  {'model':24} {'plain':>7} {'balanced':>9} {'says medium':>12}  "
          f"per-class recall")
    table = []
    for m in full:
        d = load(m, keep_declines=True)   # a silent answer is a miss, not a pass
        if not d:
            continue
        per = {}
        for c in dist:
            ks = [k for k in d if d[k][1] == c]
            per[c] = sum(d[k][0] == c for k in ks) / len(ks) * 100 if ks else 0.0
        plain = sum(d[k][0] == d[k][1] for k in d) / len(d) * 100
        bal = sum(per.values()) / len(per) if per else 0.0
        med = sum(1 for k in d if d[k][0] == "medium") / len(d) * 100
        table.append((m, plain, bal, med, per))
    for m, plain, bal, med, per in sorted(table, key=lambda r: -r[2]):
        rec = "  ".join(f"{c[:5]}:{per[c]:4.0f}" for c in sorted(per))
        print(f"  {m:24} {plain:6.1f}% {bal:8.1f}% {med:11.1f}%  {rec}")
    print("\n  Ranking is unchanged by balancing, so no model is winning on\n"
          "  class bias. `full` is where they all fail -- and where the\n"
          "  classifier is strongest, which is the interesting part.")

    print()
    print("=" * 92)
    print("PAIRED SIGNIFICANCE (McNemar) -- is the gap real?")
    print("=" * 92)
    pairs = [("gemma-4-31b", "dinov2-shotscale"),
             ("gemma-4-26b-a4b", "dinov2-shotscale"),
             ("dinov2-shotscale", "qwen3.5-9b"),
             ("gemma-4-31b", "gemma-4-26b-a4b"),
             ("dinov2-shotscale", "qwen3.6-35b-a3b-fp8"),
             ("qwen3.5-9b", "qwen3.6-35b-a3b-fp8"),
             ("gemini-lite", "dinov2-shotscale"),
             ("gemma-4-31b", "gemini-lite"),
             ("gemini-lite", "qwen3.5-9b")]
    for na, nb in pairs:
        if na not in available or nb not in available:
            print(f"  skipped {na} vs {nb} (missing result)")
            continue
        a, b = load(na), load(nb)
        wa, wb, chi, p = mcnemar(a, b)
        verdict = "SIGNIFICANT" if p < 0.05 else "not significant"
        print(f"  {na:>18} vs {nb:<18} n={len(set(a) & set(b)):4}  "
              f"{wa:4} / {wb:<4}  chi2={chi:6.2f}  p={p:.2e}  {verdict}")

    print()
    print("=" * 92)
    print("AGREEMENT AS A CONFIDENCE SIGNAL -- the constants in s5_ingest.py")
    print("=" * 92)
    if "dinov2-shotscale" not in available:
        print("  no classifier result; nothing to cross-check against")
        return
    cls = load("dinov2-shotscale")
    print(f"  {'second tagger':<20} {'agree':>7} {'acc|agree':>10} "
          f"{'acc|disagree':>13} {'spread':>7} {'2nd right on disagree':>22}")
    # gemini-lite matters most here: if stage 3 calls it anyway, its shot-size
    # answer is already paid for, so its agreement with the classifier is a free
    # confidence signal rather than a second model to host.
    for m in ["gemma-4-31b", "gemma-4-26b-a4b", "gemini-lite", "qwen3.5-9b",
              "qwen3.6-35b-a3b-fp8", "qwen3-vl-8b", "qwen3-vl-4b",
              "qwen3-vl-2b"]:
        if m not in available:
            continue
        v = load(m)
        keys = set(cls) & set(v)
        agree = [k for k in keys if cls[k][0] == v[k][0]]
        dis = [k for k in keys if cls[k][0] != v[k][0]]
        if not agree or not dis:
            continue
        a_acc = sum(cls[k][0] == cls[k][1] for k in agree) / len(agree) * 100
        d_acc = sum(cls[k][0] == cls[k][1] for k in dis) / len(dis) * 100
        v_acc = sum(v[k][0] == v[k][1] for k in dis) / len(dis) * 100
        print(f"  {m:<20} {len(agree) / len(keys) * 100:6.1f}% {a_acc:9.1f}% "
              f"{d_acc:12.1f}% {a_acc - d_acc:6.1f} {v_acc:21.1f}%")
    print("\n  The last column is the one that decides whether a second opinion can\n"
          "  correct the classifier or only doubt it. Below ~50% it can only doubt.")


if __name__ == "__main__":
    main()
