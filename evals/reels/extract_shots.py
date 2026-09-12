#!/usr/bin/env python3
"""Extract ONE frame per distinct shot, and reject what cannot be labelled.

    python extract_shots.py --videos DIR --out frames/

WHY NOT `label.py extract`
--------------------------
That samples N frames per video at fixed intervals. On a 7-second reel with
--per-video 16 that is a frame every 0.45 seconds, and a reel shot lasts a beat
or two, so consecutive samples land inside the same shot. Measured on the first
11 reels: 176 frames collapsed to 96 perceptual clusters, one of them holding
36 frames.

That matters beyond tidiness. 176 correlated items do not carry the statistical
weight of 176 independent ones -- every confidence interval computed from them
is too narrow, and the whole reason this set exists is to separate models that
sit 0.2 points apart. A set that reports a precision it does not have is worse
than a small honest one.

So: cut on shot boundaries, take the middle frame of each shot, then drop
frames that cannot carry a shot-scale label at all.

WHAT GETS REJECTED, AND WHY IT IS NOT OVER-FILTERING
----------------------------------------------------
Shot scale is defined against a SUBJECT -- "full shot" means a whole body,
"close-up" means head and shoulders. Frames with no subject have no shot scale,
and forcing a label onto them injects noise into the gold standard rather than
difficulty.

    near-black      fades, and letterboxed verticals where the bars dominate.
                    37 of the first 176 frames were darker than 25/255.
    low-texture     title cards, solid-colour graphics, UI screenshots -- flat
                    regions with hard edges and little photographic detail.
    near-duplicate  same shot reached twice, or a repeated cutaway.

Rejected frames are still written to `rejected/` rather than deleted, because
"the model must handle frames with no subject" is a real product question for
stage 3 -- it just is not a shot-scale question.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}


def shot_boundaries(video: Path, threshold: float) -> list[float]:
    """Timestamps of detected cuts, via ffmpeg's scene score."""
    cmd = ["ffmpeg", "-nostdin", "-i", str(video), "-filter_complex",
           f"select='gt(scene,{threshold})',metadata=print:file=-",
           "-an", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    times = []
    for line in (r.stdout + r.stderr).splitlines():
        if "pts_time:" in line:
            try:
                times.append(float(line.split("pts_time:")[1].split()[0]))
            except (ValueError, IndexError):
                pass
    return sorted(set(times))


def duration(video: Path) -> float | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(video)],
            capture_output=True, text=True, check=True)
        return float(r.stdout.strip())
    except Exception:
        return None


def dimensions(video: Path) -> tuple[int, int] | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
             str(video)], capture_output=True, text=True, check=True)
        w, h = r.stdout.strip().splitlines()[0].split("x")
        return int(w), int(h)
    except Exception:
        return None


def grab(video: Path, t: float, dst: Path) -> bool:
    cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{t:.3f}",
           "-i", str(video), "-frames:v", "1", "-q:v", "2", str(dst)]
    return subprocess.run(cmd).returncode == 0


def ahash(path: Path, n: int = 16) -> int:
    from PIL import Image
    im = Image.open(path).convert("L").resize((n, n), Image.LANCZOS)
    px = list(im.getdata())
    avg = sum(px) / len(px)
    return sum(1 << i for i, v in enumerate(px) if v > avg)


def describe(path: Path) -> tuple[float, float]:
    """(mean brightness, mean absolute gradient) — brightness finds fades,
    gradient separates photographic frames from flat graphics and title cards."""
    from PIL import Image
    im = Image.open(path).convert("L").resize((128, 128), Image.LANCZOS)
    px = list(im.getdata())
    brightness = sum(px) / len(px)
    g = 0
    for y in range(128):
        row = y * 128
        for x in range(127):
            g += abs(px[row + x] - px[row + x + 1])
    return brightness, g / (128 * 127)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", required=True)
    ap.add_argument("--out", default="frames")
    ap.add_argument("--threshold", type=float, default=0.30,
                    help="ffmpeg scene score for a cut; lower finds more")
    ap.add_argument("--min-brightness", type=float, default=25.0)
    ap.add_argument("--min-gradient", type=float, default=6.0)
    ap.add_argument("--hash-distance", type=int, default=20,
                    help="bits (of 256) below which two frames are the same shot")
    a = ap.parse_args()

    src, out = Path(a.videos), Path(a.out)
    rej = out / "rejected"
    out.mkdir(parents=True, exist_ok=True)
    rej.mkdir(exist_ok=True)

    videos = [p for p in sorted(src.iterdir()) if p.suffix.lower() in VIDEO_EXT]
    if not videos:
        sys.exit(f"no videos in {src}")

    kept: list[dict] = []
    hashes: list[int] = []
    counts = {"dark": 0, "flat": 0, "duplicate": 0}

    for vid in videos:
        dur = duration(vid)
        if dur is None:
            print(f"  skip {vid.name}: unreadable")
            continue
        wh = dimensions(vid)
        w, h = wh if wh else (0, 0)
        orient = ("vertical" if h > w else "landscape" if w > h else "square") if wh else "unknown"

        cuts = [0.0] + shot_boundaries(vid, a.threshold) + [dur]
        shots = [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)
                 if cuts[i + 1] - cuts[i] > 0.35]     # ignore flash frames
        print(f"  {vid.name:22} {dur:5.1f}s  {orient:9} {len(shots):3} shots", end="")

        got = 0
        for k, (s, e) in enumerate(shots):
            tmp = out / f"{vid.stem}_s{k:02d}.jpg"
            if not grab(vid, (s + e) / 2, tmp):
                continue
            bright, grad = describe(tmp)
            if bright < a.min_brightness:
                tmp.replace(rej / tmp.name); counts["dark"] += 1; continue
            if grad < a.min_gradient:
                tmp.replace(rej / tmp.name); counts["flat"] += 1; continue
            hv = ahash(tmp)
            if any(bin(hv ^ o).count("1") <= a.hash_distance for o in hashes):
                tmp.replace(rej / tmp.name); counts["duplicate"] += 1; continue
            hashes.append(hv)
            kept.append({"frame": tmp.name, "source": vid.name,
                         "orientation": orient, "width": w, "height": h})
            got += 1
        print(f" -> kept {got}")

    man = out / "manifest.tsv"
    man.write_text("frame\tsource\torientation\twidth\theight\n" +
                   "".join(f"{r['frame']}\t{r['source']}\t{r['orientation']}\t"
                           f"{r['width']}\t{r['height']}\n" for r in kept),
                   encoding="utf-8")
    (out / "rejected" / "counts.json").write_text(json.dumps(counts, indent=1))

    v = sum(1 for r in kept if r["orientation"] == "vertical")
    print(f"\nkept {len(kept)} distinct labellable frames "
          f"({v} vertical, {len(kept) - v} other)")
    print(f"rejected: {counts['dark']} near-black, {counts['flat']} flat/graphic, "
          f"{counts['duplicate']} duplicate  (in {rej}/)")
    if len(kept) < 150:
        need = 150 - len(kept)
        print(f"\n  {len(kept)} is below the 150 this set needs to separate models "
              f"that sit\n  a point apart. Roughly {need} more distinct shots are "
              f"required — add more\n  reels, ideally vertical, and re-run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
