import { useState, useCallback, type ReactNode } from "react";

interface Screen {
  id: string;
  label: string;
  icon: ReactNode;
  content: ReactNode;
}

interface ScreenContainerProps {
  screens: Screen[];
  defaultScreen?: string;
}

function NavIcon({ d, size = 24 }: { d: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={d} />
    </svg>
  );
}

export const NAV_ICONS = {
  car: <NavIcon d="M7 17m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0M17 17m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0M5 17H3v-6l2-5h9l4 5h1a2 2 0 0 1 2 2v4h-2m-4 0H9" />,
  gauge: <NavIcon d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0M12 12l3.5 -5M12 7v1M7 10l0.7 0.7M6 15h1M17 10l-0.7 0.7M18 15h-1" />,
  settings: <NavIcon d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" />,
};

export function ScreenContainer({ screens, defaultScreen }: ScreenContainerProps) {
  const [activeId, setActiveId] = useState(defaultScreen ?? screens[0]?.id ?? "");

  const handleNav = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  return (
    <div style={{ position: "fixed", inset: 0, display: "flex", flexDirection: "column" }}>
      {/* Screen content */}
      <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        {screens.map((screen) => (
          <div
            key={screen.id}
            style={{
              position: "absolute",
              inset: 0,
              opacity: screen.id === activeId ? 1 : 0,
              pointerEvents: screen.id === activeId ? "auto" : "none",
              transition: "opacity 0.35s cubic-bezier(0.4, 0, 0.2, 1)",
            }}
          >
            {screen.content}
          </div>
        ))}
      </div>

      {/* Bottom navigation bar */}
      <nav
        style={{
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-around",
          height: "calc(64px + env(safe-area-inset-bottom))",
          paddingBottom: "env(safe-area-inset-bottom)",
          background: "rgba(0, 0, 0, 0.7)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          borderTop: "1px solid rgba(255, 255, 255, 0.04)",
        }}
      >
        {screens.map((screen) => {
          const isActive = screen.id === activeId;
          return (
            <button
              key={screen.id}
              onClick={() => handleNav(screen.id)}
              aria-label={screen.label}
              style={{
                flex: 1,
                height: "64px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: "4px",
                background: "none",
                border: "none",
                cursor: "pointer",
                color: isActive ? "var(--rune-primary)" : "var(--rune-text-muted)",
                opacity: isActive ? 1 : 0.4,
                transition: "color 0.25s, opacity 0.25s",
                WebkitTapHighlightColor: "transparent",
                touchAction: "manipulation",
                padding: 0,
                position: "relative",
              }}
            >
              {/* Active indicator line */}
              {isActive && (
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    left: "25%",
                    right: "25%",
                    height: "2px",
                    borderRadius: "1px",
                    background: "var(--rune-primary)",
                    boxShadow: `0 0 8px var(--rune-primary)`,
                  }}
                />
              )}
              {screen.icon}
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "9px",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                }}
              >
                {screen.label}
              </span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
