import { useEffect, useRef } from "react";
import { useSettingsStore } from "@/stores/settingsStore";
import { useVehicleStore } from "@/stores/vehicleStore";

const PIXEL_SHIFT_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
const PIXEL_SHIFT_MAX_PX = 2;
const BRIGHTNESS_DIM_DELAY_MS = 30 * 60 * 1000; // 30 minutes idle
const BRIGHTNESS_DIM_AMOUNT = 0.85; // 15% reduction
const HAPTIC_DEBOUNCE_MS = 30_000; // 30s per subsystem

// Shifts static text elements by 1-2px every 5 minutes to prevent OLED burn-in.
// Also handles brightness dimming after extended idle and haptic alerts.
export function useBurnInProtection() {
  const lastInteractionRef = useRef(Date.now());
  const dimmedRef = useRef(false);
  const hapticTimersRef = useRef<Record<string, number>>({});

  // Track user interaction to reset idle timer
  useEffect(() => {
    const onInteraction = () => {
      lastInteractionRef.current = Date.now();

      // Restore brightness if dimmed
      if (dimmedRef.current) {
        dimmedRef.current = false;
        document.documentElement.style.opacity = "1";
      }
    };

    window.addEventListener("touchstart", onInteraction, { passive: true });
    window.addEventListener("pointerdown", onInteraction, { passive: true });
    return () => {
      window.removeEventListener("touchstart", onInteraction);
      window.removeEventListener("pointerdown", onInteraction);
    };
  }, []);

  // Pixel shift: drift static elements 1-2px in a random direction every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      const dx = (Math.random() * 2 - 1) * PIXEL_SHIFT_MAX_PX;
      const dy = (Math.random() * 2 - 1) * PIXEL_SHIFT_MAX_PX;
      document.documentElement.style.setProperty("--burn-shift-x", `${dx.toFixed(1)}px`);
      document.documentElement.style.setProperty("--burn-shift-y", `${dy.toFixed(1)}px`);
    }, PIXEL_SHIFT_INTERVAL_MS);

    return () => {
      clearInterval(interval);
      document.documentElement.style.opacity = "1";
      document.documentElement.style.removeProperty("--burn-shift-x");
      document.documentElement.style.removeProperty("--burn-shift-y");
    };
  }, []);

  // Brightness reduction after 30 minutes idle (not during warnings)
  useEffect(() => {
    const interval = setInterval(() => {
      const idle = Date.now() - lastInteractionRef.current;
      const hasWarning = useVehicleStore.getState().health.overall < 70 &&
        useVehicleStore.getState().health.overall !== -1;

      if (idle > BRIGHTNESS_DIM_DELAY_MS && !dimmedRef.current && !hasWarning) {
        dimmedRef.current = true;
        document.documentElement.style.opacity = String(BRIGHTNESS_DIM_AMOUNT);
      }
    }, 60_000); // check every minute

    return () => clearInterval(interval);
  }, []);

  // Haptic feedback on health warnings
  useEffect(() => {
    const hapticEnabled = () => useSettingsStore.getState().hapticFeedback;

    const unsub = useVehicleStore.subscribe((state) => {
      if (!hapticEnabled()) return;
      if (!navigator.vibrate) return;

      const subsystems = ["engine", "transmission", "fuel", "cooling", "exhaust", "electrical"] as const;
      const now = Date.now();

      for (const id of subsystems) {
        const score = state.health[id];
        if (score !== -1 && score < 70) {
          const lastFired = hapticTimersRef.current[id] ?? 0;
          if (now - lastFired > HAPTIC_DEBOUNCE_MS) {
            hapticTimersRef.current[id] = now;
            navigator.vibrate(score < 50 ? [100, 50, 100] : [50]);
          }
        }
      }
    });

    return unsub;
  }, []);

  // Nav auto-hide (10s idle) is handled by NavBar itself
  // Grid drift is handled by CSS animation in global.css
}
