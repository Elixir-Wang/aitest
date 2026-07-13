export const THEME_MODE_OPTIONS = [
  { label: "Default", value: "light" },
  { label: "Claude", value: "claude" },
  { label: "Mint", value: "mint" },
  { label: "Dark", value: "dark" },
] as const;

export const THEME_SCHEME_OPTIONS = THEME_MODE_OPTIONS.filter((option) => option.value !== "dark");
export const THEME_MODE_VALUES = THEME_MODE_OPTIONS.map((o) => o.value);
export const THEME_SCHEME_VALUES = THEME_SCHEME_OPTIONS.map((o) => o.value);
export type ThemeMode = (typeof THEME_MODE_VALUES)[number];
export type ThemeScheme = (typeof THEME_SCHEME_VALUES)[number];
export type ResolvedThemeMode = "light" | "dark";
