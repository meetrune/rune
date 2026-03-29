import { useRef, useEffect } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";

/**
 * CSS-animated dots flowing from the fuel tank zone to the engine zone.
 * Speed is driven by MAF sensor value (proxy for fuel consumption rate).
 * When MAF is 0 or unavailable, particles fade out.
 *
 * Rendered as an absolutely-positioned SVG overlay that matches the parent
 * car SVG's viewBox. The parent CarView passes the correct viewBox string
 * and the start/end coordinates for the current view mode.
 */

interface FuelParticlesProps {
  viewBox: string;
  /** Fuel tank position (start of flow) */
  startX: number;
  startY: number;
  /** Engine position (end of flow) */
  endX: number;
  endY: number;
}

const PARTICLE_COUNT = 4;

// Unique keyframes ID per mount to avoid collisions
let mountCounter = 0;

export function FuelParticles({
  viewBox,
  startX,
  startY,
  endX,
  endY,
}: FuelParticlesProps): React.JSX.Element {
  const durationRef = useRef(3);
  const activeRef = useRef(false);
  const containerRef = useRef<SVGSVGElement>(null);
  const styleRef = useRef<HTMLStyleElement | null>(null);
  const idRef = useRef(++mountCounter);

  const animName = `fuel-flow-${idRef.current}`;

  // Inject keyframes stylesheet once on mount
  useEffect(() => {
    const style = document.createElement("style");
    style.textContent = `
      @keyframes ${animName} {
        0% {
          cx: ${startX};
          cy: ${startY};
          opacity: 0;
        }
        10% {
          opacity: 0.2;
        }
        90% {
          opacity: 0.2;
        }
        100% {
          cx: ${endX};
          cy: ${endY};
          opacity: 0;
        }
      }
    `;
    document.head.appendChild(style);
    styleRef.current = style;

    return () => {
      if (styleRef.current) {
        document.head.removeChild(styleRef.current);
      }
    };
  }, [animName, startX, startY, endX, endY]);

  // Imperatively subscribe to MAF for animation speed updates.
  // MAF is in grams/sec. Typical idle ~3-5 g/s, highway ~15-30 g/s.
  // Map to animation duration: high MAF = fast particles, low MAF = slow.
  useEffect(() => {
    const unsubscribe = useVehicleStore.subscribe((state) => {
      const maf = state.sensors["MAF"]?.v ?? 0;
      const isActive = maf > 0.5;

      // Map MAF to duration: 30 g/s -> 0.8s, 3 g/s -> 4s. Clamped.
      const newDuration = isActive
        ? Math.max(0.8, Math.min(4, 4 - (maf / 30) * 3.2))
        : 3;

      durationRef.current = newDuration;
      activeRef.current = isActive;

      const svg = containerRef.current;
      if (!svg) return;

      const circles = svg.querySelectorAll<SVGCircleElement>(".fuel-dot");
      circles.forEach((circle, i) => {
        circle.style.animationDuration = `${newDuration}s`;
        circle.style.opacity = isActive ? "1" : "0";
        // Stagger each particle evenly across the cycle
        circle.style.animationDelay = `${-(newDuration / PARTICLE_COUNT) * i}s`;
      });
    });

    return unsubscribe;
  }, []);

  return (
    <svg
      ref={containerRef}
      viewBox={viewBox}
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
      fill="none"
    >
      {Array.from({ length: PARTICLE_COUNT }).map((_, i) => (
        <circle
          key={i}
          className="fuel-dot"
          cx={startX}
          cy={startY}
          r={1.5}
          fill="rgba(255,255,255,0.20)"
          style={{
            animation: `${animName} 3s linear infinite`,
            animationDelay: `${-(3 / PARTICLE_COUNT) * i}s`,
            opacity: 0,
          }}
        />
      ))}
    </svg>
  );
}
