import { useRef, useEffect, useState } from "react";
import { useRuneVoice } from "@/hooks/useRuneVoice";

export function VoiceText() {
  const { message } = useRuneVoice();
  const [visible, setVisible] = useState(false);
  const prevMessageRef = useRef("");

  useEffect(() => {
    if (message === prevMessageRef.current) return;
    prevMessageRef.current = message;

    // Fade out, swap text, fade in
    setVisible(false);
    const timer = setTimeout(() => {
      setVisible(true);
    }, 50);

    return () => clearTimeout(timer);
  }, [message]);

  if (!message) return null;

  return (
    <div
      style={{
        ...styles.container,
        opacity: visible ? 1 : 0,
      }}
    >
      {message}
    </div>
  );
}

const styles = {
  container: {
    fontFamily: "Inter, system-ui, sans-serif",
    fontSize: "14px",
    fontWeight: 400,
    lineHeight: 1.4,
    color: "var(--rune-text)",
    opacity: 0,
    transition: "opacity 600ms ease",
    textAlign: "center" as const,
    maxWidth: "400px",
    padding: "0 16px",
  },
} as const;
