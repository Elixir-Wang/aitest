import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const clientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const detailSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-run-detail.tsx", import.meta.url),
  "utf8",
);
const drawerSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-repair-drawer.tsx", import.meta.url),
  "utf8",
);
const progressSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-repair-progress.tsx", import.meta.url),
  "utf8",
);
const diffDialogSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-repair-diff-dialog.tsx", import.meta.url),
  "utf8",
);

test("failed API runs expose an independent AI repair drawer", () => {
  assert.match(detailSource, /ApiRepairDrawer/);
  assert.match(detailSource, /AI 分析与修复/);
  assert.doesNotMatch(detailSource, /ApiRepairPanel/);
  assert.match(drawerSource, /Drawer direction="right"/);
  assert.match(drawerSource, /data-\[vaul-drawer-direction=right\]:w-full/);
  assert.match(drawerSource, /sm:data-\[vaul-drawer-direction=right\]:max-w-5xl/);
  assert.match(drawerSource, /接口自动化 AI 分析与修复/);
  assert.match(drawerSource, /确认修改代码/);
  assert.match(drawerSource, /应用通过的测试脚本/);
  assert.doesNotMatch(drawerSource, /批准并应用/);
  assert.match(progressSource, /分析失败原因/);
  assert.match(progressSource, /确认代码修改/);
  assert.match(progressSource, /proposal_ready: "诊断完成，无需改代码"/);
  assert.match(progressSource, /生成候选修改/);
  assert.match(progressSource, /验证候选修改/);
  assert.match(progressSource, /应用正式代码/);
  assert.match(diffDialogSource, /候选修改 Diff/);
  assert.match(drawerSource, /拟修改代码/);
  assert.match(drawerSource, /caseUpdates.map/);
  assert.match(drawerSource, /用例预期变更/);
  assert.match(drawerSource, /expected_status_code/);
  assert.match(drawerSource, /actual_status_code/);
  assert.match(drawerSource, /处理建议/);
  assert.match(drawerSource, /未生成可审批的测试代码修改方案/);
  assert.match(drawerSource, /诊断已完成，无需修改测试代码/);
  assert.match(drawerSource, /当前失败来自被测接口行为，不是测试脚本错误/);
  assert.match(drawerSource, /已完成失败归因，测试代码未修改/);
  assert.match(drawerSource, /environment_issue/);
  assert.match(drawerSource, /原运行结果/);
  assert.match(drawerSource, /候选修改验证结果/);
  assert.match(drawerSource, /onOpenChange\(false\)/);
  assert.match(drawerSource, /attemptActions\.has\("reanalyze"\)/);
  assert.match(drawerSource, /重新分析/);
  assert.match(drawerSource, /function localizeRepairText/);
  assert.match(drawerSource, /测试预期/);
  assert.match(drawerSource, /attempt\?\.diagnosis\?\.issues/);
  assert.doesNotMatch(drawerSource, /判断证据/);
  assert.doesNotMatch(drawerSource, /需要确认/);
  assert.doesNotMatch(drawerSource, /补充信息/);
  assert.doesNotMatch(drawerSource, /确认接口缺陷/);
  assert.doesNotMatch(drawerSource, /performance-testing/);
  assert.doesNotMatch(drawerSource, /window\.confirm/);
  assert.match(clientSource, /createApiRepairSession/);
  assert.match(clientSource, /approveApiRepairAttempt/);
  assert.match(clientSource, /applyApiRepairAttempt/);
  assert.match(clientSource, /discardApiRepairAttempt/);
  assert.match(clientSource, /rejectApiRepairAttempt/);
  assert.match(clientSource, /available_actions: string\[\]/);
  assert.match(clientSource, /createApiRepairAttempt/);
  assert.match(clientSource, /api-repair-sessions\/\$\{sessionId\}\/attempts/);
});

test("run detail groups repair and report actions in the header toolbar", () => {
  assert.match(
    detailSource,
    /<div className="flex shrink-0 flex-wrap items-center justify-end gap-2">[\s\S]*?返回[\s\S]*?刷新[\s\S]*?重新执行[\s\S]*?查看 JSON 报告[\s\S]*?AI 分析与修复/,
  );
  assert.match(detailSource, /<ChevronLeft className="size-4" \/>/);
  assert.match(detailSource, /<Play className=\{cn\("size-4", rerunLoading && "animate-pulse"\)\} \/>/);
  assert.doesNotMatch(detailSource, /返回运行记录/);
  assert.doesNotMatch(detailSource, /按原配置重新执行/);
  assert.doesNotMatch(detailSource, /size="icon"/);
  assert.match(detailSource, /<Button onClick=\{\(\) => setRepairOpen\(true\)\}>/);
  assert.match(detailSource, /<Button onClick=\{\(\) => void openReport\(\)\} variant="outline">/);
  assert.doesNotMatch(detailSource, /<Button asChild size="sm" variant="outline">/);
});
