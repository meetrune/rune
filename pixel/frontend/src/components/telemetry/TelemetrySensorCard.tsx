import { useRef, useEffect } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { getSensorState, getSensorLabel, getSensorUnit } from "@/constants/thresholds";

// 5-minute sparkline sensor card for the Telemetry deep-dive panel.
// Circular Float32Array buffer (O(1) push, no GC pressure).
// Imperative SVG + DOM updates via rAF -- zero React re-renders in hot path.

const BUFFER_SIZE = 3000; // 5 minutes at 10Hz
const SVG_W = 200;
const SVG_H = 32;

// Minimum Y-axis ranges per sensor type to prevent jitter on steady signals
const MIN_RANGES: Record<string, number> = {
  BATTERY_V: 0.5, COOLANT_TEMP: 5, OIL_TEMP: 5, CATALYST_TEMP: 20,
  CVT_TEMP: 5, INTAKE_TEMP: 3, RPM: 100, SPEED: 5, ENGINE_LOAD: 5,
  THROTTLE_POS: 5, MAF: 1, FUEL_LEVEL: 2, STFT: 2, LTFT: 1, MAP: 5,
};

function stateColor(state: "normal" | "warn" | "critical"): string {
  if (state === "critical") return "#ef4444";
  if (state === "warn") return "#f59e0b";
  return "rgba(255,255,255,0.7)";
}

interface TelemetrySensorCardProps {
  sensorKey: string;
}

export function TelemetrySensorCard({ sensorKey }: TelemetrySensorCardProps) {
  const buffer = useRef(new Float32Array(BUFFER_SIZE));
  const writeIdx = useRef(0);
  const count = useRef(0);
  const polyRef = useRef<SVGPolylineElement>(null);
  const valRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    let af = 0;

    const unsub = useVehicleStore.subscribe((state) => {
      const v = state.sensors[sensorKey]?.v;
      if (v !== undefined) {
        buffer.current[writeIdx.current % BUFFER_SIZE] = v;
        writeIdx.current++;
        count.current = Math.min(count.current + 1, BUFFER_SIZE);
      }
    });

    const render = () => {
      const n = count.current;
      if (n < 2 || !polyRef.current) { af = requestAnimationFrame(render); return; }

      // Read circular buffer in order
      const start = writeIdx.current - n;
      let yMin = Infinity, yMax = -Infinity;
      for (let i = 0; i < n; i++) {
        const v = buffer.current[(start + i + BUFFER_SIZE) % BUFFER_SIZE]!;
        if (v < yMin) yMin = v;
        if (v > yMax) yMax = v;
      }

      // Apply minimum range to prevent jitter
      const minRange = MIN_RANGES[sensorKey] ?? 1;
      if (yMax - yMin < minRange) {
        const mid = (yMax + yMin) / 2;
        yMin = mid - minRange / 2;
        yMax = mid + minRange / 2;
      }
      const yRange = yMax - yMin;

      // Build polyline points
      let pts = "";
      for (let i = 0; i < n; i++) {
        const v = buffer.current[(start + i + BUFFER_SIZE) % BUFFER_SIZE]!;
        const x = (i / (n - 1)) * SVG_W;
        const y = SVG_H - 1 - ((v - yMin) / yRange) * (SVG_H - 2);
        pts += `${x},${y} `;
      }
      polyRef.current.setAttribute("points", pts);

      // Current value + color
      const lastVal = buffer.current[(writeIdx.current - 1 + BUFFER_SIZE) % BUFFER_SIZE]!;
      const state = getSensorState(sensorKey, lastVal);
      const color = stateColor(state);
      polyRef.current.setAttribute("stroke", color);

      if (valRef.current) {
        valRef.current.textContent = Math.abs(lastVal) < 1 && !["STFT", "LTFT"].includes(sensorKey)
          ? lastVal.toFixed(2) : lastVal < 10 && ["STFT", "LTFT", "MAF", "BATTERY_V"].includes(sensorKey)
          ? lastVal.toFixed(1) : String(Math.round(lastVal));
        valRef.current.style.color = color;
      }
      af = requestAnimationFrame(render);
    };
    af = requestAnimationFrame(render);

    return () => { unsub(); cancelAnimationFrame(af); };
  }, [sensorKey]);

  const label = getSensorLabel(sensorKey);
  const unit = getSensorUnit(sensorKey);

  return (
    <div style={{
      padding: "8px 12px 6px", borderRadius: 10,
      background: "rgba(255,255,255,0.02)",
      border: "1px solid rgba(255,255,255,0.04)",
      display: "flex", flexDirection: "column", gap: 2,
    }}>
      {/* Label + value row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{
          fontFamily: "var(--font-ui)", fontSize: 13, fontWeight: 500,
          color: "rgba(255,255,255,0.3)",
        }}>
          {label} <span style={{ opacity: 0.5 }}>{unit}</span>
        </span>
        <span ref={valRef} style={{
          fontFamily: "var(--font-data)", fontSize: 22, fontWeight: 600,
          color: "rgba(255,255,255,0.9)", lineHeight: 1,
          fontVariantNumeric: "tabular-nums", transition: "color 300ms",
        }}>--</span>
      </div>
      {/* Sparkline */}
      <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} preserveAspectRatio="none"
        style={{ width: "100%", height: 32, display: "block" }}>
        <polyline ref={polyRef} points="" fill="none"
          stroke="rgba(255,255,255,0.3)" strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
    </div>
  );
}
