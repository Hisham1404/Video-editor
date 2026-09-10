# Golden fixtures

**Append-only. Do not delete or mutate anything in this directory.**

That rule is from CLAUDE.md and it exists because a regression suite you edit
when it fails is not a regression suite. If a fixture's expected output is
genuinely wrong, add a corrected fixture alongside it and note why here -- do
not quietly change the old one.

## Layout

```
golden/
  <fixture-name>/
    reference.mp4      the reference reel
    music.wav          the user's track to render against
    assets/            the user's clips and stills
    expected.json      expected template (rhythm-relative, no seconds)
    notes.md           what this fixture is testing, and its provenance
```

## What each fixture must record

- **Provenance.** Who shot it, or where it came from. SPEC section 10: a
  copyrighted reel is fine as private reference input, but must never appear in
  a public demo, README or paper figure. Fixtures used in anything public must
  be owned outright.
- **What it is testing.** "Fast cuts on the downbeat", "long holds across a
  phrase boundary", "dissolves that PySceneDetect will miss".

## Known gaps in coverage

- No fixture yet contains gradual transitions, which is the one case
  PySceneDetect is measured to fail completely (0.00 F1 on crossfades).
  This is the first fixture worth commissioning.
