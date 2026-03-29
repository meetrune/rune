import { useSettingsStore } from "@/stores/settingsStore";

type ToggleKey = "gridBackground" | "runeVoice" | "hapticFeedback" | "parallaxTilt";

interface PreferenceCardProps {
  title: string;
  description: string;
  settingKey: ToggleKey;
}

export function PreferenceCard({ title, description, settingKey }: PreferenceCardProps) {
  const isOn = useSettingsStore((s) => s[settingKey]);
  const toggle = useSettingsStore((s) => s.toggle);

  return (
    <button
      onClick={() => toggle(settingKey)}
      style={{
        display: "block",
        width: "100%",
        textAlign: "left",
        background: "none",
        border: "none",
        borderLeft: isOn ? "3px solid var(--rune-text)" : "3px solid transparent",
        padding: "14px 14px",
        cursor: "pointer",
        WebkitTapHighlightColor: "transparent",
        touchAction: "manipulation",
        minHeight: "56px",
        position: "relative",
        transition: "border-left-color 0.2s",
      }}
    >
      {/* On/Off label top-right */}
      <span
        style={{
          position: "absolute",
          top: "10px",
          right: "12px",
          fontFamily: "var(--font-data)",
          fontSize: "10px",
          letterSpacing: "0.08em",
          color: isOn ? "var(--rune-text)" : "var(--rune-text-muted)",
          opacity: isOn ? 0.8 : 0.4,
        }}
      >
        {isOn ? "On" : "Off"}
      </span>

      {/* Title */}
      <span
        style={{
          fontFamily: "var(--font-data)",
          fontSize: "14px",
          fontWeight: 500,
          color: isOn ? "var(--rune-text)" : "var(--rune-text-muted)",
          textDecoration: isOn ? "none" : "line-through",
          display: "block",
          lineHeight: 1.3,
          transition: "color 0.2s",
          paddingRight: "32px",
        }}
      >
        {title}
      </span>

      {/* Description */}
      <span
        style={{
          fontFamily: "var(--font-data)",
          fontSize: "11px",
          color: "var(--rune-text-muted)",
          opacity: isOn ? 0.6 : 0.3,
          display: "block",
          marginTop: "3px",
          lineHeight: 1.3,
          transition: "opacity 0.2s",
        }}
      >
        {description}
      </span>
    </button>
  );
}
