import { useState } from "react";
import { ScreenContainer } from "@/components/os/ScreenContainer";
import { RuneScreen } from "@/components/screens/RuneScreen";
import { TelemetryScreen } from "@/components/screens/TelemetryScreen";
import { SettingsScreen } from "@/components/screens/SettingsScreen";
import { BootScreen } from "@/components/boot/BootScreen";
import { useVehicleSocket } from "@/hooks/useVehicleSocket";
import { useWakeLock } from "@/hooks/useWakeLock";
import { useBurnInProtection } from "@/hooks/useBurnInProtection";

export function App() {
  useVehicleSocket();
  useWakeLock();
  useBurnInProtection();

  const [booted, setBooted] = useState(false);

  if (!booted) {
    return (
      <>
        <BootScreen onComplete={() => setBooted(true)} />
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
