# Build runbook — Android

Self-contained instructions for producing an installable Android build of this
app. Written to be handed to another agent or followed by hand.

Everything here runs from `D:\video editor\mobile`. That path matters: the repo
root is **not** the Expo project.

---

## Context an agent needs

- The Expo app lives in **`mobile/`**, not the repo root. The root has no
  `app.json`; it holds a separate Python pipeline and a Next.js web app.
- The only branch is **`feat/reel-editor-scaffold`**. **There is no `main`.**
- EAS project is already linked: `app.json` →
  `expo.extra.eas.projectId = 96c9a5ec-efbd-4357-9ae2-9df0a2fbeae9`.
  **Do not run `eas init` again** and do not run `create-expo-app`.
- `eas.json` already exists with three profiles: `development`, `preview`,
  `production`.
- The app depends on `react-native-liquid-glassmorphism`, a **native module**.
  It cannot run in Expo Go. A native build is mandatory, not a preference.

## Preconditions

| Check | Command | Expected |
|---|---|---|
| EAS CLI installed | `eas --version` | `eas-cli/16.x` or newer |
| Logged in | `eas whoami` | an account name, not `Not logged in` |
| Types clean | `npx tsc --noEmit` | no output |
| Correct directory | `ls app.json eas.json` | both present |

---

## State as of the last attempt

Three config problems have already been found and fixed (commit `9b5a01b`),
each of which only surfaced once the previous one was cleared:

| Was | Now |
|---|---|
| `slug: reel-editor` ≠ the linked EAS project `nova` | `slug: nova` (display `name` is still "Reel Editor") |
| no `android.package` | `com.hisham1404.reeleditor` |
| no `ios.bundleIdentifier` | `com.hisham1404.reeleditor` |

The build now gets as far as resolving the `preview` profile and setting
`versionCode` 1, then stops on one thing and one thing only:

```
✔ Using remote Android credentials (Expo server)
Generating a new Keystore is not supported in --non-interactive mode
```

**This cannot be automated away.** It is not a missing flag — EAS deliberately
refuses to mint a signing key without a human present, because the key is what
proves future updates come from the same author. Generating one locally with
`keytool` and uploading it is the documented alternative, but that needs a JDK,
and there is none on this machine.

So: Step 2 has to be run once with a terminal attached. Every build after it —
including `--non-interactive` ones and the GitHub dashboard flow — works
unattended, because EAS stores the keystore against the project.

## Step 1 — Log in (a human must do this)

```bash
cd "D:\video editor\mobile"
eas login
```

**An agent must not perform this step, and must not ask for, read, echo or store
the password.** Auth is written to `~/.expo/state.json`; once it exists, every
later command in this file is authenticated with no secret ever passing through
a prompt or a log.

Verify, and stop here if it fails:

```bash
eas whoami
```

Already done — this returns `hisham1404`.

## Step 2 — Build the APK

```bash
cd "D:\video editor\mobile"
eas build --platform android --profile preview
```

`preview` produces a **standalone APK** — install it and it runs on its own.
Use `development` instead only when the goal is live-reloading against Metro;
that build additionally requires `npx expo start --dev-client` and is not what
you want for a first look.

### Prompts, and how to answer

| Prompt | Answer | Why |
|---|---|---|
| *Generate a new Android Keystore?* | **Yes** | EAS creates and stores the signing key. This is the step the dashboard cannot do for you |
| *Which account / owner?* | the logged-in personal account | The project is already linked by id |
| Anything about iOS | not asked on `--platform android` | If it appears, the platform flag was omitted |

The build runs in Expo's cloud and takes roughly 10–20 minutes. It prints a
build URL; the same page shows the QR code and the APK download.

## Step 3 — Install and check

Open the build URL on the Android phone and install the APK, or:

```bash
eas build:list --platform android --limit 1
```

Then confirm, in the app:

1. **Projects screen** — three recent projects with poster frames.
2. **Start a new cut** — the three pickers open the system file picker.
3. **The cut screen** — a 9:16 poster with glass chips on it, a horizontal
   filmstrip, dashed amber blocks for gaps.
4. **Drag the tempo.** The BPM number should track the finger with no lag, tick
   a haptic at each whole BPM, and the shot's seconds should change while its
   beat count stays fixed. This is the interaction most worth judging.

### Reading the glass correctly

The effect degrades by Android version. Check the phone's version before
calling anything a bug:

| Android | What renders |
|---|---|
| 13+ (API 33+) | Full AGSL lens — blur, vibrancy, **edge refraction**, tint, specular |
| 12 (API 31–32) | Blur, tint, specular — **no refraction** |
| 11 and below | Translucent tint and rim only |

Flat-looking glass on Android 12 is the designed fallback, not a defect.

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `Not logged in` | Step 1 skipped or session expired | Re-run `eas login` |
| Build fails on credentials | No keystore stored | Answer **Yes** to the keystore prompt; or `eas credentials` |
| `app.json not found` | Ran from the repo root | `cd mobile` first |
| Metro can't find the module in Expo Go | Expo Go cannot load native modules | Use the built APK, not Expo Go |
| Reanimated / New Architecture error | `newArchEnabled` missing | It is already `true` in `app.json` — do not remove it |
| Gradle fails on `compileSdk` | AGSL needs a recent toolchain | `app.json` pins `compileSdkVersion: 35` — do not lower it |

## Do not

- Do not run `npx create-expo-app` — the app already exists.
- Do not run `eas init` — the project id is already linked.
- Do not set the build's git ref to `main`; that branch does not exist.
- Do not set base directory to `/`; it is `mobile`.
- Do not enable **EAS Submit** — that uploads to the Play Store.
- Do not swap `react-native-liquid-glassmorphism` for `expo-glass-effect`; the
  latter is `platforms: ["apple"]` and renders a plain `View` on Android.

---

## Alternative: build from the Expo dashboard

Only after Step 2 has run once and stored a keystore. In
**Start a build from GitHub**:

| Field | Value |
|---|---|
| Base directory | `mobile` |
| Platform | `Android` |
| Git ref | `feat/reel-editor-scaffold` |
| EAS Build profile | `preview` |
| Environment | Default |
| EAS Submit | unchecked |

The greyed text in that dialog is placeholder, not a selection — type the values
in rather than leaving the fields empty.

## Alternative: build locally

Faster to iterate, but needs Android Studio and the Android SDK installed:

```bash
cd "D:\video editor\mobile"
npx expo run:android
```
