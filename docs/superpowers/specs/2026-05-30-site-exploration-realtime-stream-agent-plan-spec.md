# 站点探索实时事件流与 AgentPlan 展示规范

## 背景

当前站点探索已经具备任务、环境、模块、页面、日志和产物目录，但前端概览仍依赖轮询刷新，展示也偏向静态摘要。对于运行中的探索任务，用户更需要的是后端在探索过程中持续推送真实进度，前端即时把模块、页面、阻塞和动作变化映射到 `AgentPlan` 里。

本方案定义一条从后端探索引擎到前端概览的实时事件链路。后端只输出真实探索事实，前端只负责增量合并和动画渲染，不自行推断模块、不伪造页面、不模拟进度。

## 目标

- 取消探索概览页的固定轮询刷新。
- 使用实时事件流向前端推送探索进度、模块、页面、动作和阻塞变化。
- 让 `AgentPlan` 成为探索概览的主展示结构。
- 保留数据库和 YAML 产物作为事实源，前端只消费增量事件和初始快照。
- 兼容当前项目的 `motion/react`、Tailwind、shadcn 结构和现有探索详情接口。

## 非目标

- 不把每个浏览器底层事件都直接渲染为主界面子项。
- 不在前端维护独立的探索状态机。
- 不引入假数据、demo 数据或前端随机状态切换。
- 不替代现有探索产物落盘机制。
- 不要求模块划分由前端推断。

## 核心原则

1. 模块、页面、阻塞和动作事实必须由后端生成。
2. 前端只接收后端事件并增量更新本地状态。
3. `AgentPlan` 一级节点表示模块，二级节点表示页面。
4. 动作和元素只作为页面展开详情，不默认污染主进度树。
5. 实时事件流是增量通道，数据库/YAML 是权威事实源。
6. 初始详情接口负责首屏快照，实时流负责后续增量。
7. 运行结束后，页面状态必须可通过现有详情接口完整重建。

## 推荐传输方式

优先使用 **SSE**:

- 单向推送足够满足探索进度展示。
- 前端原生 `EventSource` 即可接入。
- 对当前“后端持续产出、前端实时展示”的场景实现成本最低。

备选方案是 WebSocket，但仅在未来需要前端反向控制探索、暂停、单步执行或多路交互时再引入。

## 数据边界

### 1. 事实源

后端必须继续落盘并入库：

- `run`
- `modules`
- `pages`
- `elements`
- `blockers`
- `graph`
- `summary`
- `run.log`

### 2. 实时事件

实时事件只做增量通知，不是唯一事实源。前端断线后必须能通过详情接口补齐状态。

### 3. 展示层

前端概览只展示：

- 模块标题
- 模块进度条
- 页面节点状态
- 运行中的动画态
- 页面/模块的展开详情

不展示前端自己推断的业务语义。

## 事件模型

### 事件类型

建议事件最少包含：

- `run_started`
- `run_progress`
- `module_discovered`
- `module_updated`
- `module_started`
- `page_discovered`
- `page_updated`
- `page_completed`
- `page_blocked`
- `action_observed`
- `element_discovered`
- `blocker_detected`
- `run_completed`
- `run_failed`
- `run_cancelled`

### 事件约束

- `module_*` 事件必须携带 `module_id`。
- `page_*` 事件必须携带 `module_id` 和 `page_id`。
- `action_observed` 必须关联到页面，不直接创建主树节点。
- `blocker_detected` 必须可追溯到模块、页面或动作。
- 事件 payload 必须可序列化为 JSON。

### 事件示例

```json
{
  "type": "page_completed",
  "run_id": "explore-123",
  "payload": {
    "module_id": "settings",
    "page_id": "page-users",
    "status": "completed",
    "title": "用户管理",
    "url": "/settings/users",
    "recent_event": "识别到用户表格、新增按钮和筛选条件",
    "explored_page_count": 3,
    "planned_page_count": 6
  }
}
```

## 后端设计

### 1. 事件发布器

在站点探索编排服务内新增事件发布器，职责如下：

- 接收探索运行中的结构化事件。
- 同步写入数据库/YAML。
- 将事件广播到当前 `run_id` 的实时通道。

### 2. 实时通道

建议按 `run_id` 建立独立订阅通道：

- `GET /projects/{project_id}/exploration-runs/{run_id}/stream`

返回 SSE 流，事件以 `event:` + `data:` 形式输出。

### 3. 编排接入点

探索编排在以下节点必须发事件：

- 任务开始
- 模块识别
- 模块开始
- 页面发现
- 页面完成
- 页面阻塞
- 动作执行结果
- 元素识别
- 任务完成
- 任务失败
- 任务取消

### 4. 模块划分

模块必须由后端划分，不允许前端推断。

模块来源优先级：

1. 用户显式配置的模块清单
2. 导航菜单/路由分组
3. 页面标题或面包屑归类
4. 未分组页面归为“未命名模块”或“未分组模块”

### 5. 页面映射

页面是模块下的子节点。页面发现后先发 `page_discovered`，随后随着探索更新发 `page_updated`、`page_completed` 或 `page_blocked`。

### 6. 动作粒度

动作不应全部变成 `AgentPlan` 子项。建议只在页面展开详情中展示动作摘要或最近事件，避免主树过载。

## 前端设计

### 1. 首屏

详情页进入时先请求一次快照接口，拿到：

- run
- modules
- pages
- blockers

### 2. 实时合并

随后建立 SSE 连接，按事件类型增量合并到本地 state：

- 新模块 -> 新增一级任务
- 新页面 -> 新增子任务
- 页面完成 -> 更新子任务状态
- 阻塞 -> 更新状态和说明
- 进度变化 -> 更新动画条宽度

### 3. 展示结构

`AgentPlan` 的映射建议：

- `module` -> task
- `page` -> subtask
- `completion_status` -> task.status
- `page.status` -> subtask.status

页面展开后的详细信息可以包含：

- 最近事件
- 结构摘要
- 推荐 locator
- blocker 说明

### 4. 动画规则

只有以下状态显示运行动画：

- `queued`
- `running`
- `in-progress`
- `stopping`

完成、阻塞、中止状态使用静态图标或静态样式。

### 5. 断线恢复

若 SSE 中断，前端应：

- 保留当前已渲染 state
- 重连 SSE
- 重连成功后继续合并事件
- 必要时再调用一次详情接口做校准

## 接口建议

### 详情快照

```http
GET /api/v1/projects/{project_id}/exploration-runs/{run_id}/detail
```

用于页面首次加载和断线校准。

### 实时流

```http
GET /api/v1/projects/{project_id}/exploration-runs/{run_id}/stream
```

用于增量推送。

## 验收标准

- 探索运行中，前端无需 3 秒轮询也能看到模块和页面实时变化。
- `AgentPlan` 会随着后端事件逐步展开，而不是等任务结束后一次性出现。
- 页面发现、完成、阻塞都能实时反映在前端。
- 后端仍然保留完整事实产物，断线后可通过详情接口恢复。
- 前端不持久化探索事实，不伪造模块或页面。

## 备注

当前项目已具备 `motion/react`、shadcn 风格组件和探索详情页结构，适合直接在现有页面上接 SSE。后续实现时应优先复用现有 `AgentPlan` 组件和探索详情接口，避免再造一套独立的实时看板。
