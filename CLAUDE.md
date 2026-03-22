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

Rune is the car -- a 2026 Honda Accord SE. What we're building is the translation layer: the bond between Rune and the human who drives him. A Pi 4B in the armrest listens to Rune's signals and translates them into a Tron-style 3D visualization, health scoring, and fuel intelligence on a Pixel 6 Pro via React PWA. Zero cloud dependency. GitHub: [meetrune/rune](https://github.com/meetrune/rune).

See `PRD.md` for full specifications, data contracts, OBD PID tables, build timeline, and hardware installation guide.

```
CURRENT PHASE: v1 -- First words (Desktop Development, Simulated Data)
```
Update this line as phases progress: v1 First words -> v2 Rune coaches -> v3 Rune feels -> v4 Rune speaks to the world (open source launch).

---

## Architecture

- **Backend:** Python 3.13 on Raspberry Pi OS Trixie (Debian 13) 64-bit Lite
- **Web framework:** FastAPI 0.135.1 with uvicorn 0.42.0
- **OBD-II:** `obd` 0.7.3 (PyPI package name is `obd`, install with `pip install obd`). Async mode, `fast=True`.
- **Database:** SQLite with WAL mode via aiosqlite 0.22.1. **Not InfluxDB** (50-70% CPU on Pi from TSM compaction). **Not TimescaleDB.**
- **Frontend:** React 19.2.4 + React Three Fiber 9.5.0 + Three.js 0.183.2. PWA served from Pi. Built with Vite 8.0.0.
- **State management:** zustand 5.0.12
- **ML (classical):** scikit-learn 1.8.0 (Isolation Forest, Random Forest)
- **ML (deep, v3+):** tflite-runtime 2.14.0 (autoencoder inference on ARM64)
- **Signal processing (v3+):** scipy 1.17.1, PyWavelets 1.9.0
- **Audio (v3+):** librosa 0.11.0
- **Reports (v4):** Jinja2 3.1.6 + matplotlib 3.10.x + WeasyPrint 68.1
- **Data validation:** pydantic 2.12.5
- **Data flow:** All sensor data flows through Pi (central hub). WebSocket at 10Hz to phone. Phone is display + secondary sensor source.
- **Static frontend serving:** `app.mount("/", StaticFiles(directory="frontend/dist", html=True))`

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
- **Honda Mode 22:** `22 2201` byte 27 = CVT fluid temp (`byte - 40 = C`). Send `22 22 01` with header `7E0`. Needs testing on 2026 model.
- **Extended coolant:** PID `01 67` bytes 2+3 = engine block + radiator temps, each `byte - 40`.
- **CAN protocol:** ISO 15765-4, 11-bit addressing, 500 kbaud. **ALWAYS manually select protocol. NEVER use auto-detect.** 2025-2026 Hondas have enhanced CAN bus security causing auto-detect failures.
- **CAN signals (opendbc):** github.com/commaai/opendbc -- Honda Accord DBC files with 100+ decoded signals (wheel speeds 0x1D0, steering 0x0E4, torque 0x17C, doors 0x35E). Requires WiCAN Pro raw CAN mode.
- **ADAS:** Separate CAN bus. NOT accessible through OBD-II port. Out of scope.
- **Key gap we fill:** Honda dashboard shows average MPG but NOT instant MPG.

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
  "@react-three/fiber": "^9.5.0",
  "@react-three/drei": "^10.7.7",
  "@react-three/postprocessing": "^3.0.4",
  "three": "^0.183.2",
  "zustand": "^5.0.12",
  "typescript": "^5.9.3"
}
```

Build tooling: Vite 8.0.0. Requires Node.js 20.19+ or 22.12+.

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
