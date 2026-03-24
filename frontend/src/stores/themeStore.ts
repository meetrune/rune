import { create } from "zustand";
import type { RuneTheme } from "@/types/theme";
import { THEMES, DEFAULT_THEME_ID } from "@/constants/themes";

interface ThemeState {
  activeThemeId: string;
  setTheme: (id: string) => void;
  nextTheme: () => void;
  randomize: () => void;
}

function applyThemeToDom(theme: RuneTheme): void {
  const root = document.documentElement;
  root.style.setProperty("--rune-bg", theme.bg);
  root.style.setProperty("--rune-primary", theme.primary);
  root.style.setProperty("--rune-dim", theme.dim);
  root.style.setProperty("--rune-warn", theme.warn);
  root.style.setProperty("--rune-critical", theme.critical);
  root.style.setProperty("--rune-text", theme.text);
  root.style.setProperty("--rune-text-muted", theme.textMuted);
  root.style.setProperty("--rune-surface", theme.surface);
  root.style.setProperty("--rune-border", theme.border);

  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme.bg);
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  activeThemeId: DEFAULT_THEME_ID,

  setTheme: (id: string) => {
    const theme = THEMES.find((t) => t.id === id);
    if (theme) {
      set({ activeThemeId: id });
      applyThemeToDom(theme);
    }
  },

  nextTheme: () => {
    const currentIdx = THEMES.findIndex((t) => t.id === get().activeThemeId);
    const nextIdx = (currentIdx + 1) % THEMES.length;
    const next = THEMES[nextIdx];
    if (next) {
      set({ activeThemeId: next.id });
      applyThemeToDom(next);
    }
  },

  randomize: () => {
    const currentId = get().activeThemeId;
    const others = THEMES.filter((t) => t.id !== currentId);
    const pick = others[Math.floor(Math.random() * others.length)];
    if (pick) {
      set({ activeThemeId: pick.id });
      applyThemeToDom(pick);
    }
  },
}));

export function getActiveTheme(): RuneTheme {
  const id = useThemeStore.getState().activeThemeId;
  return THEMES.find((t) => t.id === id) ?? THEMES[0]!;
}

// Apply default theme on module load
applyThemeToDom(THEMES.find((t) => t.id === DEFAULT_THEME_ID) ?? THEMES[0]!);
