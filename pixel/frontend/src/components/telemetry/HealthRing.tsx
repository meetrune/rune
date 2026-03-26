import { useEffect, useRef } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { getHealthState } from "@/constants/thresholds";

const SIZE = 120;
const STROKE = 6;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
// 270 degrees = 3/4 of a full circle
const ARC_LENGTH = CIRCUMFERENCE * 0.75;

function stateColor(state: string): string {
  if (state === "critical") return "var(--rune-critical)";
  if (state === "warn") return "var(--rune-warn)";
  return "var(--rune-text)";
}

export function HealthRing() {
  const valueRef = useRef<HTMLSpanElement>(null);
  const arcRef = useRef<SVGCircleElement>(null);
  const labelRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const score = state.health.overall;
      const display = score < 0 ? "--" : String(Math.round(score));
      const healthState = getHealthState(score);
      const color = stateColor(healthState);

      if (valueRef.current) {
        valueRef.current.textContent = display;
        valueRef.current.style.color = color;
      }

      if (labelRef.current) {
        labelRef.current.style.color =
          healthState === "normal" ? "var(--rune-text-muted)" : color;
      }

      if (arcRef.current) {
        const pct = score < 0 ? 0 : Math.min(1, Math.max(0, score / 100));
        const offset = ARC_LENGTH * (1 - pct);
        arcRef.current.style.strokeDashoffset = String(offset);
        arcRef.current.style.stroke = color;
      }
    });
    return unsub;
  }, []);

  return (
    <div
      style={{
        position: "relative",
        width: SIZE,
        height: SIZE,
        flexShrink: 0,
      }}
    >
      <svg
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        style={{ transform: "rotate(135deg)" }}
      >
        {/* Background arc */}
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={STROKE}
          strokeDasharray={`${ARC_LENGTH} ${CIRCUMFERENCE}`}
          strokeLinecap="round"
        />
        {/* Value arc */}
        <circle
          ref={arcRef}
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="var(--rune-text)"
          strokeWidth={STROKE}
          strokeDasharray={`${ARC_LENGTH} ${CIRCUMFERENCE}`}
          strokeDashoffset={String(ARC_LENGTH)}
          strokeLinecap="round"
          style={{
            transition: "stroke-dashoffset 0.6s cubic-bezier(0.4,0,0.2,1), stroke 0.3s",
          }}
        />
      </svg>

      {/* Centered score */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span
          ref={valueRef}
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "32px",
            fontWeight: 600,
            color: "var(--rune-text)",
            lineHeight: 1,
          }}
        >
          --
        </span>
        <span
          ref={labelRef}
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "10px",
            letterSpacing: "0.12em",
            color: "var(--rune-text-muted)",
            textTransform: "uppercase",
            marginTop: "4px",
          }}
        >
          Health
        </span>
      </div>
    </div>
  );
}
