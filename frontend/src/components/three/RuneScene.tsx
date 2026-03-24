import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { RuneCar } from "./RuneCar";
import { CameraRig } from "./CameraRig";
import { useThemeStore, getActiveTheme } from "@/stores/themeStore";

function SceneContent() {
  // Subscribe to theme changes to update background
  useThemeStore((s) => s.activeThemeId);
  const theme = getActiveTheme();

  return (
    <>
      <color attach="background" args={[theme.bg]} />
      <ambientLight intensity={0.15} />
      <CameraRig />
      <Suspense fallback={null}>
        <RuneCar />
      </Suspense>
      <EffectComposer>
        <Bloom
          luminanceThreshold={1.0}
          luminanceSmoothing={0.3}
          intensity={0.4}
          radius={0.4}
          mipmapBlur
        />
      </EffectComposer>
    </>
  );
}

export function RuneScene() {
  return (
    <Canvas
      dpr={[1, 2]}
      flat
      camera={{ position: [6, 3.5, 6], fov: 40, near: 0.1, far: 100 }}
      style={{ position: "fixed", inset: 0 }}
      gl={{
        antialias: true,
        alpha: false,
        powerPreference: "high-performance",
      }}
    >
      <SceneContent />
    </Canvas>
  );
}
