import { useEffect, useRef } from "react";
import { RuneScene } from "@/components/three/RuneScene";
import { useVehicleStore } from "@/stores/vehicleStore";

function HealthBadge() {
  const scoreRef = useRef<HTMLDivElement>(null);
  const labelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      if (scoreRef.current) {
        const score = state.health.overall;
        if (score === -1) {
          scoreRef.current.textContent = "--";
          scoreRef.current.style.color = "var(--rune-text-muted)";
        } else {
          scoreRef.current.textContent = Math.round(score).toString();
          if (score >= 80) {
            scoreRef.current.style.color = "var(--rune-primary)";
          } else if (score >= 60) {
            scoreRef.current.style.color = "var(--rune-warn)";
          } else {
            scoreRef.current.style.color = "var(--rune-critical)";
          }
        }
      }
      if (labelRef.current) {
        const score = state.health.overall;
        if (score === -1) {
          labelRef.current.textContent = "Calibrating";
        } else if (score >= 85) {
          labelRef.current.textContent = "All good";
        } else if (score >= 60) {
          labelRef.current.textContent = "Watch";
        } else {
          labelRef.current.textContent = "Attention";
        }
      }
    });
    return unsub;
  }, []);

  return (
    <div
      style={{
        position: "absolute",
        top: "calc(20px + env(safe-area-inset-top))",
        right: "calc(20px + env(safe-area-inset-right))",
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-end",
        gap: "2px",
        pointerEvents: "none",
      }}
    >
      <div
        ref={scoreRef}
        style={{
          fontFamily: "var(--font-data)",
          fontSize: "72px",
          fontWeight: 700,
          lineHeight: 1,
          color: "var(--rune-text-muted)",
        }}
      >
        --
      </div>
      <div
        ref={labelRef}
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "12px",
          letterSpacing: "0.15em",
          textTransform: "uppercase",
          color: "var(--rune-text-muted)",
          opacity: 0.6,
        }}
      >
        Calibrating
      </div>
    </div>
  );
}

function VoicePanel() {
  const msgRef = useRef<HTMLDivElement>(null);
  const prevScore = useRef(-1);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      if (!msgRef.current) return;
      const score = state.health.overall;

      // Only update message when score changes meaningfully
      if (Math.abs(score - prevScore.current) < 3 && prevScore.current !== -1) return;
      prevScore.current = score;

      if (score === -1) {
        msgRef.current.textContent = "Give me a minute. Still learning.";
      } else if (score >= 90) {
        msgRef.current.textContent = `All good. ${Math.round(score)} across the board.`;
      } else if (score >= 75) {
        msgRef.current.textContent = `Running fine. ${Math.round(score)} overall.`;
      } else if (score >= 60) {
        msgRef.current.textContent = "Something's a bit off. Keep an eye on it.";
      } else {
        msgRef.current.textContent = "Something I need to tell you. Worth a look.";
      }
    });
    return unsub;
  }, []);

  return (
    <div
      style={{
        position: "absolute",
        bottom: "calc(40px + env(safe-area-inset-bottom))",
        left: "20px",
        right: "20px",
        pointerEvents: "none",
      }}
    >
      <div
        ref={msgRef}
        style={{
          fontFamily: "var(--font-voice)",
          fontSize: "20px",
          color: "var(--rune-text)",
          opacity: 0.7,
          textAlign: "center",
          lineHeight: 1.4,
        }}
      >
        Waiting for Rune...
      </div>
    </div>
  );
}

function ConnectionDot() {
  const dotRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      if (dotRef.current) {
        dotRef.current.style.background = state.connected
          ? "var(--rune-primary)"
          : "var(--rune-critical)";
      }
    });
    return unsub;
  }, []);

  return (
    <div
      style={{
        position: "absolute",
        top: "calc(28px + env(safe-area-inset-top))",
        left: "calc(20px + env(safe-area-inset-left))",
        display: "flex",
        alignItems: "center",
        gap: "8px",
        pointerEvents: "none",
      }}
    >
      <div
        ref={dotRef}
        style={{
          width: "8px",
          height: "8px",
          borderRadius: "50%",
          background: "var(--rune-critical)",
          transition: "background 0.3s",
        }}
      />
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "11px",
          letterSpacing: "0.15em",
          color: "var(--rune-text-muted)",
          opacity: 0.5,
          textTransform: "uppercase",
        }}
      >
        Rune
      </span>
    </div>
  );
}

export function VisualizationScreen() {
  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <RuneScene />
      <ConnectionDot />
      <HealthBadge />
      <VoicePanel />
    </div>
  );
}
