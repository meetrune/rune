import { useRef, useEffect } from "react";
import { useSettingsStore } from "@/stores/settingsStore";
import { useVehicleStore } from "@/stores/vehicleStore";

// iOS-style grouped settings. Rounded groups, clean dividers, no individual cards.

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: "20px" }}>
      <span style={{
        fontFamily: "var(--font-ui)", fontSize: "13px", fontWeight: 600,
        letterSpacing: "0.06em", textTransform: "uppercase" as const,
        color: "rgba(255,255,255,0.3)", display: "block",
        padding: "0 16px 8px",
      }}>{title}</span>
      <div style={{
        borderRadius: "16px", overflow: "hidden",
        background: "rgba(255,255,255,0.03)",
        backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)",
        border: "1px solid rgba(255,255,255,0.05)",
      }}>
        {children}
      </div>
    </div>
  );
}

function ToggleRow({ label, desc, settingKey }: {
  label: string; desc: string;
  settingKey: "gridBackground" | "runeVoice" | "hapticFeedback" | "parallaxTilt";
}) {
  const value = useSettingsStore((s) => s[settingKey]);
  const toggle = useSettingsStore((s) => s.toggle);
  const on = Boolean(value);

  return (
    <button
      onClick={() => toggle(settingKey)}
      style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        width: "100%", padding: "14px 16px",
        background: "transparent", border: "none",
        borderBottom: "1px solid rgba(255,255,255,0.04)",
        cursor: "pointer", textAlign: "left" as const,
        minHeight: "56px", WebkitTapHighlightColor: "transparent",
        transition: "background 100ms",
      }}
      onPointerDown={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.04)"; }}
      onPointerUp={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
      onPointerLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
    >
      <div>
        <div style={{
          fontFamily: "var(--font-ui)", fontSize: "16px", fontWeight: 500,
          color: "rgba(255,255,255,0.9)",
        }}>{label}</div>
        <div style={{
          fontFamily: "var(--font-ui)", fontSize: "12px", fontWeight: 300,
          color: "rgba(255,255,255,0.25)", marginTop: "2px",
        }}>{desc}</div>
      </div>
      {/* iOS-style toggle track */}
      <div style={{
        width: "44px", height: "26px", borderRadius: "13px",
        background: on ? "rgba(74,222,128,0.6)" : "rgba(255,255,255,0.08)",
        position: "relative", transition: "background 250ms ease",
        flexShrink: 0,
      }}>
        <div style={{
          width: "22px", height: "22px", borderRadius: "11px",
          background: "#fff",
          position: "absolute", top: "2px",
          left: on ? "20px" : "2px",
          transition: "left 250ms cubic-bezier(0.4,0,0.2,1)",
          boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
        }} />
      </div>
    </button>
  );
}

function InfoRow({ label, value, valueRef, color }: {
  label: string; value?: string;
  valueRef?: React.RefObject<HTMLSpanElement | null>;
  color?: string;
}) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "14px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)",
    }}>
      <span style={{ fontFamily: "var(--font-ui)", fontSize: "16px", fontWeight: 500, color: "rgba(255,255,255,0.9)" }}>{label}</span>
      <span ref={valueRef} style={{
        fontFamily: "var(--font-data)", fontSize: "16px", fontWeight: 500,
        color: color ?? "rgba(255,255,255,0.5)",
      }}>{value ?? ""}</span>
    </div>
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
        connRef.current.textContent = state.connected ? "Connected" : "Offline";
        connRef.current.style.color = state.connected ? "rgba(74,222,128,0.8)" : "rgba(239,68,68,0.7)";
      }
    });
    return unsub;
  }, []);

  return (
    <div style={{
      width: "100%", height: "100%", background: "#000",
      display: "flex", padding: "20px 24px 28px", gap: "32px",
      overflow: "hidden",
    }}>
      {/* Left column */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        <Section title="Display">
          <ToggleRow settingKey="gridBackground" label="Grid Background" desc="Subtle grid overlay" />
          <ToggleRow settingKey="runeVoice" label="Rune Voice" desc="Status messages from Rune" />
          <ToggleRow settingKey="hapticFeedback" label="Haptic Feedback" desc="Vibration on alerts" />
          <ToggleRow settingKey="parallaxTilt" label="Parallax Tilt" desc="Gyroscope response" />
        </Section>

        <Section title="Fuel">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
            <span style={{ fontFamily: "var(--font-ui)", fontSize: "16px", fontWeight: 500, color: "rgba(255,255,255,0.9)" }}>Gas price</span>
            <div style={{ display: "flex", alignItems: "baseline", gap: "4px" }}>
              <span style={{ fontFamily: "var(--font-data)", fontSize: "18px", fontWeight: 500, color: "rgba(255,255,255,0.5)" }}>$</span>
              <input type="number" step="0.01" value={gasPrice}
                onChange={(e) => setGasPrice(parseFloat(e.target.value) || 0)}
                style={{
                  fontFamily: "var(--font-data)", fontSize: "18px", fontWeight: 600,
                  color: "rgba(255,255,255,0.9)", background: "transparent",
                  border: "none", outline: "none", width: "50px", textAlign: "right",
                }} />
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 16px" }}>
            <span style={{ fontFamily: "var(--font-ui)", fontSize: "16px", fontWeight: 500, color: "rgba(255,255,255,0.9)" }}>Units</span>
            <div style={{ display: "flex", background: "rgba(255,255,255,0.06)", borderRadius: "8px", overflow: "hidden" }}>
              {(["imperial", "metric"] as const).map((u) => (
                <button key={u} onClick={() => setUnits(u)} style={{
                  fontFamily: "var(--font-ui)", fontSize: "14px", fontWeight: 500,
                  padding: "6px 16px", border: "none", cursor: "pointer",
                  background: units === u ? "rgba(255,255,255,0.12)" : "transparent",
                  color: units === u ? "rgba(255,255,255,0.9)" : "rgba(255,255,255,0.3)",
                  transition: "all 200ms", WebkitTapHighlightColor: "transparent",
                }}>
                  {u.charAt(0).toUpperCase() + u.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </Section>
      </div>

      {/* Right column */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        <Section title="Connection">
          <InfoRow label="Status" valueRef={connRef} />
          <InfoRow label="Stream rate" value="10 Hz" />
          <InfoRow label="Pi address" value="192.168.4.1" />
        </Section>

        <Section title="About">
          <InfoRow label="Vehicle" value="2026 Honda Accord SE" />
          <InfoRow label="Engine" value="L15BE 1.5T CVT" />
          <InfoRow label="Version" value="Rune OS v0.1.0" />
        </Section>

        {/* Signature */}
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "flex-end",
          padding: "20px 16px 0", marginTop: "auto",
        }}>
          <span style={{
            fontFamily: "var(--font-credit)", fontStyle: "italic",
            fontSize: "12px", fontWeight: 300, color: "rgba(255,255,255,0.08)",
          }}>crafted by</span>
          <span style={{
            fontFamily: "var(--font-signature)", fontSize: "32px",
            color: "rgba(255,255,255,0.18)",
          }}>Kuladeep Mantri</span>
        </div>
      </div>
    </div>
  );
}
