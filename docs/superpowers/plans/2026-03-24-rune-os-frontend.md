# Rune OS Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete rewrite of the Rune frontend as a landscape-first, SVG-based car OS with White Minimal HUD aesthetic, real-time 10Hz OBD data, and five signature animations.

**Architecture:** Pure SVG + CSS animations on OLED black. No Three.js/WebGL. Three screens (Rune, Telemetry, Settings) with bottom tab bar navigation. zustand stores with imperative DOM updates for 10Hz data. React only re-renders for structural changes (screen switch, panel open/close).

**Tech Stack:** React 19, TypeScript strict, Vite 8, zustand 5, SVG, CSS animations. No Three.js.

**Spec:** `docs/superpowers/specs/2026-03-24-rune-os-frontend-design.md`

**Backend:** Complete (271 tests). WebSocket at `/ws/vehicle-data` streaming 14 sensors + health + fuel at 10Hz.

**Working directory:** `/Users/kmantri/workstation/Car-Accord/Project-IrisE/repo-staging/frontend/`

---

## File Structure

```
frontend/
  package.json                          # MODIFY: remove Three.js deps
  vite.config.ts                        # KEEP as-is
  tsconfig.json                         # KEEP as-is
  index.html                            # MODIFY: landscape meta, add Cormorant Garamond font
  public/
    manifest.json                       # CREATE: PWA manifest, landscape orientation
    models/                             # KEEP: GLB still available for future 3D mode
  src/
    main.tsx                            # KEEP as-is
    App.tsx                             # REWRITE: new screen architecture
    vite-env.d.ts                       # KEEP
    styles/
      global.css                        # REWRITE: White Minimal HUD theme, landscape
    types/
      vehicle.ts                        # KEEP as-is (already correct)
      zones.ts                          # MODIFY: remove Three.js dependency
    constants/
      zones.ts                          # MODIFY: add zone positions for SVG
      thresholds.ts                     # CREATE: sensor warning/critical thresholds
      voice.ts                          # CREATE: Rune voice message templates
    stores/
      vehicleStore.ts                   # KEEP as-is
      uiStore.ts                        # MODIFY: add activeScreen, navVisible, settings state
      settingsStore.ts                  # CREATE: persisted settings (gas price, toggles)
    hooks/
      useVehicleSocket.ts               # KEEP as-is
      useWakeLock.ts                    # KEEP as-is
      useRuneVoice.ts                   # CREATE: generates Rune messages from health changes
      useBurnInProtection.ts            # CREATE: pixel shift, nav auto-hide, brightness
      useHeartbeat.ts                   # CREATE: trip heartbeat waveform from throttle/speed deltas
    components/
      os/
        ScreenContainer.tsx             # REWRITE: tab bar nav, screen crossfade, auto-hide nav
        NavBar.tsx                      # CREATE: bottom tab bar component
      screens/
        RuneScreen.tsx                  # CREATE: Full Hero main screen (replaces VisualizationScreen)
        TelemetryScreen.tsx             # CREATE: replaces DashboardScreen
        SettingsScreen.tsx              # REWRITE: card-state toggles, two-column layout
      car/
        AccordTopDown.tsx               # CREATE: top-down SVG of Honda Accord SE
        AccordSideProfile.tsx           # CREATE: side-profile SVG of Honda Accord SE
        CarView.tsx                     # CREATE: wrapper with view toggle + breathing + fuel flow
        ZoneOverlays.tsx                # CREATE: zone highlight overlays with ripple on tap
        FuelParticles.tsx               # CREATE: animated fuel flow particles (CSS)
      hud/
        HealthBadge.tsx                 # CREATE: health score + label (imperative updates)
        MpgDisplay.tsx                  # CREATE: instant MPG display (imperative updates)
        SensorStrip.tsx                 # CREATE: right-edge vertical sensor strip
        ConnectionPulse.tsx             # CREATE: animated dots in top bar
        VoiceText.tsx                   # CREATE: Rune's voice message
        TripHeartbeat.tsx               # CREATE: ECG-like waveform at bottom
      telemetry/
        HealthRing.tsx                  # CREATE: SVG ring gauge for overall health
        SubsystemList.tsx               # CREATE: per-subsystem scores with bars
        SensorGrid.tsx                  # CREATE: 4x3 live sensor grid with color accents
        SparklineStrip.tsx              # CREATE: trend sparklines
      settings/
        PreferenceCard.tsx              # CREATE: card-state toggle (ON/OFF)
        ConnectionInfo.tsx              # CREATE: connection status block
        AboutBlock.tsx                  # CREATE: vehicle + credit info
      boot/
        BootScreen.tsx                  # CREATE: "Rune" breathing + maker's mark
        LineReveal.tsx                  # CREATE: car wireframe draws itself in

  DELETE these files (Three.js era):
    - src/components/three/CameraRig.tsx
    - src/components/three/RuneCar.tsx
    - src/components/three/RuneScene.tsx
    - src/components/ui/ThemeToggle.tsx
    - src/components/screens/VisualizationScreen.tsx
    - src/components/screens/DashboardScreen.tsx
    - src/constants/themes.ts
    - src/stores/themeStore.ts
    - src/types/theme.ts
```

---

## Task 1: Clean Slate -- Remove Three.js, Update Dependencies

**Files:**
- Modify: `package.json`
- Modify: `index.html`
- Rewrite: `src/styles/global.css`
- Rewrite: `src/App.tsx`
- Delete: `src/components/three/*`, `src/components/ui/ThemeToggle.tsx`, `src/components/screens/VisualizationScreen.tsx`, `src/components/screens/DashboardScreen.tsx`, `src/constants/themes.ts`, `src/stores/themeStore.ts`, `src/types/theme.ts`

- [ ] **Step 1:** Remove Three.js packages from `package.json` dependencies: `@react-three/fiber`, `@react-three/drei`, `@react-three/postprocessing`, `three`. Remove `@types/three` from devDependencies. Run `npm install`.

- [ ] **Step 2:** Delete all Three.js-era files listed above.

- [ ] **Step 3:** Update `index.html` -- add Cormorant Garamond to Google Fonts link, add `<meta name="screen-orientation" content="landscape">`.

- [ ] **Step 4:** Rewrite `src/styles/global.css` -- White Minimal HUD theme. OLED black background, landscape orientation lock, grid background as CSS, safe-area padding, typography vars for Space Grotesk / Inter / Cormorant Garamond. Landscape-only media query with portrait fallback message.

- [ ] **Step 5:** Rewrite `src/App.tsx` as minimal shell that just renders a "Rune OS" placeholder text on black. Verify it compiles: `npx tsc --noEmit`.

- [ ] **Step 6:** Run `npm run dev` and verify: black screen with white text in landscape browser window.

- [ ] **Step 7:** Commit: `feat: clean slate -- remove Three.js, set up White Minimal HUD base`

---

## Task 2: Stores and Hooks Update

**Files:**
- Modify: `src/stores/uiStore.ts`
- Create: `src/stores/settingsStore.ts`
- Create: `src/constants/thresholds.ts`
- Create: `src/constants/voice.ts`
- Modify: `src/types/zones.ts`
- Modify: `src/constants/zones.ts`

- [ ] **Step 1:** Update `src/types/zones.ts` -- remove Three.js import, keep `SubsystemId` from `vehicle.ts`.

- [ ] **Step 2:** Update `src/constants/zones.ts` -- add SVG zone position data (x, y, width, height percentages for each zone in both top-down and side-profile views). Add sensor-to-subsystem mapping. Research Honda Accord component positions before filling in values.

- [ ] **Step 3:** Create `src/constants/thresholds.ts` -- warning and critical thresholds for each sensor (coolant > 100C = warn, > 110C = critical, etc.). Values from PRD Honda domain knowledge.

- [ ] **Step 4:** Create `src/constants/voice.ts` -- Rune voice message templates. First person, direct, brief. Templates for: all-good, calibrating, single-subsystem-warning, single-subsystem-critical, recovering, disconnected.

- [ ] **Step 5:** Update `src/stores/uiStore.ts` -- add `activeScreen: 'rune' | 'telemetry' | 'settings'`, `navVisible: boolean`, `bootComplete: boolean`. Keep `focusedSubsystem` and `revealComplete`.

- [ ] **Step 6:** Create `src/stores/settingsStore.ts` -- persisted to localStorage. Fields: `gridBackground: boolean`, `runeVoice: boolean`, `hapticFeedback: boolean`, `parallaxTilt: boolean`, `gasPricePerGallon: number`, `units: 'imperial' | 'metric'`. All with defaults.

- [ ] **Step 7:** Verify: `npx tsc --noEmit` passes.

- [ ] **Step 8:** Commit: `feat: update stores and constants for Rune OS`

---

## Task 3: OS Shell -- Screen Container + Nav Bar

**Files:**
- Rewrite: `src/components/os/ScreenContainer.tsx`
- Create: `src/components/os/NavBar.tsx`
- Rewrite: `src/App.tsx`

- [ ] **Step 1:** Create `src/components/os/NavBar.tsx` -- bottom tab bar. Three tabs with icons (car, gauge, settings as inline SVG). Active tab has top accent line. Auto-hides after 10s of no touch (reads from `uiStore.navVisible`). Show on tap anywhere in the nav zone. 34px height + safe area.

- [ ] **Step 2:** Rewrite `src/components/os/ScreenContainer.tsx` -- renders active screen based on `uiStore.activeScreen`. Opacity crossfade transition (350ms). Manages NavBar visibility.

- [ ] **Step 3:** Rewrite `src/App.tsx` -- renders ScreenContainer with three placeholder screens (just colored text for now: "Rune Screen", "Telemetry Screen", "Settings Screen"). Initializes `useVehicleSocket()` and `useWakeLock()`.

- [ ] **Step 4:** Verify: `npm run dev` -- three tabs visible, clicking switches screens with crossfade, nav auto-hides after 10s, tap brings it back.

- [ ] **Step 5:** Commit: `feat: OS shell with tab navigation and auto-hiding nav bar`

---

## Task 4: Honda Accord SVG -- Research + Draw

**Files:**
- Create: `src/components/car/AccordTopDown.tsx`
- Create: `src/components/car/AccordSideProfile.tsx`

**IMPORTANT:** Before drawing, research the 2026 Honda Accord SE (11th gen) shape:
- Web search for reference images of the exterior (top-down and side profile)
- Web search for engine bay layout to confirm component positions (engine right, CVT left, battery front-left)
- Web search for fuel tank position (under rear seats)
- Web search for exhaust/catalyst routing

- [ ] **Step 1:** Research the 2026 Honda Accord SE exterior shape and component positions. Document findings in code comments.

- [ ] **Step 2:** Create `src/components/car/AccordTopDown.tsx` -- SVG top-down view. Accurate Accord proportions (longer hood than the generic sedan we had). Body outline, roof, windshields, rear window, headlights, taillights, wheels, mirrors. Zone overlay rectangles at correct positions. All strokes white at varying low opacities. Component accepts `zoneStates` prop for color overrides.

- [ ] **Step 3:** Create `src/components/car/AccordSideProfile.tsx` -- SVG side profile. Accurate Accord silhouette (fastback-ish C-pillar, distinctive DRL shape). A/B/C pillars, windows, doors, handles, headlights, taillights, grille, wheels with spoke detail. Zone overlay rectangles. Same `zoneStates` prop.

- [ ] **Step 4:** Verify: render both SVGs in a test page, compare against reference images for shape accuracy.

- [ ] **Step 5:** Commit: `feat: accurate Honda Accord SE SVG outlines (top-down + side)`

---

## Task 5: Car View Container -- Breathing, Fuel Flow, View Toggle

**Files:**
- Create: `src/components/car/CarView.tsx`
- Create: `src/components/car/FuelParticles.tsx`
- Create: `src/components/car/ZoneOverlays.tsx`

- [ ] **Step 1:** Create `src/components/car/FuelParticles.tsx` -- CSS-animated dots flowing from tank zone to engine zone. Speed driven by `vehicleStore.sensors.MAF.v` (fuel consumption rate). 3-4 particles staggered. Pure CSS `@keyframes` with `animation-duration` set imperatively from store subscription.

- [ ] **Step 2:** Create `src/components/car/ZoneOverlays.tsx` -- reads `vehicleStore.health` and `uiStore.focusedSubsystem`. Colors zone overlays: default = transparent, warning = amber border, critical = red border. On tap: sets `focusedSubsystem` in uiStore, triggers CSS ripple animation (sonar rings via `@keyframes`). Tap elsewhere dismisses.

- [ ] **Step 3:** Create `src/components/car/CarView.tsx` -- wrapper that renders either `AccordTopDown` or `AccordSideProfile` based on local state. Includes: view toggle floating icons, breathing animation (CSS `transform: scale()` with `animation-duration` from RPM), FuelParticles, ZoneOverlays. Size = 65% of screen width, vertically centered.

- [ ] **Step 4:** Verify: Car renders centered on black, breathes, fuel particles flow, tapping a zone triggers ripple + highlight. View toggle switches between top-down and side.

- [ ] **Step 5:** Commit: `feat: car view with breathing, fuel flow, zone tap ripple, view toggle`

---

## Task 6: HUD Elements -- Health, MPG, Sensors, Connection, Voice, Heartbeat

**Files:**
- Create: `src/components/hud/HealthBadge.tsx`
- Create: `src/components/hud/MpgDisplay.tsx`
- Create: `src/components/hud/SensorStrip.tsx`
- Create: `src/components/hud/ConnectionPulse.tsx`
- Create: `src/components/hud/VoiceText.tsx`
- Create: `src/components/hud/TripHeartbeat.tsx`
- Create: `src/hooks/useRuneVoice.ts`
- Create: `src/hooks/useHeartbeat.ts`

- [ ] **Step 1:** Create `src/components/hud/HealthBadge.tsx` -- top-left. Health score in 38px Space Grotesk bold + "Health" label. Imperative DOM update via `vehicleStore.subscribe()`. Color changes only on warning/critical.

- [ ] **Step 2:** Create `src/components/hud/MpgDisplay.tsx` -- top-right. MPG in 30px + "Instant MPG" label. Shows "idle" + GPH when speed = 0. Imperative updates.

- [ ] **Step 3:** Create `src/components/hud/SensorStrip.tsx` -- right edge. Vertical stack of 5 sensor cards (RPM, MPH, Coolant, Volts, Tank by default, or focused subsystem sensors when a zone is tapped). Frosted glass backing (`backdrop-filter: blur`). Imperative updates. Left-border color accent when sensor deviates.

- [ ] **Step 4:** Create `src/components/hud/ConnectionPulse.tsx` -- in top bar next to Rune label. 3 dots traveling rightward on a 48px track. CSS animation. Stops/flatlines when `vehicleStore.connected === false`.

- [ ] **Step 5:** Create `src/hooks/useRuneVoice.ts` -- subscribes to `vehicleStore.health`. Debounced (only fires when score changes by >= 3 points). Returns current message string. Uses templates from `constants/voice.ts`.

- [ ] **Step 6:** Create `src/components/hud/VoiceText.tsx` -- below car center. Renders voice message with fade transition on change. Uses `useRuneVoice` hook.

- [ ] **Step 7:** Create `src/hooks/useHeartbeat.ts` -- subscribes to throttle position and speed. Computes a "driving intensity" value per tick. Maintains a rolling buffer of 100 values. Returns the buffer as SVG polyline points.

- [ ] **Step 8:** Create `src/components/hud/TripHeartbeat.tsx` -- full-width at bottom. Renders SVG polyline from `useHeartbeat` buffer. Stroke at ~7% white opacity. "Trip" label on the left.

- [ ] **Step 9:** Verify: all HUD elements render in correct positions, update with live data from backend simulator.

- [ ] **Step 10:** Commit: `feat: HUD elements -- health, MPG, sensors, connection, voice, heartbeat`

---

## Task 7: Main Screen Assembly (RuneScreen)

**Files:**
- Create: `src/components/screens/RuneScreen.tsx`
- Modify: `src/App.tsx`

- [ ] **Step 1:** Create `src/components/screens/RuneScreen.tsx` -- assembles all components: grid background, CarView (center), HealthBadge (top-left), ConnectionPulse (top-left after Rune label), MpgDisplay (top-right), SensorStrip (right edge), VoiceText (below car), TripHeartbeat (bottom strip). All positioned with `position: absolute` in their designated zones. No overlaps.

- [ ] **Step 2:** Wire into `src/App.tsx` as the "rune" screen in ScreenContainer.

- [ ] **Step 3:** Start the backend simulator. Verify: full main screen renders with live data. Car breathes with RPM. Fuel particles flow. Connection dots pulse. Numbers update. Voice message shows. Heartbeat draws.

- [ ] **Step 4:** Commit: `feat: complete Rune main screen with all animations`

---

## Task 8: Telemetry Screen

**Files:**
- Create: `src/components/telemetry/HealthRing.tsx`
- Create: `src/components/telemetry/SubsystemList.tsx`
- Create: `src/components/telemetry/SensorGrid.tsx`
- Create: `src/components/telemetry/SparklineStrip.tsx`
- Create: `src/components/screens/TelemetryScreen.tsx`

- [ ] **Step 1:** Create `HealthRing.tsx` -- 270-degree SVG arc gauge. Animated stroke-dashoffset. Score number centered. Color follows health state (white normal, amber/red on deviation).

- [ ] **Step 2:** Create `SubsystemList.tsx` -- 6 rows (Engine, CVT, Cooling, Fuel, Exhaust, Electrical). Each: name + score + mini progress bar. Left-border accent color only on deviating subsystems. Imperative updates.

- [ ] **Step 3:** Create `SensorGrid.tsx` -- 4x3 grid of all 12 sensor values. Left-border color accent only on sensors outside normal range (uses thresholds from `constants/thresholds.ts`). Imperative updates.

- [ ] **Step 4:** Create `SparklineStrip.tsx` -- 3 sparkline trend strips. Maintains rolling buffer (300 values = 30s at 10Hz). Renders as SVG polyline. Stroke color matches sensor state.

- [ ] **Step 5:** Create `TelemetryScreen.tsx` -- two-column layout. Left: HealthRing + SubsystemList. Right: SensorGrid + SparklineStrip.

- [ ] **Step 6:** Wire into App.tsx. Verify with backend: all values update live, sparklines draw, color accents appear on deviating sensors.

- [ ] **Step 7:** Commit: `feat: telemetry screen with health ring, sensor grid, sparklines`

---

## Task 9: Settings Screen

**Files:**
- Create: `src/components/settings/PreferenceCard.tsx`
- Create: `src/components/settings/ConnectionInfo.tsx`
- Create: `src/components/settings/AboutBlock.tsx`
- Rewrite: `src/components/screens/SettingsScreen.tsx`

- [ ] **Step 1:** Create `PreferenceCard.tsx` -- card-state toggle. ON: bright text + 3px white left border + "On" label. OFF: dim + strikethrough + "Off" label. Tap entire card to toggle. Reads/writes from `settingsStore`.

- [ ] **Step 2:** Create `ConnectionInfo.tsx` -- status (with dot), stream rate, latency (computed from message timestamps), Pi uptime (from `/api/debug`). Imperative updates for status.

- [ ] **Step 3:** Create `AboutBlock.tsx` -- vehicle info, version, credit line. "crafted by" in Cormorant Garamond italic + "Kuladeep Mantri" in Space Grotesk.

- [ ] **Step 4:** Rewrite `SettingsScreen.tsx` -- two-column layout. Left: PreferenceCards for grid/voice/haptic/parallax + gas price + units. Right: ConnectionInfo + AboutBlock.

- [ ] **Step 5:** Verify: toggles work, state persists in localStorage across refresh, connection info shows live data.

- [ ] **Step 6:** Commit: `feat: settings screen with card-state toggles and about section`

---

## Task 10: Boot Experience

**Files:**
- Create: `src/components/boot/BootScreen.tsx`
- Create: `src/components/boot/LineReveal.tsx`
- Modify: `src/App.tsx`

- [ ] **Step 1:** Create `BootScreen.tsx` -- "Rune" text breathing (opacity pulse), thin line below, "crafted by Kuladeep Mantri" at 12% opacity. Auto-advances after 2 seconds.

- [ ] **Step 2:** Create `LineReveal.tsx` -- car SVG draws itself in using CSS `stroke-dashoffset` animation. Zone labels appear sequentially. After 2 seconds, triggers data fade-in.

- [ ] **Step 3:** Modify `App.tsx` -- boot flow: BootScreen -> LineReveal -> normal RuneScreen. Track state in `uiStore.bootComplete`. On WebSocket reconnect after disconnect, play abbreviated reveal (1 second).

- [ ] **Step 4:** Verify: fresh load plays full boot sequence. Kill backend, restart -- abbreviated reveal plays.

- [ ] **Step 5:** Commit: `feat: boot screen with maker's mark and line-draw reveal`

---

## Task 11: Burn-In Protection + Polish

**Files:**
- Create: `src/hooks/useBurnInProtection.ts`
- Modify: various components for pixel shift support

- [ ] **Step 1:** Create `useBurnInProtection.ts` -- pixel shift (every 5 min, drift static elements 1-2px random direction), nav auto-hide (10s timer, reads/writes `uiStore.navVisible`), grid drift (CSS animation 1px/min), brightness reduction (30 min idle, not during warnings).

- [ ] **Step 2:** Add pixel shift CSS class to all static text elements (Rune label, Health/MPG labels, zone labels). The hook sets a CSS custom property (`--burn-shift-x`, `--burn-shift-y`) that these elements read via `transform: translate(var(--burn-shift-x), var(--burn-shift-y))`.

- [ ] **Step 3:** Add haptic feedback: `navigator.vibrate(50)` when health drops below warning threshold. Debounced 30s per subsystem. Reads `settingsStore.hapticFeedback`.

- [ ] **Step 4:** Verify: static elements shift after 5 min (test with shortened interval). Nav hides. Haptics fire on simulator anomaly.

- [ ] **Step 5:** Commit: `feat: OLED burn-in protection and haptic feedback`

---

## Task 12: PWA Manifest + Backend Static Serving

**Files:**
- Create: `public/manifest.json`
- Modify: `index.html` (manifest link)
- Modify: `backend/main.py` (add static mount for dist/)

- [ ] **Step 1:** Create `public/manifest.json` -- name "Rune", short_name "Rune", display "standalone", orientation "landscape", background_color "#000000", theme_color "#000000". Icon placeholder (simple white "R" on black).

- [ ] **Step 2:** Add `<link rel="manifest" href="/manifest.json">` to `index.html`.

- [ ] **Step 3:** Add one line to `backend/main.py`: mount `frontend/dist` at `/` with `html=True` (below the existing `frontend/public` mount). Only active when the dist directory exists.

- [ ] **Step 4:** Build: `cd frontend && npm run build`. Verify: `npx serve dist` works, backend serves the built app at `localhost:8080`.

- [ ] **Step 5:** Commit: `feat: PWA manifest and production static serving`

---

## Task 13: Final Integration Test

- [ ] **Step 1:** Start backend with simulator: `RUNE_DB_PATH=/tmp/rune_test.db python -m uvicorn backend.main:app --port 8080`

- [ ] **Step 2:** Start frontend dev: `cd frontend && npm run dev`

- [ ] **Step 3:** Verify main screen: car renders, breathes with RPM, fuel particles flow, connection dots pulse, health score updates, MPG updates, voice shows "All good...", heartbeat draws, zone tap triggers ripple + sensor strip update, view toggle works.

- [ ] **Step 4:** Verify telemetry screen: health ring, all 12 sensors updating, sparklines drawing, color accents on deviating sensors.

- [ ] **Step 5:** Verify settings: toggles persist, connection info live, about section shows credit.

- [ ] **Step 6:** Verify boot: fresh load plays boot -> reveal -> main screen. Kill backend, restart, abbreviated reveal.

- [ ] **Step 7:** Verify burn-in: nav auto-hides, grid drifts.

- [ ] **Step 8:** Build and test production: `npm run build`, serve from backend, verify everything works.

- [ ] **Step 9:** TypeScript check: `npx tsc --noEmit` -- zero errors.

- [ ] **Step 10:** Commit: `feat: Rune OS v0.1.0 -- complete frontend`
