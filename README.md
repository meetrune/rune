# Meet Rune.

He's a 2026 Honda Accord SE. Meteorite Gray Metallic. 1.5T turbo, CVT. He's been talking since the day he left the factory -- hundreds of signals every second pulsing through his CAN bus. Engine temperature, fuel flow, wheel speed, voltage. A language he speaks fluently.

You just never had a way to hear him.

This project is that way. A Raspberry Pi tucked inside his armrest, a small WiFi adapter plugged into his OBD-II port, and a spare phone on the vent. That's all it takes. Rune's signals become a glowing 3D model where his engine beats like a heart, coolant flows like blood, and wires spark like nerves. When something's off, he doesn't throw a code at you. He just tells you.

> "Down 8% on fuel over the past three weeks. Hasn't changed on your end -- same routes, same driving. Something's off with me. Could be the air filter, could be tire pressure. Worth a look."

> "Grand River saves you sixty cents a trip over I-496. I run easier on it -- less stop-and-go."

> "Running warmer than I should be. 101 degrees -- not critical, but I don't usually sit here. Keep an eye on it."

> "Full tank. 9.2 gallons back in me. 28.4 MPG since last fill -- right where I should be."

Everything runs locally. No cloud, no subscription, no data leaving the car. Read-only, always. Rune never gets touched -- only listened to. Like a stethoscope on a heartbeat.

---

### What Rune can tell you

**How he's feeling.** A 0-100 health score that learns what "normal" means for him over 500 miles. Three layers of awareness running on a $55 Pi -- real-time pulse tracking, pattern recognition every 30 seconds, and trend analysis that spots problems weeks early. When everything's good: "All good. 92 across the board." When it's not, he tells you straight.

**What he's burning.** Instant MPG that his dashboard doesn't show. Cost per trip in dollars. Route comparisons for your commute. Monthly fuel budgets with pace projections. Automatic fill-up logging with zero manual input. When efficiency drops for no reason, he connects it to his own health data and tells you why.

**How you're driving.** Post-trip scores across five dimensions. Route-specific insights after enough data. Savings in real dollars versus your first month -- not abstract numbers.

**What the road feels like.** A sensor under the seat feels every bump, vibration, and shimmy at 8,000 samples per second. A microphone behind the dash listens to his engine. Together with the OBD data, he separates rough roads from real problems.

**How to talk to your mechanic.** Professional PDF reports matching the format of $5,000 scan tools. Summary up front, technical detail underneath. He explains what he's feeling in a way both you and a tech can understand.

---

### How the connection works

```
Rune (the car)
    |
    | speaks through the OBD-II port
    v
[WiCAN Pro]  --- WiFi --->  [Raspberry Pi 4B]  --- WiFi --->  [Pixel 6 Pro]
 under the dash              in the armrest                     on the vent
 listens to Rune             translates                         shows you
```

---

### Status

v1 built. 352 tests. Production-ready. Hardware delivered. Ready to connect.

---

### Project structure

Organized by device. Each folder tells you where its code runs.

```
pi/           Raspberry Pi 4B -- backend, deploy scripts, diagnostics dashboard
pixel/        Pixel 6 Pro -- React PWA frontend (4-screen car OS)
mac/          MacBook Pro -- training workstation (v5+, placeholder)
tests/        All 352 tests
docs/         PRD, research, hardware checklist
```

---

### Setting up

**Pi (first time):**
```bash
# 1. Flash Raspberry Pi OS Trixie 64-bit Lite to SD card
# 2. SSH in, clone the repo
git clone https://github.com/meetrune/rune.git
cd rune

# 3. Build the frontend (on your dev machine first)
cd pixel/frontend && npm ci && npm run build && cd ../..

# 4. Run the setup script (creates user, venv, WiFi AP, systemd service)
sudo pi/deploy/setup.sh --wifi-pass "your-wifi-password"

# 5. Start Rune
sudo systemctl start rune

# Dashboard: http://192.168.4.1:8080
# Diagnostics: http://192.168.4.1:8080/diagnostics
# From MacBook: http://rune.local:8080
```

**Witty Pi 4 (power management):**
```bash
# Mount on Pi GPIO headers, insert CR2032 battery
sudo pi/deploy/wittypi-setup.sh
# Verify: i2cget -y 1 0x08 0x01  (should return Vin integer)
```

**Pixel 6 Pro:**
1. Connect to "Rune" WiFi network
2. Open Chrome, go to `http://192.168.4.1:8080`
3. Install as PWA (Add to Home Screen)

**Going live (removing simulation):**
1. Open diagnostics: `http://192.168.4.1:8080/diagnostics`
2. Scroll to Manual Controls
3. Click the red "Remove Complete Simulation" button
4. Confirm -- all fake data is purged, real OBD connection activates

**Local development (Mac):**
```bash
cd rune
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
PYTHONPATH=pi uvicorn backend.main:app --host 0.0.0.0 --port 8080
# Runs with simulator by default (RUNE_USE_SIMULATOR=true)
```

---

### Docs

| File | What it is |
|------|-----------|
| [`CLAUDE.md`](CLAUDE.md) | Project instructions and safety rules |
| [`docs/PRD.md`](docs/PRD.md) | Full product requirements, data contracts, build timeline |
| [`docs/research/`](docs/research/) | Original research documents |

---

*Built by [Kuladeep Mantri](https://github.com/kuladeepmantri).*
