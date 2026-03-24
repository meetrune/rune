import { useRef, useEffect } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";

// Trace cell with three premium features:
// 1. Zero-line for sensors that oscillate around a baseline (fuel trims)
// 2. Trend arrow (up/down/stable) next to the value
// 3. Dot glow pulse when severity changes (preattentive attention grab)

interface LiveGraphProps {
  label: string;
  unit: string;
  sensorKey: string;
  min?: number;
  max: number;
  getColor: (value: number) => string;
  labelColor?: string;
  zeroLine?: number; // draw a dim reference line at this value (e.g., 0 for fuel trims)
}

const BUF_LEN = 200;

export function LiveGraph({ label, unit, sensorKey, min = 0, max, getColor, labelColor, zeroLine }: LiveGraphProps) {
  const buffer = useRef<number[]>(new Array(BUF_LEN).fill(0));
  const pathRef = useRef<SVGPathElement>(null);
  const fillRef = useRef<SVGPathElement>(null);
  const dotRef = useRef<SVGCircleElement>(null);
  const glowRef = useRef<SVGCircleElement>(null);
  const valTextRef = useRef<HTMLSpanElement>(null);
  const trendRef = useRef<HTMLSpanElement>(null);
  const prevColor = useRef<string>("");
  const glowTimeout = useRef<number>(0);
  const H = 60, W = 900;

  // Compute zero-line Y position in SVG coords
  const zeroY = zeroLine !== undefined
    ? H - 2 - ((Math.min(Math.max(zeroLine, min), max) - min) / (max - min)) * (H - 4)
    : undefined;

  useEffect(() => {
    let af = 0;

    const unsub = useVehicleStore.subscribe((state) => {
      const v = state.sensors[sensorKey]?.v ?? 0;
      buffer.current.push(v);
      if (buffer.current.length > BUF_LEN) buffer.current.shift();
    });

    const render = () => {
      const buf = buffer.current;
      if (buf.length < 2 || !pathRef.current) { af = requestAnimationFrame(render); return; }

      const pad = 2;
      const range = max - min;
      let d = "", fd = `M 0 ${H}`;
      for (let i = 0; i < buf.length; i++) {
        const x = (i / (buf.length - 1)) * W;
        const normalized = range > 0 ? (Math.min(Math.max(buf[i]!, min), max) - min) / range : 0;
        const y = H - pad - normalized * (H - pad * 2);
        if (i === 0) { d += `M ${x} ${y}`; fd += ` L ${x} ${y}`; }
        else { d += ` L ${x} ${y}`; fd += ` L ${x} ${y}`; }
      }
      fd += ` L ${W} ${H} Z`;

      const lastVal = buf[buf.length - 1]!;
      const lastNorm = range > 0 ? (Math.min(Math.max(lastVal, min), max) - min) / range : 0;
      const lastX = W - 2;
      const lastY = H - pad - lastNorm * (H - pad * 2);
      const color = getColor(lastVal);

      // Trace line + fill
      pathRef.current.setAttribute("d", d);
      pathRef.current.setAttribute("stroke", color);
      if (fillRef.current) {
        fillRef.current.setAttribute("d", fd);
        fillRef.current.setAttribute("fill", color);
        fillRef.current.setAttribute("fill-opacity", "0.03");
      }

      // Dot
      if (dotRef.current) {
        dotRef.current.setAttribute("cx", String(lastX));
        dotRef.current.setAttribute("cy", String(lastY));
        dotRef.current.setAttribute("fill", color);
      }

      // Glow pulse on severity change
      if (glowRef.current) {
        glowRef.current.setAttribute("cx", String(lastX));
        glowRef.current.setAttribute("cy", String(lastY));
        if (color !== prevColor.current && prevColor.current !== "") {
          // Color changed -- flash the glow
          glowRef.current.setAttribute("r", "12");
          glowRef.current.setAttribute("opacity", "0.4");
          glowRef.current.setAttribute("fill", color);
          clearTimeout(glowTimeout.current);
          glowTimeout.current = window.setTimeout(() => {
            if (glowRef.current) {
              glowRef.current.setAttribute("r", "6");
              glowRef.current.setAttribute("opacity", "0.08");
            }
          }, 600);
        }
        prevColor.current = color;
      }

      // Value text
      if (valTextRef.current) {
        valTextRef.current.textContent = lastVal < 1 && max < 50 ? lastVal.toFixed(1) : String(Math.round(lastVal));
        valTextRef.current.style.color = color;
      }

      // Trend arrow -- compare last value to value ~3 seconds ago (30 samples at 10Hz)
      if (trendRef.current && buf.length > 30) {
        const prev = buf[buf.length - 31]!;
        const delta = lastVal - prev;
        const threshold = range * 0.02; // 2% of range = meaningful change
        let arrow: string, arrowColor: string;
        if (delta > threshold) { arrow = "\u25B2"; arrowColor = color; }       // up triangle
        else if (delta < -threshold) { arrow = "\u25BC"; arrowColor = color; }  // down triangle
        else { arrow = "\u2014"; arrowColor = "rgba(255,255,255,0.1)"; }        // em dash = stable
        trendRef.current.textContent = arrow;
        trendRef.current.style.color = arrowColor;
      }

      af = requestAnimationFrame(render);
    };
    af = requestAnimationFrame(render);

    return () => { unsub(); cancelAnimationFrame(af); clearTimeout(glowTimeout.current); };
  }, [sensorKey, min, max, getColor]);

  return (
    <div style={{
      flex: 1, borderRadius: 6, overflow: "hidden",
      border: "1px solid rgba(255,255,255,0.03)",
      background: "rgba(255,255,255,0.012)",
      position: "relative", minHeight: 0,
    }}>
      {/* Labels */}
      <div style={{
        position: "absolute", top: 2, left: 8, right: 8, zIndex: 2,
        display: "flex", justifyContent: "space-between", alignItems: "center",
        pointerEvents: "none",
      }}>
        <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 14, fontWeight: 600, letterSpacing: "0.04em", color: labelColor ?? "rgba(255,255,255,0.25)" }}>{label}</span>
        <div style={{ display: "flex", alignItems: "baseline", gap: 3 }}>
          <span ref={trendRef} style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, color: "rgba(255,255,255,0.1)", transition: "color 300ms" }}>{"\u2014"}</span>
          <span ref={valTextRef} style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums" as const, transition: "color 150ms" }}>--</span>
          <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: "rgba(255,255,255,0.15)" }}>{unit}</span>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: "100%", display: "block" }}>
        {/* Subtle midline */}
        <line x1="0" y1={H * 0.5} x2={W} y2={H * 0.5} stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />

        {/* Zero reference line -- for sensors that oscillate around a baseline */}
        {zeroY !== undefined && (
          <line x1="0" y1={zeroY} x2={W} y2={zeroY} stroke="rgba(255,255,255,0.06)" strokeWidth="0.5" strokeDasharray="4 4" />
        )}

        {/* Subtle fill under the line */}
        <path ref={fillRef} d="" fill="rgba(255,255,255,0.03)" />

        {/* The trace -- thin, clean, colored */}
        <path ref={pathRef} d="" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" strokeLinejoin="round" />

        {/* Glow behind dot -- pulses on severity change */}
        <circle ref={glowRef} cx="0" cy="0" r="6" fill="#888" opacity="0.08" style={{ transition: "r 400ms ease-out, opacity 400ms ease-out" }} />

        {/* Dot at the tip */}
        <circle ref={dotRef} cx="0" cy="0" r="2.5" fill="#888" />
      </svg>
    </div>
  );
}
