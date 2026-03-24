import { useState, useRef, useEffect } from "react";
import { AccordTopDown } from "./AccordTopDown";
import { AccordSideProfile } from "./AccordSideProfile";
import { FuelParticles } from "./FuelParticles";
import { ZoneOverlays } from "./ZoneOverlays";
import { useVehicleStore } from "@/stores/vehicleStore";

type ViewMode = "topDown" | "sideProfile";

// ViewBox dimensions per view
const VIEW_CONFIG = {
  topDown: {
    viewBox: "0 0 400 180",
    // Fuel tank centre -> engine centre (from ZONE_CONFIGS_TOP_DOWN)
    fuelStart: { x: 310, y: 90 },
    fuelEnd: { x: 65, y: 108 },
  },
  sideProfile: {
    viewBox: "0 0 480 160",
    fuelStart: { x: 340, y: 118 },
    fuelEnd: { x: 90, y: 88 },
  },
} as const;

/**
 * Main car view container.
 * Renders the Honda Accord SVG (top-down or side profile) with:
 *   - Breathing animation synced to RPM
 *   - Fuel flow particles
 *   - Tappable zone overlays with health labels and ripple
 *   - Floating toggle to switch views
 */
export function CarView(): React.JSX.Element {
  const [viewMode, setViewMode] = useState<ViewMode>("topDown");
  const containerRef = useRef<HTMLDivElement>(null);
  const breathingRef = useRef<HTMLDivElement>(null);

  const config = VIEW_CONFIG[viewMode];

  // Imperatively subscribe to RPM for breathing animation speed.
  // Breathing = CSS scale pulse +-0.6%. Duration derived from RPM.
  // 800 RPM idle = 60/800 * 2 = 0.15s per pulse -- but we use a gentler
  // multiplier so the breathing feels calm, not frantic.
  useEffect(() => {
    const unsubscribe = useVehicleStore.subscribe((state) => {
      const rpm = state.sensors["RPM"]?.v ?? 0;
      const el = breathingRef.current;
      if (!el) return;

      if (rpm > 0) {
        // Map RPM to breathing duration. Lower RPM = slower breath.
        // 800 RPM -> ~2.5s, 3000 RPM -> ~0.67s, 6000 RPM -> ~0.33s
        const duration = Math.max(0.3, (60 / rpm) * 33);
        el.style.animationDuration = `${duration}s`;
        el.style.animationPlayState = "running";
      } else {
        el.style.animationPlayState = "paused";
        el.style.transform = "scale(1)";
      }
    });

    return unsubscribe;
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width: "65vw",
        maxWidth: "720px",
        margin: "0 auto",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Breathing keyframes injected via style tag */}
      <style>{`
        @keyframes car-breathing {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.006); }
        }
      `}</style>

      {/* Car SVG with breathing animation */}
      <div
        ref={breathingRef}
        style={{
          position: "relative",
          width: "100%",
          animation: "car-breathing 2.5s ease-in-out infinite",
          animationPlayState: "paused",
          willChange: "transform",
        }}
      >
        {viewMode === "topDown" ? (
          <AccordTopDown style={{ width: "100%", height: "auto", display: "block" }} />
        ) : (
          <AccordSideProfile style={{ width: "100%", height: "auto", display: "block" }} />
        )}

        {/* Fuel flow particles */}
        <FuelParticles
          viewBox={config.viewBox}
          startX={config.fuelStart.x}
          startY={config.fuelStart.y}
          endX={config.fuelEnd.x}
          endY={config.fuelEnd.y}
        />

        {/* Zone overlays */}
        <ZoneOverlays view={viewMode} viewBox={config.viewBox} />
      </div>

      {/* Floating view toggle button */}
      <button
        onClick={() =>
          setViewMode((m) => (m === "topDown" ? "sideProfile" : "topDown"))
        }
        aria-label={`Switch to ${viewMode === "topDown" ? "side profile" : "top down"} view`}
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          width: 56,
          height: 56,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "rgba(255,255,255,0.04)",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 12,
          cursor: "pointer",
          padding: 0,
          touchAction: "manipulation",
          WebkitTapHighlightColor: "transparent",
        }}
      >
        {viewMode === "topDown" ? (
          <SideProfileIcon />
        ) : (
          <TopDownIcon />
        )}
      </button>
    </div>
  );
}

/** Minimal SVG icon representing the side profile view. */
function SideProfileIcon(): React.JSX.Element {
  return (
    <svg
      width={24}
      height={24}
      viewBox="0 0 24 24"
      fill="none"
      stroke="rgba(255,255,255,0.5)"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* Simple side car silhouette */}
      <path d="M2 16 L4 14 L8 14 L10 10 L16 10 L18 12 L22 12 L22 16 Z" />
      <circle cx={7} cy={16} r={2} />
      <circle cx={19} cy={16} r={2} />
    </svg>
  );
}

/** Minimal SVG icon representing the top-down view. */
function TopDownIcon(): React.JSX.Element {
  return (
    <svg
      width={24}
      height={24}
      viewBox="0 0 24 24"
      fill="none"
      stroke="rgba(255,255,255,0.5)"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* Simple top-down car shape */}
      <path d="M8 2 Q6 4 6 6 L6 18 Q6 20 8 22 L16 22 Q18 20 18 18 L18 6 Q18 4 16 2 Z" />
      <line x1="6" y1="8" x2="18" y2="8" />
      <line x1="6" y1="16" x2="18" y2="16" />
    </svg>
  );
}
