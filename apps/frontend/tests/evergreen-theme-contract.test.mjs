import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const themeSource = readFileSync(new URL("../src/lib/preferences/theme.ts", import.meta.url), "utf8");
const globalsSource = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

test("Evergreen is available as a selectable light theme", () => {
  assert.match(themeSource, /\{ label: "Evergreen", value: "evergreen" \}/);
  assert.match(themeSource, /THEME_SCHEME_OPTIONS = THEME_MODE_OPTIONS\.filter/);
});

test("Evergreen uses the green-led documentation palette", () => {
  const evergreenTheme = globalsSource.match(/\[data-theme-mode="evergreen"\] \{([\s\S]*?)\n\}/)?.[1];

  assert.ok(evergreenTheme, "Evergreen theme variables must exist");
  assert.match(evergreenTheme, /--primary: #16803c;/);
  assert.match(evergreenTheme, /--accent: #e4f4ea;/);
  assert.match(evergreenTheme, /--foreground: #111827;/);
  assert.match(evergreenTheme, /--sidebar-accent: #e4f4ea;/);
});
