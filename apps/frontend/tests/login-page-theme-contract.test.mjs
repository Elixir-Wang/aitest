import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const loginPageSource = readFileSync(
  new URL("../src/components/ui/animated-characters-login-page.tsx", import.meta.url),
  "utf8",
);
const globalsSource = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

test("login illustration panel is white outside dark mode", () => {
  assert.match(loginPageSource, /overflow-hidden bg-white p-12 text-foreground lg:flex dark:bg-background/);
  assert.doesNotMatch(loginPageSource, /overflow-hidden bg-primary p-12/);
});

test("login illustration panel keeps the dark theme background at night", () => {
  assert.match(loginPageSource, /dark:bg-background/);
  assert.match(globalsSource, /\.dark \{[\s\S]*?--background: oklch\(0\.145 0 0\);/);
});
