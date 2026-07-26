import ts from "typescript";

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const sceneSource = readFileSync(new URL("../src/scene/OfficeScene.ts", import.meta.url), "utf8");
const movementSource = readFileSync(new URL("../src/scene/systems/MovementSystem.ts", import.meta.url), "utf8");
const layoutSource = readFileSync(new URL("../src/scene/layout/officeLayout.ts", import.meta.url), "utf8");
const pageSource = readFileSync(new URL("../src/app/(main)/agents/page.tsx", import.meta.url), "utf8");
const canvasSource = readFileSync(
  new URL("../src/components/ai-testing/silicon-office/office-canvas.tsx", import.meta.url),
  "utf8",
);
const canvasStyles = readFileSync(
  new URL("../src/components/ai-testing/silicon-office/office-canvas.module.css", import.meta.url),
  "utf8",
);
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
  assert.match(sceneSource, /this\.rebuildDesks\(buildOfficeDesks\(this\.agents\.length\)\)/);
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

test("office workspace keeps the scene primary and moves details behind selection", () => {
  assert.match(pageSource, /viewMode/);
  assert.match(pageSource, /卡片视图/);
  assert.match(pageSource, /列表视图/);
  assert.match(pageSource, /detailOpen/);
  assert.match(pageSource, /onClose=\{\(\) => setDetailOpen\(false\)\}/);
  assert.doesNotMatch(pageSource, /OverviewMetric/);
  assert.doesNotMatch(pageSource, /今日任务/);
  assert.doesNotMatch(pageSource, /placeholder="搜索员工"/);
});

test("active office view is a fixed front-facing employee wall", () => {
  assert.match(canvasSource, /硅基员工动态办公室/);
  assert.match(canvasSource, /function AgentDesk/);
  assert.match(canvasSource, /function LayeredChibi/);
  assert.match(canvasSource, /function DeskIllustration/);
  assert.match(canvasSource, /AI 测试总控/);
  assert.match(canvasSource, /grid-cols-2/);
  assert.match(canvasSource, /xl:grid-cols-4/);
  assert.doesNotMatch(canvasSource, /OfficeScene/);
  assert.doesNotMatch(canvasSource, /MovementSystem/);
  assert.doesNotMatch(canvasSource, /ResizeObserver/);
});

test("employee animation is limited to subtle human micro-motion", () => {
  assert.match(canvasStyles, /@keyframes eye-blink/);
  assert.match(canvasStyles, /@keyframes head-alive/);
  assert.match(canvasStyles, /@keyframes body-breathe/);
  assert.match(canvasStyles, /prefers-reduced-motion: reduce/);
  assert.doesNotMatch(canvasStyles, /translateX\([^0]/);
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
