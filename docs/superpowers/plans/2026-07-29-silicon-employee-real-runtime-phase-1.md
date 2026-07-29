# 硅基员工真实运行接线（阶段一）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留当前硅基员工办公室视觉，将硬编码员工、状态和任务替换为真实员工注册表与现有任务中心数据，并完成“张静—需求分析师—女生工位—需求分析智能体”的稳定绑定。

**Architecture:** 后端 `employee_registry` 继续作为员工目录唯一来源，增加稳定身份和视觉字段；前端通过 `/agents/employees` 与 `/tasks/running` 构建只读办公室视图模型。现有任务状态、权限和 `detail_url` 保持不变，本阶段不新增运行表、SSE 或第二套任务系统。

**Tech Stack:** FastAPI、Python 3.12、pytest、Next.js 16、React 19、TypeScript、Node test runner、Biome。

## Global Constraints

- 不修改现有智能体提示词、模型、技能或运行入口。
- 不新建任务调度系统或活动事件数据库。
- 不展示模型原始隐藏推理。
- 员工默认空闲；存在绑定的 active 任务时显示工作中。
- 状态接口加载失败时显示状态未知，不误判为空闲。
- 保留当前六房间办公室、图片资源、弹窗和右侧详情布局。
- 复用 `/agents/employees`、`/tasks/running`、`ApiTaskItem`、项目上下文和 `AI_TASK_STARTED_EVENT`。
- 不修改工作区内已有的其他用户变更。
- 不创建 Git 提交，除非用户明确要求。

---

### Task 1: 扩展员工注册表身份契约

**Files:**
- Modify: `apps/backend/app/agents/employee_registry.py`
- Modify: `apps/backend/tests/test_agent_employee_registry.py`

**Interfaces:**
- Produces: `list_agent_employees() -> list[dict]` 新增 `display_name`、`role`、`department_id`、`department_name`、`avatar_asset`、`workstation_variant`、`seat_code`。
- Preserves: 现有 `id`、`name`、`capability_name`、`description`、`department`、`accent_color`、`task_source_types`、`seat_index`、`registered`。

- [ ] **Step 1: 写失败测试**
  - 验证所有员工新增展示字段非空。
  - 验证头像和工位值来自受控枚举。
  - 验证 `requirement_analysis` 员工为“张静”、岗位“需求分析师”、女生头像和 `female-cream` 工位。
  - 验证座位编号唯一。

- [ ] **Step 2: 运行测试确认失败**
  - Run: `cd apps/backend && pytest tests/test_agent_employee_registry.py -q`
  - Expected: 缺少 `display_name` 等字段或张静绑定断言失败。

- [ ] **Step 3: 最小实现注册表扩展**
  - 扩展 `AgentEmployeeMetadata`。
  - 为当前 12 个能力配置稳定姓名、岗位、部门 ID、头像、工位和座位编号。
  - `name` 暂时保持岗位名称兼容，新增前端只使用 `display_name` 和 `role`。

- [ ] **Step 4: 运行测试确认通过**
  - Run: `cd apps/backend && pytest tests/test_agent_employee_registry.py -q`
  - Expected: PASS。

### Task 2: 建立前端员工任务投影

**Files:**
- Create: `apps/frontend/src/components/ai-testing/silicon-office/employee-projection.ts`
- Create: `apps/frontend/tests/silicon-office-data-contract.test.mjs`

**Interfaces:**
- Produces: `SiliconEmployee`、`EmployeeRuntimeState`、`OfficeEmployeeViewModel`。
- Produces: `tasksForEmployee(employee, tasks)`、`buildOfficeEmployeeViewModels(employees, tasks)`、`buildOfficeMetrics(viewModels)`。
- Consumes: `ApiTaskItem`。

- [ ] **Step 1: 写失败测试**
  - 使用 Node test runner 静态契约验证新模块存在并导出指定接口。
  - 验证任务按 `task_source_types` 绑定。
  - 验证无任务为空闲、有任务为工作中、最新更新时间任务为主任务。
  - 验证指标来自员工视图模型而非硬编码数字。

- [ ] **Step 2: 运行测试确认失败**
  - Run: `cd apps/frontend && node --test tests/silicon-office-data-contract.test.mjs`
  - Expected: 新模块不存在或导出契约不满足。

- [ ] **Step 3: 实现纯投影函数**
  - 员工状态使用 `idle | working`。
  - API 加载失败由页面使用 `unknown`，不在纯函数中伪造。
  - 主任务取绑定 active 任务中 `updated_at` 最新项。
  - 保留全部绑定任务用于并行任务展示。

- [ ] **Step 4: 运行测试确认通过**
  - Run: `cd apps/frontend && node --test tests/silicon-office-data-contract.test.mjs`
  - Expected: PASS。

### Task 3: 将办公室接入真实数据

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/silicon-office/office-dashboard.tsx`
- Modify: `apps/frontend/src/components/ai-testing/silicon-office/office-dashboard.module.css`
- Modify: `apps/frontend/tests/silicon-office-visual-contract.test.mjs`
- Modify: `apps/frontend/tests/silicon-office-data-contract.test.mjs`

**Interfaces:**
- Consumes: `/agents/employees`、`/tasks/running`、投影函数、认证状态、项目上下文。
- Produces: 当前视觉中的真实房间、工位、指标、员工状态和当前任务详情。

- [ ] **Step 1: 更新失败测试**
  - 禁止 `office-dashboard.tsx` 内出现硬编码 `EMPLOYEES` 和固定 `METRICS` 数字。
  - 要求调用 `/agents/employees` 与 `/tasks/running`。
  - 要求监听 `AI_TASK_STARTED_EVENT` 并使用 2 秒轮询。
  - 要求员工头像、工位、姓名、岗位来自 API 数据。
  - 调整旧视觉测试，移除假“今日专注”“完成任务”“今日工作安排”等断言。

- [ ] **Step 2: 运行测试确认失败**
  - Run: `cd apps/frontend && node --test tests/silicon-office-data-contract.test.mjs tests/silicon-office-visual-contract.test.mjs`
  - Expected: 当前硬编码实现不满足真实数据契约。

- [ ] **Step 3: 实现真实数据加载**
  - 加载认证与项目上下文。
  - 首次并行加载员工目录和运行任务。
  - 每 2 秒刷新任务，10 分钟刷新员工目录。
  - 在 `AI_TASK_STARTED_EVENT` 后立即刷新任务。
  - 请求乱序时只应用最新响应。
  - 未认证时清空数据并停止轮询。

- [ ] **Step 4: 实现数据驱动房间与工位**
  - 保留六个房间的静态背景配置。
  - 根据 `department_id` 分配员工。
  - 根据 `seat_index` 稳定生成工位坐标。
  - CEO 房间继续作为视觉占位，不伪装成后端智能体。
  - 房间占用、员工总数和工作中数量动态计算。

- [ ] **Step 5: 实现真实员工详情**
  - 基本信息展示真实姓名、岗位、部门、工位、能力说明。
  - 当前工作展示真实主任务、项目、状态和更新时间。
  - 并行任务展示其余绑定任务。
  - 有 `detail_url` 时提供“打开任务详情”。
  - 无任务显示“当前空闲，等待任务”。
  - 状态接口失败显示“状态未知”。

- [ ] **Step 6: 运行前端契约测试**
  - Run: `cd apps/frontend && node --test tests/silicon-office-data-contract.test.mjs tests/silicon-office-visual-contract.test.mjs`
  - Expected: PASS。

### Task 4: 类型、格式与回归验证

**Files:**
- Modify if required: Task 1–3 涉及文件

**Interfaces:**
- Produces: 可类型检查、可格式化、后端契约通过的阶段一实现。

- [ ] **Step 1: 运行后端定向测试**
  - Run: `cd apps/backend && pytest tests/test_agent_employee_registry.py tests/test_ai_agents_architecture.py -q`

- [ ] **Step 2: 运行前端 Node 测试**
  - Run: `cd apps/frontend && node --test tests/silicon-office-data-contract.test.mjs tests/silicon-office-visual-contract.test.mjs`

- [ ] **Step 3: 运行 Biome**
  - Run: `cd apps/frontend && npx biome check src/components/ai-testing/silicon-office/office-dashboard.tsx src/components/ai-testing/silicon-office/employee-projection.ts tests/silicon-office-data-contract.test.mjs tests/silicon-office-visual-contract.test.mjs`

- [ ] **Step 4: 运行 TypeScript**
  - Run: `cd apps/frontend && npx tsc --noEmit`

- [ ] **Step 5: 检查变更范围**
  - Run: `git diff --check`
  - 确认未修改用户已有文件，除计划明确列出的路径和本计划文档。

