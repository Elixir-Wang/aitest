# 站点探索 AgentPlan 前后端对接设计规范

## 背景

站点探索已经具备探索任务、Playwright runner、结构化 YAML 产物、运行日志、详情接口和 SSE 实时流。前端探索概览也已经接入 `AgentPlan`，但当前展示仍偏向模块/页面摘要，无法清楚回答“后端每一步是怎么探索的”。

本规范定义后端探索步骤事实、接口契约和前端 `AgentPlan` 展示方式。目标是保留 `AgentPlan` 作为探索概览主展示结构，同时把每次探索过程以页面详情形式展示出来。

## 目标

- `AgentPlan` 继续作为探索概览的主展示组件。
- 后端负责产出模块、页面、步骤、阻塞和产物路径等真实事实。
- 前端只消费详情快照和 SSE 增量事件，不自行推断模块、不伪造页面、不模拟步骤。
- `AgentPlan` 一级节点展示模块，二级节点展示页面。
- 页面展开后展示该页面的探索步骤。
- 模块和页面右侧只展示状态，不再展示 `5/5 页`、`3 动作`、`2 字段` 这类计数型进度 meta。
- 运行结束后，刷新详情接口也能完整重建 `AgentPlan` 展示。

## 非目标

- 不把每个点击、元素、edge 都升成 `AgentPlan` 主树节点。
- 不在前端解析 HTML、URL 或标题来推断业务模块。
- 不把探索概览改成表格、报告或日志页。
- 不新增前端本地事实源。
- 不用前端假数据补齐后端未产出的探索步骤。

## 现状依据

当前代码已有以下基础：

- runner：`apps/backend/runners/playwright/site-explorer.mjs`
- 编排服务：`apps/backend/app/services/site_exploration_orchestrator.py`
- 详情服务：`apps/backend/app/services/exploration_service.py`
- SSE 事件总线：`apps/backend/app/services/exploration_event_bus.py`
- SSE 路由：`apps/backend/app/api/v1/exploration.py`
- 前端探索页：`apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- `AgentPlan` 组件：`apps/frontend/src/components/ui/agent-plan.tsx`

当前后端已经能产出：

- `run.yaml`
- `summary.yaml`
- `graph.yaml`
- `blockers.yaml`
- `pages/*.yaml`
- `logs/run.log`
- `module_*` / `page_*` / `blocker_detected` SSE 事件

需要补齐的是：页面级探索步骤的结构化字段和前端展开渲染。

## 展示模型

### 树结构

`AgentPlan` 的结构固定为两级：

```text
模块
  页面
    探索步骤
```

映射规则：

| 后端对象 | 前端对象 | 展示位置 |
| --- | --- | --- |
| module | `AgentPlanTask` | 一级节点 |
| page | `AgentPlanSubtask` | 二级节点 |
| exploration step | subtask expanded details | 页面展开详情 |
| blocker | subtask detail 或 task description | 阻塞说明 |
| element/action/edge | step detail 或页面 YAML/日志引用 | 不作为主树节点 |

### 展示示例

```text
用户管理                                      已完成
  用户列表页                                  已完成
    进入 /users
    采集页面结构
    识别 12 个可操作元素
    发现“新增用户”“编辑”“筛选”动作
    记录跳转关系到用户编辑页
    写入 pages/page-001-user-list.yaml

系统设置                                      阻塞
  权限设置页                                  阻塞
    进入 /settings/permission
    页面返回 403
    写入 blocker：当前账号无权限
    建议使用具备系统设置权限的账号重新探索
```

## 状态模型

前端 `AgentPlan` 展示以下状态：

| 后端状态 | 前端展示 | 说明 |
| --- | --- | --- |
| `pending` | 待探索 | 已纳入计划但未开始 |
| `queued` | 排队中 | 任务已提交，等待 runner |
| `running` | 探索中 | runner 正在执行 |
| `in-progress` | 探索中 | 模块或页面进行中 |
| `stopping` | 正在停止 | 用户请求停止，后端正在终止 |
| `completed` | 已完成 | 已生成事实产物且无关键阻塞 |
| `partial` | 部分完成 | 有事实产物，但存在未覆盖、跳过或非关键阻塞 |
| `blocked` | 阻塞 | 登录、权限、验证码、超时或安全策略导致不可继续 |
| `waiting_human` | 等待人工 | 需要人工处理登录、验证码或权限 |
| `failed` | 失败 | runner 或编排异常 |
| `cancelled` | 已中止 | 用户中止或系统取消 |

前端状态映射要求：

- `running` 和 `in-progress` 都可使用探索中动画。
- `stopping` 必须单独显示为“正在停止”，不能显示为“已中止”。
- `waiting_human` 不能简单吞成失败；如果 `AgentPlanStatus` 暂不支持，应先映射为 `blocked`，但文案显示“等待人工”。
- 未识别状态显示为“待探索”，同时保留原始状态用于调试。

## 后端数据契约

### 详情快照

接口：

```http
GET /api/v1/projects/{project_id}/exploration-runs/{run_id}/detail
```

页面对象需要增加 `steps` 字段：

```json
{
  "id": "page-001",
  "module_key": "user",
  "title": "用户列表页",
  "url": "/users",
  "entry_path": "/users",
  "structure_summary": "识别到用户表格、筛选条件和新增按钮。",
  "yaml_path": "projects/.../pages/page-001-user-list.yaml",
  "page_type": "list",
  "status": "completed",
  "blocker_reason": "",
  "recent_event": "写入页面 YAML",
  "steps": [
    {
      "id": "step-001",
      "type": "visit",
      "title": "进入页面",
      "detail": "访问 /users",
      "status": "completed",
      "occurred_at": "2026-05-30T10:20:00+08:00",
      "source": "run.log"
    }
  ]
}
```

字段要求：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 页面内稳定步骤 ID |
| `type` | 是 | 步骤类型 |
| `title` | 是 | 面向用户的短标题 |
| `detail` | 否 | 具体说明 |
| `status` | 是 | 步骤状态 |
| `occurred_at` | 否 | 发生时间 |
| `artifact_path` | 否 | 关联 YAML、log 或 graph 路径 |
| `source` | 否 | `runner`、`run.log`、`page.yaml`、`graph.yaml`、`blockers.yaml` |

### 步骤类型

第一版支持以下类型：

| type | 含义 |
| --- | --- |
| `visit` | 访问页面 |
| `snapshot` | 采集无障碍树或 DOM |
| `element_discovered` | 识别页面元素 |
| `action_observed` | 识别或执行动作 |
| `edge_created` | 记录页面关系 |
| `artifact_written` | 写入页面 YAML、graph 或 log |
| `blocked` | 记录阻塞 |
| `skipped` | 因禁止路径、外链或安全规则跳过 |
| `completed` | 页面探索完成 |
| `failed` | 页面探索失败 |

### 后端步骤来源

后端构建 `steps` 的优先级：

1. runner 直接输出的结构化步骤。
2. `logs/run.log` 中的 JSON Lines 或稳定前缀日志。
3. `pages/*.yaml`、`graph.yaml`、`blockers.yaml` 派生出的可追溯事实。

不能从前端补推断步骤。若后端暂时只能提供 `recent_event`，前端只能显示单条最近事件，不允许伪造完整步骤。

## SSE 事件契约

接口：

```http
GET /api/v1/projects/{project_id}/exploration-runs/{run_id}/stream
```

### 事件类型

保留现有事件，并补充页面步骤事件：

- `run_started`
- `run_progress`
- `module_discovered`
- `module_started`
- `module_updated`
- `page_discovered`
- `page_updated`
- `page_completed`
- `page_blocked`
- `step_recorded`
- `action_observed`
- `element_discovered`
- `blocker_detected`
- `run_completed`
- `run_failed`
- `run_cancelled`

### `step_recorded`

```json
{
  "type": "step_recorded",
  "run_id": "explore-123",
  "payload": {
    "module_key": "user",
    "page_id": "page-001",
    "step": {
      "id": "step-004",
      "type": "action_observed",
      "title": "识别动作",
      "detail": "发现“新增用户”按钮",
      "status": "completed",
      "source": "runner"
    }
  }
}
```

合并规则：

- `module_key` 和 `page_id` 必须存在。
- 前端按 `page_id + step.id` 去重。
- 同一 `step.id` 再次到达时覆盖更新。
- 新步骤追加到页面展开详情末尾。
- 断线重连后以详情接口为准校准。

### `page_updated` / `page_completed`

页面事件可以携带 `steps` 全量或增量：

```json
{
  "type": "page_completed",
  "run_id": "explore-123",
  "payload": {
    "module_key": "user",
    "page_id": "page-001",
    "status": "completed",
    "title": "用户列表页",
    "url": "/users",
    "recent_event": "页面探索完成",
    "steps": []
  }
}
```

如果同时存在 `steps` 和 `step_recorded`，前端按 ID 去重合并。

## 后端实现要求

### runner

`site-explorer.mjs` 在关键节点生成结构化步骤：

- `run_started`
- 访问页面前后
- 采集 accessibility snapshot 后
- DOM fallback 采集后
- 发现 link/action/form/table 后
- 创建 graph edge 后
- 命中 forbidden path 后
- 写入页面产物后
- 页面完成或阻塞时

runner 输出中的每个 page artifact 应包含：

```json
{
  "page": {},
  "steps": [],
  "accessibility_tree": [],
  "actions": [],
  "relations": {}
}
```

### 编排服务

`site_exploration_orchestrator.py` 负责：

- 从 runner 输出读取 `steps`。
- 写入页面 YAML。
- 在创建页面记录后发布 `page_completed`。
- 对运行中的步骤发布 `step_recorded`。
- 对阻塞发布 `page_blocked` 或 `blocker_detected`。
- 终态事件发布后关闭 event bus。

### 详情服务

`exploration_service.get_project_run_detail` 负责：

- 从页面 YAML 或 `run.log` 加载页面步骤。
- 在每个 page 对象上返回 `steps`。
- 不把步骤提升到 module 级。
- 保证终态 run 刷新后可完整重建前端展示。

### Schema

`apps/backend/app/schemas/exploration.py` 需要增加：

```python
class ExplorationStepOut(BaseModel):
    id: str
    type: str
    title: str
    detail: str = ""
    status: str = "completed"
    occurred_at: str | None = None
    artifact_path: str = ""
    source: str = ""

class ExplorationPageOut(BaseModel):
    ...
    steps: list[ExplorationStepOut] = []
```

## 前端实现要求

### AgentPlan 类型

`AgentPlanSubtask` 增加详情字段：

```ts
export type AgentPlanStep = {
  id: string;
  title: string;
  detail?: string;
  status?: AgentPlanStatus;
  meta?: string[];
};

export type AgentPlanSubtask = {
  id: string;
  title: string;
  description?: string;
  status: AgentPlanStatus;
  meta?: string[];
  steps?: AgentPlanStep[];
};
```

### AgentPlan 渲染

页面子项展开时：

- 先展示 `description`，如果存在。
- 再展示 `steps`。
- 步骤使用紧凑纵向列表，不使用表格。
- 步骤状态使用小图标或轻量 badge。
- 最多默认展示最近 20 条；更多步骤可以折叠到“查看更多”。

### 探索页映射

`buildAgentPlanTasks(detail)` 映射规则：

```ts
module -> AgentPlanTask
page -> AgentPlanSubtask
page.steps -> AgentPlanSubtask.steps
```

模块 meta 不再展示：

- `5/5 页`
- `3 动作`
- `2 字段`

页面 meta 可以保留低噪声信息：

- 页面类型
- URL 或入口路径
- YAML 路径

如果 UI 过挤，页面 meta 也只在展开详情中展示。

### SSE 合并

前端需要处理：

- `module_*`：更新模块节点。
- `page_*`：更新页面节点。
- `step_recorded`：追加或更新页面步骤。
- `blocker_detected`：更新模块或页面阻塞说明。
- `run_*`：更新 run 终态，并在 stream 结束后静默刷新详情接口。

前端不能因为收到 `action_observed` 就新建页面。只有后端给出 `page_id` 且页面存在或伴随 `page_discovered` 时才合并。

## 页面文案

探索概览标题保持：

```text
探索模块进度
```

说明文案调整为：

```text
展示模块、页面状态和页面探索步骤
```

不再使用：

```text
展示模块、页面进度和最近页面
```

## 验收标准

- 探索概览仍使用 `AgentPlan`，不改成表格。
- 模块节点右侧只显示状态，不显示 `5/5 页`、动作数、字段数。
- 页面节点右侧只显示状态。
- 展开页面后能看到后端真实探索步骤。
- 运行中通过 SSE 增量追加步骤。
- 刷新页面后通过 detail 接口仍能看到同样的步骤。
- 阻塞页面显示阻塞步骤、原因和建议动作。
- 前端不会自行推断模块、页面或步骤。
- `run.log`、页面 YAML、blockers 仍是可追溯事实来源。

## 测试要求

### 后端

- 测试 detail 接口返回 `pages[].steps`。
- 测试 `step_recorded` SSE 事件格式。
- 测试页面 YAML 可持久化并恢复 steps。
- 测试 blocked run 返回阻塞步骤。
- 测试旧产物缺少 steps 时接口仍兼容，返回空数组。

### 前端

- 测试 `buildAgentPlanTasks` 不再输出页面数量、动作数、字段数 meta。
- 测试 page steps 被映射到 `AgentPlanSubtask.steps`。
- 测试 `step_recorded` 会合并到正确页面。
- 测试重复 step id 覆盖而不是重复追加。
- 测试 `stopping`、`waiting_human` 状态展示正确。

## 实施顺序

1. 后端 schema 增加 `ExplorationStepOut` 和 `pages[].steps`。
2. runner 输出页面 steps。
3. artifact service 写入并读取 steps。
4. detail service 返回 steps。
5. orchestrator 发布 `step_recorded`。
6. 前端扩展 `AgentPlanSubtask.steps`。
7. 前端探索页映射 steps 并移除计数 meta。
8. 前端 SSE 合并 `step_recorded`。
9. 补齐后端和前端测试。

## 兼容策略

- 旧 run 没有 `steps` 时，详情接口返回 `steps: []`。
- 前端没有步骤时仍显示页面 description 或 recent_event。
- 新字段只做向后兼容扩展，不破坏已有 detail 接口消费者。
- 旧的 `recent_event` 保留，用作页面摘要，不作为完整步骤列表。
