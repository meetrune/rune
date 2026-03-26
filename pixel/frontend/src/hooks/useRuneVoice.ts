import { useRef, useEffect, useState } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { useSettingsStore } from "@/stores/settingsStore";
import { generateVoiceMessage, type VoiceState } from "@/constants/voice";
import { getWorstSubsystem } from "@/constants/thresholds";
import type { HealthScores, SubsystemId } from "@/types/vehicle";

interface RuneVoiceResult {
  message: string;
  state: VoiceState;
}

// Minimum score change to trigger a new voice message.
// Prevents message flicker from minor fluctuations.
const DEBOUNCE_THRESHOLD = 8;

export function useRuneVoice(): RuneVoiceResult {
  const [result, setResult] = useState<RuneVoiceResult>({
    message: "",
    state: "calibrating",
  });

  const prevHealthRef = useRef<HealthScores | null>(null);
  const prevStateRef = useRef<VoiceState>("calibrating");

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((store) => {
      // Respect the runeVoice setting
      if (!useSettingsStore.getState().runeVoice) return;

      const { health, connected } = store;

      // Disconnected overrides everything
      if (!connected) {
        if (prevStateRef.current !== "disconnected") {
          prevStateRef.current = "disconnected";
          const message = generateVoiceMessage({
            state: "disconnected",
            overallScore: health.overall,
          });
          setResult({ message, state: "disconnected" });
        }
        return;
      }

      // Calibrating: overall is -1
      if (health.overall === -1) {
        if (prevStateRef.current !== "calibrating") {
          prevStateRef.current = "calibrating";
          const message = generateVoiceMessage({
            state: "calibrating",
            overallScore: -1,
          });
          setResult({ message, state: "calibrating" });
        }
        return;
      }

      // Check if any subsystem changed by >= DEBOUNCE_THRESHOLD
      const prev = prevHealthRef.current;
      if (prev !== null) {
        const subsystems: SubsystemId[] = [
          "engine", "transmission", "fuel", "cooling", "exhaust", "electrical",
        ];
        const changed = subsystems.some((id) => {
          const prevScore = prev[id];
          const currScore = health[id];
          if (prevScore === -1 || currScore === -1) return prevScore !== currScore;
          return Math.abs(currScore - prevScore) >= DEBOUNCE_THRESHOLD;
        });

        const overallChanged =
          prev.overall === -1 ||
          Math.abs(health.overall - prev.overall) >= DEBOUNCE_THRESHOLD;

        if (!changed && !overallChanged) return;
      }

      prevHealthRef.current = { ...health };

      // Determine current state
      const worst = getWorstSubsystem(health);

      let newState: VoiceState;

      if (worst && worst.score < 50) {
        newState = "critical";
      } else if (worst && worst.score < 70) {
        newState = "warning";
      } else if (
        (prevStateRef.current === "warning" || prevStateRef.current === "critical") &&
        health.overall >= 70
      ) {
        newState = "recovering";
      } else {
        newState = "good";
      }

      prevStateRef.current = newState;

      const message = generateVoiceMessage({
        state: newState,
        overallScore: health.overall,
        worstSubsystem: worst?.id,
        worstScore: worst?.score,
      });

      setResult({ message, state: newState });
    });

    return unsub;
  }, []);

  return result;
}
