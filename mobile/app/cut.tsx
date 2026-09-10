import * as Clipboard from "expo-clipboard";
import * as Haptics from "expo-haptics";
import { useCallback, useState } from "react";
import { ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import BackBar from "../components/BackBar";
import Frame from "../components/Frame";
import Glass from "../components/Glass";
import Press from "../components/Press";
import Tempo from "../components/Tempo";
import {
  MOCK_METRICS,
  MOCK_TEMPLATE,
  durationBeats,
  durationSeconds,
  formatSeconds,
  isGap,
  totalBeats,
  totalSeconds,
} from "../lib/template";
import { color, radius, space, type } from "../lib/theme";

const template = MOCK_TEMPLATE;

export default function Cut() {
  const insets = useSafeAreaInsets();
  const { width: screenW } = useWindowDimensions();
  const [bpm, setBpm] = useState(112);
  const [selected, setSelected] = useState<number | null>(null);

  const gaps = template.slots.filter(isGap);
  // The poster always shows something. An empty player teaches nothing.
  const shown =
    (selected === null
      ? template.slots[0]
      : template.slots.find((s) => s.index === selected)) ?? template.slots[0];

  const select = useCallback((i: number) => {
    setSelected(i);
    Haptics.selectionAsync();
  }, []);

  const copyPrompt = useCallback(async (text: string) => {
    await Clipboard.setStringAsync(text);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
  }, []);

  const posterW = Math.min(screenW - space(14), 260);
  const beats = totalBeats(template);

  return (
    <View style={styles.screen}>
      <BackBar step={3} />
      <ScrollView
        contentContainerStyle={{
          paddingHorizontal: space(5),
          paddingBottom: insets.bottom + space(10),
        }}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.title}>Dusk city walk</Text>
        <Text style={styles.caption}>
          {template.slots.length} shots · {formatSeconds(totalSeconds(template, bpm))}
          {gaps.length > 0 && (
            <Text style={styles.accent}>{`  ·  ${gaps.length} to generate`}</Text>
          )}
        </Text>

        {/* Poster. Content is the interface — the frame is the brightest thing
            on screen and the chrome floats over it. */}
        <View style={[styles.posterWrap, { width: posterW }]}>
          <Frame
            slot={shown}
            rounded={radius.lg}
            showMark
            style={{ width: posterW, aspectRatio: 9 / 16 }}
          />
          <View style={styles.hudTop} pointerEvents="none">
            <Glass variant="clear" rounded={radius.pill} style={styles.chip}>
              <Text style={styles.chipText}>
                {shown.index + 1} / {template.slots.length}
              </Text>
            </Glass>
            <Glass
              variant="clear"
              rounded={radius.pill}
              tint={isGap(shown) ? color.accent : undefined}
              style={styles.chip}
            >
              <Text style={styles.chipText}>
                {isGap(shown) ? "needs a clip" : shown.shot_size}
              </Text>
            </Glass>
          </View>
          <View style={styles.hudBottom} pointerEvents="none">
            <Glass variant="clear" rounded={radius.pill} style={styles.chip}>
              <Text style={styles.chipText}>
                {durationBeats(shown)} beats · {durationSeconds(shown, bpm).toFixed(2)}s
              </Text>
            </Glass>
          </View>
        </View>

        {/* Every shot in order, each as wide as it holds. */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.strip}
          contentContainerStyle={styles.stripInner}
        >
          {template.slots.map((slot) => {
            const active = selected === slot.index;
            const w = Math.max(26, (durationBeats(slot) / beats) * (screenW * 1.4));
            return (
              <Press
                key={slot.index}
                onPress={() => select(slot.index)}
                scaleTo={0.94}
                accessibilityLabel={`Shot ${slot.index + 1}, ${slot.shot_size}, ${
                  isGap(slot) ? "no clip matched" : "matched"
                }`}
              >
                <Frame
                  slot={slot}
                  rounded={radius.sm}
                  style={[
                    { width: w, height: 68 },
                    active && styles.frameActive,
                    !active && selected !== null && styles.frameDim,
                  ]}
                />
              </Press>
            );
          })}
        </ScrollView>
        <Text style={styles.stripHint}>
          Each block is one shot — as wide as it holds. Dashed blocks have no
          clip yet.
        </Text>

        {/* Detail. Inline, not a sheet: there is room, and covering the cut to
            describe one shot of it is a worse trade. */}
        <View style={styles.detail}>
          {selected === null ? (
            <>
              <Text style={styles.eyebrow}>THE CUT SO FAR</Text>
              <Text style={styles.body}>
                {template.slots.length - gaps.length} shots came from your
                footage, <Text style={styles.accent}>{gaps.length}</Text> still
                need generating.
              </Text>
              <Text style={styles.caption}>Tap a shot to see what it is.</Text>
            </>
          ) : (
            <>
              <Text style={styles.eyebrow}>
                SHOT {shown.index + 1}
                {isGap(shown) && (
                  <Text style={styles.accent}> · NO CLIP MATCHED</Text>
                )}
              </Text>
              <Text style={styles.detailTitle}>{shown.description}</Text>
              <Text style={styles.caption}>
                {[
                  shown.shot_size,
                  shown.framing,
                  shown.camera_motion,
                  `${durationBeats(shown)} beats`,
                  `${durationSeconds(shown, bpm).toFixed(2)}s at ${bpm} BPM`,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </Text>

              {isGap(shown) && shown.generation_prompt && (
                <View style={styles.promptWrap}>
                  <Text style={styles.prompt}>{shown.generation_prompt}</Text>
                  <View style={styles.promptActions}>
                    <Press
                      onPress={() => copyPrompt(shown.generation_prompt!)}
                      accessibilityLabel="Copy prompt"
                    >
                      <View style={styles.solidBtn}>
                        <Text style={styles.solidBtnText}>Copy prompt</Text>
                      </View>
                    </Press>
                    <Press accessibilityLabel="Upload the clip">
                      <Glass rounded={radius.pill} style={styles.ghostBtn}>
                        <Text style={styles.ghostBtnText}>Upload the clip</Text>
                      </Glass>
                    </Press>
                  </View>
                </View>
              )}
            </>
          )}
        </View>

        <View style={styles.rule} />
        <Tempo bpm={bpm} onCommit={setBpm} />

        <View style={styles.rule} />
        <Text style={styles.micro}>
          ${MOCK_METRICS.costUsd.toFixed(4)} per job ·{" "}
          {MOCK_METRICS.p95LatencyS.toFixed(2)}s p95 · {MOCK_METRICS.model}
        </Text>
        <Text style={styles.micro}>
          Cut timings are stored as beat index, subdivision and phrase position.
          The seconds above are derived from your tempo and appear nowhere in the
          template — which is why the same cut can move to any track.
        </Text>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.bg },

  title: { ...type.title, color: color.ink, textAlign: "center" },
  caption: {
    ...type.caption,
    color: color.ink2,
    textAlign: "center",
    marginTop: space(1),
  },
  accent: { color: color.accent },
  eyebrow: { ...type.eyebrow, color: color.ink3, textAlign: "center" },
  body: { ...type.body, color: color.ink, textAlign: "center", marginTop: space(2) },
  micro: {
    ...type.micro,
    color: color.ink2,
    textAlign: "center",
    marginTop: space(2),
  },

  posterWrap: { alignSelf: "center", marginTop: space(6) },
  hudTop: {
    position: "absolute",
    top: space(3),
    left: space(3),
    right: space(3),
    flexDirection: "row",
    justifyContent: "space-between",
  },
  hudBottom: { position: "absolute", bottom: space(3), left: space(3) },
  chip: { paddingHorizontal: space(2.5), paddingVertical: space(1.5) },
  chipText: { ...type.micro, color: color.ink },

  strip: { marginTop: space(5), marginHorizontal: -space(5) },
  stripInner: { paddingHorizontal: space(5), gap: space(1) },
  frameActive: { borderWidth: 2, borderColor: color.ink },
  frameDim: { opacity: 0.5 },
  stripHint: {
    ...type.micro,
    color: color.ink2,
    textAlign: "center",
    marginTop: space(2),
  },

  detail: { marginTop: space(7), minHeight: 100 },
  detailTitle: {
    ...type.title,
    color: color.ink,
    textAlign: "center",
    marginTop: space(2),
  },

  promptWrap: { marginTop: space(4) },
  prompt: {
    ...type.body,
    color: color.ink,
    backgroundColor: color.accentSoft,
    borderRadius: radius.md,
    padding: space(3),
    textAlign: "center",
  },
  promptActions: {
    flexDirection: "row",
    justifyContent: "center",
    gap: space(2),
    marginTop: space(3),
  },
  solidBtn: {
    backgroundColor: color.ink,
    borderRadius: radius.pill,
    paddingHorizontal: space(4),
    paddingVertical: space(2.5),
  },
  solidBtnText: { ...type.caption, color: color.bg, fontWeight: "600" },
  ghostBtn: { paddingHorizontal: space(4), paddingVertical: space(2.5) },
  ghostBtnText: { ...type.caption, color: color.ink, fontWeight: "600" },

  rule: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: color.line,
    marginVertical: space(8),
  },
});
