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
  assert.match(dashboardSource, /硅基员工总数/);
  assert.match(dashboardSource, /空闲/);
  assert.match(dashboardSource, /执行中/);
  assert.match(dashboardSource, /等待人工/);
  assert.match(dashboardSource, /异常/);
});

test("office dashboard keeps the six-room composition and fixed employee detail panel", () => {
  for (const room of ["需求工程组", "测试设计组", "自动化工程组", "运行与分析组", "AI能力中枢", "CEO办公室"]) {
    assert.match(dashboardSource, new RegExp(room));
  }
  assert.match(dashboardSource, /EmployeeDetailPanel/);
  assert.ok(dashboardStyles.includes("grid-template-columns: minmax(0, 1fr) 300px"));
  assert.ok(dashboardStyles.includes("grid-template-columns: repeat(3, minmax(0, 1fr))"));
});

test("office visual has only the four confirmed employee statuses", () => {
  assert.ok(dashboardSource.includes('type EmployeeStatus = "idle" | "running" | "human-waiting" | "error";'));
  assert.doesNotMatch(dashboardSource, /筛选|视图切换|viewMode|filterMode/);
});

test("office visual composes generated room backgrounds with dynamic workstation sprites", () => {
  assert.match(dashboardSource, /OfficeRoom/);
  assert.match(dashboardSource, /Workstation/);
  assert.match(dashboardSource, /next\/image/);
  for (const asset of [
    "requirement-room-empty.png",
    "test-design-room-empty.png",
    "automation-room-empty.png",
    "operations-room-empty.png",
    "ai-center-room-empty.png",
    "ceo-office.png",
    "workstation-empty.png",
    "workstation-male-gray.png",
    "workstation-male-white.png",
    "workstation-female-cream.png",
  ]) {
    assert.match(dashboardSource, new RegExp(asset.replaceAll(".", "\\.")));
  }
  assert.doesNotMatch(dashboardStyles, /\.personHead|\.personBody|\.desk|\.chair/);
});
