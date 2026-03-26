import { useRef, useEffect } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { getHealthState } from "@/constants/thresholds";

const STATE_COLORS: Record<string, string> = {
  normal: "var(--rune-text)",
  warn: "var(--rune-warn)",
  critical: "var(--rune-critical)",
};

export function HealthBadge() {
  const valueRef = useRef<HTMLSpanElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const score = state.health.overall;
      const display = score === -1 ? "--" : String(score);
      const colorState = getHealthState(score);
      const color = STATE_COLORS[colorState] ?? "var(--rune-text)";

      if (valueRef.current) {
        valueRef.current.textContent = display;
        valueRef.current.style.color = color;
      }
    });
    return unsub;
  }, []);

  return (
    <div ref={containerRef} style={styles.container}>
      <span ref={valueRef} className="font-data" style={styles.value}>
        --
      </span>
      <span style={styles.label}>HEALTH</span>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "flex-start",
    gap: "2px",
    minWidth: "56px",
    minHeight: "56px",
    justifyContent: "center",
  },
  value: {
    fontSize: "38px",
    fontWeight: 700,
    lineHeight: 1,
    color: "var(--rune-text)",
    fontFamily: "var(--font-data)",
  },
  label: {
    fontSize: "11px",
    fontWeight: 500,
    letterSpacing: "0.08em",
    textTransform: "uppercase" as const,
    color: "var(--rune-label)",
    fontFamily: "Inter, system-ui, sans-serif",
  },
} as const;
