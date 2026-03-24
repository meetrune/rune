import { useEffect, useRef } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { getHealthState } from "@/constants/thresholds";
import { SUBSYSTEM_LABELS } from "@/constants/zones";
import type { SubsystemId, HealthScores } from "@/types/vehicle";

const SUBSYSTEMS: SubsystemId[] = [
  "engine",
  "transmission",
  "cooling",
  "fuel",
  "exhaust",
  "electrical",
];

function stateColor(state: string): string {
  if (state === "critical") return "var(--rune-critical)";
  if (state === "warn") return "var(--rune-warn)";
  return "var(--rune-text)";
}

function borderColor(state: string): string {
  if (state === "critical") return "var(--rune-critical)";
  if (state === "warn") return "var(--rune-warn)";
  return "rgba(255,255,255,0.12)";
}

interface RowRefs {
  border: HTMLDivElement | null;
  score: HTMLSpanElement | null;
  bar: HTMLDivElement | null;
}

export function SubsystemList() {
  const rowRefs = useRef<Record<SubsystemId, RowRefs>>(
    Object.fromEntries(SUBSYSTEMS.map((id) => [id, { border: null, score: null, bar: null }])) as Record<SubsystemId, RowRefs>
  );

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const health = state.health;
      for (const id of SUBSYSTEMS) {
        const refs = rowRefs.current[id];
        const score = health[id as keyof HealthScores] as number;
        const display = score < 0 ? "--" : String(Math.round(score));
        const healthState = getHealthState(score);
        const color = stateColor(healthState);

        if (refs.score) {
          refs.score.textContent = display;
          refs.score.style.color = color;
        }

        if (refs.bar) {
          const pct = score < 0 ? 0 : Math.min(100, Math.max(0, score));
          refs.bar.style.width = `${pct}%`;
          refs.bar.style.backgroundColor = color;
        }

        if (refs.border) {
          refs.border.style.borderLeftColor = borderColor(healthState);
        }
      }
    });
    return unsub;
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      {SUBSYSTEMS.map((id) => (
        <div
          key={id}
          ref={(el) => {
            if (el) rowRefs.current[id].border = el;
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "8px 10px",
            borderLeft: "3px solid rgba(255,255,255,0.12)",
            transition: "border-left-color 0.3s",
          }}
        >
          {/* Subsystem name */}
          <span
            style={{
              fontFamily: "var(--font-data)",
              fontSize: "12px",
              color: "var(--rune-text-muted)",
              width: "68px",
              flexShrink: 0,
            }}
          >
            {SUBSYSTEM_LABELS[id]}
          </span>

          {/* Mini progress bar */}
          <div
            style={{
              flex: 1,
              height: "3px",
              borderRadius: "1.5px",
              backgroundColor: "rgba(255,255,255,0.06)",
              overflow: "hidden",
            }}
          >
            <div
              ref={(el) => {
                if (el) rowRefs.current[id].bar = el;
              }}
              style={{
                width: "0%",
                height: "100%",
                borderRadius: "1.5px",
                backgroundColor: "var(--rune-text)",
                transition: "width 0.6s cubic-bezier(0.4,0,0.2,1), background-color 0.3s",
              }}
            />
          </div>

          {/* Score number */}
          <span
            ref={(el) => {
              if (el) rowRefs.current[id].score = el;
            }}
            style={{
              fontFamily: "var(--font-data)",
              fontSize: "14px",
              fontWeight: 500,
              color: "var(--rune-text)",
              width: "28px",
              textAlign: "right",
              flexShrink: 0,
            }}
          >
            --
          </span>
        </div>
      ))}
    </div>
  );
}
