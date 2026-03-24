import { OrbitControls } from "@react-three/drei";

export function CameraRig() {
  return (
    <OrbitControls
      autoRotate
      autoRotateSpeed={0.15}
      enablePan={false}
      enableDamping
      dampingFactor={0.05}
      minDistance={4}
      maxDistance={14}
      minPolarAngle={Math.PI * 0.15}
      maxPolarAngle={Math.PI * 0.48}
      touches={{ ONE: 0, TWO: 2 }}
    />
  );
}
