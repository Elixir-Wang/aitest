import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageShellSource = readFileSync(new URL("../src/components/ai-testing/page-shell.tsx", import.meta.url), "utf8");

test("page shell renders the provided title and description", () => {
  assert.match(pageShellSource, /export function PageShell\(\{[\s\S]*title,[\s\S]*description,/);
  assert.match(pageShellSource, /<PageHeader[\s\S]*title=\{title\}[\s\S]*description=\{description\}/);
  assert.match(pageShellSource, /<h1[^>]*>\{title\}<\/h1>/);
  assert.match(pageShellSource, /<p[^>]*>\{description\}<\/p>/);
});
