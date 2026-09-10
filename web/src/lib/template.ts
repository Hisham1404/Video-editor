/**
 * TypeScript mirror of pipeline/template.py.
 *
 * The template is the contract between analysis and render, so it also has to
 * survive the language boundary unchanged. Same rule applies on this side:
 * NO ABSOLUTE SECONDS. Timings are beat index, subdivision and phrase
 * position. Seconds are derived at display time by resolve(), which requires a
 * tempo, exactly as in Python.
 *
 * If you change this file, change pipeline/template.py and bump SCHEMA_VERSION
 * in both.
 */

export const SCHEMA_VERSION = "1.0";

export type ShotSize =
  | "extreme wide"
  | "wide"
  | "medium wide"
  | "medium"
  | "medium close up"
  | "close up"
  | "extreme close up"
  | "unknown";

export type Framing =
  | "single"
  | "two shot"
  | "three shot"
  | "group"
  | "over the shoulder"
  | "insert"
  | "establishing"
  | "unknown";

export type CameraMotion =
  | "static"
  | "pan left"
  | "pan right"
  | "tilt up"
  | "tilt down"
  | "push in"
  | "pull out"
  | "arc"
  | "handheld"
  | "unknown";

/** A point in time expressed purely as musical structure. */
export interface RhythmPosition {
  beat: number;
  subdivision: number;
  bar: number;
  beat_in_bar: number;
  phrase: number;
  beat_in_phrase: number;
}

export interface Slot {
  index: number;
  start: RhythmPosition;
  end: RhythmPosition;
  shot_size: ShotSize;
  framing: Framing;
  description: string;
  camera_motion: CameraMotion | null;
  matched_asset: string | null;
  match_confidence: number | null;
  generation_prompt: string | null;
}

export interface Template {
  schema_version: string;
  slots: Slot[];
  time_signature: [number, number];
  beats_per_phrase: number;
  reference_bpm: number | null;
  reference_id: string | null;
  notes: string;
}

/* ---------------------------------------------------------------- helpers */

export function absoluteBeats(p: RhythmPosition): number {
  return p.beat + p.subdivision;
}

/**
 * Convert a rhythm position to seconds against a specific tempo.
 * The only place seconds are produced, and it cannot be called without a bpm.
 */
export function resolve(p: RhythmPosition, bpm: number): number {
  if (bpm <= 0) throw new Error(`bpm must be positive, got ${bpm}`);
  return absoluteBeats(p) * (60 / bpm);
}

export function durationBeats(slot: Slot): number {
  return absoluteBeats(slot.end) - absoluteBeats(slot.start);
}

export function durationSeconds(slot: Slot, bpm: number): number {
  return durationBeats(slot) * (60 / bpm);
}

export function isGap(slot: Slot): boolean {
  return slot.matched_asset === null;
}

export function totalBeats(t: Template): number {
  return t.slots.length ? absoluteBeats(t.slots[t.slots.length - 1].end) : 0;
}

export function totalSeconds(t: Template, bpm: number): number {
  return totalBeats(t) * (60 / bpm);
}

export function formatBeat(p: RhythmPosition): string {
  // Musician-facing: bar.beat, 1-indexed, the way a DAW shows it.
  const sub = p.subdivision > 0 ? `+${p.subdivision.toFixed(2).slice(1)}` : "";
  return `${p.bar + 1}.${p.beat_in_bar + 1}${sub}`;
}

export function formatSeconds(s: number): string {
  const m = Math.floor(s / 60);
  const rest = s - m * 60;
  return `${m}:${rest.toFixed(2).padStart(5, "0")}`;
}

/** Shot sizes ordered wide to tight, for the timeline's vertical encoding. */
export const SHOT_SIZE_ORDER: ShotSize[] = [
  "extreme wide",
  "wide",
  "medium wide",
  "medium",
  "medium close up",
  "close up",
  "extreme close up",
];

export function shotSizeRank(s: ShotSize): number {
  const i = SHOT_SIZE_ORDER.indexOf(s);
  return i === -1 ? 3 : i;
}

/* ------------------------------------------------------------- mock data */

function pos(beat: number, subdivision = 0, beatsPerPhrase = 32): RhythmPosition {
  return {
    beat,
    subdivision,
    bar: Math.floor(beat / 4),
    beat_in_bar: beat % 4,
    phrase: Math.floor(beat / beatsPerPhrase),
    beat_in_phrase: beat % beatsPerPhrase,
  };
}

type Seed = {
  cut: number;
  size: ShotSize;
  framing: Framing;
  desc: string;
  motion: CameraMotion;
  asset: string | null;
  conf: number | null;
  prompt?: string;
};

// A ~30s reel at 120bpm: 16 shots over 64 beats. Cut density rises into the
// chorus at beat 32, which is the kind of structure the template is meant to
// carry across to a different track.
const SEEDS: Seed[] = [
  { cut: 0, size: "extreme wide", framing: "establishing", desc: "City skyline at dusk, lights coming on", motion: "static", asset: "skyline_0042.mp4", conf: 0.91 },
  { cut: 6, size: "medium", framing: "single", desc: "Subject walking toward camera on a wet street", motion: "push in", asset: "street_walk_02.mp4", conf: 0.84 },
  { cut: 10, size: "close up", framing: "insert", desc: "Hands zipping a jacket", motion: "static", asset: "hands_zip.mp4", conf: 0.77 },
  { cut: 14, size: "wide", framing: "single", desc: "Figure small against a concrete underpass", motion: "static", asset: null, conf: 0.31, prompt: "Wide shot, single figure standing small against a large concrete underpass, overcast diffuse light, static camera, cinematic, 24fps, 2 seconds" },
  { cut: 20, size: "medium close up", framing: "single", desc: "Subject looking off-frame, neon reflection on face", motion: "static", asset: "neon_face.mp4", conf: 0.88 },
  { cut: 24, size: "extreme close up", framing: "insert", desc: "Eye opening, catchlight from a passing car", motion: "static", asset: null, conf: 0.22, prompt: "Extreme close up of an eye opening, sharp catchlight from passing car headlights sweeping across, shallow depth of field, cinematic, 1 second" },
  { cut: 28, size: "medium wide", framing: "two shot", desc: "Two people crossing a road, mid conversation", motion: "pan left", asset: "crossing_2p.mp4", conf: 0.73 },
  // Chorus: cuts double in density.
  { cut: 32, size: "close up", framing: "single", desc: "Face turning sharply into frame", motion: "handheld", asset: "turn_face.mp4", conf: 0.81 },
  { cut: 34, size: "wide", framing: "group", desc: "Crowd moving through a lit tunnel", motion: "static", asset: "tunnel_crowd.mp4", conf: 0.69 },
  { cut: 36, size: "medium", framing: "single", desc: "Subject spinning, coat flaring", motion: "arc", asset: null, conf: 0.28, prompt: "Medium shot, person spinning in place with a long coat flaring outward, camera arcs around them, night, practical street lighting, cinematic, 1 second" },
  { cut: 38, size: "extreme close up", framing: "insert", desc: "Sneaker hitting a puddle", motion: "static", asset: "shoe_splash.mp4", conf: 0.86 },
  { cut: 40, size: "medium close up", framing: "single", desc: "Laughing, head tilted back", motion: "static", asset: "laugh.mp4", conf: 0.79 },
  { cut: 44, size: "extreme wide", framing: "establishing", desc: "Rooftop view, whole city in frame", motion: "pull out", asset: "rooftop_wide.mp4", conf: 0.92 },
  { cut: 50, size: "medium", framing: "over the shoulder", desc: "Over shoulder, looking at phone screen", motion: "static", asset: "ots_phone.mp4", conf: 0.64 },
  { cut: 56, size: "close up", framing: "single", desc: "Slow blink, resolving expression", motion: "static", asset: "blink_close.mp4", conf: 0.83 },
  { cut: 60, size: "wide", framing: "single", desc: "Walking away down the centre of the street", motion: "static", asset: "walk_away.mp4", conf: 0.75 },
];

export const MOCK_TEMPLATE: Template = {
  schema_version: SCHEMA_VERSION,
  time_signature: [4, 4],
  beats_per_phrase: 32,
  reference_bpm: 120,
  reference_id: "ref_dusk_city_01",
  notes: "Mock template. Replace with pipeline output once stages 1-4 land.",
  slots: SEEDS.map((s, i) => ({
    index: i,
    start: pos(s.cut),
    end: pos(i + 1 < SEEDS.length ? SEEDS[i + 1].cut : 64),
    shot_size: s.size,
    framing: s.framing,
    description: s.desc,
    camera_motion: s.motion,
    matched_asset: s.asset,
    match_confidence: s.conf,
    generation_prompt: s.prompt ?? null,
  })),
};

/* ------------------------------------------------------- pipeline stages */

export type StageState = "pending" | "running" | "done" | "warning";

export interface Stage {
  n: number;
  name: string;
  detail: string;
  metered: boolean;
  state: StageState;
}

export const STAGES: Stage[] = [
  { n: 1, name: "Shot segmentation", detail: "PySceneDetect", metered: false, state: "warning" },
  { n: 2, name: "Rhythm extraction", detail: "beat_this", metered: false, state: "done" },
  { n: 3, name: "Shot description", detail: "gemini-3.5-flash-lite", metered: true, state: "done" },
  { n: 4, name: "Template assembly", detail: "schema v1.0", metered: false, state: "done" },
  { n: 5, name: "Asset ingestion", detail: "CLIP ViT-B/32", metered: false, state: "done" },
  { n: 6, name: "Slot matching", detail: "confidence floor 0.55", metered: false, state: "done" },
  { n: 7, name: "Gap detection", detail: "prompts emitted", metered: false, state: "done" },
  { n: 8, name: "Render", detail: "ffmpeg, hard cuts", metered: false, state: "pending" },
];

/** Job metrics. CLAUDE.md treats cost per job as a tracked metric, so it is
 *  surfaced in the UI rather than buried in a log. */
export interface JobMetrics {
  costUsd: number;
  inTokens: number;
  billedOutTokens: number;
  thinkingTokens: number;
  p95LatencyS: number;
  calls: number;
  failedCalls: number;
  model: string;
}

export const MOCK_METRICS: JobMetrics = {
  costUsd: 0.0172,
  inTokens: 55_800,
  billedOutTokens: 157,
  thinkingTokens: 0,
  p95LatencyS: 2.31,
  calls: 50,
  failedCalls: 0,
  model: "gemini-3.5-flash-lite",
};
