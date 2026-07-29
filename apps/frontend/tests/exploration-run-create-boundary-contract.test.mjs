import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/components/ai-testing/exploration-run-create-page.tsx", import.meta.url),
  "utf8",
);

test("Loop exploration hides user-facing execution boundary fields", () => {
  assert.match(source, /form\.explorationMode !== "loop"\s*&&\s*\(/);
  assert.match(source, /<FieldLabel>执行边界 \*<\/FieldLabel>/);
});

test("Loop exploration uses platform safety defaults without validating hidden inputs", () => {
  assert.match(source, /const usesPlatformSafetyLimits = form\.explorationMode === "loop"/);
  assert.match(source, /max_pages: usesPlatformSafetyLimits \? 50 : maxPages/);
  assert.match(source, /max_actions: usesPlatformSafetyLimits \? 1000 : maxActions/);
  assert.match(source, /timeout_minutes: usesPlatformSafetyLimits \? 120 : timeoutMinutes/);
  assert.match(source, /!usesPlatformSafetyLimits && \(!maxPages \|\| !maxActions \|\| !timeoutMinutes\)/);
});
