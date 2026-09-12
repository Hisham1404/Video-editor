#!/usr/bin/env python3
"""Build a vertical shot-scale test set from Pexels, one frame per video.

    python fetch_pexels.py --out frames_pexels --per-query 10

WHY THIS AND NOT INSTAGRAM
--------------------------
The clips stage 5 has to tag are the USER'S raw footage, not the reference
reel. Raw phone video has no captions, no title cards, no UI recordings and no
cuts -- all of which the 11 sampled Instagram reels were full of, because those
are edited reels, which is the other input. Stock vertical footage of people is
much closer to the asset side than a finished reel is.

It is also licensed for this. The Pexels License permits free use including
commercial, without attribution. Scraping a logged-in Instagram session is
against its terms and risks the account.

ONE FRAME PER VIDEO
-------------------
The previous extractor took 16 frames from each of 11 reels and produced 176
frames holding 33 distinct shots, because consecutive samples landed inside the
same shot. Stock clips are single continuous takes, so a second frame from the
same clip is the same shot by construction. One frame from each of N videos is
N independent items, which is the only thing that makes a confidence interval
mean what it says.

The poster frame is used rather than the preview thumbnails: previews are
123x218, too small to judge framing, and the models under test would be
handicapped by the input rather than by the task. Posters are 720x1280.

CLASS BALANCE IS DESIGNED IN, NOT HOPED FOR
-------------------------------------------
film-grab is 42% `medium`, which lets a model score well by leaning that way --
this project had to add balanced accuracy to see past it. Queries here are
grouped by the shot scale they tend to return, and the same number is drawn
from each group, so the set starts roughly balanced instead of being corrected
for afterwards. The labels still come from a human; the queries only steer what
gets shown to them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Grouped by the framing each group tends to return. Group names are a sampling
# aid only -- they are NOT labels, and nothing downstream reads them as truth.
QUERY_GROUPS = {
    "wide": ["person walking city street", "hiking mountain landscape",
             "crowd street people", "person beach walking far",
             "cyclist road landscape"],
    "full": ["woman dancing full body", "man dancing street",
             "fashion model walking", "person jumping outdoors",
             "skateboarder street"],
    "medium": ["woman cooking kitchen", "man working laptop desk",
               "person shopping store", "barista making coffee",
               "artist painting studio"],
    "medium_close": ["person talking to camera", "woman speaking interview",
                     "man portrait talking", "vlogger selfie talking"],
    "close": ["close up face portrait woman", "close up face portrait man",
              "portrait smiling face", "face beauty closeup"],
    "detail": ["hands typing keyboard closeup", "hands cooking closeup",
               "hands holding phone closeup", "close up eye macro"],
}


def api(url: str, key: str) -> dict:
    req = urllib.request.Request(
        url, headers={"Authorization": key, "User-Agent": UA,
                      "Accept": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60).read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="frames_pexels")
    ap.add_argument("--per-query", type=int, default=10)
    ap.add_argument("--min-height", type=int, default=1000)
    ap.add_argument("--env", default="../shotbench/.env")
    a = ap.parse_args()

    key = os.environ.get("PEXELS_API_KEY")
    env = Path(a.env)
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("PEXELS_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit(f"no PEXELS_API_KEY in environment or {env}")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    seen_ids: set[int] = set()
    rows: list[str] = []
    per_group: dict[str, int] = {}

    for group, queries in QUERY_GROUPS.items():
        for q in queries:
            url = ("https://api.pexels.com/videos/search?"
                   + urllib.parse.urlencode(
                       {"query": q, "orientation": "portrait",
                        "per_page": a.per_query, "size": "medium"}))
            try:
                data = api(url, key)
            except urllib.error.HTTPError as exc:
                print(f"  {q[:34]:34} HTTP {exc.code}")
                continue

            got = 0
            for v in data.get("videos", []):
                if v["id"] in seen_ids:
                    continue
                if (v.get("height") or 0) < a.min_height:
                    continue          # portrait but low-res; framing is the test
                if v.get("width", 1) >= v.get("height", 0):
                    continue          # orientation filter occasionally leaks
                dst = out / f"px{v['id']}.jpg"
                if not dst.exists():
                    img = v.get("image")
                    if not img:
                        continue
                    # Ask for a known height so every frame arrives comparable.
                    img = img.split("?")[0] + "?auto=compress&cs=tinysrgb&h=1280"
                    try:
                        dst.write_bytes(fetch_bytes(img))
                    except Exception:
                        continue
                seen_ids.add(v["id"])
                rows.append(f"{dst.name}\t{v['id']}\tvertical\t"
                            f"{v['width']}\t{v['height']}\t{group}\t{v.get('url','')}")
                got += 1
            per_group[group] = per_group.get(group, 0) + got
            print(f"  {group:13} {q[:34]:34} +{got}")
            time.sleep(0.4)           # be polite to the API

    man = out / "manifest.tsv"
    man.write_text("frame\tpexels_id\torientation\twidth\theight\tquery_group\turl\n"
                   + "\n".join(rows) + "\n", encoding="utf-8")

    print(f"\n{len(rows)} vertical frames, one per video, in {out}/")
    for g, n in per_group.items():
        print(f"  {g:13} {n}")
    print("\nquery_group is a sampling aid, NOT a label — every frame still")
    print("needs a human decision. Generate the labelling page next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
