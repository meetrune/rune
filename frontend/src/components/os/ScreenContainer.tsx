import { type ReactNode, useRef, useCallback, useEffect } from "react";
import { useUiStore, type ScreenId } from "@/stores/uiStore";

interface ScreenContainerProps {
  screens: Record<ScreenId, ReactNode>;
}

const SCREEN_ORDER: ScreenId[] = ["rune", "telemetry", "settings"];

// Swipe-based navigation with page indicator dots.
// No tab bar. Swipe left/right to switch screens.
export function ScreenContainer({ screens }: ScreenContainerProps) {
  const activeScreen = useUiStore((s) => s.activeScreen);
  const setActiveScreen = useUiStore((s) => s.setActiveScreen);

  const touchStartX = useRef(0);
  const touchStartY = useRef(0);
  const swiping = useRef(false);

  const currentIndex = SCREEN_ORDER.indexOf(activeScreen);

  const handleTouchStart = useCallback((e: TouchEvent) => {
    const touch = e.touches[0];
    if (!touch) return;
    touchStartX.current = touch.clientX;
    touchStartY.current = touch.clientY;
    swiping.current = true;
  }, []);

  const handleTouchEnd = useCallback((e: TouchEvent) => {
    if (!swiping.current) return;
    swiping.current = false;

    const touch = e.changedTouches[0];
    if (!touch) return;

    const dx = touch.clientX - touchStartX.current;
    const dy = touch.clientY - touchStartY.current;

    // Only horizontal swipes (more X movement than Y)
    if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy)) return;

    const idx = SCREEN_ORDER.indexOf(activeScreen);
    if (dx < 0 && idx < SCREEN_ORDER.length - 1) {
      // Swipe left -> next screen
      setActiveScreen(SCREEN_ORDER[idx + 1]!);
    } else if (dx > 0 && idx > 0) {
      // Swipe right -> prev screen
      setActiveScreen(SCREEN_ORDER[idx - 1]!);
    }
  }, [activeScreen, setActiveScreen]);

  useEffect(() => {
    window.addEventListener("touchstart", handleTouchStart, { passive: true });
    window.addEventListener("touchend", handleTouchEnd, { passive: true });
    return () => {
      window.removeEventListener("touchstart", handleTouchStart);
      window.removeEventListener("touchend", handleTouchEnd);
    };
  }, [handleTouchStart, handleTouchEnd]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative", overflow: "hidden" }}>
      {/* Screens with crossfade */}
      {(Object.keys(screens) as ScreenId[]).map((id) => (
        <div
          key={id}
          style={{
            position: "absolute",
            inset: 0,
            opacity: activeScreen === id ? 1 : 0,
            pointerEvents: activeScreen === id ? "auto" : "none",
            transition: "opacity 400ms ease",
          }}
        >
          {screens[id]}
        </div>
      ))}

      {/* Page indicator dots -- bottom center */}
      <div
        style={{
          position: "fixed",
          bottom: "12px",
          left: "50%",
          transform: "translateX(-50%)",
          display: "flex",
          gap: "8px",
          zIndex: 100,
        }}
      >
        {SCREEN_ORDER.map((id, i) => (
          <button
            key={id}
            onClick={() => setActiveScreen(id)}
            style={{
              width: i === currentIndex ? "20px" : "6px",
              height: "6px",
              borderRadius: "3px",
              background: i === currentIndex
                ? "rgba(255,255,255,0.5)"
                : "rgba(255,255,255,0.12)",
              border: "none",
              padding: 0,
              cursor: "pointer",
              transition: "all 300ms ease",
              WebkitTapHighlightColor: "transparent",
            }}
            aria-label={id}
          />
        ))}
      </div>
    </div>
  );
}
