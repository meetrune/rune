export function AboutBlock() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        paddingTop: "8px",
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-data)",
          fontSize: "11px",
          letterSpacing: "0.12em",
          color: "var(--rune-text-muted)",
          textTransform: "uppercase",
          opacity: 0.6,
        }}
      >
        About
      </span>

      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <InfoRow label="Vehicle" value="2026 Honda Accord SE" />
        <InfoRow label="Engine" value="L15BE 1.5T CVT" />
        <InfoRow label="Version" value="Rune OS v0.1.0" />
      </div>

      {/* Credit line */}
      <div
        style={{
          paddingTop: "16px",
          textAlign: "center",
        }}
      >
        <span
          style={{
            fontFamily: "'Cormorant Garamond', Georgia, serif",
            fontStyle: "italic",
            fontSize: "12px",
            color: "var(--rune-text-muted)",
            opacity: 0.12,
          }}
        >
          crafted by{" "}
        </span>
        <span
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "12px",
            color: "var(--rune-text-muted)",
            opacity: 0.15,
          }}
        >
          Kuladeep Mantri
        </span>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span
        style={{
          fontFamily: "var(--font-data)",
          fontSize: "12px",
          color: "var(--rune-text-muted)",
          opacity: 0.6,
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: "var(--font-data)",
          fontSize: "12px",
          color: "var(--rune-text-muted)",
        }}
      >
        {value}
      </span>
    </div>
  );
}
