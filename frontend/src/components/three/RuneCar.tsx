import { useEffect, useMemo, useRef } from "react";
import { useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useThemeStore, getActiveTheme } from "@/stores/themeStore";
import { useVehicleStore } from "@/stores/vehicleStore";
import { useUiStore } from "@/stores/uiStore";
import { ZONE_TO_SUBSYSTEM } from "@/constants/zones";
import type { SubsystemId, HealthScores } from "@/types/vehicle";

const EDGE_ANGLE_THRESHOLD = 12;
const LERP_SPEED = 0.05;

interface ZoneEntry {
  subsystem: SubsystemId;
  edgeMaterial: THREE.LineBasicMaterial;
  fillMaterial: THREE.MeshBasicMaterial;
}

function healthToColor(
  score: number,
  primaryHex: number,
  warnHex: number,
  criticalHex: number,
  dimHex: number,
): THREE.Color {
  if (score === -1) return new THREE.Color(dimHex);
  if (score >= 80) return new THREE.Color(primaryHex);
  if (score >= 60) {
    const t = (80 - score) / 20;
    return new THREE.Color(primaryHex).lerp(new THREE.Color(warnHex), t);
  }
  const t = (60 - score) / 60;
  return new THREE.Color(warnHex).lerp(new THREE.Color(criticalHex), t);
}

export function RuneCar() {
  const { scene } = useGLTF("/models/rune_sedan.glb");
  const groupRef = useRef<THREE.Group>(null);
  const zonesRef = useRef<Map<string, ZoneEntry>>(new Map());
  const bodyEdgesRef = useRef<THREE.LineBasicMaterial[]>([]);
  const bodyFillsRef = useRef<THREE.MeshBasicMaterial[]>([]);
  const prevThemeIdRef = useRef<string>("");

  const carModel = useMemo(() => {
    const model = scene.clone(true);
    const box = new THREE.Box3().setFromObject(model);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    model.position.sub(center);
    model.position.y += size.y / 2;
    return model;
  }, [scene]);

  useEffect(() => {
    const group = groupRef.current;
    if (!group) return;

    const theme = getActiveTheme();
    const zones = new Map<string, ZoneEntry>();
    const bodyEdges: THREE.LineBasicMaterial[] = [];
    const bodyFills: THREE.MeshBasicMaterial[] = [];

    carModel.updateMatrixWorld(true);

    const meshes: THREE.Mesh[] = [];
    carModel.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        meshes.push(child as THREE.Mesh);
      }
    });

    for (const mesh of meshes) {
      const subsystem = ZONE_TO_SUBSYSTEM[mesh.name];
      const isZone = subsystem !== undefined;

      const edges = new THREE.EdgesGeometry(mesh.geometry, EDGE_ANGLE_THRESHOLD);
      const edgeMat = new THREE.LineBasicMaterial({
        color: isZone ? theme.primaryHex : theme.primaryHex,
        transparent: true,
        opacity: isZone ? 0.85 : 0.55,
      });
      const lineSegments = new THREE.LineSegments(edges, edgeMat);
      mesh.add(lineSegments);

      const fillMat = new THREE.MeshBasicMaterial({
        color: theme.bgHex,
        transparent: true,
        opacity: isZone ? 0.15 : 0.08,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      mesh.material = fillMat;

      if (isZone) {
        zones.set(mesh.name, { subsystem, edgeMaterial: edgeMat, fillMaterial: fillMat });
      } else {
        bodyEdges.push(edgeMat);
        bodyFills.push(fillMat);
      }
    }

    zonesRef.current = zones;
    bodyEdgesRef.current = bodyEdges;
    bodyFillsRef.current = bodyFills;
    group.add(carModel);

    return () => {
      group.remove(carModel);
    };
  }, [carModel]);

  useFrame(() => {
    const theme = getActiveTheme();
    const themeId = useThemeStore.getState().activeThemeId;
    const health: HealthScores = useVehicleStore.getState().health;
    const focused = useUiStore.getState().focusedSubsystem;
    const themeChanged = themeId !== prevThemeIdRef.current;
    prevThemeIdRef.current = themeId;

    const time = performance.now() * 0.001;

    // Update zone materials based on health
    for (const [, zone] of zonesRef.current) {
      const score = health[zone.subsystem];
      const targetColor = healthToColor(
        score,
        theme.primaryHex,
        theme.warnHex,
        theme.criticalHex,
        theme.dimHex,
      );

      if (themeChanged) {
        zone.edgeMaterial.color.copy(targetColor);
      } else {
        zone.edgeMaterial.color.lerp(targetColor, LERP_SPEED);
      }

      // Pulse when health is low
      let targetOpacity = 0.85;
      if (score !== -1 && score < 70) {
        const pulse = 0.5 + 0.5 * Math.sin(time * 3);
        targetOpacity = 0.5 + pulse * 0.5;
      }

      // Dim unfocused zones when one is focused
      if (focused !== null && focused !== zone.subsystem) {
        targetOpacity = 0.12;
      }

      zone.edgeMaterial.opacity += (targetOpacity - zone.edgeMaterial.opacity) * LERP_SPEED;
      zone.fillMaterial.opacity += ((focused === zone.subsystem ? 0.25 : 0.15) - zone.fillMaterial.opacity) * LERP_SPEED;
    }

    // Update body (non-zone) materials on theme change
    if (themeChanged) {
      for (const mat of bodyEdgesRef.current) {
        mat.color.setHex(theme.primaryHex);
      }
    }

    // Dim body when a zone is focused
    const bodyTargetOpacity = focused !== null ? 0.15 : 0.55;
    for (const mat of bodyEdgesRef.current) {
      mat.opacity += (bodyTargetOpacity - mat.opacity) * LERP_SPEED;
    }
  });

  return <group ref={groupRef} />;
}

useGLTF.preload("/models/rune_sedan.glb");
