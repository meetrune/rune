# After Buying -- Hardware Readiness Checklist

**Last updated: March 24, 2026**
**Current status: v1 complete on simulator, 272 backend tests passing, 4 frontend screens shipped.**

This document tells you exactly what works, what doesn't, and what needs to be built when you plug in the real hardware.

---

## Quick Status

| Component | Status | Notes |
|-----------|--------|-------|
| SafeOBDConnection (safety gate) | READY | 57 tests. Read-only whitelist enforced. |
| OBDCollector (ELM327 over TCP) | READY | TCP connection, init sequence, PID polling, circuit breaker. Tested with mocks. |
| OBD Simulator | READY | Honda L15BE thermal dynamics, anomaly injection, driving phases. |
| SQLite Database | READY | WAL mode, batch writes, 90-day retention cleanup. |
| Fuel Calculator | READY | MAF-based fuel rate, trip detection, fill-up detection. |
| Health Scorer | READY | HalfSpaceTrees anomaly detection, Honda threshold scoring, EWMA. |
| WebSocket Streaming | READY | 10Hz producer, drift-compensated timing, multi-client broadcast. |
| FastAPI Backend | READY | Health check, trip API, debug dashboard, WebSocket endpoint. |
| React Frontend | READY | 4 screens: Telemetry 3D, Trace Matrix, Trip Summary, Settings. |
| 3D Car Visualization | READY | Interactive Honda Accord .glb model with zone markers. |
| PWA | PARTIAL | Manifest configured, icons exist. No service worker for offline yet. |
| Pi WiFi AP | NOT BUILT | Need to configure hostapd on Pi. |
| OverlayFS | NOT BUILT | Need to configure read-only root filesystem. |
| Witty Pi 4 Integration | NOT BUILT | Graceful shutdown on ignition off. |
| Rune Launcher (Android) | NOT BUILT | Kiosk mode APK for Pixel. |

---

## What Will Work Immediately (Day 1)

### Backend on Pi

1. **OBD-II data collection** -- `OBDCollector` is built and tested for WiCAN Pro TCP:3333. It will:
   - Connect via TCP to 192.168.4.100:3333
   - Run ELM327 init: ATZ, ATE0, ATL0, ATS0, ATSP6 (mandatory), ATSH7E0, ATCRA7E8
   - Poll all 14 confirmed Mode 01 PIDs (RPM, speed, coolant, load, throttle, MAF, fuel trims, fuel level, catalyst, oil, battery, intake temp, MAP)
   - Attempt Mode 22 CVT temp (auto-disables on negative UDS response)
   - Reconnect on disconnect with exponential backoff (1s -> 30s max)
   - Circuit breaker: 5 consecutive failures -> 10s cooldown
   - Stale data warning if PID not updated in 5s

2. **Data pipeline** -- 10Hz polling -> FuelCalculator -> HealthScorer -> WebSocket broadcast + DB writes. This entire pipeline is already built and tested.

3. **Fuel intelligence** -- Trip detection (start on speed > 5 kph, end on RPM = 0 for 10s), fuel accumulation from MAF, fill-up detection (>20% tank jump), cost tracking.

4. **Health scoring** -- Calibrates over first ~5 minutes (3000 samples), then provides real health scores. HalfSpaceTrees anomaly detection + Honda-specific threshold scoring.

5. **Frontend** -- All 4 screens work. Just needs the phone browser pointed at the Pi's IP.

### To Switch from Simulator to Real Hardware

**One config change:**
```bash
# Set environment variable before starting
export RUNE_USE_SIMULATOR=false

# Or edit the default in config.py:
# use_simulator: bool = False  (currently True for dev)
```

That's it. The `lifespan` function in `main.py` checks `settings.use_simulator` and creates either `SimulatedCollector` or `OBDCollector`.

---

## What Needs Verification on Real Hardware

### PID Support (Week 5 Checklist)

Run these tests with the WiCAN Pro connected to the 2026 Accord:

```
1. Send 0100 / 0120 / 0140 / 0160 for PID support bitmasks
2. Test each of the 14 confirmed PIDs individually:
   - 0104 (load) -> expect 41 04 XX
   - 0105 (coolant) -> expect 41 05 XX
   - 0106 (STFT B1) -> expect 41 06 XX
   - 0107 (LTFT B1) -> expect 41 07 XX
   - 010B (MAP) -> expect 41 0B XX
   - 010C (RPM) -> expect 41 0C XX XX
   - 010D (speed) -> expect 41 0D XX
   - 010F (intake temp) -> expect 41 0F XX
   - 0110 (MAF) -> expect 41 10 XX XX
   - 0111 (throttle) -> expect 41 11 XX
   - 012F (fuel level) -> expect 41 2F XX
   - 013C (catalyst) -> expect 41 3C XX XX
   - 0142 (voltage) -> expect 41 42 XX XX
   - 015C (oil temp) -> expect 41 5C XX
3. Test 015E (fuel rate) -> expect NO DATA or 7F (NOT SUPPORTED on Honda)
4. Test Mode 22 CVT temp: send "22 22 01" -> parse byte 27 as (byte - 40)
   WARNING: Byte offset is confirmed on 10th gen only. May be different on 11th gen (2026).
5. Log TRIP_FUEL_CONSUMED counter at CAN ID 0x324 over a known distance
```

### Honda CAN Protocol

- **MUST use manual protocol selection**: `ATSP6` (ISO 15765-4, 11-bit, 500 kbaud)
- **NEVER use auto-detect**: 2025-2026 Hondas have enhanced CAN bus security that causes auto-detect failures
- The OBDCollector already sends ATSP6 in its init sequence -- verified in code

### Mode 22 CVT Fluid Temperature

- **Status: UNVERIFIED on 11th gen (2026)**
- Byte offset is confirmed on 10th gen Accords only
- The code auto-disables Mode 22 if the UDS response is negative (NAK)
- If it works: CVT temp feeds into transmission health score
- If it doesn't: transmission health defaults to 100 (no data = assume healthy)
- No safety risk either way -- it's read-only

---

## What Is NOT Built Yet

### Must Build Before First Real Drive

| Feature | Effort | Priority | Notes |
|---------|--------|----------|-------|
| Pi WiFi AP "Rune" (192.168.4.1) | ~1h | P0 | hostapd + dnsmasq config |
| DB path for Pi: `/var/lib/rune/rune.db` | 5min | P0 | Create dir with correct permissions |
| systemd service for Rune backend | ~30min | P0 | Auto-start on boot |
| `RUNE_USE_SIMULATOR=false` | 1min | P0 | Switch to real OBD |

### Should Build Before Daily Use

| Feature | Effort | Priority | Notes |
|---------|--------|----------|-------|
| WiCAN Pro WiFi password change | 5min | P1 | Default is `@meatpi#` -- CHANGE IT |
| OverlayFS (read-only root) | ~2h | P1 | Prevents SD card corruption on power loss |
| Witty Pi 4 graceful shutdown | ~2h | P1 | RTC + shutdown on ignition off |
| PWA service worker (offline) | ~2h | P1 | Frontend works when WebSocket disconnects |
| Rune Launcher APK | ~4h | P2 | Kiosk mode for Pixel 6 Pro |
| CI/CD pipeline (GitHub Actions) | ~2h | P2 | lint + type check + unit tests on push |

### Future Phases (Not Needed for v1)

| Feature | Phase | Notes |
|---------|-------|-------|
| Driving style classification | v2 | Random Forest on OBD features |
| Eco-score | v2 | Post-trip scoring 0-100 |
| MPU-6050 IMU (vibration) | v3 | I2C sensor under driver's seat |
| INMP441 microphone (engine audio) | v3 | I2S sensor behind dash |
| BME280 (cabin temp/humidity) | v3 | I2C sensor in armrest |
| LSTM autoencoder | v3 | TFLite inference on Pi |
| PDF diagnostic reports | v4 | Jinja2 + matplotlib + WeasyPrint |
| Mac training workstation | v5 | MLX training, Prophet forecasting |

---

## Known Limitations

### Hardware Limitations

1. **ELM327 polling speed**: 2-5 PIDs/second in normal mode, ~7/s with fast timeout. Full 14-PID cycle takes 2-3 seconds. WebSocket still runs at 10Hz but reuses last-known values until updated.

2. **Latency budget**: OBD poll (~200ms per PID) + processing (~1ms) + WebSocket (~10ms) = end-to-end ~140ms. Within budget.

3. **Pi 4B CPU**: Health scorer + SQLite writes + WebSocket broadcast at 10Hz should stay under 30% CPU. Anomaly detection is O(depth * n_trees) per sample = ~25 * 6 = 150 node traversals, sub-millisecond.

4. **Pi 4B RAM**: Entire Python process should use ~200-400MB. OS ~150MB. Plenty of headroom on 4GB.

### Software Limitations

1. **No offline frontend**: If the WebSocket drops, the frontend shows "Offline" but has no cached data. Adding a service worker would fix this.

2. **No persistent trips across restarts**: Trips are in SQLite, but the in-memory trip state resets on backend restart. If the backend crashes mid-trip, that trip data is lost (only the buffered-but-not-yet-flushed readings, max 1 second worth).

3. **Health calibration resets on restart**: The HalfSpaceTrees needs ~5 minutes to calibrate. Every backend restart means 5 minutes of "-1" health scores.

4. **No DTC reading UI**: The backend can read DTCs (Mode 03 is allowed), but there's no frontend screen for it yet.

5. **No route fingerprinting**: Fuel intelligence tracks trips but doesn't group by route yet (v2+).

6. **Float precision on fuel costs**: Trip costs use Python float math. For a $100 trip this is fine (~$0.01 precision). Not financial-grade but adequate for fuel tracking.

---

## First Drive Checklist

```
BEFORE LEAVING THE DRIVEWAY:
  [ ] WiCAN Pro installed in OBD-II Y-splitter port 1
  [ ] WiCAN Pro WiFi password changed from default
  [ ] WiCAN Pro connected to Pi WiFi AP "Rune"
  [ ] Pi running in armrest with Witty Pi 4
  [ ] Pi WiFi AP "Rune" at 192.168.4.1 broadcasting
  [ ] Pixel 6 Pro connected to "Rune" WiFi
  [ ] Chrome open to http://192.168.4.1:8080
  [ ] Rune backend running (systemd service)
  [ ] RUNE_USE_SIMULATOR=false
  [ ] BootScreen shows "Rune" then transitions to Telemetry
  [ ] 3D car renders, zone markers appear
  [ ] "Getting a feel for things" appears in Rune Voice

DURING FIRST 5 MINUTES:
  [ ] Health scores show "--" (calibrating)
  [ ] Sensor data appears in Trace Matrix (live waveforms)
  [ ] Coolant temp climbing (cold start warmup)
  [ ] RPM settles from ~1100 to ~700 as engine warms
  [ ] Speed reads correctly when you move

AFTER 5 MINUTES:
  [ ] Health scores appear (0-100, not -1)
  [ ] "All good. XX across the board" appears in voice
  [ ] Fuel cost accumulating on hero strip
  [ ] Instant MPG showing while driving
  [ ] Cost per mile showing while driving

AFTER FIRST TRIP:
  [ ] Trip end popup appears when engine off for 10s
  [ ] Trip appears in Trip Summary screen
  [ ] Distance, fuel, cost, avg MPG look reasonable
  [ ] Data persists in SQLite (survives backend restart)

MODES TO VERIFY:
  [ ] 0104 (load) -- expect 15-40% idle, higher while driving
  [ ] 0105 (coolant) -- expect 20-40C cold start, 85-95C warm
  [ ] 0106 (STFT) -- expect ±3% normal, ±5% max
  [ ] 0107 (LTFT) -- expect ±2% on new car
  [ ] 010C (RPM) -- expect 700-750 warm idle
  [ ] 010D (speed) -- compare to speedometer
  [ ] 0110 (MAF) -- expect 2-4 g/s idle, 10-30 g/s highway
  [ ] 0142 (voltage) -- expect 12.4-14.8V (Honda ELD cycles)
  [ ] 015E (fuel rate) -- expect NO DATA (confirm not supported)
  [ ] Mode 22 CVT temp -- expect response or NAK (either is fine)
```

---

## Troubleshooting

### WiCAN Pro won't connect
- Verify it's on the Rune WiFi network (not its own AP mode)
- Check TCP port 3333 is reachable: `nc -zv 192.168.4.100 3333`
- Try firmware update to v4.40+

### No OBD data after connection
- **Most common**: auto-protocol detection failed. The code sends `ATSP6` which is correct for Honda.
- Try `ATZ` reset, then manual init sequence
- Check that the Y-splitter is properly seated in the OBD-II port

### Health scores stuck at -1
- Normal for first 5 minutes (calibration phase)
- If it persists: check that sensor data is actually flowing (debug dashboard at /debug)

### Frontend shows "Offline"
- Check Pixel is on the Rune WiFi network
- Check backend is running: `curl http://192.168.4.1:8080/api/health`
- WebSocket URL is auto-detected from page URL

### High CPU on Pi
- Expected: 15-30% sustained during normal operation
- If higher: check SQLite WAL size (`/api/debug` shows DB size)
- Health scorer anomaly detection should be sub-millisecond per tick

### SD card corruption
- Enable OverlayFS (read-only root) before daily use
- DB path should be on a writable partition with proper wear leveling
- The cleanup task runs hourly, keeps DB under control
