import { HealthRing } from "@/components/telemetry/HealthRing";
import { SubsystemList } from "@/components/telemetry/SubsystemList";
import { SensorGrid } from "@/components/telemetry/SensorGrid";
import { SparklineStrip } from "@/components/telemetry/SparklineStrip";

export function TelemetryScreen() {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        gap: "16px",
        padding: "16px 20px 56px 20px",
        background: "var(--rune-bg)",
        overflow: "hidden",
      }}
    >
      {/* Left column: 38% -- Health overview */}
      <div
        style={{
          width: "38%",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          gap: "16px",
          overflow: "hidden",
        }}
      >
        {/* Health ring centered */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            paddingTop: "8px",
            paddingBottom: "4px",
          }}
        >
          <HealthRing />
        </div>

        {/* Subsystem breakdown */}
        <div style={{ flex: 1, overflow: "hidden" }}>
          <SubsystemList />
        </div>
      </div>

      {/* Right column: 62% -- Sensor data + sparklines */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          gap: "12px",
          overflow: "hidden",
        }}
      >
        {/* 4x3 sensor grid */}
        <div style={{ flex: 1 }}>
          <SensorGrid />
        </div>

        {/* Sparkline trend charts */}
        <SparklineStrip />
      </div>
    </div>
  );
}
