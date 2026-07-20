import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const emptyStateSource = readFileSync(
  new URL("../src/components/ai-testing/illustrated-empty-state.tsx", import.meta.url),
  "utf8",
);

test("illustrated empty state uses the shared illustration and two-level copy", () => {
  assert.match(emptyStateSource, /src="\/illustrations\/api-cases-empty-right\.svg"/);
  assert.match(emptyStateSource, /\{title\}/);
  assert.match(emptyStateSource, /\{description\}/);
});
