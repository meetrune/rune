import { Suspense, useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { useGLTF, OrbitControls, ContactShadows, Environment } from "@react-three/drei";
import * as THREE from "three";

const MODEL_PATH = "/models/accord.glb";
useGLTF.preload(MODEL_PATH);

function AccordModel() {
  const { scene } = useGLTF(MODEL_PATH);

  useMemo(() => {
    // Metallic grey car paint with clearcoat for realistic reflections
    const bodyMat = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(0x3a3a42),
      metalness: 0.8,
      roughness: 0.2,
      clearcoat: 1.0,
      clearcoatRoughness: 0.1,
      envMapIntensity: 1.5,
    });

    // Dark tinted glass
    const glassMat = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(0x111115),
      metalness: 0.1,
      roughness: 0.05,
      transmission: 0.6,
      thickness: 0.5,
      envMapIntensity: 2.0,
      ior: 1.5,
    });

    // Chrome/bright trim
    const chromeMat = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(0xcccccc),
      metalness: 1.0,
      roughness: 0.05,
      envMapIntensity: 2.0,
    });

    // Dark matte for wheels/tires/grille
    const darkMat = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(0x1a1a1e),
      metalness: 0.6,
      roughness: 0.4,
      envMapIntensity: 0.8,
    });

    scene.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return;

      // Assign materials based on original material group names
      // Material2.xxx = body panels (most common)
      // Material3.xxx = glass/windows
      // Material4.xxx = chrome/trim/lights
      // Material5 = dark parts/grille
      const name = child.name.toLowerCase();

      if (name.startsWith("material3")) {
        child.material = glassMat;
      } else if (name.startsWith("material4")) {
        child.material = chromeMat;
      } else if (name.startsWith("material5")) {
        child.material = darkMat;
      } else {
        // Default body paint for Material2.xxx and anything else
        child.material = bodyMat;
      }
    });

    // Center the model
    const box = new THREE.Box3().setFromObject(scene);
    const center = box.getCenter(new THREE.Vector3());
    scene.position.sub(center);
    scene.position.y += box.getSize(new THREE.Vector3()).y * 0.5;
  }, [scene]);

  return <primitive object={scene} />;
}

export function CarScene() {
  return (
    <div style={{ width: "100%", height: "100%", touchAction: "none" }}>
      <Canvas
        camera={{
          position: [7, 3, 5],
          fov: 28,
          near: 0.1,
          far: 100,
        }}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: "high-performance",
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.2,
        }}
        style={{ background: "transparent" }}
        dpr={[1, 2]}
      >
        {/* HDRI environment for realistic reflections on the metallic paint */}
        <Environment preset="night" background={false} />

        {/* Studio lighting on top of HDRI */}
        <ambientLight intensity={0.3} />

        <directionalLight
          position={[6, 5, -2]}
          intensity={3}
          color="#ffffff"
        />

        <directionalLight
          position={[-5, 4, 3]}
          intensity={1.5}
          color="#d8d8ff"
        />

        <directionalLight
          position={[-1, 3, 7]}
          intensity={1.5}
          color="#e0e0ff"
        />

        <Suspense fallback={null}>
          <group position={[0, -0.8, 0]}>
            <AccordModel />
          </group>
          <ContactShadows
            position={[0, -0.85, 0]}
            opacity={0.3}
            scale={14}
            blur={2.5}
            far={4}
            color="#000000"
          />
        </Suspense>

        {/* Touch rotation */}
        <OrbitControls
          enableZoom={false}
          enablePan={false}
          autoRotate={false}
          minPolarAngle={Math.PI * 0.35}
          maxPolarAngle={Math.PI * 0.55}
          rotateSpeed={0.5}
          target={[0, 0, 0]}
        />
      </Canvas>
    </div>
  );
}
