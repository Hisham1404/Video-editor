"""Contact sheets for bulk review: 12 frames per sheet, index-labelled.

Aspect ratio is preserved and each frame is letterboxed into a fixed cell,
because shot scale IS framing -- stretching a 9:16 frame into a square cell
would change the very property being judged.
"""
from PIL import Image, ImageDraw
from pathlib import Path
import json

fdir = Path("frames")
rows = [l.split("\t") for l in (fdir/"manifest.tsv").read_text(encoding="utf-8").splitlines()[1:] if l.strip()]
# Same interleave as the browser page, so sheet order matches label order.
by_src = {}
for r in rows: by_src.setdefault(r[1], []).append(r)
mixed, pools = [], list(by_src.values())
while any(pools):
    for p in pools:
        if p: mixed.append(p.pop(0))

COLS, ROWS_N, CELL, PAD, HDR = 4, 3, 330, 10, 26
per = COLS*ROWS_N
order = []
Path("sheets").mkdir(exist_ok=True)
for s in range((len(mixed)+per-1)//per):
    chunk = mixed[s*per:(s+1)*per]
    W = COLS*(CELL+PAD)+PAD
    H = ROWS_N*(CELL+HDR+PAD)+PAD
    sheet = Image.new("RGB", (W, H), (24,25,30))
    d = ImageDraw.Draw(sheet)
    for k, r in enumerate(chunk):
        idx = s*per+k
        order.append(r[0])
        cx = PAD + (k % COLS)*(CELL+PAD)
        cy = PAD + (k // COLS)*(CELL+HDR+PAD)
        d.text((cx+3, cy+5), f"#{idx}  {r[2][:4]}", fill=(180,200,255))
        im = Image.open(fdir/r[0]); im.thumbnail((CELL, CELL), Image.LANCZOS)
        ox = cx + (CELL-im.width)//2
        oy = cy + HDR + (CELL-im.height)//2
        d.rectangle([cx, cy+HDR, cx+CELL, cy+HDR+CELL], outline=(60,64,78))
        sheet.paste(im, (ox, oy))
    sheet.save(f"sheets/sheet_{s:02d}.jpg", quality=88)
Path("sheets/order.json").write_text(json.dumps(order))
print(f"{len(mixed)} frames -> {(len(mixed)+per-1)//per} sheets of {per}")
