# Reference-driven reel editor

Upload a reel you admire, your own raw clips, and your own music. The system
extracts the reference's *editing grammar* -- how long shots hold, where cuts
land against the beat, how shots are framed and ordered -- and reapplies it to
your footage on your track. Where no clip of yours fits a slot, it hands you a
generation prompt instead.

Context: `SPEC.md` (what and why) - `CLAUDE.md` (build rules) -
`PROJECT_DECISION_LOG.md` (how the project was chosen).

## Status

Scaffolded. The template contract and cost accounting are implemented and
tested; the eight pipeline stages are stubs.

| Stage | Module | State |
|---|---|---|
| 1 Shot segmentation | `pipeline/stages/s1_segment.py` | stub |
| 2 Rhythm extraction | `pipeline/stages/s2_rhythm.py` | stub |
| 3 Per-shot description | `pipeline/stages/s3_describe.py` | stub (metered) |
| 4 Template assembly | `pipeline/stages/s4_assemble.py` | stub |
| 5 Asset ingestion | `pipeline/stages/s5_ingest.py` | stub |
| 6 Slot matching | `pipeline/stages/s6_match.py` | stub |
| 7 Gap detection | `pipeline/stages/s7_gaps.py` | stub |
| 8 Render | `pipeline/stages/s8_render.py` | stub |
| Template contract | `pipeline/template.py` | **done, 26 tests** |
| Cost accounting | `pipeline/costlog.py` | **done** |
| Frontend | `web/` | **done (UI on mock data)** |

## Frontend

```bash
cd web && npm run dev      # http://localhost:3000
```

Next.js 16 / React 19 / Tailwind 4. Runs on mock template data, since the
pipeline stages are stubs — but the mock is the *real* schema, so wiring the
backend in should not change the components.

The tempo slider is the load-bearing demo: drag it and every cut moves in
wall-clock time while staying locked to the same beat. Slot duration stays
"6 beats" and only the derived seconds change. That is the entire argument for
storing rhythm instead of seconds, made visible.

The UI also surfaces cost per job, p95 latency and failed-call count in the
header bar rather than hiding them in a log, because CLAUDE.md treats those as
tracked metrics. There is deliberately no "Generate" button on gap slots — the
app emits prompts and accepts clips back, and never calls a generation API.

## The one rule that shapes everything

Cut timings are never stored in seconds. They are stored as rhythm -- beat
index, subdivision, and phrase position -- so a timeline can be re-mapped onto
any track at any tempo. The reference's music cannot ship with the output, so a
timeline pinned to wall-clock time is worthless.

This is enforced in code, not documentation: `Template.from_dict` rejects any
key that looks like absolute time, and seconds only exist as the output of
`Template.resolve(bpm)`, which cannot be called without naming a tempo.

## Measured findings so far

Established by running things, not by reading docs. Details in
`evals/shotbench/README.md`.

| Finding | Consequence |
|---|---|
| PySceneDetect scores **0.00 F1** on crossfades, silently | Dissolve guard needed in stage 1 even though v1 renders hard cuts only |
| librosa beats land **+22.4ms late**, tempo off by 2.1%, no downbeats | Use `beat_this` (8.5ms MAE, has downbeats) |
| madmom requires Python <3.10 | Unusable; SPEC needs updating |
| Gemini 3 thinking tokens are **~100% of billed output** | Cost model was ~2x low; `costlog` tracks them separately |
| `gemini-3.5-flash-lite`: **87.1%** on shot size + framing, $0.017/reference | Current default. Cheaper *and* better than 3.8-flash |
| `gemini-3.8-flash`: 6.7x cost, 8x latency, 503 on ~83% of calls | Not viable today |

## Setup

```bash
python -m venv .venv && .venv/Scripts/activate     # Windows
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
cp .env.example .env        # then add your key
```

## Next

1. Benchmark ShotVL-7B against Gemini on a GPU (`evals/shotbench`). If the
   local model wins, the pipeline has no metered component at all.
2. Commission 2-3 reference reels owned outright -- SPEC section 10 blocks
   public demos using copyrighted reels.
3. Implement stages 1, 2 and 4, which are free, local, and unblock the template.
