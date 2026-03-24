import type { SubsystemId } from "./vehicle";

// SVG zone position as percentage of the car SVG viewBox
export interface ZonePosition {
  x: number;       // % from left
  y: number;       // % from top
  width: number;   // % width
  height: number;  // % height
  labelX: number;  // label anchor X %
  labelY: number;  // label anchor Y %
}

export interface ZoneConfig {
  subsystem: SubsystemId;
  label: string;
  topDown: ZonePosition;
  sideProfile: ZonePosition;
}
