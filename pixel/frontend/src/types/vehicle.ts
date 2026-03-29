export interface SensorReading {
  v: number;
  u: string;
}

export interface HealthScores {
  overall: number;
  engine: number;
  transmission: number;
  fuel: number;
  cooling: number;
  exhaust: number;
  electrical: number;
}

export interface FuelData {
  instant_mpg: number | null;
  idle_gph: number | null;
  trip_fuel_gal: number;
  trip_cost_usd: number;
  trip_distance_mi: number;
  tank_pct: number;
}

export interface VehicleMessage {
  t: number;
  d: Record<string, SensorReading>;
  health: HealthScores;
  fuel: FuelData;
}

export type SubsystemId =
  | "engine"
  | "transmission"
  | "fuel"
  | "cooling"
  | "exhaust"
  | "electrical";
