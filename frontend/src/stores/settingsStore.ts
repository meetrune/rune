import { create } from "zustand";

interface SettingsState {
  // Visual
  gridBackground: boolean;

  // Behavior
  runeVoice: boolean;
  hapticFeedback: boolean;
  parallaxTilt: boolean;

  // Fuel
  gasPricePerGallon: number;
  units: "imperial" | "metric";

  // Actions
  toggle: (key: "gridBackground" | "runeVoice" | "hapticFeedback" | "parallaxTilt") => void;
  setGasPrice: (price: number) => void;
  setUnits: (units: "imperial" | "metric") => void;
}

const STORAGE_KEY = "rune-settings";

function loadFromStorage(): Partial<SettingsState> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // Corrupt storage -- use defaults
  }
  return {};
}

function saveToStorage(state: SettingsState) {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        gridBackground: state.gridBackground,
        runeVoice: state.runeVoice,
        hapticFeedback: state.hapticFeedback,
        parallaxTilt: state.parallaxTilt,
        gasPricePerGallon: state.gasPricePerGallon,
        units: state.units,
      }),
    );
  } catch {
    // Storage full or unavailable -- silent fail
  }
}

const stored = loadFromStorage();

export const useSettingsStore = create<SettingsState>((set, get) => ({
  gridBackground: stored.gridBackground ?? true,
  runeVoice: stored.runeVoice ?? true,
  hapticFeedback: stored.hapticFeedback ?? true,
  parallaxTilt: stored.parallaxTilt ?? false,
  gasPricePerGallon: stored.gasPricePerGallon ?? 3.50,
  units: stored.units ?? "imperial",

  toggle: (key) => {
    set((s) => {
      const next = { ...s, [key]: !s[key] };
      saveToStorage(next);
      return { [key]: next[key] };
    });
  },

  setGasPrice: (price) => {
    set({ gasPricePerGallon: price });
    saveToStorage(get());
  },

  setUnits: (units) => {
    set({ units });
    saveToStorage(get());
  },
}));
