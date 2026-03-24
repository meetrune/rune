// Rune's voice -- first person, direct, honest, brief.
// He IS the car. Not a servant, not a robot.

import type { SubsystemId } from "@/types/vehicle";
import { SUBSYSTEM_LABELS } from "@/constants/zones";

export type VoiceState = "good" | "calibrating" | "warning" | "critical" | "recovering" | "disconnected";

interface VoiceTemplate {
  state: VoiceState;
  messages: string[];
}

const TEMPLATES: VoiceTemplate[] = [
  {
    state: "good",
    messages: [
      "All good. {score} across the board.",
      "Running smooth. {score} overall.",
      "Everything's where it should be. {score}.",
    ],
  },
  {
    state: "calibrating",
    messages: [
      "Getting a feel for things. Give me a minute.",
      "Still warming up. Numbers coming in.",
      "Learning my baseline. Won't be long.",
    ],
  },
  {
    state: "warning",
    messages: [
      "{subsystem} is off. {detail}",
      "Something with my {subsystem}. {detail}",
      "Heads up -- {subsystem} needs a look. {detail}",
    ],
  },
  {
    state: "critical",
    messages: [
      "Something I need to tell you. {subsystem} is not right. {detail}",
      "{subsystem} -- this is real. {detail}",
    ],
  },
  {
    state: "recovering",
    messages: [
      "{subsystem} is settling back down.",
      "Better. {subsystem} coming back to normal.",
    ],
  },
  {
    state: "disconnected",
    messages: [
      "Lost connection. Working on it.",
      "Can't hear the car right now. Reconnecting.",
    ],
  },
];

const templatesByState: Record<VoiceState, string[]> = Object.fromEntries(
  TEMPLATES.map((t) => [t.state, t.messages])
) as Record<VoiceState, string[]>;

export interface VoiceMessageOpts {
  state: VoiceState;
  overallScore?: number;
  worstSubsystem?: SubsystemId;
  worstScore?: number;
  detail?: string;
}

// Pick a random template for a given state and fill in variables
export function generateVoiceMessage(opts: VoiceMessageOpts): string {
  const pool = templatesByState[opts.state];
  const template = pool[Math.floor(Math.random() * pool.length)] ?? pool[0] ?? "";

  // Build detail string from worst subsystem score if not provided
  const detail = opts.detail ??
    (opts.worstScore != null ? `Sitting at ${opts.worstScore}.` : "");

  return template
    .replace("{score}", opts.overallScore != null ? String(opts.overallScore) : "--")
    .replace("{subsystem}", opts.worstSubsystem ? SUBSYSTEM_LABELS[opts.worstSubsystem] : "")
    .replace("{detail}", detail);
}
