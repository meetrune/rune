import { create } from "zustand";
import type { SubsystemId } from "@/types/vehicle";

interface UiState {
  focusedSubsystem: SubsystemId | null;
  revealComplete: boolean;
  setFocusedSubsystem: (id: SubsystemId | null) => void;
  setRevealComplete: (complete: boolean) => void;
}

export const useUiStore = create<UiState>((set) => ({
  focusedSubsystem: null,
  revealComplete: false,

  setFocusedSubsystem: (id: SubsystemId | null) => {
    set({ focusedSubsystem: id });
  },

  setRevealComplete: (complete: boolean) => {
    set({ revealComplete: complete });
  },
}));
