import { createStore } from "zustand/vanilla";

import type { SidebarVariant } from "@/lib/preferences/layout";
import { PREFERENCE_DEFAULTS } from "@/lib/preferences/preferences-config";
import type { ThemeMode, ThemeScheme } from "@/lib/preferences/theme";

export type PreferencesState = {
  themeMode: ThemeMode;
  themeScheme: ThemeScheme;
  sidebarVariant: SidebarVariant;
  setThemeMode: (mode: ThemeMode) => void;
  setThemeScheme: (scheme: ThemeScheme) => void;
  setSidebarVariant: (variant: SidebarVariant) => void;
  isSynced: boolean;
  setIsSynced: (val: boolean) => void;
};

export const createPreferencesStore = (init?: Partial<PreferencesState>) =>
  createStore<PreferencesState>()((set) => ({
    themeMode: init?.themeMode ?? PREFERENCE_DEFAULTS.theme_mode,
    themeScheme: init?.themeScheme ?? PREFERENCE_DEFAULTS.theme_scheme,
    sidebarVariant: init?.sidebarVariant ?? PREFERENCE_DEFAULTS.sidebar_variant,
    setThemeMode: (mode) => set({ themeMode: mode }),
    setThemeScheme: (scheme) => set({ themeScheme: scheme }),
    setSidebarVariant: (variant) => set({ sidebarVariant: variant }),
    isSynced: init?.isSynced ?? false,
    setIsSynced: (val) => set({ isSynced: val }),
  }));
