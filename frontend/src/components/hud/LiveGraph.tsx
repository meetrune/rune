import { useRef, useEffect } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";

// Premium SVG live graph. Self-contained: reads store directly, manages own buffer.
// Crisp SVG text on OLED. Dynamic color based on current value.

interface LiveGraphProps {
  label: string;
  unit: string;
  sensorKey: string;
  max: number;
  getColor: (value: number) => string;
}

const BUF_LEN = 200;

export function LiveGraph({ label, unit, sensorKey, max, getColor }: LiveGraphProps) {
  const buffer = useRef<number[]>(new Array(BUF_LEN).fill(0));
  const pathRef = useRef<SVGPathElement>(null);
  const fillRef = useRef<SVGPathElement>(null);
  const dotRef = useRef<SVGCircleElement>(null);
  const glowRef = useRef<SVGCircleElement>(null);
  const colorStopRef = useRef<SVGStopElement>(null);
  const fillStopRef = useRef<SVGStopElement>(null);
  const valTextRef = useRef<HTMLSpanElement>(null);
  const H = 60, W = 900;

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
      let d = "", fd = `M 0 ${H}`;
      for (let i = 0; i < buf.length; i++) {
        const x = (i / (buf.length - 1)) * W;
        const y = H - pad - (Math.min(buf[i]!, max) / max) * (H - pad * 2);
        if (i === 0) { d += `M ${x} ${y}`; fd += ` L ${x} ${y}`; }
        else { d += ` L ${x} ${y}`; fd += ` L ${x} ${y}`; }
      }
      fd += ` L ${W} ${H} Z`;

      pathRef.current.setAttribute("d", d);
      if (fillRef.current) fillRef.current.setAttribute("d", fd);

      const lastVal = buf[buf.length - 1]!;
      const lastX = W - 2;
      const lastY = H - pad - (Math.min(lastVal, max) / max) * (H - pad * 2);
      const color = getColor(lastVal);

      if (dotRef.current) { dotRef.current.setAttribute("cx", String(lastX)); dotRef.current.setAttribute("cy", String(lastY)); dotRef.current.setAttribute("fill", color); }
      if (glowRef.current) { glowRef.current.setAttribute("cx", String(lastX)); glowRef.current.setAttribute("cy", String(lastY)); glowRef.current.setAttribute("fill", color); }
      if (colorStopRef.current) colorStopRef.current.setAttribute("stop-color", color);
      if (fillStopRef.current) fillStopRef.current.setAttribute("stop-color", color);
      if (valTextRef.current) {
        valTextRef.current.textContent = lastVal < 1 && max < 50 ? lastVal.toFixed(1) : String(Math.round(lastVal));
        valTextRef.current.style.color = color;
      }

      af = requestAnimationFrame(render);
    };
    af = requestAnimationFrame(render);

    return () => { unsub(); cancelAnimationFrame(af); };
  }, [sensorKey, max, getColor]);

  const gid = `lg-${sensorKey}`;
  const fid = `lf-${sensorKey}`;

  return (
    <div style={{
      flex: 1, borderRadius: 8, overflow: "hidden",
      border: "1px solid rgba(255,255,255,0.04)",
      background: "rgba(255,255,255,0.015)",
      position: "relative", minHeight: 0,
    }}>
      {/* DOM labels = crisp on OLED */}
      <div style={{
        position: "absolute", top: 3, left: 8, right: 8, zIndex: 2,
        display: "flex", justifyContent: "space-between", alignItems: "center",
        pointerEvents: "none",
      }}>
        <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 9, fontWeight: 600, letterSpacing: "0.08em", color: "rgba(255,255,255,0.2)" }}>{label}</span>
        <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
          <span ref={valTextRef} style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 13, fontWeight: 700, color: "#c9952a", fontVariantNumeric: "tabular-nums", transition: "color 150ms" }}>--</span>
          <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 8, color: "rgba(255,255,255,0.12)" }}>{unit}</span>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: "100%", display: "block" }}>
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(255,255,255,0)" />
            <stop offset="50%" stopColor="rgba(255,255,255,0.2)" />
            <stop ref={colorStopRef} offset="100%" stopColor="#c9952a" />
          </linearGradient>
          <linearGradient id={fid} x1="0" y1="0" x2="0" y2="1">
            <stop ref={fillStopRef} offset="0%" stopColor="#c9952a" stopOpacity="0.12" />
            <stop offset="100%" stopColor="#000" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Grid */}
        {[0.25, 0.5, 0.75].map((p) => (
          <line key={p} x1="0" y1={H * p} x2={W} y2={H * p} stroke="rgba(255,255,255,0.025)" strokeWidth="0.5" />
        ))}

        <path ref={fillRef} d="" fill={`url(#${fid})`} />
        <path ref={pathRef} d="" fill="none" stroke={`url(#${gid})`} strokeWidth="2" strokeLinejoin="round" />
        <circle ref={glowRef} cx="0" cy="0" r="6" fill="#c9952a" opacity="0.12" />
        <circle ref={dotRef} cx="0" cy="0" r="2.5" fill="#c9952a" />
      </svg>
    </div>
  );
}
