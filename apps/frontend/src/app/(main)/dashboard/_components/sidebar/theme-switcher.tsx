"use client";

import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { persistPreference } from "@/lib/preferences/preferences-storage";
import { usePreferencesStore } from "@/stores/preferences/preferences-provider";

const THEME_CYCLE = ["light", "dark"] as const;

export function ThemeSwitcher() {
  const themeMode = usePreferencesStore((s) => s.themeMode);
  const setThemeMode = usePreferencesStore((s) => s.setThemeMode);

  const cycleTheme = () => {
    const currentIndex = THEME_CYCLE.indexOf(themeMode);
    const nextTheme = THEME_CYCLE[(currentIndex + 1) % THEME_CYCLE.length];

    setThemeMode(nextTheme);
    void persistPreference("theme_mode", nextTheme);
  };

  return (
    <Button size="icon" onClick={cycleTheme} aria-label={`Current theme: ${themeMode}. Click to cycle themes`}>
      <Sun className="hidden dark:block" />
      <Moon className="block dark:hidden" />
    </Button>
  );
}
