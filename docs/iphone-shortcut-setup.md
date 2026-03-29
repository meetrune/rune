# Rune Sync -- iPhone Shortcut Setup Guide

**One-tap install:** https://www.icloud.com/shortcuts/f4a6153ab1e74db39e812da9b21f5a0f

This documents the complete iOS Shortcut that syncs data from the Rune Pi
to your iPhone and relays alerts via push notifications.

## Prerequisites

1. **ntfy app** installed from App Store (free, by binwiederhier)
2. Subscribe to topic `rune-deepu-alerts` in the ntfy app
3. iPhone connected to "Rune" WiFi network (Pi AP at 192.168.4.1)
4. Rune service running on Pi with intelligence layer enabled

## What This Shortcut Does

When your iPhone joins the Rune WiFi network:

1. Grabs any queued alerts from the Pi (battery warnings, maintenance due, anomalies)
2. Relays each alert to ntfy.sh as a push notification (via cellular, not WiFi)
3. Prepares a SHA-256 verified database backup on the Pi
4. Downloads the backup to iCloud Drive
5. Cleans up temporary files on the Pi

## Automation Trigger

- App: **Shortcuts** > **Automation** tab
- Trigger: **When iPhone joins "Rune"** WiFi network
- Ask Before Running: **OFF**
- Run Shortcut: **Rune Sync**

## Shortcut Actions (12 steps)

### Part 1: Alert Relay (Steps 1-7)

**Step 1: Get alerts from Pi**
- Action: **Get Contents of URL**
- URL: `http://192.168.4.1:8080/api/sync/alerts`
- Method: GET

**Step 2: Extract alerts list**
- Action: **Get Dictionary Value**
- Key: `alerts`
- Dictionary: Contents of URL (from Step 1)

**Step 3: Check if alerts exist**
- Action: **If**
- Input: Dictionary Value (from Step 2)
- Condition: **has any value**

**Step 4: Loop through alerts**
- Action: **Repeat with Each**
- Input: Dictionary Value (the alerts list from Step 2)

**Step 5: Extract message from each alert**
- Action: **Get Dictionary Value**
- Key: `message`
- Dictionary: Repeat Item

**Step 6: Send push notification via ntfy**
- Action: **Get Contents of URL**
- URL: `https://ntfy.sh/rune-deepu-alerts`
- Method: **POST**
- Headers:
  - Title: `Rune`
  - Priority: `high`
- Request Body: **File**
- File: Dictionary Value (the message from Step 5)

**Step 7: Close blocks**
- End Repeat
- Otherwise (empty)
- End If

### Part 2: Resilient Database Export (Steps 8-12)

**Step 8: Prepare export on Pi**
- Action: **Get Contents of URL**
- URL: `http://192.168.4.1:8080/api/export/prepare?chunk_size_mb=5`
- Method: **POST**
- Request Body: JSON (empty, no fields needed)

**Step 9: Extract session ID**
- Action: **Get Dictionary Value**
- Key: `session_id`
- Dictionary: Contents of URL (from Step 8)

**Step 10: Save session ID to variable**
- Action: **Set Variable**
- Variable Name: `sessionId`
- Input: Dictionary Value (from Step 9)

**Step 11: Build stream URL**
- Action: **URL**
- Value: `http://192.168.4.1:8080/api/export/stream/` + `sessionId` variable

**Step 12: Download the database**
- Action: **Get Contents of URL**
- URL: URL (from Step 11)
- Method: GET

**Step 13: Save to iCloud Drive**
- Action: **Save File**
- Input: Contents of URL (from Step 12)
- Destination: **iCloud Drive**
- Subpath: `Personal/Rune/data`
- Ask Where To Save: **OFF**
- Overwrite If File Exists: **OFF** (keeps history)

**Step 14: Build complete URL**
- Action: **URL**
- Value: `http://192.168.4.1:8080/api/export/complete/` + `sessionId` variable

**Step 15: Clean up export session**
- Action: **Get Contents of URL**
- URL: URL (from Step 14)
- Method: **POST**
- Request Body: JSON (empty)

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sync/alerts` | GET | Get queued alerts (battery, maintenance, anomalies) |
| `/api/export/prepare` | POST | Create SHA-verified backup, split into chunks |
| `/api/export/stream/{id}` | GET | Download the verified backup |
| `/api/export/complete/{id}` | POST | Clean up temp files on Pi |

## Resilience

| Scenario | What happens |
|----------|-------------|
| WiFi drops during alert fetch | Alerts stay on Pi, retried next connection |
| WiFi drops during DB download | Export session stays valid for 24 hours, retry next time |
| ntfy POST fails | Alert still on Pi (unsynced), retried next connection |
| Pi rebooted between prepare and stream | Session persists in DB, chunk files on disk |
| Phone reset | Reinstall ntfy, subscribe to topic, rebuild shortcut from this doc |

## ntfy Topic

- Topic: `rune-deepu-alerts`
- URL: `https://ntfy.sh/rune-deepu-alerts`
- The topic name acts as a password -- don't share it publicly
- Anyone with the topic name can send/receive messages

## Changing the ntfy Topic

If you want a more private topic name:
1. Change the topic in the ntfy app subscription
2. Update the URL in Step 6 of the shortcut
3. That's it -- ntfy creates topics on first use, no registration needed

## Troubleshooting

**Shortcut doesn't run automatically:**
- Check Automation tab: "When iPhone joins Rune" should point to "Rune Sync"
- "Ask Before Running" must be OFF
- iPhone WiFi must be ON and auto-join enabled for "Rune" network

**No push notifications:**
- Check ntfy app is installed and topic `rune-deepu-alerts` is subscribed
- Check ntfy app notification permissions in iOS Settings
- Test manually: open `https://ntfy.sh/rune-deepu-alerts` in Safari, type a message

**Export fails:**
- Pi must have enough disk space (2x the DB size)
- Check Pi is running: `curl http://192.168.4.1:8080/api/health`
- Session expires after 24 hours -- the shortcut creates a new one automatically

**DB file not appearing in iCloud:**
- Check Files app > iCloud Drive > Personal > Rune > data
- iCloud sync can take a few minutes
- Make sure iCloud Drive is enabled in Settings > Apple ID > iCloud
