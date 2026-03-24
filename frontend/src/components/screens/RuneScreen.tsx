import { useRef, useEffect, useState, useCallback } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { useUiStore } from "@/stores/uiStore";
import { useSettingsStore } from "@/stores/settingsStore";
import { useRuneVoice } from "@/hooks/useRuneVoice";
import { LiveGraph } from "@/components/hud/LiveGraph";
import { OfflineIndicator } from "@/components/hud/OfflineIndicator";

// TRACE MATRIX -- mosaic of live waveforms + Warm Gold hero strip.
// Shows ONLY OBD-II data the Honda dash doesn't.
//
// Derived metrics (computed, not raw):
//   - Cost per mile: fuel_rate * gas_price / speed
//   - STFT Volatility: rolling stddev of STFT over 60s (leading health indicator)
//   - Warmup Progress: composite of coolant/oil/catalyst vs operating temps

// --- Warm Gold hero palette ---
const HERO = "#c9952a";
const HERO_BRIGHT = "#f0e2c8";
const HERO_DIM = "rgba(201,149,42,0.3)";
const HERO_BORDER = "rgba(201,149,42,0.08)";
// --- Severity colors ---
const WARN_COLOR = "#f59e0b";
const CRIT_COLOR = "#ef4444";

// Rolling stddev helper -- maintains a circular buffer
function rollingStdDev(buf: number[], len: number): number {
  if (buf.length < 10) return 0;
  const n = Math.min(buf.length, len);
  const slice = buf.slice(-n);
  const mean = slice.reduce((a, b) => a + b, 0) / n;
  const variance = slice.reduce((a, v) => a + (v - mean) ** 2, 0) / n;
  return Math.sqrt(variance);
}

// Warmup progress: composite of temps vs Honda operating minimums
// Sources: PRD Section 8 (coolant 82C), Honda L15BE oil ~90C, EPA catalyst light-off 400C
function warmupProgress(coolant: number, oil: number, catalyst: number): number {
  // Clamp to 0 -- cold climate starts can have negative temps (e.g. -20C coolant)
  const coolantPct = Math.max(0, Math.min(coolant / 82, 1));   // 82C = Honda normal operating min
  const oilPct = Math.max(0, Math.min(oil / 90, 1));            // 90C = normal operating min
  const catalystPct = Math.max(0, Math.min(catalyst / 400, 1));  // 400C = catalyst light-off temp
  // Weighted: coolant most important (engine protection), oil (lubrication), catalyst (emissions)
  return Math.round((coolantPct * 0.5 + oilPct * 0.3 + catalystPct * 0.2) * 100);
}

export function RuneScreen() {
  const refs = useRef<Record<string, HTMLSpanElement | null>>({});
  const stftBuffer = useRef<number[]>([]);  // rolling STFT for volatility calc
  const isActive = useUiStore((s) => s.activeScreen === "rune");

  const voice = useRuneVoice();
  const [dv, setDv] = useState("");
  const [vo, setVo] = useState(0);
  const pv = useRef("");
  useEffect(() => {
    if (!voice.message || voice.message === pv.current) return;
    pv.current = voice.message; setVo(0);
    const t = setTimeout(() => { setDv(voice.message); setVo(1); }, 300);
    return () => clearTimeout(t);
  }, [voice.message]);
  useEffect(() => { if (voice.message && !dv) { setDv(voice.message); setTimeout(() => setVo(1), 150); } }, [voice.message, dv]);

  // Imperative updates for hero strip (10Hz, no React re-renders)
  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const s = state.sensors, h = state.health;
      const set = (id: string, txt: string, color?: string) => {
        const el = refs.current[id]; if (el) { el.textContent = txt; if (color) el.style.color = color; }
      };

      // Hero MPG / GPH
      const speed = s["SPEED"]?.v ?? 0;
      const speedMph = speed * 0.621371;
      if (speed > 2) { set("fuel", state.fuel.instant_mpg?.toFixed(1) ?? "--", HERO_BRIGHT); set("fuelLbl", "MPG"); }
      else { set("fuel", state.fuel.idle_gph?.toFixed(2) ?? "--", HERO); set("fuelLbl", "GPH"); }

      // Basic stats
      set("cost", `$${state.fuel.trip_cost_usd.toFixed(2)}`);
      set("trip", `${state.fuel.trip_distance_mi.toFixed(1)}mi`);
      set("tank", `${Math.round(s["FUEL_LEVEL"]?.v ?? 0)}%`, (s["FUEL_LEVEL"]?.v ?? 100) < 15 ? WARN_COLOR : HERO);

      // --- DERIVED: Cost per mile ---
      // When moving: gasPrice / instantMpg (miles per dollar inverted)
      // idle_gph is null when moving (backend only sets it at speed=0)
      const gasPrice = useSettingsStore.getState().gasPricePerGallon;
      const instantMpg = state.fuel.instant_mpg;
      if (speedMph > 3 && instantMpg && instantMpg > 0) {
        const cpm = gasPrice / instantMpg;
        set("cpm", `$${cpm.toFixed(2)}`, cpm > 0.20 ? WARN_COLOR : HERO);
      } else {
        set("cpm", "--", HERO_DIM);
      }

      // --- DERIVED: STFT Volatility (rolling stddev over 60s = 600 samples at 10Hz) ---
      // High stddev = ECU hunting = leading indicator of problems
      // Sources: Innova fuel trim analysis, Foxwell diagnostic guide
      const stft = s["STFT"]?.v ?? 0;
      stftBuffer.current.push(stft);
      if (stftBuffer.current.length > 600) stftBuffer.current.shift();
      const sigma = rollingStdDev(stftBuffer.current, 600);
      // <2% = stable (green), 2-5% = active (gold), >5% = hunting (red)
      const sigmaColor = sigma > 5 ? CRIT_COLOR : sigma > 2 ? WARN_COLOR : "#4ade80";
      set("sigma", `${sigma.toFixed(1)}%`, sigmaColor);

      // --- DERIVED: Warmup Progress ---
      // Composite of coolant/oil/catalyst vs Honda operating minimums
      const coolant = s["COOLANT_TEMP"]?.v ?? 0;
      const oil = s["OIL_TEMP"]?.v ?? 0;
      const catalyst = s["CATALYST_TEMP"]?.v ?? 0;
      const warmup = warmupProgress(coolant, oil, catalyst);
      if (warmup >= 100) {
        set("warm", "RDY", "#4ade80");
      } else {
        set("warm", `${warmup}%`, warmup < 50 ? "rgba(255,255,255,0.4)" : HERO);
      }

      // Health
      const ho = h.overall;
      set("health", ho === -1 ? "--" : String(Math.round(ho)),
        ho === -1 ? "rgba(255,255,255,0.3)" : ho < 50 ? CRIT_COLOR : ho < 70 ? WARN_COLOR : "#4ade80");
    });
    return () => { unsub(); };
  }, []);

  const r = (id: string) => (el: HTMLSpanElement | null) => { refs.current[id] = el; };

  // --- Dynamic severity color functions per sensor ---
  const stftColor = useCallback((v: number) => {
    const a = Math.abs(v);
    return a > 10 ? CRIT_COLOR : a > 5 ? WARN_COLOR : "#4ade80";
  }, []);
  const ltftColor = useCallback((v: number) => {
    // Honda ECU adaptation limit: ±10% is critical, ±5% is warn
    const a = Math.abs(v);
    return a > 10 ? CRIT_COLOR : a > 5 ? WARN_COLOR : a > 3 ? "#e2a73a" : "#c9952a";
  }, []);
  const mafColor = useCallback((v: number) =>
    v > 30 ? CRIT_COLOR : v > 20 ? WARN_COLOR : "#a78bfa", []);
  const loadColor = useCallback((v: number) =>
    v > 85 ? CRIT_COLOR : v > 60 ? WARN_COLOR : "#60a5fa", []);
  const throttleColor = useCallback((v: number) =>
    v > 80 ? CRIT_COLOR : v > 50 ? WARN_COLOR : "#34d399", []);
  const catalystColor = useCallback((v: number) =>
    v > 900 ? CRIT_COLOR : v > 800 ? "#ef8844" : "#f59e0b", []);
  const oilColor = useCallback((v: number) =>
    v > 135 ? CRIT_COLOR : v > 120 ? WARN_COLOR : v < 60 ? "#94a3b8" : "#fb923c", []);
  const batteryColor = useCallback((v: number) =>
    v < 12.4 || v > 15.5 ? CRIT_COLOR : v < 13 || v > 15 ? WARN_COLOR : "#38bdf8", []);
  const mapColor = useCallback((v: number) =>
    v > 95 ? WARN_COLOR : v < 15 ? "#60a5fa" : "#94a3b8", []);

  return (
    <div style={S.screen}>
      <OfflineIndicator />
      {/* LEFT: Warm Gold hero strip -- driver side, closest to eyes */}
      <div style={S.hero}>
        <div style={S.heroBlock}>
          <span ref={r("fuel")} style={S.heroVal}>--</span>
          <span ref={r("fuelLbl")} style={S.heroUnit}>MPG</span>
        </div>
        <div style={S.statsBlock}>
          <div style={S.stat}><span style={S.statLabel}>COST</span><span ref={r("cost")} style={S.statVal}>--</span></div>
          <div style={S.stat}><span style={S.statLabel}>TRIP</span><span ref={r("trip")} style={S.statVal}>--</span></div>
          <div style={S.stat}><span style={S.statLabel}>$/MI</span><span ref={r("cpm")} style={S.statVal}>--</span></div>
          <div style={S.stat}><span style={S.statLabel}>TANK</span><span ref={r("tank")} style={S.statVal}>--</span></div>
        </div>
        {/* Derived indicators */}
        <div style={S.derivedBlock}>
          <div style={S.derivedRow}>
            <span style={S.derivedLabel}>TRIM&sigma;</span>
            <span ref={r("sigma")} style={S.derivedVal}>--</span>
          </div>
          <div style={S.derivedRow}>
            <span style={S.derivedLabel}>WARM</span>
            <span ref={r("warm")} style={S.derivedVal}>--</span>
          </div>
        </div>
        <div style={S.healthBadge}>
          <span ref={r("health")} style={S.healthScore}>--</span>
          <span style={S.healthLabel}>HEALTH</span>
        </div>
        {/* Voice */}
        <div style={S.voiceRow}>
          <div style={S.voiceDot} />
          <span style={{ ...S.voiceText, opacity: vo }}>{dv || "Listening..."}</span>
        </div>
      </div>

      {/* RIGHT: Trace mosaic */}
      <div style={S.mosaic}>
        <div style={S.row}>
          <div style={{ ...S.cell, flex: 2 }}>
            <LiveGraph label="FUEL TRIM (SHORT)" unit="%" sensorKey="STFT" min={-20} max={20} getColor={stftColor} labelColor="rgba(74,222,128,0.35)" zeroLine={0} active={isActive} />
          </div>
          <div style={S.cell}>
            <LiveGraph label="FUEL TRIM (LONG)" unit="%" sensorKey="LTFT" min={-20} max={20} getColor={ltftColor} labelColor="rgba(201,149,42,0.35)" zeroLine={0} active={isActive} />
          </div>
        </div>
        <div style={S.row}>
          <div style={S.cell}>
            <LiveGraph label="MAF AIRFLOW" unit="g/s" sensorKey="MAF" min={0} max={30} getColor={mafColor} labelColor="rgba(167,139,250,0.35)" active={isActive} />
          </div>
          <div style={S.cell}>
            <LiveGraph label="ENGINE LOAD" unit="%" sensorKey="ENGINE_LOAD" min={0} max={100} getColor={loadColor} labelColor="rgba(96,165,250,0.35)" active={isActive} />
          </div>
          <div style={S.cell}>
            <LiveGraph label="THROTTLE" unit="%" sensorKey="THROTTLE_POS" min={0} max={100} getColor={throttleColor} labelColor="rgba(52,211,153,0.35)" active={isActive} />
          </div>
        </div>
        <div style={S.row}>
          <div style={S.cell}>
            <LiveGraph label="CATALYST" unit="C" sensorKey="CATALYST_TEMP" min={50} max={950} getColor={catalystColor} labelColor="rgba(245,158,11,0.35)" active={isActive} />
          </div>
          <div style={S.cell}>
            <LiveGraph label="OIL TEMP" unit="C" sensorKey="OIL_TEMP" min={10} max={140} getColor={oilColor} labelColor="rgba(251,146,60,0.35)" active={isActive} />
          </div>
          <div style={S.cell}>
            <LiveGraph label="BATTERY" unit="V" sensorKey="BATTERY_V" min={11.5} max={15.5} getColor={batteryColor} labelColor="rgba(56,189,248,0.35)" active={isActive} />
          </div>
          <div style={S.cell}>
            <LiveGraph label="INTAKE MAP" unit="kPa" sensorKey="MAP" min={20} max={105} getColor={mapColor} labelColor="rgba(148,163,184,0.35)" active={isActive} />
          </div>
        </div>
      </div>
    </div>
  );
}

const MONO = "'JetBrains Mono', 'SF Mono', monospace";

const S = {
  screen: {
    width: "100%", height: "100%", background: "#000",
    display: "flex", overflow: "hidden", fontFamily: MONO,
  },

  // Warm Gold hero strip
  hero: {
    width: "150px", flexShrink: 0, display: "flex", flexDirection: "column" as const,
    padding: "10px 14px", justifyContent: "center" as const, gap: "4px",
    borderRight: `1px solid ${HERO_BORDER}`,
  },
  heroBlock: { textAlign: "center" as const, marginBottom: "2px" },
  heroVal: {
    display: "block", fontSize: 48, fontWeight: 700, color: HERO_BRIGHT,
    lineHeight: 1, fontVariantNumeric: "tabular-nums" as const,
    textShadow: `0 0 20px rgba(201,149,42,0.15)`,
  },
  heroUnit: { display: "block", fontSize: 14, color: "rgba(201,149,42,0.35)", letterSpacing: "0.1em" },

  statsBlock: { display: "flex", flexDirection: "column" as const },
  stat: {
    display: "flex", justifyContent: "space-between" as const, padding: "3px 0",
    borderBottom: `1px solid ${HERO_BORDER}`,
  },
  statLabel: { fontSize: 13, color: HERO_DIM, letterSpacing: "0.04em" },
  statVal: { fontSize: 16, fontWeight: 600, color: HERO, fontVariantNumeric: "tabular-nums" as const, transition: "color 200ms" },

  // Derived metrics section
  derivedBlock: {
    display: "flex", flexDirection: "column" as const, gap: "2px",
    padding: "4px 0", borderTop: `1px solid ${HERO_BORDER}`,
  },
  derivedRow: {
    display: "flex", justifyContent: "space-between" as const, alignItems: "center" as const,
    padding: "2px 0",
  },
  derivedLabel: { fontSize: 12, color: "rgba(255,255,255,0.2)", letterSpacing: "0.04em" },
  derivedVal: { fontSize: 16, fontWeight: 700, fontVariantNumeric: "tabular-nums" as const, transition: "color 300ms" },

  healthBadge: {
    textAlign: "center" as const, padding: "4px", borderRadius: "8px",
    background: "rgba(74,222,128,0.04)", border: "1px solid rgba(74,222,128,0.1)",
  },
  healthScore: { display: "block", fontSize: 24, fontWeight: 700, color: "#4ade80", transition: "color 300ms" },
  healthLabel: { display: "block", fontSize: 12, color: "rgba(255,255,255,0.25)", letterSpacing: "0.08em" },

  voiceRow: {
    display: "flex", alignItems: "flex-start" as const, gap: "6px", paddingTop: "4px",
    borderTop: `1px solid ${HERO_BORDER}`, marginTop: "auto",
  },
  voiceDot: {
    width: 5, height: 5, borderRadius: "50%", background: HERO, flexShrink: 0, marginTop: 3,
    boxShadow: `0 0 6px rgba(201,149,42,0.4)`,
    animation: "pulse-voice 2s ease-in-out infinite",
  },
  voiceText: { fontSize: 12, color: "rgba(240,226,200,0.4)", fontFamily: "'Inter',sans-serif", transition: "opacity 400ms" },

  // Trace mosaic
  mosaic: {
    flex: 1, display: "flex", flexDirection: "column" as const,
    padding: "6px 8px", gap: "3px",
  },
  row: { flex: 1, display: "flex", gap: "3px", minHeight: 0 },
  cell: { flex: 1, minHeight: 0, display: "flex" },
} as const;
