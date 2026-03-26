import { useRef, useEffect } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";

const BUFFER_SIZE = 100;
const HEIGHT = 40;
const LABEL_WIDTH = 40;

// Ring buffer inlined here to avoid hook overhead --
// this component updates the SVG polyline imperatively.
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

export function TripHeartbeat() {
  const polylineRef = useRef<SVGPolylineElement>(null);
  const bufferRef = useRef(new RingBuffer(BUFFER_SIZE));
  const prevThrottleRef = useRef<number | null>(null);
  const prevSpeedRef = useRef<number | null>(null);

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

      const intensity = throttleDelta + speedDelta * 0.5;
      bufferRef.current.push(intensity);

      // Build polyline points string imperatively
      const values = bufferRef.current.toArray();
      if (values.length < 2 || !polylineRef.current) return;

      const max = Math.max(...values, 1);
      const pointsStr = values
        .map((v, i) => {
          const x = (i / (BUFFER_SIZE - 1)) * 100;
          const y = HEIGHT - (v / max) * (HEIGHT - 4);
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ");

      polylineRef.current.setAttribute("points", pointsStr);
    });

    return unsub;
  }, []);

  return (
    <div style={styles.container}>
      <span style={styles.label}>TRIP</span>
      <svg
        viewBox={`0 0 100 ${HEIGHT}`}
        preserveAspectRatio="none"
        style={styles.svg}
      >
        <polyline
          ref={polylineRef}
          fill="none"
          stroke="rgba(255, 255, 255, 0.07)"
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          points=""
        />
      </svg>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "row" as const,
    alignItems: "center",
    width: "100%",
    height: `${HEIGHT}px`,
    gap: "8px",
    padding: "0 4px",
  },
  label: {
    fontSize: "10px",
    fontWeight: 500,
    letterSpacing: "0.08em",
    textTransform: "uppercase" as const,
    color: "var(--rune-label)",
    fontFamily: "Inter, system-ui, sans-serif",
    flexShrink: 0,
    width: `${LABEL_WIDTH}px`,
  },
  svg: {
    flex: 1,
    height: "100%",
    overflow: "visible" as const,
  },
} as const;
