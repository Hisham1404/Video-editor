# Vision model selection — findings

Everything measured between 2026-09-10 and 2026-09-13, and what it decided.
Written to survive the conversation it came from.

**Headline: a 1.2 GB image classifier beat every vision-language model tested,
and the published ShotBench ranking did not survive contact with an independent
test set.**

---

## 1. What was tested

| Model | Size / host | Provider |
|---|---|---|
| ShotVL-3B | 7.5 GB | local |
| ShotVL-7B | 16.6 GB | local |
| Qwen3-VL-2B | 4.3 GB | local |
| Qwen3-VL-4B | 8.9 GB | local |
| Qwen3-VL-8B | 17.5 GB | local |
| Qwen3.5-9B | 19.3 GB | local |
| Qwen3.6-35B-A3B-FP8 | 37.5 GB (MoE, ~3B active) | local |
| gemma-4-26B-A4B | 51.6 GB (MoE, ~4B active) | local, 80 GB card |
| gemma-4-31B | 62.5 GB | local, 80 GB card |
| **aslakey/shot_scale** | **1.2 GB, DINOv2 classifier** | local, CPU-capable |
| gemini-3.5-flash-lite | API | Google |
| gemini-3.8-flash | API | Google — **rejected** |
| nemotron-3-nano-omni-30b | API | NVIDIA |
| llama-3.2-11b-vision | API | NVIDIA |
| qwen/qwen3.8-27b | API | Groq — **abandoned** |

Two benchmarks, each run sighted and blind:

- **ShotBench** — 3,572 items, 8 dimensions, 4 options (chance 25%)
- **film-grab** (`szymonrucinski/types-of-film-shots`) — 859 human-labelled
  frames, 7 options (chance 14.3%). Independent: different annotators, films,
  taxonomy, and unseen by every model.

## 2. The harness is calibrated

ShotVL-3B scored **66.8%** on ShotBench against a published **65.1%** — within
1.7 points on the full set. Without that anchor no other number here would be
worth reading.

## 3. The published ranking does not generalise

| Model | ShotBench | film-grab | Drop |
|---|---|---|---|
| ShotVL-3B | 66.8% | 53.6% | **−13.2** |
| ShotVL-7B | 66.7% | 54.8% | −11.9 |
| Qwen3-VL-8B | 54.7% | 49.7% | −5.0 |
| Qwen3.5-9B | 54.1% | **54.2%** | **+0.2** |

On ShotBench the specialist beat the generalist by 12.7 points. On unseen data
the gap is **−0.6** — the generalist is fractionally ahead. ShotVL's lead is
largely a property of the benchmark it shares a lineage with.

## 4. It is not cheating, though

The contamination control (`--no-image`: same question, image withheld):

| Model | ShotBench blind | Sight | film-grab blind |
|---|---|---|---|
| ShotVL-3B | 28.6% | +38.2 | 12.6% |
| ShotVL-7B | 29.4% | +37.3 | 10.0% |
| Qwen3-VL-8B | 26.9% | +27.7 | 10.5% |
| Qwen3.5-9B | 26.9% | +27.2 | 8.4% |

All four sit near chance blind, and **all four score above chance by a similar
margin** — including generalists that have never seen ShotQA or this question
format. The small lift is a property of the questions, not of ShotVL's training.
ShotVL's edge over the generalists blind is +1.7 points at z = +1.56: not
distinguishable from noise.

On film-grab every model scores **below** chance blind. That set leaks nothing.

[RefineShot](https://arxiv.org/pdf/2510.02423) raises the same contamination
concern about ShotBench. This measures it rather than assuming either way.

## 5. The classifier wins

Scored identically, collapsed to 5 classes (chance 20%), same 859 items:

| Model | Size | 5-class |
|---|---|---|
| **aslakey/shot_scale** | **1.2 GB** | **78.0%** |
| Qwen3.5-9B | 19.3 GB | 72.8% |
| Qwen3-VL-8B | 17.5 GB | 69.8% |
| nemotron-omni | API | 69.5% |
| ShotVL-3B | 7.5 GB | 66.7% |
| ShotVL-7B | 16.6 GB | 65.7% |
| gemini-3.5-flash-lite | API | 65.4% |
| Qwen3-VL-4B | 8.9 GB | 64.4% |
| Qwen3-VL-2B | 4.3 GB | 61.8% |

19.8 images/sec, CPU-capable, no tokens. The whole benchmark in 43 seconds.

**It cannot replace the vision model.** It emits one label from five — no
framing, no description, no camera motion. A prompt built from it alone reads
"close_up. 1.2 seconds." It fills one field of five.

Its taxonomy is 5 classes against the template's 7, so it can never separate
`extremeLongShot` from `longShot`.

## 6. Two models do not reduce error — they flag doubt

| | vs Qwen3-VL-2B | vs Qwen3-VL-4B |
|---|---|---|
| Classifier alone | 78.0% | 78.0% |
| **They agree** (58% / 64%) | **88.3%** | 86.4% |
| Disagree — classifier right | 63.9% | 63.0% |
| Disagree — **VLM right** | **25.6%** | 25.0% |
| Perfect-referee ceiling | 88.8% | 87.0% |

Where they differ the VLM is worse, so the only implementable rule is "believe
the classifier" — which lands back at 78.0%. **No combination improves
accuracy.**

What agreement buys is a 24-point confidence spread, for free. That is now wired
into `s5_ingest.Asset.shot_size_confidence` and consumed by `s6_match.score()`,
because `CONFIDENCE_FLOOR = 0.55` was inherited guesswork and this is the first
measured input to it.

## 7. Bugs that produced fake results

Every one of these read as "this model is bad" and was not.

| Symptom | Actual cause |
|---|---|
| Qwen3.5-9B **0.0%** on all 3,572 | Reasoning model; `max_new_tokens=16` cut it off mid-thought. Recovered to 54.1% |
| Qwen3.6-35B-A3B-FP8 **0.0%** on all 859 | `kernels` package missing — FP8 kernel unavailable |
| Every model fails at load | `torchvision` absent; `transformers` imports it for Qwen-derived models |
| ShotVL apparently collapses on film-grab | `extract_answer` hardcoded `[A-Da-d]`; every `E`/`F`/`G` scored wrong. ShotVL-7B lost 51% of its answers. **Would have inverted the ranking** |
| dinov2-shotscale fails to load | No `preprocessor_config.json`; base DINOv2 preprocessing substituted |
| Groq "hangs" | 200k tokens/day cap. Invisible: headers report only the per-minute bucket, which reads full |

**The pattern: a missing dependency or a parser assumption produces a clean,
plausible zero.** Three separate 0.0% results were harness bugs. Nothing here is
trustworthy without checking the raw model output.

ShotVL-7B has one real defect: it returns an **empty string on ~3% of images**
(9.9% on film-grab), deterministically, images only. More tokens do not fix it.

## 8. Cost

| | |
|---|---|
| GPU (L40S ×3, A100 80GB ×1) | ~$9 |
| Gemini API | ~$1.60 |
| Groq, NVIDIA | $0 (free tiers) |

Break-even for self-hosting versus the API: **~37,800 reels/month**. Below that
a dedicated GPU costs more than per-call billing, because a GPU bills while idle.

## 9. What this decided

**Stage 5** tags user assets with the classifier, cross-checked by the vision
model, recording both votes and a confidence. Free, and the most accurate option
measured for that one field.

**Stage 6** discounts the shot-size term of a match score by that confidence, so
an asset two models disagreed about loses a tie to one they read the same way.

**Stage 3** is still open. Gemini flash-lite, nemotron-omni (284 tokens/image —
4× cheaper than Gemini) and Qwen3.5-9B are within a few points of each other.

## 10. What is still not measured

**Everything above is Hollywood.** Both benchmarks are landscape feature film,
professionally lit, cinema cameras. The app ingests vertical phone video.

No public dataset labels shot scale on vertical social video — every
cinematography set is built from cinema, because that is where film-studies
annotators are. `evals/reels/label.py` exists to build one: 150–200 frames,
labelled by hand, run through the same harness.

**Until that exists, the model choice rests entirely on data that does not look
like the input.** Nothing in sections 3–6 survives that objection.
