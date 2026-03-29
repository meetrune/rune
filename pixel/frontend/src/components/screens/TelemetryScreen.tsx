import { Suspense, useMemo, useRef, useEffect, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useGLTF, OrbitControls, ContactShadows, Environment, Html } from "@react-three/drei";
import * as THREE from "three";
import { useVehicleStore } from "@/stores/vehicleStore";
import { useUiStore } from "@/stores/uiStore";
import { SUBSYSTEM_SENSORS } from "@/constants/zones";
import { TelemetrySensorCard } from "@/components/telemetry/TelemetrySensorCard";
import { OfflineIndicator } from "@/components/hud/OfflineIndicator";
import type { SubsystemId } from "@/types/vehicle";

const MODEL_PATH = "/models/accord.glb";

// Zone positions for the real 2026 Honda Accord SE component layout.
// Camera is 3/4 front-right: right/passenger side faces us, left/driver side is far.
// Y=up, Z=front(+)/rear(-), X=right/passenger(+)/left/driver(-).
const SUBS: { id: SubsystemId; label: string; short: string; pos: [number, number, number] }[] = [
  { id: "engine", label: "Engine", short: "ENG", pos: [0.2, 0.0, 1.2] },          // on the hood, slight right
  { id: "transmission", label: "CVT", short: "CVT", pos: [-0.3, -0.1, 1.0] },    // under hood, left/driver side
  { id: "cooling", label: "Cooling", short: "COOL", pos: [0, -0.2, 1.7] },        // radiator at front grille, lower
  { id: "fuel", label: "Fuel", short: "FUEL", pos: [-0.5, -0.1, -0.5] },          // fuel cap left rear quarter panel
  { id: "exhaust", label: "Exhaust", short: "EXH", pos: [0.3, -0.3, -1.2] },      // rear exhaust outlet, right side
  { id: "electrical", label: "Electrical", short: "ELEC", pos: [0.5, 0.0, 1.3] },  // battery front-right engine bay
];

// Health score to color
function healthColor(s: number): string {
  if (s === -1) return "rgba(255,255,255,0.15)";
  if (s < 50) return "#ef4444";
  if (s < 70) return "#f59e0b";
  return "rgba(255,255,255,0.5)";
}

// Default overview sensors: unique OBD data Honda doesn't show
const DEFAULT_SENSORS = ["STFT", "LTFT", "OIL_TEMP", "CATALYST_TEMP", "BATTERY_V", "ENGINE_LOAD"];

// Camera positions
const CAM_DEFAULT = new THREE.Vector3(6, 2.8, 4.5);
const TARGET_DEFAULT = new THREE.Vector3(0, 0, 0);
const ZOOM_DISTANCE = 2.8; // how close to get to a zone
const LERP_SPEED = 3.5;    // animation smoothness (higher = faster)

// Unified camera controller: cinematic zoom + auto-rotate + manual drag.
// Uses OrbitControls ref to sync everything without fighting.
function CameraController({ targetPos, controlsRef }: {
  targetPos: [number, number, number] | null;
  controlsRef: React.RefObject<any>;
}) {
  const { camera } = useThree();
  const camGoal = useRef(new THREE.Vector3().copy(CAM_DEFAULT));
  const lookGoal = useRef(new THREE.Vector3().copy(TARGET_DEFAULT));
  const lookCurrent = useRef(new THREE.Vector3().copy(TARGET_DEFAULT));
  const animating = useRef(false);

  useEffect(() => {
    animating.current = true;
    if (targetPos) {
      const zone = new THREE.Vector3(...targetPos);
      const dir = new THREE.Vector3().copy(CAM_DEFAULT).sub(TARGET_DEFAULT).normalize();
      camGoal.current.copy(zone).add(dir.multiplyScalar(ZOOM_DISTANCE));
      lookGoal.current.copy(zone);
    } else {
      camGoal.current.copy(CAM_DEFAULT);
      lookGoal.current.copy(TARGET_DEFAULT);
    }
  }, [targetPos]);

  useFrame((_, delta) => {
    if (!animating.current) return;

    const t = 1 - Math.exp(-LERP_SPEED * delta);
    camera.position.lerp(camGoal.current, t);
    lookCurrent.current.lerp(lookGoal.current, t);
    camera.lookAt(lookCurrent.current);

    // Sync OrbitControls target so it knows where we are
    if (controlsRef.current) {
      controlsRef.current.target.copy(lookCurrent.current);
      controlsRef.current.update();
    }

    // Stop animating once arrived (hand off to OrbitControls)
    if (camera.position.distanceTo(camGoal.current) < 0.02) {
      animating.current = false;
    }
  });

  return null;
}

// ---- 3D Model (locked-in materials) ----

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

// ---- Zone Marker: dots-only, label only on selection ----

function ZoneMarker({ sub, onClick, isSelected }: {
  sub: typeof SUBS[number]; onClick: () => void; isSelected: boolean;
}) {
  const dotRef = useRef<HTMLDivElement>(null);
  const scoreRef = useRef<HTMLSpanElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const s = state.health[sub.id];
      const color = healthColor(s);
      if (dotRef.current) {
        dotRef.current.style.background = color;
        dotRef.current.style.boxShadow = `0 0 ${s < 70 && s !== -1 ? 14 : 6}px ${color}`;
      }
      if (scoreRef.current) {
        scoreRef.current.textContent = s === -1 ? "--" : String(Math.round(s));
        scoreRef.current.style.color = color;
      }
      if (ringRef.current) {
        ringRef.current.style.borderColor = color;
        ringRef.current.style.boxShadow = `0 0 12px ${color}, inset 0 0 8px ${color}`;
      }
    });
    return unsub;
  }, [sub]);

  return (
    <Html position={sub.pos} center>
      <div
        onClick={(e) => { e.stopPropagation(); onClick(); }}
        style={{
          display: "flex", flexDirection: "column", alignItems: "center",
          cursor: "pointer", WebkitTapHighlightColor: "transparent",
          padding: 10, minWidth: 56, minHeight: 56, justifyContent: "center",
          position: "relative",
        }}
      >
        {/* Marker: thin ring + center dot. Expands + glows on select. */}
        <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
          {/* Ring */}
          <div ref={ringRef} style={{
            width: isSelected ? 36 : 18, height: isSelected ? 36 : 18,
            borderRadius: "50%",
            border: isSelected ? "1.5px solid rgba(255,255,255,0.3)" : "1px solid rgba(255,255,255,0.15)",
            boxShadow: "none",
            transition: "all 400ms cubic-bezier(0.16, 1, 0.3, 1)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            {/* Center dot */}
            <div ref={dotRef} style={{
              width: isSelected ? 6 : 4, height: isSelected ? 6 : 4,
              borderRadius: "50%", background: "rgba(255,255,255,0.4)",
              transition: "all 300ms cubic-bezier(0.16, 1, 0.3, 1)",
            }} />
          </div>
        </div>

        {/* Label */}
        <span style={{
          fontFamily: "var(--font-data)", fontSize: 11, fontWeight: 600,
          color: isSelected ? "rgba(255,255,255,0.55)" : "rgba(255,255,255,0.18)",
          whiteSpace: "nowrap", letterSpacing: "0.05em", marginTop: 3,
          textShadow: "0 1px 4px rgba(0,0,0,0.9)",
          transition: "color 300ms",
        }}>{sub.short}</span>

        {/* Score -- fades in on selection */}
        {isSelected && (
          <span ref={scoreRef} style={{
            fontFamily: "var(--font-data)", fontSize: 14, fontWeight: 700,
            color: "rgba(255,255,255,0.5)", whiteSpace: "nowrap",
            textShadow: "0 1px 6px rgba(0,0,0,0.9)",
            animation: "fade-in 300ms ease",
          }}>--</span>
        )}
      </div>
    </Html>
  );
}

// ---- Main Telemetry Screen ----

export function TelemetryScreen() {
  const [selected, setSelected] = useState<SubsystemId | null>(null);
  const controlsRef = useRef<any>(null);
  const headerScoreRef = useRef<HTMLSpanElement>(null);
  const headerBarRef = useRef<HTMLDivElement>(null);
  const panelBorderRef = useRef<HTMLDivElement>(null);
  const isActive = useUiStore((s) => s.activeScreen === "telemetry");

  const selectedSub = SUBS.find((s) => s.id === selected);
  const sensorKeys = selected ? (SUBSYSTEM_SENSORS[selected] ?? DEFAULT_SENSORS) : DEFAULT_SENSORS;

  // Imperative health score + accent color updates
  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const score = selected ? state.health[selected] : state.health.overall;
      const color = healthColor(score);
      if (headerScoreRef.current) {
        headerScoreRef.current.textContent = score === -1 ? "--" : String(Math.round(score));
        headerScoreRef.current.style.color = color;
      }
      if (headerBarRef.current) {
        headerBarRef.current.style.width = score === -1 ? "0%" : `${Math.max(0, Math.min(100, score))}%`;
        headerBarRef.current.style.background = color;
      }
      if (panelBorderRef.current) {
        // Use a fixed low-opacity version of the health color for the border
        let borderColor = "rgba(255,255,255,0.04)";
        if (score !== -1) {
          if (score < 50) borderColor = "rgba(239,68,68,0.15)";
          else if (score < 70) borderColor = "rgba(245,158,11,0.15)";
          else borderColor = "rgba(255,255,255,0.08)";
        }
        panelBorderRef.current.style.borderLeftColor = borderColor;
      }
    });
    return unsub;
  }, [selected]);

  return (
    <div style={{ width: "100%", height: "100%", background: "#000", display: "flex", overflow: "hidden" }}>
      {/* 3D car -- tap empty space to deselect back to Overview */}
      <div onClick={() => setSelected(null)} style={{ flex: 1, position: "relative", touchAction: "none" }}>
        <OfflineIndicator />
        {/* Maker's bar -- architectural, part of the frame */}
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, zIndex: 10, pointerEvents: "none",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "10px 18px 8px",
          borderBottom: "1px solid rgba(255,255,255,0.04)",
          background: "linear-gradient(180deg, rgba(0,0,0,0.5) 0%, transparent 100%)",
        }}>
          <span style={{
            fontFamily: "var(--font-data)", fontSize: 16, fontWeight: 600,
            color: "rgba(255,255,255,0.4)", letterSpacing: "0.2em",
          }}>RUNE</span>
          <span style={{
            fontFamily: "var(--font-data)", fontSize: 14, fontWeight: 400,
            color: "rgba(255,255,255,0.45)", letterSpacing: "0.08em",
          }}>Kuladeep M. <span style={{ fontWeight: 300, color: "rgba(255,255,255,0.2)" }}>/</span> <span style={{ fontSize: 13, fontWeight: 300, color: "rgba(255,255,255,0.25)", letterSpacing: "0.04em" }}>engineer</span></span>
        </div>
        <Canvas
          camera={{ position: [6, 2.8, 4.5], fov: 28, near: 0.1, far: 100 }}
          gl={{ antialias: true, alpha: true, powerPreference: "high-performance", toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.2 }}
          style={{ background: "transparent" }}
          dpr={[1, 2]}
          frameloop={isActive ? "always" : "demand"}
        >
          <Environment preset="night" background={false} />
          <ambientLight intensity={0.3} />
          <directionalLight position={[6, 5, -2]} intensity={3} color="#ffffff" />
          <directionalLight position={[-5, 4, 3]} intensity={1.5} color="#d8d8ff" />
          <directionalLight position={[-1, 3, 7]} intensity={1.5} color="#e0e0ff" />

          <CameraController targetPos={selectedSub?.pos ?? null} controlsRef={controlsRef} />

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

          {/* Always mounted -- auto-rotates when idle, disabled during zoom */}
          <OrbitControls
            ref={controlsRef}
            enableZoom={false} enablePan={false}
            enabled={!selected}
            autoRotate={!selected}
            autoRotateSpeed={0.3}
            minPolarAngle={Math.PI * 0.35} maxPolarAngle={Math.PI * 0.55}
            rotateSpeed={0.4}
          />
        </Canvas>
      </div>

      {/* Right panel: subsystem deep dive */}
      <div ref={panelBorderRef} style={{
        width: "28%", minWidth: "220px", maxWidth: "320px", flexShrink: 0,
        padding: "12px 14px 10px",
        display: "flex", flexDirection: "column", gap: 8,
        borderLeft: "2px solid rgba(255,255,255,0.04)",
        overflowY: "auto", transition: "border-left-color 400ms",
      }}>
        {/* Subsystem header: name + health score + bar */}
        <div style={{ marginBottom: 4 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span style={{
              fontFamily: "var(--font-data)", fontSize: 20, fontWeight: 600,
              color: "rgba(255,255,255,0.85)",
            }}>
              {selectedSub ? selectedSub.label : "Overview"}
            </span>
            <span ref={headerScoreRef} style={{
              fontFamily: "var(--font-data)", fontSize: 32, fontWeight: 700,
              color: "rgba(255,255,255,0.5)", lineHeight: 1,
              fontVariantNumeric: "tabular-nums", transition: "color 300ms",
            }}>--</span>
          </div>
          {/* Health bar */}
          <div style={{
            height: 3, borderRadius: 2, background: "rgba(255,255,255,0.04)",
            marginTop: 6, overflow: "hidden",
          }}>
            <div ref={headerBarRef} style={{
              height: "100%", borderRadius: 2, width: "0%",
              background: "rgba(255,255,255,0.3)", transition: "width 400ms ease, background 400ms",
            }} />
          </div>
        </div>

        {/* Sensor cards with sparklines */}
        {sensorKeys.map((key) => (
          <TelemetrySensorCard
            key={`${selected ?? "overview"}-${key}`}
            sensorKey={key}
          />
        ))}
      </div>
    </div>
  );
}
