import { useCallback } from "react";
import { useThemeStore } from "@/stores/themeStore";
import { THEMES } from "@/constants/themes";

function ShuffleIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="16 3 21 3 21 8" />
      <line x1="4" y1="20" x2="21" y2="3" />
      <polyline points="21 16 21 21 16 21" />
      <line x1="15" y1="15" x2="21" y2="21" />
      <line x1="4" y1="4" x2="9" y2="9" />
    </svg>
  );
}

export function ThemeToggle() {
  const activeId = useThemeStore((s) => s.activeThemeId);
  const setTheme = useThemeStore((s) => s.setTheme);
  const randomize = useThemeStore((s) => s.randomize);

  const handleSelect = useCallback(
    (id: string) => {
      if (id === activeId) return;
      setTheme(id);
    },
    [activeId, setTheme],
  );

  return (
    <div
      style={{
        position: "fixed",
        bottom: "calc(24px + env(safe-area-inset-bottom))",
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 20,
        pointerEvents: "auto",
        display: "flex",
        alignItems: "center",
        gap: "12px",
        padding: "10px 16px",
        borderRadius: "28px",
        background: "rgba(0, 0, 0, 0.55)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        border: "1px solid var(--rune-border)",
      }}
    >
      {THEMES.map((theme) => {
        const isActive = theme.id === activeId;
        return (
          <button
            key={theme.id}
            onClick={() => handleSelect(theme.id)}
            aria-label={theme.name}
            style={{
              // 56px touch target (the tap area), visual dot is smaller inside
              width: "44px",
              height: "44px",
              borderRadius: "50%",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              padding: 0,
              flexShrink: 0,
              WebkitTapHighlightColor: "transparent",
              touchAction: "manipulation",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              position: "relative",
            }}
          >
            {/* Outer ring for active state */}
            {isActive && (
              <div
                style={{
                  position: "absolute",
                  inset: "2px",
                  borderRadius: "50%",
                  border: `2px solid ${theme.primary}`,
                  opacity: 0.4,
                  transition: "opacity 0.3s",
                }}
              />
            )}
            {/* Color dot */}
            <div
              style={{
                width: isActive ? "28px" : "22px",
                height: isActive ? "28px" : "22px",
                borderRadius: "50%",
                background: theme.primary,
                opacity: isActive ? 1 : 0.5,
                transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                boxShadow: isActive
                  ? `0 0 12px ${theme.primary}50, 0 0 4px ${theme.primary}30`
                  : "none",
              }}
            />
          </button>
        );
      })}

      {/* Divider */}
      <div
        style={{
          width: "1px",
          height: "24px",
          background: "var(--rune-border)",
          flexShrink: 0,
        }}
      />

      {/* Shuffle button */}
      <button
        onClick={randomize}
        aria-label="Randomize theme"
        style={{
          width: "44px",
          height: "44px",
          borderRadius: "50%",
          border: "1px solid var(--rune-border)",
          background: "transparent",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--rune-primary)",
          opacity: 0.6,
          transition: "opacity 0.2s",
          padding: 0,
          flexShrink: 0,
          WebkitTapHighlightColor: "transparent",
          touchAction: "manipulation",
        }}
      >
        <ShuffleIcon />
      </button>
    </div>
  );
}
