# Benchmark runs — status board

One row per model per dataset. Updated as runs land.

`n` is items completed. ShotBench is 3572, film-grab 859, reels whatever you
label. Chance is 25% on ShotBench (4 options) and 14.3% on the 7-option sets.

---

## Done

| Model | Dataset | n | Sighted | Blind | Sight |
|---|---|---|---|---|---|
| ShotVL-3B | ShotBench | 3572 | 66.8% | 28.6% | +38.2 |
| ShotVL-7B | ShotBench | 3572 | 66.7% | 29.4% | +37.3 |
| Qwen3-VL-8B | ShotBench | 3572 | 54.7% | 26.9% | +27.7 |
| Qwen3.5-9B | ShotBench | 3572 | 54.1% | 26.9% | +27.2 |
| ShotVL-3B | film-grab | 859 | 53.6% | 12.6% | +41.0 |
| ShotVL-7B | film-grab | 859 | 54.8% | 10.0% | +44.8 |
| Qwen3-VL-8B | film-grab | 859 | 49.7% | 10.5% | +39.2 |
| Qwen3.5-9B | film-grab | 859 | 54.2% | 8.4% | +45.9 |

ShotVL-3B's 66.8% against a published 65.1% is what certifies the harness.

## Running

| Model | Dataset | Where | Notes |
|---|---|---|---|
| gemini-3.5-flash-lite | film-grab | laptop, pid 30732 | ~2s/item |
| ~~groq qwen3.8-27b~~ | film-grab | **ABANDONED at 66/859** | free tier caps at 200k tokens/day; this run needs 1.78M |
| nv-nemotron-omni | film-grab | laptop | reasons internally; ~280 out tok/item |
| nv-llama32-11b-vision | film-grab | laptop | 1623 in tok/item, the priciest |

## Queued

| Model | Dataset | Fires when | Cost |
|---|---|---|---|
| gemini-3.5-flash-lite | **ShotBench full** | film-grab run ends | ~$1.20 |
| gemini-3.5-flash-lite | film-grab **blind** | the above ends | ~$0.20 |

Gemini on full ShotBench is the one that matters: the incumbent's headline
87.1% rests on **31 items**, against 3572 for every local model. Until it lands,
the production default is the least-measured option in the comparison.

## Queued for the next L40S — `bash run_tomorrow.sh`

| Model | Weights | Why |
|---|---|---|
| Qwen3-VL-2B | 4.3 GB | quarter the tested 8B; changes hosting economics if close |
| Qwen3-VL-4B | 8.9 GB | the midpoint — does accuracy scale with parameters at all? |
| Qwen3.6-35B-A3B **FP8** | 37.5 GB | MoE: ~3B active, 35B stored. bf16 is 71.9GB and will not fit |
| dinov2-shotscale | 1.2 GB | not a VLM — a classifier. 5 classes, so `--collapse5` only |

Runs film-grab sighted, film-grab blind, then ShotBench. Smallest first, so
three results are banked before the 37.5GB model risks the card.

**Too big for a 48GB card**, deliberately not registered: gemma-4-31B-it
(62.5GB), gemma-4-26B-A4B-it (51.6GB), Qwen3.6-35B-A3B bf16 (71.9GB). They need
an 80GB instance.

## Not started

| What | Blocked on |
|---|---|
| **Your own reel frames** | you — `evals/reels/label.py`, 150-200 frames |
| groq qwen3.6-27b | needs thinking suppressed first; it emits `<think>` |
| Blind controls for groq / nvidia arms | after their sighted runs |
| AutoShot for stage 1 | separate problem — shot boundaries, not scale |

## The HuggingFace survey result

Searched `shotvl`, `cinematic`, `cinematography`, `shot-scale`, `shot type`,
`film-grammar`, `camera-angle`, `storyboard`.

**ShotVL-3B and ShotVL-7B are the only cinematography-tuned VLMs on the Hub.**
Everything else returned is image *generation* (SDXL/Flux/LTX LoRAs for making
cinematic-looking images). The specialist field is fully tested; what remains is
finding a generalist that is cheaper or better.

`ethz-mtc/shot_scale_classifier-resnet50` looked promising at 0.1GB but ships no
config.json — a bare .bin with no id2label, so its outputs cannot be
interpreted. Dropped.

---

## Groq: why it stopped at 66 items

Groq's free tier caps at **200,000 tokens per day**. This benchmark needs 859
images x ~2073 tokens = **1.78 million** — nine days of running.

The trap is that the cap is invisible. The API publishes only per-minute
limits: `x-ratelimit-limit-tokens: 8000` reads *full* even while the day is
exhausted, because that header describes the minute bucket. Only the 429 body
names TPD. Pacing code written against the headers — which is what I wrote —
cannot see this coming, and retries into a five-minute backoff forever.

The harness now parses TPD out of the 429 body and aborts with a clear message
instead. The partial result stands at **53.0% on n=66**: same band as everything
else, far too small to rank.

## Standing caveats

**No number is real until its run finishes.** Gemini read 59.8% at n=234 and
52.3% at n=367 on the same run — the categories are not evenly hard, so partial
scores drift. Wait for the full n.

**ShotBench and film-grab are both feature film.** Landscape, lit, cinema
cameras. The app ingests vertical phone video. A model can be good at one and
poor at the other, and nothing here measures that. That is what the reels set is
for, and why it decides the choice rather than confirming it.

**Accepting an image is not seeing one.** Four NVIDIA models took an image
payload and returned an empty string; `gpt-oss-20b` accepts it on NVIDIA and
rejects it on Groq. Every arm here was verified with a question whose answer is
checkable, not by reading a model card.

## Cost so far

| | |
|---|---|
| GPU (L40S, 2 instances) | ~$1.40 — both destroyed |
| Gemini API | <$0.20 so far, ~$1.40 more queued |
| Groq, NVIDIA | $0 — free tiers |
