#!/bin/bash
# Provision a fresh Shadeform box from nothing to benchmark-ready.
#
#   ssh <box> 'bash -s' < setup_box.sh
#
# Everything in here was learned by having it go wrong once:
#
#   torchvision is NOT a torch dependency, and transformers imports it at
#   model-load time for every Qwen-derived model. Omitting it fails AFTER the
#   weights download, on rented time.
#
#   The cu124 index the repo originally pinned resolves to torch 2.14.0+cu130
#   against the current driver (580.x). Asking for cu130 directly is honest
#   about what actually gets installed.
#
#   tmux is not optional: it is what keeps a multi-hour run alive when the ssh
#   connection drops.
set -e

echo "=== box ==="
whoami; lsb_release -ds 2>/dev/null || true
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
df -h / | tail -1
nproc; free -g | sed -n 2p

# Weights go wherever there is room. Shadeform images vary: the A100 80GB box
# has 82GB on / and 700GB on /ephemeral, and 114GB of Gemma weights fit only on
# the latter. Downloading to the default ~/.cache and filling the root disk
# halfway through is a slow way to learn this.
CACHE_ROOT="$HOME"
for cand in /ephemeral /mnt /scratch; do
  if [ -d "$cand" ] && [ -w "$cand" ]; then
    avail=$(df --output=avail -BG "$cand" 2>/dev/null | tail -1 | tr -dc '0-9')
    root_avail=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
    if [ "${avail:-0}" -gt "${root_avail:-0}" ]; then CACHE_ROOT="$cand"; break; fi
  fi
done
export HF_HOME="$CACHE_ROOT/hf"
mkdir -p "$HF_HOME"
echo "HF cache -> $HF_HOME ($(df -h "$CACHE_ROOT" | tail -1 | awk '{print $4}') free)"

# The CUDA runtime the wheels are built against must not exceed what the driver
# supports. Driver 580+ takes cu130; 570 reports CUDA 12.8 and will fail to load
# a cu130 build. Read it rather than pinning one and hoping.
CUDA_MAJOR=$(nvidia-smi | grep -oP 'CUDA Version: \K[0-9]+' | head -1)
CUDA_MINOR=$(nvidia-smi | grep -oP 'CUDA Version: [0-9]+\.\K[0-9]+' | head -1)
if [ "${CUDA_MAJOR:-13}" -ge 13 ]; then TORCH_IDX=cu130
elif [ "${CUDA_MINOR:-0}" -ge 8 ]; then TORCH_IDX=cu128
else TORCH_IDX=cu124; fi
echo "driver reports CUDA ${CUDA_MAJOR}.${CUDA_MINOR} -> torch index ${TORCH_IDX}"

echo
echo "=== system packages ==="
sudo -n true 2>/dev/null || { echo "ABORT: sudo needs a password"; exit 1; }
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    git python3-venv python3-pip tmux >/dev/null

echo
echo "=== code (public repo — no credentials land on this machine) ==="
rm -rf ~/ve
git clone -q -b feat/reel-editor-scaffold https://github.com/Hisham1404/Video-editor.git ~/ve
cd ~/ve && git log --oneline -1

echo
echo "=== python env ==="
cd ~/ve/evals/shotbench
python3 -m venv .venv
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q torch torchvision --index-url "https://download.pytorch.org/whl/${TORCH_IDX}"
pip install -q -r requirements.txt
python -c "import torch,torchvision; print('torch',torch.__version__,'| tv',torchvision.__version__,'| cuda',torch.cuda.is_available(),'|',torch.cuda.get_device_name(0))"

echo
echo "=== secrets check — nothing sensitive should be on rented hardware ==="
find ~/ve \( -name '.env' -o -name '*.pem' -o -name '*.key' \) -print | head -5
echo "(nothing listed above = clean)"
echo
# Persist for every later shell, or run_gemma.sh downloads to the wrong disk.
grep -q "HF_HOME" ~/.bashrc 2>/dev/null || echo "export HF_HOME=$HF_HOME" >> ~/.bashrc
echo "HF_HOME=$HF_HOME persisted to ~/.bashrc"
echo "SETUP_DONE"
