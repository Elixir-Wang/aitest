import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/components/ai-testing/requirements-page.tsx", import.meta.url), "utf8");

test("requirement list shows active analysis status without hiding finalized requirements", () => {
  assert.match(pageSource, /latest_requirement_analysis_run: \{/);
  assert.match(pageSource, /function requirementDisplayStatus\(item: RequirementRow\)/);
  assert.match(pageSource, /const latestRun = item\.latest_requirement_analysis_run;/);
  assert.match(pageSource, /const hasFinalRequirement = Boolean\(item\.current_version_id \?\? item\.current_version\);/);
  assert.match(
    pageSource,
    /if \(latestRun && \(!hasFinalRequirement \|\| \["queued", "running"\]\.includes\(latestRun\.status\)\)\)/,
  );
  assert.match(pageSource, /running: "分析中"/);
  assert.match(pageSource, /failed: "分析失败"/);
  assert.match(pageSource, /<ProcessingState label=\{displayStatus\.label\} \/>/);
  assert.match(pageSource, /label: statusLabels\[item\.status\] \?\? item\.status/);
});

test("finalized requirement display status is not overridden by terminal analysis status", () => {
  const statusLabels = {
    versioned: "已生成",
  };
  const runStatusLabels = {
    queued: "排队中",
    running: "分析中",
    needs_clarification: "等待澄清",
  };
  function displayStatus(item) {
    const latestRun = item.latest_requirement_analysis_run;
    const hasFinalRequirement = Boolean(item.current_version_id || item.current_version);
    if (latestRun && (!hasFinalRequirement || ["queued", "running"].includes(latestRun.status))) {
      return runStatusLabels[latestRun.status] ?? latestRun.status;
    }
    return statusLabels[item.status] ?? item.status;
  }

  assert.equal(
    displayStatus({
      status: "versioned",
      current_version_id: "docver-1",
      latest_requirement_analysis_run: { status: "needs_clarification" },
    }),
    "已生成",
  );
  assert.equal(
    displayStatus({
      status: "versioned",
      current_version_id: "docver-1",
      latest_requirement_analysis_run: { status: "running" },
    }),
    "分析中",
  );
});
