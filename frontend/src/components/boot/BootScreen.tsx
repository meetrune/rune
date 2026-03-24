import { useEffect, useState } from "react";

interface BootScreenProps {
  onComplete: () => void;
}

// Clean, minimal boot: "Rune" fades in, holds, fades out.
export function BootScreen({ onComplete }: BootScreenProps) {
  const [phase, setPhase] = useState<"fade-in" | "hold" | "fade-out">("fade-in");

  useEffect(() => {
    const t1 = setTimeout(() => setPhase("hold"), 100);
    const t2 = setTimeout(() => setPhase("fade-out"), 2500);
    const t3 = setTimeout(onComplete, 3200);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [onComplete]);

  const opacity = phase === "hold" ? 1 : 0;

  return (
    <div
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
      <span
        style={{
          fontFamily: "var(--font-credit)",
          fontStyle: "italic",
          fontSize: "15px",
          fontWeight: 300,
          color: "rgba(255,255,255,0.12)",
        }}
      >
        crafted by Kuladeep Mantri
      </span>
    </div>
  );
}
