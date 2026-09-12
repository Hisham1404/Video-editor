"""Re-score film-grab results with the current extract_answer.

The raw model text is stored in every row, and the option layout is a pure
function of the item index (seeded shuffle), so a parser fix can be applied
without spending GPU time re-running anything.
"""
import importlib.util, json, random, sys, glob, shutil
from pathlib import Path

spec = importlib.util.spec_from_file_location("rb", "run_benchmark.py")
rb = importlib.util.module_from_spec(spec); sys.modules["rb"] = rb
spec.loader.exec_module(rb)

LETTERS = "ABCDEFG"
KEYS = list(rb.FILMSHOTS_OPTIONS)

def options_for(index: int) -> dict[str, str]:
    order = KEYS[:]
    random.Random(index).shuffle(order)
    return {LETTERS[j]: rb.FILMSHOTS_OPTIONS[k] for j, k in enumerate(order)}

for path in sorted(glob.glob("results/*filmshots*.jsonl")):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    before_bad = sum(1 for r in rows if r.get("unparsed"))
    before_ok  = sum(1 for r in rows if r.get("correct"))
    shutil.copy(path, path + ".prefix-backup")
    for r in rows:
        if "error" in r:
            continue
        pred = rb.extract_answer(r.get("raw") or "", options_for(r["index"]))
        r["pred"] = pred
        r["unparsed"] = pred is None
        r["correct"] = bool(pred and pred == r.get("gold"))
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    after_bad = sum(1 for r in rows if r.get("unparsed"))
    after_ok  = sum(1 for r in rows if r.get("correct"))
    n = len(rows)
    print(f"  {Path(path).name:40} unparsed {before_bad:4} -> {after_bad:4} "
          f"| accuracy {before_ok/n*100:5.1f}% -> {after_ok/n*100:5.1f}%")
