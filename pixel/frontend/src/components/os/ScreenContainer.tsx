import { type ReactNode, useRef, useCallback, useEffect } from "react";
import { useUiStore, type ScreenId } from "@/stores/uiStore";

interface ScreenContainerProps {
  screens: Record<ScreenId, ReactNode>;
}

const SCREEN_ORDER: ScreenId[] = ["telemetry", "rune", "trip-summary", "settings"];

// Swipe (touch) + arrow keys (desktop) + clickable pills.
export function ScreenContainer({ screens }: ScreenContainerProps) {
  const activeScreen = useUiStore((s) => s.activeScreen);
  const setActiveScreen = useUiStore((s) => s.setActiveScreen);
  const currentIndex = SCREEN_ORDER.indexOf(activeScreen);

  const touchStartX = useRef(0);
  const touchStartY = useRef(0);
  const swiping = useRef(false);

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

    if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy)) return;

    const idx = SCREEN_ORDER.indexOf(activeScreen);
    if (dx < 0 && idx < SCREEN_ORDER.length - 1) {
      setActiveScreen(SCREEN_ORDER[idx + 1]!);
    } else if (dx > 0 && idx > 0) {
      setActiveScreen(SCREEN_ORDER[idx - 1]!);
    }
  }, [activeScreen, setActiveScreen]);

  // Arrow keys for desktop dev
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const idx = SCREEN_ORDER.indexOf(activeScreen);
    if (e.key === "ArrowRight" && idx < SCREEN_ORDER.length - 1) {
      setActiveScreen(SCREEN_ORDER[idx + 1]!);
    } else if (e.key === "ArrowLeft" && idx > 0) {
      setActiveScreen(SCREEN_ORDER[idx - 1]!);
    }
  }, [activeScreen, setActiveScreen]);

  useEffect(() => {
    window.addEventListener("touchstart", handleTouchStart, { passive: true });
    window.addEventListener("touchend", handleTouchEnd, { passive: true });
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("touchstart", handleTouchStart);
      window.removeEventListener("touchend", handleTouchEnd);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [handleTouchStart, handleTouchEnd, handleKeyDown]);

  return (
    <div style={{
      width: "100%", height: "100%", position: "relative", overflow: "hidden",
      // Burn-in protection: entire UI shifts 1-2px every 5 minutes.
      // Updated by useBurnInProtection hook via CSS variables.
      transform: "translate(var(--burn-shift-x, 0px), var(--burn-shift-y, 0px))",
    }}>
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

      {/* Position pills -- clickable on desktop, visual on phone */}
      <div
        style={{
          position: "fixed",
          bottom: "8px",
          left: "50%",
          transform: "translateX(-50%)",
          display: "flex",
          gap: "6px",
          zIndex: 100,
        }}
      >
        {SCREEN_ORDER.map((id, i) => (
          <button
            key={id}
            onClick={() => setActiveScreen(id)}
            style={{
              width: i === currentIndex ? "20px" : "8px",
              height: "8px",
              borderRadius: "4px",
              background: i === currentIndex
                ? "rgba(255,255,255,0.4)"
                : "rgba(255,255,255,0.1)",
              border: "none",
              padding: "18px 12px",
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
