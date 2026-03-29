import { useState } from "react";
import { ScreenContainer } from "@/components/os/ScreenContainer";
import { RuneScreen } from "@/components/screens/RuneScreen";
import { TelemetryScreen } from "@/components/screens/TelemetryScreen";
import { TripSummaryScreen } from "@/components/screens/TripSummaryScreen";
import { SettingsScreen } from "@/components/screens/SettingsScreen";
import { BootScreen } from "@/components/boot/BootScreen";
import { TripEndPopup } from "@/components/trip/TripEndPopup";
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
          telemetry: <TelemetryScreen />,
          rune: <RuneScreen />,
          "trip-summary": <TripSummaryScreen />,
          settings: <SettingsScreen />,
        }}
      />
      <TripEndPopup />
      <div className="portrait-fallback">Rotate to landscape</div>
    </>
  );
}
