import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/page.tsx", import.meta.url),
  "utf8",
);
const clientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("scenario workbench supports ordered steps, validation, publishing, and execution", () => {
  assert.match(pageSource, /执行步骤/);
  assert.match(pageSource, /moveScenarioStep/);
  assert.match(pageSource, /handleValidateScenario/);
  assert.match(pageSource, /handlePublishScenario/);
  assert.match(pageSource, /handleExecuteScenario/);
  assert.match(pageSource, /变量绑定/);
  assert.match(pageSource, /响应提取/);
});

test("scenario api client exposes transactional step replacement and lifecycle endpoints", () => {
  assert.match(clientSource, /replaceApiAutomationScenarioSteps/);
  assert.match(clientSource, /method: "PUT"/);
  assert.match(clientSource, /\/api-scenarios\/\$\{scenarioId\}\/validate/);
  assert.match(clientSource, /\/api-scenarios\/\$\{scenarioId\}\/publish/);
  assert.match(clientSource, /\/api-scenarios\/\$\{scenarioId\}\/execute/);
});
