import ts from "typescript";

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const sceneSource = readFileSync(new URL("../src/scene/OfficeScene.ts", import.meta.url), "utf8");
const movementSource = readFileSync(new URL("../src/scene/systems/MovementSystem.ts", import.meta.url), "utf8");
const layoutSource = readFileSync(new URL("../src/scene/layout/officeLayout.ts", import.meta.url), "utf8");
const officeAssetsSource = readFileSync(new URL("../src/scene/assets/loadOfficeAssets.ts", import.meta.url), "utf8");
const pageSource = readFileSync(new URL("../src/app/(main)/agents/page.tsx", import.meta.url), "utf8");
const canvasSource = readFileSync(
  new URL("../src/components/ai-testing/silicon-office/office-canvas.tsx", import.meta.url),
  "utf8",
);
const canvasStyles = readFileSync(
  new URL("../src/components/ai-testing/silicon-office/office-canvas.module.css", import.meta.url),
  "utf8",
);
const rosterSource = readFileSync(
  new URL("../src/components/ai-testing/silicon-office/agent-roster.ts", import.meta.url),
  "utf8",
);
const manifestSource = readFileSync(new URL("../src/scene/characters/character-manifest.ts", import.meta.url), "utf8");
const spineCharacterSource = readFileSync(
  new URL("../src/scene/characters/SpineCharacter.ts", import.meta.url),
  "utf8",
);
const agentEntitySource = readFileSync(new URL("../src/scene/entities/AgentEntity.ts", import.meta.url), "utf8");
const deskEntitySource = readFileSync(new URL("../src/scene/entities/DeskEntity.ts", import.meta.url), "utf8");
const animationSystemSource = readFileSync(new URL("../src/scene/systems/AnimationSystem.ts", import.meta.url), "utf8");
const statusLabelSource = readFileSync(new URL("../src/scene/ui/StatusLabel.ts", import.meta.url), "utf8");
const movementModuleSource = ts.transpileModule(movementSource, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const movementModule = await import(
  `data:text/javascript;base64,${Buffer.from(movementModuleSource).toString("base64")}`
);
const layoutModuleSource = ts.transpileModule(layoutSource, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const layoutModule = await import(`data:text/javascript;base64,${Buffer.from(layoutModuleSource).toString("base64")}`);

test("office scene reconciles configured agents instead of only patching initial entities", () => {
  assert.match(sceneSource, /private reconcileAgents\(\)/);
  assert.match(sceneSource, /if \(!existing\)/);
  assert.match(sceneSource, /this\.spawnAgent\(agent\)/);
  assert.match(sceneSource, /if \(incomingIds\.has\(agentId\)\) continue/);
  assert.match(sceneSource, /entity\.destroy\(\{ children: true \}\)/);
});

test("agent count changes rebuild desks and place every agent at its assigned seat", () => {
  assert.match(sceneSource, /previousCount !== this\.agents\.length/);
  assert.match(sceneSource, /this\.rebuildDesks\(this\.buildCurrentDesks\(\)\)/);
  assert.match(sceneSource, /buildDepartmentOfficeLayout/);
  assert.match(sceneSource, /entity\.setPosition\(incoming\.x, incoming\.y\)/);
  assert.doesNotMatch(sceneSource, /scheduleIdleWanders|wanderPoint|idleWanderAt/);
});

test("twelve seats form a spacious four-by-three grid", () => {
  const desks = layoutModule.buildOfficeDesks(12);
  const rows = [...new Set(desks.map((desk) => desk.y))];
  const rowSizes = rows.map((rowY) => desks.filter((desk) => desk.y === rowY).length);

  assert.deepEqual(rowSizes, [4, 4, 4]);
  assert.equal(rows.length, 3);
  assert.equal(rows[0], 220);
  assert.equal(rows[1], 385);
  assert.equal(rows[2], 535);
  assert.ok(desks[0].visualScale < desks[4].visualScale);
  assert.ok(desks[4].visualScale < desks[8].visualScale);
  assert.ok(desks[1].x > desks[5].x);
  assert.ok(desks[2].x < desks[6].x);
});

test("department layout keeps the collaboration order and three seats per department", () => {
  assert.match(layoutSource, /export function buildDepartmentOfficeLayout/);
  assert.match(rosterSource, /buildDepartmentOfficeLayout/);
  assert.match(rosterSource, /department: employee\.department/);
  assert.match(layoutSource, /需求工程/);
  assert.match(layoutSource, /测试设计/);
  assert.match(layoutSource, /自动化工程/);
  assert.match(layoutSource, /运行与分析/);
  assert.match(layoutSource, /其他/);
});

test("office character manifest defines a stable CEO placeholder and every employee profile", () => {
  assert.match(manifestSource, /office-ceo/);
  assert.match(manifestSource, /CEO_CHARACTER_PROFILE/);
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
    assert.match(manifestSource, new RegExp(`\\"${employeeId}\\"`));
  }
  assert.match(manifestSource, /getCharacterProfile/);
  assert.match(manifestSource, /accessorySlots/);
  assert.match(manifestSource, /idleActions/);
});

test("office scene uses the confirmed static background and renders the CEO between department islands", () => {
  assert.match(officeAssetsSource, /silicon-office-bg\.webp/);
  assert.match(sceneSource, /office-ceo/);
  assert.match(sceneSource, /CEO_CHARACTER_PROFILE/);
  assert.match(sceneSource, /OFFICE_DEPARTMENT_ORDER/);
  assert.match(sceneSource, /协作链路/);
  assert.match(sceneSource, /战略调度官/);
});

test("seated characters render behind desks while labels stay in the foreground", () => {
  assert.match(agentEntitySource, /readonly overlayLayer = new Container/);
  assert.match(sceneSource, /entity.overlayLayer.zIndex/);
  assert.match(sceneSource, /addChild\(entity, entity\.overlayLayer\)/);
  assert.match(layoutSource, /SEAT_OFFSET_Y = 26/);
});

test("CEO receives a business-class desk, suit skin, plant, and right-side monitor", () => {
  assert.match(sceneSource, /CEO_DESK/);
  assert.match(sceneSource, /variant: "executive"/);
  assert.match(manifestSource, /skin: "harri"/);
  assert.match(manifestSource, /agentId === CEO_CHARACTER_PROFILE\.employeeId/);
  assert.match(deskEntitySource, /drawExecutiveDesk/);
  assert.match(deskEntitySource, /drawPlant/);
  assert.match(deskEntitySource, /monitorX = 48/);
  assert.match(sceneSource, /x: CEO_DESK.seatX/);
  assert.match(sceneSource, /y: CEO_DESK.seatY/);
});

test("employee desks use left-side seating, right-side monitors, and on-desk title plates", () => {
  assert.match(layoutSource, /seatX: centerX - 32/);
  assert.match(deskEntitySource, /drawStandardDesk/);
  assert.match(deskEntitySource, /monitorX = 34/);
  assert.match(statusLabelSource, /LABEL_CENTER_Y = 28/);
});

test("Spine characters use the manifest skin and render role-specific accessories", () => {
  assert.match(spineCharacterSource, /getCharacterProfile/);
  assert.match(spineCharacterSource, /profile\.skin/);
  assert.match(agentEntitySource, /accessorySlots/);
  assert.match(agentEntitySource, /mountRoleAccessories/);
});

test("human-like idle behavior keeps gestures but removes all sleeping effects", () => {
  assert.match(agentEntitySource, /stableBehaviorSeed/);
  assert.match(agentEntitySource, /profile\.idleActions/);
  assert.match(animationSystemSource, /prefersReducedMotion/);
  assert.doesNotMatch(agentEntitySource, /sleeping|sleep-loop|restIndicator|Z · z/);
  assert.doesNotMatch(animationSystemSource, /entity\.apply\(\{ state: "sleeping"/);
});

test("an incomplete perspective row stays centered", () => {
  const desks = layoutModule.buildOfficeDesks(11);
  const lastRow = desks.slice(8);
  assert.equal(lastRow[0].x + lastRow[2].x, layoutModule.SCENE_WIDTH);
});

test("movement system consumes the full frame budget across queued waypoints", () => {
  const entity = fakeEntity();
  const movement = new movementModule.MovementSystem(10);
  const entities = new Map([["agent-1", entity]]);

  assert.equal(
    movement.start(entity, [
      { x: 10, y: 0 },
      { x: 10, y: 10 },
    ]),
    true,
  );
  assert.deepEqual(movement.update(entities, 1.5), []);
  assert.deepEqual(entity.position, { x: 10, y: 5 });
  assert.equal(entity.data.walkPathIndex, 1);

  assert.deepEqual(movement.update(entities, 0.5), [entity]);
  assert.deepEqual(entity.position, { x: 10, y: 10 });
  assert.equal(entity.data.targetX, undefined);
  assert.equal(entity.data.walkPath, undefined);
});

test("walking is only started by an explicit desk handoff mission", () => {
  assert.match(sceneSource, /private startHandoff\(/);
  assert.match(sceneSource, /incoming\.mission && missionKey/);
  assert.match(sceneSource, /kind: "handoff"/);
  assert.match(sceneSource, /kind: "handoff-return"/);
  assert.match(sceneSource, /entity\.showBubble\(goal\.mission\.message/);
  assert.equal(sceneSource.match(/this\.movement\.start\(/g)?.length, 2);
});

test("employee configuration is refreshed while the workspace remains open", () => {
  assert.match(pageSource, /const EMPLOYEE_POLL_INTERVAL_MS = 10_000/);
  assert.match(pageSource, /const loadEmployees = useCallback/);
  assert.match(pageSource, /apiRequest<SiliconEmployee\[\]>\("\/agents\/employees"\)/);
  assert.match(pageSource, /window\.setInterval\(\(\) => \{/);
  assert.match(pageSource, /员工配置同步失败/);
});

test("office workspace uses a compact metrics header and permanent detail panel", () => {
  assert.doesNotMatch(pageSource, /viewMode/);
  assert.doesNotMatch(pageSource, /列表视图/);
  assert.doesNotMatch(pageSource, /卡片视图/);
  assert.match(pageSource, /status_group=failed/);
  assert.match(pageSource, /今日运行/);
  assert.match(pageSource, /失败/);
  assert.match(pageSource, /selectedEmployee/);
  assert.match(pageSource, /未选择员工/);
  assert.match(pageSource, /EmployeeDetail/);
  assert.doesNotMatch(pageSource, /EmployeeListView/);
  assert.doesNotMatch(pageSource, /placeholder="搜索员工"/);
});

test("active office view mounts one Pixi office scene and preserves DOM employee buttons", () => {
  assert.match(canvasSource, /硅基员工动态办公室/);
  assert.match(canvasSource, /new OfficeScene/);
  assert.match(canvasSource, /scene\.updateAgents\(agents\)/);
  assert.match(canvasSource, /scene\.destroy\(\)/);
  assert.match(canvasSource, /ResizeObserver/);
  assert.match(canvasSource, /aria-label=\{`\$\{agent\.name\}/);
  assert.match(canvasSource, /onAgentSelect\(agent\.id\)/);
  assert.doesNotMatch(canvasSource, /function LayeredChibi/);
  assert.doesNotMatch(canvasSource, /function DeskIllustration/);
  assert.doesNotMatch(canvasSource, /MovementSystem/);
});

test("office canvas keeps a stable aspect ratio and accessible reduced-motion fallback", () => {
  assert.match(canvasStyles, /aspect-ratio: 960 \/ 780/);
  assert.match(canvasStyles, /\.agentHitTarget/);
  assert.match(canvasStyles, /:focus-visible/);
  assert.match(canvasStyles, /prefers-reduced-motion: reduce/);
});

function fakeEntity() {
  return {
    data: { id: "agent-1", state: "idle" },
    position: { x: 0, y: 0 },
    apply(patch) {
      this.data = { ...this.data, ...patch };
    },
    setPosition(x, y) {
      this.position.x = x;
      this.position.y = y;
      this.data.x = x;
      this.data.y = y;
    },
  };
}
