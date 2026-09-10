# Project brief — reference-driven reel editor

Context document. Read once at project start, and whenever scope is in question.
Persistent per-session rules live in `CLAUDE.md`.

## 1. The problem

Editing a short-form reel to match a style you admire is slow and requires
skill most people don't have. The style lives in decisions that are hard to
articulate: how long each shot holds, where cuts land against the music, how
shots are framed, what order shot sizes appear in.

Existing tools do beat-sync (cut on the beat) but not style transfer (cut *like
that reference did*). Nothing available lets a user say "make my footage look
edited like this."

## 2. What the system does

Input: one edited reference reel, plus a repository of the user's raw clips and
stills, plus the user's own music track.

Output: a rendered reel using the user's footage, cut with the reference's
editing grammar, on the user's music. Plus a list of generation prompts for
slots where the user had no suitable asset.

The loop closes: the user takes those prompts to an external video model,
generates the missing shots, uploads them, and the timeline refills.

## 3. Prior work — what is already proven

The core is not speculative. Google Research's *Automatic Non-Linear Video
Editing Transfer* (arXiv 2105.06988) performs shot detection on a source video,
analyses each shot's framing, content type, playback speed and lighting, and
transfers those visual and temporal styles onto unseen raw footage. They ran it
across 3,872 detected shots and reported it captured camera motion well and
matched the source's temporal allocation.

*ESA: Energy-Based Shot Assembly Optimization* (arXiv 2511.02505) extends this:
it segments and labels reference shots for shot size, camera motion and
semantics, then uses energy-based models to score candidate sequences against
the reference style.

Treat both as baselines to compare against, not as competitors.

## 4. What is genuinely new here

Neither paper does **gap detection with generative fill**. They assume the user's
footage repository contains a usable match for every slot. When those papers were
written, generative video wasn't good enough to fill an empty slot; now it is.

The contribution is therefore: extending editing-style transfer with an explicit
"this slot cannot be satisfied from your assets, here is what to generate"
step, and evaluating whether generatively-filled slots preserve perceived style
fidelity.

This is also the paper, if one gets written. The paper comes *after* the product
has real users and real data — not before. Production data from a live system is
the scarce input; almost all work in this area runs on synthetic benchmarks.

## 5. Architecture

### Free / local components
- **Shot segmentation**: PySceneDetect, or TransNetV2 if gradual transitions
  need handling
- **Rhythm extraction**: librosa or madmom for beat, tempo, onset, downbeat
- **Asset embedding and matching**: CLIP or SigLIP
- **Render**: ffmpeg

### Metered component
- **Per-shot description**: a vision model, describing subject, shot size
  (wide/medium/close), framing, camera motion, and role in the sequence.
  This is the only paid part of the pipeline.

### The template
The intermediate representation between analysis and render. An ordered list of
slots, each carrying:
- rhythm-relative timing (beat index, subdivision, phrase position) — **never
  absolute seconds**
- shot size and framing
- semantic description
- camera motion (v2+)

Versioned JSON. This schema is the contract; keep it stable.

## 6. Scope

### v1 (first shippable)
Reference in → shot list with rhythm-relative durations and semantic labels →
user assets embedded and matched → hard cuts only → rendered against the user's
own music → unmatched slots surfaced as generation prompts.

### v2
Speed ramps. Camera motion synthesis (virtual camera with real easing curves,
so a push-in on the reference becomes a push-in on static footage). Colour grade
transfer via histogram matching or LUT extraction. Improved matching.

### v3
Transitions.

### Explicitly out of scope, indefinitely
Video generation inside the app. Prompts out, clips in. This keeps the cost
model viable.

## 7. Known hard parts

**Transitions are the hardest thing here.** Whip pans, match cuts and masked
reveals are what make a reel read as professionally cut, and detecting and
reproducing them is disproportionately difficult. v1 output will look simpler
than the reference. That is expected and acceptable.

**Audio is a design trap.** The reference's music cannot legally ship with the
output, but the cut timings are defined relative to that music. Hence the
rhythm-relative timing rule. Decide this correctly at the start; retrofitting it
means rebuilding the timeline model.

**Matching quality decides whether this feels magical or broken.** It is the
least glamorous component and will consume the most time. Budget accordingly.

## 8. Cost model

Roughly 15–20 shots in a 30-second reel, at 2–3 frames sampled per shot, gives
40–60 images per reference. Vision models bill images at a fixed token count by
size (order of 1,500 tokens for a 16:9 frame), so one reference analysis lands
near $0.06 at current Flash-tier rates. Analysing the user's own footage roughly
doubles it.

**Working figure: $0.12–0.15 per complete job**, halved if batch tiers are used.

Development across months of iteration: $100–300 total on the model. Hosting for
a small user group: $10–30/month. **All-in for a 4–6 month build: $200–500.**

Two pricing hazards to check before committing to a model:
- Introductory Flash rates in 2026 are scheduled to double on 1 January 2027
- The Gemini 2.5 family is set for retirement on 16 October 2026 — do not build
  on it

Verify against the provider's official pricing page; third-party pricing
summaries contradict each other constantly.

## 9. Evaluation

This project is judged partly on production discipline, so evals are a
deliverable, not a nicety.

Track:
- **Matching quality** against a golden set: does the chosen clip satisfy the
  slot's shot size and semantic description?
- **Style fidelity**: human preference test, output vs reference, side by side
- **Cost per job**, logged per run, trended over time
- **p95 latency** end to end
- **Failure catalogue**: what breaks, how often, how badly. Classify by severity
  — a wrong-but-plausible match is different from a crash.

Keep the golden fixture set append-only.

## 10. Legal

Using a copyrighted reel as a private reference input is fine. Publishing
side-by-side demos of a copyrighted reel is not. Commission or shoot 2–3
reference reels owned outright for anything public-facing — README, demo video,
paper figures.

## 11. Open questions

- Local vision model vs API — depends on available GPU
- How many reference styles the matcher needs to see before generalising
- Whether shot-size taxonomy should be fixed (wide/medium/close/extreme) or
  free-text embedded
