import { CarScene } from "@/components/car/CarScene";
import { useRef, useEffect } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { useRuneVoice } from "@/hooks/useRuneVoice";

// Main screen -- premium car OS layout.
// Car fills the center. Data overlays at edges. Everything CarPlay-readable.
export function RuneScreen() {
  const healthRef = useRef<HTMLSpanElement>(null);
  const mpgRef = useRef<HTMLSpanElement>(null);
  const mpgLabelRef = useRef<HTMLSpanElement>(null);
  const sensorRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const voice = useRuneVoice();

  // Imperative 10Hz updates for all data elements
  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      // Health score
      if (healthRef.current) {
        const score = state.health.overall;
        healthRef.current.textContent = score === -1 ? "--" : String(Math.round(score));
        healthRef.current.style.color =
          score < 50 ? "rgba(239,68,68,0.9)" :
          score < 70 ? "rgba(251,191,36,0.85)" :
          "rgba(255,255,255,0.9)";
      }

      // MPG or Idle GPH
      if (mpgRef.current && mpgLabelRef.current) {
        const speed = state.sensors["SPEED"]?.v ?? 0;
        if (speed > 2) {
          const mpg = state.fuel.instant_mpg;
          mpgRef.current.textContent = mpg != null ? mpg.toFixed(1) : "--";
          mpgLabelRef.current.textContent = "MPG";
        } else {
          const gph = state.fuel.idle_gph;
          mpgRef.current.textContent = gph != null ? gph.toFixed(2) : "--";
          mpgLabelRef.current.textContent = "IDLE GPH";
        }
      }

      // Sensor values
      const sensorKeys = ["RPM", "SPEED", "COOLANT_TEMP", "BATTERY_V", "FUEL_LEVEL"];
      sensorKeys.forEach((key, i) => {
        const el = sensorRefs.current[i];
        if (!el) return;
        const v = state.sensors[key]?.v;
        if (v === undefined) { el.textContent = "--"; return; }
        if (key === "RPM") el.textContent = Math.round(v).toLocaleString();
        else if (key === "SPEED") el.textContent = String(Math.round(v));
        else if (key === "BATTERY_V") el.textContent = v.toFixed(1);
        else el.textContent = String(Math.round(v));
      });
    });
    return unsub;
  }, []);

  return (
    <div style={styles.screen}>
      {/* 3D Car -- fills most of the screen */}
      <div style={styles.carArea}>
        <CarScene />
      </div>

      {/* Top-left: Health */}
      <div style={styles.topLeft}>
        <span style={styles.runeTag}>RUNE</span>
        <span ref={healthRef} style={styles.healthScore}>--</span>
        <span style={styles.healthLabel}>HEALTH</span>
      </div>

      {/* Top-right: MPG */}
      <div style={styles.topRight}>
        <span ref={mpgRef} style={styles.mpgValue}>--</span>
        <span ref={mpgLabelRef} style={styles.mpgLabel}>MPG</span>
      </div>

      {/* Right edge: Key sensors -- large, glanceable */}
      <div style={styles.sensorColumn}>
        {["RPM", "KPH", "°C", "V", "%"].map((unit, i) => (
          <div key={unit} style={styles.sensorRow}>
            <span
              ref={(el) => { sensorRefs.current[i] = el; }}
              style={styles.sensorValue}
            >
              --
            </span>
            <span style={styles.sensorUnit}>{unit}</span>
          </div>
        ))}
      </div>

      {/* Bottom center: Rune's voice */}
      <div style={styles.voiceArea}>
        <span style={styles.voiceText}>{voice.message}</span>
      </div>
    </div>
  );
}

const styles = {
  screen: {
    position: "relative" as const,
    width: "100%",
    height: "100%",
    background: "#000",
    overflow: "hidden",
  },
  carArea: {
    position: "absolute" as const,
    inset: 0,
    zIndex: 0,
  },
  topLeft: {
    position: "absolute" as const,
    top: "20px",
    left: "24px",
    zIndex: 10,
    display: "flex",
    flexDirection: "column" as const,
    gap: "2px",
  },
  runeTag: {
    fontFamily: "var(--font-data)",
    fontSize: "13px",
    fontWeight: 500,
    letterSpacing: "0.12em",
    color: "rgba(255,255,255,0.25)",
  },
  healthScore: {
    fontFamily: "var(--font-data)",
    fontSize: "56px",
    fontWeight: 700,
    color: "rgba(255,255,255,0.9)",
    lineHeight: 1,
    fontVariantNumeric: "tabular-nums" as const,
  },
  healthLabel: {
    fontFamily: "var(--font-ui)",
    fontSize: "11px",
    fontWeight: 600,
    letterSpacing: "0.15em",
    color: "rgba(255,255,255,0.2)",
  },
  topRight: {
    position: "absolute" as const,
    top: "20px",
    right: "24px",
    zIndex: 10,
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "flex-end" as const,
    gap: "2px",
  },
  mpgValue: {
    fontFamily: "var(--font-data)",
    fontSize: "40px",
    fontWeight: 600,
    color: "rgba(255,255,255,0.85)",
    lineHeight: 1,
    fontVariantNumeric: "tabular-nums" as const,
  },
  mpgLabel: {
    fontFamily: "var(--font-ui)",
    fontSize: "11px",
    fontWeight: 600,
    letterSpacing: "0.15em",
    color: "rgba(255,255,255,0.2)",
  },
  sensorColumn: {
    position: "absolute" as const,
    right: "24px",
    top: "50%",
    transform: "translateY(-30%)",
    zIndex: 10,
    display: "flex",
    flexDirection: "column" as const,
    gap: "20px",
    alignItems: "flex-end" as const,
  },
  sensorRow: {
    display: "flex",
    alignItems: "baseline" as const,
    gap: "8px",
  },
  sensorValue: {
    fontFamily: "var(--font-data)",
    fontSize: "28px",
    fontWeight: 600,
    color: "rgba(255,255,255,0.7)",
    lineHeight: 1,
    fontVariantNumeric: "tabular-nums" as const,
    minWidth: "60px",
    textAlign: "right" as const,
  },
  sensorUnit: {
    fontFamily: "var(--font-ui)",
    fontSize: "12px",
    fontWeight: 400,
    color: "rgba(255,255,255,0.2)",
    letterSpacing: "0.04em",
    minWidth: "32px",
  },
  voiceArea: {
    position: "absolute" as const,
    bottom: "70px",
    left: "50%",
    transform: "translateX(-50%)",
    zIndex: 10,
    maxWidth: "500px",
    textAlign: "center" as const,
  },
  voiceText: {
    fontFamily: "var(--font-ui)",
    fontSize: "15px",
    fontWeight: 300,
    color: "rgba(255,255,255,0.4)",
    lineHeight: 1.5,
  },
} as const;
