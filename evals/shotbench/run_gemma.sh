#!/bin/bash
# The two Gemma-4 builds, on an 80GB card (A100 or H100).
#
#   ssh gemma-box 'bash ~/ve/evals/shotbench/run_gemma.sh'
#
# Why these need their own instance: bf16 weights are 62.5GB and 51.6GB, so
# neither fits the 48GB L40S running everything else. They are also the only
# non-Qwen models in the whole comparison -- every other entry, ShotVL's base
# included, is Qwen-derived, so this is the one architecture-independent check.
#
# MoE first. gemma-4-26B-A4B is 51.6GB against 62.5GB and activates ~4B
# parameters per token, so it downloads sooner and runs faster; if the 31B then
# OOMs or the instance dies, one complete model is already banked.
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

SET="gemma-4-26b-a4b gemma-4-31b"

echo "=== START $(date -u +%FT%TZ) ==="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
echo "disk: $(df -h / | tail -1 | awk '{print $4}') free  (114GB of weights incoming)"

# Fail here rather than 40 minutes into a download that cannot complete.
FREE_GB=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
if [ "$FREE_GB" -lt 160 ]; then
  echo "ABORT: ${FREE_GB}GB free, need 160GB+ (114GB weights + dataset + cache)"
  exit 1
fi
VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
if [ "$VRAM" -lt 70000 ]; then
  echo "ABORT: ${VRAM}MiB VRAM. gemma-4-31b needs an 80GB card; this is not one."
  exit 1
fi

echo
echo "### 1/3  film-grab, sighted"
python run_benchmark.py --dataset filmshots --models $SET

echo
echo "### 2/3  film-grab, blind — contamination control"
python run_benchmark.py --dataset filmshots --no-image --models $SET

echo
echo "### 3/3  ShotBench, sighted"
python run_benchmark.py --models $SET

echo
echo "=== DONE $(date -u +%FT%TZ) ==="
echo "Pull results, then DESTROY THE INSTANCE — an 80GB card idles expensively:"
echo '  scp gemma-box:~/ve/evals/shotbench/results/*.jsonl ./results/'
