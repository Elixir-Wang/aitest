import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const idSource = readFileSync(new URL("../src/lib/create-id.mjs", import.meta.url), "utf8");
const inputSource = readFileSync(new URL("../src/components/ui/knowledge-chat-input.tsx", import.meta.url), "utf8");
const pageSource = readFileSync(new URL("../src/app/(main)/knowledge/page.tsx", import.meta.url), "utf8");
const scenarioModelSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-scenario-model.mjs", import.meta.url),
  "utf8",
);
const apiAutomationPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/page.tsx", import.meta.url),
  "utf8",
);

test("client ids fall back when crypto.randomUUID is unavailable", () => {
  assert.match(idSource, /typeof crypto\.randomUUID === "function"/);
  assert.match(idSource, /crypto\.getRandomValues/);
});

test("knowledge chat uses the shared client id generator", () => {
  assert.match(inputSource, /createId\(\)/);
  assert.match(pageSource, /createId\(\)/);
  assert.doesNotMatch(inputSource, /crypto\.randomUUID\(\)/);
  assert.doesNotMatch(pageSource, /crypto\.randomUUID\(\)/);
});

test("api scenarios use the shared client id generator", () => {
  assert.match(scenarioModelSource, /createId\(\)/);
  assert.match(apiAutomationPageSource, /createId\(\)/);
  assert.doesNotMatch(scenarioModelSource, /crypto\.randomUUID\(\)/);
  assert.doesNotMatch(apiAutomationPageSource, /crypto\.randomUUID\(\)/);
});
