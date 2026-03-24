import { useEffect, useRef, useState, useCallback } from "react";
import type { SubsystemId } from "@/types/vehicle";
import { SUBSYSTEM_LABELS } from "@/constants/zones";

interface LineRevealProps {
  onComplete: () => void;
}

// Zone label positions (relative %, matching the car SVG layout).
// These approximate where each subsystem sits on the top-down car silhouette.
const ZONE_POSITIONS: { id: SubsystemId; x: number; y: number }[] = [
  { id: "engine", x: 58, y: 22 },
  { id: "transmission", x: 38, y: 22 },
  { id: "cooling", x: 48, y: 28 },
  { id: "fuel", x: 48, y: 72 },
  { id: "exhaust", x: 62, y: 55 },
  { id: "electrical", x: 36, y: 30 },
];

const LINE_DRAW_DURATION = 2000; // ms
const LABEL_STAGGER = 200; // ms between each label appearing

export function LineReveal({ onComplete }: LineRevealProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [visibleLabels, setVisibleLabels] = useState<number>(0);
  const completedRef = useRef(false);

  const handleComplete = useCallback(() => {
    if (!completedRef.current) {
      completedRef.current = true;
      onComplete();
    }
  }, [onComplete]);

  // Animate the SVG stroke-dashoffset to "draw" the car outline
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;

    const paths = svg.querySelectorAll<SVGPathElement>("path, line, circle, rect, ellipse, polyline, polygon");
    let totalLength = 0;

    // Measure and set up each path for reveal
    paths.forEach((path) => {
      const len = path.getTotalLength?.() ?? 0;
      totalLength += len;
      path.style.strokeDasharray = `${len}`;
      path.style.strokeDashoffset = `${len}`;
      path.style.transition = `stroke-dashoffset ${LINE_DRAW_DURATION}ms cubic-bezier(0.4, 0, 0.2, 1)`;
    });

    // Trigger the draw animation next frame
    requestAnimationFrame(() => {
      paths.forEach((path) => {
        path.style.strokeDashoffset = "0";
      });
    });

    // After line draw completes, start showing zone labels
    let labelInterval: ReturnType<typeof setInterval>;
    const labelTimer = setTimeout(() => {
      let count = 0;
      labelInterval = setInterval(() => {
        count++;
        setVisibleLabels(count);
        if (count >= ZONE_POSITIONS.length) {
          clearInterval(labelInterval);
          setTimeout(handleComplete, 400);
        }
      }, LABEL_STAGGER);
    }, LINE_DRAW_DURATION);

    return () => {
      clearTimeout(labelTimer);
      clearInterval(labelInterval);
    };
  }, [handleComplete]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "#000",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 999,
      }}
    >
      <div
        style={{
          position: "relative",
          width: "65%",
          maxWidth: "600px",
          aspectRatio: "2 / 1",
        }}
      >
        {/* Car SVG placeholder -- the actual car SVG paths go here.
            This uses a simplified Accord silhouette for the line-draw effect.
            The real CarView SVG will be swapped in by the car agent. */}
        <svg
          ref={svgRef}
          viewBox="0 0 400 200"
          width="100%"
          height="100%"
          fill="none"
          stroke="#fff"
          strokeWidth="1"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {/* Top-down car outline -- simplified Honda Accord SE silhouette */}
          <path
            d="M140,20 C160,12 240,12 260,20 L280,35 C290,42 295,55 295,70 L295,130 C295,145 290,158 280,165 L260,180 C240,188 160,188 140,180 L120,165 C110,158 105,145 105,130 L105,70 C105,55 110,42 120,35 Z"
            opacity="0.9"
          />
          {/* Windshield */}
          <path
            d="M150,52 L160,40 C175,35 225,35 240,40 L250,52 Z"
            opacity="0.4"
          />
          {/* Rear window */}
          <path
            d="M155,150 L162,160 C178,165 222,165 238,160 L245,150 Z"
            opacity="0.4"
          />
          {/* Hood line */}
          <line x1="140" y1="52" x2="260" y2="52" opacity="0.3" />
          {/* Trunk line */}
          <line x1="145" y1="150" x2="255" y2="150" opacity="0.3" />
          {/* Center line */}
          <line x1="200" y1="35" x2="200" y2="170" opacity="0.08" strokeDasharray="4 4" />
          {/* Wheels */}
          <ellipse cx="125" cy="55" rx="12" ry="8" opacity="0.5" />
          <ellipse cx="275" cy="55" rx="12" ry="8" opacity="0.5" />
          <ellipse cx="125" cy="148" rx="12" ry="8" opacity="0.5" />
          <ellipse cx="275" cy="148" rx="12" ry="8" opacity="0.5" />
        </svg>

        {/* Zone labels, staggered appearance */}
        {ZONE_POSITIONS.map((zone, i) => (
          <span
            key={zone.id}
            style={{
              position: "absolute",
              left: `${zone.x}%`,
              top: `${zone.y}%`,
              transform: "translate(-50%, -50%)",
              fontFamily: "var(--font-data)",
              fontSize: "9px",
              letterSpacing: "0.1em",
              color: "var(--rune-text-muted)",
              textTransform: "uppercase",
              opacity: i < visibleLabels ? 0.5 : 0,
              transition: "opacity 0.4s ease-out",
              pointerEvents: "none",
              whiteSpace: "nowrap",
            }}
          >
            {SUBSYSTEM_LABELS[zone.id]}
          </span>
        ))}
      </div>
    </div>
  );
}
