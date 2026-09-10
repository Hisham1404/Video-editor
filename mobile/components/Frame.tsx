import { LinearGradient } from "expo-linear-gradient";
import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { color, radius } from "../lib/theme";
import { type Slot, isGap, shotSizeRank } from "../lib/template";

/**
 * A stand-in for a frame of footage.
 *
 * There is no real video yet, so rather than pull stock photos — which would
 * misrepresent someone's own footage — each shot gets a deterministic, filmic
 * wash derived from its index and shot size. Desaturated on purpose: it should
 * read as "a frame goes here", carry enough difference that you can tell shots
 * apart, and never compete with the interface.
 *
 * Swap the body of this component for a real poster frame once the pipeline can
 * extract them; nothing else needs to change.
 */

function hash(n: number, salt: number) {
  const x = Math.sin(n * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

function hsl(h: number, s: number, l: number) {
  return `hsl(${h.toFixed(1)}, ${s.toFixed(1)}%, ${l.toFixed(1)}%)`;
}

/** Two colours plus an angle, for any seed. */
export function wash(seed: number, rank = 3) {
  const hue = 190 + hash(seed, 1) * 60; // cool-to-warm drift, narrow band
  const sat = 8 + hash(seed, 2) * 10;
  const light = 58 - rank * 4.5; // wider shots read brighter
  return {
    from: hsl(hue, sat, light + 10),
    to: hsl(hue + 18, sat + 4, Math.max(12, light - 22)),
    start: { x: hash(seed, 4), y: 0 },
    end: { x: 1 - hash(seed, 4), y: 1 },
  };
}

export default function Frame({
  slot,
  style,
  rounded = radius.md,
  showMark = false,
}: {
  slot: Slot;
  style?: StyleProp<ViewStyle>;
  rounded?: number;
  showMark?: boolean;
}) {
  if (isGap(slot)) {
    return (
      <View
        style={[
          styles.gap,
          { borderRadius: rounded },
          style,
        ]}
      >
        {showMark && <View style={styles.plusWrap}>
          <View style={styles.plusH} />
          <View style={styles.plusV} />
        </View>}
      </View>
    );
  }

  const w = wash(slot.index, shotSizeRank(slot.shot_size));
  return (
    <LinearGradient
      colors={[w.from, w.to]}
      start={w.start}
      end={w.end}
      style={[{ borderRadius: rounded, overflow: "hidden" }, style]}
    />
  );
}

/** For project cards, which have a seed but no slot. */
export function SeedFrame({
  seed,
  style,
  rounded = radius.sm,
}: {
  seed: number;
  style?: StyleProp<ViewStyle>;
  rounded?: number;
}) {
  const w = wash(seed);
  return (
    <LinearGradient
      colors={[w.from, w.to]}
      start={w.start}
      end={w.end}
      style={[{ borderRadius: rounded, overflow: "hidden" }, style]}
    />
  );
}

const styles = StyleSheet.create({
  gap: {
    borderWidth: 1.5,
    borderColor: color.accent,
    borderStyle: "dashed",
    backgroundColor: color.accentSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  plusWrap: { width: 20, height: 20, alignItems: "center", justifyContent: "center" },
  plusH: { position: "absolute", width: 18, height: 1.6, backgroundColor: color.accent },
  plusV: { position: "absolute", width: 1.6, height: 18, backgroundColor: color.accent },
});
