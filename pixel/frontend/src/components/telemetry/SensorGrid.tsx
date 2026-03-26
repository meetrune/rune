import { useEffect, useRef } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { getSensorState, getSensorLabel, getSensorUnit } from "@/constants/thresholds";

const SENSOR_KEYS = [
  "RPM",
  "SPEED",
  "COOLANT_TEMP",
  "ENGINE_LOAD",
  "THROTTLE_POS",
  "MAF",
  "FUEL_LEVEL",
  "BATTERY_V",
  "INTAKE_TEMP",
  "OIL_TEMP",
  "CATALYST_TEMP",
  "CVT_TEMP",
] as const;

// Format sensor values for display
function formatValue(key: string, value: number): string {
  switch (key) {
    case "RPM":
      return String(Math.round(value));
    case "SPEED":
      return String(Math.round(value));
    case "BATTERY_V":
      return value.toFixed(1);
    case "MAF":
      return value.toFixed(1);
    default:
      return String(Math.round(value));
  }
}

function stateColor(state: string): string {
  if (state === "critical") return "var(--rune-critical)";
  if (state === "warn") return "var(--rune-warn)";
  return "rgba(255,255,255,0.12)";
}

interface CellRefs {
  value: HTMLSpanElement | null;
  border: HTMLDivElement | null;
}

export function SensorGrid() {
  const cellRefs = useRef<Record<string, CellRefs>>(
    Object.fromEntries(SENSOR_KEYS.map((k) => [k, { value: null, border: null }])) as Record<string, CellRefs>
  );

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      for (const key of SENSOR_KEYS) {
        const refs = cellRefs.current[key];
        if (!refs) continue;
        const reading = state.sensors[key];

        if (refs.value) {
          if (reading) {
            refs.value.textContent = formatValue(key, reading.v);
            const sensorState = getSensorState(key, reading.v);
            refs.value.style.color =
              sensorState === "normal" ? "var(--rune-text)" : stateColor(sensorState);
          } else {
            refs.value.textContent = "--";
            refs.value.style.color = "var(--rune-label)";
          }
        }

        if (refs.border) {
          if (reading) {
            const sensorState = getSensorState(key, reading.v);
            refs.border.style.borderLeftColor = stateColor(sensorState);
          } else {
            refs.border.style.borderLeftColor = "rgba(255,255,255,0.06)";
          }
        }
      }
    });
    return unsub;
  }, []);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gap: "1px",
      }}
    >
      {SENSOR_KEYS.map((key) => (
        <div
          key={key}
          ref={(el) => {
            if (el) cellRefs.current[key]!.border = el;
          }}
          style={{
            borderLeft: "3px solid rgba(255,255,255,0.06)",
            padding: "8px 8px 6px",
            transition: "border-left-color 0.3s",
          }}
        >
          <span
            ref={(el) => {
              if (el) cellRefs.current[key]!.value = el;
            }}
            style={{
              fontFamily: "var(--font-data)",
              fontSize: "16px",
              fontWeight: 500,
              color: "var(--rune-label)",
              display: "block",
              lineHeight: 1.2,
            }}
          >
            --
          </span>
          <span
            style={{
              fontFamily: "var(--font-data)",
              fontSize: "10px",
              color: "var(--rune-label)",
              opacity: 0.6,
              letterSpacing: "0.04em",
            }}
          >
            {getSensorLabel(key)} {getSensorUnit(key)}
          </span>
        </div>
      ))}
    </div>
  );
}
