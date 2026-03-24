import { useRef, useEffect } from "react";
import { Html } from "@react-three/drei";
import { useVehicleStore } from "@/stores/vehicleStore";
import type { SubsystemId } from "@/types/vehicle";

// 3D positions of each subsystem on the Honda Accord model.
// Car is ~4.9m long (Y axis), ~2.1m wide (X axis), ~1.4m tall (Z axis).
// Origin is centered via the bounding box centering in CarScene.
const ZONE_POSITIONS: { id: SubsystemId; pos: [number, number, number] }[] = [
  { id: "engine",       pos: [0.4, 1.6, 0.3] },    // front-right
  { id: "transmission", pos: [-0.3, 1.4, -0.1] },   // front-left, lower
  { id: "cooling",      pos: [0, 2.2, 0.2] },        // front-center (radiator)
  { id: "fuel",         pos: [0, -0.8, -0.2] },       // rear-center (under back seats)
  { id: "exhaust",      pos: [0.4, -1.2, -0.4] },     // underside rear-right
  { id: "electrical",   pos: [-0.5, 1.8, 0.3] },      // front-left (battery)
];

function getState(score: number): "normal" | "warn" | "critical" {
  if (score === -1) return "normal";
  if (score < 50) return "critical";
  if (score < 70) return "warn";
  return "normal";
}

const STATE_COLORS = {
  normal: "transparent",
  warn: "rgba(251,191,36,0.8)",
  critical: "rgba(239,68,68,0.9)",
};

// Renders pulsing dots at subsystem locations when there's an issue
export function ZoneIndicators() {
  const dotRefs = useRef<(HTMLDivElement | null)[]>([]);
  const rippleRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      ZONE_POSITIONS.forEach((zone, i) => {
        const score = state.health[zone.id];
        const st = getState(score);
        const dot = dotRefs.current[i];
        const ripple = rippleRefs.current[i];
        if (!dot || !ripple) return;

        if (st === "normal") {
          dot.style.opacity = "0";
          ripple.style.display = "none";
        } else {
          const color = STATE_COLORS[st];
          dot.style.opacity = "1";
          dot.style.backgroundColor = color;
          dot.style.boxShadow = `0 0 12px ${color}`;
          ripple.style.display = "block";
          ripple.style.borderColor = color;
        }
      });
    });
    return unsub;
  }, []);

  return (
    <>
      {ZONE_POSITIONS.map((zone, i) => (
        <Html
          key={zone.id}
          position={zone.pos}
          center
          style={{ pointerEvents: "none" }}
        >
          <div style={{ position: "relative", width: "12px", height: "12px" }}>
            {/* Core dot */}
            <div
              ref={(el) => { dotRefs.current[i] = el; }}
              style={{
                position: "absolute",
                inset: 0,
                borderRadius: "50%",
                backgroundColor: "transparent",
                opacity: 0,
                transition: "opacity 400ms, background-color 400ms",
              }}
            />
            {/* Ripple ring */}
            <div
              ref={(el) => { rippleRefs.current[i] = el; }}
              style={{
                position: "absolute",
                top: "50%",
                left: "50%",
                width: "12px",
                height: "12px",
                marginLeft: "-6px",
                marginTop: "-6px",
                borderRadius: "50%",
                border: "1.5px solid transparent",
                animation: "zone-ripple 2s ease-out infinite",
                display: "none",
              }}
            />
          </div>
        </Html>
      ))}
    </>
  );
}
