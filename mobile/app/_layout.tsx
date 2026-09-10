import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useReducedMotion } from "react-native-reanimated";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { color } from "../lib/theme";

/**
 * Screen transitions are the platform's, not ours.
 *
 * A push happens dozens of times a session and iOS already animates it
 * correctly, with the interactive back-swipe attached. Rebuilding that in JS
 * costs frames and loses the gesture. The only thing worth overriding is the
 * chrome: this app is dark by design, so the header is transparent and the
 * content runs under it.
 */
export default function RootLayout() {
  const reduced = useReducedMotion();

  return (
    // Gestures do nothing, with no error, unless this wraps the app.
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: color.bg }}>
      <SafeAreaProvider>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: color.bg },
            // Reduced motion means gentler, not none: a cross-fade still shows
            // that the screen changed, without the travel.
            animation: reduced ? "fade" : "default",
          }}
        >
          <Stack.Screen name="index" />
          <Stack.Screen name="new" />
          <Stack.Screen
            name="analysing"
            // There is nothing to go back to mid-analysis, and swiping back
            // into a half-finished run is worse than not offering it.
            options={{ gestureEnabled: false }}
          />
          <Stack.Screen name="cut" />
        </Stack>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
