#!/usr/bin/env python3
"""Review page: my pre-fill shown, yours is the one that counts.

    python review_page.py --frames frames_pexels --out review.html

WHY REVIEW AND NOT PLAIN LABELLING
----------------------------------
Pre-annotation plus human correction is faster than labelling from scratch, and
the human stays the arbiter, which is the part that matters here. A
vision-language model must not be the source of truth for a benchmark whose
headline comparison is a VLM against a classifier: where I misread a frame,
Gemini is likely to misread it the same way and would score as correct against
my label. On a 0.2-point gap that bias decides the result.

So every frame arrives with a suggestion and leaves with a decision.

The anchoring cost is real -- seeing a suggestion makes agreement more likely --
and it is the price of finishing. An unlabelled set measures nothing at all.
Two things reduce it: the 25 frames I found genuinely arguable are surfaced
first, while attention is freshest, and every changed frame is recorded so the
agreement rate is measurable rather than assumed.

THAT AGREEMENT RATE IS ITSELF A RESULT
--------------------------------------
If you change 5% of my labels, my reading of shot scale is close to yours and
the VLM-bias concern is small but real. If you change 30%, it is large, and it
also says the taxonomy is harder on vertical phone footage than on cinema --
which would be a finding about the app's real input, not about me.
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
<title>Shot scale review</title>
<style>
  :root { --bg:#14151a; --panel:#1d1f27; --line:#2c2f3a; --ink:#e8eaf0;
          --dim:#9aa0b0; --accent:#6ea8fe; --ok:#4ade80; --warn:#f0b429; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;
         display:grid; grid-template-columns:1fr 320px; height:100vh; }
  #stage { display:flex; align-items:center; justify-content:center;
           padding:16px; position:relative; overflow:hidden; }
  #frame { max-width:100%; max-height:calc(100vh - 32px); object-fit:contain;
           border-radius:6px; box-shadow:0 8px 40px rgba(0,0,0,.6); }
  #flag { position:absolute; top:22px; left:22px; background:var(--warn);
          color:#20160a; font-weight:700; font-size:11.5px; padding:4px 10px;
          border-radius:20px; display:none; }
  #side { background:var(--panel); border-left:1px solid var(--line); padding:16px;
          overflow-y:auto; display:flex; flex-direction:column; gap:13px; }
  h1 { font-size:15px; margin:0; }
  .meta { font-size:12px; color:var(--dim); }
  .bar { height:6px; background:var(--line); border-radius:3px; overflow:hidden; }
  .bar > i { display:block; height:100%; background:var(--accent); width:0%; transition:width .12s; }
  ul { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:4px; }
  li { display:flex; gap:9px; align-items:flex-start; padding:7px 9px;
       border:1px solid var(--line); border-radius:6px; cursor:pointer; }
  li:hover { border-color:var(--accent); }
  li.guess { border-color:var(--accent); background:rgba(110,168,254,.12); }
  li.guess::after { content:"my guess"; margin-left:auto; font-size:10px;
                    color:var(--accent); text-transform:uppercase; letter-spacing:.5px; }
  li.on { border-color:var(--ok); background:rgba(74,222,128,.13); }
  li.on::after { content:"yours"; margin-left:auto; font-size:10px; color:var(--ok);
                 text-transform:uppercase; letter-spacing:.5px; }
  kbd { background:var(--bg); border:1px solid var(--line); border-radius:4px;
        padding:1px 7px; font:600 12px/1.5 ui-monospace,monospace; color:var(--accent); }
  .nm { font-weight:600; } .ds { font-size:11.5px; color:var(--dim); }
  button { background:var(--accent); color:#08121f; border:0; border-radius:6px;
           padding:10px 12px; font:600 13px system-ui; cursor:pointer; width:100%; }
  button.ghost { background:transparent; color:var(--dim); border:1px solid var(--line); }
  .row { display:flex; gap:8px; }
  .tally { font-size:11.5px; color:var(--dim); border-top:1px solid var(--line);
           padding-top:10px; display:flex; flex-direction:column; gap:2px; }
  .tally b { color:var(--ink); }
  .note { font-size:11.5px; color:var(--dim); border-top:1px solid var(--line); padding-top:10px; }
  #done { position:absolute; inset:0; display:none; align-items:center; justify-content:center;
          flex-direction:column; gap:12px; text-align:center; padding:30px; }
</style>
<div id="stage">
  <img id="frame" alt=""><div id="flag">I wasn't sure about this one</div>
  <div id="done"><h1 style="font-size:20px">All 267 reviewed</h1>
    <p class="meta" id="summary"></p></div>
</div>
<div id="side">
  <div><h1>Shot scale — review</h1><div class="meta" id="pos">—</div></div>
  <div class="bar"><i id="prog"></i></div>
  <button id="accept">Agree &nbsp;<kbd style="color:#08121f;border-color:#08121f">space</kbd></button>
  <ul id="opts"></ul>
  <div class="row">
    <button class="ghost" id="back">← Back</button>
    <button class="ghost" id="skip">Unsure (s)</button>
  </div>
  <button id="save">Save labels.json</button>
  <button class="ghost" id="copy" style="display:none">Copy to clipboard</button>
  <textarea id="out" readonly style="display:none;height:90px;background:var(--bg);
    color:var(--dim);border:1px solid var(--line);border-radius:6px;font:11px
    ui-monospace,monospace;padding:6px"></textarea>
  <div class="tally" id="tally"></div>
  <div class="note">
    <b>Space</b> agrees with my guess and moves on. <b>1–7</b> overrides it.
    <b>s</b> drops the frame entirely — use it when two sizes are equally
    defensible; an ambiguous label is worse than a missing one.
    <br><br>The 25 I found hardest come first.
  </div>
</div>
<script>
const FRAMES=__FRAMES__, DIR=__DIR__, CLASSES=__CLASSES__, GUESS=__GUESS__;
let labels={}, changed={}, dropped={};
try { const s=JSON.parse(localStorage.getItem("shotscale_review")||"{}");
      labels=s.labels||{}; changed=s.changed||{}; dropped=s.dropped||{}; } catch(e){}
let i=0; const $=id=>document.getElementById(id);
// Probe once rather than trusting it. On file:// the origin is opaque and some
// browsers refuse storage outright; the user needs to know that BEFORE
// labelling 267 frames, not after a reload eats them.
let STORAGE_OK=false;
try { localStorage.setItem("__t","1"); localStorage.removeItem("__t"); STORAGE_OK=true; } catch(e){}

CLASSES.forEach(([k,id,name,desc])=>{
  const li=document.createElement("li"); li.dataset.id=id;
  li.innerHTML=`<kbd>${k}</kbd><span><span class="nm">${name}</span><br><span class="ds">${desc}</span></span>`;
  li.onclick=()=>pick(id); $("opts").appendChild(li);
});
function persist(){ try{ localStorage.setItem("shotscale_review",
  JSON.stringify({labels,changed,dropped})); }catch(e){} }

function render(){
  const n=FRAMES.length, done=Object.keys(labels).length+Object.keys(dropped).length;
  $("prog").style.width=(done/n*100)+"%";
  const nch=Object.keys(changed).length, ndr=Object.keys(dropped).length;
  const agreed=Object.keys(labels).length-nch;
  $("tally").innerHTML=
    `<div><b>${done}</b> of ${n} reviewed</div>`+
    `<div>agreed with me: <b>${agreed}</b></div>`+
    `<div>you changed: <b>${nch}</b></div>`+
    `<div>dropped: <b>${ndr}</b></div>`+
    (done? `<div style="margin-top:4px">agreement so far: <b>${(agreed/(agreed+nch||1)*100).toFixed(1)}%</b></div>`:"")+
    (STORAGE_OK? "" : `<div style="margin-top:6px;color:var(--warn)"><b>Browser storage is blocked.</b>
       Nothing is saved until you click Save — do not reload this page.</div>`);
  if(i>=n){
    $("frame").style.display="none"; $("flag").style.display="none";
    $("done").style.display="flex"; $("pos").textContent="finished";
    $("summary").innerHTML=`You agreed with ${agreed}, changed ${nch}, dropped ${ndr}.<br>`+
      `Click <b>Save labels.json</b> and put it in the frames folder.`;
    [...$("opts").children].forEach(li=>li.classList.remove("on","guess")); return;
  }
  $("frame").style.display=""; $("done").style.display="none";
  const f=FRAMES[i];
  $("frame").src=DIR+"/"+f.frame;
  $("flag").style.display=f.hard?"block":"none";
  $("pos").textContent=`${i+1} / ${n}${f.hard?" · flagged":""} · ${f.frame}`;
  const g=GUESS[f.frame], mine=labels[f.frame];
  [...$("opts").children].forEach(li=>{
    li.classList.toggle("guess", li.dataset.id===g && !mine);
    li.classList.toggle("on", li.dataset.id===mine);
  });
}
function commit(id,isChange){
  const f=FRAMES[i].frame;
  labels[f]=id; delete dropped[f];
  if(isChange) changed[f]=id; else delete changed[f];
  persist(); i++; render();
}
function pick(id){ if(i<FRAMES.length) commit(id, id!==GUESS[FRAMES[i].frame]); }
function accept(){ if(i<FRAMES.length) commit(GUESS[FRAMES[i].frame], false); }
function drop(){ if(i>=FRAMES.length) return; const f=FRAMES[i].frame;
  delete labels[f]; delete changed[f]; dropped[f]=1; persist(); i++; render(); }
function back(){ if(i>0){ i--; render(); } }

addEventListener("keydown",e=>{
  if(e.key===" "||e.key==="Enter"){ e.preventDefault(); return accept(); }
  if(e.key==="s") return drop();
  if(e.key==="ArrowLeft"||e.key==="Backspace") return back();
  const hit=CLASSES.find(c=>c[0]===e.key); if(hit) pick(hit[1]);
});
$("accept").onclick=accept; $("skip").onclick=drop; $("back").onclick=back;
function payload(){ return JSON.stringify({labels,changed,dropped},null,1); }
$("save").onclick=()=>{
  // ONE file. Two downloads from one page is blocked by every browser unless
  // the user grants permission, and the refusal is silent -- the button looks
  // like it worked while the file on disk stayed eight labels old.
  const blob=new Blob([payload()],{type:"application/json"});
  const a=document.createElement("a"); a.href=URL.createObjectURL(blob);
  a.download="labels.json"; a.click();
  $("out").value=payload(); $("out").style.display="block";
  $("copy").style.display="block";
};
$("copy").onclick=async()=>{
  // Downloads can be blocked by policy or a sandbox; clipboard is the fallback
  // that does not depend on the file system at all.
  try { await navigator.clipboard.writeText(payload());
        $("copy").textContent="Copied — paste into labels.json"; }
  catch(e){ $("out").select(); document.execCommand("copy");
            $("copy").textContent="Copied (fallback)"; }
};
const first=FRAMES.findIndex(f=>!(f.frame in labels)&&!(f.frame in dropped));
i=first===-1?FRAMES.length:first;
render();
</script>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default="frames_pexels")
    ap.add_argument("--out", default="review.html")
    a = ap.parse_args()

    fdir = Path(a.frames)
    guess = json.loads((fdir / "prefill.json").read_text(encoding="utf-8"))
    hard = set(json.loads((fdir / "uncertain.json").read_text(encoding="utf-8")))
    order = json.loads(Path("sheets_px/order.json").read_text(encoding="utf-8"))

    # Hard ones first, while attention is freshest -- they are where a human
    # decision is worth the most and where my guess is least trustworthy.
    frames = ([{"frame": f, "hard": True} for f in order if f in hard]
              + [{"frame": f, "hard": False} for f in order if f not in hard])

    html = (PAGE.replace("__FRAMES__", json.dumps(frames))
                .replace("__DIR__", json.dumps(fdir.name))
                .replace("__CLASSES__", json.dumps([list(c) for c in CLASSES]))
                .replace("__GUESS__", json.dumps(guess)))
    Path(a.out).write_text(html, encoding="utf-8")
    print(f"wrote {a.out} — {len(frames)} frames, {len(hard)} flagged first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
