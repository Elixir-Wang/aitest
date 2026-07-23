import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const panelSource = readFileSync(
  new URL("../src/components/ai-testing/test-points-panel.tsx", import.meta.url),
  "utf8",
);
const summarySource = readFileSync(
  new URL("../src/components/ai-testing/test-point-coverage-summary.tsx", import.meta.url),
  "utf8",
);

test("test point overview exposes coverage summary", () => {
  assert.match(apiClientSource, /coverage_summary: ApiTestPointCoverageSummary/);
  assert.match(apiClientSource, /missing_obligations: ApiTestPointRequirementObligation\[\]/);
  assert.match(apiClientSource, /requirement_obligations: ApiTestPointRequirementObligation\[\]/);
});

test("test point panel renders requirement coverage", () => {
  assert.match(panelSource, /<TestPointCoverageSummary/);
  assert.match(summarySource, /需求义务/);
  assert.match(summarySource, /已覆盖/);
  assert.match(summarySource, /未覆盖/);
  assert.match(summarySource, /当前测试要点未生成完整/);
  assert.match(
    summarySource,
    /key=\{`\$\{obligation\.obligation_key\}:\$\{obligation\.source_section\}:\$\{obligation\.statement\}`\}/,
  );
  assert.doesNotMatch(summarySource, /key=\{obligation\.obligation_key\}/);
  assert.doesNotMatch(summarySource, /测试要点：/);
});
