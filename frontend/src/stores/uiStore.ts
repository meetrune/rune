import { create } from "zustand";
import type { SubsystemId } from "@/types/vehicle";

export type ScreenId = "rune" | "telemetry" | "settings";

interface UiState {
  // Navigation
  activeScreen: ScreenId;
  navVisible: boolean;

  // Boot sequence
  bootComplete: boolean;

  // Zone focus (tap on car zone)
  focusedSubsystem: SubsystemId | null;

  // Line-draw reveal
  revealComplete: boolean;

  // Actions
  setActiveScreen: (screen: ScreenId) => void;
  setNavVisible: (visible: boolean) => void;
  setBootComplete: (complete: boolean) => void;
  setFocusedSubsystem: (id: SubsystemId | null) => void;
  setRevealComplete: (complete: boolean) => void;
}

export const useUiStore = create<UiState>((set) => ({
  activeScreen: "rune",
  navVisible: true,
  bootComplete: false,
  focusedSubsystem: null,
  revealComplete: false,

  setActiveScreen: (screen) => set({ activeScreen: screen }),
  setNavVisible: (visible) => set({ navVisible: visible }),
  setBootComplete: (complete) => set({ bootComplete: complete }),
  setFocusedSubsystem: (id) => set({ focusedSubsystem: id }),
  setRevealComplete: (complete) => set({ revealComplete: complete }),
}));
