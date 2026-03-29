# Rune Data Sync -- Pi to Mac via iPhone Bridge

Automatic pipeline: Pi collects data -> iPhone pulls it when you get in the car ->
iCloud syncs to Mac -> launchd runs analysis. Zero taps after setup.

## Architecture

```
IN CAR (Rune WiFi):
  Pi (192.168.4.1) -- collects OBD + raw CAN data
  WiCAN Pro (192.168.4.100) -- ELM327 on :3333, raw CAN on :35000
  Pixel 6 Pro -- displays live dashboard
  iPhone -- connects to Rune WiFi, keeps cellular for internet

AUTOMATIC BRIDGE:
  iPhone joins Rune WiFi -> iOS Shortcut fires silently
    -> GET http://192.168.4.1:8080/api/export
    -> saves rune-YYYY-MM-DD_HHMM.db to iCloud Drive

AT HOME:
  iCloud syncs .db to Mac (5-30 sec)
  launchd detects new file -> process_rune.py
    -> organizes into ~/Rune/data/YYYY/MM/
    -> runs analysis -> report in ~/Rune/reports/
```

## Folder Structure

```
iCloud Drive/
  Personal/
    Rune/
      data/              <- iOS Shortcut saves .db files here
        rune-2026-03-29_0914.db
        rune-2026-03-29_1742.db

~/Rune/                  <- local Mac storage (not in iCloud)
  data/
    latest.db            <- symlink to newest export
    2026/
      03/
        2026-03-29_0914_rune.db
        2026-03-29_1742_rune.db
      04/
        2026-04-01_0830_rune.db
  reports/
    2026-03-29_0914_analysis.txt
    2026-03-29_1742_analysis.txt
  logs/
    watcher.log
    watcher-stdout.log
    watcher-stderr.log
```

## Safety

Everything is READ-ONLY:
- ELM327 port (3333): SafeOBDConnection whitelist allows modes 01, 02, 03, 09, 22 only
- Raw CAN port (35000): Passive TCP listener. Never sends a single byte to the bus.
- Export endpoint (/api/export): SQLite backup API. Read-only copy of the database.

---

## Step 1: Pi dnsmasq Config (do this FIRST)

This tells iPhones "I'm a local-only network, don't try routing internet through me."
Without this, iOS might drop cellular when connected to Rune WiFi.

SSH into the Pi and edit dnsmasq config:

```bash
sudo nano /etc/dnsmasq.conf
```

Add this line (or find and uncomment it):

```
# Don't advertise a gateway -- tells phones to keep cellular for internet
dhcp-option=3
```

Restart dnsmasq:

```bash
sudo systemctl restart dnsmasq
```

Verify: Connect your iPhone to the Rune WiFi. You should still be able to
use Safari, Google Maps, and make calls over cellular. The WiFi icon may show
a "No Internet" badge but cellular data works normally.

---

## Step 2: iOS Shortcut -- "Rune Sync"

This runs automatically when your iPhone connects to the Rune WiFi network.
It downloads the full SQLite database from the Pi and saves it to iCloud Drive.

### Create the Automation

1. Open **Shortcuts** app -> **Automation** tab (bottom)
2. Tap **+** (top right) -> **Wi-Fi**
3. Choose network: **Rune** (must have connected at least once)
4. Leave on **Joined**
5. Tap **Next** -> **New Blank Automation**

### Add these actions in order:

**Action 1: Get Contents of URL**
- URL: `http://192.168.4.1:8080/api/export`
- Method: **GET**
- (No headers needed)

**Action 2: Format Date**
- Date: **Current Date**
- Format: **Custom** -> `yyyy-MM-dd_HHmm`

**Action 3: Save File**
- Input: tap the variable -> **Contents of URL** (output of Action 1)
- Ask Where to Save: **OFF**
- Destination: **iCloud Drive** > **Personal** > **Rune** > **data**
- Filename: type `rune-` then insert the **Formatted Date** variable then type `.db`
  - Result: `rune-2026-03-29_0914.db`

### Configure automation settings:

- **Ask Before Running**: **OFF** (this makes it fully silent)
- **Notify When Run**: **OFF** (optional, for stealth mode)

### Notes:

- First time: iOS will ask for Local Network permission for Shortcuts. Allow it.
- "No Internet Connection" on Rune WiFi is expected. Cellular handles internet.
- DB is typically 5-50 MB. Downloads in 1-3 seconds over local WiFi.
- You get all accumulated data since the last pull.

---

## Step 3: Mac Setup

### 3a: Create iCloud Drive folders

In **Finder** -> **iCloud Drive** -> open your **Personal** folder:
1. Create folder: **Rune**
2. Inside Rune, create folders: **data** and **reports**

Final path: `iCloud Drive / Personal / Rune / data /`

### 3b: Create local Rune directories

```bash
mkdir -p ~/Rune/{data,reports,logs}
```

### 3c: Install the launchd watcher

```bash
# macOS Tahoe 26+: install as LaunchDaemon (TCC blocks LaunchAgent Python)
sudo cp mac/rune-watcher/com.rune.watcher.plist /Library/LaunchDaemons/
sudo launchctl bootstrap system /Library/LaunchDaemons/com.rune.watcher.plist
```

### 3d: Verify

Drop a test file into the iCloud data folder from Finder and check:
```bash
cat ~/Rune/logs/watcher.log
```

You should see the watcher trigger and process the file.

### Uninstall

```bash
sudo launchctl bootout system/com.rune.watcher
sudo rm /Library/LaunchDaemons/com.rune.watcher.plist
```

---

## Step 4: Test the Full Pipeline

1. Start the Pi backend:
   ```bash
   cd pi && .venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
   ```
2. Connect your iPhone to Rune WiFi
3. Wait for the Shortcut to fire (check Shortcuts -> Automation run history)
4. Check iCloud Drive -> Personal -> Rune -> data for the .db file
5. On your Mac, check:
   - `~/Rune/data/` for the organized export
   - `~/Rune/reports/` for the analysis
   - `~/Rune/logs/watcher.log` for the log

---

## What the Mac Receives

The full `rune.db` SQLite database with 5 tables:

| Table | Contents | Rate |
|-------|----------|------|
| `sensor_readings` | 14 OBD PIDs: RPM, speed, coolant, load, MAF, fuel trims, throttle, catalyst temp, oil temp, battery voltage, intake temp, MAP + Pi sensors | 10 Hz |
| `can_frames` | Raw CAN bus: every frame on the powertrain F-CAN bus with CAN ID, data bytes, timestamps | Bus rate (~100s/sec) |
| `trips` | Trip records: distance, fuel used, cost, MPG, detailed stats JSON | Per trip |
| `fillups` | Fill-up events: before/after fuel level, estimated gallons, cost | Per fill-up |
| `health_scores` | Health scores: overall + engine, transmission, fuel, cooling, exhaust, electrical | 1 Hz |

### Quick queries on Mac

```python
import sqlite3
from pathlib import Path

conn = sqlite3.connect(str(Path.home() / "Rune" / "data" / "latest.db"))
conn.row_factory = sqlite3.Row

# All trips
trips = conn.execute(
    "SELECT * FROM trips WHERE end_time IS NOT NULL ORDER BY start_time DESC"
).fetchall()

# Battery voltage trend
voltages = conn.execute(
    "SELECT ts, battery_v FROM sensor_readings ORDER BY ts DESC LIMIT 1000"
).fetchall()

# Raw CAN frames for wheel speed (CAN ID 0x1D0 = 464 decimal)
wheels = conn.execute(
    "SELECT ts, data FROM can_frames WHERE can_id = 464 ORDER BY ts DESC LIMIT 100"
).fetchall()

# All unique CAN IDs your Accord broadcasts
unique = conn.execute(
    "SELECT DISTINCT can_id FROM can_frames ORDER BY can_id"
).fetchall()
print([f"0x{r['can_id']:03X}" for r in unique])
```

---

## Data Volumes

| What | Per day driving | Per month | 90-day peak |
|------|----------------|-----------|-------------|
| OBD sensor readings (10Hz) | ~400 KB | ~12 MB | ~36 MB |
| Raw CAN frames | ~5-20 MB | ~150-600 MB | ~0.5-1.8 GB |
| Trips + fillups + health | <100 KB | <3 MB | <9 MB |
| **Total** | ~5-20 MB | ~165-615 MB | **~0.5-2 GB** |

The 90-day auto-cleanup keeps the DB manageable. Your M3 Max handles this easily.
The iCloud data folder is cleaned to keep only the 2 most recent exports.
