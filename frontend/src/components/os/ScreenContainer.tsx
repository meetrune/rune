import { type ReactNode, useEffect, useCallback } from "react";
import { useUiStore, type ScreenId } from "@/stores/uiStore";
import { NavBar } from "./NavBar";

interface ScreenContainerProps {
  screens: Record<ScreenId, ReactNode>;
}

export function ScreenContainer({ screens }: ScreenContainerProps) {
  const activeScreen = useUiStore((s) => s.activeScreen);
  const navVisible = useUiStore((s) => s.navVisible);
  const setNavVisible = useUiStore((s) => s.setNavVisible);

  // Tap anywhere in the bottom 56px zone to show nav when hidden
  const handleTouchStart = useCallback(
    (e: TouchEvent) => {
      if (navVisible) return;
      const touch = e.touches[0];
      if (touch && touch.clientY > window.innerHeight - 56) {
        setNavVisible(true);
      }
    },
    [navVisible, setNavVisible],
  );

  useEffect(() => {
    window.addEventListener("touchstart", handleTouchStart, { passive: true });
    return () => window.removeEventListener("touchstart", handleTouchStart);
  }, [handleTouchStart]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative", overflow: "hidden" }}>
      {(Object.keys(screens) as ScreenId[]).map((id) => (
        <div
          key={id}
          style={{
            position: "absolute",
            inset: 0,
            opacity: activeScreen === id ? 1 : 0,
            pointerEvents: activeScreen === id ? "auto" : "none",
            transition: "opacity 350ms ease",
          }}
        >
          {screens[id]}
        </div>
      ))}
      <NavBar />
    </div>
  );
}
