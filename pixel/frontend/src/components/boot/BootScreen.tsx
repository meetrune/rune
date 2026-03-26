import { useEffect, useState, useRef, useCallback } from "react";

interface BootScreenProps {
  onComplete: () => void;
}

// Clean, minimal boot: "Rune" fades in, holds, fades out. Tap to skip.
export function BootScreen({ onComplete }: BootScreenProps) {
  const [phase, setPhase] = useState<"fade-in" | "hold" | "fade-out">("fade-in");
  const completed = useRef(false);

  const finish = useCallback(() => {
    if (completed.current) return;
    completed.current = true;
    onComplete();
  }, [onComplete]);

  useEffect(() => {
    const t1 = setTimeout(() => setPhase("hold"), 100);
    const t2 = setTimeout(() => setPhase("fade-out"), 2500);
    const t3 = setTimeout(finish, 3300); // 2500 + 800ms fade-out
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [finish]);

  const opacity = phase === "hold" ? 1 : 0;

  return (
    <div
      onClick={finish}
      style={{
        position: "fixed",
        inset: 0,
        background: "#000",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 200,
        gap: "16px",
        opacity,
        transition: "opacity 800ms ease",
        cursor: "pointer",
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-data)",
          fontSize: "52px",
          fontWeight: 700,
          color: "rgba(255,255,255,0.9)",
          letterSpacing: "-0.02em",
        }}
      >
        Rune
      </span>
      <div
        style={{
          width: "40px",
          height: "1px",
          background: "rgba(255,255,255,0.1)",
        }}
      />
      <span style={{ fontFamily: "var(--font-signature)", fontSize: "22px", color: "rgba(255,255,255,0.15)" }}>
        Kuladeep Mantri
      </span>
    </div>
  );
}
