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
pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu130
pip install -q -r requirements.txt
python -c "import torch,torchvision; print('torch',torch.__version__,'| tv',torchvision.__version__,'| cuda',torch.cuda.is_available(),'|',torch.cuda.get_device_name(0))"

echo
echo "=== secrets check — nothing sensitive should be on rented hardware ==="
find ~/ve \( -name '.env' -o -name '*.pem' -o -name '*.key' \) -print | head -5
echo "(nothing listed above = clean)"
echo
echo "SETUP_DONE"
