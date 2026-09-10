import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import BackBar from "../components/BackBar";
import { STAGES } from "../lib/template";
import { color, duration, ease, space, type } from "../lib/theme";

const STEP_MS = 460;

/**
 * The analysis run.
 *
 * Seen once per job, so this is where the delight budget belongs — but it is
 * still a progress view, not a show. It names the stage that is running and
 * marks the one that costs money, because cost per job is a number this project
 * tracks rather than hides.
 */
export default function Analysing() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [step, setStep] = useState(0);
  const progress = useSharedValue(0);

  useEffect(() => {
    if (step >= STAGES.length) {
      // Rare tier, and the one moment worth a success haptic.
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      const t = setTimeout(() => router.replace("/cut"), 420);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setStep((s) => s + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [step, router]);

  useEffect(() => {
    // Linear: an eased progress bar lies about the rate.
    progress.set(
      withTiming(step / STAGES.length, { duration: STEP_MS, easing: (t) => t }),
    );
  }, [step, progress]);

  // The fill is absolutely positioned and childless — the one case where
  // animating width is correct, because nothing else re-lays-out and the
  // corner radius survives, which scaleX would smear.
  const fill = useAnimatedStyle(() => ({
    width: `${progress.get() * 100}%`,
  }));

  return (
    <View style={styles.screen}>
      <BackBar step={2} />
      <View style={[styles.body, { paddingBottom: insets.bottom + space(8) }]}>
        <Text style={styles.title}>Reading the reference</Text>
        <Text style={styles.caption}>
          Shot boundaries, then rhythm, then what each shot is doing.
        </Text>

        <View style={styles.track}>
          <Animated.View style={[styles.fill, fill]} />
        </View>

        <View style={styles.list}>
          {STAGES.map((s, i) => {
            const state = i < step ? "done" : i === step ? "running" : "waiting";
            return (
              <View
                key={s.n}
                style={[styles.row, state === "waiting" && styles.rowWaiting]}
              >
                <View style={[styles.mark, state === "done" && styles.markDone]}>
                  {state === "done" && <Text style={styles.tick}>✓</Text>}
                  {state === "running" && <Pulse />}
                </View>
                <Text style={styles.stage}>{s.name}</Text>
                {s.metered && <Text style={styles.metered}>metered</Text>}
              </View>
            );
          })}
        </View>
      </View>
    </View>
  );
}

/** A single looping opacity, on the UI thread. */
function Pulse() {
  const o = useSharedValue(0.35);
  useEffect(() => {
    o.set(
      withTiming(1, { duration: 550, easing: ease.inOut }),
    );
  }, [o]);
  const style = useAnimatedStyle(() => ({ opacity: o.get() }));
  return <Animated.View style={[styles.dot, style]} />;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.bg },
  body: { flex: 1, paddingHorizontal: space(5), alignItems: "center" },

  title: { ...type.title, color: color.ink, textAlign: "center" },
  caption: {
    ...type.caption,
    color: color.ink2,
    textAlign: "center",
    marginTop: space(1),
    maxWidth: 300,
  },

  track: {
    width: "100%",
    maxWidth: 320,
    height: 1,
    backgroundColor: color.line,
    marginTop: space(8),
    overflow: "hidden",
  },
  fill: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    backgroundColor: color.ink,
  },

  list: { marginTop: space(8), width: "100%", maxWidth: 320 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: space(2.5),
    paddingVertical: space(2.5),
  },
  rowWaiting: { opacity: 0.32 },

  mark: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 1,
    borderColor: color.line2,
    alignItems: "center",
    justifyContent: "center",
  },
  markDone: { backgroundColor: color.ink, borderColor: color.ink },
  tick: { color: color.bg, fontSize: 11, fontWeight: "700", lineHeight: 13 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: color.ink },

  stage: { ...type.body, color: color.ink },
  metered: { ...type.micro, color: color.accent },
});
