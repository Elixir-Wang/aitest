# 00-12 AI测试系统 - 任务中心 PRD

> **基线日期**：2026-07-26
> **事实源**：
> - 后端：`apps/backend/app/api/v1/tasks.py`、`apps/backend/app/services/task_service.py`
> - 启动恢复：`apps/backend/app/main.py`（`@app.on_event("startup")`）
> - 前端：`apps/frontend/src/app/(main)/tasks/page.tsx`
> - 类型契约：`apps/frontend/src/lib/api-client.ts`（`ApiTaskItem`、`ApiTaskList`）
> - 数据表：`apps/backend/app/seed/schema.py`
> **状态标签**：`已实现`

---

## 1. 范围与目标

任务中心是 AI 测试系统的「异步任务聚合视图」，统一展示由后台 Worker、Agent / Long-running 调用触发的运行型任务，使用户能在一个页面里观察到这些工作的实时状态、历史记录与产物入口。

**核心目标**

- 提供统一的「任务中心」聚合列表，使用户不需进入各业务模块即可看到所有进行中、需要人工或失败的任务。
- 把每一类任务的源记录（运行表）按统一的字段形态汇总，避免前端为每类任务单独建模。
- 支持按项目 / 状态组 / 模块 / 关键字筛选，以及分页读取，适合长时间累计的任务量。
- 支持启动时与服务调用时的任务恢复，保证服务重启或心跳超时不会让任务永远停留在「运行中」假态。
- 暴露一个稳定的最简任务视图契约 `ApiTaskItem`，让任务详情可与业务模块详情互为补充而非互为替代。

**职责边界**

| 在范围内 | 不在范围内 |
| --- | --- |
| 跨模块聚合任务列表 | 任务本身的业务执行（由 `*_service` / `*_repo` 负责） |
| 任务筛选 / 检索 / 分页 | 任务重试、取消的写入接口（任务中心仅查询，不提供 retry/cancel 入口） |
| 启动恢复与心跳超时的状态校正 | 任务事件流日志的写读（事件由 `operation_log_service` 记录） |
| 任务详情弹窗（只读快照） | 业务详情页（按 `detail_url` 跳转） |

---

## 2. 聚合源

任务中心不维护独立的 `task_runs` 表，而是由 `task_service._collect_visible_tasks` 在请求时把以下 9 类运行记录聚合为统一形态的 `ApiTaskItem`：

| # | source_type | 运行表 | 模块（`module`）| 模块展示（`module_label`）| 默认跳转（`detail_url`）|
| --- | --- | --- | --- | --- | --- |
| 1 | `requirement_analysis_run` | `requirement_analysis_runs` | `requirement` | 需求分析 | `/projects/{project_id}/requirements/{document_id}` |
| 2 | `exploration_run` | `exploration_runs` | `exploration` | 站点探索 | `/projects/{project_id}/exploration/{run_id}` |
| 3 | `test_case_generation_run` | `test_case_generation_runs` | `test_case` | 测试用例 | `/test-cases?set={test_case_set_id}` |
| 4 | `test_point_generation_run` | `test_point_generation_runs` | `requirement` | 测试点 | `/projects/{project_id}/requirements/{document_id}?tab=test-points` |
| 5 | `ui_automation_generation_run` | `ui_automation_generation_runs` | `ui_automation` | UI 自动化生成 | `/projects/{project_id}/automation/ui?generationRun={run_id}` |
| 6 | `ui_automation_execution_run` | `ui_automation_execution_runs` | `ui_automation` | UI 自动化执行 | `/projects/{project_id}/automation/ui?executionRun={run_id}` |
| 7 | `api_automation_generation_run` | `api_generation_runs` | `api_automation` | 接口自动化生成 | `/projects/{project_id}/automation/api?generationRun={run_id}` |
| 8 | `api_automation_run` | `api_automation_runs` | `api_automation` | 接口自动化执行 | `/projects/{project_id}/automation/api?run={run_id}` |
| 9 | `performance_test_run` | `performance_test_runs` | `performance_testing` | 性能测试运行 | `/projects/{project_id}/performance-tests/{test_id}/runs/{run_id}` |

> **实现注意（2026-07-26 当前事实）**
> - 当前 `task_service._collect_visible_tasks` 直接读取 `exploration_runs`、`source_document_file_mappings`（作为 `requirement_file`）、`requirement_analysis_runs`、`requirement_finalization_runs`、`test_case_generation_runs`、`test_point_generation_runs`、`api_generation_runs`、`api_script_generation_runs`、`api_automation_runs`，共 9 个数据源，其中 7 类进入 `STATUS_META_BY_SOURCE_TYPE`（作为 "正在运行" 指示视图）：
>   - `exploration_run`、`requirement_file`、`requirement_analysis_run`、`requirement_finalization_run`、`test_case_generation_run`、`test_point_generation_run`、`api_automation_generation_run`、`api_script_generation_run`、`api_automation_run`
> - `performance_test_runs` 与 `ui_automation_*_runs` 当前 **尚未汇入** 任务中心聚合源，由各自业务页直接管理；但它们的 stale / interrupted 恢复已纳入服务启动流程（见第 6 节）。
> - 任务 ID 在聚合视图里使用形如 `<source_type>:<source_id>` 的合成键，便于在同一列表中区分不同 source_type 的同名记录。

每类任务从原始表投影出以下核心字段：

| 聚合字段 | 来源 |
| --- | --- |
| `id` | 合成 `<source_type>:<source_id>` |
| `source_type` / `source_id` | 原始运行表主键 |
| `project_id` / `project_name` | 来自 `projects` 表，受当前 actor 可见项目过滤 |
| `module` / `module_label` | 静态枚举 |
| `title` | 文档名 / 用例集名 / 探索标题 / 性能测试标题等业务字段 |
| `status` | 原始运行表的 `status` 字段（枚举见 §3）|
| `status_label` | 经 `STATUS_META_BY_SOURCE_TYPE[source_type].get(status)` 映射的中文标签 |
| `status_group` | 由原始 status 经映射表映射到 4 个状态组（见 §3）|
| `summary` | 失败原因或业务摘要（探索：result_summary；接口：error_message / command_summary）|
| `created_at` / `updated_at` | 原始表时间戳，用于排序与保留窗口判断 |
| `detail_url` | 静态拼接的回跳地址 |

---

## 3. 状态映射

任务中心对外暴露统一的 4 状态组（`status_group`），状态组之间不重叠：

| 状态组 | 含义 | 包含的原始 status（按 source_type）|
| --- | --- | --- |
| `running` | 运行态，正在执行 | 各模块的 `queued` / `running` / `pending`（仅 `requirement_file`）/ `processing`（仅 `requirement_file`）/ `stopping` |
| `waiting` | 等待人工 | `requirement_analysis_run` 的 `needs_clarification` |
| `failed` | 失败态 | 各模块的 `failed` / `blocked`（仅 exploration_run）|
| `completed` | 完成态 | `completed` / `passed` / `cancelled` / `interrupted` / `success` / `warning`（仅 `requirement_file`）|

> `pending` 仅 `exploration_run` 与 `requirement_file` 出现：探索的 `pending` 表示「尚未提交到 worker」，与「已入队」区别对待（在 `/tasks/running` 中 **不计入 active**，避免把草稿任务误当作运行中任务）。

### 3.1 原始 status → 状态组 → 中文标签 映射表

| source_type | running | waiting | failed | completed |
| --- | --- | --- | --- | --- |
| `exploration_run` | `pending` (待启动 — 注：active 视图排除)、`queued` (排队中)、`running` (探索中)、`stopping` (停止中) | — | `blocked` (探索阻塞)、`failed` (探索失败) | `cancelled` (已取消)、`interrupted` (已中断)、`completed` (已完成) |
| `requirement_file` | `pending` (等待转换)、`processing` (转换中) | — | `failed` (转换失败) | `success` (转换成功)、`warning` (转换完成) |
| `requirement_analysis_run` | `queued` (排队中)、`running` (分析中)、`stopping` (停止中) | `needs_clarification` (等待澄清) | `failed` (分析失败) | `cancelled` (已取消)、`completed` (已完成) |
| `requirement_finalization_run` | `running` (转换中) | — | `failed` (转换失败) | `completed` (转换完成) |
| `test_case_generation_run` | `queued` (排队中)、`running` (生成中) | — | `failed` (生成失败) | `completed` (生成完成) |
| `test_point_generation_run` | `queued` (排队中)、`running` (生成中) | — | `failed` (生成失败) | `completed` (生成完成) |
| `api_automation_generation_run` | `queued` (排队中)、`running` (生成中) | — | `failed` (生成失败) | `completed` (生成完成)、`cancelled` (已取消)、`interrupted` (已中断) |
| `api_script_generation_run` | `queued` (排队中)、`running` (生成中) | — | `failed` (生成失败) | `completed` (生成完成)、`cancelled` (已取消)、`interrupted` (已中断) |
| `api_automation_run` | `queued` (排队中)、`running` (执行中) | — | `failed` (执行失败) | `passed` (执行通过)、`cancelled` (已取消)、`interrupted` (已中断) |

> `performance_test_run` 当前 enum（`created` / `starting` / `running` / `stopping` / `completed` / `stopped` / `failed` / `cancelled`）尚未注入 `STATUS_META_BY_SOURCE_TYPE`，详情见 §2 的「实现注意」。

---

## 4. 筛选与分页

`GET /api/v1/tasks` 支持以下 query 参数：

| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `project_id` | string | 否 | — | 精确匹配，限定任务来源项目 |
| `status_group` | string | 否 | — | 取值：`running` / `waiting` / `failed` / `completed` |
| `module` | string | 否 | — | 取值见 §2，例如 `requirement` / `exploration` / `test_case` / `ui_automation` / `api_automation` |
| `keyword` | string | 否 | — | 大小写不敏感，命中 `project_name` / `module_label` / `title` / `status_label` / `summary` 任一字段 |
| `page` | int | 否 | 1 | ≥ 1 |
| `page_size` | int | 否 | 50 | 范围 1 – 100 |

**返回结构**

```json
{
  "items":  [/* ApiTaskItem[]，按 updated_at DESC, created_at DESC, id DESC */],
  "total":   <int>,        // 命中总数，含当前页之外
  "page":    <int>,
  "page_size": <int>
}
```

**保留窗口**

- `TASK_RETENTION_DAYS = 10`：原始 `updated_at` 早于「当前时间 − 10 天」的任务被自动从列表过滤掉。
- 该过滤在 `_is_retained_task` 内执行，仅对 `/tasks` 生效；`/tasks/running` 仅返回 active 任务，不进行保留窗口判断（运行中任务不应被过期清理）。

**项目可见性**

- 调用方 actor 的 `role` 为 `admin` 或 `guest`，或 `project_scope == "全部项目"`：可看到所有 `status != 'archived'` 的项目。
- 否则：仅看到 `project_scope` 字段命名的项目。
- 该过滤在 `_visible_project_names` 中执行。

---

## 5. 任务详情弹窗

任务中心首页以表格展示，点击「查看」按钮打开只读任务详情弹窗，字段全部由 `ApiTaskItem` 提供。

| 字段 | 来自 | 示例 |
| --- | --- | --- |
| 任务名称 | `title` | 登录需求 |
| 所属项目 | `project_name` | 电商系统 |
| 任务种类 | `module_label` | 需求分析 |
| 状态 | `status_label` (渲染为 `StatusBadge`：`taskStatusTone(status_group, status)`) | 分析中 |
| 更新时间 | `updated_at` | 2026-07-26 09:00 |
| 任务 ID | `source_id` | req-run-001 |
| 任务来源 | `source_type` → 中文映射 | AI 需求分析任务 |
| 摘要 | `summary` | 需求分析智能体正在分析。|
| 详情地址 | `detail_url` | `/projects/{pid}/requirements/{did}` |

> 弹窗右上角内置「一键复制」按钮（`OneClipboard`），用于把上述字段以 `key：value` 行文本复制到剪贴板，便于在测试工程师与开发间流转。

**局限**

- 详情弹窗是「任务快照」，不展示输入参数 JSON、执行时间线、Worker 日志或重试入口。这些信息需要跳转到 `detail_url` 对应的业务模块详情页查看。
- `requirement_finalization_run`、`test_point_generation_run`、`api_script_generation_run`、`ui_automation_*`、`performance_test_run` 等 source_type 当前未进入任务中心聚合时，其详情仍可由业务详情页直接打开，弹窗字段会回退为基本信息。

---

## 6. 启动恢复（`recover_interrupted_*` 系列）

`apps/backend/app/main.py` 的 `@app.on_event("startup")` 启动钩子按以下顺序执行恢复：

```python
with connect() as db:
    run_repo.recover_stale_runs(db)              # 性能测试运行（心跳超时 → failed）
recover_interrupted_exploration_runs()           # 探索
task_service.recover_interrupted_requirement_analysis_runs()   # 需求分析
test_case_service.recover_interrupted_test_case_generation_runs()  # 测试用例生成
test_point_service.recover_interrupted_generation_runs()        # 测试点生成
api_automation_service.recover_interrupted_api_automation_tasks() # 接口自动化（生成/脚本/执行）
ui_automation_service.recover_interrupted_ui_automation_tasks()  # UI 自动化（生成/执行）
ui_automation_service.prepare_background_tasks()
retention_cleanup_service.schedule_cleanup()
```

### 6.1 启动时立即触发的恢复

| 模块 | 入口 | 行为 |
| --- | --- | --- |
| 性能测试运行 | `run_repo.recover_stale_runs(db, timeout_minutes=5)` | 把 `performance_test_runs.status IN ('starting', 'running')` 且 `updated_at` 早于「now − 5 分钟」的记录批量标记为 `failed`，错误码 `PERFORMANCE_RUN_TIMEOUT`，并写一条 `worker_timeout` 事件。 |
| 站点探索 | `page_exploration_service.recover_interrupted_exploration_runs` | 把 `exploration_runs.status IN ('queued', 'running', 'stopping')` 的记录置为 `interrupted`，写入 `result_summary = "服务已重启..."` 并记录 operation log。 |
| 需求分析 | `task_service.recover_interrupted_requirement_analysis_runs` | 同上，把 `requirement_analysis_runs` 中的 active 记录置 `failed`，`failure_reason="服务已重启..."`。 |
| 测试用例生成 | `test_case_service.recover_interrupted_test_case_generation_runs` | 标记 active `test_case_generation_runs` 为失败。 |
| 测试点生成 | `test_point_service.recover_interrupted_generation_runs` | 标记 active `test_point_generation_runs` 为失败。 |
| 接口自动化（生成/脚本/执行） | `api_automation_service.recover_interrupted_api_automation_tasks` | 一次性恢复 `api_generation_runs`、`api_script_generation_runs`、`api_automation_runs`。 |
| UI 自动化（生成/执行） | `ui_automation_service.recover_interrupted_ui_automation_tasks` | 一次性恢复 `ui_automation_generation_runs`、`ui_automation_execution_runs`。 |

### 6.2 运行时的 stale 恢复

- `task_service.recover_stale_requirement_analysis_runs` 在 `list_tasks` / `list_running_tasks` / `get_task_by_source` / `get_task_by_source_for_event` 入口被调用，以「运行超过 `REQUIREMENT_ANALYSIS_RUN_TIMEOUT_MINUTES=120` 分钟」为阈值，将对应记录批量置 `failed`，`failure_reason="需求分析运行超过 120 分钟..."`。

### 6.3 失败记录的事件化

所有 `recover_interrupted_*` / `recover_stale_*` 写操作均通过 `operation_log_service.record_task_event` 写一条 operation log（`task_id`、`action` 如 `fail_requirement_analysis` / `interrupt_exploration`、`result=failed`、`failure_reason`），便于审计与事件流回放。

---

## 7. 任务表结构

> **结论**：任务中心 **没有独立 `task_runs` 表**，所有任务聚合都是对各业务运行表的按需 JOIN 与映射。

| source_type | 物理表 | 关键列（来自 schema.py）|
| --- | --- | --- |
| `requirement_file` | `source_document_file_mappings` | `id`、`document_id`、`original_filename`、`conversion_status`、`conversion_summary`、`created_at` |
| `requirement_analysis_run` | `requirement_analysis_runs` | `id`、`project_id`、`document_id`、`status`、`summary`、`failure_reason`、`created_at`、`updated_at` |
| `requirement_finalization_run` | `requirement_finalization_runs` | `id`、`project_id`、`document_id`、`status`、`summary`、`failure_reason`、`created_at`、`updated_at` |
| `exploration_run` | `exploration_runs` | `id`、`project_id`、`environment_id`、`title`、`status`、`result_summary`、`created_at`、`updated_at` |
| `test_case_generation_run` | `test_case_generation_runs` | `id`、`test_case_set_id`、`task_id`、`status`、`error_message`、`created_at`、`updated_at` |
| `test_point_generation_run` | `test_point_generation_runs` | `id`、`task_id`、`status`、`error_message`、`created_at`、`updated_at` |
| `api_automation_generation_run` | `api_generation_runs` | `id`、`project_id`、`task_id`、`status`、`generation_goal`、`error_message` |
| `api_script_generation_run` | `api_script_generation_runs` | `id`、`project_id`、`task_id`、`status`、`error_message` |
| `api_automation_run` | `api_automation_runs` | `id`、`project_id`、`task_id`、`status`、`command_summary`、`error_message` |
| `ui_automation_generation_run` | `ui_automation_generation_runs` | `id`、`project_id`、`task_id`、`status`、`created_at`、`updated_at` |
| `ui_automation_execution_run` | `ui_automation_execution_runs` | `id`、`project_id`、`asset_id`、`environment_id`、`task_id`、`status`、`started_at`、`finished_at` |
| `performance_test_run` | `performance_test_runs` | `id`、`project_id`、`performance_test_id`、`script_id`、`status`、`worker_id`、`error_code`、`error_message`、`report_directory`、`started_at`、`finished_at`、`created_by`、`created_at`、`updated_at` |

每张物理表自带的 `task_id` 文本列承载「任务调度/外部异步调用」所产生的业务 task identifier（如 `ui_generation:<run_id>`）；任务中心聚合视图里的 `id` 是一个 **合成键**（`source_type:source_id`），**不会** 与物理表里的 `task_id` 一致。

---

## 8. API 路由清单

模块前缀：`/api/v1/tasks`，鉴权：`Depends(current_user)`。

| 方法 | 路径 | 说明 | 关键 query |
| --- | --- | --- | --- |
| GET | `/tasks/running` | 仅返回 active 任务（`status_group == "running"` 且在 `RUNNING_INDICATOR_SOURCE_TYPES` 集合内），按 `created_at` 倒序；用于全局顶部「正在运行」指示器 | `project_id?` |
| GET | `/tasks` | 任务中心列表，支持筛选 + 分页；先做 stale 恢复再聚合 | `project_id?`、`status_group?`、`module?`、`keyword?`、`page=1`、`page_size=50` |

返回元素统一的 `ApiTaskItem`：

```ts
type ApiTaskItem = {
  id: string;
  source_type: string;
  source_id: string;
  project_id: string;
  project_name: string;
  module: string;
  module_label: string;
  title: string;
  status: string;
  status_label: string;
  status_group: "running" | "waiting" | "failed" | "completed";
  summary: string;
  created_at: string;
  updated_at: string;
  detail_url: string;
};

type ApiTaskList = { items: ApiTaskItem[]; total: number; page: number; page_size: number };
```

> 当前 `task_service.py` 同时暴露 `get_task_by_source(actor, source_type, source_id)` 与 `get_task_by_source_for_event(...)` 作为模块内部工具方法，**未挂到 `/tasks/*` 路由**。模块详情页或 operation log 模块如需直接定位任务，调用前者。

---

## 9. 前端页面清单

| 路径 | 文件 | 模块 |
| --- | --- | --- |
| `/tasks` | `apps/frontend/src/app/(main)/tasks/page.tsx` | 任务中心首页 |

**页面结构**

- `PageShell`：标题「任务中心」、`projectScope="all"`、面包屑 `moduleBreadcrumbs("tasks")`。
- 描述：「汇总需求分析、探索、知识库、用例、UI 自动化和失败诊断任务。」（注：实际聚合源见 §2 的「实现注意」）
- 顶部 4 个 `MetricCard`：全部任务 / 运行中 / 等待人工 / 失败任务 — 数据来自当前页 `tasks` 的 `status_group` 计数。
- `ListToolbar`：搜索框（`keyword`），提交时回 `page = 1`。
- 表格列：任务名称（溢出 Tooltip）、任务种类、项目、状态（`StatusBadge`）、更新时间、操作（查看 → 打开详情弹窗）。
- 列宽采用 `table-fixed`，保证信息密集型展示稳定。
- 分页：每页 10 / 15 / 20 / 50 / 100 可选，`page_size` 仅控制前端不写入 query 时也走 `page_size` 上限 100。
- 「全部任务 / 等待人工 / 失败任务」tab 仅用于视图过滤，**实际筛选由 query 在后端执行**。
- 任务详情弹窗（`Dialog`）：展示 §5 的 9 个字段 + 一键复制。

**前端与权限配合**

- `useProjectContextStore.scope === "project"` 且有 `currentProjectId` 时，列表请求自动附 `project_id`。
- 仅 `auth-store.token` 已 hydrate 时才发起请求，避免裸调用 401。

---

## 10. 验收规则

### 10.1 功能验收

- **聚合覆盖**：`/tasks` 返回的任务集合覆盖 §2 中已入库的 9 个 `source_type`；缺失的源须在文档「实现注意」处给出原因（性能测试 / UI 自动化运行）或列入排期。
- **状态组互斥**：每个 `ApiTaskItem.status_group` ∈ {`running`, `waiting`, `failed`, `completed`}，且 `status_label` 与 `STATUS_META_BY_SOURCE_TYPE[source_type].get(status)` 一致；未命中映射时回退为 `status_group = status`，`status_label = status`。
- **筛选生效**：分别用 `project_id=…`、`status_group=…`、`module=…`、`keyword=…` 任一组合请求 `/tasks`，命中行集合 = 客户端直连 SQLite 同等查询结果。
- **分页正确**：`page`、`page_size` 越界时被夹紧到合法区间（`page=1`，`page_size ≤ 100`）；`total` 等于过滤后的命中总数，`items.length == page_size`（除最后一页）。
- **保留窗口**：构造 `updated_at = now - 11 days` 的 active / completed 任务，`/tasks` 不返回该任务，但 `/tasks/running` 仍能反映其当前状态（如为 active）。
- **pending 排除**：`exploration_runs.status='pending'` 时 `/tasks/running` **不**返回该任务，但 `/tasks?status_group=running` 会以 `status_label="待启动"` 列在分组中（便于审计）。
- **运行指示器**：`/tasks/running` 只包含 `source_type ∈ RUNNING_INDICATOR_SOURCE_TYPES` 且 `is_active_task_status(source_type, status) == True` 的任务；`requirement_analysis_run.status='needs_clarification'` 不会被当作 running（应在 `waiting` 组）。
- **项目可见性**：`actor.role=guest` 或 `actor.project_scope="全部项目"` 时，列表覆盖所有非归档项目；其他 actor 仅看到 `actor.project_scope` 命名的项目。
- **详情弹窗字段**：弹窗字段集合 == §5 表，且「状态」字段渲染为 `StatusBadge`，状态文案来自 `status_label`。
- **聚合来源不存在**：下游表缺失（如早期部署未升级到 `requirement_finalization_runs`）时通过 `_table_exists` 安全跳过，仅打印/空集合，不抛错。

### 10.2 恢复验收

- **启动恢复**：手动在 `requirement_analysis_runs` / `exploration_runs` / `test_case_generation_runs` / `test_point_generation_runs` / `api_generation_runs` / `api_script_generation_runs` / `api_automation_runs` / `ui_automation_generation_runs` / `ui_automation_execution_runs` 中插入 `status='running'` 的脏数据，重启服务后所有相关行被置为 `failed`（或 `interrupted`），并写一条 `result=failed`、`failure_reason` 含「服务已重启」的 operation log。
- **超时恢复**：构造 `requirement_analysis_runs.updated_at = now - 121 minutes` 且 `status='running'` 的记录，连续调用 `/tasks` 一次后该记录状态变为 `failed`，`failure_reason` 含「超过 120 分钟」。
- **性能测试心跳**：`performance_test_runs.status IN ('starting','running')` 且 `updated_at < now - 5 minutes` 时，启动服务即被批量标记 `failed`，错误码 `PERFORMANCE_RUN_TIMEOUT`。
- **幂等性**：连续两次调用 `recover_interrupted_*` 不会把已被 mark 失败的记录再次改写（覆盖语义应保持稳定）。
- **operation log 一致**：每次状态写操作均同时产生一条 `operation_logs` 记录，`task_id`、`action`、`result`、`failure_reason` 字段非空。

### 10.3 性能验收

- `project_id + keyword + status_group + module` 命中约 1000 条记录时，`/tasks?page=1&page_size=50` P95 应 ≤ 500 ms（SQLite 本地场景）。
- `/tasks/running` 必须轻量：仅遍历当前 active 任务，P95 ≤ 200 ms。

### 10.4 兼容性验收

- 旧前端调用 `/tasks?keyword=xxx` 仍能命中（`keyword` 已在 2026-07-26 实现）。
- 旧前端调用 `/tasks?status_group=…` 命中筛选语义，必须与第 §4 节一致（`running` / `waiting` / `failed` / `completed`，大小写敏感）。
- 旧前端调用 `/tasks?page=0` 被服务夹紧到 `page=1`，不报错。
- 新增 `/tasks` 子路由不会改变现有 `/api/v1/tasks/running` 的返回值形态（仍为 `list[ApiTaskItem]`）。

---

## 附录 A · 关键常量

| 常量 | 取值 | 位置 |
| --- | --- | --- |
| `RUNNING_GROUP` | `"running"` | `task_service.py` |
| `WAITING_GROUP` | `"waiting"` | `task_service.py` |
| `FAILED_GROUP` | `"failed"` | `task_service.py` |
| `COMPLETED_GROUP` | `"completed"` | `task_service.py` |
| `TASK_RETENTION_DAYS` | `10` | `task_service.py` |
| `REQUIREMENT_ANALYSIS_RUN_TIMEOUT_MINUTES` | `120` | `task_service.py` |
| `performance_test_runs.recover_stale_runs timeout_minutes` | `5` | `performance_testing/run_repo.py` |
| 性能测试 `status` CHECK 枚举 | `created`, `starting`, `running`, `stopping`, `completed`, `stopped`, `failed`, `cancelled` | `seed/schema.py` |
| 性能测试 `RUN_STATUS_TRANSITIONS` | 见 `run_repo.py` | — |

## 附录 B · 已知差距

1. **`performance_test_run` 未进入 `STATUS_META_BY_SOURCE_TYPE`**，因此 `/tasks/running` 当前不包含性能测试运行行；性能测试运行列表仍由 `performance_testing/run_repo.list_runs` 暴露给前端。补齐动作：将 `performance_test_runs.status` 枚举加入 `STATUS_META_BY_SOURCE_TYPE`，并在 `_collect_visible_tasks` 内追加 `_performance_run_tasks(db, project_names)`。
2. **`ui_automation_*_run` 未进入 `STATUS_META_BY_SOURCE_TYPE`**，与上同理，恢复逻辑已纳入启动恢复，但运行态指示器缺失。
3. **任务详情弹窗**目前仅有快照字段，缺少输入参数、阶段、Worker 日志、重试入口；这些信息需要由 `detail_url` 跳转到业务模块详情页查看。
4. **`requirement_file`** 作为聚合源之一（`source_type = 'requirement_file'`）映射到 `requirement` 模块，但其 status_group 语义与 `requirement_analysis_run` 同名细分。后续若引入 `requirement` 模块子分类，需要在 `module` 上补充分层（如 `requirement.conversion` / `requirement.analysis`）以保持 `module` 字段的离散性。
