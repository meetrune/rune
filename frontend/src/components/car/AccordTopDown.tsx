import React from "react";

interface AccordTopDownProps {
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Top-down wireframe of the 2026 Honda Accord SE (11th gen).
 * White strokes on transparent background for OLED HUD display.
 *
 * Proportions based on 11th gen Accord:
 *   Overall ~4971mm L x ~1862mm W, wheelbase ~2830mm
 *   Hood ~30%, cabin ~40%, trunk ~30% of length
 *   Wheels at ~20% and ~75% from front
 */
export function AccordTopDown({
  className,
  style,
}: AccordTopDownProps): React.JSX.Element {
  // Opacity tokens
  const body = "rgba(255,255,255,0.30)";
  const glass = "rgba(255,255,255,0.20)";
  const detail = "rgba(255,255,255,0.15)";
  const accent = "rgba(255,255,255,0.35)";

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 400 180"
      className={className}
      style={style}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* ---------- BODY OUTLINE ---------- */}
      {/*
        The outline traces the full perimeter of the car from above.
        Front is left, rear is right. Centred vertically at y=90.
        Width of body ~110 units (y 35-145), length ~360 units (x 20-380).
      */}
      <path
        d={[
          // Front bumper -- subtle trapezoidal nose
          "M 56,52",
          "L 38,58",
          "Q 24,64 22,74",
          "L 20,90",
          "Q 22,106 24,106",
          "L 38,122",
          "L 56,128",

          // Driver side (bottom in SVG) -- slight fender flare at front wheel
          "L 72,130",
          "Q 80,132 88,132",   // front wheel arch flare
          "L 100,131",
          "Q 108,130 112,129",

          // Beltline runs along driver side
          "L 180,128",
          "L 260,129",

          // Rear wheel arch flare
          "Q 280,131 292,132",
          "L 310,132",
          "Q 318,131 324,129",

          // Rear quarter -- fastback taper
          "L 352,124",
          "L 368,116",
          "Q 378,108 380,100",
          "L 380,90",

          // Passenger side (top in SVG) -- mirror of driver side
          "L 380,80",
          "Q 378,72 368,64",
          "L 352,56",
          "L 324,51",
          "Q 318,49 310,48",
          "L 292,48",
          "Q 280,49 260,51",
          "L 180,52",
          "L 112,51",
          "Q 108,50 100,49",
          "L 88,48",
          "Q 80,48 72,50",
          "L 56,52",
          "Z",
        ].join(" ")}
        stroke={body}
        strokeWidth={1.6}
      />

      {/* ---------- HEADLIGHTS (C-shaped DRL wrap) ---------- */}
      {/* Passenger side headlight */}
      <path
        d="M 52,54 Q 40,58 36,62 L 30,70 Q 28,74 30,76"
        stroke={accent}
        strokeWidth={1.4}
      />
      {/* Inner C curve */}
      <path
        d="M 48,56 Q 42,60 39,64 L 35,70"
        stroke={accent}
        strokeWidth={0.8}
      />
      {/* Driver side headlight */}
      <path
        d="M 52,126 Q 40,122 36,118 L 30,110 Q 28,106 30,104"
        stroke={accent}
        strokeWidth={1.4}
      />
      <path
        d="M 48,124 Q 42,120 39,116 L 35,110"
        stroke={accent}
        strokeWidth={0.8}
      />

      {/* ---------- FRONT GRILLE (trapezoidal) ---------- */}
      <path
        d="M 30,76 L 24,82 L 22,90 L 24,98 L 30,104"
        stroke={detail}
        strokeWidth={0.8}
      />
      {/* Grille horizontal bars */}
      <line x1="26" y1="84" x2="28" y2="84" stroke={detail} strokeWidth={0.5} />
      <line x1="24" y1="90" x2="26" y2="90" stroke={detail} strokeWidth={0.5} />
      <line x1="26" y1="96" x2="28" y2="96" stroke={detail} strokeWidth={0.5} />

      {/* ---------- TAILLIGHTS (full-width LED bar) ---------- */}
      {/* The 11th gen Accord has a distinctive thin light bar spanning the trunk */}
      <path
        d="M 352,56 Q 366,62 372,68 L 376,76"
        stroke={accent}
        strokeWidth={1.4}
      />
      <path
        d="M 352,124 Q 366,118 372,112 L 376,104"
        stroke={accent}
        strokeWidth={1.4}
      />
      {/* Connecting bar across trunk */}
      <path
        d="M 376,76 Q 380,84 380,90 Q 380,96 376,104"
        stroke={accent}
        strokeWidth={1.2}
      />
      {/* Inner LED strip detail */}
      <path
        d="M 370,72 Q 376,82 376,90 Q 376,98 370,108"
        stroke={detail}
        strokeWidth={0.6}
      />

      {/* ---------- WINDSHIELD (front) ---------- */}
      <path
        d="M 108,58 Q 112,56 128,55 L 200,54 L 272,55 Q 288,56 292,58"
        stroke={glass}
        strokeWidth={0}
      />
      <path
        d={[
          "M 102,60",
          "L 120,58",
          "Q 160,55 200,54",
          "Q 240,55 280,58",
          "L 298,60",
        ].join(" ")}
        stroke={glass}
        strokeWidth={1.2}
      />
      {/* Windshield rear edge (A-pillar line) */}
      <path
        d={[
          "M 102,60",
          "L 108,120",
        ].join(" ")}
        stroke={glass}
        strokeWidth={0.8}
      />
      <path
        d={[
          "M 298,60",
          "L 292,120",
        ].join(" ")}
        stroke={glass}
        strokeWidth={0.8}
      />
      {/* Windshield bottom edge */}
      <path
        d={[
          "M 108,120",
          "L 120,122",
          "Q 160,125 200,126",
          "Q 240,125 280,122",
          "L 292,120",
        ].join(" ")}
        stroke={glass}
        strokeWidth={1.2}
      />

      {/* ---------- ROOF OUTLINE ---------- */}
      <path
        d={[
          "M 120,62",
          "Q 160,59 200,58",
          "Q 240,59 280,62",
          "L 330,68",
          "Q 345,74 348,82",
          "L 348,90",
          "L 348,98",
          "Q 345,106 330,112",
          "L 280,118",
          "Q 240,121 200,122",
          "Q 160,121 120,118",
          "L 120,62",
          "Z",
        ].join(" ")}
        stroke={body}
        strokeWidth={1.0}
      />

      {/* ---------- REAR WINDSHIELD ---------- */}
      <path
        d={[
          "M 290,66",
          "Q 310,70 324,74",
          "L 336,80",
        ].join(" ")}
        stroke={glass}
        strokeWidth={1.0}
      />
      <path
        d={[
          "M 290,114",
          "Q 310,110 324,106",
          "L 336,100",
        ].join(" ")}
        stroke={glass}
        strokeWidth={1.0}
      />
      {/* Rear glass horizontal */}
      <path
        d="M 336,80 Q 340,86 340,90 Q 340,94 336,100"
        stroke={glass}
        strokeWidth={1.0}
      />

      {/* ---------- SIDE WINDOWS ---------- */}
      {/* Passenger side -- front window */}
      <path
        d="M 124,62 L 186,59 L 186,62 L 126,64"
        stroke={glass}
        strokeWidth={0.7}
      />
      {/* Passenger side -- rear window */}
      <path
        d="M 190,59 L 276,62 Q 286,64 290,66 L 190,62"
        stroke={glass}
        strokeWidth={0.7}
      />
      {/* Driver side -- front window */}
      <path
        d="M 124,118 L 186,121 L 186,118 L 126,116"
        stroke={glass}
        strokeWidth={0.7}
      />
      {/* Driver side -- rear window */}
      <path
        d="M 190,121 L 276,118 Q 286,116 290,114 L 190,118"
        stroke={glass}
        strokeWidth={0.7}
      />

      {/* ---------- B-PILLAR ---------- */}
      <line
        x1="186" y1="59" x2="186" y2="62"
        stroke={detail}
        strokeWidth={1.4}
      />
      <line
        x1="186" y1="118" x2="186" y2="121"
        stroke={detail}
        strokeWidth={1.4}
      />

      {/* ---------- SIDE MIRRORS ---------- */}
      {/* Passenger */}
      <path
        d="M 110,46 L 104,40 L 98,42 L 104,48"
        stroke={body}
        strokeWidth={0.8}
      />
      {/* Driver */}
      <path
        d="M 110,134 L 104,140 L 98,138 L 104,132"
        stroke={body}
        strokeWidth={0.8}
      />

      {/* ---------- WHEELS ---------- */}
      {/* Front passenger */}
      <ellipse
        cx="80" cy="46"
        rx="16" ry="5"
        stroke={body}
        strokeWidth={1.0}
      />
      <ellipse
        cx="80" cy="46"
        rx="11" ry="3.5"
        stroke={detail}
        strokeWidth={0.5}
      />

      {/* Front driver */}
      <ellipse
        cx="80" cy="134"
        rx="16" ry="5"
        stroke={body}
        strokeWidth={1.0}
      />
      <ellipse
        cx="80" cy="134"
        rx="11" ry="3.5"
        stroke={detail}
        strokeWidth={0.5}
      />

      {/* Rear passenger */}
      <ellipse
        cx="300" cy="46"
        rx="16" ry="5"
        stroke={body}
        strokeWidth={1.0}
      />
      <ellipse
        cx="300" cy="46"
        rx="11" ry="3.5"
        stroke={detail}
        strokeWidth={0.5}
      />

      {/* Rear driver */}
      <ellipse
        cx="300" cy="134"
        rx="16" ry="5"
        stroke={body}
        strokeWidth={1.0}
      />
      <ellipse
        cx="300" cy="134"
        rx="11" ry="3.5"
        stroke={detail}
        strokeWidth={0.5}
      />

      {/* ---------- BODY CREASE LINES ---------- */}
      {/* Shoulder line -- passenger side */}
      <path
        d="M 60,53 L 180,51 L 320,50 L 354,56"
        stroke={detail}
        strokeWidth={0.5}
      />
      {/* Shoulder line -- driver side */}
      <path
        d="M 60,127 L 180,129 L 320,130 L 354,124"
        stroke={detail}
        strokeWidth={0.5}
      />

      {/* Center hood line */}
      <line
        x1="30" y1="90" x2="108" y2="90"
        stroke={detail}
        strokeWidth={0.4}
      />
      {/* Center trunk line */}
      <line
        x1="340" y1="90" x2="376" y2="90"
        stroke={detail}
        strokeWidth={0.4}
      />
    </svg>
  );
}
