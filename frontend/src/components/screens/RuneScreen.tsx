import { useRef, useEffect, useState, useCallback } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { useRuneVoice } from "@/hooks/useRuneVoice";
import { LiveGraph } from "@/components/hud/LiveGraph";

// Cockpit Gauges layout. Warm premium palette.
// Left: circular gauge instruments. Center: hero data + waveforms. Right: sensor list.

const WARM = "#c9952a";   // gold - primary accent
const CREAM = "#f0e2c8";  // warm white - data values
const COPPER = "#b87a3d";  // copper - secondary
const DIM = "rgba(201,149,42,0.25)"; // dim gold for labels
const BORDER = "rgba(201,149,42,0.08)";
const GLASS = "rgba(201,149,42,0.03)";
const WARN = "#ea580c";   // orange warning
const CRIT = "#c53030";   // red critical

function tc(v: number, wH: number, cH: number) { return v >= cH ? CRIT : v >= wH ? WARN : WARM; }
function ftc(v: number) { return Math.abs(v) > 15 ? CRIT : Math.abs(v) > 8 ? WARN : WARM; }

export function RuneScreen() {
  const refs = useRef<Record<string, HTMLSpanElement | null>>({});
  const arcRefs = useRef<Record<string, SVGCircleElement | null>>({});
  const barsRef = useRef<Record<string, HTMLDivElement | null>>({});
  // Graph buffers managed by LiveGraph components

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

  const GR = 24, GC = 2 * Math.PI * GR, GA = (240 / 360) * GC;

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const s = state.sensors, h = state.health;
      const set = (id: string, txt: string, color?: string) => {
        const el = refs.current[id]; if (el) { el.textContent = txt; if (color) el.style.color = color; }
      };
      const setArc = (id: string, pct: number, color: string) => {
        const el = arcRefs.current[id]; if (el) {
          el.style.strokeDashoffset = String(GA - (Math.min(pct, 1)) * GA);
          el.style.stroke = color;
        }
      };
      const bar = (id: string, pct: number, c?: string) => {
        const el = barsRef.current[id]; if (el) { el.style.width = `${pct}%`; if (c) el.style.background = c; }
      };

      // Health gauge
      const ho = h.overall;
      set("health", ho === -1 ? "--" : String(Math.round(ho)), ho < 50 ? CRIT : ho < 70 ? WARN : CREAM);
      setArc("healthArc", ho === -1 ? 0 : ho / 100, ho < 50 ? CRIT : ho < 70 ? WARN : WARM);

      // Temperature gauges
      const gauges: [string, string, number, number][] = [
        ["oil", "OIL_TEMP", 120, 135],
        ["cvt", "CVT_TEMP", 110, 125],
        ["cool", "COOLANT_TEMP", 100, 110],
        ["cat", "CATALYST_TEMP", 800, 900],
      ];
      gauges.forEach(([id, key, wH, cH]) => {
        const v = s[key]?.v ?? 0;
        const maxT = id === "cat" ? 1000 : 150;
        set(id, `${Math.round(v)}°`, tc(v, wH, cH));
        setArc(`${id}Arc`, v / maxT, tc(v, wH, cH));
      });

      // Center data
      const speed = s["SPEED"]?.v ?? 0;
      if (speed > 2) { set("fuel", state.fuel.instant_mpg?.toFixed(1) ?? "--", CREAM); set("fuelLbl", "INSTANT MPG"); }
      else { set("fuel", state.fuel.idle_gph?.toFixed(2) ?? "--", WARM); set("fuelLbl", "GALLONS / HOUR"); }

      const load = s["ENGINE_LOAD"]?.v ?? 0;
      const throttle = s["THROTTLE_POS"]?.v ?? 0;
      set("load", `${Math.round(load)}%`); bar("loadBar", load, load > 85 ? WARN : WARM);
      set("throttle", `${Math.round(throttle)}%`); bar("throttleBar", throttle);

      // Strip data
      const stft = s["STFT"]?.v ?? 0; set("stft", `${stft >= 0 ? "+" : ""}${stft.toFixed(1)}%`, ftc(stft));
      const ltft = s["LTFT"]?.v ?? 0; set("ltft", `${ltft >= 0 ? "+" : ""}${ltft.toFixed(1)}%`, ftc(ltft));
      set("rpm", Math.round(s["RPM"]?.v ?? 0).toLocaleString());
      set("maf", (s["MAF"]?.v ?? 0).toFixed(1));
      set("map", String(Math.round(s["MAP"]?.v ?? 0)));
      set("intake", `${Math.round(s["INTAKE_TEMP"]?.v ?? 0)}°`);
      set("volts", (s["BATTERY_V"]?.v ?? 0).toFixed(1), (s["BATTERY_V"]?.v ?? 14) < 12.4 ? WARN : CREAM);
      set("tank", `${Math.round(s["FUEL_LEVEL"]?.v ?? 0)}%`, (s["FUEL_LEVEL"]?.v ?? 100) < 15 ? WARN : CREAM);
      set("cost", `$${state.fuel.trip_cost_usd.toFixed(2)}`);
      set("dist", `${state.fuel.trip_distance_mi.toFixed(1)}mi`);
      const gph = state.fuel.idle_gph ?? 0;
      set("rate", `${(gph * 350 / 60).toFixed(1)}¢/m`);

      // Graph data handled by LiveGraph components
    });

    return () => { unsub(); };
  }, [GA]);

  // Dynamic color functions: value -> color based on severity
  const throttleColor = useCallback((v: number) => v > 80 ? "#ef4444" : v > 50 ? "#ea580c" : v > 20 ? "#c9952a" : "#4ade80", []);
  const loadColor = useCallback((v: number) => v > 85 ? "#ef4444" : v > 60 ? "#ea580c" : v > 30 ? "#c9952a" : "#60a5fa", []);
  const mafColor = useCallback((v: number) => v > 20 ? "#ea580c" : v > 10 ? "#c9952a" : "#a78bfa", []);
  const coolantColor = useCallback((v: number) => v > 110 ? "#ef4444" : v > 100 ? "#ea580c" : v > 60 ? "#38bdf8" : "#60a5fa", []);

  const r = (id: string) => (el: HTMLSpanElement | null) => { refs.current[id] = el; };
  const ra = (id: string) => (el: SVGCircleElement | null) => { arcRefs.current[id] = el; };
  const rb = (id: string) => (el: HTMLDivElement | null) => { barsRef.current[id] = el; };

  // Mini gauge component
  const Gauge = ({ id, label }: { id: string; label: string }) => (
    <div style={S.gauge}>
      <div style={S.gaugeRing}>
        <svg viewBox="0 0 56 56" style={{ width: 52, height: 52 }}>
          <circle cx="28" cy="28" r={GR} fill="none" stroke="rgba(201,149,42,0.06)" strokeWidth="3"
            strokeDasharray={`${GA} ${GC}`} strokeLinecap="round" transform="rotate(150 28 28)" />
          <circle ref={ra(`${id}Arc`)} cx="28" cy="28" r={GR} fill="none" stroke={WARM} strokeWidth="3"
            strokeDasharray={`${GA} ${GC}`} strokeDashoffset={String(GA)} strokeLinecap="round"
            transform="rotate(150 28 28)"
            style={{ transition: "stroke-dashoffset 150ms ease-out, stroke 200ms", filter: `drop-shadow(0 0 3px ${WARM}40)` }} />
        </svg>
        <span ref={r(id)} style={S.gaugeNum}>--</span>
      </div>
      <span style={S.gaugeLabel}>{label}</span>
    </div>
  );

  return (
    <div style={S.screen}>
      {/* LEFT: Gauge instruments */}
      <div style={S.left}>
        <div style={{ ...S.gauge, marginBottom: 4 }}>
          <div style={{ ...S.gaugeRing, width: 68, height: 68 }}>
            <svg viewBox="0 0 56 56" style={{ width: 68, height: 68 }}>
              <circle cx="28" cy="28" r={GR} fill="none" stroke="rgba(201,149,42,0.06)" strokeWidth="3"
                strokeDasharray={`${GA} ${GC}`} strokeLinecap="round" transform="rotate(150 28 28)" />
              <circle ref={ra("healthArc")} cx="28" cy="28" r={GR} fill="none" stroke={WARM} strokeWidth="3.5"
                strokeDasharray={`${GA} ${GC}`} strokeDashoffset={String(GA)} strokeLinecap="round"
                transform="rotate(150 28 28)"
                style={{ transition: "stroke-dashoffset 400ms ease, stroke 300ms", filter: `drop-shadow(0 0 4px ${WARM}50)` }} />
            </svg>
            <span ref={r("health")} style={{ ...S.gaugeNum, fontSize: 22, color: CREAM }}>--</span>
          </div>
          <span style={S.gaugeLabel}>HEALTH</span>
        </div>
        <Gauge id="oil" label="OIL" />
        <Gauge id="cvt" label="CVT FL" />
        <Gauge id="cool" label="COOLANT" />
        <Gauge id="cat" label="CATALYST" />
      </div>

      {/* CENTER: Hero data + bars + waveforms */}
      <div style={S.center}>
        {/* Hero fuel number */}
        <div style={S.heroBlock}>
          <span ref={r("fuel")} style={S.heroNum}>--</span>
          <span ref={r("fuelLbl")} style={S.heroLabel}>GPH</span>
        </div>

        {/* Live bars */}
        <div style={S.barSection}>
          <div style={S.barRow}>
            <span style={S.barLabel}>THROTTLE</span>
            <div style={S.barTrack}><div ref={rb("throttleBar")} style={{ ...S.barFill, background: `linear-gradient(90deg, ${WARM}, ${COPPER})` }} /></div>
            <span ref={r("throttle")} style={S.barVal}>0%</span>
          </div>
          <div style={S.barRow}>
            <span style={S.barLabel}>LOAD</span>
            <div style={S.barTrack}><div ref={rb("loadBar")} style={{ ...S.barFill, background: `linear-gradient(90deg, ${WARM}, ${COPPER})` }} /></div>
            <span ref={r("load")} style={S.barVal}>0%</span>
          </div>
        </div>

        {/* Compact data strip */}
        <div style={S.strip}>
          {[["STFT", "stft"], ["LTFT", "ltft"], ["RPM", "rpm"], ["MAF", "maf"], ["MAP", "map"]].map(([label, id]) => (
            <div key={id} style={S.stripCell}>
              <span style={S.stripLabel}>{label}</span>
              <span ref={r(id!)} style={S.stripVal}>--</span>
            </div>
          ))}
        </div>

        {/* 4 Premium SVG Graphs -- each with distinct dynamic color */}
        <div style={S.waveStack}>
          <LiveGraph label="THROTTLE" unit="%" sensorKey="THROTTLE_POS" max={100} getColor={throttleColor} />
          <LiveGraph label="ENGINE LOAD" unit="%" sensorKey="ENGINE_LOAD" max={100} getColor={loadColor} />
          <LiveGraph label="AIR FLOW" unit="g/s" sensorKey="MAF" max={30} getColor={mafColor} />
          <LiveGraph label="COOLANT" unit="°C" sensorKey="COOLANT_TEMP" max={130} getColor={coolantColor} />
        </div>

        {/* Voice */}
        <div style={S.voiceRow}>
          <div style={{ width: 5, height: 5, borderRadius: "50%", background: WARM, boxShadow: `0 0 6px ${WARM}60`, animation: "pulse-voice 2s ease-in-out infinite", flexShrink: 0, marginTop: 2 }} />
          <span style={{ ...S.voiceText, opacity: vo, transition: "opacity 400ms" }}>{dv || "Monitoring..."}</span>
        </div>
      </div>

      {/* RIGHT: Sensor list */}
      <div style={S.right}>
        {[
          ["INTAKE", "intake"], ["VOLTS", "volts"], ["TANK", "tank"],
          ["COST", "cost"], ["¢/MIN", "rate"], ["DIST", "dist"],
        ].map(([label, id]) => (
          <div key={id} style={S.listRow}>
            <span style={S.listKey}>{label}</span>
            <span ref={r(id!)} style={S.listVal}>--</span>
          </div>
        ))}
      </div>
    </div>
  );
}

const MONO = "'JetBrains Mono', 'SF Mono', monospace";

const S = {
  screen: {
    width: "100%", height: "100%",
    background: "radial-gradient(ellipse at 30% 40%, rgba(201,149,42,0.03) 0%, #000 50%)",
    display: "flex", padding: "10px 14px", gap: "12px", overflow: "hidden",
    fontFamily: MONO,
  },

  // LEFT gauges
  left: {
    width: "90px", flexShrink: 0, display: "flex", flexDirection: "column" as const,
    alignItems: "center" as const, gap: "6px", justifyContent: "center" as const,
  },
  gauge: {
    display: "flex", flexDirection: "column" as const, alignItems: "center" as const, gap: "2px",
  },
  gaugeRing: {
    position: "relative" as const, width: 52, height: 52,
    display: "flex", alignItems: "center" as const, justifyContent: "center" as const,
  },
  gaugeNum: {
    position: "absolute" as const, fontSize: 14, fontWeight: 700, color: WARM,
    fontVariantNumeric: "tabular-nums" as const, transition: "color 200ms",
  },
  gaugeLabel: {
    fontSize: 8, fontWeight: 600, letterSpacing: "0.1em", color: DIM,
  },

  // CENTER
  center: {
    flex: 1, display: "flex", flexDirection: "column" as const, gap: "6px",
  },
  heroBlock: {
    display: "flex", alignItems: "baseline" as const, gap: "8px",
    padding: "6px 14px", borderRadius: "8px", border: `1px solid ${BORDER}`, background: GLASS,
    alignSelf: "flex-start" as const,
  },
  heroNum: {
    fontSize: 36, fontWeight: 700, color: CREAM, fontVariantNumeric: "tabular-nums" as const,
    textShadow: `0 0 12px ${WARM}20`,
  },
  heroLabel: { fontSize: 10, color: DIM, letterSpacing: "0.1em" },

  barSection: { display: "flex", flexDirection: "column" as const, gap: "4px" },
  barRow: { display: "flex", alignItems: "center" as const, gap: "8px" },
  barLabel: { fontSize: 9, color: DIM, width: 65, letterSpacing: "0.06em" },
  barTrack: { flex: 1, height: 4, borderRadius: 2, background: "rgba(201,149,42,0.06)", overflow: "hidden" as const },
  barFill: { height: "100%", borderRadius: 2, transition: "width 80ms ease-out", width: "0%" } as React.CSSProperties,
  barVal: { fontSize: 13, fontWeight: 600, color: CREAM, width: 32, textAlign: "right" as const, fontVariantNumeric: "tabular-nums" as const },

  strip: { display: "flex", gap: "4px" },
  stripCell: {
    flex: 1, padding: "4px 6px", borderRadius: "4px", border: `1px solid ${BORDER}`,
    display: "flex", flexDirection: "column" as const, alignItems: "center" as const,
  },
  stripLabel: { fontSize: 8, color: DIM, letterSpacing: "0.06em" },
  stripVal: { fontSize: 15, fontWeight: 600, color: WARM, fontVariantNumeric: "tabular-nums" as const, transition: "color 200ms" },

  waveStack: { flex: 1, display: "flex", flexDirection: "column" as const, gap: "4px", minHeight: 0 },
  waveBox: {
    flex: 1, borderRadius: "6px", border: `1px solid ${BORDER}`, background: GLASS,
    position: "relative" as const, overflow: "hidden" as const, minHeight: 0,
  },
  waveTag: { position: "absolute" as const, top: 3, left: 8, fontSize: 7, letterSpacing: "0.08em", color: `${WARM}30` },

  voiceRow: {
    display: "flex", alignItems: "flex-start" as const, gap: "8px", flexShrink: 0, paddingTop: "4px",
    borderTop: `1px solid ${BORDER}`,
  },
  voiceText: { fontSize: 11, color: "rgba(240,226,200,0.45)", fontFamily: "'Inter',sans-serif" },

  // RIGHT list
  right: {
    width: "110px", flexShrink: 0, display: "flex", flexDirection: "column" as const,
    justifyContent: "center" as const, gap: "6px",
  },
  listRow: {
    display: "flex", justifyContent: "space-between" as const, alignItems: "center" as const,
    padding: "3px 0", borderBottom: `1px solid ${BORDER}`,
  },
  listKey: { fontSize: 9, color: DIM, letterSpacing: "0.06em" },
  listVal: { fontSize: 15, fontWeight: 600, color: CREAM, fontVariantNumeric: "tabular-nums" as const, transition: "color 200ms" },
} as const;
