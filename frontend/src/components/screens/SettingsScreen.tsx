import { useRef, useEffect } from "react";
import { useSettingsStore } from "@/stores/settingsStore";
import { useVehicleStore } from "@/stores/vehicleStore";

const TOGGLES: { key: "gridBackground" | "runeVoice" | "hapticFeedback" | "parallaxTilt"; label: string; desc: string }[] = [
  { key: "gridBackground", label: "Grid Background", desc: "Subtle grid overlay" },
  { key: "runeVoice", label: "Rune Voice", desc: "Status messages from Rune" },
  { key: "hapticFeedback", label: "Haptic Feedback", desc: "Vibration on alerts" },
  { key: "parallaxTilt", label: "Parallax Tilt", desc: "Gyroscope response" },
];

function Toggle({ settingKey, label, desc }: { settingKey: typeof TOGGLES[number]["key"]; label: string; desc: string }) {
  const value = useSettingsStore((s) => s[settingKey]);
  const toggle = useSettingsStore((s) => s.toggle);
  const on = Boolean(value);

  return (
    <button
      onClick={() => toggle(settingKey)}
      style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        width: "100%", padding: "14px 18px",
        background: on ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.015)",
        border: "none", borderRadius: "14px", cursor: "pointer",
        borderLeft: on ? "3px solid rgba(255,255,255,0.4)" : "3px solid transparent",
        transition: "all 200ms", minHeight: "56px",
        WebkitTapHighlightColor: "transparent", textAlign: "left" as const,
      }}
    >
      <div>
        <div style={{
          fontFamily: "var(--font-ui)", fontSize: "16px",
          fontWeight: on ? 600 : 400,
          color: on ? "rgba(255,255,255,0.9)" : "rgba(255,255,255,0.25)",
          textDecoration: on ? "none" : "line-through",
        }}>{label}</div>
        <div style={{
          fontFamily: "var(--font-ui)", fontSize: "12px", fontWeight: 300,
          color: "rgba(255,255,255,0.25)", marginTop: "2px",
        }}>{desc}</div>
      </div>
      <div style={{
        width: "40px", height: "24px", borderRadius: "12px",
        background: on ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.05)",
        position: "relative" as const, transition: "background 200ms",
        flexShrink: 0,
      }}>
        <div style={{
          width: "18px", height: "18px", borderRadius: "9px",
          background: on ? "rgba(255,255,255,0.8)" : "rgba(255,255,255,0.15)",
          position: "absolute" as const, top: "3px",
          left: on ? "19px" : "3px",
          transition: "all 200ms",
        }} />
      </div>
    </button>
  );
}

export function SettingsScreen() {
  const gasPrice = useSettingsStore((s) => s.gasPricePerGallon);
  const setGasPrice = useSettingsStore((s) => s.setGasPrice);
  const units = useSettingsStore((s) => s.units);
  const setUnits = useSettingsStore((s) => s.setUnits);
  const connRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      if (connRef.current) {
        connRef.current.textContent = state.connected ? "Connected" : "Disconnected";
        connRef.current.style.color = state.connected ? "rgba(74,222,128,0.8)" : "rgba(239,68,68,0.8)";
      }
    });
    return unsub;
  }, []);

  return (
    <div style={S.screen}>
      {/* Left: Preferences */}
      <div style={S.col}>
        <span style={S.heading}>Preferences</span>
        <div style={S.toggles}>
          {TOGGLES.map((t) => (
            <Toggle key={t.key} settingKey={t.key} label={t.label} desc={t.desc} />
          ))}
        </div>

        <div style={S.field}>
          <span style={S.fieldLabel}>Gas price</span>
          <div style={S.priceRow}>
            <span style={S.dollar}>$</span>
            <input
              type="number" step="0.01" value={gasPrice}
              onChange={(e) => setGasPrice(parseFloat(e.target.value) || 0)}
              style={S.priceInput}
            />
            <span style={S.perGal}>/ gal</span>
          </div>
        </div>

        <div style={S.field}>
          <span style={S.fieldLabel}>Units</span>
          <div style={{ display: "flex", gap: "8px" }}>
            {(["imperial", "metric"] as const).map((u) => (
              <button key={u} onClick={() => setUnits(u)} style={{
                ...S.unitBtn,
                background: units === u ? "rgba(255,255,255,0.08)" : "transparent",
                color: units === u ? "rgba(255,255,255,0.85)" : "rgba(255,255,255,0.2)",
                borderColor: units === u ? "rgba(255,255,255,0.15)" : "rgba(255,255,255,0.04)",
              }}>
                {u.charAt(0).toUpperCase() + u.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right: System info */}
      <div style={S.col}>
        <span style={S.heading}>Connection</span>
        <div style={S.infoCard}>
          <Row label="Status" valueRef={connRef} defaultVal="--" />
          <Row label="Stream" value="10 Hz" />
          <Row label="Pi" value="192.168.4.1" />
        </div>

        <span style={{ ...S.heading, marginTop: "20px" }}>Vehicle</span>
        <div style={S.infoCard}>
          <Row label="Model" value="2026 Honda Accord SE" />
          <Row label="Engine" value="L15BE 1.5T CVT" />
          <Row label="Version" value="Rune OS v0.1.0" />
        </div>

        {/* Signature */}
        <div style={S.signature}>
          <span style={S.sigBy}>crafted by</span>
          <span style={S.sigName}>Kuladeep Mantri</span>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, valueRef, defaultVal }: {
  label: string;
  value?: string;
  valueRef?: React.RefObject<HTMLSpanElement | null>;
  defaultVal?: string;
}) {
  return (
    <div style={S.infoRow}>
      <span style={S.infoLabel}>{label}</span>
      <span ref={valueRef} style={S.infoValue}>{value ?? defaultVal ?? ""}</span>
    </div>
  );
}

const S = {
  screen: {
    width: "100%", height: "100%", background: "#000",
    display: "flex", padding: "24px 28px 32px", gap: "40px", overflow: "hidden",
  },
  col: {
    flex: 1, display: "flex", flexDirection: "column" as const, gap: "14px",
  },
  heading: {
    fontFamily: "var(--font-data)", fontSize: "20px", fontWeight: 600,
    color: "rgba(255,255,255,0.75)", letterSpacing: "-0.01em",
    display: "block" as const,
  },
  toggles: {
    display: "flex", flexDirection: "column" as const, gap: "6px",
  },
  field: {
    display: "flex", flexDirection: "column" as const, gap: "8px", marginTop: "8px",
  },
  fieldLabel: {
    fontFamily: "var(--font-ui)", fontSize: "14px", fontWeight: 500,
    color: "rgba(255,255,255,0.35)",
  },
  priceRow: {
    display: "flex", alignItems: "baseline" as const, gap: "4px",
  },
  dollar: {
    fontFamily: "var(--font-data)", fontSize: "22px", fontWeight: 500,
    color: "rgba(255,255,255,0.4)",
  },
  priceInput: {
    fontFamily: "var(--font-data)", fontSize: "22px", fontWeight: 600,
    color: "rgba(255,255,255,0.85)", background: "transparent",
    border: "none", borderBottom: "1px solid rgba(255,255,255,0.1)",
    outline: "none", width: "70px", padding: "2px 0",
  },
  perGal: {
    fontFamily: "var(--font-ui)", fontSize: "13px", fontWeight: 300,
    color: "rgba(255,255,255,0.2)",
  },
  unitBtn: {
    fontFamily: "var(--font-ui)", fontSize: "15px", fontWeight: 500,
    padding: "12px 24px", border: "1px solid rgba(255,255,255,0.04)",
    borderRadius: "12px", cursor: "pointer", transition: "all 200ms",
    minHeight: "48px", WebkitTapHighlightColor: "transparent",
  } as React.CSSProperties,

  // Info cards
  infoCard: {
    display: "flex", flexDirection: "column" as const, gap: "12px",
    padding: "16px 18px", borderRadius: "14px", background: "rgba(255,255,255,0.025)",
  },
  infoRow: {
    display: "flex", justifyContent: "space-between" as const, alignItems: "center" as const,
  },
  infoLabel: {
    fontFamily: "var(--font-ui)", fontSize: "15px", fontWeight: 400,
    color: "rgba(255,255,255,0.35)",
  },
  infoValue: {
    fontFamily: "var(--font-data)", fontSize: "15px", fontWeight: 500,
    color: "rgba(255,255,255,0.75)",
  },

  // Signature
  signature: {
    marginTop: "auto", paddingTop: "16px",
    display: "flex", flexDirection: "column" as const, alignItems: "flex-end" as const,
    gap: "2px",
  },
  sigBy: {
    fontFamily: "var(--font-credit)", fontStyle: "italic" as const,
    fontSize: "14px", fontWeight: 300, color: "rgba(255,255,255,0.15)",
  },
  sigName: {
    fontFamily: "var(--font-data)", fontSize: "22px", fontWeight: 300,
    color: "rgba(255,255,255,0.35)", letterSpacing: "0.02em",
  },
} as const;
