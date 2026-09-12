# ShotBench on a rented GPU — runbook

Self-contained instructions for running the local-model arm of the benchmark on a
Shadeform instance. The Gemini arm already ran from the laptop; this is the part
that needs a card.

Written to be followed by hand or handed to another agent. Every local command
runs from `D:\video editor\evals\shotbench`.

---

## What to provision

**The 9B model decides the card.** `run_benchmark.py` records a BF16 weight
footprint per model in `MODELS`:

| Model | Weights | Peak with `--video-frames 8` |
|---|---|---|
| ShotVL-3B | 7.5 GB | ~11 GB |
| ShotVL-7B | 16.6 GB | ~21 GB |
| Qwen3-VL-8B | 17.5 GB | ~22 GB |
| **Qwen3.5-9B** | **19.3 GB** | **~24 GB** |

Weights are exact; the peaks add vision-encoder activations for 8 frames and are
estimates. That puts the 9B **on the line for a 24 GB card** — it may pass and may
OOM on the heaviest items, which is the worst outcome: you pay for the hours and
find out at the end.

| Tier | Cards | Verdict |
|---|---|---|
| 24 GB | RTX 4090, L4 | Fine for 3B/7B/8B. **Marginal for the 9B** — drop to `--video-frames 4` |
| **48 GB** | **L40S, A6000, A40** | **Recommended.** Cheapest tier that runs all four unmodified |
| 80 GB | A100, H100 | Memory is overkill. Buy only for speed — see below |

**Pick 48 GB.** It is the cheapest tier with no OOM risk, and an OOM eight hours in
costs more than the tier upgrade.

The one argument for 80 GB: if the full sweep runs long, an H100 at roughly double
the throughput can be *cheaper in total* than a slower card billed for twice the
hours. Decide that after Step 7 prints the item count — not before.

**Disk is the silent failure.** Weights total **60.9 GB**, plus `images.tar`
(2.2 GB) and `videos.tar` (1.2 GB) plus their extracted copies.

> **Ask for 200 GB. Do not accept less than 150 GB.**

Many CUDA images eat 20 GB before you start. Running out mid-download wastes an
hour of billed time.

Also require: **NVIDIA driver supporting CUDA 12.4** (the `torch` wheel this repo
pins is `cu124`), and Ubuntu 22.04 or 24.04.

---

## Step 0 — Move the private key (local, once)

Shadeform's key lands wherever the browser put it. Move it somewhere sane:

```bash
mv "/c/Users/hisha/Pictures/Camera Roll/private_key.pem" ~/.ssh/shadeform_key.pem
```

Two reasons, neither cosmetic:

1. `Camera Roll` is the exact folder OneDrive's camera-upload feature targets.
   OneDrive is installed on this machine. A private key inside a sync root is a
   private key uploaded to someone else's server.
2. The path has a space in it, which has to be quoted correctly at every single
   call site. One missed quote is a confusing failure.

`chmod 600` **does not work here** — Git Bash's POSIX bits are cosmetic on NTFS
(verified: a file chmod'd to 600 still reads 644). If ssh rejects the key with
`UNPROTECTED PRIVATE KEY FILE`, fix the Windows ACL instead:

```bash
powershell -Command "icacls C:\Users\hisha\.ssh\shadeform_key.pem /inheritance:r /grant:r hisha:R"
```

## Step 1 — Pin the host key

Interactive prompts cannot be answered by an agent — stdin is `/dev/null`, so the
`Are you sure you want to continue connecting?` prompt is a hang, not a question.
Pin the key up front:

```bash
ssh-keyscan -H <IP> >> ~/.ssh/known_hosts
```

This is trust-on-first-use: it accepts whatever answers on that IP. If the
Shadeform console shows a host fingerprint, compare it against
`ssh-keyscan <IP> | ssh-keygen -lf -` before continuing.

## Step 2 — Add a host alias

Append to `~/.ssh/config` (**append** — the file already holds Lightning and
Pythagora entries):

```
Host shadeform
  HostName <IP>
  User shadeform
  IdentityFile ~/.ssh/shadeform_key.pem
  IdentitiesOnly yes
  BatchMode yes
  ServerAliveInterval 30
  ServerAliveCountMax 6
```

`BatchMode yes` is the important line: it makes ssh **fail immediately** rather
than block forever when something unexpected asks a question.

Every later command is then just `ssh shadeform '<cmd>'`.

## Step 3 — Smoke test

```bash
ssh shadeform 'nvidia-smi; python3 -V; df -h /; free -g'
```

Stop here unless all four are right: the GPU is the one you paid for, the driver
is CUDA 12.4-capable, the root filesystem has 150 GB+ free, and there is enough
RAM to stage a download.

## Step 4 — System dependencies

```bash
ssh shadeform 'sudo apt-get update && sudo apt-get install -y git wget python3-venv tmux'
```

`tmux` is not optional here — it is what keeps an 8-hour run alive after the SSH
connection drops.

## Step 5 — Get the code

The repo is public, so it clones with no credentials. **Nothing secret goes on the
rented box**, which matters because someone else owns that hardware.

```bash
ssh shadeform 'git clone -b feat/reel-editor-scaffold https://github.com/Hisham1404/Video-editor.git ~/ve'
```

Do **not** copy `.env` up. The GPU arm needs no API key — `--key-only` is for the
Gemini arm, which has already run.

## Step 6 — Python environment (detached)

Ten minutes of downloading. Detach it, then poll:

```bash
ssh shadeform 'cd ~/ve/evals/shotbench && python3 -m venv .venv && \
  tmux new -d -s setup "source .venv/bin/activate && \
  pip install torch --index-url https://download.pytorch.org/whl/cu124 && \
  pip install -r requirements.txt > ~/setup.log 2>&1"'
```

```bash
ssh shadeform 'tail -5 ~/setup.log'
```

## Step 7 — Preflight, and the go/no-go

```bash
ssh shadeform 'cd ~/ve/evals/shotbench && source .venv/bin/activate && \
  python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"'
```

Then download the dataset and **count the items before committing to the full
sweep**:

```bash
ssh shadeform 'cd ~/ve/evals/shotbench && source .venv/bin/activate && \
  python run_benchmark.py --models shotvl-3b --limit 20'
```

That one command downloads the dataset, loads the smallest model, and proves the
whole path end to end for a few minutes of GPU time. It also prints the item
count.

> **Multiply it out before Step 8.** Items × 4 models × ~2 s/item is the wall
> clock, and the wall clock is the bill. If the full set is several thousand
> items, run `--limit 500` instead — a 500-item sample separates these models
> perfectly well, and the published averages are only a reference point.

## Step 8 — The run

```bash
ssh shadeform 'cd ~/ve/evals/shotbench && \
  tmux new -d -s bench "source .venv/bin/activate && \
  python run_benchmark.py --models shotvl-7b shotvl-3b qwen3-vl-8b qwen3.5-9b \
  > ~/run.log 2>&1"'
```

Results stream to `results/*.jsonl` as they are produced, and the harness is
**resumable** — if the instance dies, re-running the same command picks up where
it stopped rather than starting over.

## Step 9 — Poll

```bash
ssh shadeform 'tail -5 ~/run.log; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader'
```

Sustained GPU utilisation near zero with memory held means it is stuck, not
working. `memory.used` climbing to the card's limit right before a crash is the
OOM signature — restart that model with `--video-frames 4`.

## Step 10 — Retrieve

```bash
scp shadeform:~/ve/evals/shotbench/results/*.jsonl "D:/video editor/evals/shotbench/results/"
```

Then score locally, no GPU needed:

```bash
python run_benchmark.py --report
```

## Step 11 — Destroy the instance

**In the Shadeform console, by hand.** Billing is hourly and runs until the
instance is destroyed, not until you disconnect.

Then clean up locally:

```bash
rm -f ~/.ssh/shadeform_key.pem ~/.ssh/shadeform_ed25519 ~/.ssh/shadeform_ed25519.pub
```

and delete the `Host shadeform` block from `~/.ssh/config` — the IP will be
reassigned to someone else.

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `UNPROTECTED PRIVATE KEY FILE` | NTFS ACL too open; `chmod` is cosmetic here | The `icacls` command in Step 0 |
| ssh hangs forever | Host key not pinned, prompt waiting on dead stdin | Step 1, and keep `BatchMode yes` |
| `CUDA out of memory` on the 9B | 24 GB card, 8 frames | `--video-frames 4`, or provision 48 GB |
| `No space left on device` mid-download | Root volume under 150 GB | Nothing to do but reprovision — check in Step 3 |
| Run dies when the laptop sleeps | Command ran in the foreground | It must be inside `tmux` (Step 8) |
| `torch.cuda.is_available()` is False | Driver older than the cu124 wheel | Reprovision with a current CUDA image |
| Numbers far below published averages | `extract_answer` mis-parsing, not model quality | Inspect raw `response` fields in the JSONL before drawing conclusions |

## Do not

- Do not copy `.env`, API keys, or the repo's git credentials onto the instance.
  Someone else owns that hardware.
- Do not run the sweep in the foreground of an SSH call. It dies with the link.
- Do not skip Step 7's `--limit 20` run. It costs minutes and catches every
  environment problem before the expensive part.
- Do not leave the instance running after Step 10. This is the only step that
  costs real money if forgotten.
- Do not trust a single accuracy number over `n` in the dozens. The Gemini arm
  already produced a misleading read at n=3.
