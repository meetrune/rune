import { useRef, useEffect } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";

export function MpgDisplay() {
  const valueRef = useRef<HTMLSpanElement>(null);
  const labelRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const speed = state.sensors.SPEED?.v ?? 0;
      const isIdle = speed === 0;

      let display: string;
      let label: string;

      if (isIdle) {
        const gph = state.fuel.idle_gph;
        display = gph === null ? "--" : gph.toFixed(2);
        label = "IDLE GPH";
      } else {
        const mpg = state.fuel.instant_mpg;
        display = mpg === null ? "--" : mpg.toFixed(1);
        label = "INSTANT MPG";
      }

      if (valueRef.current) {
        valueRef.current.textContent = display;
      }
      if (labelRef.current) {
        labelRef.current.textContent = label;
      }
    });
    return unsub;
  }, []);

  return (
    <div style={styles.container}>
      <span ref={valueRef} className="font-data" style={styles.value}>
        --
      </span>
      <span ref={labelRef} style={styles.label}>
        INSTANT MPG
      </span>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "flex-end",
    gap: "2px",
    minWidth: "56px",
    minHeight: "56px",
    justifyContent: "center",
  },
  value: {
    fontSize: "30px",
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
