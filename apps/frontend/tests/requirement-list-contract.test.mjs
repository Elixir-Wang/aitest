import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/components/ai-testing/requirements-page.tsx", import.meta.url), "utf8");

test("requirement list shows active analysis status without hiding finalized requirements", () => {
  assert.match(pageSource, /latest_requirement_analysis_run: \{/);
  assert.match(pageSource, /function requirementDisplayStatus\(item: RequirementRow\)/);
  assert.match(pageSource, /const latestRun = item\.latest_requirement_analysis_run;/);
  assert.match(pageSource, /const hasFinalRequirement = Boolean\(item\.current_version_id\);/);
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

test("requirement batch delete reports partial failures with concrete document names", () => {
  assert.match(pageSource, /export type RequirementDeleteResult =/);
  assert.match(pageSource, /function summarizeRequirementDeleteResults/);
  assert.match(pageSource, /Promise\.all\(\s*targets\.map\(async \(row\): Promise<RequirementDeleteResult> =>/);
  assert.match(
    pageSource,
    /setRows\(\(current\) => current\.filter\(\(row\) => !successfulIds\.includes\(row\.id\)\)\);/,
  );
  assert.match(pageSource, /部分需求文档删除失败/);
  assert.match(pageSource, /actionLabel: `删除需求文档：\$\{summary\.failedNames\}`/);
  assert.match(pageSource, /网络异常，未收到后端响应/);
});

test("requirement row actions expose delete with a trash icon", () => {
  assert.match(pageSource, /import \{ Eye, History, Trash2 \} from "lucide-react";/);
  assert.match(
    pageSource,
    /label: "删除",[\s\S]*icon: Trash2,[\s\S]*destructive: true,[\s\S]*onSelect: \(\) => deleteDocuments\(\[item\.id\]\)/,
  );
});

test("requirement delete failure explains linked test case sets briefly", () => {
  assert.match(pageSource, /function summarizeRequirementDeleteReason\(error: unknown\)/);
  assert.match(pageSource, /已关联测试用例集，需先删除测试用例集/);
  assert.match(pageSource, /failureMessage: failed\.length > 0 \? `删除失败：\$\{reasonSummary\}` : ""/);
  assert.doesNotMatch(pageSource, /failureMessage: failed\.length > 0 \? `删除失败：\$\{failedNames\}/);
});
