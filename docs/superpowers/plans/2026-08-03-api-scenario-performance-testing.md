# 接口场景性能测试 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让性能测试可选择接口场景，并在生成脚本时直接读取场景当前保存版本，以一个 Locust 虚拟用户顺序执行完整场景。

**Architecture:** 保留现有单接口性能测试链路，在 `performance_tests` 中增加互斥的 `scenario_id` 目标；服务层把接口目标或场景当前快照编译为统一的 Locust Plan。场景脚本复用接口自动化现有的变量解析、绑定、提取、断言和失败策略语义，不引入发布、版本选择、Hash 或脚本过期检测。

**Tech Stack:** FastAPI、Pydantic v2、SQLite、Locust、Next.js/React、TypeScript、Node test runner、pytest。

## Global Constraints

- 用户只选择接口场景，不选择场景版本。
- 场景脚本生成时读取当前保存版本。
- 不增加发布、Hash、快照追踪和脚本过期检测。
- 场景修改后由用户手动重新生成性能脚本。
- 保留现有单接口性能测试行为。
- 所有生产代码修改先由失败测试驱动。

---

### Task 1: 性能测试目标联合模型

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/app/schemas/performance_test.py`
- Modify: `apps/backend/app/repositories/performance_test_repo.py`
- Modify: `apps/backend/app/services/performance_testing/service.py`
- Test: `apps/backend/tests/test_performance_testing.py`

**Interfaces:**
- Consumes: 现有 `PerformanceTestCreateIn`、`PerformanceTestUpdateIn` 和 `performance_tests` 表。
- Produces: `target_type: Literal["endpoint", "scenario"]`、可空 `endpoint_id`、可空 `scenario_id`，以及严格互斥校验。

- [ ] **Step 1: 写目标校验失败测试**

增加 Pydantic 与服务测试，覆盖 `scenario` 必须提供 `scenario_id`、`endpoint` 必须提供 `endpoint_id`、两个 ID 不可同时存在。

- [ ] **Step 2: 运行测试确认失败**

Run: `rtk pytest apps/backend/tests/test_performance_testing.py -q`
Expected: FAIL，原因是 schema 尚不接受 `scenario` 或数据库尚无 `scenario_id`。

- [ ] **Step 3: 扩展表结构与迁移**

将新建表约束改为 `target_type IN ('endpoint', 'scenario')`，新增 `scenario_id` 外键；对既有 SQLite 数据库采用安全重建迁移，保留现有性能测试、脚本和运行外键关系。

- [ ] **Step 4: 扩展 schema、repository 与 service**

创建和更新时按目标类型验证引用；列表和详情联表返回 `scenario_name`，序列化返回 `scenario_id`，单接口路径保持不变。

- [ ] **Step 5: 运行目标模型测试确认通过**

Run: `rtk pytest apps/backend/tests/test_performance_testing.py -q`
Expected: PASS。

### Task 2: 当前场景版本解析与编译

**Files:**
- Create: `apps/backend/app/services/performance_testing/scenario_compiler.py`
- Modify: `apps/backend/app/services/performance_testing/script_service.py`
- Modify: `apps/backend/app/agents/performance_testing/script_generation/schemas.py`
- Test: `apps/backend/tests/test_performance_testing.py`

**Interfaces:**
- Consumes: `api_scenarios.published_snapshot_json` 中的当前保存快照和现有接口资产。
- Produces: `compile_scenario_plan(db, project_id, scenario_id, load, data) -> LocustScriptPlan`。

- [ ] **Step 1: 写当前版本与步骤编译失败测试**

覆盖无当前保存版本、无启用请求步骤、接口引用不存在，以及 `api_request`、`wait`、`condition`、`assign` 的计划序列化。

- [ ] **Step 2: 运行测试确认失败**

Run: `rtk pytest apps/backend/tests/test_performance_testing.py -q -k scenario`
Expected: FAIL，原因是尚无场景计划模型和编译器。

- [ ] **Step 3: 增加场景计划类型**

使 `LocustScriptPlan` 按 `target_type` 接受单个 `request` 或场景 `steps`；步骤保留 ID、名称、类型、请求配置、绑定、提取器、断言、失败策略及 `always_run`。

- [ ] **Step 4: 实现最小场景编译器**

读取当前快照，过滤禁用步骤，解析接口引用，合并环境和步骤请求配置，并以步骤 ID/字段路径返回确定性的校验错误。

- [ ] **Step 5: 运行场景编译测试确认通过**

Run: `rtk pytest apps/backend/tests/test_performance_testing.py -q -k scenario`
Expected: PASS。

### Task 3: 多步骤 Locust 脚本与指标

**Files:**
- Modify: `apps/backend/app/services/performance_testing/script_renderer.py`
- Modify: `apps/backend/app/services/performance_testing/validator.py`
- Modify: `apps/backend/app/services/performance_testing/script_service.py`
- Test: `apps/backend/tests/test_performance_testing.py`

**Interfaces:**
- Consumes: Task 2 的场景 `LocustScriptPlan.steps`。
- Produces: 每虚拟用户独立上下文、完整场景事务指标和逐请求步骤指标。

- [ ] **Step 1: 写场景脚本行为失败测试**

覆盖变量隔离、顺序执行、等待、条件、赋值、绑定、提取、断言、`stop/continue/always_run`，并断言场景事务名为 `SCENARIO <name>`、请求步骤名带稳定序号。

- [ ] **Step 2: 运行测试确认失败**

Run: `rtk pytest apps/backend/tests/test_performance_testing.py -q -k locust_scenario`
Expected: FAIL，原因是 renderer 只处理单个请求。

- [ ] **Step 3: 渲染场景运行时**

在生成脚本中为 `HttpUser` 初始化 variables、outputs、data cursor 和 failure state；每次 `execute_target` 执行完整步骤列表，并在迭代末通过 Locust request event 记录场景事务。

- [ ] **Step 4: 扩展脚本校验器**

按目标类型校验 Plan 与源代码一致性；接口目标检查单请求，场景目标检查场景名和每个请求步骤名，同时继续禁止危险导入和调用。

- [ ] **Step 5: 运行脚本与运行链路回归**

Run: `rtk pytest apps/backend/tests/test_performance_testing.py -q`
Expected: PASS，且现有单接口脚本测试不变。

### Task 4: 前端目标选择器

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-test-form.tsx`
- Test: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Consumes: 现有接口场景列表 API 与扩展后的性能测试创建 API。
- Produces: 单接口/接口场景切换、当前版本只读展示，以及互斥的 `endpoint_id`/`scenario_id` 请求体。

- [ ] **Step 1: 写前端契约失败测试**

断言 API 类型包含 `scenario` 和 `scenario_id`，表单调用现有场景列表方法，不包含发布按钮或版本选择器。

- [ ] **Step 2: 运行测试确认失败**

Run: `rtk proxy node --test apps/frontend/tests/performance-testing-contract.test.mjs`
Expected: FAIL，原因是表单仍仅支持接口。

- [ ] **Step 3: 扩展客户端类型与表单**

增加目标类型切换；切换项目时并行加载接口、场景和环境；场景仅允许选择存在当前保存版本的记录，提交时仅发送对应目标 ID。

- [ ] **Step 4: 调整请求配置区域**

接口目标保留请求预览和覆盖编辑；场景目标显示当前版本与步骤摘要，不展示单接口请求覆盖项，负载、数据、门禁配置继续复用。

- [ ] **Step 5: 运行前端契约测试确认通过**

Run: `rtk proxy node --test apps/frontend/tests/performance-testing-contract.test.mjs`
Expected: PASS。

### Task 5: 集成验证

**Files:**
- Verify: `apps/backend/tests/test_performance_testing.py`
- Verify: `apps/backend/tests/test_api_automation_scenarios_tasks.py`
- Verify: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Consumes: Tasks 1-4 的完整实现。
- Produces: 可回归验证的接口与场景性能测试流程。

- [ ] **Step 1: 运行后端定向回归**

Run: `rtk pytest apps/backend/tests/test_performance_testing.py apps/backend/tests/test_api_automation_scenarios_tasks.py -q`
Expected: PASS。

- [ ] **Step 2: 运行前端契约回归**

Run: `rtk proxy node --test apps/frontend/tests/performance-testing-contract.test.mjs`
Expected: PASS。

- [ ] **Step 3: 检查补丁质量**

Run: `rtk git diff --check`
Expected: 无输出且退出码为 0。

- [ ] **Step 4: 审核范围**

确认没有新增发布 API、版本选择器、Hash、快照字段、自动过期检测，也没有覆盖工作区中无关的用户修改。
