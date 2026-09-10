import { BlurView } from "expo-blur";
import {
  GlassView,
  isGlassEffectAPIAvailable,
  isLiquidGlassAvailable,
} from "expo-glass-effect";
import type { ReactNode } from "react";
import { Platform, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { color, radius } from "../lib/theme";

/**
 * One glass surface, three tiers.
 *
 * `expo-glass-effect` renders real UIVisualEffectView liquid glass, but only on
 * iOS 26+. Everywhere else it silently falls back to a plain `View` — which
 * would leave the app looking flat and unfinished rather than deliberately
 * different. So the fallback is designed here, once, and every screen just asks
 * for `<Glass>`:
 *
 *   iOS 26+     real liquid glass, interactive on controls
 *   older iOS   a blur, tinted, with a bright top edge to catch light
 *   Android     a solid lifted surface — blur is expensive and inconsistent
 *               there, and a bad blur reads worse than an honest surface
 *
 * Two hard constraints, both from the platform rather than taste:
 *
 * 1. Setting `opacity: 0` on a GlassView *or any parent* stops the effect
 *    rendering at all. Never fade this component. If something must appear or
 *    disappear, mount and unmount it, or animate a child.
 * 2. Never animate blur intensity — on Android it re-renders the blur every
 *    frame. Cross-fade a static layer instead.
 */

/** Resolved once: these cannot change while the app is running. */
export const GLASS_TIER: "liquid" | "blur" | "solid" =
  Platform.OS === "ios"
    ? isLiquidGlassAvailable() && isGlassEffectAPIAvailable()
      ? "liquid"
      : "blur"
    : "solid";

export const hasLiquidGlass = GLASS_TIER === "liquid";

interface Props {
  children?: ReactNode;
  style?: StyleProp<ViewStyle>;
  /** `clear` for chrome over footage, `regular` for a surface carrying text. */
  variant?: "clear" | "regular";
  /** Adds the platform's own press response. Controls only, never containers. */
  interactive?: boolean;
  tint?: string;
  rounded?: number;
}

export default function Glass({
  children,
  style,
  variant = "regular",
  interactive = false,
  tint,
  rounded = radius.lg,
}: Props) {
  const shape: ViewStyle = { borderRadius: rounded, overflow: "hidden" };

  if (GLASS_TIER === "liquid") {
    return (
      <GlassView
        style={[shape, style]}
        glassEffectStyle={variant}
        isInteractive={interactive}
        tintColor={tint}
      >
        {children}
      </GlassView>
    );
  }

  if (GLASS_TIER === "blur") {
    return (
      <View style={[shape, style]}>
        <BlurView
          intensity={variant === "clear" ? 24 : 44}
          tint="dark"
          style={StyleSheet.absoluteFill}
        />
        {/* A bright top edge is what makes a material look lit rather than
            like a grey rectangle. Real glass gets this for free. */}
        <View style={[StyleSheet.absoluteFill, styles.edge, { borderRadius: rounded }]} />
        {children}
      </View>
    );
  }

  return (
    <View
      style={[
        shape,
        styles.solid,
        variant === "clear" && styles.solidClear,
        style,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  edge: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,255,255,0.14)",
    borderTopColor: "rgba(255,255,255,0.24)",
  },
  solid: {
    backgroundColor: color.raise,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.line,
  },
  solidClear: {
    // Over footage, an opaque panel would hide the thing being described.
    backgroundColor: "rgba(22,22,24,0.82)",
  },
});
