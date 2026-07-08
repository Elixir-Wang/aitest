/**
 * Boot script that reads user preference values from cookies or localStorage
 * based on the configured persistence mode.
 *
 * Runs early in <head> to apply the correct data attributes before hydration,
 * preventing theme flicker and keeping RootLayout fully static.
 */
import { PREFERENCE_DEFAULTS, PREFERENCE_PERSISTENCE } from "@/lib/preferences/preferences-config";
import { THEME_MODE_VALUES, THEME_SCHEME_VALUES } from "@/lib/preferences/theme";

export function ThemeBootScript() {
  const persistence = JSON.stringify({
    theme_mode: PREFERENCE_PERSISTENCE.theme_mode,
    theme_scheme: PREFERENCE_PERSISTENCE.theme_scheme,
    sidebar_variant: PREFERENCE_PERSISTENCE.sidebar_variant,
  });

  const defaults = JSON.stringify({
    theme_mode: PREFERENCE_DEFAULTS.theme_mode,
    theme_scheme: PREFERENCE_DEFAULTS.theme_scheme,
    sidebar_variant: PREFERENCE_DEFAULTS.sidebar_variant,
  });
  const themeModes = JSON.stringify(THEME_MODE_VALUES);
  const themeSchemes = JSON.stringify(THEME_SCHEME_VALUES);

  const code = `
    (function () {
      try {
        var root = document.documentElement;
        var PERSISTENCE = ${persistence};
        var DEFAULTS = ${defaults};
        var THEME_MODES = ${themeModes};
        var THEME_SCHEMES = ${themeSchemes};

        function readCookie(name) {
          var match = document.cookie.split("; ").find(function(c) {
            return c.startsWith(name + "=");
          });
          return match ? decodeURIComponent(match.split("=")[1]) : null;
        }

        function readLocal(name) {
          try {
            return window.localStorage.getItem(name);
          } catch (e) {
            return null;
          }
        }

        function readPreference(key, fallback) {
          var mode = PERSISTENCE[key];
          var value = null;

          if (mode === "localStorage") {
            value = readLocal(key);
          }

          if (!value && (mode === "client-cookie" || mode === "server-cookie")) {
            value = readCookie(key);
          }

          if (!value || typeof value !== "string") {
            return fallback;
          }

          return value;
        }

        var rawMode = readPreference("theme_mode", DEFAULTS.theme_mode);
        var rawScheme = readPreference("theme_scheme", DEFAULTS.theme_scheme);
        var rawSidebarVariant = readPreference("sidebar_variant", DEFAULTS.sidebar_variant);

        var isValidMode = THEME_MODES.indexOf(rawMode) !== -1;
        var isValidScheme = THEME_SCHEMES.indexOf(rawScheme) !== -1;
        var migratedScheme = THEME_SCHEMES.indexOf(rawMode) !== -1 ? rawMode : DEFAULTS.theme_scheme;
        var scheme = isValidScheme ? rawScheme : migratedScheme;
        var mode = isValidMode ? rawMode : scheme;
        var resolvedMode = mode === "dark" ? "dark" : "light";
        var sidebarVariant = rawSidebarVariant || DEFAULTS.sidebar_variant;

        root.classList.toggle("dark", resolvedMode === "dark");
        root.setAttribute("data-theme-mode", mode);
        root.setAttribute("data-theme-scheme", scheme);
        root.setAttribute("data-sidebar-variant", sidebarVariant);

        root.style.colorScheme = resolvedMode === "dark" ? "dark" : "light";

      } catch (e) {
        console.warn("ThemeBootScript error:", e);
      }
    })();
  `;

  /* biome-ignore lint/security/noDangerouslySetInnerHtml: required for pre-hydration boot script */
  return <script dangerouslySetInnerHTML={{ __html: code }} />;
}
