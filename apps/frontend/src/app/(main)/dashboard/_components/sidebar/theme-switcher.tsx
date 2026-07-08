"use client";

import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { persistPreference } from "@/lib/preferences/preferences-storage";
import { usePreferencesStore } from "@/stores/preferences/preferences-provider";

export function ThemeSwitcher() {
  const themeMode = usePreferencesStore((s) => s.themeMode);
  const themeScheme = usePreferencesStore((s) => s.themeScheme);
  const setThemeMode = usePreferencesStore((s) => s.setThemeMode);

  const toggleDarkMode = () => {
    const nextTheme = themeMode === "dark" ? themeScheme : "dark";
    setThemeMode(nextTheme);
    void persistPreference("theme_mode", nextTheme);
  };

  return (
    <Button size="icon" onClick={toggleDarkMode} aria-label={`Current mode: ${themeMode}. Click to toggle dark mode`}>
      {themeMode === "dark" ? <Sun /> : <Moon />}
    </Button>
  );
}
