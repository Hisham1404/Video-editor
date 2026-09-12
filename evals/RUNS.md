# Benchmark runs — status board

One row per model per dataset. Updated as runs land.

`n` is items completed. ShotBench is 3572, film-grab 859, reels whatever you
label. Chance is 25% on ShotBench (4 options) and 14.3% on the 7-option sets;
the **5-class** column collapses both taxonomies to the classifier's five, which
is the only space in which every model here is comparable (chance 20%).

Regenerate the 5-class column, the significance tests and the agreement table
with `python evals/shotbench/analyze.py`. Conclusions live in `FINDINGS.md`.

---

## Done — film-grab (859 human-labelled frames, independent set)

| Model | n | 7-class | 5-class | Blind | Notes |
|---|---|---|---|---|---|
| gemma-4-31B | 859 | 68.3% | **81.0%** | void | best measured; 62.5 GB, needs an 80 GB card |
| **dinov2-shotscale** | 859 | — | **78.0%** | n/a | 1.2 GB classifier; 7-class is meaningless for it |
| gemma-4-26B-A4B | 859 | 62.5% | 78.0% | void | MoE, ~4B active |
| Qwen3.5-9B | 859 | 54.2% | 72.8% | 8.4% | best model that fits a consumer card |
| Qwen3.6-35B-A3B-FP8 | 859 | 61.8% | 72.3% | 8.8% | MoE, ~3B active; ties the 19 GB dense model |
| Qwen3-VL-8B | 859 | 49.7% | 69.8% | 10.5% | |
| ShotVL-3B | 859 | 53.6% | 66.7% | 12.6% | |
| ShotVL-7B | 859 | 54.8% | 65.7% | 10.0% | returns an empty string on 9.9% of images |
| Qwen3-VL-4B | 859 | 46.9% | 64.4% | 17.6% | |
| Qwen3-VL-2B | 859 | 44.8% | 61.8% | 10.4% | |
| llama-3.2-11b-vision | 859 | 37.6% | 51.7% | — | API; last of every complete run, and the priciest at 1623 in-tok/item |

"void" = the model refused rather than guessed, so the blind run measured
nothing. See `FINDINGS.md` §4 — a refusal scored as a wrong answer reads as the
cleanest result in the table and is not a result at all.

## Done — ShotBench (3572 items, 8 dimensions)

| Model | n | Sighted | Blind | Sight |
|---|---|---|---|---|
| ShotVL-3B | 3572 | 66.8% | 28.6% | +38.2 |
| ShotVL-7B | 3572 | 66.7% | 29.4% | +37.3 |
| Qwen3-VL-8B | 3572 | 54.7% | 26.9% | +27.7 |
| Qwen3.5-9B | 3572 | 54.1% | 26.9% | +27.2 |
| Qwen3-VL-4B | 3572 | 52.5% | — | |
| Qwen3-VL-2B | 3572 | 48.3% | — | |

ShotVL-3B's 66.8% against a published 65.1% is what certifies the harness.

## Partial — the API arms, still running when the GPUs were released

| Model | Dataset | n / 859 | 5-class | Notes |
|---|---|---|---|---|
| nemotron-3-nano-omni-30b | film-grab | 596 | 66.6% | 284 tok/image, 4× cheaper than Gemini |
| gemini-3.5-flash-lite | film-grab | 631 | 56.1% | **133 errors (21%)** — the incumbent default |

## Not obtained

| Model | Dataset | Why |
|---|---|---|
| Qwen3.6-35B-A3B-FP8 | ShotBench | the 3572-row file was entirely `ImportError` from the pre-`kernels` run; resume treats an error row as done and skipped all of them. Quarantined to `.kernel-failure` |
| gemma-4-26B-A4B, gemma-4-31B | ShotBench | instance released before stage 3/3 |
| gemma ×2 | film-grab blind | refusal, not an answer — void |
| qwen/qwen3.8-27b (Groq) | film-grab | abandoned at 75/859; free tier caps at 200k tokens/day, this run needs 1.78M |

## Next — the only test that decides anything

| | |
|---|---|
| **reels** | 150–200 hand-labelled vertical frames, via `evals/reels/label.py` |

Every number above is landscape Hollywood footage. The app ingests vertical
phone video, and no public dataset labels shot scale on it. Until this set
exists the model choice rests on data that does not look like the input.
