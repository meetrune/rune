# Rune OS Frontend Design Spec

**Date:** March 24, 2026
**Status:** Approved via brainstorming session
**Author:** Kuladeep Mantri + Claude

---

## 1. Overview

Rune OS is the frontend for the Rune car diagnostic system. It runs as a landscape PWA on a dedicated Pixel 6 Pro (6.7" LTPO OLED, 3120x1440) mounted on the driver's vent. It is not a web app on a phone -- it is a car operating system.

The backend (complete, 271 tests) streams 14 OBD-II sensor values at 10Hz via WebSocket from a Raspberry Pi 4B connected to a 2026 Honda Accord SE via WiCAN Pro.

---

## 2. Visual Identity

**Aesthetic:** White Minimal HUD. Pure white (#ffffff at varying opacities) on OLED black (#000000). Zero accent color in normal state. Subtle grid background (1px lines at ~1.2% white opacity, 36px spacing).

**Color philosophy:** Monochrome is the default. Color is the exception. Amber appears ONLY when a sensor approaches its warning threshold. Red appears ONLY when a sensor is critical. Because the screen is otherwise monochrome, any color instantly demands attention.

**Color values:**
- Normal: `rgba(255, 255, 255, 0.55)` (data values), `rgba(255, 255, 255, 0.12)` (labels)
- Warning (amber): `rgba(251, 191, 36, 0.7)` -- only on the specific sensor/zone deviating
- Critical (red): `rgba(239, 68, 68, 0.8)` -- only on the specific sensor/zone in critical state
- Healthy indicators (rare, subtle): `rgba(74, 222, 128, 0.5)` -- only for subsystem scores in Telemetry screen

**Typography:**
- Numbers/data: Space Grotesk (weights 400-700)
- UI text/labels: Inter (weights 200-600)
- Boot credit: Cormorant Garamond (300 italic)

---

## 3. Screen Architecture

Three screens, navigated via bottom tab bar:

### 3.1 Main Screen: "Rune" (Full Hero Layout)

The car SVG fills the entire screen. Data overlays at the edges.

**Layout:**
- **Top-left:** Health score (38px, bold) + "Health" label + Rune tag with connection pulse dots
- **Top-right:** Instant MPG (30px) + "Instant MPG" label
- **Center:** Car SVG (65% width), breathing animation, fuel particle flow, zone labels
- **Right edge:** Vertical sensor strip (5 key values: RPM, MPH, Coolant, Volts, Tank) with frosted glass backing
- **Below car center:** Voice text ("Running clean. Nothing to report.")
- **Bottom:** Full-width trip heartbeat waveform
- **Bottom bar:** Nav tabs (Rune / Telemetry / Settings)

**Car SVG views:**
- Top-down view (bird's eye) -- default
- Side profile view (classic sedan)
- Toggle between views with floating icon buttons (below car, left of center)
- Car shape must be researched to match the 2026 Honda Accord SE specifically

**Zone positions (must be accurate to real Honda Accord component locations):**
- Engine (L15BE 1.5T): front-right of engine bay
- CVT transmission: front-left, bolted to engine
- Fuel tank: rear center, under rear seats/trunk
- Cooling (radiator): front center, coolant lines to engine
- Exhaust (catalyst): underside, runs from engine to rear-right
- Electrical (battery): front-left engine bay

**Animations (all real-time, all data-backed):**

| Animation | Data Source | Behavior |
|-----------|-----------|----------|
| Breathing | RPM (PID 010C) | Car outline scales +-0.6% in sync with RPM. ~1.2s at idle, faster under load. |
| Fuel flow | MAF (PID 0110) via fuel rate calc | Particles flow from tank zone to engine zone. Speed = fuel consumption rate. |
| Connection pulse | WebSocket heartbeat | Dots travel from "Rune" label rightward. Visible data link. Flatlines on disconnect. |
| Trip heartbeat | Throttle delta (PID 0111) + speed delta (PID 010D) | ECG-like waveform. Smooth = steady driving. Spikes = hard accel/brake. |
| Zone ripple | User tap | Sonar rings radiate from tapped zone. Only on interaction, not default. |

### 3.2 Telemetry Screen

Deep data view. Two-column layout.

**Left column (38% width):**
- Health ring gauge (overall score, 270-degree arc)
- Subsystem list: Engine, CVT, Cooling, Fuel, Exhaust, Electrical
- Each row: name + score number + mini progress bar
- Left border accent color when deviating (amber/red only)

**Right column (62% width):**
- "Live Sensors" label
- 4x3 grid of all 12 sensor values
- Left-border color accent only on deviating sensors
- "Trends" label
- 3 sparkline strips (RPM, Coolant, Catalyst or whichever is most relevant)
- Sparkline stroke color matches sensor state

### 3.3 Settings Screen

Two-column layout.

**Left column -- Preferences:**
- Card-state toggles (no toggle switches -- ADHD-unfriendly)
- ON state: bright text + white left accent bar + "On" text
- OFF state: dimmed + strikethrough text + "Off" text
- Tap entire row to toggle
- Options: Grid Background, Rune's Voice, Haptic Feedback, Parallax Tilt
- Gas price input, Units toggle (Imperial/Metric)

**Right column -- Info:**
- Connection block: Status (with dot), Stream rate, Latency, Pi Uptime
- About block: Vehicle, Engine, Adapter, Version
- Credit: "crafted by" (Cormorant Garamond italic) + "Kuladeep Mantri" (Space Grotesk)

---

## 4. Navigation

Bottom tab bar, 34px height:
- Three tabs: Rune, Telemetry, Settings
- Active tab: white text + 1.5px top accent line with subtle glow
- Inactive tabs: 12% white opacity
- Frosted glass background (rgba(0,0,0,0.85))
- Screen transitions: opacity crossfade, 350ms ease

---

## 5. Boot Experience

When the engine starts (Pi boots -> WiFi appears -> Pixel connects):

1. **Boot screen (2 seconds):** Pure black -> "Rune" text breathes (Space Grotesk, 36px, 300 weight). Below: thin line + "crafted by Kuladeep Mantri" in Cormorant Garamond italic at 12% opacity.
2. **Line-draw reveal (2 seconds):** Car wireframe draws itself in, edge by edge. Zones light up sequentially.
3. **Data fade-in:** Health score + MPG fade in. Voice text appears: "All good. {score} across the board."
4. **Normal mode:** All animations active.

On disconnect + reconnect: abbreviated reveal replays (car re-draws, 1 second).

---

## 6. Touch Interaction

- **Min touch target:** 56x56px (vent-mounted, reduced finger precision)
- **Zone tap:** Tap a zone on the car -> sonar ripple radiates from tap point -> right-edge sensor strip updates to show that subsystem's specific sensors -> tap elsewhere or wait 5s to dismiss
- **View toggle:** Floating icon buttons below the car (top-down / side view)
- **Nav tabs:** Tap to switch screens
- **Settings rows:** Tap entire row to toggle on/off
- **No swipe navigation** (conflicts with potential future 3D orbit controls)
- **No hover states** (touch-only device)
- All critical controls in bottom 60% of screen (thumb-reachable while mounted)

---

## 7. Responsive Considerations

This is a single-device build (Pixel 6 Pro landscape). No other screen sizes need to be supported. However:
- Development/testing happens on a desktop browser, so basic desktop compatibility is needed
- CSS `env(safe-area-inset-*)` for the punch-hole camera cutout
- `viewport-fit=cover`, `user-scalable=no`

---

## 8. Performance

- **FPS:** Uncapped. Target 120fps on Pixel 6 Pro LTPO (10-120Hz adaptive). Dynamic DPR scaling (2x -> 1x) as thermal safety valve.
- **Rendering:** Pure SVG + CSS animations. No Three.js/WebGL needed for the White Minimal HUD aesthetic. This dramatically reduces GPU load compared to the previous 3D approach.
- **10Hz data handling:** zustand store with imperative DOM updates (`subscribe()` + `ref.textContent`). No React re-renders for data updates.
- **PWA:** Wake Lock API keeps screen on. Workbox for caching. Installable via manifest.

---

## 9. Data Contract

WebSocket at `ws://{host}/ws/vehicle-data`, 10Hz JSON messages:

```typescript
interface VehicleMessage {
  t: number;                          // unix timestamp
  d: Record<string, { v: number; u: string }>;  // 14 sensor readings
  health: {
    overall: number;   // 0-100, -1 = calibrating
    engine: number;
    transmission: number;
    fuel: number;
    cooling: number;
    exhaust: number;
    electrical: number;
  };
  fuel: {
    instant_mpg: number | null;
    idle_gph: number | null;
    trip_fuel_gal: number;
    trip_cost_usd: number;
    trip_distance_mi: number;
    tank_pct: number;
  };
}
```

All animation data sources confirmed available via WiCAN Pro OBD-II PIDs at 10Hz.

---

## 10. OLED Burn-In Prevention

The Pixel 6 Pro has an OLED screen (already has some burn-in from previous use). Since Rune runs for hours during drives, burn-in prevention is mandatory.

**Already safe (dynamic elements):** All sensor numbers (10Hz updates), breathing animation, fuel particles, connection pulse, trip heartbeat.

**Static elements that need protection:**
| Element | Mitigation |
|---------|-----------|
| "Rune" label, "Health"/"MPG" labels, zone labels | Pixel shift: every 5 minutes, drift all static text 1-2px in a random direction. Imperceptible to the eye, prevents pixel lock. |
| Grid background | Slow drift: grid scrolls ~1px per minute. Barely visible, keeps those pixel rows cycling. |
| Nav bar | Auto-hide after 10 seconds of no touch. Show on tap. Hidden most of the time during driving. |
| Overall brightness | After 30 minutes of no touch + stable driving (no warnings), reduce brightness 15%. Touch or health alert restores full. |

**Implementation:** A `useBurnInProtection` hook that manages the pixel shift interval, nav auto-hide timer, and brightness adjustment. Runs in the background, costs zero performance.

---

## 11. Implementation Notes

- **Car SVG accuracy:** Before drawing the SVG, research the 2026 Honda Accord SE (11th gen) exterior shape and under-hood component layout. Use reference images to trace an accurate outline. Zone positions must match real component locations.
- **No Three.js needed:** The switch from 3D wireframe to 2D SVG eliminates the entire R3F/Three.js dependency for the main screen. This is a massive simplification. PostProcessing, Bloom, EdgesGeometry -- all gone. Pure SVG + CSS.
- **Keep Three.js as optional:** The Telemetry screen or a future "3D explore" mode could use Three.js, but the main Rune screen is SVG-only.
- **Landscape lock:** Use `"orientation": "landscape"` in PWA manifest + CSS `@media (orientation: portrait)` fallback message.
- **Kiosk setup:** Tasker + Android Screen Pinning for dedicated device mode. Future: Rune Launcher APK.

---

## 12. What Was Rejected

- Blueprint wireframe aesthetic (looked like debug view)
- 6 color themes (monochrome is the identity)
- Portrait orientation (landscape gives more useful space on vent mount)
- Swipe navigation (conflicts with touch interactions)
- Toggle switches in settings (ADHD-unfriendly ambiguity)
- Three.js/WebGL for main screen (SVG is lighter, crisper, sufficient)
- Holographic/metallic/neon aesthetics (looked cheap)
- Dense data grids on main screen (Full Hero layout won -- car is the star)
