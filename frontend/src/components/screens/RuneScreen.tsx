import { useRef, useEffect, useState } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { useRuneVoice } from "@/hooks/useRuneVoice";

export function RuneScreen() {
  const healthRef = useRef<HTMLSpanElement>(null);
  const speedRef = useRef<HTMLSpanElement>(null);
  const rpmRef = useRef<HTMLSpanElement>(null);
  const mpgRef = useRef<HTMLSpanElement>(null);
  const mpgLabelRef = useRef<HTMLSpanElement>(null);
  const costRef = useRef<HTMLSpanElement>(null);
  const distRef = useRef<HTMLSpanElement>(null);
  const stateRef = useRef<HTMLSpanElement>(null);
  const waveCanvasRef = useRef<HTMLCanvasElement>(null);
  const waveBuffer = useRef<number[]>(new Array(200).fill(0));

  const voice = useRuneVoice();
  const [displayVoice, setDisplayVoice] = useState("");
  const [voiceOpacity, setVoiceOpacity] = useState(0);
  const prevVoice = useRef("");

  // Smooth voice transition
  useEffect(() => {
    if (!voice.message || voice.message === prevVoice.current) return;
    prevVoice.current = voice.message;
    setVoiceOpacity(0);
    const t = setTimeout(() => { setDisplayVoice(voice.message); setVoiceOpacity(1); }, 400);
    return () => clearTimeout(t);
  }, [voice.message]);

  useEffect(() => {
    if (voice.message && !displayVoice) {
      setDisplayVoice(voice.message);
      setTimeout(() => setVoiceOpacity(1), 200);
    }
  }, [voice.message, displayVoice]);

  // 10Hz imperative updates + heartbeat waveform
  useEffect(() => {
    let prevThrottle = 0;
    let prevSpeed = 0;
    let animFrame = 0;

    const unsub = useVehicleStore.subscribe((state) => {
      const h = state.health.overall;
      if (healthRef.current) {
        healthRef.current.textContent = h === -1 ? "--" : String(Math.round(h));
        healthRef.current.style.color =
          h < 50 ? "#c53030" : h < 70 ? "#d4a017" : "rgba(255,255,255,0.95)";
      }

      const speed = state.sensors["SPEED"]?.v ?? 0;
      const rpm = state.sensors["RPM"]?.v ?? 0;
      const throttle = state.sensors["THROTTLE_POS"]?.v ?? 0;

      if (speedRef.current) speedRef.current.textContent = String(Math.round(speed));
      if (rpmRef.current) rpmRef.current.textContent = Math.round(rpm).toLocaleString();

      if (mpgRef.current && mpgLabelRef.current) {
        if (speed > 2) {
          const mpg = state.fuel.instant_mpg;
          mpgRef.current.textContent = mpg != null ? mpg.toFixed(1) : "--";
          mpgLabelRef.current.textContent = "MPG";
        } else {
          const gph = state.fuel.idle_gph;
          mpgRef.current.textContent = gph != null ? gph.toFixed(2) : "--";
          mpgLabelRef.current.textContent = "GPH idle";
        }
      }

      if (costRef.current) costRef.current.textContent = `$${state.fuel.trip_cost_usd.toFixed(2)}`;
      if (distRef.current) distRef.current.textContent = `${state.fuel.trip_distance_mi.toFixed(1)} mi`;

      // Driving state
      if (stateRef.current) {
        if (speed < 2) stateRef.current.textContent = "Idle";
        else if (throttle > 60) stateRef.current.textContent = "Accelerating";
        else if (speed > 80) stateRef.current.textContent = "Highway";
        else stateRef.current.textContent = "Cruising";
      }

      // Push to heartbeat waveform buffer
      const intensity = Math.abs(throttle - prevThrottle) + Math.abs(speed - prevSpeed) * 0.3;
      prevThrottle = throttle;
      prevSpeed = speed;
      waveBuffer.current.push(Math.min(intensity, 40));
      if (waveBuffer.current.length > 200) waveBuffer.current.shift();
    });

    // Draw waveform at 30fps
    const draw = () => {
      const canvas = waveCanvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext("2d");
        if (ctx) {
          const w = canvas.width;
          const h = canvas.height;
          ctx.clearRect(0, 0, w, h);

          const buf = waveBuffer.current;
          const len = buf.length;
          if (len < 2) { animFrame = requestAnimationFrame(draw); return; }

          // Gradient stroke
          const grad = ctx.createLinearGradient(0, 0, w, 0);
          grad.addColorStop(0, "rgba(234,179,8,0)");
          grad.addColorStop(0.3, "rgba(234,179,8,0.25)");
          grad.addColorStop(1, "rgba(234,179,8,0.6)");

          ctx.beginPath();
          ctx.strokeStyle = grad;
          ctx.lineWidth = 1.5;
          ctx.lineJoin = "round";

          for (let i = 0; i < len; i++) {
            const x = (i / (len - 1)) * w;
            const y = h / 2 - (buf[i]! / 40) * (h * 0.4);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.stroke();

          // Subtle glow line on top
          ctx.beginPath();
          ctx.strokeStyle = "rgba(234,179,8,0.08)";
          ctx.lineWidth = 6;
          for (let i = 0; i < len; i++) {
            const x = (i / (len - 1)) * w;
            const y = h / 2 - (buf[i]! / 40) * (h * 0.4);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.stroke();
        }
      }
      animFrame = requestAnimationFrame(draw);
    };
    animFrame = requestAnimationFrame(draw);

    return () => { unsub(); cancelAnimationFrame(animFrame); };
  }, []);

  return (
    <div style={S.screen}>
      {/* Top bar: health + driving state */}
      <div style={S.topBar}>
        <div style={S.healthBlock}>
          <span ref={healthRef} style={S.healthNum}>--</span>
          <div style={S.healthMeta}>
            <span style={S.healthLabel}>HEALTH</span>
            <span ref={stateRef} style={S.stateLabel}>Idle</span>
          </div>
        </div>
        <div style={S.topRight}>
          <div style={S.statBox}>
            <span ref={mpgRef} style={S.statNum}>--</span>
            <span ref={mpgLabelRef} style={S.statLabel}>MPG</span>
          </div>
        </div>
      </div>

      {/* Center: Rune's voice -- the hero */}
      <div style={S.voiceSection}>
        <div style={S.voiceTag}>
          <div style={S.voiceDot} />
          <span style={S.voiceTagText}>RUNE</span>
        </div>
        <p style={{
          ...S.voiceMessage,
          opacity: voiceOpacity,
          transform: voiceOpacity ? "translateY(0)" : "translateY(6px)",
          transition: "opacity 600ms ease, transform 600ms ease",
        }}>
          {displayVoice || "Listening..."}
        </p>
      </div>

      {/* Bottom: Trip heartbeat + live stats */}
      <div style={S.bottomSection}>
        {/* Trip stats row */}
        <div style={S.tripRow}>
          <div style={S.tripStat}>
            <span ref={speedRef} style={S.tripNum}>0</span>
            <span style={S.tripUnit}>KPH</span>
          </div>
          <div style={S.tripStat}>
            <span ref={rpmRef} style={S.tripNum}>--</span>
            <span style={S.tripUnit}>RPM</span>
          </div>
          <div style={S.tripStat}>
            <span ref={costRef} style={S.tripNum}>$0.00</span>
            <span style={S.tripUnit}>TRIP COST</span>
          </div>
          <div style={S.tripStat}>
            <span ref={distRef} style={S.tripNum}>0.0 mi</span>
            <span style={S.tripUnit}>DISTANCE</span>
          </div>
        </div>

        {/* Heartbeat waveform */}
        <div style={S.waveWrap}>
          <span style={S.waveLabel}>HEARTBEAT</span>
          <canvas
            ref={waveCanvasRef}
            width={1200}
            height={100}
            style={{ width: "100%", height: "50px", display: "block" }}
          />
        </div>
      </div>

      {/* Branding */}
      <div style={S.brand}>
        <span style={S.brandName}>Rune</span>
        <span style={S.brandBy}>by <span style={{ fontFamily: "var(--font-signature)", fontSize: "18px" }}>Kuladeep Mantri</span></span>
      </div>
    </div>
  );
}

const S = {
  screen: {
    width: "100%", height: "100%",
    background: "radial-gradient(ellipse at 15% 20%, rgba(234,160,8,0.08) 0%, rgba(197,120,8,0.03) 30%, #000 65%)",
    display: "flex", flexDirection: "column" as const,
    padding: "20px 28px 24px", overflow: "hidden",
    position: "relative" as const,
  },

  // Top bar
  topBar: {
    display: "flex", justifyContent: "space-between" as const, alignItems: "flex-start" as const,
  },
  healthBlock: {
    display: "flex", alignItems: "baseline" as const, gap: "12px",
  },
  healthNum: {
    fontFamily: "var(--font-data)", fontSize: "64px", fontWeight: 700,
    color: "rgba(255,255,255,0.95)", lineHeight: 1, fontVariantNumeric: "tabular-nums" as const,
    textShadow: "0 0 50px rgba(234,160,8,0.2)",
  },
  healthMeta: {
    display: "flex", flexDirection: "column" as const, gap: "2px",
  },
  healthLabel: {
    fontFamily: "var(--font-ui)", fontSize: "11px", fontWeight: 600,
    letterSpacing: "0.15em", color: "rgba(255,255,255,0.25)",
  },
  stateLabel: {
    fontFamily: "var(--font-ui)", fontSize: "14px", fontWeight: 400,
    color: "rgba(255,255,255,0.4)",
  },
  topRight: {
    display: "flex", gap: "20px",
  },
  statBox: {
    display: "flex", flexDirection: "column" as const, alignItems: "flex-end" as const, gap: "2px",
  },
  statNum: {
    fontFamily: "var(--font-data)", fontSize: "36px", fontWeight: 600,
    color: "rgba(255,255,255,0.85)", lineHeight: 1, fontVariantNumeric: "tabular-nums" as const,
  },
  statLabel: {
    fontFamily: "var(--font-ui)", fontSize: "11px", fontWeight: 600,
    letterSpacing: "0.12em", color: "rgba(255,255,255,0.2)",
  },

  // Voice section -- the hero
  voiceSection: {
    flex: 1, display: "flex", flexDirection: "column" as const,
    justifyContent: "center" as const, alignItems: "center" as const,
    padding: "0 40px",
  },
  voiceTag: {
    display: "flex", alignItems: "center" as const, gap: "8px", marginBottom: "16px",
  },
  voiceDot: {
    width: "8px", height: "8px", borderRadius: "4px",
    background: "#eab308",
    boxShadow: "0 0 14px rgba(234,179,8,0.5)",
    animation: "pulse-voice 2.5s ease-in-out infinite",
  },
  voiceTagText: {
    fontFamily: "var(--font-ui)", fontSize: "12px", fontWeight: 600,
    letterSpacing: "0.15em", color: "rgba(255,255,255,0.2)",
  },
  voiceMessage: {
    fontFamily: "var(--font-ui)", fontSize: "24px", fontWeight: 300,
    lineHeight: 1.6, color: "rgba(255,235,200,0.85)",
    textAlign: "center" as const, maxWidth: "600px", margin: 0,
  },

  // Bottom section
  bottomSection: {
    display: "flex", flexDirection: "column" as const, gap: "12px",
  },
  tripRow: {
    display: "flex", justifyContent: "space-between" as const, gap: "12px",
    padding: "14px 0",
    borderTop: "1px solid rgba(234,179,8,0.08)",
  },
  tripStat: {
    display: "flex", flexDirection: "column" as const, alignItems: "center" as const, gap: "3px",
    flex: 1, padding: "8px 0", borderRadius: "10px",
    background: "rgba(255,255,255,0.02)",
    backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
  },
  tripNum: {
    fontFamily: "var(--font-data)", fontSize: "22px", fontWeight: 600,
    color: "rgba(255,255,255,0.85)", fontVariantNumeric: "tabular-nums" as const,
  },
  tripUnit: {
    fontFamily: "var(--font-ui)", fontSize: "9px", fontWeight: 600,
    letterSpacing: "0.12em", color: "rgba(255,255,255,0.15)",
  },

  // Waveform
  waveWrap: {
    position: "relative" as const,
  },
  waveLabel: {
    position: "absolute" as const, top: "0", left: "0",
    fontFamily: "var(--font-ui)", fontSize: "9px", fontWeight: 600,
    letterSpacing: "0.12em", color: "rgba(255,255,255,0.08)",
  },

  // Brand
  brand: {
    position: "absolute" as const, bottom: "24px", right: "28px",
    display: "flex", alignItems: "baseline" as const, gap: "8px",
  },
  brandName: {
    fontFamily: "var(--font-data)", fontSize: "14px", fontWeight: 600,
    color: "rgba(255,255,255,0.12)",
  },
  brandBy: {
    fontFamily: "var(--font-ui)", fontSize: "11px", fontWeight: 300,
    color: "rgba(255,255,255,0.08)",
  },
} as const;
