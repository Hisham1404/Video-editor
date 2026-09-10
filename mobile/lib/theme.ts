/**
 * The palette, type scale and motion constants.
 *
 * Near-black rather than pure black: `#000` flattens the sense of depth that
 * glass depends on, because there is nothing behind the material to refract.
 * Colour comes from the footage — the interface itself is greyscale plus one
 * accent, and that accent means exactly one thing.
 */

import { Easing } from "react-native-reanimated";

export const color = {
  bg: "#0A0A0B",
  raise: "#161618", // a lifted surface where glass isn't available
  sunken: "#1C1C1F",

  ink: "#F5F5F7",
  ink2: "#8E8E93",
  ink3: "#5A5A5F",

  line: "rgba(255,255,255,0.09)",
  line2: "rgba(255,255,255,0.16)",

  /** The only colour with meaning: this shot has no clip. */
  accent: "#F5A04A",
  accentSoft: "rgba(245,160,74,0.16)",

  /** Sits on top of a frame, so it must read against any footage. */
  scrim: "rgba(0,0,0,0.45)",
} as const;

/**
 * Tracking is size-specific. Large text reads too loose as it grows and wants
 * negative tracking; the smallest labels want a little positive to stay legible.
 * A single letterSpacing value is wrong somewhere.
 */
export const type = {
  display: { fontSize: 34, lineHeight: 38, letterSpacing: -1.1, fontWeight: "700" },
  title: { fontSize: 20, lineHeight: 25, letterSpacing: -0.45, fontWeight: "600" },
  body: { fontSize: 16, lineHeight: 23, letterSpacing: -0.2, fontWeight: "400" },
  caption: { fontSize: 14, lineHeight: 20, letterSpacing: -0.1, fontWeight: "400" },
  micro: { fontSize: 12, lineHeight: 16, letterSpacing: 0.2, fontWeight: "500" },
  eyebrow: { fontSize: 11, lineHeight: 13, letterSpacing: 1.1, fontWeight: "600" },
} as const;

export const radius = { sm: 8, md: 12, lg: 18, xl: 26, pill: 999 } as const;

export const space = (n: number) => n * 4;

/**
 * The built-in easings are too weak to read as intentional, on any platform.
 * `ease-in` never appears: it delays the exact moment the user is watching.
 */
export const ease = {
  out: Easing.bezier(0.23, 1, 0.32, 1),
  inOut: Easing.bezier(0.77, 0, 0.175, 1),
  sheet: Easing.bezier(0.32, 0.72, 0, 1),
} as const;

export const duration = {
  press: 120,
  fast: 180,
  base: 240,
} as const;

/** Apple's two designer parameters, which Reanimated takes directly. */
export const spring = {
  /** Settles without overshoot. The default for anything not thrown. */
  settle: { duration: 400, dampingRatio: 1 },
  /** For a release that carried momentum — a flick earns the overshoot. */
  release: { duration: 400, dampingRatio: 0.8 },
  sheet: { duration: 300, dampingRatio: 0.8 },
} as const;
