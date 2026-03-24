import { useEffect, useRef } from "react";

interface BootScreenProps {
  onComplete: () => void;
}

export function BootScreen({ onComplete }: BootScreenProps) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    timerRef.current = setTimeout(() => {
      onComplete();
    }, 2000);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [onComplete]);

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
        zIndex: 1000,
      }}
    >
      {/* "Rune" text with breathing animation */}
      <span
        style={{
          fontFamily: "var(--font-data)",
          fontSize: "48px",
          fontWeight: 500,
          color: "#fff",
          letterSpacing: "0.08em",
          animation: "runeBreathing 2s ease-in-out infinite",
        }}
      >
        Rune
      </span>

      {/* Thin horizontal divider */}
      <div
        style={{
          width: "40%",
          height: "1px",
          background: "rgba(255,255,255,0.08)",
          marginTop: "16px",
        }}
      />

      {/* Maker's mark at bottom */}
      <div
        style={{
          position: "absolute",
          bottom: "32px",
          left: "50%",
          transform: "translateX(-50%)",
          textAlign: "center",
          whiteSpace: "nowrap",
        }}
      >
        <span
          style={{
            fontFamily: "'Cormorant Garamond', Georgia, serif",
            fontStyle: "italic",
            fontSize: "13px",
            color: "#fff",
            opacity: 0.12,
          }}
        >
          crafted by{" "}
        </span>
        <span
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "13px",
            color: "#fff",
            opacity: 0.15,
          }}
        >
          Kuladeep Mantri
        </span>
      </div>

      {/* Keyframes injected via style tag */}
      <style>{`
        @keyframes runeBreathing {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 0.9; }
        }
      `}</style>
    </div>
  );
}
