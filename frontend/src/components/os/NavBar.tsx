import { useUiStore, type ScreenId } from "@/stores/uiStore";
import { useEffect, useRef, useCallback, type ReactNode } from "react";

const TABS: { id: ScreenId; label: string; icon: ReactNode }[] = [
  {
    id: "rune",
    label: "Rune",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M5 17h14M6 10l1-5h10l1 5M4 17a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v1H4v-1z" />
        <circle cx="7.5" cy="17" r="1" />
        <circle cx="16.5" cy="17" r="1" />
      </svg>
    ),
  },
  {
    id: "telemetry",
    label: "Telemetry",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3.5 3.5" />
        <path d="M16.24 7.76l-4.24 4.24" />
      </svg>
    ),
  },
  {
    id: "settings",
    label: "Settings",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    ),
  },
];

const AUTO_HIDE_MS = 10_000;

export function NavBar() {
  const activeScreen = useUiStore((s) => s.activeScreen);
  const navVisible = useUiStore((s) => s.navVisible);
  const setActiveScreen = useUiStore((s) => s.setActiveScreen);
  const setNavVisible = useUiStore((s) => s.setNavVisible);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const resetTimer = useCallback(() => {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setNavVisible(false), AUTO_HIDE_MS);
  }, [setNavVisible]);

  // Start auto-hide timer when nav becomes visible
  useEffect(() => {
    if (navVisible) {
      resetTimer();
    }
    return () => clearTimeout(timerRef.current);
  }, [navVisible, resetTimer]);

  const handleTab = (id: ScreenId) => {
    setActiveScreen(id);
    resetTimer();
  };

  return (
    <nav
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        height: "56px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "2px",
        background: "rgba(0, 0, 0, 0.85)",
        backdropFilter: "blur(12px)",
        borderTop: "1px solid var(--rune-border)",
        zIndex: 100,
        paddingBottom: "env(safe-area-inset-bottom)",
        transform: navVisible ? "translateY(0)" : "translateY(100%)",
        transition: "transform 300ms ease",
        pointerEvents: navVisible ? "auto" : "none",
      }}
    >
      {TABS.map((tab) => {
        const isActive = activeScreen === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => handleTab(tab.id)}
            style={{
              flex: 1,
              maxWidth: "140px",
              height: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              background: "transparent",
              border: "none",
              borderTop: isActive ? "2px solid var(--rune-white)" : "2px solid transparent",
              color: isActive ? "var(--rune-text-bright)" : "var(--rune-label)",
              cursor: "pointer",
              fontFamily: "var(--font-ui)",
              fontSize: "11px",
              fontWeight: 500,
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              transition: "color 200ms, border-color 200ms",
              padding: 0,
              WebkitTapHighlightColor: "transparent",
              minWidth: "56px",
              minHeight: "56px",
            }}
          >
            {tab.icon}
            {tab.label}
          </button>
        );
      })}
    </nav>
  );
}
