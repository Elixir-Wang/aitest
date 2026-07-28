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
  assert.match(dashboardSource, /工作中/);
  assert.match(dashboardSource, /运行中/);
  assert.match(dashboardSource, /空闲/);
  assert.match(dashboardSource, /异常/);
});

test("office overview uses three independent status cards", () => {
  assert.match(dashboardSource, /metricsSection/);
  for (const label of ["员工总数", "工作中", "异常"]) {
    assert.match(dashboardSource, new RegExp(label));
  }
  for (const removedLabel of ["在线人数", "会议中", "离线/休息"]) {
    assert.doesNotMatch(dashboardSource, new RegExp(removedLabel));
  }
  assert.match(dashboardStyles, /\.metrics[\s\S]*?grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(dashboardStyles, /\.metrics[\s\S]*?gap: 10px/);
  assert.match(dashboardStyles, /\.metricCard[\s\S]*?min-height: 68px/);
  assert.match(dashboardStyles, /\.metricCard[\s\S]*?border: 1px solid #e4e9f0/);
  assert.match(dashboardStyles, /\.metricCard[\s\S]*?border-radius: 10px/);
  assert.match(dashboardStyles, /\.metricCard[\s\S]*?background: #fff/);
  assert.match(dashboardStyles, /\.metricCopy[\s\S]*?grid-template-areas:[^;]*"label hint"[^;]*"value hint"/);
  assert.match(dashboardStyles, /\.metricHint[\s\S]*?grid-area: hint/);
  assert.match(dashboardSource, /usePreferencesStore/);
  assert.match(dashboardSource, /styles\.darkTheme/);
  assert.match(dashboardStyles, /\.darkTheme \.metricCard/);
  assert.match(dashboardStyles, /\.darkTheme/);
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
  assert.match(dashboardSource, /专注工作/);
  assert.match(dashboardSource, /今日专注/);
  assert.match(dashboardSource, /完成任务/);
  assert.match(dashboardSource, /查看日程/);
  assert.match(dashboardStyles, /\.detailSnapshot[\s\S]*?grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(dashboardStyles, /\.detailActions button:first-child[\s\S]*?background: #2f6bff/);
  assert.ok(dashboardStyles.includes("flex-direction: column"));
  assert.ok(dashboardStyles.includes("border-right: 1px solid #edf1f6"));
});

test("employee detail keeps contact email in the profile and hides redundant modules", () => {
  assert.match(dashboardSource, /Building2 aria-hidden="true"/);
  assert.match(dashboardSource, /MapPin aria-hidden="true"/);
  assert.match(dashboardSource, /Mail aria-hidden="true"/);
  assert.match(dashboardSource, /className=\{styles\.profileMeta\}/);
  assert.match(dashboardSource, /<h3>[\s\S]*styles\.profileStatus/);
  assert.doesNotMatch(dashboardSource, /<DetailSection title="工位信息">/);
  assert.doesNotMatch(dashboardSource, /<DetailSection title="联系方式">/);
  assert.doesNotMatch(dashboardSource, /138\*\*\*\*5678/);
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

test("employee name and status stay together on the right side of each workstation", () => {
  assert.match(dashboardStyles, /\.nameplate[\s\S]*?top: 48%/);
  assert.match(dashboardStyles, /\.nameplate[\s\S]*?left: 82%/);
  assert.match(dashboardStyles, /\.nameplate[\s\S]*?width: max-content/);
  assert.match(dashboardStyles, /\.nameCopy small[\s\S]*?white-space: nowrap/);
});

test("office rooms use standardized desk scenes and a centered CEO office", () => {
  for (const asset of [
    "requirement-room-unified.png",
    "test-design-room-unified.png",
    "automation-room-unified.png",
    "operations-room-unified.png",
    "ai-center-room-unified.png",
    "ceo-office-unified.png",
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
    "requirement-room-unified.png",
    "test-design-room-unified.png",
    "automation-room-unified.png",
    "operations-room-unified.png",
    "ai-center-room-unified.png",
    "ceo-office-unified.png",
  ]) {
    assert.match(dashboardSource, new RegExp(asset.replaceAll(".", "\\.")));
  }
  assert.doesNotMatch(dashboardSource, /WORKSTATION_IMAGES|EMPTY_WORKSTATION_IMAGE/);
  assert.doesNotMatch(dashboardStyles, /\.personHead|\.personBody|\.desk|\.chair/);
});
