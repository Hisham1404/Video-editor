#!/bin/bash
# The remaining local models, on a fresh L40S. One command, start to finish.
#
#   ssh shadeform 'bash ~/ve/evals/shotbench/run_tomorrow.sh'
#
# Everything is resumable: results append per item, and re-running skips what is
# already done. A dropped connection or a dead instance costs one item.
#
# ORDER IS DELIBERATE. Smallest first, so the cheap models are banked before the
# 37.5GB one risks the card. If the MoE OOMs at the end you still have three
# complete results rather than none.
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

SET="qwen3-vl-2b qwen3-vl-4b dinov2-shotscale qwen3.6-35b-a3b-fp8"

echo "=== START $(date -u +%FT%TZ) ==="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
df -h / | tail -1

echo
echo "### 1/3  film-grab, sighted — the independent set that decides ranking"
python -u run_benchmark.py --dataset filmshots --models $SET

echo
echo "### 2/3  film-grab, blind — the contamination control"
# The classifier is excluded: with no image there is nothing to classify, so a
# blind run would measure nothing and bank a fake number.
python -u run_benchmark.py --dataset filmshots --no-image \
    --models qwen3-vl-2b qwen3-vl-4b qwen3.6-35b-a3b-fp8

echo
echo "### 3/3  ShotBench, sighted — comparability with the published leaderboard"
python -u run_benchmark.py --models $SET

echo
echo "=== DONE $(date -u +%FT%TZ) ==="
python -u run_benchmark.py --report | tail -40
echo
echo "Pull the results down, then DESTROY THE INSTANCE:"
echo '  scp shadeform:~/ve/evals/shotbench/results/*.jsonl ./results/'
