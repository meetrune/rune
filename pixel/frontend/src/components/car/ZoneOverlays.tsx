import { useRef, useEffect } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { useUiStore } from "@/stores/uiStore";
import { SUBSYSTEM_LABELS } from "@/constants/zones";
import type { SubsystemId } from "@/types/vehicle";

interface ZoneOverlaysProps {
  view: string;
  viewBox: string;
}

// Zone label positions as percentages of the car image container.
// Mapped to where each subsystem physically sits on the 3/4 view render.
const ZONE_POSITIONS: { id: SubsystemId; top: string; left: string }[] = [
  { id: "engine", top: "32%", left: "38%" },
  { id: "transmission", top: "44%", left: "26%" },
  { id: "cooling", top: "20%", left: "32%" },
  { id: "fuel", top: "68%", left: "52%" },
  { id: "exhaust", top: "60%", left: "36%" },
  { id: "electrical", top: "38%", left: "18%" },
];

const STATE_COLORS = {
  normal: "rgba(255,255,255,0.12)",
  warn: "rgba(251,191,36,0.7)",
  critical: "rgba(239,68,68,0.8)",
};

function getState(score: number): "normal" | "warn" | "critical" {
  if (score === -1) return "normal";
  if (score < 50) return "critical";
  if (score < 70) return "warn";
  return "normal";
}

export function ZoneOverlays(_props: ZoneOverlaysProps) {
  const labelRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const setFocusedSubsystem = useUiStore((s) => s.setFocusedSubsystem);

  // Imperative health score updates
  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      ZONE_POSITIONS.forEach((zone, i) => {
        const el = labelRefs.current[i];
        if (!el) return;

        const score = state.health[zone.id];
        const display = score === -1 ? "--" : String(Math.round(score));
        const st = getState(score);

        el.textContent = `${SUBSYSTEM_LABELS[zone.id]} ${display}`;
        el.style.color = STATE_COLORS[st];
      });
    });
    return unsub;
  }, []);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
      }}
    >
      {ZONE_POSITIONS.map((zone, i) => (
        <span
          key={zone.id}
          ref={(el) => { labelRefs.current[i] = el; }}
          onClick={() => setFocusedSubsystem(zone.id)}
          style={{
            position: "absolute",
            top: zone.top,
            left: zone.left,
            fontFamily: "var(--font-data)",
            fontSize: "11px",
            fontWeight: 500,
            letterSpacing: "0.04em",
            color: "rgba(255,255,255,0.12)",
            pointerEvents: "auto",
            cursor: "pointer",
            padding: "4px 6px",
            borderRadius: "2px",
            transition: "color 400ms",
            whiteSpace: "nowrap",
            userSelect: "none",
            WebkitTapHighlightColor: "transparent",
          }}
        >
          {SUBSYSTEM_LABELS[zone.id]} --
        </span>
      ))}
    </div>
  );
}
