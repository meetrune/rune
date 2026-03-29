import { useRef, useEffect, useState } from "react";
import { useRuneVoice } from "@/hooks/useRuneVoice";

export function VoiceText() {
  const { message } = useRuneVoice();
  const [displayMessage, setDisplayMessage] = useState("");
  const [opacity, setOpacity] = useState(0);
  const prevRef = useRef("");

  useEffect(() => {
    if (!message || message === prevRef.current) return;
    prevRef.current = message;

    // Fade out current message
    setOpacity(0);

    // After fade-out completes, swap text and fade in
    const swapTimer = setTimeout(() => {
      setDisplayMessage(message);
      setOpacity(1);
    }, 500);

    return () => clearTimeout(swapTimer);
  }, [message]);

  // Show initial message
  useEffect(() => {
    if (message && !displayMessage) {
      setDisplayMessage(message);
      const t = setTimeout(() => setOpacity(1), 100);
      return () => clearTimeout(t);
    }
  }, [message, displayMessage]);

  if (!displayMessage) return null;

  return (
    <div
      style={{
        fontFamily: "var(--font-ui)",
        fontSize: "15px",
        fontWeight: 300,
        lineHeight: 1.5,
        color: "rgba(255,255,255,0.4)",
        textAlign: "center",
        maxWidth: "500px",
        opacity,
        transition: "opacity 500ms ease",
      }}
    >
      {displayMessage}
    </div>
  );
}
