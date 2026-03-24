import { CarScene } from "@/components/car/CarScene";
import { useRef, useEffect, useState } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { useRuneVoice } from "@/hooks/useRuneVoice";

export function RuneScreen() {
  const healthRef = useRef<HTMLSpanElement>(null);
  const mpgRef = useRef<HTMLSpanElement>(null);
  const mpgLabelRef = useRef<HTMLSpanElement>(null);
  const sensorRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const voice = useRuneVoice();
  const [displayVoice, setDisplayVoice] = useState("");
  const [voiceOpacity, setVoiceOpacity] = useState(0);
  const prevVoice = useRef("");

  // Smooth voice transition
  useEffect(() => {
    if (!voice.message || voice.message === prevVoice.current) return;
    prevVoice.current = voice.message;
    setVoiceOpacity(0);
    const t = setTimeout(() => {
      setDisplayVoice(voice.message);
      setVoiceOpacity(1);
    }, 400);
    return () => clearTimeout(t);
  }, [voice.message]);

  useEffect(() => {
    if (voice.message && !displayVoice) {
      setDisplayVoice(voice.message);
      setTimeout(() => setVoiceOpacity(1), 100);
    }
  }, [voice.message, displayVoice]);

  // Imperative 10Hz sensor updates
  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      if (healthRef.current) {
        const s = state.health.overall;
        healthRef.current.textContent = s === -1 ? "--" : String(Math.round(s));
        healthRef.current.style.color =
          s < 50 ? "rgba(239,68,68,0.9)" :
          s < 70 ? "rgba(251,191,36,0.85)" :
          "rgba(255,255,255,0.9)";
      }
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
      const keys = ["RPM", "SPEED", "COOLANT_TEMP", "BATTERY_V", "FUEL_LEVEL"];
      keys.forEach((key, i) => {
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
    <div style={S.screen}>
      {/* 3D Car fills the screen */}
      <div style={S.carArea}>
        <CarScene />
      </div>

      {/* Top-left: Rune identity */}
      <div style={S.topLeft}>
        <div style={S.brandRow}>
          <span style={S.runeName}>Rune</span>
          <span style={S.byLine}>by Kuladeep Mantri</span>
        </div>
        <div style={S.healthRow}>
          <span ref={healthRef} style={S.healthScore}>--</span>
          <span style={S.healthLabel}>HEALTH</span>
        </div>
      </div>

      {/* Top-right: MPG */}
      <div style={S.topRight}>
        <span ref={mpgRef} style={S.mpgValue}>--</span>
        <span ref={mpgLabelRef} style={S.mpgLabel}>MPG</span>
      </div>

      {/* Right edge: Key sensors */}
      <div style={S.sensorColumn}>
        {["RPM", "KPH", "\u00B0C", "V", "%"].map((unit, i) => (
          <div key={unit} style={S.sensorRow}>
            <span
              ref={(el) => { sensorRefs.current[i] = el; }}
              style={S.sensorValue}
            >--</span>
            <span style={S.sensorUnit}>{unit}</span>
          </div>
        ))}
      </div>

      {/* Bottom: Rune speaking -- modern card */}
      <div style={S.voiceArea}>
        <div
          style={{
            ...S.voiceCard,
            opacity: voiceOpacity,
            transform: voiceOpacity ? "translateY(0)" : "translateY(8px)",
            transition: "opacity 600ms ease, transform 600ms ease",
          }}
        >
          <div style={S.voiceAvatar}>R</div>
          <p style={S.voiceText}>
            {displayVoice || "Listening..."}
          </p>
        </div>
      </div>
    </div>
  );
}

const S = {
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

  // Top-left: Rune identity
  topLeft: {
    position: "absolute" as const,
    top: "20px",
    left: "24px",
    zIndex: 10,
  },
  brandRow: {
    display: "flex",
    flexDirection: "column" as const,
    marginBottom: "10px",
  },
  runeName: {
    fontFamily: "var(--font-data)",
    fontSize: "32px",
    fontWeight: 700,
    color: "rgba(255,255,255,0.9)",
    letterSpacing: "-0.02em",
    lineHeight: 1,
  },
  byLine: {
    fontFamily: "var(--font-credit)",
    fontStyle: "italic" as const,
    fontSize: "13px",
    fontWeight: 300,
    color: "rgba(255,255,255,0.18)",
    marginTop: "4px",
    letterSpacing: "0.02em",
  },
  healthRow: {
    display: "flex",
    alignItems: "baseline" as const,
    gap: "10px",
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
    fontSize: "13px",
    fontWeight: 600,
    letterSpacing: "0.12em",
    color: "rgba(255,255,255,0.2)",
  },

  // Top-right: MPG
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
    fontSize: "12px",
    fontWeight: 600,
    letterSpacing: "0.12em",
    color: "rgba(255,255,255,0.2)",
  },

  // Right sensor column
  sensorColumn: {
    position: "absolute" as const,
    right: "24px",
    top: "50%",
    transform: "translateY(-25%)",
    zIndex: 10,
    display: "flex",
    flexDirection: "column" as const,
    gap: "18px",
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

  // Voice area -- Rune speaking
  voiceArea: {
    position: "absolute" as const,
    bottom: "28px",
    left: "24px",
    right: "24px",
    zIndex: 10,
    display: "flex",
    justifyContent: "center" as const,
  },
  voiceCard: {
    display: "flex",
    alignItems: "flex-start" as const,
    gap: "14px",
    maxWidth: "520px",
    padding: "14px 20px",
    borderRadius: "16px",
    background: "rgba(255,255,255,0.04)",
    backdropFilter: "blur(20px)",
    WebkitBackdropFilter: "blur(20px)",
    border: "1px solid rgba(255,255,255,0.06)",
  },
  voiceAvatar: {
    width: "32px",
    height: "32px",
    borderRadius: "10px",
    background: "rgba(255,255,255,0.08)",
    display: "flex",
    alignItems: "center" as const,
    justifyContent: "center" as const,
    fontFamily: "var(--font-data)",
    fontSize: "14px",
    fontWeight: 700,
    color: "rgba(255,255,255,0.4)",
    flexShrink: 0,
  },
  voiceText: {
    fontFamily: "var(--font-ui)",
    fontSize: "16px",
    fontWeight: 400,
    lineHeight: 1.6,
    color: "rgba(255,255,255,0.65)",
    margin: 0,
    paddingTop: "4px",
  },
} as const;
