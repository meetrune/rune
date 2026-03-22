# Rune -- Product Requirements Document

**Version:** 1.0
**Date:** March 22, 2026
**Author:** Kuladeep Mantri
**Status:** Pre-development

---

## 0. Safety Covenant

**THIS SECTION OVERRIDES EVERYTHING ELSE IN THIS DOCUMENT.**

Rune is the car. What we build is the translation layer -- the bond between Rune and the human who drives him. This system is **READ-ONLY**. It listens to Rune. It never speaks for him, never changes him, never writes to the vehicle.

### Allowed OBD-II Modes (read-only)

```
Mode 01 -- Current powertrain data (live sensor readings)
Mode 02 -- Freeze frame data (snapshot at time of fault)
Mode 03 -- Read diagnostic trouble codes
Mode 09 -- Vehicle information (VIN, calibration IDs)
Mode 22 -- UDS ReadDataByIdentifier (read-only, Honda proprietary PIDs like CVT fluid temp)
```

### Blocked OBD-II Modes (write/control -- NEVER USE)

```
Mode 04 -- Clear diagnostic trouble codes (WRITES)
Mode 08 -- Control onboard systems (WRITES)
Mode 10 -- UDS diagnostic session control
Mode 27 -- UDS security access (seed/key authentication)
Mode 2E -- UDS write data by identifier
Mode 31 -- UDS routine control
Mode 3E -- UDS tester present
```

### SafeOBDConnection (first code written)

```python
ALLOWED_MODES = {'01', '02', '03', '09', '22'}  # 22 = UDS ReadDataByIdentifier (read-only)
BLOCKED_MODES = {'04', '08', '10', '27', '2E', '31', '3E'}

def send_command(self, cmd: str) -> Response:
    mode = cmd.strip().split()[0].upper()
    if mode not in ALLOWED_MODES:
        raise BlockedCommandError(
            f"BLOCKED: Mode {mode} is not in the read-only whitelist. "
            f"Rune only uses read-only modes: {ALLOWED_MODES}"
        )
    return self._connection.query(cmd)
```

**Why this is safe:**
- OBD-II Mode 01 queries are read-only by design per ISO 15031-5
- Writing to the ECU requires UDS services (0x2E, 0x31) with authenticated seed/key exchange -- impossible to trigger through a standard OBD adapter
- No documented case exists of a read-only adapter damaging a Honda ECU in 10+ years of consumer use
- The Magnuson-Moss Warranty Act (15 U.S.C. 2301) protects consumers. Honda cannot void warranty solely because a read-only OBD adapter was used

---

## 1. Vision

Your car already talks. Every second, hundreds of signals pulse through its CAN bus -- RPM, coolant temperature, fuel flow, wheel speed, voltage. Rune has been speaking this language since he left the factory. The problem is no one built a way for you to understand him.

Rune is the car. The 2026 Honda Accord SE, Meteorite Gray Metallic. What we're building is the translation layer -- the bond between Rune and the human who drives him. A system where Rune can show you how he feels through a glowing 3D model, tell you what he's burning in dollars not gauges, and warn you weeks before something goes wrong -- not with error codes, but in language that makes sense.

**The gap:** The Honda Accord dashboard shows average MPG but not instant MPG. No open-source project turns raw vehicle signals into a living connection between car and driver. Nothing out there feels like this.

**Target audience:** Enthusiast developers building portfolio projects for automotive tech careers (Tesla, Rivian, Honda R&D, Waymo, Continental/AUMOVIO).

**GitHub:** [meetrune/rune](https://github.com/meetrune/rune)
**License:** MIT. Open source. Zero cloud dependency. Everything runs locally on a $55 Pi and a spare phone.

---

## 1.1 Rune's Voice

Rune speaks like a brother. Not a servant, not a robot, not a dashboard. A brother who has your back, who respects you enough to be direct, and who you trust enough to listen to.

### The rules

1. **Direct, not dramatic.** Rune says what's happening and what it means. No alarmist language, no corporate jargon, no marketing speak. He respects your intelligence.
2. **First person.** Rune says "I'm running warm" not "coolant temperature elevated." He talks about himself because he IS the car.
3. **Honest about uncertainty.** "Could be the air filter, could be tire pressure" -- not "CRITICAL: SERVICE REQUIRED." If he doesn't know, he says so.
4. **Brief.** Rune doesn't over-explain. If it's good, he says it's good. If something's wrong, he tells you what, how bad, and what to do about it. Then he stops.
5. **Never performative.** No forced personality, no catchphrases, no emoji, no "Hey there!" energy. Just steady and real.
6. **Respects the relationship.** He doesn't boss you around. He gives you information and lets you decide. "Worth a look" not "YOU MUST SERVICE IMMEDIATELY."

### How Rune sounds across situations

**Everything's fine:**
> "All good. 92 across the board."
> "Running clean today. Nothing to report."

**Something needs attention (not urgent):**
> "Running warmer than I should be. 101 degrees -- not critical, but I don't usually sit here. Keep an eye on it."
> "Down 8% on fuel over the past three weeks. Hasn't changed on your end -- same routes, same driving. Something's off with me. Could be the air filter, could be tire pressure. Worth a look."

**Something serious:**
> "Something I need to tell you. My catalyst efficiency has been dropping for about two weeks now. It's not urgent today, but it's trending the wrong way. I'd get it looked at within a thousand miles."

**Fuel and trips:**
> "That was 12.4 miles, 1.2 gallons, $4.08. You averaged 32 MPG -- solid run."
> "Grand River saves you sixty cents a trip over I-496. I run easier on it -- less stop-and-go."
> "Full tank. 9.2 gallons back in me. 28.4 MPG since last fill -- right where I should be."

**Budget:**
> "$87 of $150 spent with 12 days left. At this pace you'll hit $162. Ease off the throttle and you'll make it."

**Gas timing:**
> "Based on how the last two weeks have gone, I'll need fuel by Thursday."

**Calibration period:**
> "Still getting to know each other. Give me 500 miles or a couple more weeks and I'll have my baselines down."

**During idle:**
> "Idling. Burning about 0.3 gallons an hour."

---

## 2. Vehicle

**2026 Honda Accord SE** -- Meteorite Gray Metallic

| Spec | Value |
|------|-------|
| Engine | L15BE 1.5L VTEC Turbo 4-cylinder |
| Output | 192 hp / 192 lb-ft torque |
| Transmission | CVT (Continuously Variable) |
| Drivetrain | FWD |
| Fuel tank | 14.8 gallons |
| Fuel economy | 28 city / 36 highway / 31 combined MPG (EPA) |
| Hybrid | **No. The SE trim is non-hybrid. The hybrid uses a 2.0L engine.** |
| OBD-II protocol | ISO 15765-4 (CAN bus, 11-bit, 500 kbps) |
| OBD-II port | Under dashboard, driver's side, left of steering column. Behind removable snap-clip panel. |

---

## 3. Hardware Platform

### Already Owned

| Component | Specs | Role |
|-----------|-------|------|
| Raspberry Pi 4B | 4GB RAM, BCM2711 quad-core Cortex-A72 | The brain. FastAPI, OBD polling, ML inference, sensor fusion. |
| Google Pixel 6 Pro | Google Tensor, 12GB RAM, Mali-G78 MP20 GPU, 6.7" LTPO OLED, LSM6DSO IMU | The face. Displays React PWA. Dedicated to this project. |
| MicroSD card | Currently in Pi running Raspberry Pi OS | Development use. Back up to GitHub monthly. |
| USB-C to USB-C cable | From SanDisk SSD | Connects Pixel 6 Pro to console USB-C charging port. |
| Dupont jumper wires | Multiple sets | Connecting sensors to Pi GPIO. |
| Small Phillips screwdriver | -- | Witty Pi terminal work. |

### All Hardware Ordered (March 22, 2026)

**Order 1: Crowd Supply -- $102.34**
Order #318980. Ships from Mouser warehouse, Mansfield TX. Expected delivery: March 30 - April 1, 2026.

| Item | Price |
|------|-------|
| WiCAN Pro OBD-II adapter | $89.00 + $8.00 shipping + $5.34 tax |

**WiCAN Pro specs:** ESP32-S3, WiFi + BLE, raw CAN bus + CAN-FD, dedicated OBD interpreter chip supporting all legislated protocols (ISO 15765-4, SAE J1939, GMLAN, J1850), ELM327/ELM329/STN instruction set emulation, WebSocket communication, sleep mode <3mA, firmware v4.40, open-source firmware (meatpiHQ/wican-fw).

**Order 2: Adafruit -- $57.09**
Order #3653420-7503210349. UPS Ground, ~1 week delivery.

| Item | PID | Price |
|------|-----|-------|
| Witty Pi 4 HAT (RTC + power management) | 5704 | $39.95 |
| CR2032 Lithium Coin Cell Battery (for RTC) | 654 | $0.95 |
| | Shipping: $13.74 / Tax: $2.45 | **$57.09** |

**Order 3: Amazon -- $41.43**
Order #112-8743973-9470624. Expected delivery: Thursday, March 26, 2026.

| # | Item | Price |
|---|------|-------|
| 1 | Miracase Phone Mount (air vent, metal hook clip, Dark Black) | $12.34 |
| 2 | AITRIP INMP441 MEMS Microphone x3 pack (I2S digital, engine acoustics) | $9.99 |
| 3 | ZHWXFW BME280 x2 pack (temp/humidity/pressure, I2C) | $11.99 |
| 4 | HiLetgo GY-521 MPU-6050 (3-axis accel + 3-axis gyro, I2C) | $6.99 |
| 5 | bbfly-B6 OBD2 Y-Splitter (1ft/30cm, all 16 pins pass-through) | $10.90 |
| 6 | YONHAN 12V Cigarette Lighter Plug x2 pack (bare leads, 16AWG, 15A fuse) | $6.39 |
| 7 | JOTO Car Cable Clips x10 (adhesive, black) | $6.99 |
| 8 | Scotch Extreme Interlocking Fasteners (4 strips, 1"x3", Dual-Lock) | $4.98 |

### Total Hardware Cost

| Source | Amount |
|--------|--------|
| Crowd Supply (WiCAN Pro) | $102.34 |
| Adafruit (Witty Pi 4 + battery) | $57.09 |
| Amazon (8 items) | $41.43 |
| **GRAND TOTAL** | **$200.86** |

### Not Buying (Decided Against)

- **Flirc aluminum case** -- Won't fit with Witty Pi 4 HAT stacked on top. Using Scotch Dual-Lock strips in armrest instead.
- **Add-a-fuse tap** -- Not needed. Using 12V outlet inside armrest compartment (ignition-switched).
- **u-blox NEO-M8N GPS module** -- Deferred. Using Pixel 6 Pro built-in GPS via Web Geolocation API (~1Hz).
- **Dedicated MicroSD** -- Already own one in the Pi.
- **Hailo AI accelerator** -- Incompatible with Pi 4B (requires Pi 5 PCIe).
- **Google Coral USB** -- Approaching end-of-life.

### DO NOT BUY

- **ELM327 clones ($5-25):** Counterfeit chips truncate commands. 45-100+ mA parasitic drain with no sleep mode. Documented overnight battery kills. Can keep ECUs awake.
- **Veepeak BLE+ ($30):** No raw CAN access. Notoriously poor Bluetooth pairing with Raspberry Pi. python-obd docs explicitly warn about Pi Bluetooth issues.

---

## 4. Physical Installation

Mapped from actual photos taken March 22, 2026.

### Installation Layout

```
DRIVER'S SIDE (under dash, behind snap-clip panel):
  [OBD-II Port] --> [bbfly-B6 Y-Splitter] --> Port 1: [WiCAN Pro] (permanent, hidden)
                                           --> Port 2: Open for dealer diagnostic scanner
                     WiCAN Pro communicates to Pi via WiFi (station mode on Rune network)
                     Powered by OBD port (no extra wiring)

CENTER ARMREST COMPARTMENT:
  [12V Outlet]  --> [YONHAN 12V plug] --> bare leads --> [Witty Pi 4 HAT + CR2032]
   (180W MAX)                                            stacked on [Raspberry Pi 4B]
   ignition-sw                                           (secured with Scotch Dual-Lock)
                                                         + [ZHWXFW BME280] next to Pi (I2C)

CENTER CONSOLE USB-C PORT:
  [Charging Port] --USB-C cable--> [Pixel 6 Pro on Miracase Vent Mount]
   (charge only)                    Driver's side leftmost vent
                                    Chrome PWA: 3D viz + fuel + health

UNDER DRIVER'S SEAT (v3 -- sensor fusion phase):
  [HiLetgo MPU-6050]  velcroed to seat frame
                      Jumper wire along floor to armrest Pi (I2C addr 0x68)
                      Routed with JOTO cable clips

BEHIND DASHBOARD TRIM (v3 -- sensor fusion phase):
  [AITRIP INMP441 Mic]  velcroed behind dash trim near firewall
                         Picks up engine audio through firewall
                         Wire to Pi GPIO (I2S: BCLK=GPIO18, LRCLK=GPIO19, DIN=GPIO20)
                         Routed with JOTO cable clips
```

### Network Topology

```
Pi 4B creates WiFi AP "Rune" (192.168.4.1)
  |
  |-- WiCAN Pro joins in station mode
  |     Sends OBD-II / raw CAN data to Rune
  |
  |-- Pixel 6 Pro joins
        Chrome PWA at http://192.168.4.1:8080
        Rune shows the car via WebSocket (ws://192.168.4.1:8080/ws)
        Phone sends GPS + accelerometer data back via second WS channel
```

### GPIO Pin Assignments

| Bus | Protocol | GPIO Pins | Devices |
|-----|----------|-----------|---------|
| I2C | I2C (shared bus) | GPIO 2 (SDA), GPIO 3 (SCL) | MPU-6050 (addr 0x68), BME280 (addr 0x76 or 0x77), Witty Pi 4 |
| I2S | I2S (dedicated) | GPIO 18 (BCLK), GPIO 19 (LRCLK), GPIO 20 (DIN) | INMP441 MEMS microphone |

- I2C bus is shared between MPU-6050 and BME280 (different addresses, no conflict)
- Witty Pi 4 also uses I2C for RTC communication
- I2S bus is dedicated to the INMP441 microphone

### Key Physical Notes

- **12V outlet** is ignition-switched (power only when car ON). Witty Pi 4 detects voltage drop and triggers graceful `shutdown -h` on Pi. CR2032 battery keeps RTC running between ignition cycles.
- **Wireless charging pad** in console tray is NOT used (phone is on Miracase vent mount, not flat).
- **Hood/trunk release buttons** are near the OBD port -- useful landmarks for locating it.
- **Nothing goes near the pedals.** OBD port and fuse box are 12+ inches above pedal area.
- **Fuse box** is directly above/behind OBD port. Low-profile mini fuses (red 10A, yellow 20A). Fuse #9 (FR ACC SOCKET) is switched accessory. NOT used in this project -- power comes from 12V outlet.
- **Everything unplugs in 2 minutes with zero trace** for dealer service visits. Y-splitter keeps dealer diagnostic access.
- **Scotch Dual-Lock** holds 2 lbs per strip set, weather/UV resistant, removable without damage.

---

## 5. Intelligence Layers

### Tier Definitions

- **MVP (v1):** Ships in Weeks 1-5. The core product. Must work before anything else.
- **Enhancement:** Adds significant value. Built incrementally after MVP is solid.
- **Stretch:** Impressive but optional. Build if time allows.

### Layer Summary

| # | What Rune does | Tier | Version | Description |
|---|----------------|------|---------|-------------|
| 1 | Shows you how he feels | **MVP** | v1 | Tron-style 3D sedan on phone. 360-degree touch rotation. Subsystems glow and pulse with live data. The engine beats like a heart. |
| 2 | Watches over himself | **MVP** | v1 | 0-100 health score that learns what "normal" means for this specific car. Three detection layers. Tells you when something drifts. |
| 3 | Tracks what he burns | **MVP** | v1 | Instant MPG the Honda dash doesn't show. Cost per trip in dollars. Route comparisons. Budget tracking. Auto fill-up logging. |
| 4 | Helps you drive better | Enhancement | v2 | Post-trip scores. Route-specific insights. Savings in dollars vs your first month. No real-time audio -- just a debrief after you park. |
| 5 | Feels the road | Enhancement | v3 | Chassis accelerometer at 8kHz + phone IMU. Detects tire imbalance, suspension wear, road quality. Separates road bumps from real problems. |
| 6 | Listens to himself | Enhancement | v3 | MEMS mic behind the dash hears misfires, belt wear, bearing noise, knock. CNN classification across 7 fault categories at 92%+ accuracy. |
| 7 | Explains to your mechanic | Enhancement | v4 | Professional PDF reports matching $5K scan tool format. Summary for the customer, technical detail for the tech. |
| 8 | Connects the dots | Stretch | v4 | 8-node subsystem graph. Sees cascading failures that per-sensor detection misses. ~200KB model, <10ms inference. |

**Cut from scope:** Federated learning, real-time audio coaching while driving, hybrid/i-MMD features, ADAS data.

---

## 6. Fuel Intelligence (MVP) -- Rune tracks what he burns

**The 2026 Honda Accord dashboard shows average MPG but not instant. Rune fixes that.**

### 6.1 Real-Time Instant MPG

- **Source PIDs:** 015E (engine fuel rate, L/h) and 010D (vehicle speed, km/h)
- **Formula:** `MPG = (speed_kmh * 0.621371) / (fuel_rate_lph * 0.264172)`
- **Idle edge case:** When speed = 0, display gallons/hour instead
- **Fallback:** If PID 015E is not supported on 2026 Accord, calculate from MAF (PID 0110): `fuel_rate_lph = (MAF_gps / 14.7 / 750) * 3600` where 14.7 is stoichiometric ratio, 750 is gasoline density (g/L), and *3600 converts L/s to L/h
- **Display:** Large, glanceable number on dashboard. Color coded: green >30 MPG, amber 20-30 MPG, red <20 MPG
- **Rune says (idle):** "Idling. Burning about 0.3 gallons an hour."

### 6.2 Cost-Per-Trip Tracking

- Integrate PID 015E fuel rate over trip duration for total gallons consumed
- User enters local gas price manually (update weekly). Optional: GasBuddy API.
- **Rune says (post-trip):** "That was 12.4 miles, 1.2 gallons, $4.08. You averaged 32 MPG -- solid run."
- **Rune says (weekly):** "This week: 8.4 gallons, $28.56. Slightly better than last week."
- **Rune says (monthly):** "This month: 34 gallons, $115.60."
- SQLite `trips` table: trip_id, start_time, end_time, distance_miles, fuel_gallons, fuel_cost, avg_mpg, eco_score

### 6.3 Route Cost Comparison

- GPS-based route fingerprinting via Web Geolocation API (~1Hz from Pixel 6 Pro)
- Geofence waypoints identify distinct routes to same destination
- Primary commute: Lansing (313 N Capitol Ave) to Dimondale (7150 HR Drive) -- Wed, Thu in-office + varies
- **Rune says (after 2+ weeks of data):** "You've been taking I-496 on Wednesdays. It costs you $3.80 a trip. Grand River gets you there for $3.20. I run easier on it -- less stop-and-go."
- SQLite `routes` table: route_hash, waypoints_json, avg_fuel_gal, avg_cost, trip_count

### 6.4 Monthly Fuel Budget Tracker

- User sets monthly fuel budget (e.g., $150)
- **Rune says (on pace):** "$87 of $150 spent with 12 days left. You're on track."
- **Rune says (over pace):** "$87 of $150 spent with 12 days left. At this pace you'll hit $162. Ease off the throttle and you'll make it."

### 6.5 Fuel Savings Attribution

- Baseline efficiency established during calibration (first 500 miles / 14 days)
- **Rune says:** "You've been driving cleaner this month. Eco-score went from 62 to 78. That's about $23.40 saved compared to your first month."
- Dollar amounts, not abstract scores. This is the long-term motivation hook.

### 6.6 Gas Station Timing Prediction

- Track fuel tank level via PID 012F (0-100%)
- Learn consumption pattern over time (daily average, commute days vs weekends)
- **Rune says:** "Based on how the last two weeks have gone, I'll need fuel by Thursday."
- Optional: GasBuddy API for nearby station prices along commute route

### 6.7 Automatic Fill-Up Log

- Detect fill-up event: fuel tank level jumps >20% between readings
- Auto-log: date, estimated gallons (tank % delta * 14.8 gal), cost (if gas price known), calculated MPG since last fill
- **Tank capacity: 14.8 gallons** (2026 Honda Accord SE)
- **Rune says:** "Full tank. 9.2 gallons back in me. 28.4 MPG since last fill -- right where I should be."
- Zero manual input fuel history over months

### 6.8 Efficiency Degradation Alert

- If average MPG drops >5% over 2+ weeks without change in driving behavior or routes, flag it
- Cross-reference with Rune's health data: fuel trim drift (LTFT trending beyond +/-10%), O2 sensor response degradation, intake air temp anomaly
- **Rune says:** "Down 8% on fuel over the past three weeks. Hasn't changed on your end -- same routes, same driving. Something's off with me. Could be the air filter, could be tire pressure. Worth a look."

### Fuel Intelligence OBD PIDs

| PID | Parameter | Formula | Units | Purpose |
|-----|-----------|---------|-------|---------|
| 015E | Engine fuel rate | (A*256+B)*0.05 | L/h | Instant MPG, trip fuel integration |
| 010D | Vehicle speed | A | km/h | MPG calculation, distance |
| 012F | Fuel tank level | A*100/255 | % | Fill-up detection, gas timing |
| 010C | Engine RPM | (A*256+B)/4 | rpm | Idle fuel tracking |
| 0104 | Engine load | A*100/255 | % | Efficiency context |
| 010F | Intake air temp | A-40 | C | Seasonal baseline adjustment |
| 0110 | MAF air flow | (A*256+B)/100 | g/s | Fuel rate fallback calculation |

---

## 7. Data Contracts

### Core OBD-II PIDs (Mode 01 -- read-only, federally mandated)

| PID | Parameter | Formula | Units | 3D Visual | Fuel Intel |
|-----|-----------|---------|-------|-----------|------------|
| 0104 | Engine load | A*100/255 | % | Engine glow intensity | Efficiency context |
| 0105 | Coolant temp | A-40 | C | Engine block color gradient | -- |
| 0106 | Short-term fuel trim B1 | (A-128)*100/128 | % | Fuel system health color | -- |
| 0107 | Long-term fuel trim B1 | (A-128)*100/128 | % | Fuel system trend arrow | Degradation alert |
| 010B | Intake manifold pressure | A | kPa | Intake animation | -- |
| 010C | Engine RPM | (A*256+B)/4 | rpm | Engine pulse rate (heartbeat) | Idle fuel tracking |
| 010D | Vehicle speed | A | km/h | Wheel rotation speed | MPG calculation |
| 010F | Intake air temp | A-40 | C | Temperature bin selection | Seasonal baseline |
| 0110 | MAF air flow rate | (A*256+B)/100 | g/s | Air intake particles | Fuel rate fallback |
| 0111 | Throttle position | A*100/255 | % | Throttle body animation | -- |
| 012F | Fuel tank level | A*100/255 | % | Fuel gauge overlay | Fill-up detection |
| 013C | Catalyst temp B1S1 | ((A*256+B)/10)-40 | C | Exhaust system color | -- |
| 0142 | Control module voltage | (A*256+B)/1000 | V | Wire glow intensity | -- |
| 015C | Engine oil temp | A-40 | C | Oil system visualization | -- |
| 015E | Engine fuel rate | (A*256+B)*0.05 | L/h | Fuel consumption overlay | Instant MPG, trip cost |

### Honda Mode 22 Proprietary (needs testing on 2026 Accord)

| PID | Parameter | How to Query | Formula |
|-----|-----------|-------------|---------|
| 22 2201 | CVT fluid temp | Send `22 22 01` with header `7E0`, read byte 27 | byte - 40 = C |
| 01 67 | Extended coolant (dual sensor) | Standard Mode 01, bytes 2 and 3 | byte - 40 = C each (engine block + radiator) |

### CAN Bus Signals (via opendbc, 100Hz passive, requires WiCAN Pro raw CAN mode)

| CAN ID | Signal | Resolution | Visual Use |
|--------|--------|------------|------------|
| 0x1D0 | Individual wheel speeds (FL, FR, RL, RR) | 0.01 km/h | Differential wheel rotation |
| 0x0E4 | Steering angle and rate | deg, deg/s | Steering wheel animation |
| 0x094, 0x1B0 | Lateral + longitudinal acceleration | m/s2 | Vehicle dynamics visualization |
| 0x1A4 | Brake pedal pressure | % | Brake system health monitoring |
| 0x17C | Engine torque estimate | Nm | Power output visualization |
| 0x35E | Door status (individual) | boolean | Door open/closed overlay |
| 0x255, 0x296 | Turn signals, seatbelt, cruise control | binary | Status indicators |

### Data Access Tiers

1. **Guaranteed** (federal mandate, will always work): All Mode 01 PIDs, Mode 03 DTCs, Mode 09 VIN
2. **Likely** (manufacturer-specific, needs testing): Honda Mode 22 proprietary PIDs
3. **Requires raw CAN** (via opendbc DBC files): Individual wheel speeds, steering, torque, doors. Needs WiCAN Pro raw CAN mode.

**Out of scope:** Honda Sensing ADAS data (adaptive cruise, lead distance, LKAS, collision mitigation) lives on a separate ADAS CAN bus not accessible through the OBD-II port.

### WebSocket Message Schema

```json
{
  "t": 1711100000.123,
  "d": {
    "RPM": {"v": 2450, "u": "rpm"},
    "SPEED": {"v": 65, "u": "kph"},
    "COOLANT_TEMP": {"v": 92, "u": "degC"},
    "ENGINE_LOAD": {"v": 42, "u": "pct"},
    "FUEL_RATE": {"v": 2.8, "u": "lph"},
    "FUEL_LEVEL": {"v": 72.5, "u": "pct"},
    "THROTTLE_POS": {"v": 28, "u": "pct"},
    "BATTERY_V": {"v": 14.2, "u": "V"}
  },
  "health": {
    "overall": 87,
    "engine": 92,
    "transmission": 88,
    "fuel": 90,
    "cooling": 85,
    "exhaust": 82,
    "electrical": 91
  },
  "fuel": {
    "instant_mpg": 34.2,
    "trip_fuel_gal": 0.8,
    "trip_cost_usd": 2.72,
    "trip_distance_mi": 12.4,
    "tank_pct": 72.5
  }
}
```

### Polling Rates

| Method | Rate | Use Case |
|--------|------|----------|
| WiCAN Pro ELM327 mode | 2-5 PIDs/sec (50-100ms per roundtrip) | Standard OBD-II queries |
| WiCAN Pro ELM327 fast mode | ~7 responses/sec (appends "1" to reduce timeout) | Real-time dashboard |
| WiCAN Pro raw CAN | 100Hz passive per signal | High-res wheel speeds, steering, torque |
| WebSocket to phone | 10Hz | Smooth 3D animation with client-side interpolation |

---

## 8. Health Scoring -- how Rune watches over himself

### Three-Layer Architecture (~100-130MB on Pi)

| Layer | Frequency | Latency | RAM | Purpose |
|-------|-----------|---------|-----|---------|
| Dual-timescale EWMA | Every data point | <1ms | Negligible | Fast (alpha=0.3) tracks current state. Slow (alpha=0.01) tracks long-term baseline. Anomaly when fast-slow divergence exceeds threshold. Degradation when slow EWMA drifts over weeks. |
| Isolation Forest | Every 30 seconds | ~5ms | ~30MB | 100 trees. Detects multivariate anomalies that single-parameter checks miss (e.g., slightly elevated coolant + slightly elevated load + slightly low voltage = problem together, normal individually). |
| Trend Regression | Every 5 minutes | ~1ms | Negligible | Linear regression on 7-30 day rolling windows via scipy.stats.linregress. Flags statistically significant degradation (p < 0.05). Feeds remaining useful life estimates. |

### Subsystem Weights

```python
SUBSYSTEM_WEIGHTS = {
    'engine': 0.30,
    'transmission': 0.20,
    'fuel': 0.15,
    'cooling': 0.15,
    'exhaust': 0.10,
    'electrical': 0.10,
}
```

Each subsystem starts at 100, loses points from parameter deviations. Active DTCs impose penalties: -15 for confirmed generic powertrain codes, -30 for critical codes (misfire, catalyst, overtemp).

### Honda Accord 2026 SE Normal Operating Ranges

| Parameter | Normal | Warning | Critical |
|-----------|--------|---------|----------|
| Coolant temp | 82-96 C | 96-104 C | >110 C |
| Idle RPM | 650-750 | 500-650 or 750-900 | <500 or >1000 |
| Short-term fuel trim | +/-5% | +/-5-10% | >+/-10% |
| Long-term fuel trim | +/-5% | +/-5-10% | >+/-15% |
| Battery voltage (running) | 13.5-14.5V | 13.0-13.5V | <12.8V or >15.2V |
| Engine load at idle | 15-30% | 30-45% | >50% |
| O2 sensor response time | <100ms | 100-200ms | >400ms |
| CVT fluid temp (Mode 22) | 60-95 C | 95-115 C | >120 C |

### Calibration

- **Duration:** 500 miles or 14 days, whichever comes first
- **Method:** Baselines maintained per ambient temperature bin using intake air temp (PID 010F):
  - Cold: <5 C
  - Cool: 5-15 C
  - Mild: 15-25 C
  - Warm: 25-35 C
  - Hot: >35 C
- **Rune says:** "Still getting to know each other. Give me 500 miles or a couple more weeks and I'll have my baselines down."

### What Rune can tell you early (from OBD-II alone)

| What's happening | Lead Time | How Rune says it |
|------------------|-----------|-----------------|
| Catalyst degradation | 2-4 weeks | "Something I need to tell you. My catalyst efficiency has been dropping for about two weeks now. It's not urgent today, but it's trending the wrong way. I'd get it looked at within a thousand miles." |
| Fuel system issues (vacuum leak, MAF, injector) | 1-4 weeks | "My fuel trims have been drifting. LTFT is at 12% and climbing. That usually means I'm compensating for something -- could be a small vacuum leak or the MAF getting dirty." |
| Thermostat failure | Days-weeks | "I'm taking too long to warm up. Should be at 82 degrees in about 6 minutes but it's taking over 10. Thermostat might be sticking open." |
| O2 sensor aging | 2-8 weeks | "My O2 sensor is getting slow. Response time went from 80ms to 170ms over the past month. Not affecting anything yet but it'll need replacing eventually." |
| Alternator degradation | Days-weeks | "Voltage has been trending down under load. 14.1 last month, 13.6 now. Alternator might be on its way out. Worth checking before it leaves you stranded." |

### What Rune can't feel yet (needs v3 sensors)

Brake pad wear, suspension degradation, tire condition -- Rune can't detect these from OBD-II data alone. The vibration and acoustic layers (v3) give him those senses.

---

## 9. Tech Stack

### Pi 4B -- Backend

| Layer | Package | Version | Purpose |
|-------|---------|---------|---------|
| OS | Raspberry Pi OS Trixie (Debian 13) 64-bit Lite | Latest | Default since Oct 2025. Ships Python 3.13. 100-150MB idle RAM. OverlayFS for SD protection. 8-15s boot. |
| Runtime | Python | 3.13 | Ships with Trixie. |
| Web Framework | FastAPI | 0.135.1 | Async Python. Native WebSocket. Serves API + static frontend build. |
| ASGI Server | uvicorn | 0.42.0 | With `[standard]` extras for production. |
| OBD-II | obd (python-obd) | 0.7.3 | Async mode with `fast=True`. ~7 responses/sec. PyPI package name is `obd`. |
| Database | SQLite (stdlib) + aiosqlite | 0.22.1 | WAL mode. <10MB RAM. No daemon. Tables: trips, routes, sensor_readings, health_scores, fillups. |
| Data Models | pydantic | 2.12.5 | Settings classes, request/response models, config validation. |
| ML: Classical | scikit-learn | 1.8.0 | Isolation Forest (100 trees, ~30MB). Random Forest for driving style. |
| ML: Deep | tflite-runtime | 2.14.0 | Autoencoder inference for vibration/audio (v3). ARM64 wheels available. |
| Signal Processing | scipy | 1.17.1 | STFT, Butterworth filters, linregress for trends. |
| Wavelets | PyWavelets | 1.9.0 | CWT with Morlet/Daubechies-4 (v3). |
| Audio | librosa | 0.11.0 | MFCC extraction from engine audio (v3). |
| PDF Reports | Jinja2 | 3.1.6 | HTML report templates (v4). |
| PDF Charts | matplotlib | 3.10.x | Trend charts in diagnostic reports (v4). |
| PDF Render | WeasyPrint | 68.1 | HTML-to-PDF conversion (v4). |
| Real-time | WebSocket (FastAPI native) | -- | 10Hz push. 200-400 bytes/msg. ~10-20 KB/sec total. |

### Pixel 6 Pro -- Frontend (React PWA)

| Layer | Package | Version | Purpose |
|-------|---------|---------|---------|
| Platform | Chrome PWA | -- | Served from Pi at `http://192.168.4.1:8080`. Added to home screen. Screen Wake Lock API keeps display on. |
| UI Framework | React | 19.2.4 | React 19 stable. Functional components, hooks. |
| 3D Engine | @react-three/fiber (R3F) | 9.5.0 | Declarative Three.js for React 19. |
| 3D Helpers | @react-three/drei | 10.7.7 | OrbitControls, effects, loaders. |
| 3D Core | three | 0.183.2 | Three.js r183. 155KB gzipped core. |
| Post-processing | @react-three/postprocessing | 3.0.4 | Selective bloom (UnrealBloomPass). |
| State | zustand | 5.0.12 | Minimal reactive state from WebSocket stream. |
| Build | Vite | 8.0.0 | Fast builds. Static output served by FastAPI. Requires Node 20.19+ or 22.12+. |
| Types | TypeScript | 5.9.3 | Strict mode. |
| Phone Sensors | Web Generic Sensor API | -- | 60Hz accelerometer (Chromium hard cap). Secondary vibration source. |
| GPS | Web Geolocation API | -- | ~1Hz. Route fingerprinting, speed validation. |
| Wake Lock | Screen Wake Lock API | -- | Prevents screen sleep. Supported in all browsers since 2024. |

### Web API Limitations (researched and accepted)

| API | Limitation | Impact | Mitigation |
|-----|-----------|--------|------------|
| Generic Sensor (accelerometer) | **60Hz hard cap** in Chromium (privacy measure against gyrophone attacks) | Cannot reach 400Hz for vibration analysis | Chassis MPU-6050 at 8kHz via Pi I2C is primary vibration sensor. 60Hz phone is secondary. Native Kotlin companion app (~50 lines) is escape hatch if needed. |
| Geolocation | ~1Hz update rate | Cannot do sub-second position tracking | Sufficient for route fingerprinting and speed validation. |
| Background execution | WebSocket killed when tab backgrounded. Sensors stop. | Dashboard must stay in foreground. | Screen Wake Lock keeps display on. Dashboard is always-foreground use case. |
| Bluetooth | BLE only on Android Chrome. No Classic Bluetooth SPP. | Cannot connect to Bluetooth OBD adapters from web. | Using WiFi (WiCAN Pro). OBD data comes from Pi, not phone. |

---

## 10. Visual Design System

### Color Palette

| Element | Hex | CSS Variable | Usage |
|---------|-----|-------------|-------|
| Scene background | `#0A0E17` | `--bg-deep` | 3D scene background |
| Panel surface | `#0D1117` | `--bg-card` | UI cards and panels |
| Elevated surface | `#161B22` | `--bg-elevated` | Hover states |
| Primary accent | `#00D4FF` | `--accent-cyan` | Interactive elements, borders |
| Healthy green | `#00E676` | `--green` | Score 90-100, MPG >30 |
| Warning amber | `#FFB300` | `--amber` | Score 40-69, MPG 20-30 |
| Critical red | `#FF1744` | `--red` | Score <20, MPG <20 |
| Primary text | `#E6EDF3` | `--text-primary` | Headings, key values |
| Secondary text | `#8B949E` | `--text-secondary` | Labels, descriptions |
| Dim text | `#484F58` | `--text-dim` | Inactive, decorative |
| Temperature cold | `#1D4877` | `--temp-cold` | <60 C |
| Temperature normal | `#FBB021` | `--temp-normal` | 80-95 C |
| Temperature hot | `#EE3E32` | `--temp-hot` | >105 C |

### Biological Metaphor

| Vehicle System | Biological Analog | Animation |
|---------------|-------------------|-----------|
| Engine | Heart | Pulses red with RPM. 60 BPM at idle, faster at high RPM. `engine.position.y = Math.sin(time * rpm/1000) * 0.002` |
| Coolant | Circulatory system | Animated particles along coolant paths. Blue-to-red gradient based on temp. Speed proportional to flow rate. |
| Electrical | Nervous system | Propagating spark/pulse animations along wire paths. Glow intensity proportional to voltage. |
| Exhaust | Respiratory system | Particle emission from exhaust, density proportional to load. Color shifts with catalyst temp. |

**Transitions:** 200-400ms ease-out curves. Idle ambient animations cycle at 2000-4000ms. Only critical alerts use dramatic animation.

### NHTSA Phase 1 Compliance

- Individual off-road glances: **<2 seconds**
- Max visible non-driving text: **30 characters**
- Critical data (speed, RPM, health score, instant MPG): **9mm+ font**
- Max visible data elements at any time: **5**
- Communicate through **preattentive cues** (color, size, motion) over text

### 3D Model Specification

| Spec | Target |
|------|--------|
| Source | Generic sedan from Sketchfab (CC-BY license, e.g., assetfactory generic sedan). Attribution in README. |
| Modification | Blender: match sedan proportions to Accord. Segment into named mesh groups. |
| Mesh groups | body_shell, engine_block, wheel_FL, wheel_FR, wheel_RL, wheel_RR, exhaust_system, coolant_lines, wiring_harness |
| Triangle count | 20,000-50,000 |
| Export format | GLB with Draco compression (60-95% size reduction) |
| Controls | OrbitControls for 360-degree touch rotation, pinch-to-zoom, tap subsystem to inspect |
| Bloom | UnrealBloomPass via @react-three/postprocessing. luminanceThreshold: 1.0. Parts glow via emissiveIntensity >1.0. |

### Performance Targets

| Metric | Target |
|--------|--------|
| Frame rate | 30-45 fps on Pixel 6 Pro Chrome |
| Draw calls | <100 |
| Shadows | None (disabled for performance) |
| Pixel ratio | Capped at 2x (`renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))`) |
| Textures | Max 512x512 with KTX2 compression |
| Lights | Max 3 (ambient + 2 directional) |
| Scene graph | Flat hierarchy, instanced meshes where possible |

---

## 11. Build Timeline

### v1 -- MVP (Weeks 1-5): 3D Viz + Health Scoring + Fuel Intelligence

| Week | Focus | Key Tasks | Deliverable |
|------|-------|-----------|-------------|
| 1 | Pi backend + SafeOBD + simulator + fuel backend | SafeOBDConnection whitelist (FIRST CODE). FastAPI project structure. OBD simulator generating realistic Honda Accord values (warmup curves, throttle patterns, configurable anomaly injection). Fuel rate integration and instant MPG calculation. SQLite schema (trips, routes, readings, scores, fillups). WebSocket endpoint at `/ws/vehicle-data` streaming at 10Hz. | Pi serves realistic mock Honda Accord data over WebSocket. Verify from laptop browser. |
| 2 | React PWA + 3D visualization + fuel UI | React 19 + R3F 9 + Vite 8 project. WebSocket client hook. Download CC-BY sedan model, decimate in Blender, segment into subsystems, export GLB+Draco. Tron scene: #0A0E17 background, semi-transparent body, selective bloom. Data-to-visual bindings (coolant->color, RPM->pulse, wheels->rotation). Instant MPG display (large, color-coded). Trip cost display. Health score dashboard with subsystem cards. | PWA on Pixel 6 Pro shows animated 3D car + fuel data + health scores responding to simulated data. |
| 3 | Health scoring engine + fuel budget/tracking | Dual-timescale EWMA. Isolation Forest (100 trees). Per-subsystem scoring with Honda thresholds. Calibration mode (500mi/14d). Monthly fuel budget tracker UI. Fill-up detection logic. Route fingerprinting with simulated GPS. Gas station timing prediction. | Health scores update real-time. Inject anomalies in simulator, verify detection within 30s. Budget tracker functional. |
| 4 | Polish + integration testing | End-to-end integration testing. Fuel efficiency degradation alerts. Trend regression (7-30 day windows). Complete simulated MVP demo. PWA manifest + service worker for offline shell. **ORDER REMAINING HARDWARE this week.** | Complete simulated MVP. Demoable product with simulator. |
| 5 | Hardware setup + first real data | Install WiCAN Pro (expected delivery ~April 1). Configure: change default WiFi password (@meatpi#), set station mode on Rune network. **Manually select CAN protocol: ISO 15765-4, 11-bit, 500 kbaud** (do NOT auto-detect, 2026 Honda compatibility). Switch backend from simulator to real python-obd. Test all standard PIDs. Test Honda Mode 22 (CVT fluid temp). First real drive with full system. | Rune running on real vehicle data. Health scoring begins calibration. First real instant MPG readings. |

### v2 -- Driving Coach (Weeks 6-7)

| Week | Focus | Deliverable |
|------|-------|-------------|
| 6 | Driving style classification + eco-score | Random Forest on OBD features: acceleration RMS, speed variance, jerk (d(accel)/dt), throttle change rate, engine load. Three classes: Eco / Normal / Aggressive. Post-trip eco-score 0-100 across 5 dimensions (throttle smoothness, braking anticipation, cruising steadiness, load optimization, cold-start behavior). |
| 7 | Route learning + savings attribution | GPS geofencing route comparison using real commute data. Fuel savings vs baseline in dollars: "$23.40 saved vs your first month." Route cost comparison: "I-496 avg $3.80/trip vs Grand River avg $3.20/trip." Per-road-segment speed profiles from historical data. |

### v3 -- Sensor Fusion (Weeks 8-9)

| Week | Focus | Deliverable |
|------|-------|-------------|
| 8 | Wire sensors + vibration pipeline | Wire MPU-6050 to Pi I2C (under driver's seat). Wire INMP441 to Pi I2S GPIO (behind dash). Wire BME280 to Pi I2C (in armrest). Test each individually. STFT (256-point windows), Butterworth bandpass, statistical feature extraction (RMS, peak, kurtosis, crest factor). Mount quality validation: check coherence between phone vibration and OBD-derived engine frequency. |
| 9 | Audio MFCC + sensor fusion | INMP441 recording at 16kHz (downsampled). 13 MFCCs per 20ms frame, 10ms hop. Train initial autoencoder on "normal driving" vibration data. Multi-modal fusion: cross-reference vibration events with OBD speed/RPM to classify road vs vehicle origin. Compute orientation-independent magnitude sqrt(x^2 + y^2 + z^2). |

### v4 -- Portfolio Showcase (Weeks 10-12)

| Week | Focus | Deliverable |
|------|-------|-------------|
| 10 | PDF diagnostic reports | Jinja2 HTML templates + matplotlib charts + WeasyPrint PDF. Two-tier: customer-friendly summary (traffic-light per subsystem) + detailed technical section (DTCs, freeze frames, trend charts, spectrograms). |
| 11 | GNN health graph (stretch) | 8-node graph: Engine, Transmission, Exhaust, Cooling, Fuel, Electrical, Brakes, HVAC. 2-3 layer GCN, 64-dim embeddings. Train on desktop with PyTorch Geometric, export to ONNX/TFLite (~200KB). Graph overlay on 3D model (green/yellow/red nodes, highlighted fault propagation edges). |
| 12 | Plugin architecture + open source launch | BasePlugin ABC (initialize, process, shutdown). Dynamic discovery via importlib scanning `plugins/` dir. Vehicle profile YAML system (auto-detect via VIN). Circuit breaker for sensor failures. GitHub release: MIT license, README with architecture diagram, hardware BOM, safety section. Demo video (2 min). |

---

## 12. Project Structure

```
rune/
├── backend/
│   ├── main.py                     # FastAPI entry, WebSocket handler, static file serving
│   ├── config.py                   # Pydantic Settings, env vars, defaults
│   ├── obd_manager/
│   │   ├── __init__.py
│   │   ├── connection.py           # SafeOBDConnection (FIRST CODE WRITTEN)
│   │   ├── collector.py            # Async OBD data collector, PID polling loop
│   │   └── simulator.py            # Mock Honda Accord data with anomaly injection
│   ├── health/
│   │   ├── __init__.py
│   │   ├── scorer.py               # Health scoring: EWMA, Isolation Forest, trend regression
│   │   ├── rules.py                # Per-subsystem scoring rules
│   │   └── thresholds.py           # Honda Accord normal/warning/critical ranges
│   ├── fuel/
│   │   ├── __init__.py
│   │   ├── calculator.py           # Instant MPG, trip fuel integration
│   │   ├── budget.py               # Monthly budget tracker, pace projection
│   │   ├── routes.py               # GPS route fingerprinting, cost comparison
│   │   └── fillup.py               # Auto fill-up detection, fuel history logging
│   ├── vibration/                  # v3
│   │   ├── __init__.py
│   │   ├── processor.py            # STFT, CWT, Butterworth, feature extraction
│   │   └── anomaly.py              # Convolutional autoencoder inference (TFLite)
│   ├── audio/                      # v3
│   │   ├── __init__.py
│   │   ├── capture.py              # INMP441 I2S recording via pyaudio
│   │   └── classifier.py           # MFCC extraction + CNN classification
│   ├── coach/                      # v2
│   │   ├── __init__.py
│   │   ├── driver_style.py         # Random Forest: Eco/Normal/Aggressive
│   │   ├── eco_score.py            # Multi-dimensional efficiency scoring
│   │   └── route_learner.py        # GPS geofencing, braking patterns, route insights
│   ├── gnn/                        # v4 stretch
│   │   ├── __init__.py
│   │   ├── vehicle_graph.py        # 8-node subsystem graph definition
│   │   └── inference.py            # GCN inference via ONNX/TFLite
│   ├── reports/                    # v4
│   │   ├── __init__.py
│   │   ├── generator.py            # Jinja2 + WeasyPrint PDF generation
│   │   └── templates/              # HTML report templates
│   └── database/
│       ├── __init__.py
│       └── db.py                   # SQLite WAL: schema, migrations, queries
├── frontend/                       # React 19 + R3F 9 PWA
│   ├── src/
│   │   ├── components/
│   │   │   ├── three/              # R3F components: CarModel, SubsystemGlow, Bloom
│   │   │   ├── dashboard/          # HealthScore, SubsystemCards, StatusBar
│   │   │   └── fuel/               # InstantMPG, TripCost, BudgetTracker, FillHistory
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts     # WebSocket connection + reconnect logic
│   │   │   ├── useSensors.ts       # Web Generic Sensor API (60Hz accel)
│   │   │   └── useGeolocation.ts   # Web Geolocation API (~1Hz GPS)
│   │   ├── stores/
│   │   │   └── vehicleStore.ts     # zustand store: OBD data, health, fuel state
│   │   ├── App.tsx                 # Root component, layout
│   │   └── main.tsx                # Entry point
│   ├── public/
│   │   ├── models/                 # GLB car model files (Draco compressed)
│   │   └── manifest.json           # PWA manifest
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── plugins/                        # v4: community analysis modules
├── profiles/
│   └── honda_accord_2026_se.yaml   # Vehicle profile: PIDs, ranges, specs, tank capacity
├── deploy/
│   ├── rune.service            # systemd unit for auto-start on Pi boot
│   └── setup.sh                    # Pi setup script (WiFi AP, deps, OverlayFS)
└── tests/
    ├── replay_data/                # Captured real sensor data for regression tests
    ├── test_safe_obd.py            # SafeOBDConnection whitelist tests
    ├── test_health_scorer.py       # Health scoring with injected anomalies
    ├── test_fuel_calculator.py     # MPG calculation, fill-up detection
    └── test_simulator.py           # Simulator output validation
```

---

## 13. Success Metrics

| Metric | Target | How to Measure |
|--------|--------|---------------|
| End-to-end latency | <140ms | Timestamp delta: OBD poll to 3D viz update on phone |
| 3D frame rate | 30+ fps sustained | Chrome DevTools Performance tab on Pixel 6 Pro |
| Health score accuracy | Detects injected anomalies within 30s | Simulator anomaly injection test suite |
| Instant MPG accuracy | Within 5% of Honda dashboard avg MPG over same trip | Side-by-side comparison during real drives |
| Fill-up detection | Auto-detects >20% tank level jump | Test with real fill-up event |
| Battery drain (WiCAN Pro) | <1mA in sleep | WiCAN Pro spec. Verify with multimeter after 24hr park. |
| Calibration | Functional baselines after 500mi / 14 days | Health score stability (score variance <5 pts over 24hr normal driving) |
| Pi resource usage | <50% CPU, <1GB RAM sustained | `htop` monitoring during full operation |
| WebSocket reliability | <1% message drop over 1hr drive | Client-side sequence number gap detection |
| PWA load time | <3s from Pi WiFi | Chrome Lighthouse on Pixel 6 Pro |

---

## 14. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| 2026 Honda gateway blocks raw CAN signals | Medium | Low-Medium | WiCAN Pro raw CAN mode bypasses ELM327 layer. Manual protocol selection (ISO 15765-4, 11-bit, 500 kbaud). Standard Mode 01 PIDs are federally mandated and always work regardless. |
| PID 015E (fuel rate) not supported | Medium | Low | Fallback: calculate from MAF (PID 0110) via `fuel_rate_lph = (MAF_gps / 14.7 / 750) * 3600`. Less accurate but functional. Test on first real connection (Week 5). |
| React + Three.js mobile performance | Low | Low | Aggressive polygon budget (20-50K), selective bloom only, no shadows, pixel ratio cap at 2x. Mali-G78 MP20 handles optimized scenes at 30-45fps. |
| Pi thermal throttling (summer, car interior 60-80 C) | Medium | Medium | Aluminum heatsink case (Flirc/Argon NEO). Mount inside armrest (shaded from sun). BCM2711 rated to 85 C with auto-throttle. Pi 4 survived 3-4 months in Australian car at 44 C+. |
| Scope creep from enhancement layers | High | High | Strict v1/v2/v3/v4 tiering. Each version is independently shippable and demoable. Do NOT start v2 until v1 is solid and tested on real car. |
| python-obd async reliability | Medium | Medium | Circuit breaker pattern with exponential backoff. Auto-reconnect on disconnect. Structured JSON logging for debugging. Library is at 0.7.3 with slow maintenance cadence -- pin version. |
| Web Sensor API 60Hz cap for phone IMU | Low | Certain | 60Hz is confirmed Chromium hard cap. MPU-6050 chassis sensor at 8kHz via Pi is the primary vibration source. Phone IMU is supplementary. Native Kotlin companion app (~50 lines, streams to Pi via WebSocket) is escape hatch if 400Hz is ever needed. |
| SD card corruption from sudden power loss | Low | Low | OverlayFS makes root filesystem read-only. Witty Pi 4 detects ignition-off and triggers graceful `shutdown -h`. Industrial SD card rated to 85 C. 2,100+ power cut test showed zero corruption even without OverlayFS. |
| WiCAN Pro delivery delay | Low | Low | Already ordered, in stock. Weeks 1-4 are simulator-first development -- no hardware needed. CANable 2.0 clone ($25, Amazon) as USB SocketCAN fallback for development. |

---

## 15. Non-Goals

These are explicitly out of scope for Rune:

- **Writing to the ECU** -- Ever, for any reason, under any circumstances
- **ADAS data** -- Honda Sensing lives on a separate CAN bus, requires comma panda hardware
- **Cloud dependency** -- Everything runs locally. Only optional external call: GasBuddy API for gas prices.
- **Multi-vehicle support in v1** -- Honda Accord 2026 SE only. Vehicle profile system (v4) enables future expansion.
- **iOS** -- Pixel 6 Pro with Chrome PWA only
- **Federated learning** -- Cut from scope entirely
- **Real-time audio coaching** -- Driving coach is post-trip visual only. No audio cues while driving.
- **Hybrid/i-MMD features** -- Car is non-hybrid 1.5T. No regen braking levels, EV mode tracking, or ICE start counting.
- **Android Auto integration** -- Separate display ecosystem, not in scope
- **Photorealistic rendering** -- Tron/neon wireframe aesthetic, not PBR materials
