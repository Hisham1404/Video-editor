# CLAUDE.md

## WHY

Reference-driven reel editor. A user uploads an edited reference reel plus their
own raw clips and images. The system extracts the *editing grammar* of the
reference and reapplies it to the user's footage. Where the user has no suitable
clip for a slot, it emits a generation prompt they can take to an external video
model, then accepts the returned clip back into the timeline.

This is a portfolio project targeting AI-native product startups. That means
production discipline is part of the deliverable: evals, cost per job, and
latency numbers matter as much as features. See `SPEC.md` for full context.

## WHAT

Pipeline stages:

1. Shot segmentation of the reference (local, free)
2. Rhythm extraction from the reference audio (local, free)
3. Per-shot semantic + framing description (metered vision model)
4. Template assembly: ordered slots with rhythm-relative timing
5. User asset ingestion and embedding (local, free)
6. Slot matching, with confidence scoring
7. Gap detection → generation prompt emission
8. Render (ffmpeg)

## HOW — hard rules

**Never store cut timings in absolute seconds.** Timings are stored as rhythmic
structure: beat index, subdivision, and phrase position. The reference's music
cannot ship with the output, so every timeline must be re-mappable onto a
different track. Violating this forces a rewrite of the timeline model.

**Video generation never runs inside this app.** The app emits prompts; the user
generates elsewhere and uploads the result. This is a deliberate cost decision,
not an unfinished feature. Do not add a generation API call.

**v1 is hard cuts only.** No transitions, no speed ramps, no colour grading, no
camera-motion synthesis. These are v2/v3. Reject scope expansion into them
unless explicitly asked.

**Every metered call gets logged with token count and cost.** Cost per job is a
tracked metric, not an afterthought.

**Prefer local and free over API.** Shot detection, beat tracking, embeddings and
rendering all run locally. The vision model is the only paid component.

## Stack

- Pipeline and ML: Python
- Frontend: Next.js + TypeScript
- Render: ffmpeg
- Object storage: Cloudflare R2 or Backblaze B2 (zero/low egress — video egress
  fees are the main hosting risk)

## Conventions

- Templates are serialised as JSON and are the contract between analysis and
  render. Analysis changes must keep the template schema versioned.
- Any prompt sent to a model lives in a versioned prompt file, not inline in
  application code.
- Golden test set of reference reels lives in `evals/`. Do not delete or mutate
  golden fixtures; add new ones.

## Commands

- Install: `pip install torch --index-url https://download.pytorch.org/whl/cu124`
  then `pip install -r requirements.txt`
- Run pipeline: `python -m pipeline.cli --reference REF.mp4 --assets DIR --music TRACK.wav`
  (stages are stubs; not yet runnable end to end)
- Run tests: `python -m pytest tests/ -q`
- Run model evals: `python evals/shotbench/run_benchmark.py --models all --key-only --skip-video`
- Dev server: `cd web && npm run dev` (Next.js 16, React 19, Tailwind 4)
- Frontend checks: `cd web && npx tsc --noEmit && npm run lint && npm run build`

`web/src/lib/template.ts` mirrors `pipeline/template.py`. The template crosses a
language boundary, so the no-absolute-seconds rule holds on both sides: the UI
derives seconds via `resolve(bpm)` and never reads them off the template. Change
one, change the other, and bump `SCHEMA_VERSION` in both.

## Corrections to SPEC, established by measurement

These override SPEC where they conflict. Details in `evals/shotbench/README.md`
and the stage module docstrings.

- **madmom is unusable.** Requires Python <3.10. SPEC names it as an option for
  stage 2; it is not one. Use `beat_this` — CPU-capable, provides the downbeats
  librosa lacks, and measured 8.5ms MAE against librosa's 22.4ms.
- **librosa alone cannot satisfy the timing rule.** It has no downbeat tracker,
  so phrase position — which this file mandates — is unbuildable on it.
- **Detecting transitions is not the same as rendering them.** v1 renders hard
  cuts only, but reference reels contain dissolves and PySceneDetect scores
  0.00 F1 on them *silently*. Stage 1 must flag them or the template is wrong.
- **Thinking tokens bill as output** and are ~100% of output cost on Gemini 3
  for short answers. Any cost estimate counting input tokens only is ~2x low.
  `pipeline/costlog.py` tracks them separately.
- **Vision model default is `gemini-3.5-flash-lite`**, chosen on measured
  accuracy-per-rupee, not preference. It is also not on introductory pricing,
  so it does not double on 2027-01-01.
