// RuneScreen -- Main screen shell. Assembles existing HUD components around the car SVG.
// Components imported here are created by other agents and will exist at build time.

import { CarView } from "@/components/car/CarView";
import { ConnectionPulse } from "@/components/hud/ConnectionPulse";
import { HealthBadge } from "@/components/hud/HealthBadge";
import { MpgDisplay } from "@/components/hud/MpgDisplay";
import { SensorStrip } from "@/components/hud/SensorStrip";
import { VoiceText } from "@/components/hud/VoiceText";
import { TripHeartbeat } from "@/components/hud/TripHeartbeat";

export function RuneScreen() {
  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        background: "var(--rune-bg)",
        overflow: "hidden",
        padding: "16px 20px 56px 20px",
      }}
    >
      {/* Top-left: "Rune" label + connection pulse */}
      <div
        style={{
          position: "absolute",
          top: "16px",
          left: "20px",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          zIndex: 10,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "16px",
            fontWeight: 500,
            color: "var(--rune-text-muted)",
            letterSpacing: "0.06em",
          }}
        >
          Rune
        </span>
        <ConnectionPulse />
      </div>

      {/* Top-left below label: health badge */}
      <div
        style={{
          position: "absolute",
          top: "42px",
          left: "20px",
          zIndex: 10,
        }}
      >
        <HealthBadge />
      </div>

      {/* Top-right: MPG display */}
      <div
        style={{
          position: "absolute",
          top: "16px",
          right: "20px",
          zIndex: 10,
        }}
      >
        <MpgDisplay />
      </div>

      {/* Center: Car SVG -- 65% width, vertically centered */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: "65%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <CarView />
      </div>

      {/* Right edge: sensor strip */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          right: "20px",
          transform: "translateY(-50%)",
          zIndex: 10,
        }}
      >
        <SensorStrip />
      </div>

      {/* Below car center: Rune's voice text */}
      <div
        style={{
          position: "absolute",
          bottom: "80px",
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 10,
          width: "60%",
          textAlign: "center",
        }}
      >
        <VoiceText />
      </div>

      {/* Bottom full-width: trip heartbeat */}
      <div
        style={{
          position: "absolute",
          bottom: "56px",
          left: "20px",
          right: "20px",
          zIndex: 10,
        }}
      >
        <TripHeartbeat />
      </div>
    </div>
  );
}
