import type { ReactNode } from "react";
import { Platform, type StyleProp, type ViewStyle } from "react-native";
import {
  LiquidGlassContainer,
  LiquidGlassView,
} from "react-native-liquid-glassmorphism";
import { radius } from "../lib/theme";

/**
 * One glass surface, everywhere.
 *
 * The first version used `expo-glass-effect`, which is genuinely Liquid Glass —
 * but its module config is `platforms: ["apple"]` with an empty `android` block,
 * so on Android it renders a plain View and nothing else. That is an iOS-only
 * effect, and this app is being used on Android.
 *
 * `react-native-liquid-glassmorphism` is the one that isn't an iOS wrapper: it
 * uses Apple's native UIGlassEffect on iOS 26, and a real AGSL RuntimeShader on
 * Android — blur, then vibrancy, then edge refraction, then tint and specular —
 * with its own degradation tiers underneath:
 *
 *   Android 33+   the full lens, refraction included
 *   Android 31-32 blur plus tint and specular, no refraction
 *   Android < 31  translucent tint and rim only
 *   iOS 26+       native Liquid Glass
 *   iOS 15-25     blur fallback
 *
 * The cost is that it is a native module: it does **not** run in Expo Go. The
 * app needs a development build or `expo prebuild`.
 *
 * Values here are deliberately restrained. The library will happily render a
 * heavy lens with grain and gyro tilt; a video editor is not the place for it.
 * Refraction stays subtle, thickness near default, grain off.
 */

interface Props {
  children?: ReactNode;
  style?: StyleProp<ViewStyle>;
  /** `clear` for chrome laid over footage, `regular` for a surface with text. */
  variant?: "clear" | "regular";
  /** The platform's own press response. Controls only, never containers. */
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
  const clear = variant === "clear";

  return (
    <LiquidGlassView
      variant={variant}
      // Chrome over footage stays light so the frame reads through it; a
      // surface carrying text needs more separation to stay legible.
      intensity={clear ? 45 : 70}
      tintColor={tint ?? (clear ? "rgba(10,10,12,0.28)" : "rgba(22,22,24,0.42)")}
      borderRadius={rounded}
      interactive={interactive}
      // Android-only lens controls. Edge lensing is what makes it read as
      // glass rather than frosting, but past about 1.2 it starts to look like
      // a fisheye lens instead of a pane.
      refraction
      thickness={clear ? 0.9 : 1.1}
      edgeReflectionStrength={0.7}
      grain={0}
      // Gyro specular is a party trick on a screen you hold still to work on.
      tilt={false}
      style={style}
    >
      {children}
    </LiquidGlassView>
  );
}

/**
 * Wraps sibling glass controls so they merge as they approach, which is the
 * behaviour that makes the material read as liquid rather than as separate
 * frosted rectangles.
 */
export function GlassGroup({
  children,
  spacing = 10,
  style,
}: {
  children: ReactNode;
  spacing?: number;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <LiquidGlassContainer spacing={spacing} style={style}>
      {children}
    </LiquidGlassContainer>
  );
}

/** True where the effect is a real lens rather than a translucent fallback. */
export const hasRealGlass =
  Platform.OS === "ios" || (Platform.OS === "android" && Platform.Version >= 31);
