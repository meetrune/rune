import type { SubsystemId } from "@/types/vehicle";

export const ZONE_TO_SUBSYSTEM: Record<string, SubsystemId> = {
  zone_hood_right_engine: "engine",
  zone_hood_left_cvt: "transmission",
  zone_trunk_left_fuel: "fuel",
  zone_cabin_left: "cooling",
  zone_cabin_right: "cooling",
  zone_trunk_right_exhaust: "exhaust",
};

export const SUBSYSTEM_LABELS: Record<SubsystemId, string> = {
  engine: "Engine",
  transmission: "CVT",
  fuel: "Fuel",
  cooling: "Cooling",
  exhaust: "Exhaust",
  electrical: "Electrical",
};

export const SUBSYSTEM_SENSORS: Record<SubsystemId, string[]> = {
  engine: ["RPM", "ENGINE_LOAD", "OIL_TEMP", "COOLANT_TEMP"],
  transmission: ["RPM", "SPEED", "CVT_TEMP"],
  fuel: ["FUEL_LEVEL", "STFT", "LTFT"],
  cooling: ["COOLANT_TEMP", "INTAKE_TEMP", "OIL_TEMP"],
  exhaust: ["CATALYST_TEMP", "STFT", "LTFT"],
  electrical: ["BATTERY_V"],
};
