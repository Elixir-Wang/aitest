import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pageSource = readFileSync(new URL("../src/app/office-preview/page.tsx", import.meta.url), "utf8");
const mainPageSource = readFileSync(new URL("../src/app/(main)/agents/page.tsx", import.meta.url), "utf8");
const dashboardSource = readFileSync(
  new URL("../src/components/ai-testing/silicon-office/office-dashboard.tsx", import.meta.url),
  "utf8",
);
const dashboardStyles = readFileSync(
  new URL("../src/components/ai-testing/silicon-office/office-dashboard.module.css", import.meta.url),
  "utf8",
);

test("official employee route renders the dedicated visual dashboard", () => {
  assert.match(mainPageSource, /SiliconOfficeDashboard/);
  assert.doesNotMatch(mainPageSource, /OfficeCanvas/);
  assert.ok(dashboardStyles.includes(".embedded .metrics"));
  assert.ok(dashboardStyles.includes("min-width: 0"));
});

test("office preview renders the dedicated visual dashboard", () => {
  assert.match(pageSource, /SiliconOfficeDashboard/);
  assert.match(dashboardSource, /员工总数/);
  assert.match(dashboardSource, /在线人数/);
  assert.match(dashboardSource, /运行中/);
  assert.match(dashboardSource, /空闲/);
  assert.match(dashboardSource, /异常/);
});

test("office overview matches the target five-card composition", () => {
  assert.match(dashboardSource, /metricsSection/);
  for (const label of ["员工总数", "在线人数", "专注工作", "会议中", "离线/休息"]) {
    assert.match(dashboardSource, new RegExp(label));
  }
  assert.match(dashboardStyles, /\.metrics[\s\S]*?border: 1px solid #e4e9f0/);
  assert.match(dashboardStyles, /\.metricCard[\s\S]*?min-height: 68px/);
  assert.match(dashboardStyles, /\.metricCard[\s\S]*?background: #fff/);
  assert.match(dashboardStyles, /\.metricCard:not\(:last-child\)[\s\S]*?border-right: 1px solid #e8edf3/);
  assert.match(dashboardStyles, /\.metricCopy[\s\S]*?grid-template-areas:[^;]*"label hint"[^;]*"value hint"/);
  assert.match(dashboardStyles, /\.metricHint[\s\S]*?grid-area: hint/);
  assert.match(dashboardStyles, /\.workspace[\s\S]*?360px/);
  assert.ok(dashboardStyles.includes("  height: calc(100dvh - 24px);"));
  assert.match(dashboardStyles, /\.officeFloor[\s\S]*?flex: 1/);
});

test("office dashboard keeps the six-room composition and fixed employee detail panel", () => {
  for (const room of ["需求工程组", "测试设计组", "自动化工程组", "运行与分析组", "AI能力中枢", "CEO办公室"]) {
    assert.match(dashboardSource, new RegExp(room));
  }
  assert.match(dashboardSource, /EmployeeDetailPanel/);
  assert.match(dashboardSource, /StatusLegend/);
  assert.ok(dashboardStyles.includes("grid-template-columns: minmax(0, 1fr) 300px"));
  assert.ok(dashboardStyles.includes("grid-template-columns: repeat(3, minmax(0, 1fr))"));
});

test("employee detail uses photographic assets and the reference action layout", () => {
  assert.match(dashboardSource, /EMPLOYEE_PORTRAITS/);
  assert.match(dashboardSource, /profileAvatarImage/);
  assert.match(dashboardSource, /roomImage\(employee\.room\)/);
  assert.match(dashboardSource, /专注工作/);
  assert.match(dashboardSource, /今日专注/);
  assert.match(dashboardSource, /完成任务/);
  assert.match(dashboardSource, /查看日程/);
  assert.match(dashboardStyles, /\.detailSnapshot[\s\S]*?grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(dashboardStyles, /\.detailActions button:first-child[\s\S]*?background: #2f6bff/);
  assert.ok(dashboardStyles.includes("flex-direction: column"));
  assert.ok(dashboardStyles.includes("border-right: 1px solid #edf1f6"));
});

test("department occupancy matches the target office board", () => {
  for (const occupancy of ["6, 7", "8, 8", "7, 7", "5, 6", "4, 4", "1, 1"]) {
    assert.match(dashboardSource, new RegExp(`room\\([^\\n]+${occupancy}`));
  }
  assert.match(dashboardSource, /room\.occupied/);
});

test("office visual has only the three confirmed employee statuses", () => {
  assert.ok(dashboardSource.includes('type EmployeeStatus = "idle" | "running" | "error";'));
  assert.doesNotMatch(dashboardSource, /human-waiting|EmptyWorkstation|emptyLabel/);
  assert.doesNotMatch(dashboardSource, /筛选|视图切换|viewMode|filterMode/);
  assert.match(dashboardSource, /employee\.status !== "idle" \? <Nameplate/);
});

test("office rooms use standardized desk scenes and a centered CEO office", () => {
  for (const asset of [
    "requirement-room-standardized.png",
    "test-design-room-standardized.png",
    "automation-room-standardized.png",
    "operations-room-standardized.png",
    "ai-center-room-standardized.png",
    "ceo-office-centered.png",
  ]) {
    assert.match(dashboardSource, new RegExp(asset.replaceAll(".", "\\.")));
  }
  assert.match(dashboardStyles, /\.executiveHotspot[\s\S]*?top: 38%/);
});

test("office visual uses complete generated room scenes with interactive DOM overlays", () => {
  assert.match(dashboardSource, /OfficeRoom/);
  assert.match(dashboardSource, /Workstation/);
  assert.match(dashboardSource, /next\/image/);
  for (const asset of [
    "requirement-room-standardized.png",
    "test-design-room-standardized.png",
    "automation-room-standardized.png",
    "operations-room-standardized.png",
    "ai-center-room-standardized.png",
    "ceo-office-centered.png",
  ]) {
    assert.match(dashboardSource, new RegExp(asset.replaceAll(".", "\\.")));
  }
  assert.doesNotMatch(dashboardSource, /WORKSTATION_IMAGES|EMPTY_WORKSTATION_IMAGE/);
  assert.doesNotMatch(dashboardStyles, /\.personHead|\.personBody|\.desk|\.chair/);
});
