import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/components/ai-testing/requirements-page.tsx", import.meta.url), "utf8");

test("requirement list uses latest analysis run status for display", () => {
  assert.match(pageSource, /latest_requirement_analysis_run: \{/);
  assert.match(pageSource, /function requirementDisplayStatus\(item: RequirementRow\)/);
  assert.match(pageSource, /const latestRun = item\.latest_requirement_analysis_run;/);
  assert.match(pageSource, /running: "分析中"/);
  assert.match(pageSource, /failed: "分析失败"/);
  assert.match(pageSource, /<ProcessingState label=\{displayStatus\.label\} \/>/);
  assert.doesNotMatch(pageSource, /\(statusLabels\[item\.status\] \?\? item\.status\)/);
});
