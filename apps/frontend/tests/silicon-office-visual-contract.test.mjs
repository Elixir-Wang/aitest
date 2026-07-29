import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
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
  assert.match(dashboardSource, /空闲/);
  assert.match(dashboardSource, /状态未知/);
});

test("office overview uses three independent status cards", () => {
  assert.match(dashboardSource, /metricsSection/);
  for (const label of ["员工总数", "工作中", "空闲"]) {
    assert.match(dashboardSource, new RegExp(label));
  }
  for (const removedLabel of ["在线人数", "会议中", "离线/休息", "较昨日", "75.0%", "3.1%"]) {
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
  assert.match(dashboardSource, /PERSON_PORTRAIT_ASSETS/);
  assert.match(dashboardSource, /profileAvatarImage/);
  assert.match(dashboardSource, /当前工作/);
  assert.match(dashboardSource, /并行任务/);
  assert.match(dashboardSource, /打开任务详情/);
  assert.doesNotMatch(dashboardSource, /今日专注|完成任务|今日会议|今日工作安排/);
  assert.match(dashboardStyles, /\.detailSnapshot[\s\S]*?grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(dashboardStyles, /\.detailActions button:first-child[\s\S]*?background: #2f6bff/);
  assert.ok(dashboardStyles.includes("flex-direction: column"));
  assert.ok(dashboardStyles.includes("border-right: 1px solid #edf1f6"));
});

test("employee detail keeps capability and workstation metadata without fake contact data", () => {
  assert.match(dashboardSource, /Building2 aria-hidden="true"/);
  assert.match(dashboardSource, /MapPin aria-hidden="true"/);
  assert.match(dashboardSource, /className=\{styles\.profileMeta\}/);
  assert.match(dashboardSource, /<h3>[\s\S]*styles\.profileStatus/);
  assert.match(dashboardSource, /employee\.capability_name/);
  assert.match(dashboardSource, /employee\.seat_code/);
  assert.doesNotMatch(dashboardSource, /@siliconflow\.ai/);
  assert.doesNotMatch(dashboardSource, /138\*\*\*\*5678/);
});

test("department occupancy is derived from registered employees", () => {
  assert.match(dashboardSource, /room\.employees\.length/);
  assert.match(dashboardSource, /buildOfficeRooms/);
  assert.match(dashboardSource, /const ROOM_CAPACITY = 4/);
  assert.match(dashboardSource, /slice\(0, ROOM_CAPACITY\)/);
  assert.doesNotMatch(dashboardSource, /room\([^\n]+6, 7/);
});

test("office visual uses real idle and working states with unknown fallback", () => {
  assert.match(dashboardSource, /EmployeeRuntimeState/);
  assert.match(dashboardSource, /statusUnknown/);
  assert.doesNotMatch(dashboardSource, /human-waiting|EmptyWorkstation|emptyLabel/);
  assert.doesNotMatch(dashboardSource, /筛选|视图切换|viewMode|filterMode/);
  assert.match(dashboardSource, /<Nameplate employee=\{employee\} statusUnknown=\{statusUnknown\} \/>/);
  assert.match(
    dashboardSource,
    /function Nameplate[\s\S]*?<small>[\s\S]*?statusUnknown \? "[^"}]+" : stateLabel\(employee\.state\)[\s\S]*?<\/small>/,
  );
});

test("employee name and status stay together on the right side of each workstation", () => {
  assert.match(dashboardStyles, /\.nameplate[\s\S]*?top: 88%/);
  assert.match(dashboardStyles, /\.nameplate[\s\S]*?left: 130%/);
  assert.match(dashboardStyles, /\.nameplate[\s\S]*?width: max-content/);
  assert.match(dashboardStyles, /\.nameCopy small[\s\S]*?white-space: nowrap/);
});

test("department header renders before the room scene", () => {
  assert.match(
    dashboardSource,
    /<header className=\{styles\.roomHeader\}>[\s\S]*?<\/header>[\s\S]*?<div className=\{styles\.roomScene\}>/,
  );
});

test("office rooms use original furniture scenes and a centered CEO office", () => {
  for (const roomId of ["requirement", "test-design", "automation", "operations", "ai-center"]) {
    assert.match(dashboardSource, new RegExp(`roomConfig\\("${roomId}"`));
  }
  assert.match(dashboardSource, /-room-furniture-clean\.png/);
  assert.match(dashboardSource, /-room-monitor-foreground\.png/);
  assert.match(dashboardSource, /ceo-office-unified\.png/);
  assert.match(dashboardStyles, /\.executiveHotspot[\s\S]*?top: 38%/);
});

test("office visual uses unique employee assets and layered desk occlusion", () => {
  assert.match(dashboardSource, /OfficeRoom/);
  assert.match(dashboardSource, /Workstation/);
  assert.match(dashboardSource, /next\/image/);
  assert.match(dashboardSource, /personBodyAsset\(employee\)/);
  assert.match(dashboardSource, /personHandsAsset\(employee\)/);
  assert.match(dashboardSource, /PERSON_BODY_ASSETS/);
  assert.match(dashboardSource, /PERSON_HANDS_ASSETS/);
  for (const employeeId of [
    "document_editor",
    "requirement_standardization",
    "requirement_analysis",
    "knowledge_query",
    "test_case_generation",
    "test_point_generation",
    "api_test_generation",
    "api_scenario_orchestration",
    "ui_test_generation",
    "page_exploration",
    "performance_script_generation",
    "performance_report_analysis",
  ]) {
    assert.match(dashboardSource, new RegExp(`"${employeeId}"`));
    assert.match(dashboardSource, new RegExp(`${employeeId}-body\\.png`));
    assert.match(dashboardSource, new RegExp(`${employeeId}-hands\\.png`));
  }
  assert.match(dashboardSource, /className=\{styles\.personBodyImage\}/);
  assert.match(dashboardSource, /className=\{styles\.personHandsImage\}/);
  assert.match(dashboardSource, /className=\{styles\.deskForeground\}/);
  assert.match(dashboardStyles, /\.personBodyLayer[\s\S]*?z-index: 3/);
  assert.match(dashboardStyles, /\.deskForeground[\s\S]*?z-index: 4/);
  assert.match(dashboardStyles, /\.personHandsLayer[\s\S]*?z-index: 5/);
  assert.match(dashboardStyles, /\.personHandsImage[\s\S]*?clip-path: inset\(82% 0 0\)/);
  assert.match(dashboardStyles, /\.monitorForeground[\s\S]*?z-index: 6/);
  assert.match(dashboardStyles, /\.workstation[\s\S]*?z-index: 7/);
  assert.doesNotMatch(dashboardSource, /PERSONALIZED_WORKSTATION_ASSETS|personalizedWorkstationAsset/);
  assert.doesNotMatch(dashboardSource, /workstation-[^"\n]+-avatar\.png/);
  assert.doesNotMatch(dashboardSource, /PERSON_BODY_ASSETS\[employee\.avatar_asset\]/);
  assert.doesNotMatch(dashboardSource, /PERSON_HANDS_ASSETS\[employee\.avatar_asset\]/);
  assert.match(dashboardStyles, /\.roomScene[\s\S]*?z-index: 2[\s\S]*?pointer-events: none/);
  assert.match(dashboardStyles, /\.workstation[\s\S]*?pointer-events: auto/);
});

test("office rooms do not expose a click-to-expand interaction", () => {
  assert.doesNotMatch(dashboardSource, /roomExpandHotspot/);
  assert.doesNotMatch(dashboardSource, /expandedRoomId|setExpandedRoomId|expandedRoom/);
  assert.doesNotMatch(dashboardSource, /<Dialog/);
  assert.doesNotMatch(dashboardStyles, /\.roomExpandHotspot/);
});

test("office ships twenty unique character identities with matching layered assets", () => {
  const characterIdsMatch = dashboardSource.match(/const BUILT_IN_CHARACTER_IDS = \[([\s\S]*?)\] as const;/);
  assert.ok(characterIdsMatch);

  const characterIds = [...characterIdsMatch[1].matchAll(/"([^"]+)"/g)].map((match) => match[1]);
  assert.equal(characterIds.length, 20);
  assert.equal(new Set(characterIds).size, 20);

  for (const characterId of characterIds) {
    for (const layer of ["body", "hands", "portrait"]) {
      assert.match(dashboardSource, new RegExp(`${characterId}-${layer}\\.png`));
      assert.equal(
        existsSync(new URL(`../public/assets/silicon-office-v2/people/${characterId}-${layer}.png`, import.meta.url)),
        true,
      );
    }
  }
});

test("office rooms resolve department-local seat layouts by employee seat index", () => {
  assert.match(dashboardSource, /ROOM_SEAT_LAYOUTS/);
  for (const roomId of ["requirement", "test-design", "automation", "operations", "ai-center"]) {
    assert.match(dashboardSource, new RegExp(`"?${roomId}"?\\s*:`));
  }
  assert.match(dashboardSource, /employee\.seat_index/);
  assert.doesNotMatch(dashboardSource, /SEAT_POSITIONS\[index\]/);
});
