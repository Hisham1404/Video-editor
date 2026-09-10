import * as DocumentPicker from "expo-document-picker";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import BackBar from "../components/BackBar";
import Glass from "../components/Glass";
import Press from "../components/Press";
import { color, radius, space, type } from "../lib/theme";

const SOURCES = [
  {
    key: "reference",
    label: "Reference reel",
    hint: "The edit you want to borrow from",
    type: "video/*",
    multiple: false,
  },
  {
    key: "footage",
    label: "Your footage",
    hint: "Clips and stills to cut from",
    type: ["video/*", "image/*"],
    multiple: true,
  },
  {
    key: "track",
    label: "Your music",
    hint: "The reference's track can't ship with your reel",
    type: "audio/*",
    multiple: false,
  },
] as const;

type Counts = Partial<Record<(typeof SOURCES)[number]["key"], number>>;

export default function NewCut() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [counts, setCounts] = useState<Counts>({});
  const ready = SOURCES.every((s) => (counts[s.key] ?? 0) > 0);

  const pick = useCallback(
    async (key: (typeof SOURCES)[number]["key"], type: string | string[], multiple: boolean) => {
      const res = await DocumentPicker.getDocumentAsync({
        type: type as string | string[],
        multiple,
        copyToCacheDirectory: false,
      });
      if (res.canceled) return;
      setCounts((c) => ({ ...c, [key]: res.assets.length }));
      // One per user action, at the causal moment — the files landing.
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    },
    [],
  );

  return (
    <View style={styles.screen}>
      <BackBar step={1} />
      <ScrollView
        contentContainerStyle={{
          paddingHorizontal: space(5),
          paddingBottom: insets.bottom + space(10),
        }}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.display}>
          Cut your footage{"\n"}like the reel you admire.
        </Text>
        <Text style={styles.intro}>
          Bring an edit you like, your own clips, and your own music. Where
          nothing of yours fits, you&apos;ll get a prompt to generate the missing
          shot.
        </Text>

        <View style={styles.list}>
          {SOURCES.map((s, i) => {
            const n = counts[s.key] ?? 0;
            const filled = n > 0;
            return (
              <Press
                key={s.key}
                onPress={() => pick(s.key, s.type as string | string[], s.multiple)}
                scaleTo={0.985}
                style={[styles.row, i > 0 && styles.divider]}
                accessibilityLabel={`${s.label}. ${filled ? `${n} selected` : s.hint}`}
              >
                <View style={[styles.check, filled && styles.checkOn]}>
                  {filled && <Text style={styles.tick}>✓</Text>}
                </View>
                <Text style={styles.rowTitle}>{s.label}</Text>
                <Text style={styles.caption}>
                  {filled ? `${n} file${n > 1 ? "s" : ""} selected` : s.hint}
                </Text>
              </Press>
            );
          })}
        </View>

        <View style={styles.cta}>
          <Press
            onPress={() => {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
              router.push("/analysing");
            }}
            disabled={!ready}
            accessibilityLabel="Analyse the reference"
          >
            <Glass
              variant="regular"
              rounded={radius.pill}
              interactive={ready}
              style={[styles.button, ready && styles.buttonReady]}
            >
              <Text style={[styles.buttonLabel, ready && styles.buttonLabelReady]}>
                Analyse the reference
              </Text>
            </Glass>
          </Press>
          {!ready && <Text style={styles.hintUnder}>Add all three to continue</Text>}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.bg },

  display: { ...type.display, color: color.ink, textAlign: "center" },
  intro: {
    ...type.caption,
    color: color.ink2,
    textAlign: "center",
    marginTop: space(4),
    maxWidth: 340,
    alignSelf: "center",
  },

  list: { marginTop: space(11) },
  row: { alignItems: "center", paddingVertical: space(5), gap: space(2) },
  divider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: color.line },

  // The mark sits above the title, not beside it: inline, every row's circle
  // would land at a different x as the titles differ in width.
  check: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: color.line2,
    alignItems: "center",
    justifyContent: "center",
  },
  checkOn: { backgroundColor: color.ink, borderColor: color.ink },
  tick: { color: color.bg, fontSize: 13, fontWeight: "700", lineHeight: 16 },

  rowTitle: { ...type.body, color: color.ink, fontWeight: "600" },
  caption: { ...type.caption, color: color.ink2, textAlign: "center" },

  cta: { marginTop: space(9), alignItems: "center", gap: space(3) },
  button: { paddingHorizontal: space(7), paddingVertical: space(3.5) },
  buttonReady: { backgroundColor: color.ink },
  buttonLabel: { ...type.body, color: color.ink3, fontWeight: "600" },
  buttonLabelReady: { color: color.bg },
  hintUnder: { ...type.caption, color: color.ink2 },
});
