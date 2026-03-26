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
    // Backend: normal 70-100, warning 40-105, critical 0-110
    label: "Coolant",
    unit: "\u00B0C",
    warn: { high: 105, low: 40 },
    critical: { high: 110, low: 0 },
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
    // Backend: normal 12.0-15.0, warning 11.8-15.2, critical 11.0-16.0
    // Honda ELD cycles voltage to 12.4-12.9V during cruising -- that is normal
    label: "Volts",
    unit: "V",
    warn: { low: 11.8, high: 15.2 },
    critical: { low: 11.0, high: 16.0 },
  },
  STFT: {
    label: "STFT",
    unit: "%",
    warn: { low: -15, high: 15 },
    critical: { low: -25, high: 25 },
  },
  LTFT: {
    // Backend: normal +/-5%, warning +/-8%, critical +/-10%
    label: "LTFT",
    unit: "%",
    warn: { low: -8, high: 8 },
    critical: { low: -10, high: 10 },
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
    // Backend: normal 300-800, warning 100-950, critical 0-1050
    label: "Cat",
    unit: "\u00B0C",
    warn: { high: 950 },
    critical: { high: 1050 },
  },
  OIL_TEMP: {
    // Backend: normal 80-120, warning 40-130, critical 0-140
    label: "Oil",
    unit: "\u00B0C",
    warn: { high: 130, low: 40 },
    critical: { high: 140, low: 0 },
  },
  CVT_TEMP: {
    // Backend: normal 50-100, warning 20-115, critical 0-130
    label: "CVT",
    unit: "\u00B0C",
    warn: { high: 115 },
    critical: { high: 130 },
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
