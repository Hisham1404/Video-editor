#!/bin/bash
# Finish the gemini-lite film-grab run once the free-tier daily quota resets.
#
#   bash evals/shotbench/resume_gemini.sh
#
# The run stopped at item 498 of 859 because the free tier allows 500 requests
# per day per model (quota GenerateRequestsPerDayPerProjectPerModel-FreeTier).
# 498 answers plus a couple of setup calls is exactly 500. The remaining 361
# items fit inside a single day's allowance, so this needs one run, not two.
#
# Quotas reset at midnight Pacific -- 12:30 IST. Probing first rather than just
# launching, because a run that starts under a spent quota writes 361 rows of
# HTTP 429, and this project has already been bitten by exactly that.
set -e
cd "$(dirname "$0")"

RESULT=results/gemini-lite.filmshots.jsonl
have=$(wc -l < "$RESULT" 2>/dev/null | tr -d ' ' || echo 0)
echo "have $have of 859 answers; $((859 - have)) remaining"
if [ "$have" -ge 859 ]; then echo "already complete"; exit 0; fi

echo "probing the quota with one request..."
python - <<'PY'
import json, os, sys, urllib.error, urllib.request

for line in open(".env", encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

key = os.environ.get("GEMINI_API_KEY")
if not key:
    sys.exit("no GEMINI_API_KEY in .env")

url = ("https://generativelanguage.googleapis.com/v1beta/models/"
       "gemini-3.5-flash-lite:generateContent")
body = json.dumps({"contents": [{"parts": [{"text": "Reply with the letter A."}]}]})
req = urllib.request.Request(url, data=body.encode(),
                             headers={"Content-Type": "application/json",
                                      "x-goog-api-key": key})
try:
    urllib.request.urlopen(req, timeout=60)
    print("  quota is available")
except urllib.error.HTTPError as exc:
    if exc.code != 429:
        sys.exit(f"  unexpected HTTP {exc.code}")
    # Tell a per-minute limit from a per-day one. They look identical in the
    # status code and need opposite responses: wait a minute, or wait a day.
    detail = exc.read().decode("utf-8", "replace")
    quota_id = ""
    try:
        for d in json.loads(detail)["error"].get("details", []):
            for v in d.get("violations", []):
                quota_id = v.get("quotaId", "")
    except Exception:
        pass
    if "PerDay" in quota_id:
        sys.exit("  daily quota still spent -- resets at midnight Pacific "
                 "(12:30 IST). Nothing to do but wait, or enable billing.")
    sys.exit(f"  rate limited ({quota_id or 'unknown quota'}); retry shortly")
PY

echo
echo "resuming. The 429 rows were compacted out, so this starts at item $have."
python run_benchmark.py --dataset filmshots --models gemini-lite

echo
echo "rescoring:"
python analyze.py | head -20
