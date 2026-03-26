import { useEffect, useRef } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";

export function ConnectionInfo() {
  const dotRef = useRef<HTMLDivElement>(null);
  const statusRef = useRef<HTMLSpanElement>(null);
  const rateRef = useRef<HTMLSpanElement>(null);

  // Track message timestamps for stream rate calculation
  const timestampsRef = useRef<number[]>([]);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const now = Date.now();
      const connected = state.connected;

      // Update connection dot and status text
      if (dotRef.current) {
        dotRef.current.style.backgroundColor = connected
          ? "#22c55e"
          : "var(--rune-critical)";
      }
      if (statusRef.current) {
        statusRef.current.textContent = connected ? "Connected" : "Disconnected";
        statusRef.current.style.color = connected
          ? "var(--rune-text)"
          : "var(--rune-label)";
      }

      // Compute stream rate from recent messages
      if (connected && state.lastMessageAt > 0) {
        const ts = timestampsRef.current;
        ts.push(now);
        // Keep only the last 2 seconds of timestamps
        const cutoff = now - 2000;
        while (ts.length > 0 && ts[0]! < cutoff) {
          ts.shift();
        }
        const rate = ts.length > 1 ? (ts.length / 2).toFixed(0) : "0";
        if (rateRef.current) {
          rateRef.current.textContent = `${rate} msg/s`;
        }
      } else {
        if (rateRef.current) {
          rateRef.current.textContent = "-- msg/s";
        }
      }
    });
    return unsub;
  }, []);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-data)",
          fontSize: "11px",
          letterSpacing: "0.12em",
          color: "var(--rune-label)",
          textTransform: "uppercase",
          opacity: 0.6,
        }}
      >
        Connection
      </span>

      {/* Status row */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <div
          ref={dotRef}
          style={{
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            backgroundColor: "var(--rune-critical)",
            flexShrink: 0,
          }}
        />
        <span
          ref={statusRef}
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "14px",
            color: "var(--rune-label)",
          }}
        >
          Disconnected
        </span>
      </div>

      {/* Stream rate */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "12px",
            color: "var(--rune-label)",
            opacity: 0.6,
          }}
        >
          Stream rate
        </span>
        <span
          ref={rateRef}
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "12px",
            color: "var(--rune-label)",
          }}
        >
          -- msg/s
        </span>
      </div>

      {/* Pi address */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "12px",
            color: "var(--rune-label)",
            opacity: 0.6,
          }}
        >
          Pi address
        </span>
        <span
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "12px",
            color: "var(--rune-label)",
          }}
        >
          192.168.4.1
        </span>
      </div>
    </div>
  );
}
