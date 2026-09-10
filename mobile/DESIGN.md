# Reel Editor for iOS — design brief

The spec this app is built to. Written first, on purpose: the interface has to be
decided before it is typed.

## What the app is

You bring a reel whose editing you admire, your own clips, and your own music.
The app reads the reference's *editing grammar* — how long shots hold, where cuts
land against the beat, how shots are framed and ordered — and reapplies it to
your footage. Where nothing of yours fits a slot, it hands you a prompt to
generate that shot elsewhere and takes the clip back.

Generation never runs in the app. Prompts out, clips in.

## The surface, completely

Four screens. Nothing else exists.

### 1. Projects — the launch screen

| Element | Behaviour |
|---|---|
| Title, project count | Static |
| **Start a new cut** | Primary. Pushes `/new` |
| Recent list | Poster frame, name, date, shot count, gaps. Tap opens the cut |

No overflow menus. Rename, duplicate and delete need a backend that doesn't
exist; a control that opens nothing is worse than no control.

### 2. New cut — three sources

| Element | Behaviour |
|---|---|
| Headline + one sentence | Static |
| Reference reel | Picker. One video |
| Your footage | Picker. Many clips and stills |
| Your music | Picker. One track |
| **Analyse the reference** | Disabled until all three are present |

Each row is a check mark, a title, and a hint that becomes "3 files selected".

### 3. Reading — the analysis run

Eight named stages, ticking in order: shot segmentation, rhythm extraction, shot
description, template assembly, asset ingestion, slot matching, gap detection,
render. Stage 3 is marked **metered** — it is the only one that costs money, and
this project tracks cost per job rather than hiding it.

One hairline fills left to right. Linear: an eased progress bar lies about rate.

### 4. The cut — the working screen

| Element | Behaviour |
|---|---|
| Poster | 9:16, the selected shot. Shot n/16, shot size, beats + seconds |
| Filmstrip | Every shot in order, each as wide as it holds. Tap to select |
| Shot detail | Description, size, framing, camera, duration |
| Gap detail | Generation prompt, **Copy prompt**, **Upload the clip** |
| Tempo | Drag 60–180 BPM. The cut re-times live |
| **Render** | Disabled until stage 8 exists |

**The tempo drag is the app's argument.** Cut timings are stored as beat index,
subdivision and phrase position — never seconds. Drag the tempo and every shot's
seconds change while its beats do not. That is why the same cut can move to any
track, and dragging it is the fastest way to understand the product.

## The look

Reference: **Apple TV**. Not its content, its posture.

1. **Content is the interface.** The frames are the brightest thing on screen.
   Chrome is glass laid over them, never a panel that takes their space.
2. **The background is near-black and stays near-black.** Colour comes from the
   footage. `#0A0A0B`, not `#000` — pure black kills the sense of depth glass
   depends on.
3. **One accent, one meaning.** Amber says exactly one thing: this shot has no
   clip. Nothing else is coloured.
4. **Type carries hierarchy, not boxes.** Large tight-tracked titles, generous
   space, few rules. Tracking is size-specific — negative on display, near zero
   on body, slightly positive on the smallest labels.

### Liquid Glass, and the honest part

`expo-glass-effect` renders real `UIVisualEffectView` glass — but **iOS 26+
only**. On older iOS and on every Android device it falls back to a plain `View`,
which would leave the app looking flat and unfinished rather than deliberately
different.

So glass is a three-tier primitive, decided once in `components/Glass.tsx`:

| Platform | Surface |
|---|---|
| iOS 26+ | `GlassView` — real liquid glass, `isInteractive` on controls |
| Older iOS | `BlurView` — a blur, tinted, with a bright top edge |
| Android | Solid elevated surface, one step lighter than the background |

Every tier is designed, none is a degradation the user can feel as a bug.

**Two hard constraints from the API:**

- Setting `opacity: 0` on a `GlassView` *or any parent* stops the effect
  rendering at all. Fades must use `glassEffectStyle`'s own `animate` /
  `animationDuration`, never opacity.
- Never animate blur intensity. On Android it re-renders the blur every frame.
  Cross-fade a static layer instead.

Where several glass controls sit together, `GlassContainer` with a `spacing`
lets them merge as they approach — the behaviour that makes the material read as
liquid rather than as frosted rectangles.

## Motion

Gated by frequency, before anything is written.

| Interaction | Tier | Decision |
|---|---|---|
| Tab / screen switch | 100+/day | Platform default. Never a hand-rolled slide |
| Press feedback | tens/day | `scale 0.97`, 120ms. Nothing more |
| Selecting a shot | tens/day | Instant. Content must never wait on a decoration |
| Tempo drag | continuous | Shared value, UI thread, spring on release |
| Sheet | occasional | Native `formSheet`, or a spring at `dampingRatio 0.8` |
| Analysis complete | rare | The delight budget lives here, and only here |

**Everything a finger touches runs on the UI thread.** Shared value plus
`useAnimatedStyle`; never `setState` in a gesture handler. `transform` and
`opacity` only — every other property re-runs layout on the node and its
siblings each frame.

**Haptics, sparingly.** `selectionAsync` when the tempo ticks past a whole BPM,
`impactAsync(Light)` when a drag commits, `notificationAsync(Success)` once when
analysis finishes. Never per frame, never as the only feedback — haptics are off
system-wide for many people and silent on most Android hardware.

**Reduced motion ships with the animation.** Fewer and gentler, not zero: keep
the opacity and colour changes that explain a state change, drop travel,
overshoot and parallax.

## What this design refuses

- No tab bar. Four screens in one linear flow do not need one.
- No modal for the shot detail. There is room for it inline, and covering the
  cut to describe one shot of it is a worse trade.
- No skeleton shimmer. The analysis screen names what is happening, which is
  more informative than a pulsing grey rectangle.
- No onboarding carousel. The first screen is the product.
- No gradient buttons, no glow, no floating particles. Glass is the effect; it
  does not need help.
