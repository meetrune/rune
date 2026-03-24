import { useState } from "react";
import { ScreenContainer } from "@/components/os/ScreenContainer";
import { RuneScreen } from "@/components/screens/RuneScreen";
import { TelemetryScreen } from "@/components/screens/TelemetryScreen";
import { SettingsScreen } from "@/components/screens/SettingsScreen";
import { BootScreen } from "@/components/boot/BootScreen";
import { LineReveal } from "@/components/boot/LineReveal";
import { useVehicleSocket } from "@/hooks/useVehicleSocket";
import { useWakeLock } from "@/hooks/useWakeLock";
import { useBurnInProtection } from "@/hooks/useBurnInProtection";
import { useUiStore } from "@/stores/uiStore";

type BootPhase = "boot" | "reveal" | "ready";

export function App() {
  useVehicleSocket();
  useWakeLock();
  useBurnInProtection();

  const bootComplete = useUiStore((s) => s.bootComplete);
  const setBootComplete = useUiStore((s) => s.setBootComplete);
  const [bootPhase, setBootPhase] = useState<BootPhase>(
    bootComplete ? "ready" : "boot",
  );

  // Boot sequence: boot -> reveal -> ready
  if (bootPhase === "boot") {
    return (
      <>
        <BootScreen onComplete={() => setBootPhase("reveal")} />
        <div className="portrait-fallback">Rotate to landscape</div>
      </>
    );
  }

  if (bootPhase === "reveal") {
    return (
      <>
        <LineReveal
          onComplete={() => {
            setBootPhase("ready");
            setBootComplete(true);
          }}
        />
        <div className="portrait-fallback">Rotate to landscape</div>
      </>
    );
  }

  return (
    <>
      <ScreenContainer
        screens={{
          rune: <RuneScreen />,
          telemetry: <TelemetryScreen />,
          settings: <SettingsScreen />,
        }}
      />
      <div className="portrait-fallback">Rotate to landscape</div>
    </>
  );
}
