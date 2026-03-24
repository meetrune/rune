import { useState, useCallback } from "react";
import { PreferenceCard } from "@/components/settings/PreferenceCard";
import { ConnectionInfo } from "@/components/settings/ConnectionInfo";
import { AboutBlock } from "@/components/settings/AboutBlock";
import { useSettingsStore } from "@/stores/settingsStore";

function GasPriceInput() {
  const gasPrice = useSettingsStore((s) => s.gasPricePerGallon);
  const setGasPrice = useSettingsStore((s) => s.setGasPrice);
  const [localValue, setLocalValue] = useState(gasPrice.toFixed(2));

  const handleBlur = useCallback(() => {
    const parsed = parseFloat(localValue);
    if (!isNaN(parsed) && parsed > 0 && parsed < 20) {
      setGasPrice(parsed);
      setLocalValue(parsed.toFixed(2));
    } else {
      setLocalValue(gasPrice.toFixed(2));
    }
  }, [localValue, gasPrice, setGasPrice]);

  return (
    <div style={{ padding: "10px 14px" }}>
      <span
        style={{
          fontFamily: "var(--font-data)",
          fontSize: "12px",
          color: "var(--rune-text-muted)",
          opacity: 0.6,
          display: "block",
          marginBottom: "6px",
        }}
      >
        Gas price per gallon
      </span>
      <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
        <span
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "16px",
            color: "var(--rune-text-muted)",
          }}
        >
          $
        </span>
        <input
          type="text"
          inputMode="decimal"
          value={localValue}
          onChange={(e) => setLocalValue(e.target.value)}
          onBlur={handleBlur}
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "16px",
            fontWeight: 500,
            color: "var(--rune-text)",
            background: "none",
            border: "none",
            borderBottom: "1px solid rgba(255,255,255,0.1)",
            outline: "none",
            width: "64px",
            padding: "4px 0",
          }}
        />
      </div>
    </div>
  );
}

function UnitsSelector() {
  const units = useSettingsStore((s) => s.units);
  const setUnits = useSettingsStore((s) => s.setUnits);

  return (
    <div style={{ padding: "10px 14px" }}>
      <span
        style={{
          fontFamily: "var(--font-data)",
          fontSize: "12px",
          color: "var(--rune-text-muted)",
          opacity: 0.6,
          display: "block",
          marginBottom: "8px",
        }}
      >
        Units
      </span>
      <div style={{ display: "flex", gap: "8px" }}>
        {(["imperial", "metric"] as const).map((u) => {
          const isActive = units === u;
          return (
            <button
              key={u}
              onClick={() => setUnits(u)}
              style={{
                flex: 1,
                minHeight: "44px",
                background: "none",
                border: "none",
                borderLeft: isActive ? "3px solid var(--rune-text)" : "3px solid transparent",
                padding: "8px 12px",
                cursor: "pointer",
                WebkitTapHighlightColor: "transparent",
                touchAction: "manipulation",
                fontFamily: "var(--font-data)",
                fontSize: "13px",
                fontWeight: 500,
                color: isActive ? "var(--rune-text)" : "var(--rune-text-muted)",
                textDecoration: isActive ? "none" : "line-through",
                textAlign: "left",
                transition: "color 0.2s, border-left-color 0.2s",
              }}
            >
              {u === "imperial" ? "Imperial" : "Metric"}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function SettingsScreen() {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        gap: "24px",
        padding: "16px 20px 56px 20px",
        background: "var(--rune-bg)",
        overflow: "hidden",
      }}
    >
      {/* Left column: preferences */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          gap: "2px",
          overflowY: "auto",
          scrollbarWidth: "none",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "11px",
            letterSpacing: "0.15em",
            color: "var(--rune-text-muted)",
            textTransform: "uppercase",
            opacity: 0.5,
            padding: "4px 14px 8px",
          }}
        >
          Preferences
        </span>

        <PreferenceCard
          title="Grid Background"
          description="Subtle grid overlay on main screen"
          settingKey="gridBackground"
        />
        <PreferenceCard
          title="Rune Voice"
          description="First-person status messages from Rune"
          settingKey="runeVoice"
        />
        <PreferenceCard
          title="Haptic Feedback"
          description="Vibration on interactions"
          settingKey="hapticFeedback"
        />
        <PreferenceCard
          title="Parallax Tilt"
          description="Car responds to phone gyroscope"
          settingKey="parallaxTilt"
        />

        <div style={{ height: "8px" }} />

        <GasPriceInput />
        <UnitsSelector />
      </div>

      {/* Right column: connection + about */}
      <div
        style={{
          width: "40%",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          gap: "24px",
          justifyContent: "space-between",
        }}
      >
        <ConnectionInfo />
        <AboutBlock />
      </div>
    </div>
  );
}
