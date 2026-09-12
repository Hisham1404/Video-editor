#!/usr/bin/env python3
"""Generate a single-file browser labeller for the extracted frames.

    python make_page.py --frames frames/ --out labeller.html

WHY NOT JUST USE `label.py label`
---------------------------------
That path opens each frame in the OS image viewer and reads a keystroke from
the terminal. For six frames it is fine. For 176 it means 176 viewer windows,
alt-tabbing between two applications for every single decision, and a labelling
session that is unpleasant enough to not get finished -- which is the actual
failure mode here, since an unfinished test set measures nothing.

This writes one HTML file that shows the frame full-size, takes 1-7 as a
keypress, and moves on. The frame list is baked in at generation time because a
page opened from file:// cannot fetch a local manifest -- Chrome treats it as a
cross-origin read -- but <img src="frames/x.jpg"> works fine.

Labels are held in the page and written out as labels.json on demand, which
label.py's `export` then reads. localStorage is attempted as a crash guard and
is not relied on: on file:// the origin is opaque and some browsers refuse it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CLASSES = [
    ("1", "extremeLongShot", "Extreme long", "figure is a speck; the place is the subject"),
    ("2", "longShot", "Long", "whole body, space above and below"),
    ("3", "fullShot", "Full", "whole body, roughly fills frame height"),
    ("4", "mediumShot", "Medium", "waist up"),
    ("5", "mediumCloseUp", "Medium close", "chest up"),
    ("6", "closeUp", "Close-up", "head and shoulders"),
    ("7", "detail", "Detail", "part of a face or object; no whole face"),
]

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Shot scale labeller</title>
<style>
  :root {
    --bg:#14151a; --panel:#1d1f27; --line:#2c2f3a; --ink:#e8eaf0;
    --dim:#9aa0b0; --accent:#6ea8fe; --ok:#4ade80; --skip:#f0b429;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;
         display:grid; grid-template-columns:1fr 300px; height:100vh; }
  #stage { display:flex; align-items:center; justify-content:center;
           padding:16px; overflow:hidden; position:relative; }
  #frame { max-width:100%; max-height:calc(100vh - 32px);
           object-fit:contain; border-radius:6px;
           box-shadow:0 8px 40px rgba(0,0,0,.6); }
  #side { background:var(--panel); border-left:1px solid var(--line);
          padding:16px; overflow-y:auto; display:flex; flex-direction:column; gap:14px; }
  h1 { font-size:15px; margin:0; letter-spacing:.2px; }
  .meta { font-size:12px; color:var(--dim); }
  .bar { height:6px; background:var(--line); border-radius:3px; overflow:hidden; }
  .bar > i { display:block; height:100%; background:var(--accent); width:0%; transition:width .15s; }
  ul { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:5px; }
  li { display:flex; gap:9px; align-items:flex-start; padding:7px 9px;
       border:1px solid var(--line); border-radius:6px; cursor:pointer; }
  li:hover { border-color:var(--accent); }
  li.on { border-color:var(--ok); background:rgba(74,222,128,.10); }
  kbd { background:var(--bg); border:1px solid var(--line); border-radius:4px;
        padding:1px 7px; font:600 12px/1.5 ui-monospace,monospace; color:var(--accent); }
  .nm { font-weight:600; }
  .ds { font-size:11.5px; color:var(--dim); }
  button { background:var(--accent); color:#08121f; border:0; border-radius:6px;
           padding:9px 12px; font:600 13px system-ui; cursor:pointer; width:100%; }
  button.ghost { background:transparent; color:var(--dim); border:1px solid var(--line); }
  .row { display:flex; gap:8px; }
  .tally { font-size:11.5px; color:var(--dim); display:flex;
           flex-direction:column; gap:2px; border-top:1px solid var(--line); padding-top:10px; }
  .tally b { color:var(--ink); font-weight:600; }
  .note { font-size:11.5px; color:var(--dim); border-top:1px solid var(--line); padding-top:10px; }
  #done { position:absolute; inset:0; display:none; align-items:center;
          justify-content:center; flex-direction:column; gap:14px; text-align:center; padding:30px; }
</style>
<div id="stage">
  <img id="frame" alt="">
  <div id="done"><h1 style="font-size:20px">All frames seen</h1>
    <p class="meta">Click <b>Save labels.json</b>, put the file in the frames folder,<br>then run the export command.</p></div>
</div>
<div id="side">
  <div>
    <h1>Shot scale</h1>
    <div class="meta" id="pos">—</div>
  </div>
  <div class="bar"><i id="prog"></i></div>
  <ul id="opts"></ul>
  <div class="row">
    <button class="ghost" id="back">← Back</button>
    <button class="ghost" id="skip">Skip (s)</button>
  </div>
  <button id="save">Save labels.json</button>
  <div class="tally" id="tally"></div>
  <div class="note">
    Judge by how much of the <b>subject</b> fills the frame, not how far the
    camera looks. Vertical crops feel tighter — apply the same rule anyway.
    <br><br>Torn between two neighbours? <b>Skip.</b> A guessed label is worse
    than a missing one.
  </div>
</div>
<script>
const FRAMES = __FRAMES__;
const DIR    = __DIR__;
const CLASSES= __CLASSES__;
let labels = {};
try { labels = JSON.parse(localStorage.getItem("shotscale") || "{}"); } catch (e) {}

let i = 0;
const $ = id => document.getElementById(id);

CLASSES.forEach(([key, id, name, desc]) => {
  const li = document.createElement("li");
  li.dataset.id = id;
  li.innerHTML = `<kbd>${key}</kbd><span><span class="nm">${name}</span><br><span class="ds">${desc}</span></span>`;
  li.onclick = () => pick(id);
  $("opts").appendChild(li);
});

function persist() {
  try { localStorage.setItem("shotscale", JSON.stringify(labels)); } catch (e) {}
}

function render() {
  const n = FRAMES.length;
  const labelled = Object.keys(labels).length;
  $("prog").style.width = (labelled / n * 100) + "%";
  const counts = {};
  for (const v of Object.values(labels)) counts[v] = (counts[v] || 0) + 1;
  $("tally").innerHTML = `<div><b>${labelled}</b> of ${n} labelled</div>` +
    CLASSES.map(([, id, name]) => counts[id] ? `<div>${name}: <b>${counts[id]}</b></div>` : "").join("");

  if (i >= n) {
    $("frame").style.display = "none";
    $("done").style.display = "flex";
    $("pos").textContent = "finished";
    [...$("opts").children].forEach(li => li.classList.remove("on"));
    return;
  }
  $("frame").style.display = "";
  $("done").style.display = "none";
  const f = FRAMES[i];
  $("frame").src = DIR + "/" + f.frame;
  $("pos").textContent = `${i + 1} / ${n} · ${f.orientation} · ${f.frame}`;
  [...$("opts").children].forEach(li => li.classList.toggle("on", labels[f.frame] === li.dataset.id));
}

function pick(id) {
  if (i >= FRAMES.length) return;
  labels[FRAMES[i].frame] = id;
  persist(); i++; render();
}
function skip() { if (i < FRAMES.length) { delete labels[FRAMES[i].frame]; persist(); i++; render(); } }
function back() { if (i > 0) { i--; render(); } }

addEventListener("keydown", e => {
  if (e.key === "s") return skip();
  if (e.key === "ArrowLeft" || e.key === "Backspace") return back();
  if (e.key === "ArrowRight") { if (i < FRAMES.length) { i++; render(); } return; }
  const hit = CLASSES.find(c => c[0] === e.key);
  if (hit) pick(hit[1]);
});
$("skip").onclick = skip;
$("back").onclick = back;
$("save").onclick = () => {
  const blob = new Blob([JSON.stringify(labels, null, 1)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "labels.json";
  a.click();
};

// Resume where the last session stopped rather than at the top.
const firstUnlabelled = FRAMES.findIndex(f => !(f.frame in labels));
i = firstUnlabelled === -1 ? FRAMES.length : firstUnlabelled;
render();
</script>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default="frames")
    ap.add_argument("--out", default="labeller.html")
    a = ap.parse_args()

    fdir = Path(a.frames)
    manifest = fdir / "manifest.tsv"
    if manifest.exists():
        rows = [l.split("\t") for l in
                manifest.read_text(encoding="utf-8").splitlines()[1:] if l.strip()]
        frames = [{"frame": r[0], "orientation": r[2]} for r in rows]
    else:
        frames = [{"frame": p.name, "orientation": "?"}
                  for p in sorted(fdir.glob("*.jpg"))]
    if not frames:
        raise SystemExit(f"no frames in {fdir}")

    # Interleave sources so consecutive frames come from different videos.
    # Sixteen frames of one reel in a row invites anchoring on the previous
    # answer, and that correlation would be baked into the labels.
    by_src: dict[str, list] = {}
    for f in frames:
        by_src.setdefault(f["frame"].rsplit("_", 1)[0], []).append(f)
    mixed, pools = [], list(by_src.values())
    while any(pools):
        for pool in pools:
            if pool:
                mixed.append(pool.pop(0))

    # When every frame is its own source -- the Pexels set, one frame per video
    # -- the interleave above is a no-op and the manifest order survives, which
    # means all fifty `wide` results arrive in a block. Fifty of one framing in
    # a row is the same anchoring trap from the other direction, so shuffle.
    # Seeded, so regenerating the page does not reshuffle a half-finished job
    # and strand the labels already collected.
    import random as _r
    if len(by_src) == len(frames):
        _r.Random(20260913).shuffle(mixed)

    html = (PAGE
            .replace("__FRAMES__", json.dumps(mixed))
            .replace("__DIR__", json.dumps(fdir.name))
            .replace("__CLASSES__", json.dumps([list(c) for c in CLASSES])))
    Path(a.out).write_text(html, encoding="utf-8")
    v = sum(1 for f in mixed if f["orientation"] == "vertical")
    print(f"wrote {a.out} — {len(mixed)} frames ({v} vertical, {len(mixed)-v} other)")
    print(f"open it in a browser, label, then save labels.json into {fdir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
