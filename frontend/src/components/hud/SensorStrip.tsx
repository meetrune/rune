import { useRef, useEffect, useCallback } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { useUiStore } from "@/stores/uiStore";
import { getSensorState, getSensorLabel, getSensorUnit } from "@/constants/thresholds";
import { SUBSYSTEM_SENSORS } from "@/constants/zones";
import type { SensorState } from "@/constants/thresholds";

const DEFAULT_SENSORS = ["RPM", "SPEED", "COOLANT_TEMP", "BATTERY_V", "FUEL_LEVEL"];

const STATE_COLORS: Record<SensorState, string> = {
  normal: "rgba(255,255,255,0.55)",
  warn: "rgba(251,191,36,0.7)",
  critical: "rgba(239,68,68,0.8)",
};

const LABEL_COLORS: Record<SensorState, string> = {
  normal: "rgba(255,255,255,0.12)",
  warn: "rgba(251,191,36,0.35)",
  critical: "rgba(239,68,68,0.4)",
};

interface CardRefs {
  value: HTMLSpanElement | null;
  label: HTMLSpanElement | null;
  dot: HTMLDivElement | null;
}

export function SensorStrip() {
  const cardRefs = useRef<CardRefs[]>([]);
  const activeSensorsRef = useRef<string[]>(DEFAULT_SENSORS);

  const focusedSubsystem = useUiStore((s) => s.focusedSubsystem);

  const getSensors = useCallback((): string[] => {
    if (focusedSubsystem) {
      return SUBSYSTEM_SENSORS[focusedSubsystem] ?? DEFAULT_SENSORS;
    }
    return DEFAULT_SENSORS;
  }, [focusedSubsystem]);

  const activeSensors = getSensors();
  activeSensorsRef.current = activeSensors;

  // Imperative 10Hz updates
  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const sensors = activeSensorsRef.current;
      for (let i = 0; i < sensors.length; i++) {
        const refs = cardRefs.current[i];
        if (!refs) continue;

        const key = sensors[i]!;
        const reading = state.sensors[key];
        const value = reading?.v;

        const sensorState: SensorState =
          value !== undefined ? getSensorState(key, value) : "normal";

        if (refs.value) {
          refs.value.textContent =
            value !== undefined ? formatValue(key, value) : "--";
          refs.value.style.color = STATE_COLORS[sensorState];
        }
        if (refs.label) {
          refs.label.style.color = LABEL_COLORS[sensorState];
        }
        if (refs.dot) {
          refs.dot.style.backgroundColor =
            sensorState === "normal" ? "transparent" : STATE_COLORS[sensorState];
        }
      }
    });
    return unsub;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={styles.strip}>
      {activeSensors.map((key, i) => (
        <div key={key} style={styles.row}>
          {/* Status dot -- only visible on warn/critical */}
          <div
            ref={(el) => {
              if (!cardRefs.current[i]) cardRefs.current[i] = { value: null, label: null, dot: null };
              cardRefs.current[i]!.dot = el;
            }}
            style={styles.dot}
          />
          {/* Value */}
          <span
            ref={(el) => {
              if (!cardRefs.current[i]) cardRefs.current[i] = { value: null, label: null, dot: null };
              cardRefs.current[i]!.value = el;
            }}
            className="font-data"
            style={styles.value}
          >
            --
          </span>
          {/* Label */}
          <span
            ref={(el) => {
              if (!cardRefs.current[i]) cardRefs.current[i] = { value: null, label: null, dot: null };
              cardRefs.current[i]!.label = el;
            }}
            style={styles.label}
          >
            {getSensorLabel(key)} <span style={styles.unit}>{getSensorUnit(key)}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

function formatValue(key: string, value: number): string {
  if (key === "RPM") return Math.round(value).toLocaleString();
  if (key === "SPEED") return Math.round(value).toString();
  if (key === "BATTERY_V") return value.toFixed(1);
  if (key === "FUEL_LEVEL") return Math.round(value).toString();
  if (key === "STFT" || key === "LTFT") {
    const sign = value >= 0 ? "+" : "";
    return `${sign}${value.toFixed(1)}`;
  }
  if (["COOLANT_TEMP", "OIL_TEMP", "INTAKE_TEMP", "CATALYST_TEMP", "CVT_TEMP"].includes(key)) {
    return Math.round(value).toString();
  }
  return value.toFixed(1);
}

const styles = {
  strip: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "16px",
    alignItems: "flex-end",
  },
  row: {
    display: "flex",
    flexDirection: "row" as const,
    alignItems: "baseline",
    gap: "6px",
  },
  dot: {
    width: "4px",
    height: "4px",
    borderRadius: "50%",
    backgroundColor: "transparent",
    flexShrink: 0,
    alignSelf: "center" as const,
    transition: "background-color 300ms",
  },
  value: {
    fontFamily: "var(--font-data)",
    fontSize: "22px",
    fontWeight: 600,
    color: "rgba(255,255,255,0.55)",
    lineHeight: 1,
    fontVariantNumeric: "tabular-nums" as const,
    transition: "color 300ms",
    minWidth: "48px",
    textAlign: "right" as const,
  },
  label: {
    fontFamily: "var(--font-ui)",
    fontSize: "9px",
    fontWeight: 400,
    color: "rgba(255,255,255,0.12)",
    letterSpacing: "0.04em",
    textTransform: "uppercase" as const,
    lineHeight: 1,
    transition: "color 300ms",
  },
  unit: {
    opacity: 0.6,
  },
} as const;
