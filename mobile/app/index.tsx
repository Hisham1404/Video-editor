import { useRouter } from "expo-router";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import Animated, { FadeIn } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Glass from "../components/Glass";
import { SeedFrame } from "../components/Frame";
import Press from "../components/Press";
import { PROJECTS, formatWhen } from "../lib/projects";
import { color, radius, space, type } from "../lib/theme";

/**
 * Where you land.
 *
 * Opening straight into a file picker assumes every visit is a new job. Most
 * aren't — you come back to something you already started. So: start a new cut,
 * or reopen one.
 *
 * No overflow menus on the rows. Rename, duplicate and delete need a backend
 * that doesn't exist, and a control that opens nothing is worse than none.
 */
export default function Projects() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={{
        paddingTop: insets.top + space(6),
        paddingBottom: insets.bottom + space(10),
        paddingHorizontal: space(5),
      }}
      showsVerticalScrollIndicator={false}
    >
      <Text style={styles.display}>Reel Editor</Text>
      <Text style={styles.caption}>
        {PROJECTS.length} projects
      </Text>

      {/* The primary action is glass because it sits at the top of the
          hierarchy, not because glass is available. */}
      <Press
        onPress={() => router.push("/new")}
        scaleTo={0.985}
        style={styles.newWrap}
        accessibilityLabel="Start a new cut"
      >
        <Glass variant="regular" rounded={radius.xl} style={styles.newCard} interactive>
          <View style={styles.plusBadge}>
            <View style={styles.plusH} />
            <View style={styles.plusV} />
          </View>
          <View style={styles.flex}>
            <Text style={styles.cardTitle}>Start a new cut</Text>
            <Text style={styles.caption}>
              A reference reel, your footage, a track
            </Text>
          </View>
        </Glass>
      </Press>

      <Text style={styles.eyebrow}>RECENT</Text>

      {PROJECTS.map((p, i) => (
        <Animated.View
          key={p.id}
          // Rare tier: a first-paint stagger, seen once per launch.
          entering={FadeIn.delay(60 + i * 45).duration(260)}
        >
          <Press
            onPress={() => router.push("/cut")}
            scaleTo={0.985}
            style={[styles.row, i > 0 && styles.rowDivider]}
            accessibilityLabel={`${p.name}, ${p.shots} shots, ${p.gaps} to generate`}
          >
            <SeedFrame seed={p.seed} style={styles.thumb} rounded={radius.sm} />
            <View style={styles.flex}>
              <Text style={styles.rowTitle} numberOfLines={1}>
                {p.name}
              </Text>
              <Text style={styles.caption} numberOfLines={1}>
                {formatWhen(p.updatedAt)} · {p.shots} shots
                {p.gaps > 0 && (
                  <Text style={styles.accent}>{`  ·  ${p.gaps} to generate`}</Text>
                )}
              </Text>
            </View>
            <Text style={styles.chevron}>›</Text>
          </Press>
        </Animated.View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.bg },
  flex: { flex: 1 },

  display: { ...type.display, color: color.ink },
  caption: { ...type.caption, color: color.ink2, marginTop: 2 },
  eyebrow: {
    ...type.eyebrow,
    color: color.ink3,
    marginTop: space(9),
    marginBottom: space(3),
  },
  accent: { color: color.accent },

  newWrap: { marginTop: space(7) },
  newCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: space(4),
    padding: space(4),
  },
  cardTitle: { ...type.body, color: color.ink, fontWeight: "600" },

  plusBadge: {
    width: 52,
    height: 52,
    borderRadius: radius.md,
    backgroundColor: color.ink,
    alignItems: "center",
    justifyContent: "center",
  },
  plusH: { position: "absolute", width: 20, height: 2, backgroundColor: color.bg, borderRadius: 1 },
  plusV: { position: "absolute", width: 2, height: 20, backgroundColor: color.bg, borderRadius: 1 },

  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: space(3.5),
    paddingVertical: space(3.5),
  },
  rowDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: color.line },
  thumb: { width: 42, height: 58 },
  rowTitle: { ...type.body, color: color.ink, fontWeight: "600" },
  chevron: { ...type.title, color: color.ink3, fontWeight: "400" },
});
