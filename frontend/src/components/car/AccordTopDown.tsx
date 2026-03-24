import type { CSSProperties } from "react";

interface AccordTopDownProps {
  className?: string;
  style?: CSSProperties;
}

// 2026 Honda Accord SE (11th gen) top-down wireframe.
// Proportions: 4975mm L x 1862mm W, wheelbase 2830mm.
// viewBox 500x188 maintains the 2.67:1 length-to-width ratio.
export function AccordTopDown({ className, style }: AccordTopDownProps) {
  return (
    <svg
      viewBox="0 0 500 188"
      className={className}
      style={style}
      xmlns="http://www.w3.org/2000/svg"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    >
      {/* Body outline -- the main silhouette */}
      <path
        d="
          M 60,30
          Q 30,30 20,50
          L 12,70
          Q 8,80 8,94
          Q 8,108 12,118
          L 20,138
          Q 30,158 60,158
          L 400,158
          Q 440,158 460,145
          L 480,130
          Q 492,120 492,94
          Q 492,68 480,58
          L 460,43
          Q 440,30 400,30
          Z
        "
        stroke="rgba(255,255,255,0.30)"
        strokeWidth="1.5"
      />

      {/* Hood panel line */}
      <line x1="140" y1="38" x2="140" y2="150" stroke="rgba(255,255,255,0.08)" strokeWidth="0.8" />

      {/* Hood center crease */}
      <line x1="60" y1="94" x2="140" y2="94" stroke="rgba(255,255,255,0.06)" strokeWidth="0.6" />

      {/* Windshield -- raked back */}
      <path
        d="M 145,48 Q 155,42 175,40 L 175,148 Q 155,146 145,140"
        stroke="rgba(255,255,255,0.20)"
        strokeWidth="1.2"
      />

      {/* Roof outline -- narrower than body */}
      <path
        d="
          M 178,46
          L 320,44
          Q 340,44 355,50
          L 365,56
        "
        stroke="rgba(255,255,255,0.18)"
        strokeWidth="1"
      />
      <path
        d="
          M 178,142
          L 320,144
          Q 340,144 355,138
          L 365,132
        "
        stroke="rgba(255,255,255,0.18)"
        strokeWidth="1"
      />

      {/* Rear window -- fastback slope */}
      <path
        d="M 365,56 Q 380,60 385,70 L 385,118 Q 380,128 365,132"
        stroke="rgba(255,255,255,0.20)"
        strokeWidth="1.2"
      />

      {/* Trunk panel line */}
      <line x1="390" y1="50" x2="390" y2="138" stroke="rgba(255,255,255,0.08)" strokeWidth="0.8" />

      {/* A-pillar lines */}
      <line x1="145" y1="48" x2="178" y2="46" stroke="rgba(255,255,255,0.12)" strokeWidth="0.8" />
      <line x1="145" y1="140" x2="178" y2="142" stroke="rgba(255,255,255,0.12)" strokeWidth="0.8" />

      {/* B-pillar */}
      <line x1="245" y1="38" x2="245" y2="42" stroke="rgba(255,255,255,0.10)" strokeWidth="1.5" />
      <line x1="245" y1="146" x2="245" y2="150" stroke="rgba(255,255,255,0.10)" strokeWidth="1.5" />

      {/* Side windows -- front */}
      <rect x="180" y="42" width="63" height="5" rx="1" stroke="rgba(255,255,255,0.10)" strokeWidth="0.6" />
      <rect x="180" y="141" width="63" height="5" rx="1" stroke="rgba(255,255,255,0.10)" strokeWidth="0.6" />

      {/* Side windows -- rear */}
      <rect x="247" y="42" width="70" height="5" rx="1" stroke="rgba(255,255,255,0.10)" strokeWidth="0.6" />
      <rect x="247" y="141" width="70" height="5" rx="1" stroke="rgba(255,255,255,0.10)" strokeWidth="0.6" />

      {/* Headlights -- angular C-shape wrapping around fenders */}
      <path
        d="M 18,65 Q 12,72 10,80 L 10,94"
        stroke="rgba(255,255,255,0.35)"
        strokeWidth="2"
      />
      <path
        d="M 18,123 Q 12,116 10,108 L 10,94"
        stroke="rgba(255,255,255,0.35)"
        strokeWidth="2"
      />

      {/* Headlight inner detail (DRL) */}
      <path d="M 22,68 L 14,78" stroke="rgba(255,255,255,0.20)" strokeWidth="1" />
      <path d="M 22,120 L 14,110" stroke="rgba(255,255,255,0.20)" strokeWidth="1" />

      {/* Taillights -- full-width LED bar (signature 11th gen feature) */}
      <path
        d="M 470,55 Q 488,65 490,80"
        stroke="rgba(255,255,255,0.30)"
        strokeWidth="2"
      />
      <path
        d="M 470,133 Q 488,123 490,108"
        stroke="rgba(255,255,255,0.30)"
        strokeWidth="2"
      />
      {/* Connecting bar across trunk */}
      <line x1="440" y1="35" x2="440" y2="153" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />

      {/* Front grille -- trapezoidal */}
      <path
        d="M 14,75 L 10,82 L 10,106 L 14,113"
        stroke="rgba(255,255,255,0.15)"
        strokeWidth="0.8"
      />

      {/* Wheels -- front pair at ~18% of length */}
      <ellipse cx="90" cy="28" rx="22" ry="8" stroke="rgba(255,255,255,0.25)" strokeWidth="1.2" />
      <ellipse cx="90" cy="160" rx="22" ry="8" stroke="rgba(255,255,255,0.25)" strokeWidth="1.2" />
      {/* Wheel inner rim */}
      <ellipse cx="90" cy="28" rx="14" ry="5" stroke="rgba(255,255,255,0.12)" strokeWidth="0.6" />
      <ellipse cx="90" cy="160" rx="14" ry="5" stroke="rgba(255,255,255,0.12)" strokeWidth="0.6" />

      {/* Wheels -- rear pair at ~75% of length */}
      <ellipse cx="375" cy="28" rx="22" ry="8" stroke="rgba(255,255,255,0.25)" strokeWidth="1.2" />
      <ellipse cx="375" cy="160" rx="22" ry="8" stroke="rgba(255,255,255,0.25)" strokeWidth="1.2" />
      <ellipse cx="375" cy="28" rx="14" ry="5" stroke="rgba(255,255,255,0.12)" strokeWidth="0.6" />
      <ellipse cx="375" cy="160" rx="14" ry="5" stroke="rgba(255,255,255,0.12)" strokeWidth="0.6" />

      {/* Side mirrors */}
      <ellipse cx="155" cy="24" rx="8" ry="4" stroke="rgba(255,255,255,0.20)" strokeWidth="0.8" />
      <ellipse cx="155" cy="164" rx="8" ry="4" stroke="rgba(255,255,255,0.20)" strokeWidth="0.8" />

      {/* Shoulder crease lines -- run along body sides */}
      <path
        d="M 50,36 Q 100,33 200,35 L 400,35"
        stroke="rgba(255,255,255,0.06)"
        strokeWidth="0.6"
      />
      <path
        d="M 50,152 Q 100,155 200,153 L 400,153"
        stroke="rgba(255,255,255,0.06)"
        strokeWidth="0.6"
      />
    </svg>
  );
}
