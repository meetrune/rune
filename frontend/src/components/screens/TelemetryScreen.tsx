import { useRef, useEffect } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { getSensorState, getSensorLabel, getSensorUnit } from "@/constants/thresholds";
import type { SubsystemId } from "@/types/vehicle";

const SUBSYSTEMS: { id: SubsystemId; label: string; icon: string }[] = [
  { id: "engine", label: "Engine", icon: "E" },
  { id: "transmission", label: "CVT", icon: "T" },
  { id: "cooling", label: "Cooling", icon: "C" },
  { id: "fuel", label: "Fuel", icon: "F" },
  { id: "exhaust", label: "Exhaust", icon: "X" },
  { id: "electrical", label: "Electrical", icon: "V" },
];

const SENSORS_ALL = [
  "RPM", "SPEED", "COOLANT_TEMP", "ENGINE_LOAD",
  "THROTTLE_POS", "MAF", "FUEL_LEVEL", "BATTERY_V",
  "INTAKE_TEMP", "OIL_TEMP", "CATALYST_TEMP", "CVT_TEMP",
];

const COL = {
  ok: "rgba(255,255,255,0.9)",
  warn: "rgba(251,191,36,0.9)",
  crit: "rgba(239,68,68,0.95)",
  dim: "rgba(255,255,255,0.4)",
  subtle: "rgba(255,255,255,0.12)",
  bg: "rgba(255,255,255,0.03)",
  barOk: "rgba(255,255,255,0.25)",
  barWarn: "rgba(251,191,36,0.5)",
  barCrit: "rgba(239,68,68,0.6)",
};

function scoreColor(s: number) {
  return s < 50 ? COL.crit : s < 70 ? COL.warn : COL.ok;
}
function barColor(s: number) {
  return s < 50 ? COL.barCrit : s < 70 ? COL.barWarn : COL.barOk;
}
function fmt(k: string, v: number) {
  if (k === "RPM") return Math.round(v).toLocaleString();
  if (k === "BATTERY_V" || k === "MAF") return v.toFixed(1);
  return String(Math.round(v));
}

export function TelemetryScreen() {
  const healthRef = useRef<HTMLSpanElement>(null);
  const subScoreRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const subBarRefs = useRef<(HTMLDivElement | null)[]>([]);
  const subIconRefs = useRef<(HTMLDivElement | null)[]>([]);
  const sValRefs = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const h = state.health;
      if (healthRef.current) {
        const s = h.overall;
        healthRef.current.textContent = s === -1 ? "--" : String(Math.round(s));
        healthRef.current.style.color = s === -1 ? COL.dim : scoreColor(s);
      }
      SUBSYSTEMS.forEach((sub, i) => {
        const s = h[sub.id];
        const sc = subScoreRefs.current[i];
        const bar = subBarRefs.current[i];
        const icon = subIconRefs.current[i];
        if (sc) { sc.textContent = s === -1 ? "--" : String(Math.round(s)); sc.style.color = s === -1 ? COL.dim : scoreColor(s); }
        if (bar) { bar.style.width = `${s === -1 ? 0 : s}%`; bar.style.backgroundColor = s === -1 ? COL.subtle : barColor(s); }
        if (icon) { icon.style.borderColor = s < 70 && s !== -1 ? scoreColor(s) : "rgba(255,255,255,0.08)"; }
      });
      SENSORS_ALL.forEach((key, i) => {
        const el = sValRefs.current[i];
        if (!el) return;
        const v = state.sensors[key]?.v;
        const st = v !== undefined ? getSensorState(key, v) : "normal";
        el.textContent = v !== undefined ? fmt(key, v) : "--";
        el.style.color = st === "critical" ? COL.crit : st === "warn" ? COL.warn : COL.ok;
      });
    });
    return unsub;
  }, []);

  return (
    <div style={S.screen}>
      {/* Header row: overall health + subsystem cards */}
      <div style={S.topRow}>
        <div style={S.healthCard}>
          <span ref={healthRef} style={S.healthNum}>--</span>
          <span style={S.healthTag}>HEALTH</span>
        </div>

        <div style={S.subCards}>
          {SUBSYSTEMS.map((sub, i) => (
            <div key={sub.id} style={S.subCard}>
              <div style={S.subTop}>
                <div
                  ref={(el) => { subIconRefs.current[i] = el; }}
                  style={S.subIcon}
                >
                  {sub.icon}
                </div>
                <span style={S.subLabel}>{sub.label}</span>
                <span
                  ref={(el) => { subScoreRefs.current[i] = el; }}
                  style={S.subScore}
                >--</span>
              </div>
              <div style={S.subBarBg}>
                <div
                  ref={(el) => { subBarRefs.current[i] = el; }}
                  style={S.subBarFill}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Sensor grid */}
      <div style={S.sensorSection}>
        <span style={S.sectionTag}>LIVE SENSORS</span>
        <div style={S.sGrid}>
          {SENSORS_ALL.map((key, i) => (
            <div key={key} style={S.sCell}>
              <span style={S.sLabel}>{getSensorLabel(key)} <span style={{ opacity: 0.4 }}>{getSensorUnit(key)}</span></span>
              <span
                ref={(el) => { sValRefs.current[i] = el; }}
                style={S.sVal}
              >--</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const S = {
  screen: {
    width: "100%", height: "100%", background: "#000",
    display: "flex", flexDirection: "column" as const,
    padding: "20px 24px 28px", gap: "16px", overflow: "hidden",
  },

  // Top row
  topRow: {
    display: "flex", gap: "24px", alignItems: "flex-start" as const,
  },
  healthCard: {
    display: "flex", flexDirection: "column" as const, gap: "4px",
    padding: "16px 24px", borderRadius: "16px", background: COL.bg,
    minWidth: "120px",
  },
  healthNum: {
    fontFamily: "var(--font-data)", fontSize: "56px", fontWeight: 700,
    color: COL.ok, lineHeight: 1, fontVariantNumeric: "tabular-nums" as const,
  },
  healthTag: {
    fontFamily: "var(--font-ui)", fontSize: "12px", fontWeight: 600,
    letterSpacing: "0.15em", color: COL.dim,
  },

  // Subsystem cards
  subCards: {
    display: "flex", gap: "8px", flex: 1, flexWrap: "wrap" as const,
  },
  subCard: {
    flex: "1 1 140px", padding: "12px 14px", borderRadius: "12px",
    background: COL.bg, display: "flex", flexDirection: "column" as const, gap: "8px",
    minHeight: "56px",
  },
  subTop: {
    display: "flex", alignItems: "center" as const, gap: "8px",
  },
  subIcon: {
    width: "28px", height: "28px", borderRadius: "8px",
    border: "1.5px solid rgba(255,255,255,0.08)",
    display: "flex", alignItems: "center" as const, justifyContent: "center" as const,
    fontFamily: "var(--font-data)", fontSize: "12px", fontWeight: 700,
    color: COL.dim, flexShrink: 0, transition: "border-color 300ms",
  },
  subLabel: {
    fontFamily: "var(--font-ui)", fontSize: "14px", fontWeight: 500,
    color: "rgba(255,255,255,0.55)", flex: 1,
  },
  subScore: {
    fontFamily: "var(--font-data)", fontSize: "20px", fontWeight: 700,
    color: COL.ok, fontVariantNumeric: "tabular-nums" as const,
  },
  subBarBg: {
    height: "4px", borderRadius: "2px", background: "rgba(255,255,255,0.04)",
    overflow: "hidden" as const,
  },
  subBarFill: {
    height: "100%", borderRadius: "2px", backgroundColor: COL.barOk,
    transition: "width 300ms, background-color 300ms", width: "0%",
  },

  // Sensors
  sensorSection: {
    display: "flex", flexDirection: "column" as const, gap: "10px", flex: 1,
  },
  sectionTag: {
    fontFamily: "var(--font-ui)", fontSize: "12px", fontWeight: 600,
    letterSpacing: "0.15em", color: "rgba(255,255,255,0.2)",
  },
  sGrid: {
    display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "6px",
    flex: 1, alignContent: "start" as const,
  },
  sCell: {
    display: "flex", flexDirection: "column" as const, gap: "2px",
    padding: "10px 12px", borderRadius: "10px", background: COL.bg,
  },
  sLabel: {
    fontFamily: "var(--font-ui)", fontSize: "12px", fontWeight: 400,
    color: "rgba(255,255,255,0.3)",
  },
  sVal: {
    fontFamily: "var(--font-data)", fontSize: "24px", fontWeight: 600,
    color: COL.ok, lineHeight: 1.2, fontVariantNumeric: "tabular-nums" as const,
  },
} as const;
