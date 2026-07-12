import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const reportPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx", import.meta.url),
  "utf8",
);
const explorationTypesSource = readFileSync(new URL("../src/lib/exploration-types.ts", import.meta.url), "utf8");
const explorationServiceSource = readFileSync(
  new URL("../../backend/app/services/page_exploration/service.py", import.meta.url),
  "utf8",
);

test("exploration report removes version and generated time metadata", () => {
  assert.doesNotMatch(reportPageSource, /label="报告版本"/);
  assert.doesNotMatch(reportPageSource, /label="生成时间"/);
  assert.doesNotMatch(explorationTypesSource, /version_no: number \| null/);
  assert.doesNotMatch(explorationTypesSource, /created_at: string \| null/);
  const reportResponse =
    explorationServiceSource.match(/def get_exploration_report[\s\S]*?def get_artifact_content/)?.[0] ?? "";
  assert.doesNotMatch(reportResponse, /"version_no"/);
  assert.doesNotMatch(reportResponse, /"created_at"/);
});

test("exploration report owns a vertical scroll container inside the fixed viewport shell", () => {
  assert.match(reportPageSource, /<ShellSection className="min-h-0 flex-1 overflow-y-auto">/);
});
