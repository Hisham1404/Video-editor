# Backend backlog

What exists, what doesn't, and what blocks what. Status as of 2026-09-10.

The web UI runs on mock data. **There is no server between them yet** — that is
the largest single gap, and it isn't any one pipeline stage.

## Done

| Piece | State |
|---|---|
| `pipeline/template.py` | Implemented. 26 tests, incl. tempo portability at 78/96.5/120/174 BPM |
| `pipeline/costlog.py` | Implemented. Untested |
| `pipeline/config.py`, `cli.py` | Wiring only; `cli.py` fails at stage 1 by design |
| `evals/shotbench/run_benchmark.py` | Implemented, parser verified on all 3,572 rows |
| `web/` | 4 routes, builds clean, mock data |

## P0 — blocks everything downstream

### 1. Run the GPU benchmark

**This is the pending decision, and it gates stage 3's whole shape.** If a local
ShotVL beats Gemini on shot size and framing, the pipeline has *no metered
component at all* — which changes the cost model, the hosting model, and the
architecture of stage 3.

- Rent an RTX 4090 (Shadeform, $0.46/hr on-demand, $0.18 spot). ~$2–3 total.
- `python evals/shotbench/run_benchmark.py --models all --key-only --skip-video`
- **Calibration gate:** ShotVL-7B must land near the published 70.1 overall. If
  it doesn't, the harness is wrong and no other row is trustworthy.
- Also finish the `gemini-3.8-flash` arm — it never completed locally (503 on
  ~83% of calls). Retry off-peak.
- The transformers inference path is **unexercised** — no GPU has run it. The
  60-item smoke test surfaces any processor mismatch in about a minute.

Blocks: stage 3, the cost model, the hosting decision.

### 2. Stages 1, 2, 4 — the free, local, fully-specified ones

No external dependency, no cost, no open questions. These make the template
real end to end and unblock everything after it.

- **Stage 1 — segmentation.** PySceneDetect `ContentDetector`, plus the
  dissolve guard. Non-negotiable: PySceneDetect scores **0.00 F1 on crossfades
  and fails silently**, so undetected transitions must be flagged, not guessed.
- **Stage 2 — rhythm.** `beat_this`, CPU-capable, 18.7× realtime. Not madmom
  (needs Python <3.10), not librosa alone (no downbeat tracker, so phrase
  position is unbuildable on it).
- **Stage 4 — assembly.** Snap shot boundaries to the reference beat grid and
  store as rhythm. This is the one place seconds are converted and discarded;
  `assert_no_absolute_time` already enforces the boundary.

## P1

### 3. Stage 3 — shot description

Shape depends on item 1. Either a local VLM served on the GPU box, or the
Gemini REST path already proven in the harness.

- Load the prompt from `prompts/shot_description/v1.md`, never inline.
- Every call through `CostLog`. Allow enough output tokens for thinking or
  Gemini 3 returns an empty string with `finishReason=MAX_TOKENS`.

### 4. Stages 5 and 6 — ingestion and matching

**Budget the most time here.** SPEC: matching decides whether this feels
magical or broken, and it is the least glamorous part.

- Embedding is a one-time per-asset cost and cached, so a slower, better model
  is affordable here in a way it is not per-job.
- Evaluate `Qwen3-VL-Embedding-2B/8B` (Apache 2.0, 2026-04) against CLIP.
  They're jointly multimodal, so a slot's text description and a candidate clip
  embed into one space — exactly the operation stage 6 needs. CLIP is 2021.
- **`CONFIDENCE_FLOOR = 0.55` is a guess.** It decides which slots become
  generation prompts, so a miscalibrated threshold either floods the user with
  prompts or silently ships bad matches. Calibrate against golden fixtures.

### 5. The API layer — currently missing entirely

There is no server. The UI cannot reach the pipeline.

- Job submission, status polling, result retrieval.
- Object storage: Cloudflare R2 or Backblaze B2. Egress is the main hosting
  risk, which is why those two.
- A queue. Analysis is minutes, not milliseconds — it cannot run in a request.
- **The GPU cost model forces a decision here:** a 4090 is ~$0.005/job but
  ~$336/month left idle, against SPEC's $10–30/month hosting budget. Either
  batch jobs and spin the GPU per batch, or serve live traffic through the API.

## P2

### 6. Stages 7 and 8

- **Stage 7 — gap prompts.** Emit text. Never call a generation API.
- **Stage 8 — render.** ffmpeg, hard cuts only. Seconds come from
  `Template.resolve(bpm)` against the *user's* track, never off the template.

### 7. Evals and fixtures

- `evals/golden/` is **empty**. Needs 2–3 reference reels **owned outright** —
  copyrighted reels are fine as private input but cannot appear in a README,
  demo or paper (SPEC §10).
- First fixture worth commissioning: one containing dissolves, the case
  PySceneDetect is measured to fail on completely.
- Track per CLAUDE.md: matching quality, style fidelity, cost per job, p95
  latency, severity-classified failure catalogue.

### 8. Test coverage

Only `template.py` is tested. `costlog.py` has none, and every stage will need
its own as it lands.

## Known open questions

- Fixed shot-size taxonomy (wide/medium/close/extreme) vs free-text embedded.
- How many reference styles the matcher needs before it generalises.
- Whether stage 3 can take video natively instead of sampled frames. Frame
  sampling destroys camera motion, which is why that dimension scores worst for
  every model — and it's a v2 headline feature.
