import * as Haptics from "expo-haptics";
import { useCallback } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, {
  useAnimatedProps,
  useAnimatedReaction,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from "react-native-reanimated";
import { scheduleOnRN } from "react-native-worklets";
import { color, radius, space, spring, type } from "../lib/theme";

const MIN = 60;
const MAX = 180;

const AnimatedTextInput = Animated.createAnimatedComponent(TextInput);

/** Past the end the value follows less the further you push. Real things slow
 *  before they stop; a hard clamp reads as frozen. */
function rubberband(overshoot: number, dimension: number, c = 0.55) {
  "worklet";
  return (overshoot * dimension * c) / (dimension + c * Math.abs(overshoot));
}

/**
 * Tempo, dragged rather than typed.
 *
 * This is the app's argument: cut timings are stored as beat index and phrase
 * position, never seconds, so dragging the tempo re-times every shot in real
 * time while its beats stay put. Feeling that is faster than reading it.
 *
 * Everything here runs on the UI thread. The readout is an uncontrolled
 * TextInput driven by `animatedProps`, which is the one way to change text
 * every frame without a React render — a `setState` per frame is the single
 * biggest cause of jank in a React Native gesture.
 *
 * React only hears about the value once, in `onEnd`.
 */
export default function Tempo({
  bpm,
  onCommit,
}: {
  bpm: number;
  onCommit: (bpm: number) => void;
}) {
  const width = useSharedValue(0);
  const value = useSharedValue(bpm); // live, fractional
  const overshoot = useSharedValue(0); // visual only, never leaks into `value`

  const commit = useCallback(
    (v: number) => onCommit(Math.round(v)),
    [onCommit],
  );

  const setFromX = (x: number) => {
    "worklet";
    const w = width.get();
    if (w <= 0) return;
    const raw = MIN + (x / w) * (MAX - MIN);
    value.set(Math.min(MAX, Math.max(MIN, raw)));

    if (raw < MIN) overshoot.set(-rubberband(((MIN - raw) / (MAX - MIN)) * w, w));
    else if (raw > MAX) overshoot.set(rubberband(((raw - MAX) / (MAX - MIN)) * w, w));
    else overshoot.set(0);
  };

  const pressed = useSharedValue(0);

  const pan = Gesture.Pan()
    .onBegin((e) => {
      pressed.set(withSpring(1, spring.settle));
      setFromX(e.x);
    })
    .onUpdate((e) => {
      setFromX(e.x);
    })
    .onEnd(() => {
      pressed.set(withSpring(0, spring.settle));
      overshoot.set(withSpring(0, spring.release));
      // The only hop back to the RN runtime, and it happens once.
      scheduleOnRN(commit, value.get());
    });

  // A detent every whole BPM. Fired from a reaction at the threshold, never
  // from onUpdate — that would be 60–120 haptics a second.
  useAnimatedReaction(
    () => Math.round(value.get()),
    (now, prev) => {
      if (prev !== null && now !== prev) scheduleOnRN(Haptics.selectionAsync);
    },
  );

  const readout = useAnimatedProps(() => ({
    text: `${Math.round(value.get())}`,
    defaultValue: `${Math.round(value.get())}`,
  }));

  const trackStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: overshoot.get() }],
  }));

  const knobStyle = useAnimatedStyle(() => {
    const pct = (value.get() - MIN) / (MAX - MIN);
    return {
      transform: [
        { translateX: pct * width.get() },
        { scale: 1 + pressed.get() * 0.35 },
      ],
    };
  });

  return (
    <View>
      <Text style={styles.title}>Your tempo</Text>
      <Text style={styles.caption}>The reference was cut at 120 BPM</Text>

      <View style={styles.readoutRow}>
        <AnimatedTextInput
          editable={false}
          // The value comes from animatedProps every frame; React never
          // re-renders this node.
          animatedProps={readout}
          style={styles.readout}
          accessibilityElementsHidden
        />
        <Text style={styles.unit}>BPM</Text>
      </View>

      <GestureDetector gesture={pan}>
        <Animated.View
          style={[styles.hit, trackStyle]}
          onLayout={(e) => width.set(e.nativeEvent.layout.width)}
          accessibilityRole="adjustable"
          accessibilityLabel="Tempo in beats per minute"
          accessibilityValue={{ min: MIN, max: MAX, now: bpm }}
          accessibilityActions={[{ name: "increment" }, { name: "decrement" }]}
          onAccessibilityAction={(e) => {
            const next =
              e.nativeEvent.actionName === "increment" ? bpm + 1 : bpm - 1;
            const clamped = Math.min(MAX, Math.max(MIN, next));
            value.set(clamped);
            onCommit(clamped);
          }}
        >
          <View style={styles.rail} />
          <Animated.View style={[styles.knob, knobStyle]} />
        </Animated.View>
      </GestureDetector>

      <View style={styles.scale}>
        <Text style={styles.micro}>{MIN}</Text>
        <Text style={styles.micro}>Drag to re-time the cut</Text>
        <Text style={styles.micro}>{MAX}</Text>
      </View>
    </View>
  );
}

const KNOB = 14;

const styles = StyleSheet.create({
  title: { ...type.title, color: color.ink, textAlign: "center" },
  caption: {
    ...type.caption,
    color: color.ink2,
    textAlign: "center",
    marginTop: space(1),
  },

  readoutRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "center",
    gap: space(1.5),
    marginTop: space(3),
  },
  readout: {
    fontSize: 52,
    lineHeight: 56,
    letterSpacing: -2,
    fontWeight: "700",
    color: color.ink,
    padding: 0,
    minWidth: 110,
    textAlign: "center",
    fontVariant: ["tabular-nums"],
  },
  unit: { ...type.micro, color: color.ink2, marginBottom: space(2) },

  // 44pt of touch target around a 1pt rail.
  hit: { height: 44, justifyContent: "center", marginTop: space(4) },
  rail: { height: 1, backgroundColor: color.line2 },
  knob: {
    position: "absolute",
    width: KNOB,
    height: KNOB,
    borderRadius: KNOB / 2,
    backgroundColor: color.ink,
    marginLeft: -KNOB / 2,
  },

  scale: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: space(2),
  },
  micro: { ...type.micro, color: color.ink2 },
});
