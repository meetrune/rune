import { useRef, useEffect, useCallback, useState } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { useUiStore } from "@/stores/uiStore";
import {
  ZONE_CONFIGS,
  SUBSYSTEM_LABELS,
} from "@/constants/zones";
import { getHealthState } from "@/constants/thresholds";
import type { SubsystemId } from "@/types/vehicle";
import type { ZoneConfig } from "@/types/zones";
import type { HealthScores } from "@/types/vehicle";
import type { SensorState } from "@/constants/thresholds";

interface ZoneOverlaysProps {
  view: "topDown" | "sideProfile";
  viewBox: string;
}

interface RippleState {
  x: number;
  y: number;
  key: number;
}

// Border glow colours per state
const GLOW_COLOR: Record<SensorState, string> = {
  normal: "transparent",
  warn: "var(--rune-warn)",
  critical: "var(--rune-critical)",
};

const LABEL_OPACITY: Record<SensorState, number> = {
  normal: 0.12,
  warn: 0.5,
  critical: 0.7,
};

let rippleCounter = 0;

// Helper to get the zone position for the current view and compute center/size in viewBox coords
function getZoneRect(zone: ZoneConfig, view: "topDown" | "sideProfile", viewBox: string) {
  const pos = zone[view];
  const parts = viewBox.split(" ").map(Number);
  const vbW = parts[2] ?? 400;
  const vbH = parts[3] ?? 180;
  const x = (pos.x / 100) * vbW;
  const y = (pos.y / 100) * vbH;
  const w = (pos.width / 100) * vbW;
  const h = (pos.height / 100) * vbH;
  const cx = (pos.labelX / 100) * vbW;
  const cy = (pos.labelY / 100) * vbH;
  return { x, y, w, h, cx, cy };
}

export function ZoneOverlays({
  view,
  viewBox,
}: ZoneOverlaysProps): React.JSX.Element {
  const labelsRef = useRef<Map<SubsystemId, SVGTextElement>>(new Map());
  const rectsRef = useRef<Map<SubsystemId, SVGRectElement>>(new Map());
  const [ripples, setRipples] = useState<RippleState[]>([]);

  const focusedSubsystem = useUiStore((s) => s.focusedSubsystem);
  const setFocusedSubsystem = useUiStore((s) => s.setFocusedSubsystem);

  // Imperatively subscribe to health scores for label/glow updates
  useEffect(() => {
    const unsubscribe = useVehicleStore.subscribe((state) => {
      updateZoneVisuals(state.health);
    });

    // Initial render with current state
    updateZoneVisuals(useVehicleStore.getState().health);

    return unsubscribe;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  function updateZoneVisuals(health: HealthScores): void {
    for (const zone of ZONE_CONFIGS) {
      const score = health[zone.subsystem as keyof HealthScores];
      if (typeof score !== "number") continue;

      const state = getHealthState(score);
      const label = labelsRef.current.get(zone.subsystem);
      const rect = rectsRef.current.get(zone.subsystem);

      if (label) {
        const displayScore = score < 0 ? "--" : String(Math.round(score));
        label.textContent = `${SUBSYSTEM_LABELS[zone.subsystem]} ${displayScore}`;
        label.style.opacity = String(LABEL_OPACITY[state]);
      }

      if (rect) {
        const glowColor = GLOW_COLOR[state];
        if (glowColor === "transparent") {
          rect.style.stroke = "transparent";
          rect.style.filter = "none";
        } else {
          rect.style.stroke = glowColor;
          rect.style.filter = `drop-shadow(0 0 4px ${glowColor})`;
        }
      }
    }
  }

  // Update focused zone brightness
  useEffect(() => {
    for (const zone of ZONE_CONFIGS) {
      const label = labelsRef.current.get(zone.subsystem);
      if (!label) continue;

      const health = useVehicleStore.getState().health;
      const score = health[zone.subsystem as keyof HealthScores];
      const state: SensorState = typeof score === "number" ? getHealthState(score) : "normal";
      const baseOpacity = LABEL_OPACITY[state];

      label.style.opacity = String(
        focusedSubsystem === zone.subsystem
          ? Math.min(1, baseOpacity + 0.25)
          : baseOpacity
      );
    }
  }, [focusedSubsystem]);

  const handleZoneTap = useCallback(
    (subsystem: SubsystemId, cx: number, cy: number) => {
      setFocusedSubsystem(subsystem);
      // Trigger ripple at tap location
      const key = ++rippleCounter;
      setRipples((prev) => [...prev, { x: cx, y: cy, key }]);
      // Clean up ripple after animation
      setTimeout(() => {
        setRipples((prev) => prev.filter((r) => r.key !== key));
      }, 800);
    },
    [setFocusedSubsystem],
  );

  const handleBackgroundTap = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      // Only clear if the tap was directly on the SVG background
      if (e.target === e.currentTarget) {
        setFocusedSubsystem(null);
      }
    },
    [setFocusedSubsystem],
  );

  return (
    <svg
      viewBox={viewBox}
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
      }}
      fill="none"
      onPointerDown={handleBackgroundTap}
    >
      {/* Ripple animation definition */}
      <defs>
        <style>{`
          @keyframes zone-ripple {
            0% {
              r: 4;
              opacity: 0.3;
              stroke-width: 1.5;
            }
            100% {
              r: 30;
              opacity: 0;
              stroke-width: 0.3;
            }
          }
          .zone-ripple-ring {
            animation: zone-ripple 0.8s ease-out forwards;
          }
        `}</style>
      </defs>

      {/* Zone overlay rectangles */}
      {ZONE_CONFIGS.map((zone) => {
        const r = getZoneRect(zone, view, viewBox);
        return (
          <g key={zone.subsystem}>
            {/* Invisible tap target (meets 56x56 min touch, scaled by viewBox) */}
            <rect
              ref={(el) => {
                if (el) rectsRef.current.set(zone.subsystem, el);
              }}
              x={r.x}
              y={r.y}
              width={r.w}
              height={r.h}
              rx={4}
              ry={4}
              fill="transparent"
              stroke="transparent"
              strokeWidth={1}
              style={{ cursor: "pointer" }}
              onPointerDown={(e) => {
                e.stopPropagation();
                handleZoneTap(zone.subsystem, r.cx, r.cy);
              }}
            />
            {/* Label: "ENG 94" */}
            <text
              ref={(el) => {
                if (el) labelsRef.current.set(zone.subsystem, el);
              }}
              x={r.cx}
              y={r.cy}
              textAnchor="middle"
              dominantBaseline="central"
              fill="white"
              fontSize={view === "topDown" ? 8 : 9}
              fontFamily="var(--font-data)"
              fontWeight={500}
              style={{
                opacity: 0.12,
                pointerEvents: "none",
                userSelect: "none",
              }}
            >
              {`${SUBSYSTEM_LABELS[zone.subsystem]} --`}
            </text>
          </g>
        );
      })}

      {/* Sonar ripple rings on tap */}
      {ripples.map((ripple) => (
        <g key={ripple.key}>
          <circle
            className="zone-ripple-ring"
            cx={ripple.x}
            cy={ripple.y}
            r={4}
            fill="none"
            stroke="white"
          />
          <circle
            className="zone-ripple-ring"
            cx={ripple.x}
            cy={ripple.y}
            r={4}
            fill="none"
            stroke="white"
            style={{ animationDelay: "0.15s" }}
          />
        </g>
      ))}
    </svg>
  );
}
