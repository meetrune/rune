import { ScreenContainer, NAV_ICONS } from "@/components/os/ScreenContainer";
import { VisualizationScreen } from "@/components/screens/VisualizationScreen";
import { DashboardScreen } from "@/components/screens/DashboardScreen";
import { SettingsScreen } from "@/components/screens/SettingsScreen";
import { useVehicleSocket } from "@/hooks/useVehicleSocket";
import { useWakeLock } from "@/hooks/useWakeLock";

export function App() {
  useVehicleSocket();
  useWakeLock();

  return (
    <ScreenContainer
      screens={[
        {
          id: "viz",
          label: "Rune",
          icon: NAV_ICONS.car,
          content: <VisualizationScreen />,
        },
        {
          id: "dash",
          label: "Data",
          icon: NAV_ICONS.gauge,
          content: <DashboardScreen />,
        },
        {
          id: "settings",
          label: "Settings",
          icon: NAV_ICONS.settings,
          content: <SettingsScreen />,
        },
      ]}
      defaultScreen="viz"
    />
  );
}
