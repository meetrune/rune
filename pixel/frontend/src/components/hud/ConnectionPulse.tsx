import { useRef, useEffect } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";

const DOT_COUNT = 3;
const TRACK_WIDTH = 48;
const DOT_SIZE = 4;

export function ConnectionPulse() {
  const dotsRef = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const connected = state.connected;
      for (let i = 0; i < DOT_COUNT; i++) {
        const dot = dotsRef.current[i];
        if (!dot) continue;
        dot.style.opacity = connected ? "0.6" : "0.12";
        dot.style.animationPlayState = connected ? "running" : "paused";
      }
    });
    return unsub;
  }, []);

  return (
    <div style={styles.track}>
      <style>{keyframes}</style>
      {Array.from({ length: DOT_COUNT }, (_, i) => (
        <div
          key={i}
          ref={(el) => {
            dotsRef.current[i] = el;
          }}
          style={{
            ...styles.dot,
            animationDelay: `${i * 200}ms`,
          }}
        />
      ))}
    </div>
  );
}

const keyframes = `
@keyframes connection-pulse-travel {
  0% {
    transform: translateX(0);
    opacity: 0;
  }
  15% {
    opacity: 0.6;
  }
  85% {
    opacity: 0.6;
  }
  100% {
    transform: translateX(${TRACK_WIDTH - DOT_SIZE}px);
    opacity: 0;
  }
}
`;

const styles = {
  track: {
    position: "relative" as const,
    width: `${TRACK_WIDTH}px`,
    height: `${DOT_SIZE + 4}px`,
    overflow: "hidden",
    display: "flex",
    alignItems: "center",
  },
  dot: {
    position: "absolute" as const,
    left: 0,
    width: `${DOT_SIZE}px`,
    height: `${DOT_SIZE}px`,
    borderRadius: "50%",
    backgroundColor: "var(--rune-text)",
    opacity: 0.6,
    animation: `connection-pulse-travel 1.8s ease-in-out infinite`,
    willChange: "transform, opacity",
  },
} as const;
