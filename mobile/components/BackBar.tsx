import { useRouter } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Press from "./Press";
import { color, space, type } from "../lib/theme";

const STEPS = 3;

/**
 * Where you are, and how to get out.
 *
 * Every screen should answer both. The step marker is three rules rather than
 * numbered circles: it reads as progress at a glance and adds no chrome to
 * argue with the content.
 *
 * Not glass. This sits on the plain background rather than over footage, and
 * glass with nothing behind it is just a grey rectangle.
 */
export default function BackBar({
  step,
  onBack,
}: {
  step: 1 | 2 | 3;
  onBack?: () => void;
}) {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.bar, { paddingTop: insets.top + space(2) }]}>
      <Press
        onPress={onBack ?? (() => router.back())}
        style={styles.back}
        hitSlop={16}
        accessibilityLabel="Go back"
      >
        <Text style={styles.chevron}>‹</Text>
        <Text style={styles.label}>Back</Text>
      </Press>

      <View
        style={styles.steps}
        accessibilityRole="progressbar"
        accessibilityLabel={`Step ${step} of ${STEPS}`}
      >
        {Array.from({ length: STEPS }, (_, i) => {
          const n = i + 1;
          return (
            <View
              key={n}
              style={[
                styles.rule,
                n === step && styles.ruleCurrent,
                n < step && styles.ruleDone,
              ]}
            />
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: space(5),
    paddingBottom: space(6),
  },
  back: {
    position: "absolute",
    left: space(5),
    bottom: space(5),
    flexDirection: "row",
    alignItems: "center",
    gap: space(1),
  },
  chevron: { ...type.title, color: color.ink2, fontWeight: "400", marginTop: -2 },
  label: { ...type.caption, color: color.ink2 },

  steps: { flexDirection: "row", gap: space(2) },
  rule: { width: 26, height: 1, backgroundColor: color.line },
  ruleCurrent: { backgroundColor: color.ink },
  ruleDone: { backgroundColor: color.ink, opacity: 0.35 },
});
