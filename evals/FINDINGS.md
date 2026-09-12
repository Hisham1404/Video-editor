# Vision model selection — findings

Everything measured between 2026-09-10 and 2026-09-13, and what it decided.
Written to survive the conversation it came from.

**Headline: a 1.2 GB image classifier is statistically indistinguishable from
the best vision-language model tested — a 62.5 GB one — on shot scale, and the
published ShotBench ranking did not survive contact with an independent test
set.**

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
| Qwen3-VL-4B | 52.5% | 46.9% | −5.6 |
| Qwen3-VL-2B | 48.3% | 44.8% | −3.5 |

On ShotBench the specialist beat the generalist by 12.7 points. On unseen data
the gap is **−0.6** — the generalist is fractionally ahead. ShotVL's lead is
largely a property of the benchmark it shares a lineage with.

The Qwen3-VL 2B → 4B → 8B ladder is the cleanest reading of the drop: the
family is internally consistent on both sets (accuracy rises with parameters
both times) and loses a near-constant 3–6 points crossing to film-grab. That is
what a *domain* gap looks like. ShotVL's 12–13 points is something else.

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

**Both Gemma blind controls are void, not clean.** They score 0.0%, which the
report's verdict column reads as "below chance blind" — the strongest possible
clean result. It is not a result at all. Gemma refuses rather than guesses:

    "Please provide the image or frame you are referring to so I can
     determine the shot scale for you."

859 of 859 rows, and 654 of 654. A model that declines to answer tells you
nothing about whether it *could* have guessed from the option list, which is
the only thing the blind control is asking. Scoring a refusal as a wrong answer
turns an abstention into evidence, and it points the wrong way. Gemma's
contamination status is **unmeasured**; forcing a choice would measure it.

## 5. The classifier ties the largest model tested

Scored identically, collapsed to 5 classes (chance 20%), same 859 items:

| Model | Size | 5-class |
|---|---|---|
| gemma-4-31B | 62.5 GB | **81.0%** |
| **aslakey/shot_scale** | **1.2 GB** | **78.0%** |
| gemma-4-26B-A4B | 51.6 GB | 78.0% |
| Qwen3.5-9B | 19.3 GB | 72.8% |
| Qwen3-VL-8B | 17.5 GB | 69.8% |
| Qwen3.6-35B-A3B-FP8 | 37.5 GB | 68.2% *(85 items only)* |
| ShotVL-3B | 7.5 GB | 66.7% |
| ShotVL-7B | 16.6 GB | 65.7% |
| nemotron-omni | API | 64.9% *(502 items)* |
| Qwen3-VL-4B | 8.9 GB | 64.4% |
| Qwen3-VL-2B | 4.3 GB | 61.8% |
| llama-3.2-11b-vision | API | 51.5% *(761 items)* |

gemma-4-31B is 3 points ahead of the classifier and **that gap is not
significant**. McNemar on the paired items — the right test, because both models
answered the same questions, so a two-proportion test would overstate it. Items
where either model gave no parseable answer are excluded rather than counted
wrong, so the Qwen3.5-9B row is n=849 and the rest n=859. Reproduce with
`python evals/shotbench/analyze.py`:

| Comparison | wins A | wins B | χ² | p | |
|---|---|---|---|---|---|
| gemma-4-31B vs classifier | 100 | 74 | 3.59 | **0.058** | not significant |
| gemma-4-26B-A4B vs classifier | 91 | 91 | 0.01 | 0.94 | dead heat |
| classifier vs Qwen3.5-9B | 117 | 78 | 7.41 | **0.0065** | classifier wins |
| gemma-4-31B vs gemma-4-26B-A4B | 77 | 51 | 4.88 | **0.027** | dense beats MoE |

So: a 1.2 GB classifier is **not beaten** by a 62.5 GB model at 52× its size,
and it **does beat** every model that fits on consumer hardware. It runs 19.8
images/sec, on CPU, emitting no tokens. The whole benchmark in 43 seconds.

**It still cannot replace the vision model.** It emits one label from five — no
framing, no description, no camera motion. A prompt built from it alone reads
"close_up. 1.2 seconds." It fills one field of five. Its taxonomy is 5 classes
against the template's 7, so it can never separate `extremeLongShot` from
`longShot`.

## 6. Two models do not reduce error — they flag doubt

Classifier as primary tagger, each candidate as the cross-check, on the same
859 frames:

| Second tagger | Agree | Correct when they agree | Correct when they disagree | **Spread** | VLM right on disagreement |
|---|---|---|---|---|---|
| gemma-4-31B | 77.5% | 89.5% | 38.3% | **51.1** | 51.8% |
| gemma-4-26B-A4B | 76.6% | 88.0% | 45.3% | 42.7 | 45.3% |
| Qwen3.5-9B | 73.5% | 87.7% | 52.0% | 35.7 | 34.7% |
| Qwen3-VL-8B | 68.6% | 87.3% | 57.8% | 29.5 | 31.9% |
| Qwen3-VL-4B | 64.1% | 86.4% | 63.0% | 23.4 | 25.0% |
| Qwen3-VL-2B | 57.7% | 88.3% | 63.9% | 24.4 | 25.6% |

Two things hold across every row:

**No combination improves accuracy.** "Believe whichever model is better on
disagreements" always resolves to "use that model alone" — with gemma-4-31B
that is 77.5%×89.5% + 22.5%×51.8% = 81.0%, which is gemma-4-31B's own score.
Ensembling buys nothing here.

**Agreement is a strong confidence signal, and it gets stronger with a better
second opinion.** The spread runs from 23 points to 51. Note the last column:
below Qwen3.5-9B the second model is *worse* than the classifier on the very
items they dispute, so it can only flag doubt; at gemma-4-31B it is finally
better, which is why that row's disagree bucket collapses to 38.3%.

What ships is constrained by cost, not by this table. gemma-4-31B needs an
80 GB card; the pipeline's rule is local and free. So stage 5 uses the
classifier plus whatever VLM stage 3 already loaded — currently a small Qwen,
spread ~24 points — and the constants in `s5_ingest.py` are set from that row.
**If stage 3 lands on a hosted model, its second opinion is already paid for and
the spread widens for free.** Re-measure before changing the constants.

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
| Qwen3.6-35B-A3B-FP8 **0.0%** on ShotBench *after* the fix | **Resume treats an error row as a completed row.** The 3,572 rows from the pre-`kernels` failure were all `ImportError`; the re-run skipped every one of them and "finished" instantly with a full row count and a fresh mtime. Quarantined to `.kernel-failure`; the result is simply missing |
| Gemma scores a perfect **0.0%** blind | Refusal, not a wrong answer — see §4. The report called it the cleanest result in the table |

**The pattern: a missing dependency, a parser assumption, or a resume rule
produces a clean, plausible zero.** Four separate 0.0% results were harness
bugs and a fifth was an abstention misread as evidence. Nothing here is
trustworthy without reading the raw model output — `raw` is stored on every row
for exactly this reason.

Two defects that are real, not harness artifacts:

- **ShotVL-7B returns an empty string on ~3% of images** (9.9% on film-grab),
  deterministically, images only. More tokens do not fix it.
- **gemini-3.5-flash-lite errored on 119 of 617 film-grab items** (19%) — the
  incumbent production default, on the only independent test set.

## 8. Cost

| | |
|---|---|
| GPU (L40S ×3, A100 80 GB ×1) | ~$9 plus the 80 GB instance's uptime |
| Gemini API | ~$1.60 |
| Groq, NVIDIA | $0 (free tiers) |

Break-even for self-hosting versus the API: **~37,800 reels/month**. Below that
a dedicated GPU costs more than per-call billing, because a GPU bills while idle.

## 9. What this decided

**Stage 5** tags user assets with the classifier, cross-checked by the vision
model, recording both votes and a confidence. Free, and statistically the most
accurate option measured for that one field regardless of budget.

**Stage 6** discounts the shot-size term of a match score by that confidence, so
an asset two models disagreed about loses a tie to one they read the same way.

**Stage 3** is still open. Gemini flash-lite, nemotron-omni (284 tokens/image —
4× cheaper than Gemini) and Qwen3.5-9B are within a few points of each other,
and flash-lite's 19% error rate on film-grab is a mark against the incumbent.

**gemma-4-31B is the accuracy ceiling found, and is not deployable** under the
local-and-free rule at 62.5 GB. It is worth knowing as the ceiling: nothing
tested reaches 82% on this task, so a pipeline designed around ~80% shot-size
accuracy is designing around the state of the art, not around a shortcut.

## 10. What is still not measured

**Everything above is Hollywood.** Both benchmarks are landscape feature film,
professionally lit, cinema cameras. The app ingests vertical phone video.

No public dataset labels shot scale on vertical social video — every
cinematography set is built from cinema, because that is where film-studies
annotators are. `evals/reels/label.py` exists to build one: 150–200 frames,
labelled by hand, run through the same harness.

**Until that exists, the model choice rests entirely on data that does not look
like the input.** Nothing in sections 3–6 survives that objection.

Also outstanding:

- Qwen3.6-35B-A3B-FP8 has **85 of 859** film-grab items and no ShotBench result.
- Gemma has no ShotBench result and no valid blind control.
- The gemini-lite and NVIDIA arms were still running when the GPUs were
  released; their film-grab rows are partial and marked as such above.
