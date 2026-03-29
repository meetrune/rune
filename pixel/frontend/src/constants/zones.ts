import type { SubsystemId } from "@/types/vehicle";
import type { ZoneConfig } from "@/types/zones";

// Sensor keys mapped to their subsystem
export const SUBSYSTEM_SENSORS: Record<SubsystemId, string[]> = {
  engine: ["RPM", "ENGINE_LOAD", "OIL_TEMP", "THROTTLE_POS"],
  transmission: ["RPM", "SPEED", "CVT_TEMP"],
  fuel: ["FUEL_LEVEL", "STFT", "LTFT", "MAF"],
  cooling: ["COOLANT_TEMP", "INTAKE_TEMP"],
  exhaust: ["CATALYST_TEMP", "STFT", "LTFT"],
  electrical: ["BATTERY_V"],
};

export const SUBSYSTEM_LABELS: Record<SubsystemId, string> = {
  engine: "ENG",
  transmission: "CVT",
  fuel: "FUEL",
  cooling: "COOL",
  exhaust: "EXH",
  electrical: "ELEC",
};

// Zone positions on the car SVG (percentages of viewBox)
// 2026 Honda Accord SE: engine front-right, CVT front-left,
// fuel tank under rear seats, cooling front-center,
// exhaust front-to-rear underside, battery front-left
export const ZONE_CONFIGS: ZoneConfig[] = [
  {
    subsystem: "engine",
    label: "ENG",
    topDown: { x: 52, y: 8, width: 22, height: 18, labelX: 63, labelY: 17 },
    sideProfile: { x: 10, y: 30, width: 20, height: 25, labelX: 20, labelY: 42 },
  },
  {
    subsystem: "transmission",
    label: "CVT",
    topDown: { x: 26, y: 8, width: 22, height: 18, labelX: 37, labelY: 17 },
    sideProfile: { x: 28, y: 45, width: 18, height: 20, labelX: 37, labelY: 55 },
  },
  {
    subsystem: "cooling",
    label: "COOL",
    topDown: { x: 30, y: 2, width: 40, height: 10, labelX: 50, labelY: 7 },
    sideProfile: { x: 5, y: 35, width: 12, height: 20, labelX: 11, labelY: 45 },
  },
  {
    subsystem: "fuel",
    label: "FUEL",
    topDown: { x: 30, y: 55, width: 40, height: 15, labelX: 50, labelY: 62 },
    sideProfile: { x: 50, y: 50, width: 20, height: 15, labelX: 60, labelY: 57 },
  },
  {
    subsystem: "exhaust",
    label: "EXH",
    topDown: { x: 55, y: 30, width: 18, height: 45, labelX: 64, labelY: 52 },
    sideProfile: { x: 30, y: 65, width: 50, height: 10, labelX: 55, labelY: 70 },
  },
  {
    subsystem: "electrical",
    label: "ELEC",
    topDown: { x: 26, y: 28, width: 15, height: 12, labelX: 33, labelY: 34 },
    sideProfile: { x: 15, y: 35, width: 10, height: 12, labelX: 20, labelY: 41 },
  },
];

// Quick lookup: subsystem -> zone config
export const ZONE_BY_SUBSYSTEM: Record<SubsystemId, ZoneConfig> = Object.fromEntries(
  ZONE_CONFIGS.map((z) => [z.subsystem, z])
) as Record<SubsystemId, ZoneConfig>;
