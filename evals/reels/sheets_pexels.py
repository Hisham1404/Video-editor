"""Contact sheets for the vertical Pexels set, in the page's shuffled order.

Order must match make_page.py exactly, or a pre-filled label lands on the wrong
frame. Both read the manifest and apply the same seeded shuffle.
"""
from PIL import Image, ImageDraw
from pathlib import Path
import json, random

fdir = Path("frames_pexels")
rows = [l.split("\t") for l in (fdir/"manifest.tsv").read_text(encoding="utf-8").splitlines()[1:] if l.strip()]
frames = [{"frame": r[0], "group": r[5]} for r in rows]
random.Random(20260913).shuffle(frames)          # same seed as make_page.py

COLS, ROWS_N, CW, CH, PAD, HDR = 5, 3, 258, 460, 8, 22
per = COLS * ROWS_N
Path("sheets_px").mkdir(exist_ok=True)
order = [f["frame"] for f in frames]
Path("sheets_px/order.json").write_text(json.dumps(order))

for s in range((len(frames)+per-1)//per):
    chunk = frames[s*per:(s+1)*per]
    W = COLS*(CW+PAD)+PAD
    H = ROWS_N*(CH+HDR+PAD)+PAD
    sheet = Image.new("RGB", (W, H), (22,23,28))
    d = ImageDraw.Draw(sheet)
    for k, f in enumerate(chunk):
        idx = s*per+k
        cx = PAD + (k % COLS)*(CW+PAD)
        cy = PAD + (k // COLS)*(CH+HDR+PAD)
        d.text((cx+3, cy+4), f"#{idx}", fill=(150,190,255))
        im = Image.open(fdir/f["frame"]); im.thumbnail((CW, CH), Image.LANCZOS)
        sheet.paste(im, (cx+(CW-im.width)//2, cy+HDR+(CH-im.height)//2))
        d.rectangle([cx, cy+HDR, cx+CW, cy+HDR+CH], outline=(55,58,70))
    sheet.save(f"sheets_px/px_{s:02d}.jpg", quality=90)
print(f"{len(frames)} frames -> {(len(frames)+per-1)//per} sheets of {per}")
