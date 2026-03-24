import { useRef, useEffect, useCallback } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { useUiStore } from "@/stores/uiStore";
import {
  getSensorState,
  getSensorLabel,
  getSensorUnit,
} from "@/constants/thresholds";
import { SUBSYSTEM_SENSORS } from "@/constants/zones";
import type { SensorState } from "@/constants/thresholds";

const DEFAULT_SENSORS = ["RPM", "SPEED", "COOLANT_TEMP", "BATTERY_V", "FUEL_LEVEL"];

const ACCENT_COLORS: Record<SensorState, string> = {
  normal: "rgba(255, 255, 255, 0.25)",
  warn: "var(--rune-warn)",
  critical: "var(--rune-critical)",
};

const VALUE_COLORS: Record<SensorState, string> = {
  normal: "var(--rune-text)",
  warn: "var(--rune-warn)",
  critical: "var(--rune-critical)",
};

interface CardRefs {
  value: HTMLSpanElement | null;
  accent: HTMLDivElement | null;
}

export function SensorStrip() {
  const cardRefs = useRef<CardRefs[]>([]);
  const activeSensorsRef = useRef<string[]>(DEFAULT_SENSORS);

  // Track focused subsystem reactively (this changes rarely, React re-render is fine)
  const focusedSubsystem = useUiStore((s) => s.focusedSubsystem);

  const getSensors = useCallback((): string[] => {
    if (focusedSubsystem) {
      return SUBSYSTEM_SENSORS[focusedSubsystem] ?? DEFAULT_SENSORS;
    }
    return DEFAULT_SENSORS;
  }, [focusedSubsystem]);

  const activeSensors = getSensors();
  activeSensorsRef.current = activeSensors;

  // Imperative updates at 10Hz
  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const sensors = activeSensorsRef.current;
      for (let i = 0; i < sensors.length; i++) {
        const refs = cardRefs.current[i];
        if (!refs) continue;

        const key = sensors[i]!;
        const reading = state.sensors[key];
        const value = reading?.v;

        if (refs.value) {
          refs.value.textContent =
            value !== undefined ? formatSensorValue(key, value) : "--";

          const sensorState: SensorState =
            value !== undefined ? getSensorState(key, value) : "normal";
          refs.value.style.color = VALUE_COLORS[sensorState];
          if (refs.accent) {
            refs.accent.style.backgroundColor = ACCENT_COLORS[sensorState];
          }
        }
      }
    });
    return unsub;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={styles.strip}>
      {activeSensors.map((key, i) => (
        <div key={key} style={styles.card}>
          <div
            ref={(el) => {
              if (!cardRefs.current[i]) {
                cardRefs.current[i] = { value: null, accent: null };
              }
              cardRefs.current[i].accent = el;
            }}
            style={styles.accent}
          />
          <div style={styles.cardContent}>
            <span
              ref={(el) => {
                if (!cardRefs.current[i]) {
                  cardRefs.current[i] = { value: null, accent: null };
                }
                cardRefs.current[i].value = el;
              }}
              className="font-data"
              style={styles.value}
            >
              --
            </span>
            <span style={styles.unit}>
              {getSensorLabel(key)} {getSensorUnit(key) ? `(${getSensorUnit(key)})` : ""}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function formatSensorValue(key: string, value: number): string {
  // RPM and speed are integers
  if (key === "RPM") return Math.round(value).toLocaleString();
  if (key === "SPEED") return Math.round(value).toString();
  // Voltage gets 1 decimal
  if (key === "BATTERY_V") return value.toFixed(1);
  // Fuel level is integer percent
  if (key === "FUEL_LEVEL") return Math.round(value).toString();
  // Fuel trims get 1 decimal with sign
  if (key === "STFT" || key === "LTFT") {
    const sign = value >= 0 ? "+" : "";
    return `${sign}${value.toFixed(1)}`;
  }
  // Temperature values are integers
  if (
    key === "COOLANT_TEMP" ||
    key === "OIL_TEMP" ||
    key === "INTAKE_TEMP" ||
    key === "CATALYST_TEMP" ||
    key === "CVT_TEMP"
  ) {
    return Math.round(value).toString();
  }
  // Default: 1 decimal
  return value.toFixed(1);
}

const styles = {
  strip: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "6px",
    padding: "4px 0",
  },
  card: {
    display: "flex",
    flexDirection: "row" as const,
    alignItems: "stretch",
    minHeight: "44px",
    minWidth: "56px",
    background: "rgba(255, 255, 255, 0.03)",
    backdropFilter: "blur(8px)",
    WebkitBackdropFilter: "blur(8px)",
    borderRadius: "6px",
    overflow: "hidden",
  },
  accent: {
    width: "3px",
    flexShrink: 0,
    backgroundColor: "rgba(255, 255, 255, 0.25)",
    transition: "background-color 300ms ease",
  },
  cardContent: {
    display: "flex",
    flexDirection: "column" as const,
    justifyContent: "center",
    padding: "6px 10px",
    gap: "1px",
  },
  value: {
    fontSize: "16px",
    fontWeight: 600,
    lineHeight: 1.2,
    color: "var(--rune-text)",
    fontFamily: "var(--font-data)",
    transition: "color 300ms ease",
  },
  unit: {
    fontSize: "10px",
    fontWeight: 400,
    color: "var(--rune-label)",
    fontFamily: "Inter, system-ui, sans-serif",
    lineHeight: 1,
  },
} as const;
