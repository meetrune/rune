import { useRef, useEffect, useState } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";

interface HeartbeatPoint {
  x: number;
  y: number;
}

const BUFFER_SIZE = 100;
const MAX_HEIGHT = 40;

// Ring buffer for driving intensity values
class RingBuffer {
  private data: number[];
  private head: number = 0;
  private count: number = 0;

  constructor(private capacity: number) {
    this.data = new Array(capacity).fill(0);
  }

  push(value: number): void {
    this.data[this.head] = value;
    this.head = (this.head + 1) % this.capacity;
    if (this.count < this.capacity) this.count++;
  }

  // Returns values in insertion order (oldest first)
  toArray(): number[] {
    if (this.count < this.capacity) {
      return this.data.slice(0, this.count);
    }
    return [...this.data.slice(this.head), ...this.data.slice(0, this.head)];
  }

  get length(): number {
    return this.count;
  }
}

export function useHeartbeat(): HeartbeatPoint[] {
  const bufferRef = useRef(new RingBuffer(BUFFER_SIZE));
  const prevThrottleRef = useRef<number | null>(null);
  const prevSpeedRef = useRef<number | null>(null);
  const [points, setPoints] = useState<HeartbeatPoint[]>([]);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const throttle = state.sensors.THROTTLE_POS?.v ?? null;
      const speed = state.sensors.SPEED?.v ?? null;

      if (throttle === null && speed === null) return;

      const throttleDelta =
        prevThrottleRef.current !== null && throttle !== null
          ? Math.abs(throttle - prevThrottleRef.current)
          : 0;

      const speedDelta =
        prevSpeedRef.current !== null && speed !== null
          ? Math.abs(speed - prevSpeedRef.current)
          : 0;

      prevThrottleRef.current = throttle;
      prevSpeedRef.current = speed;

      // Driving intensity: throttle responsiveness + speed changes
      const intensity = throttleDelta + speedDelta * 0.5;
      bufferRef.current.push(intensity);

      // Convert buffer to SVG points
      const values = bufferRef.current.toArray();
      if (values.length < 2) return;

      // Normalize: find max in buffer, scale to fit height
      const max = Math.max(...values, 1);
      const newPoints: HeartbeatPoint[] = values.map((v, i) => ({
        x: (i / (values.length - 1)) * 100,
        y: MAX_HEIGHT - (v / max) * (MAX_HEIGHT - 4),
      }));

      setPoints(newPoints);
    });

    return unsub;
  }, []);

  return points;
}
