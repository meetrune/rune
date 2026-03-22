# Meet Rune.

Rune lives in your car. A Raspberry Pi tucked inside the armrest, connected to your engine through a tiny WiFi adapter. He watches every heartbeat, tracks every mile, and shows you what's really happening under the hood -- through a glowing 3D model on your phone.

Built for a **2026 Honda Accord SE**. Read-only. Open source. MIT license.

---

### What Rune does

**He sees the car.** A Tron-style 3D sedan on your phone that glows, pulses, and shifts color with live engine data. The engine beats like a heart synchronized to RPM. Coolant flows as particles through animated paths. Wires spark brighter when voltage climbs. Touch to rotate 360 degrees. Tap any subsystem to inspect it.

**He watches over the car.** A 0-100 health score that learns what "normal" looks like for your specific car over 500 miles, then flags anything that drifts. Three detection layers running on a $55 Pi: statistical tracking that catches spikes in under a millisecond, a multivariate anomaly detector that spots combinations no single sensor would catch, and long-term trend analysis that predicts problems weeks before they become failures.

**He tracks your fuel and money.** Instant MPG that the Honda dashboard doesn't show. Cost per trip in dollars. Route comparison for your commute. Monthly fuel budgets with pace projections. Automatic fill-up logging with zero manual input. And when your efficiency drops for no reason, Rune tells you why.

**He coaches your driving.** Post-trip efficiency scores across five dimensions. Route-specific insights after enough data: "This route costs $0.60 less per trip." Dollar-amount savings versus your first month, not abstract scores.

**He feels the road.** A chassis-mounted accelerometer at 8,000 samples per second detects tire imbalance, suspension wear, and road quality. A MEMS microphone behind the dashboard listens to the engine for misfires, belt wear, and bearing noise. Rune fuses these with OBD data to separate real problems from road bumps.

**He explains to your mechanic.** Professional PDF reports matching the format of $5,000 diagnostic tools. Customer-friendly summary up front with traffic-light indicators. Detailed technical section with DTCs, freeze frames, trend charts, and spectrograms underneath.

---

### How Rune works

```
Your car's OBD-II port
    |
    v
[WiCAN Pro] --- WiFi ---> [Raspberry Pi 4B] --- WiFi ---> [Pixel 6 Pro]
 under dash                 in armrest                      on vent mount
 reads the car              the brain                       the face
```

Rune never writes to the car. He only reads. Every command passes through a whitelist that blocks all write operations at the code level. Like a thermometer -- he reads the temperature, he doesn't change it.

---

### Status

**Pre-development.** Research complete. Hardware ordered ($200.86 total). PRD and architecture docs finalized. Code starts Week 1.

---

### Project structure

```
rune/
├── README.md               # You are here
├── CLAUDE.md               # Project instructions for Claude Code
└── docs/
    ├── PRD.md              # Product Requirements Document
    └── research/           # Original research documents
        ├── deep-research-enhancements.md
        ├── complete-build-guide.md
        ├── build-plan-v1.html
        ├── research-conversation-1.pdf
        └── research-conversation-2.pdf
```

Code directories (`backend/`, `frontend/`, `tests/`) will be created when development begins.

---

### Hardware

| Component | Role | Cost |
|-----------|------|------|
| Raspberry Pi 4B (4GB) | The brain. Lives in the armrest. | Already owned |
| Pixel 6 Pro | The face. Dedicated to Rune. | Already owned |
| WiCAN Pro | Reads OBD-II / CAN bus data over WiFi | $102.34 |
| Witty Pi 4 HAT | Power management, RTC, graceful shutdown | $57.09 |
| Sensors + mounting + cables | MPU-6050, INMP441, BME280, Y-splitter, clips, mount | $41.43 |
| **Total** | | **$200.86** |

---

### Safety

Rune is read-only by design. The first code written for this project is a command whitelist that only allows OBD-II Modes 01, 02, 03, 09, and 22 (all read-only). Write modes (04, 08, 10, 27, 2E, 31, 3E) are blocked at the code level. There is no code path that can write to the vehicle.

The Magnuson-Moss Warranty Act protects your warranty. Honda cannot void it for using a read-only OBD adapter.

---

### Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI 0.135.1, SQLite WAL |
| Frontend | React 19.2.4, React Three Fiber 9.5.0, Three.js 0.183.2, Vite 8.0.0 |
| ML | scikit-learn 1.8.0 (Isolation Forest), TFLite 2.14.0 |
| OBD-II | python-obd 0.7.3 via WiCAN Pro WiFi |
| Platform | Raspberry Pi OS Trixie (Debian 13) 64-bit Lite |
| Display | Chrome PWA on Pixel 6 Pro (Screen Wake Lock) |

---

*Built by [Kuladeep Mantri](https://github.com/kuladeepmantri).*
