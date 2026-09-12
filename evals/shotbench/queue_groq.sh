#!/bin/bash
# Independent API and quota, so this runs alongside the Gemini queue.
# Free tier: 8k tokens/min, 1000 req/day. 859 items ~= 5h and 86% of the day's
# requests. The backend paces itself from the rate-limit headers.
cd "D:/video editor/evals/shotbench"
echo "=== GROQ qwen3.8-27b on film-grab, full 859 ==="
python -u run_benchmark.py --dataset filmshots --models groq-qwen3.8-27b
echo "=== GROQ QUEUE DONE $(date -u +%FT%TZ) ==="
