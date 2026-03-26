import React from "react";

interface AccordSideProfileProps {
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Side profile wireframe of the 2026 Honda Accord SE (11th gen).
 * White strokes on transparent background for OLED HUD display.
 *
 * Key silhouette features of the 11th gen Accord:
 *   - Fastback-style sloping roofline from B-pillar
 *   - Beltline kicks up at C-pillar
 *   - Slim angular headlights wrapping around fenders
 *   - Full-width thin LED taillight strip
 *   - Hexagonal/trapezoidal grille
 *   - 19-inch multi-spoke wheels
 */
export function AccordSideProfile({
  className,
  style,
}: AccordSideProfileProps): React.JSX.Element {
  const body = "rgba(255,255,255,0.30)";
  const glass = "rgba(255,255,255,0.20)";
  const detail = "rgba(255,255,255,0.15)";
  const accent = "rgba(255,255,255,0.35)";

  // Wheel centres: front ~96, rear ~368. Ground line y=130.
  const frontWheelCx = 96;
  const rearWheelCx = 368;
  const wheelCy = 126;
  const wheelR = 20;
  const tireR = 24;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 480 160"
      className={className}
      style={style}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* ---------- BODY LOWER OUTLINE ---------- */}
      {/*
        Traces the lower body from front bumper under the car to rear bumper.
        Wheel arches are cut out.
      */}
      <path
        d={[
          // Front bumper lower
          "M 26,112",
          "L 20,116",
          "Q 16,120 18,126",
          "L 24,132",

          // Rocker panel to front wheel arch
          "L 62,134",

          // Front wheel arch
          "Q 66,118 78,110",
          "Q 88,104 96,104",
          "Q 104,104 114,110",
          "Q 126,118 130,134",

          // Rocker panel between wheels
          "L 334,134",

          // Rear wheel arch
          "Q 338,118 350,110",
          "Q 360,104 368,104",
          "Q 376,104 386,110",
          "Q 398,118 402,134",

          // Rear bumper lower
          "L 448,134",
          "L 456,130",
          "Q 460,126 460,120",
          "L 458,114",
        ].join(" ")}
        stroke={body}
        strokeWidth={1.5}
      />

      {/* ---------- BODY UPPER OUTLINE ---------- */}
      {/*
        Front bumper top -> hood -> windshield -> roof -> rear glass -> trunk -> tail
      */}
      <path
        d={[
          // Front bumper / fascia top edge
          "M 26,112",
          "L 22,106",
          "Q 20,100 24,94",

          // Hood line -- long and low, slight upward slope
          "L 42,88",
          "L 80,82",
          "L 130,78",
          "L 148,76",

          // A-pillar -- windshield rake
          "L 162,56",
          "Q 164,50 168,46",

          // Roofline -- subtle crown, starts to descend at B-pillar
          "L 196,38",
          "Q 220,34 248,33",
          "Q 276,34 300,38",

          // C-pillar -- fastback slope, the signature 11th gen curve
          "L 340,48",
          "Q 360,56 378,68",

          // Trunk lid / deck
          "L 400,82",
          "L 430,92",

          // Rear fascia
          "L 444,98",
          "Q 456,104 458,114",
        ].join(" ")}
        stroke={body}
        strokeWidth={1.5}
      />

      {/* ---------- HEADLIGHT ---------- */}
      {/* Slim angular headlight wrapping around fender */}
      <path
        d="M 42,88 L 28,92 Q 22,96 24,94"
        stroke={accent}
        strokeWidth={1.3}
      />
      {/* DRL / inner detail */}
      <path
        d="M 46,87 L 34,90 Q 28,92 26,94"
        stroke={accent}
        strokeWidth={0.7}
      />
      {/* Lower headlight edge */}
      <path
        d="M 40,90 L 30,96 Q 26,100 26,104"
        stroke={detail}
        strokeWidth={0.7}
      />

      {/* ---------- FRONT GRILLE ---------- */}
      {/* Trapezoidal grille shape */}
      <path
        d="M 26,96 L 24,100 Q 22,104 24,108 L 26,112"
        stroke={detail}
        strokeWidth={1.0}
      />
      {/* Grille horizontal slats */}
      <line x1="24" y1="100" x2="26" y2="100" stroke={detail} strokeWidth={0.5} />
      <line x1="23" y1="104" x2="26" y2="104" stroke={detail} strokeWidth={0.5} />
      <line x1="24" y1="108" x2="26" y2="108" stroke={detail} strokeWidth={0.5} />

      {/* Front bumper intake */}
      <path
        d="M 28,118 Q 40,122 60,122"
        stroke={detail}
        strokeWidth={0.6}
      />

      {/* ---------- TAILLIGHT ---------- */}
      {/* Full-width LED strip -- from side view it's a thin bright accent */}
      <path
        d="M 430,92 L 444,96 Q 452,100 456,106"
        stroke={accent}
        strokeWidth={1.6}
      />
      {/* Inner LED detail */}
      <path
        d="M 434,94 L 446,98 Q 450,100 452,104"
        stroke={accent}
        strokeWidth={0.7}
      />
      {/* Reflector / lower tail */}
      <path
        d="M 448,110 L 456,112"
        stroke={detail}
        strokeWidth={0.6}
      />

      {/* ---------- WINDSHIELD (front glass) ---------- */}
      <path
        d={[
          "M 148,76",
          "L 162,56",
          "Q 164,50 168,46",
        ].join(" ")}
        stroke={glass}
        strokeWidth={1.2}
      />

      {/* ---------- REAR GLASS ---------- */}
      <path
        d={[
          "M 340,48",
          "Q 360,56 378,68",
          "L 400,82",
        ].join(" ")}
        stroke={glass}
        strokeWidth={1.2}
      />

      {/* ---------- ROOF (chrome trim line) ---------- */}
      <path
        d={[
          "M 168,46",
          "L 196,38",
          "Q 220,34 248,33",
          "Q 276,34 300,38",
          "L 340,48",
        ].join(" ")}
        stroke={detail}
        strokeWidth={0.6}
      />

      {/* ---------- A-PILLAR ---------- */}
      <line
        x1="162" y1="56" x2="150" y2="76"
        stroke={body}
        strokeWidth={1.8}
      />

      {/* ---------- B-PILLAR ---------- */}
      <line
        x1="240" y1="36" x2="236" y2="82"
        stroke={body}
        strokeWidth={2.0}
      />

      {/* ---------- C-PILLAR (fastback) ---------- */}
      <path
        d="M 310,38 Q 336,50 360,66 L 380,80"
        stroke={body}
        strokeWidth={1.6}
      />

      {/* ---------- WINDOWS ---------- */}
      {/* Front window */}
      <path
        d={[
          "M 154,74",
          "L 164,54",
          "Q 166,48 170,46",
          "L 232,36",
          "L 234,80",
          "Z",
        ].join(" ")}
        stroke={glass}
        strokeWidth={0.8}
      />

      {/* Rear window */}
      <path
        d={[
          "M 242,80",
          "L 244,36",
          "L 306,40",
          "Q 330,50 350,62",
          "L 370,76",
          "L 290,82",
          "Z",
        ].join(" ")}
        stroke={glass}
        strokeWidth={0.8}
      />

      {/* Quarter window (small triangle behind C-pillar on some trims) */}
      <path
        d="M 354,64 L 374,76 L 382,80 L 370,74 Z"
        stroke={glass}
        strokeWidth={0.5}
      />

      {/* ---------- BELTLINE ---------- */}
      {/* Distinctive upward kick at C-pillar */}
      <path
        d={[
          "M 42,88",
          "L 130,80",
          "L 150,78",
          "L 234,82",
          "L 290,82",
          "L 340,80",
          "Q 370,78 400,82",
          "L 430,92",
        ].join(" ")}
        stroke={body}
        strokeWidth={0.9}
      />

      {/* ---------- DOOR LINE ---------- */}
      {/* Front door shut line */}
      <line
        x1="236" y1="82" x2="236" y2="130"
        stroke={detail}
        strokeWidth={0.6}
      />
      {/* Rear door shut line */}
      <line
        x1="330" y1="82" x2="334" y2="130"
        stroke={detail}
        strokeWidth={0.6}
      />

      {/* ---------- DOOR HANDLES ---------- */}
      {/* Front door handle */}
      <line
        x1="214" y1="82" x2="228" y2="82"
        stroke={detail}
        strokeWidth={1.2}
      />
      {/* Rear door handle */}
      <line
        x1="308" y1="82" x2="322" y2="82"
        stroke={detail}
        strokeWidth={1.2}
      />

      {/* ---------- SIDE MIRROR ---------- */}
      <path
        d="M 148,74 L 140,70 L 136,74 L 144,76"
        stroke={body}
        strokeWidth={0.8}
      />

      {/* ---------- HOOD CREASE ---------- */}
      <path
        d="M 80,84 L 130,80"
        stroke={detail}
        strokeWidth={0.4}
      />

      {/* ---------- LOWER BODY CREASE ---------- */}
      <path
        d="M 60,120 L 130,118 L 334,118 L 402,120"
        stroke={detail}
        strokeWidth={0.4}
      />

      {/* ---------- FRONT WHEEL ---------- */}
      {/* Tire */}
      <circle
        cx={frontWheelCx}
        cy={wheelCy}
        r={tireR}
        stroke={body}
        strokeWidth={1.2}
      />
      {/* Rim */}
      <circle
        cx={frontWheelCx}
        cy={wheelCy}
        r={wheelR}
        stroke={body}
        strokeWidth={0.8}
      />
      {/* Hub */}
      <circle
        cx={frontWheelCx}
        cy={wheelCy}
        r={4}
        stroke={detail}
        strokeWidth={0.6}
      />
      {/* Multi-spoke pattern (10 spokes) */}
      {Array.from({ length: 10 }).map((_, i) => {
        const angle = (i * 36 * Math.PI) / 180;
        const innerR = 5;
        const outerR = wheelR - 1;
        return (
          <line
            key={`fw-spoke-${i}`}
            x1={frontWheelCx + innerR * Math.cos(angle)}
            y1={wheelCy + innerR * Math.sin(angle)}
            x2={frontWheelCx + outerR * Math.cos(angle)}
            y2={wheelCy + outerR * Math.sin(angle)}
            stroke={detail}
            strokeWidth={0.5}
          />
        );
      })}

      {/* ---------- REAR WHEEL ---------- */}
      {/* Tire */}
      <circle
        cx={rearWheelCx}
        cy={wheelCy}
        r={tireR}
        stroke={body}
        strokeWidth={1.2}
      />
      {/* Rim */}
      <circle
        cx={rearWheelCx}
        cy={wheelCy}
        r={wheelR}
        stroke={body}
        strokeWidth={0.8}
      />
      {/* Hub */}
      <circle
        cx={rearWheelCx}
        cy={wheelCy}
        r={4}
        stroke={detail}
        strokeWidth={0.6}
      />
      {/* Multi-spoke pattern (10 spokes) */}
      {Array.from({ length: 10 }).map((_, i) => {
        const angle = (i * 36 * Math.PI) / 180;
        const innerR = 5;
        const outerR = wheelR - 1;
        return (
          <line
            key={`rw-spoke-${i}`}
            x1={rearWheelCx + innerR * Math.cos(angle)}
            y1={wheelCy + innerR * Math.sin(angle)}
            x2={rearWheelCx + outerR * Math.cos(angle)}
            y2={wheelCy + outerR * Math.sin(angle)}
            stroke={detail}
            strokeWidth={0.5}
          />
        );
      })}

      {/* ---------- GROUND SHADOW (subtle) ---------- */}
      <line
        x1="60" y1="150" x2="410" y2="150"
        stroke="rgba(255,255,255,0.06)"
        strokeWidth={1.0}
      />
    </svg>
  );
}
