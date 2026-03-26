# Advanced Diagnostics Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build all 19 advanced diagnostic features for Rune's engineering dashboard -- topology animations, sparklines, interactive panels, log viewer, config viewer, manual controls. Production quality, no MVPs.

**Architecture:** The diagnostics dashboard is a standalone HTML file (`diagnostics.html`) with inline CSS/JS, served at `/diagnostics`. It fetches data from FastAPI endpoints and streams live data via WebSocket. New features add 9 backend endpoints to `backend/main.py` and enhance the HTML/CSS/JS in `diagnostics.html`. Backend endpoints also get new modules: `backend/api/system.py`, `backend/api/logs.py`, `backend/api/controls.py`.

**Tech Stack:** Python 3.14 (FastAPI, aiosqlite, pydantic), vanilla JS (no React -- this is the engineering dashboard), SVG animations, Canvas API for sparklines.

---

## File Structure

### New Files
- `backend/api/__init__.py` -- API sub-package init
- `backend/api/system.py` -- System info endpoint (CPU/RAM/disk/temp/uptime)
- `backend/api/logs.py` -- Log viewer endpoint (ring buffer + query)
- `backend/api/controls.py` -- Manual control endpoints (checkpoint, recalibrate, restart)

### Modified Files
- `backend/main.py` -- Add 9 new route handlers, import new modules, store producer task ref on app.state
- `backend/database/db.py` -- Add `get_wal_size()`, `get_last_vacuum_time()`, `force_checkpoint()` methods
- `backend/diagnostics.py` -- Add `run_integration_test()` function
- `backend/health/scorer.py` -- Add `reset_calibration()` method
- `diagnostics.html` -- All 19 frontend features (CSS + HTML + JS)

### Test Files
- `tests/test_api_system.py` -- System info endpoint tests
- `tests/test_api_logs.py` -- Log viewer endpoint tests
- `tests/test_api_controls.py` -- Manual control endpoint tests
- `tests/test_api_diagnostics_endpoints.py` -- Integration test, health-trend, config, OBD test endpoints
- `tests/test_diagnostics_advanced.py` -- Extended diagnostics tests

---

## Batch 1: Backend Endpoints (9 endpoints)

### Task 1: GET /api/health-trend endpoint

**Files:**
- Modify: `backend/main.py`
- Test: `tests/test_api_diagnostics_endpoints.py`

Already have `db.get_health_trend()`. Just need the route.

- [ ] **Step 1: Write test**
```python
@pytest.mark.anyio
async def test_health_trend_endpoint(client):
    resp = await client.get("/api/health-trend?hours=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "scores" in data
    assert isinstance(data["scores"], list)
```

- [ ] **Step 2: Add route to main.py**
```python
@app.get("/api/health-trend")
async def health_trend(hours: int = Query(default=1, ge=1, le=168)) -> JSONResponse:
    db: RuneDatabase = app.state.db
    scores = await db.get_health_trend(hours=hours)
    return JSONResponse({"scores": scores, "hours": hours})
```

- [ ] **Step 3: Run tests, verify pass**
- [ ] **Step 4: Commit**

---

### Task 2: GET /api/system endpoint

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/system.py`
- Modify: `backend/main.py`
- Test: `tests/test_api_system.py`

Research: Use `psutil`-free approach -- read `/proc/stat`, `/proc/meminfo`, `/proc/uptime` on Linux, fallback to `platform` + `os` on macOS for dev. This is a Pi-targeted app so /proc is the production path.

- [ ] **Step 1: Write test**
- [ ] **Step 2: Implement `get_system_info()` in `backend/api/system.py`**

Returns: cpu_percent, ram_total_mb, ram_used_mb, ram_percent, disk_total_mb, disk_used_mb, disk_percent, cpu_temp_c, uptime_seconds, python_version, os_version, hostname

- [ ] **Step 3: Add route to main.py**
```python
@app.get("/api/system")
async def system_info() -> JSONResponse:
    from backend.api.system import get_system_info
    return JSONResponse(await get_system_info())
```

- [ ] **Step 4: Run tests, verify pass**
- [ ] **Step 5: Commit**

---

### Task 3: POST /api/obd/test endpoint

**Files:**
- Modify: `backend/main.py`
- Test: `tests/test_api_diagnostics_endpoints.py`

Sends ATI command to WiCAN Pro, returns ELM327 version string. In simulator mode, returns simulated response.

- [ ] **Step 1: Write test**
- [ ] **Step 2: Add route** -- uses `app.state.collector` to check if simulator, returns mock ATI response or real one
- [ ] **Step 3: Run tests, verify pass**
- [ ] **Step 4: Commit**

---

### Task 4: POST /api/test/integration endpoint

**Files:**
- Modify: `backend/diagnostics.py` -- add `run_integration_test()`
- Modify: `backend/main.py`
- Test: `tests/test_api_diagnostics_endpoints.py`

Deep integration test: generate snapshot -> write to DB -> read back -> verify -> measure timing.

- [ ] **Step 1: Write test**
- [ ] **Step 2: Implement `run_integration_test()` in diagnostics.py**
- [ ] **Step 3: Add route to main.py**
- [ ] **Step 4: Run tests, verify pass**
- [ ] **Step 5: Commit**

---

### Task 5: GET /api/logs endpoint

**Files:**
- Create: `backend/api/logs.py`
- Modify: `backend/main.py`
- Test: `tests/test_api_logs.py`

Research: Use Python's logging module with a custom `MemoryHandler` or ring buffer handler that stores last N log records in memory. Query by level, return as JSON array.

- [ ] **Step 1: Write test**
- [ ] **Step 2: Implement `RuneLogBuffer` -- custom logging.Handler with a deque(maxlen=500)**
- [ ] **Step 3: Install handler at startup in main.py**
- [ ] **Step 4: Add route**
```python
@app.get("/api/logs")
async def get_logs(
    lines: int = Query(default=50, ge=1, le=500),
    level: str = Query(default="DEBUG"),
) -> JSONResponse:
    from backend.api.logs import get_recent_logs
    return JSONResponse({"logs": get_recent_logs(lines=lines, min_level=level)})
```

- [ ] **Step 5: Run tests, verify pass**
- [ ] **Step 6: Commit**

---

### Task 6: GET /api/config endpoint

**Files:**
- Modify: `backend/main.py`
- Test: `tests/test_api_diagnostics_endpoints.py`

Returns all RuneSettings values as JSON. Read-only. Redact any sensitive fields (passwords).

- [ ] **Step 1: Write test**
- [ ] **Step 2: Add route** -- `settings.model_dump()` with field filtering
- [ ] **Step 3: Run tests, verify pass**
- [ ] **Step 4: Commit**

---

### Task 7: POST /api/control/* endpoints (3 control actions)

**Files:**
- Create: `backend/api/controls.py`
- Modify: `backend/main.py`
- Modify: `backend/database/db.py` -- add `force_checkpoint()`
- Modify: `backend/health/scorer.py` -- add `reset_calibration()`
- Test: `tests/test_api_controls.py`

Three control endpoints:
1. `POST /api/control/checkpoint` -- force WAL checkpoint
2. `POST /api/control/recalibrate` -- reset health scorer calibration
3. `POST /api/control/restart-producer` -- restart the producer loop

- [ ] **Step 1: Write tests for all 3**
- [ ] **Step 2: Add `force_checkpoint()` to db.py**
- [ ] **Step 3: Add `reset_calibration()` to scorer.py**
- [ ] **Step 4: Implement restart-producer (cancel task, re-create)**
- [ ] **Step 5: Add all 3 routes to main.py**
- [ ] **Step 6: Run tests, verify pass**
- [ ] **Step 7: Commit**

---

## Batch 2: Frontend -- Topology Improvements (Features 1-5)

### Task 8: Click device node -> expand detailed info panel

**Files:**
- Modify: `diagnostics.html`

Click any topology node to expand a detail panel below the SVG showing device-specific info:
- Pi: CPU/RAM/disk (from /api/system), Python version, uptime
- WiCAN: firmware version, connection uptime, PID poll rate (from /api/debug)
- Witty Pi: Vin/Vout/Iout, temperature, action reason (from /api/debug)
- Phone: WebSocket message count, latency, connected duration (from JS state)
- Honda: OBD protocol, simulator status, supported PIDs (from /api/debug)

- [ ] **Step 1: Research -- best UX patterns for expandable panels in SVG-heavy layouts**
- [ ] **Step 2: Add CSS for `.topo-detail-panel` (slide-down, dark card)**
- [ ] **Step 3: Add HTML container below topology SVG for detail panel**
- [ ] **Step 4: Add JS click handlers on each topo-node-rect**
- [ ] **Step 5: Fetch device-specific data and render in panel**
- [ ] **Step 6: Test all 5 device panels open/close/toggle**
- [ ] **Step 7: Commit**

---

### Task 9: Animated packet dots on bezier paths

**Files:**
- Modify: `diagnostics.html`

SVG animateMotion with mpath. Multiple dots staggered by begin offset. Speed reflects actual data rate.

- [ ] **Step 1: Research -- SVG animateMotion with mpath for packet visualization**
- [ ] **Step 2: Add SVG circle elements with animateMotion on each connection path**
- [ ] **Step 3: Stagger 3 dots per path with different begin offsets**
- [ ] **Step 4: JS function to adjust animation duration based on actual message rate**
- [ ] **Step 5: Test visual appearance, verify dots follow bezier curves**
- [ ] **Step 6: Commit**

---

### Task 10: Connection lines pulse when data flowing, dim when stale

**Files:**
- Modify: `diagnostics.html`

- [ ] **Step 1: Add CSS animations for pulsing glow (opacity cycle) and dim state**
- [ ] **Step 2: Track last-message-time per connection in JS**
- [ ] **Step 3: On each WS message, mark connection as "active" (full opacity + glow)**
- [ ] **Step 4: 1Hz timer: if no data for 5s+, dim to 20% opacity**
- [ ] **Step 5: Red flash animation on connection drop with timestamp text**
- [ ] **Step 6: Test all states: active, stale, disconnected**
- [ ] **Step 7: Commit**

---

### Task 11: Hover connection line -> throughput tooltip

**Files:**
- Modify: `diagnostics.html`

- [ ] **Step 1: Track messages/sec, bytes/sec, avg latency in JS from WS message timestamps**
- [ ] **Step 2: Add CSS for `.topo-tooltip` (positioned tooltip, dark card)**
- [ ] **Step 3: Add invisible wider hit-area path over each connection line**
- [ ] **Step 4: On mouseenter: show tooltip with throughput stats**
- [ ] **Step 5: On mouseleave: hide tooltip**
- [ ] **Step 6: Test tooltip positioning, verify stats are accurate**
- [ ] **Step 7: Commit**

---

### Task 12: Red flash on connection drop with timestamp (Feature 5)

Already covered in Task 10 step 5. This task adds the "Last connected: HH:MM:SS" text near the line.

- [ ] **Step 1: Add SVG text element near each connection line for last-connected timestamp**
- [ ] **Step 2: Show/hide based on connection state**
- [ ] **Step 3: CSS `@keyframes flash-red` animation**
- [ ] **Step 4: Test by disconnecting WS, verify timestamp appears**
- [ ] **Step 5: Commit**

---

## Batch 3: Frontend -- Data Visualization (Features 6-11)

### Task 13: Per-sensor 60-second sparkline charts (Feature 6)

**Files:**
- Modify: `diagnostics.html`

Tiny canvas behind each sensor value (60px tall). 60-sample ring buffer per sensor at 1Hz. Color matches sensor severity.

- [ ] **Step 1: Research -- efficient Canvas sparkline rendering at 60fps**
- [ ] **Step 2: Add small canvas element inside each sensor-cell**
- [ ] **Step 3: Implement ring buffer (Float32Array, size 60) per sensor**
- [ ] **Step 4: On each WS message (throttled to 1Hz): push value, redraw canvas**
- [ ] **Step 5: Color sparkline based on severity (green/amber/red)**
- [ ] **Step 6: Test with live WS data, verify smooth rendering**
- [ ] **Step 7: Commit**

---

### Task 14: Historical health trend sparkline (Feature 7)

**Files:**
- Modify: `diagnostics.html`

Small sparkline next to the health score in the status banner, showing 1-hour trend from GET /api/health-trend.

- [ ] **Step 1: Add canvas element to status banner area**
- [ ] **Step 2: Fetch /api/health-trend?hours=1 on page load and every 60s**
- [ ] **Step 3: Render sparkline of overall health scores**
- [ ] **Step 4: Show trend arrow (up/down/stable)**
- [ ] **Step 5: Test with real data from scorer**
- [ ] **Step 6: Commit**

---

### Task 15: Trip history panel (Feature 8)

**Files:**
- Modify: `diagnostics.html`

Collapsible panel showing recent trips from existing GET /api/trips.

- [ ] **Step 1: Add "Trips" nav link and section**
- [ ] **Step 2: CSS for trip cards (distance, cost, MPG, duration)**
- [ ] **Step 3: Fetch /api/trips on load, render trip list**
- [ ] **Step 4: Color-code MPG numbers (green > EPA, amber near, red below)**
- [ ] **Step 5: Test with trip data, verify collapsible behavior**
- [ ] **Step 6: Commit**

---

### Task 16: Thermal manager visual gauge (Feature 9)

**Files:**
- Modify: `diagnostics.html`

Show current thermal band as a visual thermometer/color bar. Show CPU temp, armrest temp, rate of change, startup ambient.

- [ ] **Step 1: Add thermal section below topology**
- [ ] **Step 2: SVG or CSS thermometer gauge with 5 bands (GREEN-DANGER)**
- [ ] **Step 3: Show current CPU temp, armrest temp, rates, startup ambient from /api/debug**
- [ ] **Step 4: Animate gauge fill based on current thermal state**
- [ ] **Step 5: Test all 5 thermal states visually**
- [ ] **Step 6: Commit**

---

### Task 17: Database growth trend (Feature 10)

**Files:**
- Modify: `diagnostics.html`

Track DB size over time, show trend line.

- [ ] **Step 1: Sample DB size from /api/debug every 15s during diagnostics page open**
- [ ] **Step 2: Store samples in JS array (max 240 = 1 hour)**
- [ ] **Step 3: Render small canvas sparkline of DB size over time**
- [ ] **Step 4: Show current size, growth rate, WAL size**
- [ ] **Step 5: Test with live data**
- [ ] **Step 6: Commit**

---

### Task 18: WebSocket latency measurement (Feature 11)

**Files:**
- Modify: `diagnostics.html`

WS messages already have `t` field (server timestamp). Measure client-receive vs server-send.

- [ ] **Step 1: On each WS message: compute latency = Date.now()/1000 - msg.t**
- [ ] **Step 2: Track rolling average (last 60 samples)**
- [ ] **Step 3: Show current latency and rolling average near WS indicator**
- [ ] **Step 4: Color code: green <50ms, amber <200ms, red >200ms**
- [ ] **Step 5: Note: clock skew between Pi and phone makes this approximate. Display "~Xms"**
- [ ] **Step 6: Test with live WS data**
- [ ] **Step 7: Commit**

---

## Batch 4: Frontend -- Interactive Features (Features 12-16)

### Task 19: Click failed check -> detailed diagnostic panel (Feature 12)

**Files:**
- Modify: `diagnostics.html`

- [ ] **Step 1: Expand ERROR_HINTS with step-by-step remediation for each check**
- [ ] **Step 2: Make check-items clickable (cursor pointer)**
- [ ] **Step 3: On click: expand to show what the check does, why it failed, exact error, fix steps**
- [ ] **Step 4: CSS for expanded state with slide-down animation**
- [ ] **Step 5: Test with both passing and failing checks**
- [ ] **Step 6: Commit**

---

### Task 20: Click WiCAN node -> send ATI test (Feature 13)

**Files:**
- Modify: `diagnostics.html`

- [ ] **Step 1: On WiCAN node click (from Task 8): add "Test Connection" button in detail panel**
- [ ] **Step 2: Button calls POST /api/obd/test**
- [ ] **Step 3: Show result (ELM327 version or error) with timing**
- [ ] **Step 4: Loading state while request is in-flight**
- [ ] **Step 5: Test in simulator mode**
- [ ] **Step 6: Commit**

---

### Task 21: Click Pi node -> system info (Feature 14)

**Files:**
- Modify: `diagnostics.html`

- [ ] **Step 1: On Pi node click (from Task 8): fetch GET /api/system**
- [ ] **Step 2: Render CPU%, RAM%, disk%, temp, uptime, Python version, OS in detail panel**
- [ ] **Step 3: Auto-refresh system info every 5s while panel is open**
- [ ] **Step 4: Progress bars for CPU/RAM/disk usage**
- [ ] **Step 5: Test on macOS dev environment**
- [ ] **Step 6: Commit**

---

### Task 22: Click DB node -> database stats (Feature 15)

Note: There's no explicit DB node in the topology SVG. Add a DB node connected to Pi.

**Files:**
- Modify: `diagnostics.html`

- [ ] **Step 1: Add SQLite node to topology SVG (below Pi, connected via line)**
- [ ] **Step 2: On click: fetch /api/debug, extract database section**
- [ ] **Step 3: Show table counts, DB size, WAL size, last vacuum, insert rate**
- [ ] **Step 4: Add force checkpoint button (calls POST /api/control/checkpoint)**
- [ ] **Step 5: Test with live data**
- [ ] **Step 6: Commit**

---

### Task 23: Deep integration test button (Feature 16)

**Files:**
- Modify: `diagnostics.html`

- [ ] **Step 1: Add "Run Integration Test" button to diagnostics page**
- [ ] **Step 2: On click: call POST /api/test/integration**
- [ ] **Step 3: Show step-by-step results with pass/fail and timing for each step**
- [ ] **Step 4: Loading spinner while running**
- [ ] **Step 5: Test with running server**
- [ ] **Step 6: Commit**

---

## Batch 5: Frontend -- Operational Tools (Features 17-19)

### Task 24: Log viewer (Feature 17)

**Files:**
- Modify: `diagnostics.html`

- [ ] **Step 1: Add "Logs" nav link and section**
- [ ] **Step 2: CSS for log viewer (monospace, dark background, colored by level)**
- [ ] **Step 3: Fetch GET /api/logs?lines=100 on load**
- [ ] **Step 4: Level filter buttons (DEBUG/INFO/WARNING/ERROR/CRITICAL)**
- [ ] **Step 5: Auto-scroll to bottom, pause button to freeze**
- [ ] **Step 6: Auto-refresh every 3 seconds (unless paused)**
- [ ] **Step 7: Test with various log levels**
- [ ] **Step 8: Commit**

---

### Task 25: Config viewer (Feature 18)

**Files:**
- Modify: `diagnostics.html`

- [ ] **Step 1: Add "Config" nav link and section**
- [ ] **Step 2: Fetch GET /api/config on load**
- [ ] **Step 3: Render all settings as a styled key-value table**
- [ ] **Step 4: Group by category (server, OBD, vehicle, database, modes)**
- [ ] **Step 5: Read-only display, no edit capabilities**
- [ ] **Step 6: Test with all settings visible**
- [ ] **Step 7: Commit**

---

### Task 26: Manual controls (Feature 19)

**Files:**
- Modify: `diagnostics.html`

- [ ] **Step 1: Add "Controls" nav link and section**
- [ ] **Step 2: Three action cards: Checkpoint, Recalibrate, Restart Producer**
- [ ] **Step 3: Each card has description, confirmation dialog, execute button**
- [ ] **Step 4: On confirm: call respective POST /api/control/* endpoint**
- [ ] **Step 5: Show result (success/error) with timing**
- [ ] **Step 6: Test all 3 controls with running server**
- [ ] **Step 7: Commit**

---

## Batch 6: Final Integration & Polish

### Task 27: Full integration test pass

- [ ] **Step 1: Run all backend tests: `pytest tests/ -v`**
- [ ] **Step 2: Start server, open /diagnostics, verify all 19 features work**
- [ ] **Step 3: Test topology animations (dots, pulsing, hover tooltips)**
- [ ] **Step 4: Test all click interactions (nodes, checks, controls)**
- [ ] **Step 5: Test responsive layout (narrow viewport)**
- [ ] **Step 6: Run mypy strict on all new Python files**
- [ ] **Step 7: Final commit**
