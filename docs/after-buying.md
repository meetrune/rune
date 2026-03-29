# After Buying -- Hardware Readiness Checklist

**Last updated: March 24, 2026 (Session 10)**
**Current status: v1 code-complete. 280 tests passing. PWA service worker built. Pi deployment scripts ready.**

This document tells you exactly what works, what doesn't, and what to do when you get the car.

---

## Quick Status

| Component | Status | Notes |
|-----------|--------|-------|
| SafeOBDConnection (safety gate) | READY | 57 tests. Read-only whitelist enforced. |
| OBDCollector (ELM327 over TCP) | READY | TCP connection, init sequence, PID polling, circuit breaker, reconnect. |
| OBD Simulator | READY | Honda L15BE thermal dynamics, anomaly injection, driving phases. |
| SQLite Database | READY | WAL mode, batch writes, 90-day retention cleanup. |
| Fuel Calculator | READY | MAF-based fuel rate, trip detection, fill-up detection (3-sample noise filter). |
| Health Scorer | READY | HalfSpaceTrees anomaly detection, Honda threshold scoring, EWMA. |
| WebSocket Streaming | READY | 10Hz producer, drift-compensated timing, multi-client broadcast. |
| FastAPI Backend | READY | Health check, trip API, debug dashboard, WebSocket endpoint. |
| React Frontend | READY | 4 screens: Telemetry 3D, Trace Matrix, Trip Summary, Settings. |
| 3D Car Visualization | READY | Interactive Honda Accord .glb model with zone markers. |
| PWA Service Worker | READY | Workbox precache (all assets + 3D model). Offline app shell. Auto-update. |
| systemd Service | READY | `deploy/rune.service` -- security hardened, auto-restart, resource limits. |
| Pi WiFi AP Setup | READY | `deploy/setup.sh` -- NetworkManager AP, DHCP leases, no-NAT dispatcher. |
| OverlayFS Prep | READY | Bind-mount unit for /var/lib/rune persistence through overlay. |
| Witty Pi 4 Integration | NOT BUILT | Graceful shutdown on ignition off. Build during hardware install. |
| Rune Launcher (Android) | NOT BUILT | Kiosk mode APK for Pixel. Build during deployment phase. |

---

## Your Pi Situation

**You have:** A 4-year-old Pi 4B running an old version of Ubuntu.
**Target OS:** Raspberry Pi OS Trixie (Debian 13) 64-bit Lite.

### You MUST reflash the SD card.

The deploy script, WiFi AP setup (NetworkManager), OverlayFS, and systemd service are all built for Trixie. Ubuntu Server uses different network stacks (netplan), different paths, and different package versions. Trying to make it work on old Ubuntu would mean rewriting all the deploy scripts and debugging compatibility issues with every package.

A fresh Trixie flash takes 10 minutes. Fighting Ubuntu compatibility takes hours.

### What you need before car delivery:

1. **A new SD card** (32GB+ Class A2 recommended) OR reuse the existing one
2. **Raspberry Pi Imager** on your Mac (free download)
3. **Ethernet cable or keyboard+monitor** for initial Pi setup (WiFi isn't configured yet)

---

## Day-by-Day Plan (Car Delivery in ~2 Days)

### Day 0: TODAY (before the car arrives)

**Goal: Pi ready to go, nothing left to do on delivery day.**

#### Step 1: Flash Trixie (10 min)

1. Download **Raspberry Pi Imager** on your Mac
2. Insert SD card
3. Choose: **Raspberry Pi OS Lite (64-bit)** -- make sure it says Trixie/Debian 13
4. Click the gear icon BEFORE flashing and set:
   - Hostname: `rune`
   - Enable SSH: yes
   - Username: `pi` (or whatever you want for your admin account)
   - Password: something you'll remember
   - WiFi: your home WiFi (temporary, just for initial setup)
   - Locale/timezone: your timezone
5. Flash it

#### Step 2: First boot + SSH in (5 min)

1. Put SD card in Pi, plug in power + ethernet (or use the home WiFi you configured)
2. Find the Pi on your network: `ping rune.local` or check your router
3. SSH in: `ssh pi@rune.local`

#### Step 3: Clone Rune and run setup (15 min)

```bash
# On the Pi:
sudo apt-get update && sudo apt-get upgrade -y

# Clone the repo
git clone https://github.com/meetrune/rune.git /tmp/rune-install

# Run the deployment script
cd /tmp/rune-install/deploy
sudo bash setup.sh --wifi-pass "YOUR_SECURE_PASSPHRASE"
```

The setup script does everything: creates user, installs venv, deploys code, configures WiFi AP, installs systemd service.

**You won't know the WiCAN Pro or Pixel MAC addresses yet** -- that's fine. Skip `--wican-mac` and `--pixel-mac` for now. Add them later after first boot with the real devices.

#### Step 4: Verify (5 min)

```bash
# Check the WiFi AP is broadcasting
nmcli con show Rune

# Start Rune in simulator mode (just to verify it works)
sudo systemctl start rune
sudo journalctl -u rune -f
# Should see: "Rune started: simulator_mode=True"

# From your Mac, connect to "Rune" WiFi
# Open browser: http://192.168.4.1:8080
# You should see the boot screen -> Telemetry 3D
```

If all that works, the Pi is ready. Turn it off and wait for the car.

### Day 1: CAR DELIVERY DAY

**Goal: WiCAN Pro installed, first connection verified, first real drive.**

#### Morning (before pickup/delivery)

1. **Charge the Pixel 6 Pro** to 100%
2. **Pack:**
   - Pi 4B (with SD card, ready to go)
   - Witty Pi 4 + CR2032 battery
   - YONHAN 12V plug
   - WiCAN Pro (still in box)
   - bbfly-B6 Y-Splitter
   - Miracase phone mount
   - Scotch Dual-Lock strips
   - USB-C cable for Pixel
   - A laptop (optional, for SSH troubleshooting)

#### At the car

**Step 1: Install WiCAN Pro (5 min)**

1. Find the OBD-II port (under the dash, driver's side, left of steering column)
2. Plug the Y-splitter into the OBD-II port
3. Plug WiCAN Pro into Y-splitter Port 1
4. Leave Port 2 empty (for dealer scanner access)
5. The WiCAN Pro LED should light up when you turn the ignition to ON

**Step 2: Change WiCAN Pro WiFi password (5 min)**

1. On your phone, connect to the WiCAN Pro's default AP (password: `@meatpi#`)
2. Open browser: `http://192.168.0.10` (WiCAN Pro web UI -- factory-fresh units use this IP; after setup, normal AP mode uses 192.168.80.1)
3. Go to WiFi settings
4. Switch from AP mode to **Station mode**
5. Connect it to the "Rune" network with the passphrase you set
6. Note the WiCAN Pro's MAC address while you're in the web UI
7. Save and reboot the WiCAN Pro

**Step 3: Power up the Pi (5 min)**

1. Plug YONHAN 12V plug into the armrest 12V outlet
2. Connect Witty Pi 4 to Pi via GPIO header
3. Connect YONHAN output to Witty Pi 4 input
4. Pi should boot (green LED flickering)
5. Secure Pi + Witty with Dual-Lock in armrest compartment

**Step 4: Connect Pixel and verify (5 min)**

1. Mount Pixel on Miracase vent mount
2. Connect Pixel to "Rune" WiFi
3. Open Chrome: `http://192.168.4.1:8080`
4. You should see the Rune boot screen

**Step 5: Switch to real OBD (2 min)**

SSH into the Pi from your phone or laptop:
```bash
ssh pi@192.168.4.1

# Edit the env file to disable simulator
sudo nano /etc/rune/rune.env
# Change RUNE_USE_SIMULATOR=false (should already be false)

# Restart the service
sudo systemctl restart rune

# Watch the logs
sudo journalctl -u rune -f
# Should see: "Connecting to WiCAN Pro at 192.168.4.100:3333"
# Then: "WiCAN Pro connection established and initialized"
# Then: PID data flowing
```

**Step 6: First drive verification**

```
BEFORE MOVING:
  [ ] Boot screen shows "Rune" then transitions
  [ ] 3D car renders on Telemetry screen
  [ ] Swipe to Trace Matrix -- waveforms alive
  [ ] RPM showing ~700 (warm idle) or ~1100 (cold)
  [ ] Coolant temp showing (20-40C if cold start)
  [ ] Battery voltage showing (12.4-14.8V)
  [ ] "Getting a feel for things" in Rune Voice (calibrating)

WHILE DRIVING:
  [ ] Speed reading matches speedometer (roughly)
  [ ] Instant MPG appears on hero strip
  [ ] Fuel cost accumulating
  [ ] Waveforms moving in real-time
  [ ] No lag or freezing on the Pixel

AFTER 5 MINUTES:
  [ ] Health scores appear (numbers, not "--")
  [ ] Voice changes to "All good. XX across the board"

AFTER STOPPING (engine off 10+ seconds):
  [ ] Trip end popup appears
  [ ] Trip shows in Trip Summary screen
  [ ] Distance/fuel/cost look reasonable
```

### Day 2+: Hardening

Once the basics work:

1. **Add static DHCP leases** (now that you know the MAC addresses):
   ```bash
   sudo nano /etc/NetworkManager/dnsmasq-shared.d/rune-leases.conf
   # Add: dhcp-host=XX:XX:XX:XX:XX:XX,wican,192.168.4.100,infinite
   # Add: dhcp-host=YY:YY:YY:YY:YY:YY,pixel,192.168.4.50,infinite
   sudo nmcli con down Rune && sudo nmcli con up Rune
   ```

2. **Enable OverlayFS** (SD card write protection):
   ```bash
   sudo raspi-config
   # Performance -> Overlay File System -> Enable
   # Then:
   echo 'overlayroot="tmpfs:recurse=0"' | sudo tee /etc/overlayroot.local.conf
   sudo update-initramfs -u
   sudo reboot
   ```

3. **Witty Pi 4 setup** (graceful shutdown):
   - Install Witty Pi software
   - Configure shutdown on 12V power loss (ignition off)
   - We'll build this together when you have the hardware in hand

4. **Pixel kiosk mode** (Rune Launcher APK):
   - Lock Pixel to Chrome in fullscreen
   - Auto-launch on boot
   - We'll build this APK together

---

## What Will Work Immediately (Day 1)

1. **OBD-II data collection** -- all 14 PIDs, TCP to WiCAN Pro, auto-reconnect
2. **Full data pipeline** -- 10Hz polling -> fuel calc -> health scoring -> WebSocket -> phone
3. **Fuel intelligence** -- instant MPG, trip cost, fill-up detection
4. **Health scoring** -- calibrates in ~5 min, then real scores for all 6 subsystems
5. **All 4 frontend screens** -- 3D telemetry, trace matrix, trip summary, settings
6. **Offline PWA** -- app shell cached, loads even if backend is slow to start

---

## What Needs Verification on Real Hardware

### PID Support (First Drive)

The OBDCollector polls all 14 PIDs automatically. Check the debug dashboard at `http://192.168.4.1:8080/debug` to see which ones return data vs NO DATA.

**Critical PIDs to verify:**
- `010C` (RPM) -- if this doesn't work, nothing works
- `010D` (speed) -- trip detection depends on this
- `0110` (MAF) -- fuel calculation depends on this
- `012F` (fuel level) -- fill-up detection depends on this

**Nice-to-have PIDs:**
- `013C` (catalyst temp) -- feeds exhaust health
- `015C` (oil temp) -- feeds engine health
- `0142` (battery voltage) -- feeds electrical health

**Expected to fail:**
- `015E` (fuel rate) -- NOT SUPPORTED on Honda, this is fine (we use MAF calculation)
- Mode 22 CVT temp -- unverified on 11th gen, auto-disables if unsupported

### Honda CAN Protocol

- `ATSP6` is mandatory and already in the init sequence
- NEVER use auto-detect on 2025-2026 Hondas
- This is already handled in the code

---

## Known Limitations

1. **ELM327 polling speed**: Full 14-PID cycle takes 2-3 seconds. WebSocket reuses last-known values between updates.
2. **Health calibration resets on restart**: ~5 minutes of "-1" scores after every backend restart.
3. **No DTC reading UI**: Backend can read DTCs (Mode 03) but no frontend screen for it yet.
4. **No route fingerprinting**: Trips tracked but not grouped by route (v2+).
5. **Mid-trip crash**: If backend crashes during a trip, up to 1 second of buffered readings are lost.

---

## Troubleshooting

### WiCAN Pro won't connect
- Check it's in Station mode (not AP mode) and on the "Rune" network
- Verify TCP: `nc -zv 192.168.4.100 3333` from the Pi
- Check WiCAN Pro firmware is latest (check github.com/meatpiHQ/wican-fw/releases)
- Try power cycling the WiCAN Pro (unplug from Y-splitter, wait 10s, replug)

### No OBD data after connection
- Check logs: `sudo journalctl -u rune -f`
- Look for "ELM327 init failed" -- means ATSP6 or another AT command failed
- Look for "Circuit breaker tripped" -- means too many consecutive PID failures
- Verify Y-splitter is fully seated in OBD-II port (click sound)

### Health scores stuck at -1
- Normal for first 5 minutes (3000-sample calibration)
- If it persists: check `/debug` dashboard for sensor data flow
- If sensors show 0s: OBD connection issue

### Frontend shows "Offline"
- Check Pixel is on Rune WiFi: Settings -> WiFi -> "Rune"
- Check backend: `curl http://192.168.4.1:8080/api/health`
- Try refreshing Chrome

### High CPU on Pi
- Normal: 15-30% sustained
- Check with `htop` on the Pi
- If >50%: check SQLite WAL size at `/api/debug`

### SD card corruption
- Enable OverlayFS (Day 2 task)
- The bind-mount keeps /var/lib/rune writable while protecting everything else
