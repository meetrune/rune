import { useRef, useEffect } from "react";
import { useSettingsStore } from "@/stores/settingsStore";
import { useVehicleStore } from "@/stores/vehicleStore";

// Settings screen -- dark engineering aesthetic.
// Every toggle actually works. Gas price feeds into $/MI calculation.

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <span style={{
        fontFamily: "var(--font-data)", fontSize: 14, fontWeight: 600,
        letterSpacing: "0.08em", color: "rgba(255,255,255,0.2)",
        display: "block", padding: "0 0 6px",
      }}>{title}</span>
      <div style={{
        borderRadius: 10, overflow: "hidden",
        background: "rgba(255,255,255,0.02)",
        border: "1px solid rgba(255,255,255,0.04)",
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
        width: "100%", padding: "10px 14px",
        background: "transparent", border: "none",
        borderBottom: "1px solid rgba(255,255,255,0.03)",
        cursor: "pointer", textAlign: "left" as const,
        minHeight: 52, WebkitTapHighlightColor: "transparent",
      }}
    >
      <div>
        <div style={{
          fontFamily: "var(--font-ui)", fontSize: 15, fontWeight: 500,
          color: on ? "rgba(255,255,255,0.85)" : "rgba(255,255,255,0.35)",
          transition: "color 200ms",
        }}>{label}</div>
        <div style={{
          fontFamily: "var(--font-ui)", fontSize: 13, fontWeight: 300,
          color: "rgba(255,255,255,0.15)", marginTop: 1,
        }}>{desc}</div>
      </div>
      {/* Minimal indicator: dot, not a toggle switch */}
      <div style={{
        width: 10, height: 10, borderRadius: "50%",
        background: on ? "#4ade80" : "rgba(255,255,255,0.08)",
        boxShadow: on ? "0 0 8px rgba(74,222,128,0.3)" : "none",
        transition: "all 250ms", flexShrink: 0,
      }} />
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
      padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.03)",
      minHeight: 44,
    }}>
      <span style={{ fontFamily: "var(--font-ui)", fontSize: 15, fontWeight: 500, color: "rgba(255,255,255,0.5)" }}>{label}</span>
      <span ref={valueRef} style={{
        fontFamily: "var(--font-data)", fontSize: 15, fontWeight: 600,
        color: color ?? "rgba(255,255,255,0.35)",
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
  const rateRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    let msgCount = 0;
    let lastReset = Date.now();

    const unsub = useVehicleStore.subscribe((state) => {
      if (connRef.current) {
        connRef.current.textContent = state.connected ? "Connected" : "Offline";
        connRef.current.style.color = state.connected ? "#4ade80" : "#ef4444";
      }
      // Live message rate counter
      msgCount++;
      const now = Date.now();
      if (now - lastReset >= 1000 && rateRef.current) {
        rateRef.current.textContent = `${msgCount} Hz`;
        msgCount = 0;
        lastReset = now;
      }
    });
    return unsub;
  }, []);

  return (
    <div style={{
      width: "100%", height: "100%", background: "#000",
      display: "flex", padding: "10px 16px 8px", gap: 20,
      overflow: "hidden", fontFamily: "var(--font-ui)",
    }}>
      {/* Left column */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        <Section title="DISPLAY">
          <ToggleRow settingKey="gridBackground" label="Grid Background" desc="Subtle grid overlay on home screen" />
          <ToggleRow settingKey="runeVoice" label="Rune Voice" desc="Status messages from Rune" />
          <ToggleRow settingKey="hapticFeedback" label="Haptic Feedback" desc="Vibration on alerts" />
          <ToggleRow settingKey="parallaxTilt" label="Parallax Tilt" desc="Gyroscope response on 3D car" />
        </Section>

        <Section title="FUEL">
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.03)", minHeight: 52,
          }}>
            <span style={{ fontSize: 15, fontWeight: 500, color: "rgba(255,255,255,0.5)" }}>Gas price</span>
            <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
              <span style={{ fontFamily: "var(--font-data)", fontSize: 16, color: "rgba(255,255,255,0.3)" }}>$</span>
              <input type="number" step="0.01" value={gasPrice}
                onChange={(e) => setGasPrice(parseFloat(e.target.value) || 0)}
                style={{
                  fontFamily: "var(--font-data)", fontSize: 18, fontWeight: 600,
                  color: "rgba(255,255,255,0.85)", background: "transparent",
                  border: "none", outline: "none", width: 55, textAlign: "right",
                  padding: "6px 0",
                }} />
            </div>
          </div>
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "10px 14px", minHeight: 52,
          }}>
            <span style={{ fontSize: 15, fontWeight: 500, color: "rgba(255,255,255,0.5)" }}>Units</span>
            <div style={{ display: "flex", gap: 2, background: "rgba(255,255,255,0.04)", borderRadius: 8, overflow: "hidden" }}>
              {(["imperial", "metric"] as const).map((u) => (
                <button key={u} onClick={() => setUnits(u)} style={{
                  fontFamily: "var(--font-ui)", fontSize: 14, fontWeight: 500,
                  padding: "8px 16px", border: "none", cursor: "pointer",
                  background: units === u ? "rgba(255,255,255,0.1)" : "transparent",
                  color: units === u ? "rgba(255,255,255,0.85)" : "rgba(255,255,255,0.2)",
                  transition: "all 200ms", WebkitTapHighlightColor: "transparent",
                  minHeight: 40,
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
        <Section title="CONNECTION">
          <InfoRow label="Status" valueRef={connRef} />
          <InfoRow label="Stream rate" valueRef={rateRef} value="-- Hz" />
          <InfoRow label="Pi address" value="192.168.4.1" />
        </Section>

        <Section title="VEHICLE">
          <InfoRow label="Car" value="2026 Accord SE" />
          <InfoRow label="Engine" value="L15BE 1.5T" />
          <InfoRow label="Trans" value="CVT" />
          <InfoRow label="Tank" value="14.8 gal" />
        </Section>

        <Section title="SYSTEM">
          <InfoRow label="Version" value="Rune OS v0.1.0" />
          <InfoRow label="Mode" value="Simulator" />
        </Section>

        {/* Builder card */}
        <div style={{
          marginTop: 14, padding: "16px 18px", borderRadius: 14,
          background: "rgba(201,149,42,0.04)",
          border: "1px solid rgba(201,149,42,0.12)",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{
                fontFamily: "var(--font-data)", fontSize: 20, fontWeight: 600,
                color: "rgba(255,255,255,0.9)", letterSpacing: "0.02em",
              }}>Kuladeep Mantri</div>
              <div style={{
                fontFamily: "var(--font-ui)", fontSize: 14, fontWeight: 400,
                color: "#c9952a", marginTop: 3, opacity: 0.6,
              }}>Software & Security Engineer</div>
            </div>
            <div style={{
              fontFamily: "var(--font-data)", fontSize: 14, fontWeight: 600,
              color: "#c9952a", letterSpacing: "0.15em",
              padding: "5px 12px", borderRadius: 8,
              background: "rgba(201,149,42,0.08)",
              border: "1px solid rgba(201,149,42,0.2)",
            }}>RUNE</div>
          </div>
          <div style={{
            fontFamily: "var(--font-ui)", fontSize: 14, fontWeight: 400,
            color: "rgba(255,255,255,0.45)", marginTop: 12, lineHeight: 1.6,
          }}>
            Built from scratch for my 2026 Honda Accord SE. Every sensor reading, every algorithm, every pixel -- designed and engineered for this car. Zero cloud. Zero compromise. Open source.
          </div>
          <div style={{
            fontFamily: "var(--font-data)", fontSize: 14, fontWeight: 500,
            color: "rgba(201,149,42,0.4)", marginTop: 10, letterSpacing: "0.04em",
          }}>
            github.com/meetrune/rune
          </div>
        </div>
      </div>
    </div>
  );
}
