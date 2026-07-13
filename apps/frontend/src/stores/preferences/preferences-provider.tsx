"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";

import { type StoreApi, useStore } from "zustand";

import { SIDEBAR_VARIANT_VALUES } from "@/lib/preferences/layout";
import { THEME_MODE_VALUES, THEME_SCHEME_VALUES } from "@/lib/preferences/theme";
import { applyThemeMode } from "@/lib/preferences/theme-utils";

import { createPreferencesStore, type PreferencesState } from "./preferences-store";

const PreferencesStoreContext = createContext<StoreApi<PreferencesState> | null>(null);

function getSafeValue<T extends string>(raw: string | null, allowed: readonly T[]): T | undefined {
  if (!raw) return undefined;
  return allowed.includes(raw as T) ? (raw as T) : undefined;
}

function readDomState(): Partial<PreferencesState> {
  const root = document.documentElement;

  const themeModeAttr = getSafeValue(root.getAttribute("data-theme-mode"), THEME_MODE_VALUES);
  const themeSchemeAttr = getSafeValue(root.getAttribute("data-theme-scheme"), THEME_SCHEME_VALUES);
  const themeModeScheme = getSafeValue(themeModeAttr ?? null, THEME_SCHEME_VALUES);
  const resolvedMode = root.classList.contains("dark") ? "dark" : "light";

  return {
    themeMode: themeModeAttr ?? resolvedMode,
    themeScheme: themeSchemeAttr ?? themeModeScheme ?? "light",
    sidebarVariant: getSafeValue(root.getAttribute("data-sidebar-variant"), SIDEBAR_VARIANT_VALUES),
  };
}

export const PreferencesStoreProvider = ({
  children,
  themeMode,
  themeScheme,
}: {
  children: React.ReactNode;
  themeMode: PreferencesState["themeMode"];
  themeScheme: PreferencesState["themeScheme"];
}) => {
  const [store] = useState<StoreApi<PreferencesState>>(() =>
    createPreferencesStore({
      themeMode,
      themeScheme,
    }),
  );

  const domSnapshotRef = useRef<Partial<PreferencesState> | null>(null);

  useEffect(() => {
    const domState = readDomState();
    domSnapshotRef.current = domState;

    store.setState((prev) => ({
      ...prev,
      ...domState,
      isSynced: true,
    }));
  }, [store]);

  useEffect(() => {
    const applyFromMode = (mode: PreferencesState["themeMode"]) => {
      applyThemeMode(mode);
    };

    const startMode = domSnapshotRef.current?.themeMode ?? store.getState().themeMode;
    applyFromMode(startMode);

    const unsubscribeStore = store.subscribe((s, p) => {
      if (s.themeMode !== p.themeMode) applyFromMode(s.themeMode);
    });

    return () => {
      unsubscribeStore();
    };
  }, [store]);

  return <PreferencesStoreContext.Provider value={store}>{children}</PreferencesStoreContext.Provider>;
};

export const usePreferencesStore = <T,>(selector: (state: PreferencesState) => T): T => {
  const store = useContext(PreferencesStoreContext);
  if (!store) throw new Error("Missing PreferencesStoreProvider");
  return useStore(store, selector);
};
