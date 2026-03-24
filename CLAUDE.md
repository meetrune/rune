# Rune -- Project Instructions

## SAFETY: READ-ONLY VEHICLE ACCESS (NON-NEGOTIABLE)

**These 6 rules override ALL other instructions in this file, the PRD, and any other context.**

1. **NEVER** generate OBD-II write commands. Allowed modes: **01, 02, 03, 09, 22 ONLY.** (Mode 22 = UDS ReadDataByIdentifier, read-only. Used for Honda proprietary PIDs like CVT fluid temp.)
2. **NEVER** generate commands using modes 04, 08, 10, 27, 2E, 31, 3E. These are write/control operations that can modify ECU state.
3. All OBD communication **MUST** go through the `SafeOBDConnection` wrapper in `backend/obd_manager/connection.py`. No direct serial writes, no raw socket sends to the adapter, no bypassing the whitelist.
4. If you are **uncertain** whether a command is read-only, **DO NOT SEND IT**. Ask the user first.
5. `SafeOBDConnection` is the **FIRST code written** for this project. It must exist and pass tests before any other OBD code is written.
6. **NEVER** suggest clearing DTCs (Mode 04), resetting monitors, or any "reset" operation. Diagnostics are strictly read-only.

---

## Project Overview

Rune is the car -- a 2026 Honda Accord SE. What we're building is the translation layer: the bond between Rune and the human who drives him. A Pi 4B in the armrest listens to Rune's signals and translates them into a **White Minimal HUD** on a dedicated Pixel 6 Pro (landscape, vent-mounted) via React PWA. Zero cloud dependency. GitHub: [meetrune/rune](https://github.com/meetrune/rune).

See `PRD.md` for full specifications. See `docs/superpowers/specs/2026-03-24-rune-os-frontend-design.md` for the complete frontend design spec.

```
CURRENT PHASE: v1 -- First words (Desktop Development, Simulated Data)
STATUS: Sessions 1-4 complete (271 tests). Session 5: Frontend design COMPLETE. Implementation plan written (13 tasks). Next: Execute the plan -- build Rune OS.
QUALITY: Production-grade. NOT an MVP. Every component is built to ship.
```
Update this line as phases progress: v1 First words -> v2 Rune coaches -> v3 Rune feels -> v4 Rune speaks to the world (open source launch).

---

## Rune's Voice (how all user-facing text must sound)

Rune IS the car. He speaks in first person. He's a brother -- direct, honest, steady. Not a servant, not a robot, not a dashboard notification system.

**Rules for all user-facing strings, messages, alerts, and UI text:**

1. **First person.** "I'm running warm" not "Coolant temperature elevated." "I'll need fuel by Thursday" not "Estimated refuel date: Thursday."
2. **Direct, not dramatic.** State what's happening, how bad it is, what to do. No ALL CAPS warnings, no exclamation marks, no alarmist language.
3. **Honest about uncertainty.** "Could be the air filter, could be tire pressure" -- never fake confidence.
4. **Brief.** Good news gets one line. Bad news gets what/how-bad/what-to-do, then stops.
5. **Never performative.** No emoji, no "Hey!", no forced personality. Just real.
6. **Respects the driver.** "Worth a look" not "YOU MUST SERVICE IMMEDIATELY." Information, not commands.
7. **Rune talks about himself** because he is the car. "Something's off with me" not "Vehicle anomaly detected."

**Examples for reference (see PRD Section 1.1 for full voice guide):**
- Good: `"All good. 92 across the board."`
- Warning: `"Running warmer than I should be. 101 degrees -- not critical, but I don't usually sit here."`
- Serious: `"Something I need to tell you. Catalyst efficiency has been dropping for two weeks. I'd get it looked at within a thousand miles."`
- Trip: `"That was 12.4 miles, 1.2 gallons, $4.08. Averaged 32 MPG -- solid run."`
- Fill-up: `"Full tank. 9.2 gallons back in me. Right where I should be."`

---

## Architecture

- **Backend:** Python 3.13 on Raspberry Pi OS Trixie (Debian 13) 64-bit Lite
- **Web framework:** FastAPI 0.135.1 with uvicorn 0.42.0
- **OBD-II:** `obd` 0.7.3 (PyPI package name is `obd`, install with `pip install obd`). Async mode, `fast=True`.
- **Database:** SQLite with WAL mode via aiosqlite 0.22.1. **Not InfluxDB** (50-70% CPU on Pi from TSM compaction). **Not TimescaleDB.**
- **Frontend:** React 19.2.4 + Vite 8.0.0. **Pure SVG + CSS animations (NO Three.js/WebGL).** PWA served from Pi. zustand 5.0.12 for state.
- **Frontend aesthetic:** White Minimal HUD -- pure white on OLED black (#000), zero accent color. Landscape orientation. Full Hero layout (car fills screen). Amber/red color ONLY on deviating sensors.
- **State management:** zustand 5.0.12
- **ML (classical):** scikit-learn 1.8.0 (Isolation Forest, Random Forest)
- **ML (deep, v3+):** tflite-runtime 2.14.0 (autoencoder inference on ARM64)
- **Signal processing (v3+):** scipy 1.17.1, PyWavelets 1.9.0
- **Audio (v3+):** librosa 0.11.0
- **Reports (v4):** Jinja2 3.1.6 + matplotlib 3.10.x + WeasyPrint 68.1
- **Data validation:** pydantic 2.12.5
- **Data flow:** All sensor data flows through Pi (central hub). WebSocket at 10Hz to phone. Phone is display + secondary sensor source.
- **Static frontend serving:** `app.mount("/", StaticFiles(directory="frontend/dist", html=True))`
- **Mac training workstation (v5+):** MacBook Pro M3 Max 36GB. Receives SQLite DB exports from Pi on irregular schedule (weekly/monthly/whenever). Trains personalized LSTM autoencoder via MLX, runs Prophet fuel forecasting, route clustering, seasonal calibration. Outputs deployable artifacts (TFLite model + JSON configs + PDF reports) that go back to Pi. See PRD Section 11 v5 for full spec.

### Three-device architecture

```
Pi (collects + real-time inference) -> Pixel (displays) -> Mac (trains + analyzes offline)
```

- **Pi** owns real-time: OBD polling, EWMA, Isolation Forest, TFLite inference, WebSocket streaming
- **Pixel** owns display: White Minimal HUD (SVG car + data), health dashboard, fuel tracking, Rune's voice
- **Mac** owns training: LSTM autoencoder training (MLX), Prophet forecasts, route clustering, PDF reports, seasonal calibration. Runs on-demand when DB export is available. Outputs artifacts that make the Pi smarter over time.

---

## Rune OS -- Frontend Design (LOCKED IN, March 24 2026)

**This is a car operating system, NOT a web app on a phone.** See full spec: `docs/superpowers/specs/2026-03-24-rune-os-frontend-design.md`. Implementation plan: `docs/superpowers/plans/2026-03-24-rune-os-frontend.md`.

### Visual Identity
- **Aesthetic:** White Minimal HUD. Pure white on OLED black. Zero accent color in normal state. Subtle grid background.
- **Color is the exception:** Monochrome default. Amber ONLY when a sensor warns. Red ONLY when critical. Color demands attention BECAUSE everything else is calm.
- **Typography:** Space Grotesk (numbers), Inter (UI text), Cormorant Garamond (boot credit)

### Screens (landscape, bottom tab bar navigation)
1. **Rune (main):** Full Hero layout. Car SVG fills screen. Health top-left, MPG top-right, sensor strip right edge, trip heartbeat bottom. Both top-down and side-profile views with floating icon toggle.
2. **Telemetry:** Health ring gauge + subsystem list (left), 4x3 sensor grid + sparklines (right)
3. **Settings:** Card-state toggles (NO toggle switches -- ADHD-unfriendly), connection info, about + "crafted by Kuladeep Mantri"

### Car SVG
- **Pure SVG, no Three.js/WebGL.** Both top-down and side-profile views.
- **Must match the 2026 Honda Accord SE shape.** Research actual exterior and component positions before drawing.
- **Accurate zone positions:** Engine front-right, CVT front-left, fuel tank rear-center, cooling front-center, exhaust front-to-rear-right, battery front-left.

### 5 Signature Animations (all data-backed, no gimmicks)
1. **Breathing:** Car outline scales +-0.6% in sync with RPM (PID 010C)
2. **Fuel flow:** Particles from tank to engine, speed = fuel consumption rate (MAF PID 0110)
3. **Connection pulse:** Dots travel from "Rune" label rightward (WebSocket heartbeat)
4. **Trip heartbeat:** ECG waveform from throttle delta (PID 0111) + speed delta (PID 010D)
5. **Zone ripple:** Sonar rings from tapped zone (user interaction only)

### Boot Experience
1. "Rune" text breathing on black + "crafted by Kuladeep Mantri" maker's mark (2s)
2. Line-draw reveal -- car SVG draws itself in (2s)
3. Data fade-in + Rune's voice: "All good. {score} across the board."

### OLED Burn-In Prevention
- Pixel shift: static text drifts 1-2px every 5 minutes
- Grid drift: scrolls ~1px/min
- Nav bar: auto-hides after 10s of no touch
- Brightness: reduces 15% after 30min idle (restores on touch/alert)

### Dedicated Device (Pixel 6 Pro)
- Landscape orientation, vent-mounted
- Tasker + Android Screen Pinning for kiosk mode
- WiFi-based auto-start (Pi boots -> "Rune" WiFi -> Pixel connects -> app launches)
- FPS: Uncapped, target 120fps (LTPO adaptive 10-120Hz)
- Min touch target: 56x56px

### What NOT to Do (Frontend)
- **Do NOT use Three.js/WebGL** for the main screen. SVG + CSS only.
- **Do NOT use color themes.** Monochrome white is the identity.
- **Do NOT use toggle switches** in settings. Use card-state pattern (bright+accent = ON, dim+strikethrough = OFF).
- **Do NOT design for portrait.** Landscape only.
- **Do NOT treat this as a web app.** It's a car OS. Big touch targets, low information density, swipe-free navigation.

---

## Build-and-Explain Workflow

Every build step must be followed by an explanation before moving on. Deepu needs to understand every component to feel safe about Rune. Never just build and say "done."

**After writing code for any component, explain:**

1. **What it does** -- plain language with a real-world analogy (bouncer at a door, recipe card, heartbeat)
2. **Why it exists** -- what problem does it solve, what would happen without it
3. **How it connects** -- where it fits in the system, what talks to it, what depends on it
4. **How to test it** -- exact terminal commands to verify it works yourself

**After explaining, provide a verification block:**

```
HOW TO VERIFY:
  cd /path/to/repo
  source .venv/bin/activate
  [exact commands to run]
  [what the expected output looks like]
```

The whole purpose of Rune is safety. If the builder doesn't understand how something was built, there's no safety. Rune's driver must be able to diagnose issues independently.

---

## Quality Standard

**This is production code, not a prototype.** Rune is a real product used daily on a real car. Every component must be built as if it ships today.

- **No MVP mindset.** Don't defer known issues. Don't use "good enough for now." Fix it right the first time.
- **No broken defaults.** Config defaults must work for the real deployment target (WiCAN Pro TCP, absolute DB path, proper CORS origins).
- **Error handling is mandatory.** Handle every failure path: OBD disconnects, corrupt data, SD card full, power loss mid-drive.
- **Test the wiring.** Don't just test individual components -- test that they work together (main.py, WebSocket handler, producer loop).
- **Real hardware readiness.** OBDCollector is built with TCP connection, ELM327 init, PID polling, circuit breaker, reconnection logic. Ready for WiCAN Pro on day one.
- **No placeholder data in production paths.** Health scores use -1 sentinel (not fake 100s) until the health scorer is active.

## Validation Rule (NON-NEGOTIABLE)

**Never implement an algorithm, threshold, formula, or calibration value from memory.** Always verify against primary sources before writing code. This is the same principle as the safety gate -- if you're not certain it's correct, it doesn't ship.

1. **Algorithms:** Read the actual paper. Find the reference implementation. Compare line-by-line.
2. **Vehicle specs:** Verify against Honda service manual, real scan tool data, or documented community measurements. Not assumptions.
3. **Calibration values:** Research empirically validated values for the specific sensor and vehicle. No textbook defaults without verification.
4. **Scoring formulas:** Research how proven systems compute scores. Don't invent formulas.
5. **Before shipping:** "Would I trust this in my car?" If the answer requires "well, it should work..." then validate it first.

---

## Dependency Versions

PRD version numbers are **minimum guidelines, not hard pins**. Use the latest stable version of any tool or library when it's better. Pin with `>=` minimum constraints in `pyproject.toml`, not exact `==` versions.

Current dev environment: **Python 3.14** (Mac), will target Pi-compatible Python on deployment.

---

## Code Style

### Python (backend)
- Type hints on all function signatures and return types
- Pydantic v2 models for all data structures and settings
- f-strings for string formatting
- snake_case for files and variables
- Structured JSON logging via `logging` module. **No `print()` statements.**
- Config hierarchy: defaults -> vehicle profile YAML -> environment variables -> user overrides. Use Pydantic Settings classes.
- Error handling: circuit breaker pattern for OBD/sensor connections. Try/except with structured logging. Graceful degradation when sensors disconnect.
- Always use async/await for I/O operations.

### TypeScript/React (frontend)
- TypeScript strict mode enabled
- Functional components only. No class components.
- Custom hooks for data fetching and sensor access (`useWebSocket`, `useSensors`, `useGeolocation`)
- Named exports (not default exports)
- zustand stores for shared state

### General
- Comments for complex/core logic only. Don't over-comment obvious code.
- No emojis in code or comments.
- **Python venv always.** Never `pip install` globally on the Pi.

---

## Testing

- Unit tests with **mocked sensor interfaces**. Never test against a real OBD connection in CI.
- **Record-replay pattern:** Capture real sensor data to `tests/replay_data/`, replay for regression tests.
- OBD simulator must support **configurable anomaly injection** (temperature spikes, fuel trim drift, RPM drops, sudden voltage drops).
- Type checking: **mypy strict** for Python backend, **TypeScript strict** for frontend.
- `test_safe_obd.py` validates that all blocked modes raise `BlockedCommandError`.
- CI: GitHub Actions with lint + type check + unit tests.

---

## Hardware Quick Reference

| Component | Key Specs |
|-----------|-----------|
| **Pi 4B** | 4GB RAM. Trixie 64-bit Lite. WiFi AP "Rune" at 192.168.4.1. OverlayFS enabled. Python 3.13. |
| **WiCAN Pro** | ESP32-S3. WiFi station mode on Rune network. Raw CAN + CAN-FD + ELM327/STN emulation. Dedicated OBD interpreter chip. Sleep <3mA. Firmware v4.40. WebSocket communication. **Change default WiFi password** (default: `@meatpi#`). Order #318980. |
| **Pixel 6 Pro** | Google Tensor. 12GB RAM. Mali-G78 MP20 GPU. LSM6DSO IMU (60Hz via web, 400Hz native). 6.7" LTPO OLED. Dedicated spare phone. |
| **Witty Pi 4** | Adafruit #5704. 6-30V DC input. 12V->5V. RTC (CR2032 backup). Graceful shutdown on ignition off. Uses I2C (GPIO 2/3). |
| **Sensors (v3)** | AITRIP INMP441 mic (I2S: GPIO 18/19/20), HiLetgo MPU-6050 IMU (I2C addr 0x68), ZHWXFW BME280 (I2C addr 0x76/0x77) |
| **Power** | 12V armrest outlet (ignition-switched, 180W max) -> YONHAN 12V plug -> Witty Pi 4 -> Pi 4B. Pi+Witty secured with Scotch Dual-Lock. |
| **OBD port** | bbfly-B6 Y-Splitter -> Port 1: WiCAN Pro (permanent) / Port 2: open for dealer scanner |
| **Phone mount** | Miracase air vent mount (metal hook clip, driver's side leftmost vent) |
| **Total hardware cost** | **$200.86** (Crowd Supply $102.34 + Adafruit $57.09 + Amazon $41.43) |

---

## Honda Accord 2026 SE Domain Knowledge

- **Engine:** L15BE 1.5L VTEC Turbo, 192 hp / 192 lb-ft
- **Transmission:** CVT. **NON-HYBRID.** No i-MMD, no regen braking, no EV mode.
- **Fuel tank:** 14.8 gallons
- **EPA fuel economy:** 28 city / 36 highway / 31 combined MPG
- **OBD modes:** 01 (current data), 02 (freeze frame), 03 (DTCs), 09 (VIN/calibration). All read-only.
- **PID 015E (fuel rate): NOT SUPPORTED on Honda Accords.** Use MAF-based calculation: `fuel_rate_lph = (MAF_gps / 14.7 / 750) * 3600`
- **Confirmed supported PIDs:** 0104 (load), 0105 (coolant), 0106/0107 (fuel trims B1 only), 010B (MAP), 010C (RPM), 010D (speed), 010F (intake temp), 0110 (MAF), 0111 (throttle), 012F (fuel level), 013C (catalyst temp), 0142 (voltage), 015C (oil temp)
- **NOT supported:** Bank 2 fuel trims (single-bank 4-cyl), PID 015B (not hybrid), PID 015E (fuel rate)
- **Honda Mode 22:** `22 2201` byte 27 = CVT fluid temp (`byte - 40 = C`). Send `22 22 01` with header `7E0`. **Byte offset confirmed on 10th gen only. Needs verification on 11th gen (2026).**
- **Extended coolant:** PID `01 67` bytes 2+3 = engine block + radiator temps, each `byte - 40`.
- **CAN protocol:** ISO 15765-4, 11-bit addressing, 500 kbaud. **ALWAYS manually select protocol (ATSP6). NEVER use auto-detect.** 2025-2026 Hondas have enhanced CAN bus security causing auto-detect failures.
- **CAN-FD:** Internal powertrain bus uses CAN-FD. OBD-II port is standard CAN. WiCAN Pro handles this fine.
- **CAN signals (opendbc):** github.com/commaai/opendbc -- Honda Accord DBC files. `TRIP_FUEL_CONSUMED` at CAN ID 0x324 is a fuel counter (unknown units, needs calibration). Wheel speeds 0x1D0, steering 0x14A, torque 0x17C, doors 0x405.
- **ADAS:** Separate CAN bus. NOT accessible through OBD-II port. Out of scope.
- **Key gap we fill:** Honda dashboard shows average MPG but NOT instant MPG.

---

## WiCAN Pro Connection Details (researched March 22, 2026)

- **ELM327 mode (primary):** TCP port **3333**. ASCII hex responses like `41 0C 0F A0\r\n>`. python-obd connects here.
- **Raw CAN mode:** TCP port **35000** for SocketCAN via socat. JSON WebSocket for raw frames: `{"bus":"0","type":"rx","frame":[{"id":2024,"dlc":8,"data":[...]}]}`. CAN IDs are **decimal**.
- **AutoPID HTTP:** `GET http://<wican_ip>/autopid_data` returns pre-parsed JSON with configurable vehicle profile.
- **Init sequence:** `ATSP6` (mandatory), `ATSH7E0`, `ATCRA7E8`
- **Default WiFi password:** `@meatpi#` -- **CHANGE THIS** on first setup.
- **First connection checklist:** Send `0100`/`0120`/`0140`/`0160` for PID bitmasks. Test 015E (expect unsupported). Test Mode 22 CVT temp. Log `TRIP_FUEL_CONSUMED` counter.

---

## Performance Budgets

| Resource | Budget |
|----------|--------|
| Pi CPU | <50% sustained (target 15-30%) |
| Pi RAM | <1GB total (OS ~150MB + app ~400MB + ML ~130MB) |
| 3D model | 20,000-50,000 triangles |
| Draw calls | <100 |
| Shadows | Disabled |
| Lights | Max 3 |
| Pixel ratio | Capped at 2x |
| Textures | Max 512x512, KTX2 compressed |
| WebSocket msg size | 200-400 bytes |
| WebSocket rate | 10Hz |
| Bandwidth | ~10-20 KB/sec |
| End-to-end latency | <140ms (OBD poll -> screen update) |
| Phone frame rate | 30 fps minimum |

---

## Key Dependencies

### Python (Pi backend -- always in venv)

```
fastapi==0.135.1
uvicorn[standard]==0.42.0
obd==0.7.3
scikit-learn==1.8.0
scipy==1.17.1
pydantic==2.12.5
aiosqlite==0.22.1

# v3+ (sensor fusion)
tflite-runtime==2.14.0
PyWavelets==1.9.0
librosa==0.11.0

# v4 (reports)
Jinja2==3.1.6
matplotlib>=3.10,<3.11
WeasyPrint==68.1
```

### Frontend (React PWA -- package.json)

```json
{
  "react": "^19.2.4",
  "react-dom": "^19.2.4",
  "zustand": "^5.0.12",
  "typescript": "^6.0.2"
}
```

**No Three.js.** Frontend is pure SVG + CSS animations. Build tooling: Vite 8.0.0. Requires Node.js 20.19+ or 22.12+.

---

## What NOT to Do

- **Do NOT use InfluxDB or TimescaleDB** -- 50-70% CPU on Pi 4B from TSM compaction. SQLite WAL handles our workload.
- **Do NOT use Flutter, SvelteKit, Vue, or Angular** -- React 19 + R3F 9 is the definitive frontend choice.
- **Do NOT use Bluetooth for WiCAN Pro** -- WiFi station mode only. Pi Bluetooth is unreliable for OBD.
- **Do NOT generate OBD write commands** -- Repeated intentionally. Modes 01, 02, 03, 09 only.
- **Do NOT install Python packages globally** -- Always use a venv on the Pi.
- **Do NOT use ELM327 auto-protocol detection** -- Manually select ISO 15765-4, 11-bit, 500 kbaud for 2026 Honda.
- **Do NOT add hybrid/i-MMD features** -- Car is 1.5T non-hybrid. No regen, no EV mode, no ICE start counting.
- **Do NOT add real-time audio coaching** -- Driving coach is post-trip visual only. No audio cues while driving.
- **Do NOT add federated learning** -- Cut from scope entirely.
- **Do NOT add ADAS features** -- Separate CAN bus, not accessible via OBD-II port.
- **Do NOT use Hailo accelerator** -- Incompatible with Pi 4B (needs Pi 5 PCIe).
- **Do NOT use Bookworm** -- Trixie (Debian 13) is the current Raspberry Pi OS since Oct 2025.
