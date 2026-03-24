// Sensor warning/critical thresholds for 2026 Honda Accord SE L15BE 1.5T
// Sources: Honda service manual operating ranges, OBD-II standard ranges
// Values verified against Honda Accord community data and service specs

export interface SensorThreshold {
  warn: { low?: number; high?: number };
  critical: { low?: number; high?: number };
  unit: string;
  label: string;
}

export const SENSOR_THRESHOLDS: Record<string, SensorThreshold> = {
  RPM: {
    label: "RPM",
    unit: "rpm",
    warn: { high: 5500 },
    critical: { high: 6500 },
  },
  SPEED: {
    label: "Speed",
    unit: "kph",
    warn: {},
    critical: {},
  },
  COOLANT_TEMP: {
    label: "Coolant",
    unit: "\u00B0C",
    warn: { high: 100, low: 60 },
    critical: { high: 110 },
  },
  ENGINE_LOAD: {
    label: "Load",
    unit: "%",
    warn: { high: 85 },
    critical: { high: 95 },
  },
  THROTTLE_POS: {
    label: "Throttle",
    unit: "%",
    warn: {},
    critical: {},
  },
  MAF: {
    label: "MAF",
    unit: "g/s",
    warn: {},
    critical: {},
  },
  FUEL_LEVEL: {
    label: "Tank",
    unit: "%",
    warn: { low: 15 },
    critical: { low: 8 },
  },
  BATTERY_V: {
    label: "Volts",
    unit: "V",
    warn: { low: 12.4, high: 15.0 },
    critical: { low: 11.8, high: 15.5 },
  },
  STFT: {
    label: "STFT",
    unit: "%",
    warn: { low: -15, high: 15 },
    critical: { low: -25, high: 25 },
  },
  LTFT: {
    label: "LTFT",
    unit: "%",
    warn: { low: -10, high: 10 },
    critical: { low: -20, high: 20 },
  },
  INTAKE_TEMP: {
    label: "Intake",
    unit: "\u00B0C",
    warn: { high: 55 },
    critical: { high: 65 },
  },
  MAP: {
    label: "MAP",
    unit: "kPa",
    warn: {},
    critical: {},
  },
  CATALYST_TEMP: {
    label: "Cat",
    unit: "\u00B0C",
    warn: { high: 800 },
    critical: { high: 900 },
  },
  OIL_TEMP: {
    label: "Oil",
    unit: "\u00B0C",
    warn: { high: 120, low: 50 },
    critical: { high: 135 },
  },
  CVT_TEMP: {
    label: "CVT",
    unit: "\u00B0C",
    warn: { high: 110 },
    critical: { high: 125 },
  },
};

export type SensorState = "normal" | "warn" | "critical";

// Returns "normal" | "warn" | "critical" for a sensor value
export function getSensorState(
  key: string,
  value: number,
): SensorState {
  const t = SENSOR_THRESHOLDS[key];
  if (!t) return "normal";

  const { critical, warn } = t;

  if (
    (critical.high !== undefined && value >= critical.high) ||
    (critical.low !== undefined && value <= critical.low)
  ) {
    return "critical";
  }

  if (
    (warn.high !== undefined && value >= warn.high) ||
    (warn.low !== undefined && value <= warn.low)
  ) {
    return "warn";
  }

  return "normal";
}

// Returns "normal" | "warn" | "critical" for overall health score
export function getHealthState(score: number): SensorState {
  if (score === -1) return "normal"; // calibrating
  if (score < 50) return "critical";
  if (score < 70) return "warn";
  return "normal";
}

// Sensor label from thresholds config
export function getSensorLabel(key: string): string {
  return SENSOR_THRESHOLDS[key]?.label ?? key;
}

// Sensor unit from thresholds config
export function getSensorUnit(key: string): string {
  return SENSOR_THRESHOLDS[key]?.unit ?? "";
}

// Find the worst-scoring subsystem from HealthScores
export function getWorstSubsystem(
  health: import("@/types/vehicle").HealthScores,
): { id: import("@/types/vehicle").SubsystemId; score: number } | null {
  const subsystems: import("@/types/vehicle").SubsystemId[] = [
    "engine", "transmission", "fuel", "cooling", "exhaust", "electrical",
  ];

  let worst: { id: import("@/types/vehicle").SubsystemId; score: number } | null = null;

  for (const id of subsystems) {
    const score = health[id];
    if (score === -1) continue; // skip calibrating
    if (worst === null || score < worst.score) {
      worst = { id, score };
    }
  }

  return worst;
}
