# ShotBench harness

Decides which vision model describes shots for the reel editor's analysis stage.

## The question

`SPEC.md` assumes a metered vision model (Gemini) for per-shot description. But
[ShotBench](https://arxiv.org/abs/2506.21356) showed a purpose-built 8B model,
[ShotVL-7B](https://huggingface.co/Vchitect/ShotVL-7B), beating every commercial
model tested — including Gemini 2.5 Flash by 15.6 points, and Qwen2.5-VL-72B
despite being 9× smaller.

Two things make that result unusable as-is:

1. The newest commercial entry on that leaderboard is `gemini-2.5-flash-preview-04-17`
   (April 2025). Gemini 3.8 Flash launched September 2026.
2. ShotVL-7B is fine-tuned on Qwen2.5-VL-7B, now roughly four generations behind
   (2.5 → 3 → 3.5 → 3.6 → 3.8). Its cinematic training was worth ~15 points in
   mid-2025; whether that survives a year of base-model progress is unmeasured.

Nobody has published ShotBench numbers for Gemini 3.x or the modern Qwen line.
This harness produces them.

## Published baseline (for calibration)

| Model | Shot size | Framing | Overall |
|---|---|---|---|
| ShotVL-7B | 81.2 | 90.1 | **70.1** |
| ShotVL-3B | 77.9 | 85.6 | 65.1 |
| GPT-4o | 69.3 | 83.1 | 59.3 |
| Qwen2.5-VL-72B | 75.1 | 82.9 | 59.1 |
| Gemini-2.5-flash-preview | 57.7 | 82.9 | 54.5 |

**If `shotvl-7b` scores near 70.1 overall, the harness is calibrated.** If it
doesn't, fix the harness before trusting any other row.

## Models under test

Four providers. Every hosted model was verified multimodal by **sending a real
image and asking a question with a checkable answer** — "what colour is this?"
on a blue square — never by reading a model card. That check mattered: four
NVIDIA models accept an image payload and return an empty string, and
`openai/gpt-oss-20b` accepts it on NVIDIA while Groq rejects the same request.

### Local (rented GPU)

| Key | HuggingFace id | Weights |
|---|---|---|
| `shotvl-3b` | `Vchitect/ShotVL-3B` | 7.5 GB |
| `shotvl-7b` | `Vchitect/ShotVL-7B` | 16.6 GB |
| `qwen3-vl-8b` | `Qwen/Qwen3-VL-8B-Instruct` | 17.5 GB |
| `qwen3.5-9b` | `Qwen/Qwen3.5-9B` | 19.3 GB |
| `qwen3-vl-2b` | `Qwen/Qwen3-VL-2B-Instruct` | 4.3 GB |
| `qwen3-vl-4b` | `Qwen/Qwen3-VL-4B-Instruct` | 8.9 GB |
| `qwen3.6-35b-a3b-fp8` | `Qwen/Qwen3.6-35B-A3B-FP8` | 37.5 GB |
| `gemma-4-26b-a4b` | `google/gemma-4-26B-A4B-it` | 51.6 GB |
| `gemma-4-31b` | `google/gemma-4-31B-it` | 62.5 GB |
| `dinov2-shotscale` | `aslakey/shot_scale` | 1.2 GB |

The Gemma pair needs an 80 GB card. They are also the only non-Qwen entries —
every other model here, ShotVL's own base included, is Qwen-derived, so they are
the one architecture-independent check in the set.

`dinov2-shotscale` is not a VLM but a classification head. The task is mapping an
image to one of seven labels, which does not need a model that can converse. It
knows 5 classes rather than 7, so it is only comparable under `COLLAPSE_5`.

### Hosted

| Key | Provider id | Tokens/image |
|---|---|---|
| `gemini-lite` | `gemini-3.5-flash-lite` | 1,141 |
| `gemini` | `gemini-3.8-flash` | 1,141 + thinking |
| `nv-nemotron-omni` | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | **284** |
| `nv-llama32-11b-vision` | `meta/llama-3.2-11b-vision-instruct` | 1,623 |

### Dropped, and why

| Model | Reason |
|---|---|
| **`qwen/qwen3.8-27b` (Groq)** | **Free tier caps at 200,000 tokens/day. This benchmark needs 859 × ~2,073 = 1.78M — nine days.** The cap is invisible: the API publishes only per-minute limits, and `x-ratelimit-remaining-tokens` reads a full 8,000 while the day is exhausted. Abandoned at 66/859 (53.0%) |
| `qwen/qwen3.6-27b` (Groq) | Same daily cap, and it emits `<think>` |
| `gemini-3.8-flash` | 6.7× the cost of flash-lite, 8× the latency, HTTP 503 on ~83% of calls |
| `meta/llama-3.2-90b-vision-instruct` | Timed out at both 45s and 180s |
| `ethz-mtc/shot_scale_classifier-resnet50` | Ships no `config.json` — a bare `.bin` with no `id2label`, so its output indices cannot be interpreted |
| 55 of 82 NVIDIA catalogue models | HTTP 404 — advertised on build.nvidia.com, unreachable with the key |

**The catalogue is not the account.** Anything picked from a docs page needs a
live call before it goes in a plan.

### The HuggingFace survey

`shotvl`, `cinematic`, `cinematography`, `shot-scale`, `shot type`,
`film-grammar`, `camera-angle`, `storyboard` — **ShotVL-3B and ShotVL-7B are the
only cinematography-tuned VLMs on the Hub.** Everything else returned is image
*generation* (SDXL/Flux/LTX LoRAs). The specialist field is fully tested; what
remains is finding a generalist that is cheaper or better.

## Setup

Target: RTX 4090 (24 GB) — every model in the default set fits at BF16.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
export GEMINI_API_KEY="your-key"   # never commit this, never pass it as a flag
```

## Run

Smoke test first — 60 items, images only, confirms plumbing before the 2.2 GB download matters:

```bash
python run_benchmark.py --models shotvl-3b --limit 60 --skip-video
```

The decision run — the two dimensions the template depends on:

```bash
python run_benchmark.py --models all --key-only --skip-video
```

Full benchmark, all 8 dimensions including video items:

```bash
python run_benchmark.py --models all
```

Score whatever has finished:

```bash
python run_benchmark.py --report
```

If the Gemini model id has moved: `python run_benchmark.py --list-gemini-models`

## Spot instances

Results append to `results/<model>.jsonl` and flush after every item. Re-running
the same command skips completed indices, so an eviction costs one item, not the
run. Spot at $0.18/hr is the right choice here.

## Reading the output

Three tables:

1. **Accuracy by dimension** — all 8, comparable to the published leaderboard.
2. **Decision metric** — shot size + framing only. *This is the one that matters.*
   The overall average includes lens size, lighting and composition, which never
   reach the template. Do not pick a model on the overall number.
3. **Operations** — median latency, unparsed-answer count, errors, and Gemini
   token spend. A high `unparsed` count means the model ignored the
   letter-only instruction, not that it got the question wrong — check `raw`
   in the JSONL before trusting a low score.

## Dataset shape (verified against all 3,572 rows)

| Dimension | Items | Media |
|---|---|---|
| lens size | 489 | image |
| shot size | 485 | image |
| composition | 479 | image |
| camera movement | 464 | **video** |
| camera angle | 455 | image |
| shot framing | 445 | image |
| lighting type | 405 | image |
| lighting | 350 | image |

Every item is 4-option MCQ, the gold answer is always among the options, and the
answer letter is near-uniformly distributed (858–942 each) — so there's no
majority-class shortcut to worry about.

**The video items are exactly the camera-movement items** — the two sets are
identical, all 464. So `--skip-video` drops that one dimension and nothing else,
and saves the 1.2 GB `videos.tar` download. Your decision metric (shot size +
shot framing, 930 items) is entirely image-based and unaffected. Run with
`--skip-video --key-only` first; add video only when you care about camera
motion for v2.

## Known limitations

- **Video items are frame-sampled**, not passed as native video (8 frames
  uniformly, `--video-frames`). This will understate camera-movement scores.
  Both ShotVL and Qwen3.5 accept native video with fps control; wiring that up
  is the obvious next iteration, and matters because camera motion is the
  weakest dimension for every model and a v2 headline feature.
- Gemini has no `media_resolution` sweep in the default run. `--media-resolution
  MEDIA_RESOLUTION_LOW` caps tokens per image (~258 vs ~1,548 for a 16:9 frame,
  a ~6× cost lever). Worth a second Gemini arm to find where accuracy breaks.
- Frame sampling for video decodes with OpenCV seeking, which is approximate on
  some codecs.

## Licensing

- **ShotBench** (this eval set) — Apache 2.0. Fine to use and publish results from.
- **ShotVL-3B / 7B weights** — Apache 2.0. Fine to use and ship.
- **ShotQA** (the *training* set) — CC-BY-NC-ND-4.0. Non-commercial **and**
  no-derivatives. Do not plan to fine-tune your own model on it for anything
  commercial or public-facing. This belongs in `SPEC.md` §10.

## Cost

The whole benchmark is a few GPU-hours: roughly **$2–3** on a 4090 on-demand
($0.46/hr) or **under $1** on spot ($0.18/hr). The Gemini arm over 3,572 items
costs a few cents; `--key-only` cuts it further.
