# 需求分析任务生命周期 Spec

## 背景

当前需求详情页的 `需求评审` 按钮会调用：

```text
POST /api/v1/projects/{project_id}/requirements/{document_id}/review
```

后端同步执行 `review_primary_requirement_file`，内部调用 `requirement_analysis` 智能体，完成后写入：

- `source_document_versions`
- `requirement_analyses`
- `operation_logs` 中一条 `log_type="agent"` 的成功日志

但任务中心只聚合 `exploration_run`、`knowledge_build`、`requirement_file`。因此用户点击 `需求评审` 后：

- 顶部运行中任务提示不会出现。
- 任务中心没有需求评审任务。
- 任务详情没有任务日志。
- 失败时只能从接口错误感知，缺少可追踪任务记录。

这与任务中心文案中“汇总需求分析、探索、知识库...”的产品承诺不一致。

## 目标

- 让需求评审/需求分析拥有明确的任务运行生命周期。
- 用户点击后立即产生可见任务，而不是等智能体完成后才有结果记录。
- 任务中心能展示需求评审任务的运行、完成、待澄清、阻塞和失败状态。
- 顶部运行中任务提示能展示正在执行的需求评审。
- 任务详情能关联 operation logs，展示开始、运行、完成、失败等事件。
- 保留现有 `requirement_analyses` 作为业务分析结果表。
- 不把任务执行状态混入 `RequirementAnalysisOutput.status`。

## 非目标

- 不重建需求归并智能体。
- 不改变 `requirement_analysis` 智能体的分析边界、prompt 或输出结构。
- 不把完整 prompt、完整 Markdown、完整模型响应写入 operation logs。
- 不在本次设计中实现人工澄清后的自动写回闭环。
- 不把所有同步业务操作都强行任务化；只有 AI 后台处理进入任务生命周期。

## 核心原则

```text
requirement_analysis_runs = 执行生命周期
requirement_analyses = 业务分析结果
operation_logs = 可审计事件摘要
task_service = 统一任务视图聚合
```

`RequirementAnalysisOutput.status` 当前只有：

```text
completed | needs_clarification | blocked
```

这些是业务分析结论，不是执行状态。不得把 `queued`、`running`、`failed` 塞进该字段。

## 推荐方案

新增轻量运行表 `requirement_analysis_runs`，将 `/review` 改造成任务启动入口。后端先创建 run，再异步执行现有需求评审核心逻辑。

### 生命周期

```text
queued -> running -> completed
                  -> needs_clarification
                  -> blocked
                  -> failed
```

含义：

| 状态 | 分组 | 含义 |
| --- | --- | --- |
| `queued` | running | 已提交，等待后台执行 |
| `running` | running | 智能体正在分析 |
| `completed` | completed | 分析完成，无阻塞问题 |
| `needs_clarification` | waiting | 分析完成，但存在待确认问题 |
| `blocked` | failed | 分析完成，但质量门禁阻塞 |
| `failed` | failed | 执行异常，未产出可用分析结果 |

`needs_clarification` 使用 `waiting` 分组，是因为它需要人工继续处理，但不是系统失败。

## 数据库设计

新增表：

```sql
CREATE TABLE IF NOT EXISTS requirement_analysis_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  primary_mapping_id TEXT NOT NULL DEFAULT '',
  analysis_id TEXT,
  status TEXT NOT NULL CHECK(status IN (
    'queued',
    'running',
    'completed',
    'needs_clarification',
    'blocked',
    'failed'
  )),
  summary TEXT NOT NULL DEFAULT '',
  failure_reason TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
  FOREIGN KEY(primary_mapping_id) REFERENCES source_document_file_mappings(id) ON DELETE SET DEFAULT,
  FOREIGN KEY(analysis_id) REFERENCES requirement_analyses(id) ON DELETE SET NULL
);
```

新增索引：

```sql
CREATE INDEX IF NOT EXISTS idx_requirement_analysis_runs_project_created
ON requirement_analysis_runs(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_requirement_analysis_runs_document_created
ON requirement_analysis_runs(document_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_requirement_analysis_runs_status
ON requirement_analysis_runs(status);
```

SQLite 的 `ON DELETE SET DEFAULT` 对空字符串外键可能不适合严格外键环境；如果实现中发现兼容性问题，改为 `primary_mapping_id TEXT` 可空，并使用 `ON DELETE SET NULL`。

## Repository 设计

新增 `apps/backend/app/repositories/requirement_analysis_run_repo.py`，提供：

```python
def create_run(...)
def update_run_status(...)
def attach_analysis(...)
def find_run(...)
def find_latest_by_document(...)
def list_by_visible_projects(...)
```

更新 `updated_at` 时复用 SQLite `CURRENT_TIMESTAMP`，不要在 service 层手写时间字符串。

## 后端流程

### 启动评审

`POST /projects/{project_id}/requirements/{document_id}/review`

第一版推荐保留现有路径，但响应语义改成 task-start response。前端同步改造，不再假设该接口立即返回完整分析结果。

流程：

1. 校验文档存在。
2. 校验已选择主需求文件。
3. 校验主需求标准 Markdown 已转换完成。
4. 创建 `requirement_analysis_runs`，状态 `queued`。
5. 写 task event 日志：`需求评审已提交`。
6. 启动后台线程或 FastAPI `BackgroundTasks`。
7. 立即返回 run。

返回示例：

```json
{
  "id": "reqrun-abc",
  "source_type": "requirement_analysis_run",
  "source_id": "reqrun-abc",
  "project_id": "project-1",
  "document_id": "doc-1",
  "status": "queued",
  "status_label": "排队中",
  "status_group": "running",
  "summary": "需求评审已提交，等待智能体分析。",
  "detail_url": "/projects/project-1/requirements/doc-1"
}
```

### 后台执行

后台执行函数，例如：

```text
run_requirement_analysis_review(run_id)
```

流程：

1. 读取 run。
2. 将 run 更新为 `running`。
3. 写 task event 日志：`需求评审开始`。
4. 执行现有 `review_primary_requirement_file` 的核心逻辑。
5. 生成 `requirement_analyses` 和文档版本。
6. 将 `analysis_id` 挂到 run。
7. 根据 `RequirementAnalysisOutput.status` 更新 run：
   - `completed`
   - `needs_clarification`
   - `blocked`
8. 写 task event 日志：`需求评审完成`。
9. 写现有 agent 成功日志，或将现有成功日志改为 `record_agent_run` 并带上 `task_id=run_id`。

失败时：

1. 捕获异常。
2. 更新 run 为 `failed`。
3. 写 task event 日志，包含脱敏后的 `failure_reason`。
4. 不创建空的 `requirement_analyses`。
5. 不吞掉日志写入失败，但日志写入失败不能导致后台任务二次失败。

## Service 拆分

现有 `review_primary_requirement_file` 同时承担校验、执行、落库、返回结果。实现时应拆成三层：

```text
start_requirement_review_run(...)
execute_requirement_review_run(run_id)
perform_requirement_review(...)
```

职责：

- `start_requirement_review_run`：同步校验、创建 run、调度后台任务、返回 run。
- `execute_requirement_review_run`：更新生命周期状态、记录 task event、处理异常。
- `perform_requirement_review`：复用现有分析逻辑，返回 analysis result 和 analysis id。

这样可以保留单元测试对核心分析逻辑的覆盖，也能单独测试任务生命周期。

## Task Service 集成

`apps/backend/app/services/task_service.py` 增加：

```python
REQUIREMENT_ANALYSIS_STATUS = {
    "queued": (RUNNING_GROUP, "排队中"),
    "running": (RUNNING_GROUP, "评审中"),
    "completed": (COMPLETED_GROUP, "已完成"),
    "needs_clarification": (WAITING_GROUP, "等待澄清"),
    "blocked": (FAILED_GROUP, "评审阻塞"),
    "failed": (FAILED_GROUP, "评审失败"),
}
```

并注册：

```python
STATUS_META_BY_SOURCE_TYPE["requirement_analysis_run"] = REQUIREMENT_ANALYSIS_STATUS
RUNNING_INDICATOR_SOURCE_TYPES.add("requirement_analysis_run")
```

新增聚合函数：

```text
_requirement_analysis_run_tasks(db, project_names)
```

任务字段：

| 字段 | 值 |
| --- | --- |
| `task_id` | `requirement_analysis:{run_id}` |
| `source_type` | `requirement_analysis_run` |
| `source_id` | `run_id` |
| `module` | `requirement` |
| `module_label` | `需求评审` 或 `需求分析`，以最终页面文案为准 |
| `title` | 需求文档名 |
| `status` | run.status |
| `summary` | run.summary 或 failure_reason |
| `created_at` | run.created_at |
| `updated_at` | run.updated_at |
| `detail_url` | `/projects/{project_id}/requirements/{document_id}` |

如果产品已统一入口名称为 `需求分析`，则 `module_label` 应使用 `需求分析`。如果当前页面按钮仍是 `需求评审`，先使用 `需求评审`，避免用户困惑。

## Operation Log 集成

需求分析运行应写 task 事件：

| 时机 | log_type | action | result | summary |
| --- | --- | --- | --- | --- |
| run 创建 | `task` | `submit_requirement_analysis` | `success` | 需求评审已提交 |
| run 开始 | `task` | `start_requirement_analysis` | `success` | 需求评审开始 |
| run 完成 | `task` | `finish_requirement_analysis` | `success` | 需求评审完成 |
| run 待澄清 | `task` | `finish_requirement_analysis` | `partial_success` | 需求评审完成，存在待确认问题 |
| run 阻塞 | `task` | `finish_requirement_analysis` | `partial_success` | 需求评审阻塞 |
| run 失败 | `task` | `fail_requirement_analysis` | `failed` | 需求评审失败 |

所有日志应带：

```text
module="requirement"
object_type="requirement_analysis_run"
object_id=run_id
task_id=run_id
project_id=project_id
```

业务结果成功日志可带：

```text
log_type="agent"
object_type="requirement_analysis"
object_id=analysis_id
task_id=run_id
```

任务详情查日志时优先按 `task_id=run_id` 查询。

## API 设计

保留：

```text
GET /projects/{project_id}/requirements/{document_id}/analysis
```

返回最新业务分析结果。

调整或新增：

```text
POST /projects/{project_id}/requirements/{document_id}/review
```

返回 run/task，而不是完整 analysis。

可选新增：

```text
GET /projects/{project_id}/requirements/{document_id}/analysis-runs
GET /projects/{project_id}/requirements/{document_id}/analysis-runs/{run_id}
GET /projects/{project_id}/requirements/{document_id}/analysis-runs/{run_id}/logs
```

如果已有通用任务详情和项目日志过滤能满足需求，第一版可不新增 run logs endpoint，只在前端任务详情链接到项目日志筛选。

## 前端设计

### 需求详情页

点击 `需求评审` 后：

1. 调用 `/review`。
2. 使用返回 run 立即触发顶部任务提示。
3. toast 显示 `需求评审已提交`，不要显示 `需求评审已完成`。
4. 禁用按钮直到当前 document 的 active run 结束。
5. 可显示当前 run 状态：
   - `排队中`
   - `评审中`
   - `等待澄清`
   - `评审阻塞`
   - `评审失败`
6. run 结束后重新拉取：
   - document overview
   - latest requirement analysis

如果当前项目尚未接入任务 SSE，可先依赖 `/tasks/running` 和手动刷新；但最终应接入 task event bus。

### 任务中心

任务列表展示 `需求评审/需求分析` 任务。

任务详情至少展示：

- 项目
- 任务种类
- 任务名称
- 状态
- 创建时间
- 更新时间
- 摘要
- 失败原因
- 详情地址

后续增强：在任务详情中内嵌 operation logs 列表，按 `task_id` 过滤。

## 兼容策略

现有前端可能期望 `/review` 直接返回 `RequirementAnalysisResult`。实施时有两个选择：

### 推荐选择：同 PR 修改前后端契约

- `/review` 改为返回 run。
- 前端点击后不再立即消费 analysis payload。
- run 完成后通过 `GET /analysis` 获取结果。

优点：契约清晰，符合任务化。

### 过渡选择：新增 `/analysis-runs`，保留 `/review`

- `/review` 暂时保持同步旧行为。
- 新前端使用 `/analysis-runs`。
- 后续废弃 `/review` 的同步语义。

优点：兼容旧调用。

缺点：短期双入口，容易产生文案和行为不一致。

第一版如果没有外部 API 消费者，推荐直接同 PR 修改 `/review`。

## 失败和重试

失败 run 不自动重试。

用户可再次点击 `需求评审` 创建新 run。新 run 不覆盖旧 run，只更新最新分析结果。

如果同一 document 已有 active run：

- 返回 409 `REQUIREMENT_ANALYSIS_RUN_ACTIVE`
- 文案：`当前需求已有评审任务正在执行，请等待完成后再发起。`

active statuses：

```text
queued | running
```

`needs_clarification` 不阻止再次评审，但前端应提示用户“仍有待确认问题，重新评审可能生成新的问题列表”。

## 测试要求

后端测试：

- 创建 review run 后返回 `queued`。
- 有 active run 时重复提交返回 409。
- 后台执行开始后 run 变为 `running`。
- 分析成功且 output.status 为 `completed` 时 run 变为 `completed` 并关联 `analysis_id`。
- output.status 为 `needs_clarification` 时 task 分组为 `waiting`。
- output.status 为 `blocked` 时 task 分组为 `failed`。
- 智能体异常时 run 变为 `failed`，记录 `failure_reason`。
- `task_service.list_tasks` 能返回需求评审任务。
- `task_service.list_running_tasks` 能返回 queued/running 的需求评审任务。
- operation logs 中 task events 带 `task_id=run_id`。

前端测试：

- 点击需求评审后 toast 为 `需求评审已提交`。
- 点击后不再假设接口返回完整 analysis。
- active run 存在时按钮禁用并显示运行态。
- run 完成后重新加载 latest analysis。
- 任务中心能展示 `需求评审` 任务。
- 任务详情能打开需求详情页。

## 实施顺序

1. 新增 `requirement_analysis_runs` 表、索引和 repo。
2. 拆分 document requirement review service，分离启动、执行和核心分析。
3. 将 `/review` 改为创建 run 并后台执行。
4. 为 run 生命周期写 operation task events。
5. `task_service` 聚合 `requirement_analysis_run`。
6. 前端需求详情页改为 task-start 交互。
7. 任务中心展示需求评审任务。
8. 补充后端和前端测试。
9. 手工验证上传、标准化、设为主需求、需求评审、任务中心、项目日志闭环。

## 验收标准

- 点击 `需求评审` 后，任务中心立即出现一条需求评审任务。
- 智能体运行中，顶部运行任务提示能看到该任务。
- 任务完成后，需求详情页能看到最新分析结果。
- 有待确认问题时，任务状态显示 `等待澄清`，不是失败。
- 智能体异常时，任务状态显示 `评审失败`，任务详情能看到失败原因。
- 项目日志能按任务追踪提交、开始、完成或失败事件。
- `RequirementAnalysisOutput.status` 不包含 `queued/running/failed`。

## 待确认事项

- 页面最终文案使用 `需求评审` 还是 `需求分析`。现有 2026-06-06 spec 倾向统一为 `需求分析`，但当前实现仍显示 `需求评审`。
- 是否已有外部客户端依赖 `/review` 同步返回完整 analysis。如果有，应采用过渡选择新增 `/analysis-runs`。
- 是否要在第一版接入全局 task SSE。若尚未实现，可先通过任务中心刷新验证生命周期，后续再接入实时事件。
