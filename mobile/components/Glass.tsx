import { BlurView } from "expo-blur";
import {
  GlassView,
  isGlassEffectAPIAvailable,
  isLiquidGlassAvailable,
} from "expo-glass-effect";
import type { ReactNode } from "react";
import {
  Platform,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { color, radius } from "../lib/theme";

/**
 * One glass surface, two real tiers.
 *
 * `expo-glass-effect` renders true UIVisualEffectView liquid glass, but only on
 * iOS 26+. Everywhere else it falls back to a plain `View` — which would leave
 * the app looking flat rather than deliberately different. So the fallback is
 * designed here, once, and every screen just asks for `<Glass>`:
 *
 *   iOS 26+                real liquid glass, interactive on controls
 *   older iOS / Android    a real blur, tinted, with a lit top edge
 *
 * Android needs `blurMethod` explicitly: it defaults to `'none'`, which renders
 * a flat semi-transparent view and no blur at all. `dimezisBlurViewSdk31Plus`
 * uses the efficient RenderNode API on Android 12+ and degrades to that
 * semi-transparent view on older devices — which is why the tint underneath is
 * chosen to look intentional on its own rather than to rely on the blur.
 *
 * Two platform constraints, both from the API rather than taste:
 *
 * 1. Setting `opacity: 0` on a GlassView *or any parent* stops the effect
 *    rendering at all. Never fade this component — mount and unmount it, or
 *    animate a child.
 * 2. Never animate blur intensity. On Android it re-renders the blur every
 *    frame. Cross-fade a static layer instead.
 */

/** Resolved once: this cannot change while the app is running. */
export const GLASS_TIER: "liquid" | "blur" =
  Platform.OS === "ios" && isLiquidGlassAvailable() && isGlassEffectAPIAvailable()
    ? "liquid"
    : "blur";

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

  const clear = variant === "clear";

  return (
    <View style={[shape, style]}>
      <BlurView
        intensity={clear ? 28 : 48}
        tint="dark"
        // Android renders no blur at all without this.
        blurMethod="dimezisBlurViewSdk31Plus"
        style={StyleSheet.absoluteFill}
      />
      {/* The tint has to carry the surface on its own wherever the blur
          degrades, so it is a real colour rather than a wash over the blur. */}
      <View
        style={[
          StyleSheet.absoluteFill,
          { backgroundColor: tint ?? (clear ? "rgba(12,12,14,0.42)" : "rgba(22,22,24,0.55)") },
        ]}
      />
      {/* A bright top edge is what makes a material look lit rather than like
          a grey rectangle. Real glass gets this for free. */}
      <View
        style={[StyleSheet.absoluteFill, styles.edge, { borderRadius: rounded }]}
      />
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  edge: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.line,
    borderTopColor: "rgba(255,255,255,0.22)",
  },
});
