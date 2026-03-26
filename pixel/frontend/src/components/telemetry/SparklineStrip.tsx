import { useEffect, useRef } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { getSensorState, getSensorLabel } from "@/constants/thresholds";

const TRACKED_SENSORS = ["RPM", "COOLANT_TEMP", "BATTERY_V"] as const;
const BUFFER_SIZE = 300; // 30 seconds at 10Hz
const SVG_WIDTH = 200;
const SVG_HEIGHT = 40;

function stateStrokeColor(state: string): string {
  if (state === "critical") return "var(--rune-critical)";
  if (state === "warn") return "var(--rune-warn)";
  return "var(--rune-text)";
}

export function SparklineStrip() {
  // One buffer per tracked sensor
  const buffers = useRef<Record<string, number[]>>(
    Object.fromEntries(TRACKED_SENSORS.map((k) => [k, []])) as Record<string, number[]>
  );
  const polylineRefs = useRef<Record<string, SVGPolylineElement | null>>(
    Object.fromEntries(TRACKED_SENSORS.map((k) => [k, null])) as Record<string, SVGPolylineElement | null>
  );
  const labelRefs = useRef<Record<string, HTMLSpanElement | null>>(
    Object.fromEntries(TRACKED_SENSORS.map((k) => [k, null])) as Record<string, HTMLSpanElement | null>
  );

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      for (const key of TRACKED_SENSORS) {
        const reading = state.sensors[key];
        const buf = buffers.current[key];
        if (!buf) continue;

        if (reading) {
          buf.push(reading.v);
          if (buf.length > BUFFER_SIZE) {
            buf.shift();
          }
        }

        const polyline = polylineRefs.current[key];
        const label = labelRefs.current[key];

        if (polyline && buf.length > 1) {
          // Auto-scale Y axis
          let yMin = buf[0]!;
          let yMax = buf[0]!;
          for (let i = 1; i < buf.length; i++) {
            if (buf[i]! < yMin) yMin = buf[i]!;
            if (buf[i]! > yMax) yMax = buf[i]!;
          }
          // Prevent flat line from collapsing
          const yRange = yMax - yMin || 1;
          const padding = yRange * 0.1;
          const adjMin = yMin - padding;
          const adjRange = yRange + padding * 2;

          const xStep = SVG_WIDTH / (BUFFER_SIZE - 1);
          const xOffset = (BUFFER_SIZE - buf.length) * xStep;
          let points = "";
          for (let i = 0; i < buf.length; i++) {
            const x = xOffset + i * xStep;
            const y = SVG_HEIGHT - ((buf[i]! - adjMin) / adjRange) * SVG_HEIGHT;
            points += `${x.toFixed(1)},${y.toFixed(1)} `;
          }
          polyline.setAttribute("points", points.trimEnd());

          // Color based on latest value
          const latestValue = buf[buf.length - 1]!;
          const sensorState = getSensorState(key, latestValue);
          polyline.style.stroke = stateStrokeColor(sensorState);
        }

        if (label && reading) {
          const sensorState = getSensorState(key, reading.v);
          label.style.color = stateStrokeColor(sensorState);
        }
      }
    });
    return unsub;
  }, []);

  return (
    <div
      style={{
        display: "flex",
        gap: "12px",
      }}
    >
      {TRACKED_SENSORS.map((key) => (
        <div key={key} style={{ flex: 1, minWidth: 0 }}>
          <svg
            width="100%"
            height={SVG_HEIGHT}
            viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
            preserveAspectRatio="none"
            style={{ display: "block" }}
          >
            <polyline
              ref={(el) => {
                polylineRefs.current[key] = el;
              }}
              fill="none"
              stroke="var(--rune-text)"
              strokeWidth="1.5"
              strokeLinejoin="round"
              strokeLinecap="round"
              style={{ transition: "stroke 0.3s" }}
            />
          </svg>
          <span
            ref={(el) => {
              labelRefs.current[key] = el;
            }}
            style={{
              fontFamily: "var(--font-data)",
              fontSize: "9px",
              color: "var(--rune-label)",
              letterSpacing: "0.06em",
              marginTop: "3px",
              display: "block",
            }}
          >
            {getSensorLabel(key)}
          </span>
        </div>
      ))}
    </div>
  );
}
