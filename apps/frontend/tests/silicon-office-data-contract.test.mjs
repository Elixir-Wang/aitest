import {
  buildOfficeEmployeeViewModels,
  buildOfficeMetrics,
  tasksForEmployee,
} from "../src/components/ai-testing/silicon-office/employee-projection.ts";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const dashboardSource = readFileSync(
  new URL("../src/components/ai-testing/silicon-office/office-dashboard.tsx", import.meta.url),
  "utf8",
);

const zhangJing = {
  id: "requirement_analysis",
  name: "需求分析师",
  display_name: "张静",
  role: "需求分析师",
  capability_name: "需求分析",
  description: "分析需求",
  department: "需求工程组",
  department_id: "requirement",
  department_name: "需求工程组",
  accent_color: "#e85d4a",
  avatar_asset: "female-yujie-emerald",
  workstation_variant: "female-cream",
  seat_code: "REQ-03",
  task_source_types: ["requirement_analysis_run", "requirement_finalization_run"],
  seat_index: 2,
  registered: true,
};

const testDesigner = {
  ...zhangJing,
  id: "test_case_generation",
  display_name: "张伟",
  role: "测试用例设计师",
  capability_name: "测试用例生成",
  department: "测试设计组",
  department_id: "test-design",
  department_name: "测试设计组",
  avatar_asset: "male-handsome-charcoal",
  workstation_variant: "male-gray",
  seat_code: "TST-02",
  task_source_types: ["test_case_generation_run"],
  seat_index: 4,
};

function task(overrides = {}) {
  return {
    id: "task-1",
    source_type: "requirement_analysis_run",
    source_id: "run-1",
    project_id: "project-1",
    project_name: "示例项目",
    module: "requirement",
    module_label: "需求分析",
    title: "登录模块需求分析",
    status: "running",
    status_label: "分析中",
    status_group: "running",
    summary: "",
    created_at: "2026-07-29T01:00:00Z",
    updated_at: "2026-07-29T01:01:00Z",
    detail_url: "/projects/project-1/requirements/document-1",
    ...overrides,
  };
}

test("tasksForEmployee only returns bound tasks ordered by latest update", () => {
  const result = tasksForEmployee(zhangJing, [
    task({ id: "older", updated_at: "2026-07-29T01:01:00Z" }),
    task({ id: "other-agent", source_type: "test_case_generation_run" }),
    task({ id: "newer", source_type: "requirement_finalization_run", updated_at: "2026-07-29T01:03:00Z" }),
  ]);

  assert.deepEqual(
    result.map((item) => item.id),
    ["newer", "older"],
  );
});

test("employee without tasks is idle and employee with tasks is working", () => {
  const viewModels = buildOfficeEmployeeViewModels([zhangJing, testDesigner], [task()]);

  assert.equal(viewModels[0].state, "working");
  assert.equal(viewModels[0].currentTask?.id, "task-1");
  assert.equal(viewModels[1].state, "idle");
  assert.equal(viewModels[1].currentTask, null);
});

test("office metrics are derived from employee view models", () => {
  const viewModels = buildOfficeEmployeeViewModels([zhangJing, testDesigner], [task()]);

  assert.deepEqual(buildOfficeMetrics(viewModels), {
    total: 2,
    working: 1,
    idle: 1,
  });
});

test("office dashboard loads the real employee catalog and running tasks", () => {
  assert.match(dashboardSource, /apiRequest<SiliconEmployee\[]>\("\/agents\/employees"\)/);
  assert.match(dashboardSource, /`\/tasks\/running\$\{query\}`/);
  assert.match(dashboardSource, /AI_TASK_STARTED_EVENT/);
  assert.match(dashboardSource, /2_000/);
  assert.doesNotMatch(dashboardSource, /const EMPLOYEES/);
  assert.doesNotMatch(dashboardSource, /const METRICS/);
});

test("office dashboard uses employee identity and runtime task data", () => {
  assert.match(dashboardSource, /employee\.display_name/);
  assert.match(dashboardSource, /employee\.role/);
  assert.match(dashboardSource, /employee\.characterId/);
  assert.match(dashboardSource, /employee\.workstation_variant/);
  assert.match(dashboardSource, /employee\.currentTask/);
  assert.match(dashboardSource, /employee\.activeTasks/);
});
