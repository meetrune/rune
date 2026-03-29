import { useRef, useEffect } from "react";
import { ZoneOverlays } from "./ZoneOverlays";
import { useVehicleStore } from "@/stores/vehicleStore";

// 3/4 perspective view rendered from Blender (Honda Accord 3D model).
// Single view -- no top-down/side toggle needed with 3D-rendered image.
export function CarView() {
  const breathingRef = useRef<HTMLDivElement>(null);

  // Breathing animation: car image scales +-0.6% synced to RPM
  useEffect(() => {
    const unsubscribe = useVehicleStore.subscribe((state) => {
      const rpm = state.sensors["RPM"]?.v ?? 0;
      const el = breathingRef.current;
      if (!el) return;

      if (rpm > 0) {
        // 800 RPM -> ~2.5s breath, 3000 RPM -> ~0.67s
        const duration = Math.max(0.3, (60 / rpm) * 33);
        el.style.animationDuration = `${duration}s`;
        el.style.animationPlayState = "running";
      } else {
        el.style.animationPlayState = "paused";
        el.style.transform = "scale(1)";
      }
    });
    return unsubscribe;
  }, []);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <style>{`
        @keyframes car-breathing {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.006); }
        }
      `}</style>

      <div
        ref={breathingRef}
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          animation: "car-breathing 2.5s ease-in-out infinite",
          animationPlayState: "paused",
          willChange: "transform",
        }}
      >
        {/* Blender-rendered Honda Accord 3/4 wireframe */}
        <img
          src="/accord-hud.png"
          alt=""
          draggable={false}
          style={{
            width: "100%",
            maxWidth: "680px",
            height: "auto",
            objectFit: "contain",
            userSelect: "none",
            pointerEvents: "none",
          }}
        />

        {/* Zone overlays positioned on the car image */}
        <ZoneOverlays view="topDown" viewBox="0 0 1920 900" />
      </div>
    </div>
  );
}
