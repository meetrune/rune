/* Rune Topology -- Interactive draggable network diagram
 *
 * HTML div nodes positioned with CSS, connected by dynamically computed
 * SVG lines. Drag any node and all connections redraw in real-time.
 * No hardcoded SVG coordinates -- everything is computed from DOM positions.
 */
(function() {
  "use strict";

  var topoContainer = document.getElementById("topo-container");
  if (!topoContainer) return;

  // ---- Node definitions with default positions (percentage-based) ----
  var NODES = [
    // Hub-and-spoke layout: data flows left->center->right
    // Left: data sources (Honda + WiCAN stacked vertically)
    // Center: Pi hub (larger, dominant)
    // Right: output (Pixel)
    // Below center: infrastructure (SQLite + Witty Pi)
    { id: "honda",  label: "Honda Accord SE", detail: "2026 L15BE 1.5T CVT", role: "DATA SOURCE",   pctX: 1,  pctY: 3,  accent: "#a78bfa" },
    { id: "wican",  label: "WiCAN Pro",       detail: "ESP32-S3 / WiFi STA", role: "OBD BRIDGE",    pctX: 1,  pctY: 45, accent: "#f472b6" },
    { id: "pi",     label: "Raspberry Pi 4B", detail: "Trixie / Python 3.13", role: "CENTRAL HUB",  pctX: 35, pctY: 18, accent: "#34d399", isHub: true },
    { id: "pixel",  label: "Pixel 6 Pro",     detail: "Display PWA",          role: "DISPLAY OUT",   pctX: 72, pctY: 18, accent: "#38bdf8" },
    { id: "db",     label: "SQLite DB",       detail: "WAL mode",             role: "STORAGE",       pctX: 28, pctY: 64, accent: "#fbbf24" },
    { id: "witty",  label: "Witty Pi 4",      detail: "12V-5V / RTC / Sensors", role: "POWER",       pctX: 53, pctY: 64, accent: "#fb923c" },
  ];

  // ---- Connection definitions ----
  var CONNECTIONS = [
    { from: "honda", to: "wican", label: "OBD-II CAN",        id: "line-honda-wican" },
    { from: "wican", to: "pi",    label: "ELM327 TCP:3333",   id: "line-wican-pi" },
    { from: "pi",    to: "pixel", label: "WebSocket 10Hz",    id: "line-pi-pixel" },
    { from: "pi",    to: "db",    label: "WAL",               id: "line-pi-db" },
    { from: "pi",    to: "witty", label: "I2C 0x08",          id: "line-pi-witty" },
  ];

  var nodeEls = {};
  var svgEl = null;
  var dragState = null;
  var didDrag = false;

  // ---- Build the topology ----
  function build() {
    topoContainer.style.position = "relative";
    topoContainer.style.minHeight = "520px";
    topoContainer.style.userSelect = "none";
    topoContainer.style.background = "radial-gradient(ellipse at 50% 40%, #0d1117 0%, #000 70%)";
    topoContainer.style.borderRadius = "16px";
    topoContainer.style.padding = "20px";
    topoContainer.style.border = "1px solid #1a1a1a";

    // SVG layer for connection lines (behind nodes)
    svgEl = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svgEl.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;";
    // Arrowhead markers
    var defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    // Modern chevron-style arrowheads (open, not filled -- cleaner look)
    ["#eab308", "#22c55e", "#ef4444"].forEach(function(color, i) {
      var names = ["amber", "green", "red"];
      var marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
      marker.setAttribute("id", "topo-arrow-" + names[i]);
      marker.setAttribute("viewBox", "0 0 14 14");
      marker.setAttribute("refX", "12");
      marker.setAttribute("refY", "7");
      marker.setAttribute("markerWidth", "12");
      marker.setAttribute("markerHeight", "12");
      marker.setAttribute("orient", "auto");
      var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", "M2,2 L12,7 L2,12");
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", color);
      path.setAttribute("stroke-width", "2");
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-linejoin", "round");
      marker.appendChild(path);
      defs.appendChild(marker);
    });
    // Glow filter
    var filter = document.createElementNS("http://www.w3.org/2000/svg", "filter");
    filter.setAttribute("id", "topo-dot-glow");
    filter.setAttribute("x", "-50%");
    filter.setAttribute("y", "-50%");
    filter.setAttribute("width", "200%");
    filter.setAttribute("height", "200%");
    var blur = document.createElementNS("http://www.w3.org/2000/svg", "feGaussianBlur");
    blur.setAttribute("in", "SourceGraphic");
    blur.setAttribute("stdDeviation", "3");
    blur.setAttribute("result", "blur");
    filter.appendChild(blur);
    var merge = document.createElementNS("http://www.w3.org/2000/svg", "feMerge");
    var mn1 = document.createElementNS("http://www.w3.org/2000/svg", "feMergeNode");
    mn1.setAttribute("in", "blur");
    var mn2 = document.createElementNS("http://www.w3.org/2000/svg", "feMergeNode");
    mn2.setAttribute("in", "SourceGraphic");
    merge.appendChild(mn1);
    merge.appendChild(mn2);
    filter.appendChild(merge);
    defs.appendChild(filter);
    svgEl.appendChild(defs);
    topoContainer.appendChild(svgEl);

    // Create connection line elements
    CONNECTIONS.forEach(function(conn) {
      // Main line
      var line = document.createElementNS("http://www.w3.org/2000/svg", "path");
      line.setAttribute("id", conn.id);
      line.setAttribute("fill", "none");
      line.setAttribute("stroke", "#eab308");
      line.setAttribute("stroke-width", "1.5");
      line.setAttribute("stroke-linecap", "round");
      line.setAttribute("marker-end", "url(#topo-arrow-amber)");
      line.style.transition = "stroke 0.5s ease, opacity 0.5s ease";
      line.style.opacity = "0.3";
      svgEl.appendChild(line);

      // Label background
      var labelBg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      labelBg.setAttribute("fill", "#000");
      labelBg.setAttribute("opacity", "0.85");
      labelBg.setAttribute("rx", "4");
      labelBg.setAttribute("data-label-bg", conn.id);
      svgEl.appendChild(labelBg);

      // Label text
      var label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("data-label", conn.id);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("fill", "#aaa");
      label.setAttribute("font-family", "'JetBrains Mono', monospace");
      label.setAttribute("font-size", "13");
      label.setAttribute("font-weight", "500");
      label.textContent = conn.label;
      svgEl.appendChild(label);

      // Breathing glow line (overlays the base line with animated opacity)
      var glowLine = document.createElementNS("http://www.w3.org/2000/svg", "path");
      glowLine.setAttribute("fill", "none");
      glowLine.setAttribute("stroke", "#eab308");
      glowLine.setAttribute("stroke-width", "4");
      glowLine.setAttribute("stroke-linecap", "round");
      glowLine.setAttribute("filter", "url(#topo-dot-glow)");
      glowLine.setAttribute("data-glow", conn.id);
      glowLine.style.opacity = "0";
      glowLine.style.transition = "stroke 0.3s";
      svgEl.appendChild(glowLine);
    });

    // Create HTML node elements
    NODES.forEach(function(node) {
      var div = document.createElement("div");
      div.className = "topo-node";
      div.setAttribute("data-device", node.id);
      div.style.left = node.pctX + "%";
      div.style.top = node.pctY + "%";
      // Unique accent color per node
      var c = node.accent;
      div.style.borderColor = c + "60";
      div.style.background = "linear-gradient(145deg, " + c + "0a 0%, #0a0a0a 50%)";
      div.style.boxShadow = "0 0 20px " + c + "0d, 0 4px 12px rgba(0,0,0,0.5)";
      // Hub node is bigger
      if (node.isHub) {
        div.style.width = "20%";
        div.style.minWidth = "180px";
        div.style.borderWidth = "2px";
        div.style.borderColor = c + "80";
        div.style.boxShadow = "0 0 30px " + c + "18, 0 0 60px " + c + "08, 0 4px 16px rgba(0,0,0,0.6)";
      }

      // Icon + role row
      var topRow = document.createElement("div");
      topRow.style.cssText = "display:flex;align-items:center;gap:6px;margin-bottom:6px;height:22px;";

      var iconSvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      iconSvg.setAttribute("viewBox", "0 0 24 24");
      iconSvg.setAttribute("width", "22");
      iconSvg.setAttribute("height", "22");
      iconSvg.setAttribute("class", "topo-node-icon");
      iconSvg.style.cssText = "flex-shrink:0;opacity:0.8;color:" + node.accent + ";transition:opacity 0.3s;";
      var iconPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      iconPath.setAttribute("fill", "none");
      iconPath.setAttribute("stroke", "currentColor");
      iconPath.setAttribute("stroke-width", "1.5");
      iconPath.setAttribute("stroke-linecap", "round");
      iconPath.setAttribute("stroke-linejoin", "round");
      // Modern minimal outline icons
      var icons = {
        honda: "M5 17a2 2 0 104 0 2 2 0 10-4 0M15 17a2 2 0 104 0 2 2 0 10-4 0M5 15h14l-2-6H7l-2 6z",
        wican: "M12 20h.01M8.53 16.11a6 6 0 016.95 0M5 12.55a11 11 0 0114.08 0M1.42 9a16 16 0 0121.16 0",
        pi: "M6 6h12v12H6zM9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3",
        pixel: "M7 2h10a1 1 0 011 1v18a1 1 0 01-1 1H7a1 1 0 01-1-1V3a1 1 0 011-1zM12 18h.01",
        db: "M4 7c0-1.66 3.58-3 8-3s8 1.34 8 3v10c0 1.66-3.58 3-8 3s-8-1.34-8-3V7zM4 12c0 1.66 3.58 3 8 3s8-1.34 8-3",
        witty: "M13 2L3 14h9l-1 8 10-12h-9l1-8",
      };
      iconPath.setAttribute("d", icons[node.id] || icons.pi);
      iconSvg.appendChild(iconPath);
      topRow.appendChild(iconSvg);

      var role = document.createElement("div");
      role.className = "topo-node-role";
      role.textContent = node.role;
      role.style.color = node.accent;
      role.style.opacity = "0.7";
      topRow.appendChild(role);
      div.appendChild(topRow);

      var name = document.createElement("div");
      name.className = "topo-node-name";
      name.textContent = node.label;
      div.appendChild(name);

      var detail = document.createElement("div");
      detail.className = "topo-node-detail";
      detail.id = node.id === "db" ? "db-size-label" : "";
      detail.textContent = node.detail;
      div.appendChild(detail);

      var badge = document.createElement("div");
      badge.className = "topo-node-badge";
      badge.id = "badge-" + node.id;
      badge.textContent = "SIMULATED";
      badge.style.cssText = "background:" + c + "15;color:" + c + ";border-color:" + c + "40;";
      div.appendChild(badge);

      topoContainer.appendChild(div);
      nodeEls[node.id] = div;

      // Drag handling
      div.addEventListener("mousedown", startDrag);
      div.addEventListener("touchstart", startDrag, { passive: false });
    });

    // Reset button
    addResetButton();

    // Initial line draw (slight delay so DOM has rendered node sizes)
    setTimeout(updateLines, 50);

    // Breathing glow animation
    requestAnimationFrame(animateGlow);
  }

  // ---- Get center point of a node element ----
  function getNodeCenter(id) {
    var el = nodeEls[id];
    if (!el) return { x: 0, y: 0 };
    var containerRect = topoContainer.getBoundingClientRect();
    var nodeRect = el.getBoundingClientRect();
    return {
      x: nodeRect.left - containerRect.left + nodeRect.width / 2,
      y: nodeRect.top - containerRect.top + nodeRect.height / 2,
    };
  }

  // ---- Get edge point (where line exits the node box) ----
  function getEdgePoint(fromId, toId) {
    var from = getNodeCenter(fromId);
    var to = getNodeCenter(toId);
    var el = nodeEls[fromId];
    var containerRect = topoContainer.getBoundingClientRect();
    var r = el.getBoundingClientRect();
    var hw = r.width / 2, hh = r.height / 2;
    var dx = to.x - from.x, dy = to.y - from.y;
    var angle = Math.atan2(dy, dx);

    // Find intersection with rectangle border + 10px gap
    var cos = Math.cos(angle), sin = Math.sin(angle);
    var sx = cos !== 0 ? hw / Math.abs(cos) : Infinity;
    var sy = sin !== 0 ? hh / Math.abs(sin) : Infinity;
    var s = Math.min(sx, sy) + 10;
    return { x: from.x + cos * s, y: from.y + sin * s };
  }

  // ---- Update all SVG connection lines ----
  function updateLines() {
    var containerRect = topoContainer.getBoundingClientRect();
    var svgW = containerRect.width, svgH = containerRect.height;
    svgEl.setAttribute("viewBox", "0 0 " + svgW + " " + svgH);

    CONNECTIONS.forEach(function(conn) {
      var p1 = getEdgePoint(conn.from, conn.to);
      var p2 = getEdgePoint(conn.to, conn.from);

      var mx = (p1.x + p2.x) / 2, my = (p1.y + p2.y) / 2;
      var dx = p2.x - p1.x, dy = p2.y - p1.y;

      // Straight lines -- no curves
      var cx = mx, cy = my;

      var pathD = "M " + p1.x.toFixed(1) + "," + p1.y.toFixed(1) +
                  " L " + p2.x.toFixed(1) + "," + p2.y.toFixed(1);

      var line = document.getElementById(conn.id);
      if (line) line.setAttribute("d", pathD);

      // Update glow overlay line to match
      var glowEl = svgEl.querySelector('[data-glow="' + conn.id + '"]');
      if (glowEl) glowEl.setAttribute("d", pathD);

      // Store path data for dot animation
      conn._p1 = p1;
      conn._p2 = p2;
      conn._cx = cx;
      conn._cy = cy;

      // Update label position (midpoint of the curve, offset above the highest point)
      var labelEl = svgEl.querySelector('[data-label="' + conn.id + '"]');
      var labelBg = svgEl.querySelector('[data-label-bg="' + conn.id + '"]');
      if (labelEl) {
        var lx = mx;
        // For mostly-vertical lines, offset label to the right; otherwise above
        var isVertical = Math.abs(dy) > Math.abs(dx) * 1.5;
        var ly;
        if (isVertical) {
          lx = Math.max(p1.x, p2.x) + 20;
          ly = my + 5;
        } else {
          ly = Math.min(p1.y, p2.y, cy) - 14;
        }
        labelEl.setAttribute("x", lx.toFixed(1));
        labelEl.setAttribute("y", ly.toFixed(1));

        if (labelBg) {
          var textLen = conn.label.length * 8 + 16;
          labelBg.setAttribute("x", (lx - textLen / 2).toFixed(1));
          labelBg.setAttribute("y", (ly - 14).toFixed(1));
          labelBg.setAttribute("width", String(textLen));
          labelBg.setAttribute("height", "20");
        }
      }
    });
  }

  // ---- Breathing glow animation on connection lines ----
  var glowTime = 0;
  function animateGlow() {
    glowTime += 0.016;
    CONNECTIONS.forEach(function(conn, idx) {
      var glowEl = svgEl.querySelector('[data-glow="' + conn.id + '"]');
      if (!glowEl) return;
      // Each connection breathes on a different phase (staggered by index)
      var phase = glowTime * 0.6 + idx * 1.3;
      // Stronger glow so it's clearly visible
      var opacity = 0.15 + Math.sin(phase) * 0.12;
      glowEl.style.opacity = opacity.toFixed(3);
    });
    requestAnimationFrame(animateGlow);
  }

  // ---- Drag handling ----
  function startDrag(e) {
    e.preventDefault();
    var node = e.currentTarget;
    var containerRect = topoContainer.getBoundingClientRect();
    var nodeRect = node.getBoundingClientRect();

    var clientX = e.touches ? e.touches[0].clientX : e.clientX;
    var clientY = e.touches ? e.touches[0].clientY : e.clientY;

    didDrag = false;
    dragState = {
      node: node,
      offsetX: clientX - nodeRect.left,
      offsetY: clientY - nodeRect.top,
      containerRect: containerRect,
      startX: clientX,
      startY: clientY,
    };

    node.style.zIndex = "5";
    node.style.cursor = "grabbing";
    node.style.transition = "none";

    document.addEventListener("mousemove", onDrag);
    document.addEventListener("mouseup", endDrag);
    document.addEventListener("touchmove", onDrag, { passive: false });
    document.addEventListener("touchend", endDrag);
  }

  function onDrag(e) {
    if (!dragState) return;
    e.preventDefault();

    var clientX = e.touches ? e.touches[0].clientX : e.clientX;
    var clientY = e.touches ? e.touches[0].clientY : e.clientY;

    // Only count as drag if moved more than 5px (prevents accidental drag on click)
    var dx = clientX - dragState.startX, dy = clientY - dragState.startY;
    if (!didDrag && Math.abs(dx) < 5 && Math.abs(dy) < 5) return;
    didDrag = true;

    var cr = dragState.containerRect;
    var x = clientX - cr.left - dragState.offsetX;
    var y = clientY - cr.top - dragState.offsetY;

    // Clamp to container
    var nodeW = dragState.node.offsetWidth;
    var nodeH = dragState.node.offsetHeight;
    x = Math.max(0, Math.min(cr.width - nodeW, x));
    y = Math.max(0, Math.min(cr.height - nodeH, y));

    dragState.node.style.left = x + "px";
    dragState.node.style.top = y + "px";

    updateLines();
  }

  function endDrag() {
    if (dragState) {
      dragState.node.style.zIndex = "";
      dragState.node.style.cursor = "grab";
      dragState.node.style.transition = "";
      dragState = null;
    }
    document.removeEventListener("mousemove", onDrag);
    document.removeEventListener("mouseup", endDrag);
    document.removeEventListener("touchmove", onDrag);
    document.removeEventListener("touchend", endDrag);
  }

  // Rebuild lines on resize
  var resizeTimer;
  window.addEventListener("resize", function() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(updateLines, 100);
  });

  // ---- Node click -> detail panel (only if not dragging) ----
  topoContainer.addEventListener("click", function(e) {
    var node = e.target.closest("[data-device]");
    if (!node) return;
    // If user just finished dragging, don't open panel
    if (didDrag) { didDrag = false; return; }
    var device = node.getAttribute("data-device");
    document.dispatchEvent(new CustomEvent("topo-node-click", { detail: { device: device } }));
  });

  // ---- Reset button ----
  function addResetButton() {
    var btn = document.createElement("button");
    btn.textContent = "Reset Layout";
    btn.style.cssText = "position:absolute;top:8px;right:8px;z-index:5;padding:6px 14px;font-size:12px;font-weight:500;font-family:Inter,sans-serif;color:#888;background:#0a0a0a;border:1px solid #1a1a1a;border-radius:6px;cursor:pointer;transition:all 0.15s;";
    btn.addEventListener("mouseenter", function() { btn.style.color = "#fff"; btn.style.borderColor = "#333"; });
    btn.addEventListener("mouseleave", function() { btn.style.color = "#888"; btn.style.borderColor = "#1a1a1a"; });
    btn.addEventListener("click", function() {
      // Animate nodes back to default positions with smooth CSS transitions
      NODES.forEach(function(node) {
        var el = nodeEls[node.id];
        if (el) {
          el.style.transition = "left 0.5s cubic-bezier(0.16, 1, 0.3, 1), top 0.5s cubic-bezier(0.16, 1, 0.3, 1)";
          el.style.left = node.pctX + "%";
          el.style.top = node.pctY + "%";
        }
      });
      // Update lines continuously during the animation
      var startTime = performance.now();
      function animateReset(now) {
        updateLines();
        if (now - startTime < 550) requestAnimationFrame(animateReset);
        else {
          // Clean up transitions
          NODES.forEach(function(node) {
            var el = nodeEls[node.id];
            if (el) el.style.transition = "";
          });
        }
      }
      requestAnimationFrame(animateReset);
    });
    topoContainer.appendChild(btn);
  }

  // ---- Public API for diagnostics.js ----
  window.runeTopology = {
    updateLines: updateLines,
    setNodeStatus: function(nodeId, status) {
      var el = nodeEls[nodeId];
      if (!el) return;
      el.classList.remove("status-connected", "status-simulated", "status-disconnected");
      el.classList.add("status-" + status);
      var badge = document.getElementById("badge-" + nodeId);
      if (badge) {
        badge.textContent = status === "connected" ? "CONNECTED" : status === "simulated" ? "SIMULATED" : "OFFLINE";
        badge.className = "topo-node-badge " + status;
      }
    },
    setLineStatus: function(lineId, status) {
      var line = document.getElementById(lineId);
      if (!line) return;
      var colors = { connected: "#22c55e", simulated: "#eab308", disconnected: "#ef4444" };
      var arrows = { connected: "url(#topo-arrow-green)", simulated: "url(#topo-arrow-amber)", disconnected: "url(#topo-arrow-red)" };
      line.setAttribute("stroke", colors[status] || "#eab308");
      line.setAttribute("marker-end", arrows[status] || "url(#topo-arrow-amber)");
      line.style.opacity = status === "disconnected" ? "0.15" : "0.3";
      // Update glow line color
      var glowEl = svgEl.querySelector('[data-glow="' + lineId + '"]');
      if (glowEl) {
        glowEl.setAttribute("stroke", colors[status] || "#eab308");
      }
    },
  };

  build();
})();
