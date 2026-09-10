import type { ReactNode } from "react";
import { Pressable, type StyleProp, type ViewStyle } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import { duration, ease } from "../lib/theme";

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

/**
 * Press feedback, and nothing else.
 *
 * There is no hover on a phone, so every affordance the web puts in hover has
 * to live in the press. Feedback fires on press-*in* and commits on press-out —
 * waiting for the tap to complete before showing anything is the latency people
 * actually perceive.
 *
 * `scale` takes the label and icons with it, which is what makes it read as a
 * physical object rather than a colour change. It runs on the UI thread, so it
 * stays smooth while JS is busy.
 *
 * A large surface compresses less: a full-width card at 0.97 reads rubbery.
 */
export default function Press({
  children,
  onPress,
  style,
  scaleTo = 0.97,
  disabled,
  hitSlop = 8,
  accessibilityLabel,
  accessibilityRole = "button",
}: {
  children: ReactNode;
  onPress?: () => void;
  style?: StyleProp<ViewStyle>;
  scaleTo?: number;
  disabled?: boolean;
  hitSlop?: number;
  accessibilityLabel?: string;
  accessibilityRole?: "button" | "link" | "none";
}) {
  const pressed = useSharedValue(0);

  const animated = useAnimatedStyle(() => ({
    transform: [
      { scale: 1 - pressed.get() * (1 - scaleTo) },
    ],
  }));

  return (
    <AnimatedPressable
      onPressIn={() => {
        pressed.set(withTiming(1, { duration: duration.press, easing: ease.out }));
      }}
      onPressOut={() => {
        pressed.set(withTiming(0, { duration: duration.press, easing: ease.out }));
      }}
      onPress={onPress}
      disabled={disabled}
      hitSlop={hitSlop}
      // A finger drifting a few pixels shouldn't cancel a press the user meant.
      pressRetentionOffset={16}
      accessibilityRole={accessibilityRole}
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled: !!disabled }}
      style={[style, animated]}
    >
      {children}
    </AnimatedPressable>
  );
}
