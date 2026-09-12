#!/usr/bin/env python3
"""Label shot scale on your own reel frames.

WHY THIS EXISTS
---------------
Every benchmark this project has run -- ShotBench (3572 items) and film-grab
(859) -- is Oscar-nominated feature film: landscape, professionally lit, shot on
cinema cameras. The app ingests vertical phone video: handheld, mixed lighting,
9:16, usually one subject at arm's length.

"Medium close-up" on a 2.39:1 anamorphic frame and on a 9:16 selfie are not the
same visual problem, and nothing measured so far says which models survive the
shift. No public dataset closes this: every cinematography set is built from
cinema, because that is where film-studies annotators are. So it has to be made.

150-200 labelled frames is enough to separate models that currently sit within
one point of each other.

USAGE
-----
    python label.py extract  --videos DIR --out frames/ --per-video 6
    python label.py label    --frames frames/            # the clicking part
    python label.py export   --out reels_test.tsv       # harness-ready

Then, from evals/shotbench:

    python run_benchmark.py --dataset reels \\
        --reels-tsv ../reels/reels_test.tsv --models <model>

HOW TO LABEL CONSISTENTLY
-------------------------
Judge by how much of the SUBJECT fills the frame, not by how far the camera
looks. Vertical crops make everything feel tighter, so the same rule has to be
applied deliberately:

    extreme long   figure is a speck; the location is the subject
    long           whole body with space above and below
    full           whole body, roughly filling frame height
    medium         waist up
    medium close   chest up
    close          head and shoulders
    detail         part of a face or an object; no whole face

Two rules that matter more than the definitions:

  Label what is there, not what was intended. A badly framed shot still has a
  shot scale.

  When torn between two adjacent sizes, press `s` to skip. An ambiguous label is
  worse than a missing one -- it becomes noise in every score computed from it.
  The film-grab set found the same thing: its reviewer overruled the machine on
  53-65% of low-confidence frames, because adjacent shot sizes are genuinely
  hard.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

# Identical to FILMSHOTS_OPTIONS in the harness so scores are comparable.
CLASSES = {
    "1": ("extremeLongShot", "Extreme long shot — figure is a speck"),
    "2": ("longShot", "Long shot — whole body, space around it"),
    "3": ("fullShot", "Full shot — whole body fills frame height"),
    "4": ("mediumShot", "Medium shot — waist up"),
    "5": ("mediumCloseUp", "Medium close-up — chest up"),
    "6": ("closeUp", "Close-up — head and shoulders"),
    "7": ("detail", "Detail / insert — part of a face or object"),
}

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}


def extract(args: argparse.Namespace) -> None:
    """Pull evenly spaced frames from each video via ffmpeg.

    Evenly spaced rather than random: a reel's opening and closing shots are
    systematically different from its middle, and sampling that misses them
    measures a different distribution than the one the app sees.
    """
    src, out = Path(args.videos), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    videos = [p for p in sorted(src.iterdir()) if p.suffix.lower() in VIDEO_EXT]
    if not videos:
        sys.exit(f"no videos in {src} (looked for {sorted(VIDEO_EXT)})")

    # Record each frame's source orientation. The whole reason this set exists
    # is that every public benchmark is landscape cinema while the app ingests
    # vertical phone video -- so if the reels supplied are a mix, that has to be
    # recoverable at scoring time or the set silently fails to answer its own
    # question. A manifest rather than a filename suffix, so relabelling or
    # re-extracting cannot quietly change what a frame claims to be.
    manifest = out / "manifest.tsv"
    seen = set()
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines()[1:]:
            if line.strip():
                seen.add(line.split("\t")[0])
    rows, total = [], 0
    counts = {"vertical": 0, "landscape": 0, "square": 0}

    for vid in videos:
        dur = _duration(vid)
        if dur is None:
            print(f"  skip {vid.name}: could not read duration")
            continue
        wh = _dimensions(vid)
        if wh is None:
            orient, w, h = "unknown", 0, 0
        else:
            w, h = wh
            orient = ("vertical" if h > w else
                      "landscape" if w > h else "square")
        # Inset from both ends: the first and last frames are often black or a
        # title card, which are not shots and would pollute the set.
        for i in range(args.per_video):
            t = dur * (i + 0.5) / args.per_video
            dst = out / f"{vid.stem}_{i:02d}.jpg"
            if not dst.exists():
                cmd = ["ffmpeg", "-nostdin", "-loglevel", "error",
                       "-ss", f"{t:.3f}", "-i", str(vid), "-frames:v", "1",
                       "-q:v", "3", str(dst)]
                if subprocess.run(cmd).returncode != 0:
                    continue
                total += 1
            if dst.name not in seen:
                rows.append(f"{dst.name}\t{vid.name}\t{orient}\t{w}\t{h}")
                seen.add(dst.name)
                counts[orient] = counts.get(orient, 0) + 1

    if rows:
        new = not manifest.exists()
        with manifest.open("a", encoding="utf-8") as fh:
            if new:
                fh.write("frame\tsource\torientation\twidth\theight\n")
            fh.write("\n".join(rows) + "\n")

    print(f"extracted {total} frames from {len(videos)} videos into {out}/")
    print(f"  orientation: " + "  ".join(f"{k} {v}" for k, v in counts.items() if v))
    if counts.get("landscape", 0) > counts.get("vertical", 0):
        print("  NOTE: more landscape than vertical frames. This set exists to")
        print("  test vertical phone video against landscape-cinema benchmarks;")
        print("  a mostly-landscape set measures something closer to what the")
        print("  existing benchmarks already cover. Scores can still be split by")
        print("  orientation via manifest.tsv, but add vertical reels if you can.")
    print(f"next:  python label.py label --frames {out}")


def _dimensions(path: Path) -> tuple[int, int] | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=p=0:s=x", str(path)],
            capture_output=True, text=True, check=True)
        w, h = r.stdout.strip().split("\n")[0].split("x")
        return int(w), int(h)
    except Exception:
        return None


def _duration(path: Path) -> float | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, check=True)
        return float(r.stdout.strip())
    except Exception:
        return None


def label(args: argparse.Namespace) -> None:
    """Show each frame and record one keystroke.

    Progress is written after every single label. Labelling is tedious and gets
    interrupted; losing an hour of it to a closed terminal would be the end of
    the exercise in practice.
    """
    frames_dir = Path(args.frames)
    store = frames_dir / "labels.json"
    labels: dict[str, str] = json.loads(store.read_text()) if store.exists() else {}

    frames = sorted(p for p in frames_dir.iterdir()
                    if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    todo = [p for p in frames if p.name not in labels]
    if not todo:
        print(f"all {len(frames)} frames already labelled. "
              f"next:  python label.py export")
        return

    # Shuffled so fatigue spreads across videos instead of concentrating on
    # whichever one happens to sort last.
    random.Random(0).shuffle(todo)

    print(f"{len(labels)} done, {len(todo)} to go.\n")
    for k, (_, desc) in CLASSES.items():
        print(f"  {k}  {desc}")
    print("  s  skip (genuinely ambiguous — better than a wrong label)")
    print("  q  save and quit\n")

    _open_viewer(todo[0])
    for i, frame in enumerate(todo, 1):
        _open_viewer(frame)
        while True:
            key = input(f"[{i}/{len(todo)}] {frame.name} > ").strip().lower()
            if key == "q":
                store.write_text(json.dumps(labels, indent=1))
                print(f"saved {len(labels)} labels")
                return
            if key == "s":
                break
            if key in CLASSES:
                labels[frame.name] = CLASSES[key][0]
                store.write_text(json.dumps(labels, indent=1))
                break
            print("  press 1-7, s to skip, q to quit")
    store.write_text(json.dumps(labels, indent=1))
    print(f"\ndone — {len(labels)} labelled. next:  python label.py export")


def _open_viewer(path: Path) -> None:
    """Show the frame in the OS image viewer. Best-effort: if it fails, the
    filename is still printed and the frame can be opened by hand."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(["cmd", "/c", "start", "", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def export(args: argparse.Namespace) -> None:
    """Write the harness's TSV format: relative path, class name."""
    frames_dir = Path(args.frames)
    store = frames_dir / "labels.json"
    if not store.exists():
        sys.exit(f"no labels at {store} — run `label` first")
    labels: dict[str, str] = json.loads(store.read_text())
    if not labels:
        sys.exit("labels.json is empty")

    out = Path(args.out)
    rows = [f"{frames_dir.name}/{name}\t{cls}" for name, cls in sorted(labels.items())]
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")

    from collections import Counter
    dist = Counter(labels.values())
    print(f"wrote {len(rows)} items to {out}\n")
    print("  class distribution:")
    for cls, n in dist.most_common():
        print(f"    {cls:18} {n:4}  {n/len(labels)*100:5.1f}%")
    if len(dist) < 4:
        print("\n  WARNING: fewer than 4 classes present. A model can score well "
              "here by guessing the majority class — label a wider spread.")
    thin = [c for c, n in dist.items() if n < 10]
    if thin:
        print(f"\n  WARNING: under 10 examples of {thin}. Per-class accuracy on "
              "those is not measurable; treat only the overall number as real.")


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="label.py",
        description="Build a shot-scale test set from your own reels.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="pull evenly spaced frames from videos")
    e.add_argument("--videos", required=True, help="directory of source reels")
    e.add_argument("--out", default="frames", help="where to write frames")
    e.add_argument("--per-video", type=int, default=6,
                   help="frames per video; 150-200 total is the target")
    e.set_defaults(fn=extract)

    l = sub.add_parser("label", help="label the extracted frames")
    l.add_argument("--frames", default="frames", help="directory of frames")
    l.set_defaults(fn=label)

    x = sub.add_parser("export", help="write the harness TSV")
    x.add_argument("--frames", default="frames", help="directory of frames")
    x.add_argument("--out", default="reels_test.tsv", help="TSV to write")
    x.set_defaults(fn=export)

    args = ap.parse_args()
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
