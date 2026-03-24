import { useThemeStore } from "@/stores/themeStore";
import { useVehicleStore } from "@/stores/vehicleStore";
import { THEMES } from "@/constants/themes";
import { useEffect, useRef } from "react";

function ThemePicker() {
  const activeId = useThemeStore((s) => s.activeThemeId);
  const setTheme = useThemeStore((s) => s.setTheme);
  const randomize = useThemeStore((s) => s.randomize);

  return (
    <div
      style={{
        background: "var(--rune-surface)",
        borderRadius: "20px",
        border: "1px solid var(--rune-border)",
        padding: "24px",
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "12px",
          letterSpacing: "0.12em",
          color: "var(--rune-text-muted)",
          textTransform: "uppercase",
          display: "block",
          marginBottom: "20px",
        }}
      >
        Theme
      </span>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "12px",
        }}
      >
        {THEMES.map((theme) => {
          const isActive = theme.id === activeId;
          return (
            <button
              key={theme.id}
              onClick={() => setTheme(theme.id)}
              style={{
                height: "72px",
                borderRadius: "16px",
                border: isActive
                  ? `2.5px solid ${theme.primary}`
                  : "2px solid rgba(255,255,255,0.06)",
                background: theme.bg,
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                padding: 0,
                WebkitTapHighlightColor: "transparent",
                touchAction: "manipulation",
                transition: "border-color 0.2s, transform 0.15s",
                transform: isActive ? "scale(1.02)" : "scale(1)",
              }}
            >
              <div
                style={{
                  width: "16px",
                  height: "16px",
                  borderRadius: "50%",
                  background: theme.primary,
                  boxShadow: isActive ? `0 0 12px ${theme.primary}60` : "none",
                }}
              />
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "10px",
                  color: theme.primary,
                  opacity: isActive ? 1 : 0.5,
                  letterSpacing: "0.08em",
                }}
              >
                {theme.name}
              </span>
            </button>
          );
        })}
      </div>

      <button
        onClick={randomize}
        style={{
          width: "100%",
          height: "56px",
          marginTop: "16px",
          borderRadius: "16px",
          border: "1px solid var(--rune-border)",
          background: "transparent",
          color: "var(--rune-primary)",
          fontFamily: "var(--font-mono)",
          fontSize: "13px",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          cursor: "pointer",
          WebkitTapHighlightColor: "transparent",
          touchAction: "manipulation",
        }}
      >
        Shuffle
      </button>
    </div>
  );
}

function ConnectionInfo() {
  const statusRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      if (statusRef.current) {
        statusRef.current.textContent = state.connected ? "Connected" : "Disconnected";
        statusRef.current.style.color = state.connected
          ? "var(--rune-primary)"
          : "var(--rune-critical)";
      }
    });
    return unsub;
  }, []);

  return (
    <div
      style={{
        background: "var(--rune-surface)",
        borderRadius: "20px",
        border: "1px solid var(--rune-border)",
        padding: "24px",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "12px",
          letterSpacing: "0.12em",
          color: "var(--rune-text-muted)",
          textTransform: "uppercase",
        }}
      >
        Connection
      </span>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontFamily: "var(--font-data)", fontSize: "16px", color: "var(--rune-text)" }}>
          Status
        </span>
        <div
          ref={statusRef}
          style={{ fontFamily: "var(--font-data)", fontSize: "16px", color: "var(--rune-text-muted)" }}
        >
          --
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontFamily: "var(--font-data)", fontSize: "16px", color: "var(--rune-text)" }}>
          WebSocket
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "14px", color: "var(--rune-text-muted)" }}>
          10 Hz
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontFamily: "var(--font-data)", fontSize: "16px", color: "var(--rune-text)" }}>
          Vehicle
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "14px", color: "var(--rune-text-muted)" }}>
          2026 Accord SE
        </span>
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
        background: "var(--rune-bg)",
        padding: "calc(16px + env(safe-area-inset-top)) 16px calc(32px + env(safe-area-inset-bottom))",
        overflowY: "auto",
        overflowX: "hidden",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "11px",
          letterSpacing: "0.2em",
          color: "var(--rune-text-muted)",
          textTransform: "uppercase",
          padding: "8px 4px",
        }}
      >
        Settings
      </div>

      <ThemePicker />
      <ConnectionInfo />

      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "10px",
          color: "var(--rune-text-muted)",
          opacity: 0.4,
          textAlign: "center",
          padding: "16px",
          letterSpacing: "0.08em",
        }}
      >
        RUNE v0.1.0
      </div>
    </div>
  );
}
