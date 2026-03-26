import { useRef, useEffect, useState } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";

// Prominent but non-intrusive offline indicator for driving screens.
// Shows a pulsing red dot + "OFFLINE" when the WebSocket disconnects.
// Tap to dismiss temporarily (reappears after 15 seconds if still offline).

export function OfflineIndicator() {
  const connected = useVehicleStore((s) => s.connected);
  const [dismissed, setDismissed] = useState(false);
  const dismissTimer = useRef<ReturnType<typeof setTimeout>>(null);

  // Reset dismissed state when connection status changes
  useEffect(() => {
    if (connected) setDismissed(false);
  }, [connected]);

  // Auto-reappear after 15 seconds if still offline
  const handleDismiss = () => {
    setDismissed(true);
    if (dismissTimer.current) clearTimeout(dismissTimer.current);
    dismissTimer.current = setTimeout(() => setDismissed(false), 15_000);
  };

  useEffect(() => {
    return () => { if (dismissTimer.current) clearTimeout(dismissTimer.current); };
  }, []);

  if (connected || dismissed) return null;

  return (
    <div
      style={{
        position: "absolute",
        top: 8,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 16px",
        borderRadius: 20,
        background: "rgba(239,68,68,0.12)",
        border: "1px solid rgba(239,68,68,0.25)",
        pointerEvents: "auto",
        cursor: "pointer",
        minHeight: 44,
        minWidth: 44,
      }}
      onClick={handleDismiss}
    >
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: "#ef4444",
          boxShadow: "0 0 8px rgba(239,68,68,0.5)",
          animation: "pulse-voice 1.5s ease-in-out infinite",
        }}
      />
      <span
        style={{
          fontFamily: "var(--font-data)",
          fontSize: 14,
          fontWeight: 600,
          color: "rgba(239,68,68,0.8)",
          letterSpacing: "0.1em",
        }}
      >
        OFFLINE
      </span>
    </div>
  );
}
