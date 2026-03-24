import { Suspense, useMemo, useRef, useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { useGLTF, OrbitControls, ContactShadows, Environment, Html } from "@react-three/drei";
import * as THREE from "three";
import { useVehicleStore } from "@/stores/vehicleStore";
import { getSensorState, getSensorLabel, getSensorUnit } from "@/constants/thresholds";
import type { SubsystemId } from "@/types/vehicle";

const MODEL_PATH = "/models/accord.glb";

const SUBS: { id: SubsystemId; label: string; pos: [number, number, number]; sensors: string[] }[] = [
  { id: "engine", label: "Engine", pos: [0.4, 0.4, 1.6], sensors: ["RPM", "ENGINE_LOAD", "OIL_TEMP", "THROTTLE_POS"] },
  { id: "transmission", label: "CVT", pos: [-0.3, 0, 1.4], sensors: ["RPM", "SPEED", "CVT_TEMP"] },
  { id: "cooling", label: "Cooling", pos: [0, 0.3, 2.2], sensors: ["COOLANT_TEMP", "INTAKE_TEMP"] },
  { id: "fuel", label: "Fuel", pos: [0, -0.1, -0.8], sensors: ["FUEL_LEVEL", "MAF", "STFT", "LTFT"] },
  { id: "exhaust", label: "Exhaust", pos: [0.4, -0.3, -1.2], sensors: ["CATALYST_TEMP"] },
  { id: "electrical", label: "Electrical", pos: [-0.5, 0.4, 1.8], sensors: ["BATTERY_V"] },
];

function stColor(s: number) {
  if (s === -1) return "rgba(255,255,255,0.15)";
  if (s < 50) return "#c53030";
  if (s < 70) return "#d4a017";
  return "rgba(255,255,255,0.5)";
}

function fmt(k: string, v: number) {
  if (k === "RPM") return Math.round(v).toLocaleString();
  if (k === "BATTERY_V" || k === "MAF") return v.toFixed(1);
  if (k === "STFT" || k === "LTFT") return `${v >= 0 ? "+" : ""}${v.toFixed(1)}`;
  return String(Math.round(v));
}

function TelemetryModel() {
  const { scene } = useGLTF(MODEL_PATH);

  useMemo(() => {
    const bodyMat = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(0x3a3a42), metalness: 0.8, roughness: 0.2,
      clearcoat: 1.0, clearcoatRoughness: 0.1, envMapIntensity: 1.5,
    });
    const glassMat = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(0x111115), metalness: 0.1, roughness: 0.05,
      transmission: 0.6, thickness: 0.5, envMapIntensity: 2.0, ior: 1.5,
    });
    const darkMat = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(0x1a1a1e), metalness: 0.6, roughness: 0.4, envMapIntensity: 0.8,
    });

    scene.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return;
      const name = child.name.toLowerCase();
      if (name.startsWith("material3")) child.material = glassMat;
      else if (name.startsWith("material4") || name.startsWith("material5")) child.material = darkMat;
      else child.material = bodyMat;
    });

    const box = new THREE.Box3().setFromObject(scene);
    const center = box.getCenter(new THREE.Vector3());
    scene.position.sub(center);
    scene.position.y += box.getSize(new THREE.Vector3()).y * 0.5;
  }, [scene]);

  return <primitive object={scene} />;
}

function ZoneMarker({ sub, onClick, isSelected }: {
  sub: typeof SUBS[number]; onClick: () => void; isSelected: boolean;
}) {
  const dotRef = useRef<HTMLDivElement>(null);
  const labelRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const s = state.health[sub.id];
      const color = stColor(s);
      if (dotRef.current) {
        dotRef.current.style.background = color;
        dotRef.current.style.boxShadow = s < 70 && s !== -1 ? `0 0 16px ${color}` : "0 0 8px rgba(255,255,255,0.1)";
      }
      if (labelRef.current) {
        labelRef.current.textContent = `${sub.label} ${s === -1 ? "--" : Math.round(s)}`;
        labelRef.current.style.color = color;
      }
    });
    return unsub;
  }, [sub]);

  return (
    <Html position={sub.pos} center>
      <div
        onClick={onClick}
        style={{
          display: "flex", flexDirection: "column", alignItems: "center", gap: "4px",
          cursor: "pointer", WebkitTapHighlightColor: "transparent",
          transform: isSelected ? "scale(1.15)" : "scale(1)",
          transition: "transform 200ms ease",
        }}
      >
        <div ref={dotRef} style={{
          width: isSelected ? "14px" : "10px", height: isSelected ? "14px" : "10px",
          borderRadius: "50%", background: "rgba(255,255,255,0.5)",
          transition: "all 300ms",
        }} />
        <span ref={labelRef} style={{
          fontFamily: "var(--font-data)", fontSize: "11px", fontWeight: 600,
          color: "rgba(255,255,255,0.5)", whiteSpace: "nowrap",
          textShadow: "0 1px 4px rgba(0,0,0,0.8)",
        }}>{sub.label} --</span>
      </div>
    </Html>
  );
}

export function TelemetryScreen() {
  const [selected, setSelected] = useState<SubsystemId | null>(null);
  const sensorRefs = useRef<(HTMLSpanElement | null)[]>([]);

  const selectedSub = SUBS.find((s) => s.id === selected);
  const sensorKeys = selectedSub?.sensors ?? ["RPM", "SPEED", "COOLANT_TEMP", "BATTERY_V", "FUEL_LEVEL", "OIL_TEMP"];

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      sensorKeys.forEach((key, i) => {
        const el = sensorRefs.current[i];
        if (!el) return;
        const v = state.sensors[key]?.v;
        const st = v !== undefined ? getSensorState(key, v) : "normal";
        el.textContent = v !== undefined ? fmt(key, v) : "--";
        el.style.color = st === "critical" ? "#c53030" : st === "warn" ? "#d4a017" : "rgba(255,255,255,0.9)";
      });
    });
    return unsub;
  }, [sensorKeys]);

  return (
    <div style={{ width: "100%", height: "100%", background: "#000", display: "flex", overflow: "hidden" }}>
      {/* 3D car view -- the telemetry IS the car */}
      <div style={{ flex: 1, position: "relative", touchAction: "none" }}>
        <Canvas
          camera={{ position: [0, 8, 3], fov: 30, near: 0.1, far: 100 }}
          gl={{ antialias: true, alpha: true, powerPreference: "high-performance", toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.2 }}
          style={{ background: "transparent" }}
          dpr={[1, 2]}
        >
          <Environment preset="night" background={false} />
          <ambientLight intensity={0.4} />
          <directionalLight position={[4, 6, -2]} intensity={3} color="#ffffff" />
          <directionalLight position={[-4, 5, 3]} intensity={1.5} color="#d8d8ff" />

          <Suspense fallback={null}>
            <group position={[0, -0.8, 0]}>
              <TelemetryModel />
            </group>
            {SUBS.map((sub) => (
              <ZoneMarker
                key={sub.id}
                sub={sub}
                isSelected={selected === sub.id}
                onClick={() => setSelected(selected === sub.id ? null : sub.id)}
              />
            ))}
            <ContactShadows position={[0, -0.85, 0]} opacity={0.2} scale={14} blur={2.5} far={4} />
          </Suspense>

          <OrbitControls
            enableZoom={false} enablePan={false}
            minPolarAngle={Math.PI * 0.1} maxPolarAngle={Math.PI * 0.45}
            rotateSpeed={0.4} target={[0, 0, 0]}
          />
        </Canvas>

        {/* Instruction hint */}
        {!selected && (
          <div style={{
            position: "absolute", bottom: "32px", left: "50%", transform: "translateX(-50%)",
            fontFamily: "var(--font-ui)", fontSize: "13px", fontWeight: 300,
            color: "rgba(255,255,255,0.2)", pointerEvents: "none",
          }}>
            Tap a zone to inspect
          </div>
        )}
      </div>

      {/* Right panel: sensor detail */}
      <div style={{
        width: "280px", flexShrink: 0,
        padding: "24px 20px 28px",
        display: "flex", flexDirection: "column", gap: "12px",
        borderLeft: "1px solid rgba(255,255,255,0.04)",
        overflowY: "auto",
      }}>
        <span style={{
          fontFamily: "var(--font-data)", fontSize: "20px", fontWeight: 600,
          color: "rgba(255,255,255,0.85)",
        }}>
          {selectedSub ? selectedSub.label : "Overview"}
        </span>

        {sensorKeys.map((key, i) => (
          <div key={key} style={{
            padding: "14px 16px", borderRadius: "12px",
            background: "rgba(255,255,255,0.025)",
            backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)",
            border: "1px solid rgba(255,255,255,0.04)",
            display: "flex", flexDirection: "column", gap: "4px",
          }}>
            <span style={{
              fontFamily: "var(--font-ui)", fontSize: "12px", fontWeight: 500,
              color: "rgba(255,255,255,0.3)",
            }}>
              {getSensorLabel(key)} <span style={{ opacity: 0.5 }}>{getSensorUnit(key)}</span>
            </span>
            <span
              ref={(el) => { sensorRefs.current[i] = el; }}
              style={{
                fontFamily: "var(--font-data)", fontSize: "28px", fontWeight: 600,
                color: "rgba(255,255,255,0.9)", lineHeight: 1,
                fontVariantNumeric: "tabular-nums", transition: "color 400ms",
              }}
            >--</span>
          </div>
        ))}
      </div>
    </div>
  );
}
