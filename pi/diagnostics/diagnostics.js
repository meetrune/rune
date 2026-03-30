/* Rune Advanced Diagnostics Dashboard -- JavaScript
 *
 * All 19 diagnostic features: topology animations, sparklines, interactive panels,
 * log viewer, config viewer, manual controls, thermal gauges, trip history,
 * WebSocket latency tracking, integration tests, and connection staleness detection.
 *
 * Vanilla JS -- no React, no build step. This is the engineering dashboard.
 */
(function() {
  "use strict";

  var API = window.location.origin;
  var WS_URL = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/vehicle-data";
  var DIAG_REFRESH_MS = 15000;
  var LOG_REFRESH_MS = 3000;
  var WS_RECONNECT_MS = 3000;

  // ---- Sensor definitions with thresholds ----
  var SENSOR_DEFS = [
    { key: "RPM", label: "RPM", unit: "rpm", dec: 0, warn: 5500, crit: 6500 },
    { key: "SPEED", label: "Speed", unit: "kph", dec: 0 },
    { key: "COOLANT_TEMP", label: "Coolant", unit: "C", dec: 1, warn: 100, crit: 110 },
    { key: "OIL_TEMP", label: "Oil Temp", unit: "C", dec: 1, warn: 115, crit: 130 },
    { key: "BATTERY_V", label: "Battery", unit: "V", dec: 1, warnLow: 12.0, critLow: 11.5 },
    { key: "MAF", label: "MAF", unit: "g/s", dec: 2 },
    { key: "STFT", label: "STFT", unit: "%", dec: 1, warn: 10, crit: 25, warnLow: -10, critLow: -25 },
    { key: "LTFT", label: "LTFT", unit: "%", dec: 1, warn: 10, crit: 25, warnLow: -10, critLow: -25 },
    { key: "FUEL_LEVEL", label: "Fuel Level", unit: "%", dec: 0, warnLow: 15, critLow: 5 },
    { key: "ENGINE_LOAD", label: "Engine Load", unit: "%", dec: 0 },
    { key: "THROTTLE_POS", label: "Throttle", unit: "%", dec: 0 },
    { key: "CATALYST_TEMP", label: "Catalyst", unit: "C", dec: 0 },
    { key: "INTAKE_TEMP", label: "Intake Temp", unit: "C", dec: 0 },
    { key: "MAP", label: "MAP", unit: "kPa", dec: 0 },
    { key: "PI_CPU_TEMP", label: "Pi CPU", unit: "C", dec: 1, warn: 72, crit: 83 },
    { key: "ARMREST_TEMP", label: "Armrest", unit: "C", dec: 1, warn: 48, crit: 62 },
    { key: "VIN_VOLTAGE", label: "Vin", unit: "V", dec: 1, warnLow: 11.8, critLow: 11.0 },
    { key: "PI_CURRENT", label: "Pi Current", unit: "A", dec: 2 }
  ];

  // Error hints with step-by-step fix instructions
  var ERROR_HINTS = {
    "FastAPI Server": { hint: "Backend may not be running.", fix: ["Check uvicorn process: ps aux | grep uvicorn", "Start: RUNE_DB_PATH=/tmp/rune.db python -m uvicorn backend.main:app --port 8080"] },
    "SQLite Database": { hint: "Database file missing or corrupted.", fix: ["Check db path: echo $RUNE_DB_PATH", "Verify permissions: ls -la /var/lib/rune/", "Delete and restart if corrupted"] },
    "OBD Collector": { hint: "OBD data collector not running.", fix: ["Mac dev: ensure RUNE_USE_SIMULATOR=true", "Pi: check WiCAN Pro WiFi", "Test: nc -z 192.168.4.100 3333"] },
    "Health Scorer": { hint: "Needs ~5 minutes of data to calibrate.", fix: ["Wait for calibration to complete", "Or use Controls section to Recalibrate"] },
    "Thermal Manager": { hint: "Thermal manager failed.", fix: ["Check backend/sensors/thermal.py", "Verify Witty Pi I2C on Pi"] },
    "Witty Pi Reader": { hint: "I2C not connected (expected on Mac).", fix: ["Mac: normal, simulated reader used", "Pi: check I2C wiring", "Verify: i2cdetect -y 1"] },
    "Snapshot Generation": { hint: "Cannot generate sensor snapshots.", fix: ["Check collector startup", "Verify simulator config"] },
    "DB Write/Read Cycle": { hint: "Cannot write/read database.", fix: ["Check file permissions", "Check disk space: df -h", "SD card may be full"] }
  };

  var CATEGORY_ORDER = ["backend", "sensors", "pipeline", "deploy", "frontend"];
  var CATEGORY_LABELS = { backend: "Backend", sensors: "Sensors", pipeline: "Data Pipeline", deploy: "Deployment", frontend: "Frontend" };

  // ---- State ----
  var currentFilter = "all";
  var lastChecks = [];
  var ws = null;
  var wsReconnectTimer = null;
  var logPaused = false;
  var logLevel = "DEBUG";
  var lastWsMessageTime = 0;
  var wsStartTime = Date.now();
  var wsMessageCount = 0;
  var wsByteCount = 0;
  var wsLatencies = [];
  var connLastSeen = {};
  var openDevicePanel = null;
  var dbSizeSamples = [];
  var sensorBuffers = {};
  var sparklineThrottle = 0;

  // ---- DOM refs ----
  var statusContent = document.getElementById("status-content");
  var checksContainer = document.getElementById("checks-container");
  var sensorGrid = document.getElementById("sensor-grid");
  var sensorNoData = document.getElementById("sensor-no-data");
  var wsIndicator = document.getElementById("ws-indicator");
  var navTimestamp = document.getElementById("nav-timestamp");
  var wsLatencyEl = document.getElementById("ws-latency");
  var devicePanel = document.getElementById("device-detail-panel");
  var deviceContent = document.getElementById("device-detail-content");
  var topoTooltip = document.getElementById("topo-tooltip");

  // ---- Utilities ----
  function formatTime(ts) {
    return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function formatBytes(b) {
    if (b < 1024) return b.toFixed(0) + " B";
    if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
    return (b / 1048576).toFixed(1) + " MB";
  }

  function formatDuration(sec) {
    if (sec < 60) return Math.round(sec) + "s";
    if (sec < 3600) return Math.round(sec / 60) + "m";
    return Math.floor(sec / 3600) + "h " + Math.round((sec % 3600) / 60) + "m";
  }

  function getSeverity(def, val) {
    if (def.crit !== undefined && val >= def.crit) return "critical";
    if (def.critLow !== undefined && val <= def.critLow) return "critical";
    if (def.warn !== undefined && val >= def.warn) return "warn";
    if (def.warnLow !== undefined && val <= def.warnLow) return "warn";
    return "normal";
  }

  function severityColor(sev) {
    return sev === "critical" ? "#ef4444" : sev === "warn" ? "#eab308" : "#22c55e";
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function el(tag, className, text) {
    var e = document.createElement(tag);
    if (className) e.className = className;
    if (text) e.textContent = text;
    return e;
  }

  // ---- Sensor Grid with Sparklines ----
  function buildSensorGrid() {
    sensorGrid.textContent = "";
    for (var i = 0; i < SENSOR_DEFS.length; i++) {
      var def = SENSOR_DEFS[i];
      sensorBuffers[def.key] = new Float32Array(60);
      sensorBuffers[def.key].fill(NaN);
      sensorBuffers[def.key]._idx = 0;
      sensorBuffers[def.key]._count = 0;

      var cell = el("div", "sensor-cell");
      cell.id = "sensor-" + def.key;
      cell.appendChild(el("div", "sensor-label", def.label));

      var valWrap = el("div");
      var valSpan = el("span", "sensor-value sensor-no-data", "--");
      valSpan.id = "sval-" + def.key;
      valWrap.appendChild(valSpan);
      var unitSpan = el("span", "sensor-unit", def.unit);
      valWrap.appendChild(unitSpan);
      cell.appendChild(valWrap);

      var canvas = document.createElement("canvas");
      canvas.className = "sensor-sparkline";
      canvas.height = 44;
      canvas.id = "spark-" + def.key;
      cell.appendChild(canvas);

      sensorGrid.appendChild(cell);
    }
  }

  function drawSparkline(canvasId, buffer, color) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) return;
    // Resize canvas drawing buffer to match its CSS display size
    var displayWidth = canvas.offsetWidth || canvas.clientWidth;
    if (displayWidth > 0 && canvas.width !== displayWidth) {
      canvas.width = displayWidth;
    }
    var ctx = canvas.getContext("2d");
    var w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    var count = Math.min(buffer._count, 60);
    if (count < 2) return;

    var min = Infinity, max = -Infinity;
    for (var i = 0; i < count; i++) {
      var idx = (buffer._idx - count + i + 60) % 60;
      var v = buffer[idx];
      if (!isNaN(v)) { if (v < min) min = v; if (v > max) max = v; }
    }
    if (min === max) { min -= 1; max += 1; }

    ctx.beginPath();
    var first = true;
    for (var i = 0; i < count; i++) {
      var idx = (buffer._idx - count + i + 60) % 60;
      var v = buffer[idx];
      if (isNaN(v)) continue;
      var x = (i / (count - 1)) * w;
      var y = h - ((v - min) / (max - min)) * h;
      if (first) { ctx.moveTo(x, y); first = false; }
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = color + "1a";
    ctx.fill();
  }

  function updateSensors(data) {
    if (!data || !data.d) return;
    sensorNoData.style.display = "none";
    sensorGrid.style.display = "";

    for (var i = 0; i < SENSOR_DEFS.length; i++) {
      var def = SENSOR_DEFS[i];
      var valEl = document.getElementById("sval-" + def.key);
      if (!valEl) continue;
      var entry = data.d[def.key];
      if (entry && entry.v !== undefined && entry.v !== null) {
        var num = Number(entry.v);
        if (isNaN(num)) { valEl.textContent = "--"; valEl.className = "sensor-value sensor-no-data"; continue; }
        valEl.textContent = num.toFixed(def.dec);
        var sev = getSeverity(def, num);
        valEl.className = "sensor-value" + (sev !== "normal" ? " " + sev : "");

        var buf = sensorBuffers[def.key];
        if (buf) { buf[buf._idx] = num; buf._idx = (buf._idx + 1) % 60; buf._count = Math.min(buf._count + 1, 60); }
      } else {
        valEl.textContent = "--";
        valEl.className = "sensor-value sensor-no-data";
      }
    }

    var now = Date.now();
    if (now - sparklineThrottle > 1000) {
      sparklineThrottle = now;
      for (var i = 0; i < SENSOR_DEFS.length; i++) {
        var def = SENSOR_DEFS[i];
        var buf = sensorBuffers[def.key];
        var lastVal = buf[(buf._idx - 1 + 60) % 60];
        var sev = isNaN(lastVal) ? "normal" : getSeverity(def, lastVal);
        drawSparkline("spark-" + def.key, buf, severityColor(sev));
      }
    }
  }

  // ---- WebSocket Latency ----
  function trackLatency(msgTimestamp) {
    var latency = Math.abs(Date.now() / 1000 - msgTimestamp) * 1000;
    if (latency > 60000) return;
    wsLatencies.push(latency);
    if (wsLatencies.length > 60) wsLatencies.shift();
    var avg = wsLatencies.reduce(function(a, b) { return a + b; }, 0) / wsLatencies.length;
    wsLatencyEl.textContent = "~" + Math.round(avg) + "ms";
    wsLatencyEl.className = "nav-latency " + (avg < 50 ? "good" : avg < 200 ? "warn" : "bad");
  }

  function trackThroughput(msgSize) {
    wsMessageCount++;
    wsByteCount += msgSize;
    lastWsMessageTime = Date.now();
    connLastSeen["honda-wican"] = lastWsMessageTime;
    connLastSeen["wican-pi"] = lastWsMessageTime;
    connLastSeen["pi-iphone"] = lastWsMessageTime;
  }

  // ---- Connection Staleness (1Hz) ----
  function checkConnectionStaleness() {
    var now = Date.now();
    var ids = ["honda-wican", "wican-pi", "pi-iphone"];
    for (var i = 0; i < ids.length; i++) {
      var conn = ids[i];
      var line = document.getElementById("line-" + conn);
      var lastSeenEl = document.getElementById("lastseen-" + conn);
      if (!line) continue;
      var elapsed = connLastSeen[conn] ? now - connLastSeen[conn] : 999999;
      if (elapsed > 5000) {
        line.classList.add("stale");
        line.classList.remove("pulsing");
        if (lastSeenEl && connLastSeen[conn]) {
          lastSeenEl.textContent = "Last: " + new Date(connLastSeen[conn]).toLocaleTimeString();
          lastSeenEl.classList.add("visible");
        }
      } else if (elapsed < 3000) {
        line.classList.remove("stale");
        line.classList.add("pulsing");
        if (lastSeenEl) lastSeenEl.classList.remove("visible");
      }
    }
  }

  // ---- Topology Tooltips ----
  function setupTopoTooltips() {
    var hits = document.querySelectorAll("[data-conn]");
    for (var i = 0; i < hits.length; i++) {
      hits[i].addEventListener("mouseenter", function(e) {
        var wrapper = e.currentTarget.closest(".topology-wrapper");
        var rect = wrapper.getBoundingClientRect();
        var svgRect = e.currentTarget.getBoundingClientRect();
        var elapsed = (Date.now() - wsStartTime) / 1000;
        var mps = elapsed > 0 ? (wsMessageCount / elapsed).toFixed(1) : "--";
        var bps = elapsed > 0 ? formatBytes(wsByteCount / elapsed) + "/s" : "--";
        var avgLat = wsLatencies.length > 0 ? "~" + Math.round(wsLatencies.reduce(function(a,b){return a+b},0) / wsLatencies.length) + "ms" : "--";
        document.getElementById("tt-msgs").textContent = mps;
        document.getElementById("tt-bytes").textContent = bps;
        document.getElementById("tt-latency").textContent = avgLat;
        topoTooltip.style.left = (svgRect.left - rect.left + svgRect.width / 2 - 80) + "px";
        topoTooltip.style.top = (svgRect.top - rect.top + 20) + "px";
        topoTooltip.classList.add("visible");
      });
      hits[i].addEventListener("mouseleave", function() { topoTooltip.classList.remove("visible"); });
    }
  }

  // ---- Device Detail Panels ----
  function setupTopoNodeClicks() {
    // Listen for custom event from topology.js (fires on node click, not drag)
    document.addEventListener("topo-node-click", function(e) {
      var device = e.detail.device;
      if (openDevicePanel === device) {
        devicePanel.classList.remove("open");
        openDevicePanel = null;
        return;
      }
      openDevicePanel = device;
      loadDeviceDetail(device);
      devicePanel.classList.add("open");
    });
    // Close button
    var closeBtn = document.getElementById("detail-close-btn");
    if (closeBtn) {
      closeBtn.addEventListener("click", function() {
        devicePanel.classList.remove("open");
        openDevicePanel = null;
      });
    }
  }

  function loadDeviceDetail(device) {
    deviceContent.textContent = "Loading...";

    if (device === "pi") {
      fetch(API + "/api/system").then(function(r) { return r.json(); }).then(function(d) {
        deviceContent.textContent = "";
        var hdr = el("div", "detail-header");
        var dot = el("div", "dot green");
        hdr.appendChild(dot);
        hdr.appendChild(document.createTextNode("Raspberry Pi 4B"));
        deviceContent.appendChild(hdr);

        var grid = el("div", "detail-grid");
        var items = [
          ["CPU Usage", d.cpu_percent + "%"],
          ["RAM", d.ram.used_mb.toFixed(0) + " / " + d.ram.total_mb.toFixed(0) + " MB"],
          ["Disk", d.disk.used_gb.toFixed(1) + " / " + d.disk.total_gb.toFixed(1) + " GB"],
          ["CPU Temp", d.cpu_temp_c !== null ? d.cpu_temp_c + " C" : "N/A"],
          ["Uptime", formatDuration(d.uptime_seconds)],
          ["Python", d.python_version],
          ["OS", d.os_version],
          ["Hostname", d.hostname]
        ];
        for (var i = 0; i < items.length; i++) {
          var item = el("div", "detail-item");
          item.appendChild(el("div", "detail-label", items[i][0]));
          var val = el("div", i >= 5 ? "detail-value small" : "detail-value", items[i][1]);
          item.appendChild(val);
          grid.appendChild(item);
        }
        deviceContent.appendChild(grid);
      }).catch(function() { deviceContent.textContent = "Failed to load system info."; });

    } else if (device === "wican") {
      deviceContent.textContent = "";
      var hdr = el("div", "detail-header");
      hdr.appendChild(el("div", "dot amber"));
      hdr.appendChild(document.createTextNode("WiCAN Pro"));
      deviceContent.appendChild(hdr);
      var grid = el("div", "detail-grid");
      [["Protocol", "ELM327 TCP:3333"], ["CAN", "ISO 15765-4 (ATSP6)"], ["Firmware", "latest"]].forEach(function(pair) {
        var item = el("div", "detail-item");
        item.appendChild(el("div", "detail-label", pair[0]));
        item.appendChild(el("div", "detail-value small", pair[1]));
        grid.appendChild(item);
      });
      deviceContent.appendChild(grid);
      var btn = el("button", "detail-btn", "Test Connection (ATI)");
      btn.id = "btn-ati-test";
      var resultDiv = el("div");
      resultDiv.id = "ati-result";
      resultDiv.style.cssText = "margin-top:8px;font-size:13px;color:#888;font-family:JetBrains Mono,monospace";
      btn.addEventListener("click", function() { testATI(btn, resultDiv); });
      deviceContent.appendChild(btn);
      deviceContent.appendChild(resultDiv);

    } else if (device === "db") {
      fetch(API + "/api/debug").then(function(r) { return r.json(); }).then(function(d) {
        deviceContent.textContent = "";
        var db = d.database || {};
        var hdr = el("div", "detail-header");
        hdr.appendChild(el("div", "dot green"));
        hdr.appendChild(document.createTextNode("SQLite Database"));
        deviceContent.appendChild(hdr);
        var grid = el("div", "detail-grid");
        var items = [["Size", (db.size_mb || 0).toFixed(2) + " MB"], ["Journal", db.journal_mode || "WAL"], ["Retention", (db.retention_days || 90) + " days"]];
        var tables = db.tables || {};
        for (var t in tables) items.push([t, tables[t].toLocaleString() + " rows"]);
        items.forEach(function(pair) {
          var item = el("div", "detail-item");
          item.appendChild(el("div", "detail-label", pair[0]));
          item.appendChild(el("div", "detail-value", pair[1]));
          grid.appendChild(item);
        });
        deviceContent.appendChild(grid);
        var btn = el("button", "detail-btn", "Force Checkpoint");
        btn.addEventListener("click", function() { executeControl("checkpoint"); });
        deviceContent.appendChild(btn);
      }).catch(function() { deviceContent.textContent = "Failed to load DB info."; });

    } else if (device === "honda") {
      deviceContent.textContent = "";
      var hdr = el("div", "detail-header");
      hdr.appendChild(el("div", "dot amber"));
      hdr.appendChild(document.createTextNode("2026 Honda Accord SE"));
      deviceContent.appendChild(hdr);
      var grid = el("div", "detail-grid");
      [["Engine","L15BE 1.5T"],["Transmission","CVT (non-hybrid)"],["OBD Protocol","ISO 15765-4"],["PIDs","14 standard + Mode 22"],["Tank","14.8 gal"],["EPA","31 MPG"]].forEach(function(p) {
        var item = el("div", "detail-item");
        item.appendChild(el("div", "detail-label", p[0]));
        item.appendChild(el("div", "detail-value small", p[1]));
        grid.appendChild(item);
      });
      deviceContent.appendChild(grid);

    } else if (device === "iphone") {
      deviceContent.textContent = "";
      var hdr = el("div", "detail-header");
      hdr.appendChild(el("div", "dot amber"));
      hdr.appendChild(document.createTextNode("iPhone"));
      deviceContent.appendChild(hdr);
      var grid = el("div", "detail-grid");
      [["Role","Sync relay / ntfy"],["Sync","WiFi to Pi"],["Relay","iCloud to Mac"]].forEach(function(p) {
        var item = el("div", "detail-item");
        item.appendChild(el("div", "detail-label", p[0]));
        item.appendChild(el("div", "detail-value small", p[1]));
        grid.appendChild(item);
      });
      deviceContent.appendChild(grid);

    } else if (device === "mac") {
      deviceContent.textContent = "";
      var hdr = el("div", "detail-header");
      hdr.appendChild(el("div", "dot amber"));
      hdr.appendChild(document.createTextNode("MacBook M3 Max"));
      deviceContent.appendChild(hdr);
      var grid = el("div", "detail-grid");
      [["Role","ML training / analysis"],["Chip","Apple M3 Max"],["RAM","36 GB"],["ML","MLX + Prophet"]].forEach(function(p) {
        var item = el("div", "detail-item");
        item.appendChild(el("div", "detail-label", p[0]));
        item.appendChild(el("div", "detail-value small", p[1]));
        grid.appendChild(item);
      });
      deviceContent.appendChild(grid);

    } else if (device === "witty") {
      fetch(API + "/api/debug").then(function(r) { return r.json(); }).then(function(d) {
        deviceContent.textContent = "";
        var therm = d.thermal || {};
        var hdr = el("div", "detail-header");
        hdr.appendChild(el("div", "dot amber"));
        hdr.appendChild(document.createTextNode("Witty Pi 4"));
        deviceContent.appendChild(hdr);
        var grid = el("div", "detail-grid");
        [["Role","12V->5V / RTC / I2C"],["Vin Baseline",(therm.vin_baseline_mean||"--")+" V"],["Armrest",(therm.armrest_filtered||"--")+" C"],["Startup Ambient",(therm.startup_ambient||"--")+" C"]].forEach(function(p) {
          var item = el("div", "detail-item");
          item.appendChild(el("div", "detail-label", p[0]));
          item.appendChild(el("div", "detail-value", p[1]));
          grid.appendChild(item);
        });
        deviceContent.appendChild(grid);
      }).catch(function() { deviceContent.textContent = "Failed to load Witty Pi info."; });
    }
  }

  function testATI(btn, resultDiv) {
    btn.disabled = true;
    btn.textContent = "Testing...";
    resultDiv.textContent = "";
    fetch(API + "/api/obd/test", { method: "POST" })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        btn.disabled = false;
        btn.textContent = "Test Connection (ATI)";
        resultDiv.style.color = d.success ? "#22c55e" : "#ef4444";
        resultDiv.textContent = d.success ? d.response + " (" + d.duration_ms.toFixed(1) + "ms, " + d.mode + ")" : "Error: " + (d.error || "Unknown");
      })
      .catch(function(e) {
        btn.disabled = false;
        btn.textContent = "Test Connection (ATI)";
        resultDiv.style.color = "#ef4444";
        resultDiv.textContent = "Request failed: " + e.message;
      });
  }

  // ---- Status Banner ----
  function renderBanner(summary) {
    statusContent.textContent = "";
    if (!summary) { statusContent.appendChild(el("span", "status-loading", "Loading diagnostics...")); return; }

    var overall = summary.fail > 0 ? "fail" : summary.warn > 0 ? "warn" : "pass";
    var text = summary.fail > 0 ? summary.fail + " check" + (summary.fail === 1 ? "" : "s") + " failed" :
               summary.warn > 0 ? summary.warn + " warning" + (summary.warn === 1 ? "" : "s") : "All systems operational";

    var wrapper = el("div", "status-inner");
    wrapper.appendChild(el("div", "status-dot-large " + overall));

    var textEl = el("span", overall !== "pass" ? "status-text clickable" : "status-text", text);
    if (overall !== "pass") {
      textEl.addEventListener("click", function() { scrollToChecksWithFilter(overall === "fail" ? "fail" : "warn"); });
    }
    wrapper.appendChild(textEl);

    var sparkCanvas = document.createElement("canvas");
    sparkCanvas.className = "status-sparkline";
    sparkCanvas.width = 120; sparkCanvas.height = 32;
    sparkCanvas.id = "health-trend-spark";
    wrapper.appendChild(sparkCanvas);

    var counts = el("div", "status-counts");
    var pc = el("span", "status-count pass-count");
    pc.appendChild(el("span", "num", String(summary.pass)));
    pc.appendChild(document.createTextNode(" passed"));
    counts.appendChild(pc);
    if (summary.warn > 0) {
      var wc = el("span", "status-count warn-count");
      wc.appendChild(el("span", "num", String(summary.warn)));
      wc.appendChild(document.createTextNode(" warn"));
      wc.addEventListener("click", function() { scrollToChecksWithFilter("warn"); });
      counts.appendChild(wc);
    }
    if (summary.fail > 0) {
      var fc = el("span", "status-count fail-count");
      fc.appendChild(el("span", "num", String(summary.fail)));
      fc.appendChild(document.createTextNode(" failed"));
      fc.addEventListener("click", function() { scrollToChecksWithFilter("fail"); });
      counts.appendChild(fc);
    }
    wrapper.appendChild(counts);
    statusContent.appendChild(wrapper);

    fetchHealthTrend();
  }

  function fetchHealthTrend() {
    fetch(API + "/api/health-trend?hours=1").then(function(r) { return r.json(); }).then(function(data) {
      var canvas = document.getElementById("health-trend-spark");
      if (!canvas || !data.scores || data.scores.length < 2) return;
      var dw = canvas.offsetWidth || canvas.clientWidth;
      if (dw > 0 && canvas.width !== dw) canvas.width = dw;
      var ctx = canvas.getContext("2d");
      var w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      var scores = data.scores.map(function(s) { return s.overall || 0; });
      var min = Math.min.apply(null, scores.filter(function(v){return v>0})) || 0;
      var max = Math.max.apply(null, scores) || 100;
      if (min === max) { min -= 5; max += 5; }
      ctx.beginPath();
      for (var i = 0; i < scores.length; i++) {
        var x = (i / (scores.length - 1)) * w;
        var y = h - ((scores[i] - min) / (max - min)) * h;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.strokeStyle = "#22c55e"; ctx.lineWidth = 1.5; ctx.stroke();
    }).catch(function() {});
  }

  // ---- Scroll to checks with filter ----
  function scrollToChecksWithFilter(filter) {
    // Activate the filter button
    var buttons = document.querySelectorAll(".check-filter-btn");
    for (var i = 0; i < buttons.length; i++) {
      var f = buttons[i].getAttribute("data-filter");
      buttons[i].classList.toggle("active", f === filter);
    }
    currentFilter = filter;
    renderChecks(lastChecks, currentFilter);
    // Scroll to checks section
    var checksSection = document.getElementById("checks");
    if (checksSection) checksSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---- Render Checks ----
  function renderChecks(checks, filter) {
    checksContainer.textContent = "";
    if (!checks || checks.length === 0) { checksContainer.appendChild(el("p", "no-data-msg", "No diagnostic data available.")); return; }

    var filtered = filter === "all" ? checks : checks.filter(function(c) { return c.status === filter; });
    if (filtered.length === 0) { checksContainer.appendChild(el("p", "no-data-msg", "No checks match this filter.")); return; }

    var groups = {};
    filtered.forEach(function(c) { var cat = c.category || "other"; if (!groups[cat]) groups[cat] = []; groups[cat].push(c); });

    CATEGORY_ORDER.forEach(function(catKey) {
      if (!groups[catKey]) return;
      var catChecks = groups[catKey];
      var group = el("div", "category-group");

      var header = el("div", "category-header");
      header.appendChild(el("span", "category-name", CATEGORY_LABELS[catKey] || catKey));
      var passCount = catChecks.filter(function(c) { return c.status === "pass"; }).length;
      header.appendChild(el("span", "category-count", passCount + "/" + catChecks.length + " passed"));
      group.appendChild(header);

      catChecks.forEach(function(check) {
        var item = el("div", "check-item");
        item.appendChild(el("div", "check-dot " + check.status));
        var info = el("div", "check-info");
        info.appendChild(el("div", "check-name", check.name));
        info.appendChild(el("div", "check-message", check.message));

        if ((check.status === "warn" || check.status === "fail") && ERROR_HINTS[check.name]) {
          var hintData = ERROR_HINTS[check.name];
          info.appendChild(el("div", check.status === "fail" ? "check-hint fail-hint" : "check-hint", hintData.hint + " (click for fix steps)"));

          var detailDiv = el("div", "check-detail");
          var inner = el("div", "check-detail-inner");
          inner.appendChild(el("strong", null, "How to fix:"));
          hintData.fix.forEach(function(fix) { inner.appendChild(el("div", "step", fix)); });
          detailDiv.appendChild(inner);
          info.appendChild(detailDiv);

          item.addEventListener("click", function() { detailDiv.classList.toggle("open"); });
        }

        item.appendChild(info);
        if (check.duration_ms !== undefined) item.appendChild(el("div", "check-duration", check.duration_ms.toFixed(1) + " ms"));
        group.appendChild(item);
      });

      checksContainer.appendChild(group);
    });
  }

  // ---- Update Topology (uses runeTopology API from diagnostics-topology.js) ----
  function updateTopology(checks) {
    if (!window.runeTopology) return;

    var isSimulator = true, serverOk = false, collectorOk = false, wsOk = false;
    checks.forEach(function(c) {
      if (c.name === "FastAPI Server") { serverOk = c.status === "pass"; if (c.details && c.details.simulator === false) isSimulator = false; }
      if (c.name === "OBD Collector") collectorOk = c.status === "pass";
      if (c.name === "WebSocket Manager") wsOk = c.status === "pass";
    });

    var obdStatus = isSimulator ? "simulated" : (collectorOk ? "connected" : "disconnected");
    var piStatus = isSimulator ? "simulated" : (serverOk ? "connected" : "disconnected");
    var iphoneStatus = isSimulator ? "simulated" : (wsOk ? "connected" : "disconnected");

    window.runeTopology.setNodeStatus("honda", obdStatus);
    window.runeTopology.setNodeStatus("wican", obdStatus);
    window.runeTopology.setNodeStatus("pi", piStatus);
    window.runeTopology.setNodeStatus("iphone", iphoneStatus);
    window.runeTopology.setNodeStatus("mac", piStatus);
    window.runeTopology.setNodeStatus("db", piStatus);
    window.runeTopology.setNodeStatus("witty", isSimulator ? "simulated" : "connected");

    window.runeTopology.setLineStatus("line-honda-wican", obdStatus);
    window.runeTopology.setLineStatus("line-wican-pi", obdStatus);
    window.runeTopology.setLineStatus("line-pi-iphone", iphoneStatus);
    window.runeTopology.setLineStatus("line-iphone-mac", iphoneStatus);
    window.runeTopology.setLineStatus("line-pi-db", piStatus);
    window.runeTopology.setLineStatus("line-pi-witty", isSimulator ? "simulated" : "connected");
  }

  // ---- Thermal Gauges ----
  function updateThermalGauges() {
    fetch(API + "/api/debug").then(function(r) { return r.json(); }).then(function(data) {
      var therm = data.thermal || {}, db = data.database || {};
      var colors = { green: "#22c55e", yellow: "#eab308", orange: "#f97316", red: "#ef4444", danger: "#dc2626" };

      function updateGauge(prefix, temp, status, maxTemp) {
        var valEl = document.getElementById(prefix + "-val");
        var fillEl = document.getElementById(prefix + "-fill");
        if (valEl) { valEl.textContent = temp.toFixed(1) + " C"; valEl.className = "thermal-bar-value " + status; }
        if (fillEl) { fillEl.style.width = Math.min(100, Math.max(0, temp / maxTemp * 100)) + "%"; fillEl.style.background = colors[status] || "#22c55e"; }
      }

      updateGauge("therm-cpu", therm.cpu_filtered || 0, therm.cpu_status || "green", 105);
      updateGauge("therm-arm", therm.armrest_filtered || 0, therm.armrest_status || "green", 80);

      var cpuRate = document.getElementById("therm-cpu-rate");
      var armRate = document.getElementById("therm-arm-rate");
      if (cpuRate) cpuRate.textContent = "Rate: " + (therm.cpu_rate_per_min || 0).toFixed(1) + " C/min";
      if (armRate) armRate.textContent = "Rate: " + (therm.armrest_rate_per_min || 0).toFixed(1) + " C/min";

      var dbSizeVal = document.getElementById("db-size-val");
      var dbWalVal = document.getElementById("db-wal-val");
      var dbRateEl = document.getElementById("db-rate");
      var dbLabel = document.getElementById("db-size-label");
      if (dbSizeVal) dbSizeVal.textContent = (db.size_mb || 0).toFixed(2) + " MB";
      if (dbLabel) dbLabel.textContent = (db.size_mb || 0).toFixed(1) + " MB";

      // Fetch WAL size and insert rate from system endpoint
      fetch(API + "/api/debug").then(function(r2) { return r2.json(); }).then(function(d2) {
        // WAL size from DB tables
        var tables = (d2.database || {}).tables || {};
        var readings = tables.sensor_readings || 0;
        if (dbWalVal) {
          // Estimate WAL activity from readings count growth
          var walKb = readings > 0 ? "active" : "0 KB";
          dbWalVal.textContent = walKb;
        }
        if (dbRateEl) {
          // readings / seconds since start
          var uptime = (d2.server || {}).uptime_seconds || 1;
          var rate = (readings / uptime).toFixed(1);
          dbRateEl.textContent = "Insert rate: " + rate + " rows/s";
        }
      }).catch(function() {});

      dbSizeSamples.push({ t: Date.now(), size: db.size_mb || 0 });
      if (dbSizeSamples.length > 240) dbSizeSamples.shift();
      drawDbGrowth();
    }).catch(function() {});
  }

  function drawDbGrowth() {
    var canvas = document.getElementById("db-growth-canvas");
    if (!canvas || dbSizeSamples.length < 2) return;
    var displayWidth = canvas.offsetWidth || canvas.clientWidth;
    if (displayWidth > 0 && canvas.width !== displayWidth) canvas.width = displayWidth;
    var displayHeight = canvas.offsetHeight || canvas.clientHeight;
    if (displayHeight > 0 && canvas.height !== displayHeight) canvas.height = displayHeight;
    var ctx = canvas.getContext("2d");
    var w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    var sizes = dbSizeSamples.map(function(s) { return s.size; });
    var min = Math.min.apply(null, sizes), max = Math.max.apply(null, sizes);
    if (min === max) { min -= 0.01; max += 0.01; }
    ctx.beginPath();
    for (var i = 0; i < sizes.length; i++) {
      var x = (i / (sizes.length - 1)) * w;
      var y = h - ((sizes[i] - min) / (max - min)) * h;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = "#3b82f6"; ctx.lineWidth = 1.5; ctx.stroke();
  }

  // ---- Trip History ----
  function loadTrips() {
    var container = document.getElementById("trips-list");
    fetch(API + "/api/trips?limit=20").then(function(r) { return r.json(); }).then(function(data) {
      var trips = data.trips || [];
      if (trips.length === 0) { container.textContent = ""; container.appendChild(el("p", "no-data-msg", "No trips recorded yet.")); return; }
      container.textContent = "";
      trips.forEach(function(t) {
        var card = el("div", "trip-card");
        var dist = t.distance_miles || 0, cost = t.fuel_cost_usd || 0, mpg = t.avg_mpg;
        var dur = t.start_time && t.end_time ? (t.end_time - t.start_time) / 60000 : 0;
        var mpgClass = !mpg ? "" : mpg >= 31 ? "good" : mpg >= 25 ? "ok" : "poor";

        function addStat(label, value, cls) {
          var wrap = el("div");
          wrap.appendChild(el("div", "trip-stat-label", label));
          wrap.appendChild(el("div", "trip-stat-value" + (cls ? " " + cls : ""), value));
          card.appendChild(wrap);
        }
        addStat("Distance", dist.toFixed(1) + " mi");
        addStat("Cost", "$" + cost.toFixed(2));
        addStat("Avg MPG", mpg ? mpg.toFixed(1) : "--", mpgClass);
        addStat("Duration", dur > 0 ? dur.toFixed(0) + " min" : "--");
        container.appendChild(card);
      });
    }).catch(function() { container.textContent = ""; container.appendChild(el("p", "no-data-msg", "Failed to load trips.")); });
  }

  // ---- Log Viewer ----
  function loadLogs() {
    if (logPaused) return;
    var viewer = document.getElementById("log-viewer");
    fetch(API + "/api/logs?lines=100&level=" + logLevel).then(function(r) { return r.json(); }).then(function(data) {
      var logs = data.logs || [];
      if (logs.length === 0) { viewer.textContent = ""; viewer.appendChild(el("p", "no-data-msg", "No log entries at " + logLevel + " level.")); return; }
      viewer.textContent = "";
      for (var i = logs.length - 1; i >= 0; i--) {
        var log = logs[i];
        var entry = el("div", "log-entry");
        var ts = log.timestamp ? log.timestamp.split("T")[1].split(".")[0] : "";
        entry.appendChild(el("span", "log-time", ts));
        entry.appendChild(el("span", "log-level-tag " + log.level, log.level));
        entry.appendChild(el("span", "log-logger", log.logger || ""));
        entry.appendChild(el("span", "log-msg", log.message || ""));
        viewer.appendChild(entry);
      }
      viewer.scrollTop = viewer.scrollHeight;
    }).catch(function() { viewer.textContent = ""; viewer.appendChild(el("p", "no-data-msg", "Failed to load logs.")); });
  }

  function setupLogLevelButtons() {
    var buttons = document.querySelectorAll(".log-level-btn");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function(e) {
        for (var j = 0; j < buttons.length; j++) buttons[j].classList.remove("active");
        e.currentTarget.classList.add("active");
        logLevel = e.currentTarget.getAttribute("data-level");
        loadLogs();
      });
    }

    document.getElementById("log-pause-btn").addEventListener("click", function() {
      logPaused = !logPaused;
      this.textContent = logPaused ? "Resume" : "Pause";
      this.classList.toggle("paused", logPaused);
    });
  }

  // ---- Config Viewer ----
  function loadConfig() {
    var container = document.getElementById("config-container");
    fetch(API + "/api/config").then(function(r) { return r.json(); }).then(function(data) {
      var settings = data.settings || {}, categories = data.categories || {};
      container.textContent = "";
      for (var catName in categories) {
        var keys = categories[catName];
        var group = el("div", "config-group");
        group.appendChild(el("div", "config-group-header", catName));
        var table = el("table", "config-table");
        keys.forEach(function(key) {
          var row = el("tr");
          row.appendChild(el("td", "config-key", key));
          row.appendChild(el("td", "config-val", settings[key] !== undefined ? String(settings[key]) : "--"));
          table.appendChild(row);
        });
        group.appendChild(table);
        container.appendChild(group);
      }
    }).catch(function() { container.textContent = ""; container.appendChild(el("p", "no-data-msg", "Failed to load config.")); });
  }

  // ---- Manual Controls ----
  function executeControl(action) {
    var btn = document.getElementById("btn-" + action);
    var resultEl = document.getElementById("result-" + action);
    if (!btn) return;

    if (action === "go-live") {
      if (!confirm("WARNING: This will DELETE ALL simulated data and switch to real OBD hardware.\n\nThis cannot be undone. Are you sure?")) return;
    } else if (action === "reset-data") {
      if (!confirm("This will DELETE ALL stored data (readings, trips, health scores, logs) and reset calibration.\n\nThe system will keep running in its current mode. Are you sure?")) return;
    } else if (action === "recalibrate" || action === "restart-producer") {
      var msg = action === "recalibrate" ? "Health scores will show -1 for ~5 minutes. Continue?" : "Producer loop will stop and restart. Continue?";
      if (!confirm(msg)) return;
    }

    btn.disabled = true;
    var origText = btn.textContent;
    btn.textContent = "Running...";
    if (resultEl) resultEl.style.display = "none";

    fetch(API + "/api/control/" + action, { method: "POST" }).then(function(r) { return r.json(); }).then(function(d) {
      if (action === "go-live" && d.success) { btn.disabled = true; btn.textContent = "Live Mode Active"; btn.style.background = "#166534"; } else { btn.disabled = false; btn.textContent = origText; }
      if (resultEl) {
        resultEl.style.display = "block";
        resultEl.className = "control-result " + (d.success ? "success" : "error");
        if (d.success && action === "go-live" && d.purged) {
          var purgeMsg = "LIVE MODE ACTIVE. Purged: " + Object.keys(d.purged).map(function(k) { return k + "=" + d.purged[k]; }).join(", ") + " (" + (d.duration_ms || 0).toFixed(1) + "ms)";
          resultEl.textContent = purgeMsg;
        } else {
          resultEl.textContent = d.success ? (d.message || "Success") + " (" + (d.duration_ms || 0).toFixed(1) + "ms)" : "Error: " + (d.error || "Unknown");
        }
      }
    }).catch(function(e) {
      btn.disabled = false; btn.textContent = origText;
      if (resultEl) { resultEl.style.display = "block"; resultEl.className = "control-result error"; resultEl.textContent = "Request failed: " + e.message; }
    });
  }

  // Wire up control buttons
  function setupControls() {
    document.getElementById("btn-checkpoint").addEventListener("click", function() { executeControl("checkpoint"); });
    document.getElementById("btn-recalibrate").addEventListener("click", function() { executeControl("recalibrate"); });
    document.getElementById("btn-restart-producer").addEventListener("click", function() { executeControl("restart-producer"); });
    document.getElementById("btn-reset-data").addEventListener("click", function() { executeControl("reset-data"); });
  }

  // ---- Integration Test ----
  function setupIntegrationTest() {
    document.getElementById("btn-integration-test").addEventListener("click", function() {
      var btn = this;
      var statusEl = document.getElementById("integration-status");
      var stepsEl = document.getElementById("integration-steps");
      btn.disabled = true; btn.textContent = "Running...";
      statusEl.textContent = ""; stepsEl.style.display = "none"; stepsEl.textContent = "";

      fetch(API + "/api/test/integration", { method: "POST" }).then(function(r) { return r.json(); }).then(function(data) {
        btn.disabled = false; btn.textContent = "Run Integration Test";
        stepsEl.style.display = "block";
        (data.steps || []).forEach(function(step) {
          var row = el("div", "integration-step");
          row.appendChild(el("div", "step-dot " + step.status));
          row.appendChild(el("div", "step-name", step.name));
          row.appendChild(el("div", "step-detail", step.detail || ""));
          row.appendChild(el("div", "step-time", step.duration_ms.toFixed(1) + "ms"));
          stepsEl.appendChild(row);
        });
        statusEl.textContent = data.overall === "pass" ? "All passed (" + (data.total_duration_ms || 0).toFixed(1) + "ms)" : "Some steps failed";
        statusEl.style.color = data.overall === "pass" ? "#22c55e" : "#ef4444";
      }).catch(function(e) {
        btn.disabled = false; btn.textContent = "Run Integration Test";
        statusEl.textContent = "Request failed: " + e.message;
        statusEl.style.color = "#ef4444";
      });
    });
  }

  // ---- Fetch Diagnostics ----
  function fetchDiagnostics() {
    fetch(API + "/api/diagnostics").then(function(r) { return r.json(); }).then(function(data) {
      lastChecks = data.checks || [];
      renderBanner(data.summary);
      renderChecks(lastChecks, currentFilter);
      updateTopology(lastChecks);
      if (data.timestamp) navTimestamp.textContent = "Last: " + formatTime(data.timestamp);
    }).catch(function() {
      renderBanner(null);
      checksContainer.textContent = "";
      checksContainer.appendChild(el("p", "no-data-msg", "Cannot reach backend at " + API + ". Is the server running?"));
    });
  }

  // ---- WebSocket ----
  function connectWebSocket() {
    if (ws) { try { ws.close(); } catch(e) {} }
    try { ws = new WebSocket(WS_URL); } catch(e) { return; }
    ws.onopen = function() { wsIndicator.className = "nav-ws-status connected"; wsIndicator.title = "WebSocket connected"; wsStartTime = Date.now(); };
    ws.onmessage = function(event) {
      try {
        var data = JSON.parse(event.data);
        if (data.type === "trip_ended") return;
        trackThroughput(event.data.length);
        if (data.t) trackLatency(data.t);
        updateSensors(data);
      } catch(e) {}
    };
    ws.onclose = function() { wsIndicator.className = "nav-ws-status disconnected"; clearTimeout(wsReconnectTimer); wsReconnectTimer = setTimeout(connectWebSocket, WS_RECONNECT_MS); };
    ws.onerror = function() { wsIndicator.className = "nav-ws-status disconnected"; };
  }

  // ---- Filters ----
  function setupFilters() {
    var buttons = document.querySelectorAll(".check-filter-btn");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function(e) {
        for (var j = 0; j < buttons.length; j++) buttons[j].classList.remove("active");
        e.currentTarget.classList.add("active");
        currentFilter = e.currentTarget.getAttribute("data-filter");
        renderChecks(lastChecks, currentFilter);
      });
    }
  }

  // ---- Nav Scroll Spy ----
  function setupNav() {
    var links = document.querySelectorAll(".nav-link");
    for (var i = 0; i < links.length; i++) {
      links[i].addEventListener("click", function(e) {
        var sectionId = e.currentTarget.getAttribute("data-section");
        if (sectionId === "overview") {
          // Overview = scroll to top of page
          window.scrollTo({ top: 0, behavior: "smooth" });
        } else {
          var sec = document.getElementById(sectionId);
          if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        for (var j = 0; j < links.length; j++) links[j].classList.remove("active");
        e.currentTarget.classList.add("active");
      });
    }

    var sections = ["overview","topology","sensors","thermal","checks","sect-intelligence","trips","logs","config","controls"];
    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          for (var j = 0; j < links.length; j++)
            links[j].classList.toggle("active", links[j].getAttribute("data-section") === entry.target.id);
        }
      });
    }, { rootMargin: "-50% 0px -50% 0px" });

    sections.forEach(function(s) { var e = document.getElementById(s); if (e) observer.observe(e); });
  }

  // --- Intelligence Layer ---

  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function loadIntelligence() {
    fetch(API + "/api/intelligence/status").then(function(r) { return r.json(); }).then(function(d) {
      if (d.battery) {
        setText("batt-state", d.battery.state || "unknown");
        setText("batt-resting", d.battery.resting_voltage_ewma.toFixed(2) + "V");
        setText("batt-charging", d.battery.charging_voltage_ewma.toFixed(2) + "V");
        setText("batt-drain", d.battery.drain_rate_v_per_hour.toFixed(4) + " V/hr");
        setText("batt-samples", String(d.battery.samples));
        var stateEl = document.getElementById("batt-state");
        if (stateEl) {
          var colors = { full: "#22c55e", good: "#22c55e", fair: "#f59e0b", low: "#f59e0b", critical: "#ef4444", charging: "#60a5fa", weak_charging: "#f59e0b", unknown: "#666" };
          stateEl.style.color = colors[d.battery.state] || "#666";
        }
      }
      setText("drive-baseline", (d.baseline_mpg || 31.0).toFixed(1));
      if (d.can_decoder) {
        setText("drive-can", d.can_decoder.known_can_ids + " IDs / " + d.can_decoder.decoded_frames + " frames");
      }
      if (d.warmup_model) {
        setText("drive-warmup", "Fitted (" + d.warmup_model.n_samples + " samples, R\u00B2=" + d.warmup_model.r_squared.toFixed(2) + ")");
      } else {
        setText("drive-warmup", "Learning...");
      }
      setText("intel-updated", "Updated " + new Date().toLocaleTimeString());
    }).catch(function() {});
  }

  function loadSyncStatus() {
    fetch(API + "/api/sync/status").then(function(r) { return r.json(); }).then(function(d) {
      setText("sync-pending", String(d.pending_alerts));
      var pendingEl = document.getElementById("sync-pending");
      if (pendingEl) pendingEl.style.color = d.pending_alerts > 0 ? "#f59e0b" : "#22c55e";
      setText("sync-last", d.last_sync_at ? new Date(d.last_sync_at).toLocaleString() : "Never");
      setText("sync-readings", String(d.readings_since_sync));
      setText("sync-hasdata", d.has_data ? "Yes" : "No");
      var hasEl = document.getElementById("sync-hasdata");
      if (hasEl) hasEl.style.color = d.has_data ? "#f59e0b" : "#22c55e";
    }).catch(function() {});
  }

  function loadMaintenance() {
    fetch(API + "/api/maintenance/status").then(function(r) { return r.json(); }).then(function(d) {
      var container = document.getElementById("maint-list");
      if (!container || !d.items) return;
      container.textContent = "";
      d.items.forEach(function(item) {
        var row = document.createElement("div");
        row.className = "intel-row";
        var label = document.createElement("span");
        label.className = "intel-label";
        label.textContent = item.item.replace(/_/g, " ");
        var value = document.createElement("span");
        value.className = "intel-value";
        var miles = item.miles_remaining;
        if (miles <= 0) {
          value.textContent = Math.abs(miles).toFixed(0) + " mi overdue";
          value.className += " maint-overdue";
        } else if (miles <= 1000) {
          value.textContent = miles.toFixed(0) + " mi left";
          value.className += " maint-soon";
        } else {
          value.textContent = miles.toFixed(0) + " mi left";
          value.className += " maint-due";
        }
        row.appendChild(label);
        row.appendChild(value);
        container.appendChild(row);
      });
    }).catch(function() {});
  }

  function loadAlerts() {
    fetch(API + "/api/sync/alerts").then(function(r) { return r.json(); }).then(function(d) {
      var container = document.getElementById("alert-list");
      if (!container) return;
      if (!d.alerts || d.alerts.length === 0) {
        container.textContent = "";
        var emptyRow = document.createElement("div");
        emptyRow.className = "intel-row";
        var emptyLabel = document.createElement("span");
        emptyLabel.className = "intel-label";
        emptyLabel.textContent = "No pending alerts";
        emptyRow.appendChild(emptyLabel);
        container.appendChild(emptyRow);
        return;
      }
      container.textContent = "";
      d.alerts.forEach(function(alert) {
        var row = document.createElement("div");
        row.className = "intel-row";
        row.style.flexDirection = "column";
        row.style.alignItems = "flex-start";
        row.style.gap = "4px";
        var header = document.createElement("div");
        header.style.display = "flex";
        header.style.gap = "8px";
        header.style.alignItems = "center";
        var badge = document.createElement("span");
        badge.className = "alert-badge " + alert.severity;
        badge.textContent = alert.severity;
        header.appendChild(badge);
        var cat = document.createElement("span");
        cat.className = "intel-label";
        cat.textContent = alert.category;
        header.appendChild(cat);
        row.appendChild(header);
        var msg = document.createElement("div");
        msg.className = "intel-value";
        msg.style.fontSize = "13px";
        msg.style.lineHeight = "1.4";
        msg.textContent = alert.message;
        row.appendChild(msg);
        container.appendChild(row);
      });
    }).catch(function() {});
  }

  // ---- Init ----
  function init() {
    buildSensorGrid();
    sensorGrid.style.display = "none";
    setupFilters();
    setupNav();
    setupLogLevelButtons();
    setupTopoTooltips();
    setupTopoNodeClicks();
    setupControls();
    setupIntegrationTest();

    fetchDiagnostics();
    connectWebSocket();
    loadTrips();
    loadLogs();
    loadConfig();
    updateThermalGauges();
    loadIntelligence();
    loadSyncStatus();
    loadMaintenance();
    loadAlerts();

    setInterval(function() {
      fetchDiagnostics();
      loadIntelligence();
      loadSyncStatus();
      loadMaintenance();
      loadAlerts();
    }, DIAG_REFRESH_MS);
    setInterval(loadLogs, LOG_REFRESH_MS);
    setInterval(checkConnectionStaleness, 1000);
    setInterval(updateThermalGauges, DIAG_REFRESH_MS);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
