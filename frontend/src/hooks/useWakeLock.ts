import { useEffect, useRef } from "react";

export function useWakeLock() {
  const lockRef = useRef<WakeLockSentinel | null>(null);

  useEffect(() => {
    async function acquire() {
      try {
        if ("wakeLock" in navigator) {
          lockRef.current = await navigator.wakeLock.request("screen");
        }
      } catch {
        // Wake Lock request failed (e.g., low battery)
      }
    }

    function handleVisibilityChange() {
      if (document.visibilityState === "visible") {
        acquire();
      }
    }

    acquire();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      lockRef.current?.release().catch(() => {});
    };
  }, []);
}
