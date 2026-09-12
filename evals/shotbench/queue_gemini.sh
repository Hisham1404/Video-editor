#!/bin/bash
# Wait for the in-flight film-grab run, then the two Gemini jobs that are
# blocking the decision. Sequential: same API key, same quota.
cd "D:/video editor/evals/shotbench"
while tasklist //FI "PID eq 30732" 2>/dev/null | grep -q 30732; do sleep 60; done
echo "=== film-grab finished $(date -u +%FT%TZ), starting queue ==="
echo "--- [1/2] Gemini on full ShotBench (3572 items, ~3.5h, ~\$1.20) ---"
python -u run_benchmark.py --models gemini-lite
echo "--- [2/2] Gemini blind control on film-grab (859 items, ~\$0.20) ---"
python -u run_benchmark.py --dataset filmshots --no-image --models gemini-lite
echo "=== GEMINI QUEUE DONE $(date -u +%FT%TZ) ==="
