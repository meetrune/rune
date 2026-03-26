import { create } from "zustand";
import type { SensorReading, HealthScores, FuelData, VehicleMessage } from "@/types/vehicle";

const DEFAULT_HEALTH: HealthScores = {
  overall: -1,
  engine: -1,
  transmission: -1,
  fuel: -1,
  cooling: -1,
  exhaust: -1,
  electrical: -1,
};

const DEFAULT_FUEL: FuelData = {
  instant_mpg: null,
  idle_gph: null,
  trip_fuel_gal: 0,
  trip_cost_usd: 0,
  trip_distance_mi: 0,
  tank_pct: 0,
};

interface VehicleState {
  connected: boolean;
  lastMessageAt: number;
  sensors: Record<string, SensorReading>;
  health: HealthScores;
  fuel: FuelData;
  updateFromMessage: (msg: VehicleMessage) => void;
  setConnected: (connected: boolean) => void;
}

export const useVehicleStore = create<VehicleState>((set) => ({
  connected: false,
  lastMessageAt: 0,
  sensors: {},
  health: DEFAULT_HEALTH,
  fuel: DEFAULT_FUEL,

  updateFromMessage: (msg: VehicleMessage) => {
    set((state) => ({
      // Merge sensors: keep last-known values for sensors not in this message.
      // Prevents flicker if backend sends partial data during OBD polling cycle.
      sensors: { ...state.sensors, ...msg.d },
      health: msg.health,
      fuel: msg.fuel,
      lastMessageAt: msg.t,
      connected: true,
    }));
  },

  setConnected: (connected: boolean) => {
    set({ connected });
  },
}));
