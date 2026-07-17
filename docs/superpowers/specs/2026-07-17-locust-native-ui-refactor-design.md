# 性能测试 Locust 原生 UI 项目内迁移重构 Spec

**日期：** 2026-07-17  
**状态：** 已确认设计，待实施  
**适用模块：** 性能测试 / Locust 运行控制台  
**目标：** 消除页面职责错乱，将 Locust 原生 UI 迁移到本项目内部

## 1. 背景

当前性能测试流程存在页面职责重叠和跳转错乱：新建、脚本审核、任务详情、启动 Locust 和运行统计之间没有清晰边界，部分页面会直接进入启动逻辑，部分页面重复承载运行配置，导致用户无法判断当前处于“定义测试”“审核脚本”还是“执行压测”阶段。

现有设计还同时存在两种互相冲突的方向：

1. 脚本审核后打开独立 Locust UI。
2. 脚本审核后进入平台自研的运行详情和实时统计页面。

本次重构统一采用 Locust 作为唯一性能执行和统计内核，并将 Locust 原生 UI 的页面结构与交互迁移到本项目的 React 页面中，不使用 iframe、外部页面、新窗口或第二套平台统计口径。

## 2. 设计目标

### 2.1 必须实现

- 删除“性能测试详情”页面，不再将测试定义单独拆成一个详情路由。
- 建立唯一且可理解的页面流程：列表 → 新建 → 脚本审核 → Locust 控制台 → 运行历史。
- 脚本审核只负责脚本版本确认，不自动启动 Locust。
- Locust 控制台页面必须在本项目内部渲染。
- Locust 控制台保持原生信息架构、操作语义和统计字段。
- Locust 继续负责用户调度、请求执行、统计、百分位、失败和异常聚合。
- 一次性能测试可以创建多次独立运行。
- 页面刷新后可以恢复运行会话及其当前状态。
- 所有运行操作经过当前用户和项目权限校验。

### 2.2 明确不做

- 不使用 iframe 嵌入 Locust Web UI。
- 不通过 `window.open` 或外部 URL 打开 Locust。
- 不在平台侧重新实现另一套统计算法。
- 不保留独立的“性能测试详情”页面。
- 不在脚本审核页展示实时统计或启动表单。
- 不在列表页直接启动压测。
- 不在本次范围内支持分布式 Locust master/worker。
- 不在本次范围内支持多接口业务场景编排。

## 3. 页面与路由设计

### 3.1 页面流程

```text
性能测试列表
    ↓
新建性能测试
    ↓
脚本审核
    ↓
创建运行会话并进入 Locust 控制台
    ↓
Locust 原生启动与运行页面
    ↓
运行历史 / 结果下载
```

“创建运行会话”和“开始压力测试”是两个明确动作：前者建立可恢复的运行上下文并进入控制台，后者由 Locust 控制台中的原生启动表单触发真实压测。

### 3.2 性能测试列表

路由：

```text
/performance-tests
/projects/:projectId/performance-tests
```

职责：

- 展示全部项目或当前项目的性能测试。
- 展示名称、项目、接口、测试模式、脚本状态和最近运行状态。
- 支持搜索、项目过滤和状态过滤。
- 进入新建页面。
- 进入脚本审核页面。
- 进入某一次运行的 Locust 控制台。
- 展开或查看运行历史。
- 删除或归档性能测试。

列表页不负责编辑运行参数、展示实时统计或直接启动 Locust。

### 3.3 新建性能测试

路由：

```text
/performance-tests/new
/performance-tests/new?projectId={projectId}
```

职责：

- 选择项目、环境和单个接口。
- 配置请求数据、成功规则和测试数据。
- 配置固定负载、手动梯度、压力、峰值或耐久模式。
- 配置性能目标和失败熔断规则。
- 保存测试定义并生成 Locust 脚本草稿。

页面章节：

```text
基础信息
请求配置
测试数据
负载配置
性能目标
安全熔断
```

交互规则：

- 项目 → 环境 → 接口按顺序联动。
- 切换项目时清空环境、接口和下游请求配置。
- 环境认证和 Secret 只在执行侧注入，不进入可见前端状态。
- 新建页不启动 Locust，不展示实时统计、图表、失败和异常。

### 3.4 脚本审核

路由：

```text
/projects/:projectId/performance-tests/:testId/scripts/:scriptId
```

职责：

- 展示脚本版本、生成来源和配置摘要。
- 展示语法、导入、结构和安全校验结果。
- 编辑结构化请求配置、数据模板和成功规则。
- 重新生成脚本。
- 确认不可变脚本版本。
- 创建运行会话并进入 Locust 控制台。

脚本审核页禁止：

- 自动创建运行会话。
- 自动启动 Locust。
- 自动打开新窗口。
- 展示实时统计。

用户确认脚本后留在审核结果状态；只有显式点击“进入 Locust 控制台”才创建新的运行会话，不进入性能测试详情页。

### 3.5 Locust 原生控制台

路由：

```text
/projects/:projectId/performance-tests/:testId/runs/:runId
```

该路由是本次重构的核心运行页面。它由本项目承载，但遵循 Locust 原生 UI 的页面结构和交互语义。

页面结构：

```text
项目上下文与运行编号
    ↓
运行控制区 / Start new load test / Stop / Reset Stats
    ↓
Statistics
    ↓
Charts
    ↓
Failures
    ↓
Exceptions
    ↓
Download Data
```

项目上下文只用于显示项目、性能测试名称、脚本版本、运行编号和权限范围，不改变 Locust 核心交互。

## 4. Locust 控制台功能设计

### 4.1 未开始状态

展示 Locust 原生启动表单：

- Number of users。
- Spawn rate。
- Host。
- Run time。
- 表单校验和错误提示。
- `Start new load test`。

点击启动后调用 Locust Runner，不由前端自行计算用户增长或请求统计。

### 4.2 运行中状态

运行控制区展示：

- 当前用户数。
- 目标用户数。
- Spawn rate。
- 运行时长。
- 请求总数。
- Requests per second。
- 平均响应时间。
- P50、P90、P95、P99。
- 失败数和失败率。

可执行操作：

```text
Stop
Reset Stats
```

操作状态由服务端运行状态决定，不能只依赖前端 loading 状态。

### 4.3 Statistics

统计表保持 Locust 原生字段语义：

- 请求名称。
- 请求类型。
- 请求数。
- 失败数。
- 平均响应时间。
- 最小响应时间。
- 最大响应时间。
- 中位数。
- 各百分位响应时间。
- 当前 RPS。
- 当前失败率。

统计数据必须直接来自 Locust 的 `RequestStats` / `StatsEntry`，平台不得使用另一套计算结果覆盖原生结果。

### 4.4 Charts

迁移 Locust 原生图表语义：

- Users。
- Requests per second。
- Response time。
- Failure rate。

图表只负责展示 Locust 运行快照和时间序列，不承担自动调节负载、自动停止或 AI 决策。

### 4.5 Failures

展示失败请求聚合信息：

- 请求名称。
- 方法。
- 错误信息。
- 失败次数。
- 最近发生时间。

### 4.6 Exceptions

展示运行期间的异常：

- 异常类型。
- 异常消息。
- 来源位置。
- 发生次数。
- 最近发生时间。

### 4.7 Download Data

提供 Locust 结果产物下载：

- Statistics CSV。
- Failures CSV。
- Exceptions CSV。
- Statistics history CSV。
- JSON 运行快照。
- HTML 结果报告（如果当前运行生成）。

所有下载接口必须先校验项目权限，再限制文件路径在当前运行目录内，拒绝路径穿越和跨项目读取。

## 5. 运行历史设计

取消性能测试详情页后，运行历史归属性能测试列表：

- 每条性能测试支持展开最近运行记录。
- 支持从行操作进入“全部运行历史”抽屉或对话框。
- 每条运行记录直接链接到对应的 Locust 控制台路由。
- 运行记录展示运行编号、开始时间、结束时间、状态、实际用户数、总请求数、失败数、平均响应时间、P95 和 RPS。
- 历史运行保持只读；重新运行会创建新的 `runId`，不会覆盖旧运行。

本次不新增独立的性能测试详情路由，也不依赖详情页面承载运行历史。

## 6. 前端组件边界

建议新建：

```text
apps/frontend/src/components/performance/locust/
```

组件：

```text
locust-console.tsx
locust-console-shell.tsx
locust-start-panel.tsx
locust-run-toolbar.tsx
locust-statistics-table.tsx
locust-charts-panel.tsx
locust-failures-table.tsx
locust-exceptions-table.tsx
locust-download-panel.tsx
locust-status-badge.tsx
```

组件职责：

- `locust-console-shell`：运行状态切换和 Locust 页面整体布局。
- `locust-start-panel`：原生启动表单和参数校验。
- `locust-run-toolbar`：Stop、Reset Stats 和状态操作。
- `locust-statistics-table`：原生统计表。
- `locust-charts-panel`：原生图表区域。
- `locust-failures-table`：失败聚合表。
- `locust-exceptions-table`：异常聚合表。
- `locust-download-panel`：结果产物下载。
- `locust-status-badge`：运行状态展示。

Locust UI 组件只依赖稳定的前端领域模型，不直接读取数据库实体或页面路由参数。

## 7. 后端运行与 API 设计

### 7.1 执行内核

后端继续使用 Locust 原生能力：

- `Environment`。
- `LocalRunner`。
- `RequestStats`。
- `StatsEntry`。
- Locust 事件系统。
- Locust 原生用户和请求执行逻辑。

平台扩展只负责运行会话、权限、脚本快照、状态持久化、事件转发和结果产物。

### 7.2 运行会话 API

```text
POST /projects/{projectId}/performance-tests/{testId}/runs
GET  /projects/{projectId}/performance-tests/{testId}/runs/{runId}
POST /projects/{projectId}/performance-tests/{testId}/runs/{runId}/start
POST /projects/{projectId}/performance-tests/{testId}/runs/{runId}/stop
POST /projects/{projectId}/performance-tests/{testId}/runs/{runId}/reset-stats
```

### 7.3 Locust 数据 API

```text
GET /projects/{projectId}/performance-tests/{testId}/runs/{runId}/locust/state
GET /projects/{projectId}/performance-tests/{testId}/runs/{runId}/locust/stats
GET /projects/{projectId}/performance-tests/{testId}/runs/{runId}/locust/charts
GET /projects/{projectId}/performance-tests/{testId}/runs/{runId}/locust/failures
GET /projects/{projectId}/performance-tests/{testId}/runs/{runId}/locust/exceptions
```

实时数据优先使用 SSE；连接不可用时使用轮询降级。页面卸载时必须清理订阅和轮询。

### 7.4 下载 API

```text
GET /projects/{projectId}/performance-tests/{testId}/runs/{runId}/locust/download/stats
GET /projects/{projectId}/performance-tests/{testId}/runs/{runId}/locust/download/failures
GET /projects/{projectId}/performance-tests/{testId}/runs/{runId}/locust/download/exceptions
GET /projects/{projectId}/performance-tests/{testId}/runs/{runId}/locust/download/report
```

浏览器只访问项目后端 API，不直接访问 Locust 内部端口。

## 8. 运行状态模型

统一状态：

```text
created
starting
ready
running
stopping
stopped
completed
failed
cancelled
```

正常状态流转：

```text
created → starting → ready → running → stopping → stopped → completed
```

异常状态流转：

```text
starting → failed
ready → failed
running → failed
running → cancelled
```

页面行为：

| 状态 | 页面行为 |
|---|---|
| `created` | 显示运行会话准备状态 |
| `starting` | 显示 Locust 初始化状态 |
| `ready` | 显示原生 Start 表单 |
| `running` | 显示统计、图表、失败、异常和 Stop |
| `stopping` | 禁用重复操作并等待结束 |
| `stopped` | 显示最终结果和下载 |
| `completed` | 显示最终结果、报告和重新运行 |
| `failed` | 显示错误、日志和重新运行 |
| `cancelled` | 显示取消原因和重新运行 |

## 9. 旧功能迁移与清理

### 9.1 删除

- 删除性能测试详情路由和对应导航入口。
- 删除脚本审核后的自动 Locust session 创建。
- 删除任务详情页的自动启动逻辑。
- 删除 `window.open`、iframe 和外部 Locust URL。
- 删除重复的平台自研实时运行详情组件。
- 删除将 `active_sessions.json` 作为运行状态唯一来源的逻辑。

### 9.2 保留

- 性能测试列表。
- 性能测试新建表单。
- Locust 脚本生成、校验和版本确认。
- Locust Runner 执行内核。
- 运行快照和运行历史。
- CSV、JSON、HTML 结果产物。
- 项目权限、操作日志和错误追踪。

## 10. 测试策略

### 10.1 前端契约测试

- 列表页只暴露新建、审核、运行历史和运行入口。
- 不存在性能测试详情路由引用。
- 脚本审核页不包含自动启动逻辑。
- Locust 控制台路由存在且接收 `projectId`、`testId`、`runId`。
- Locust 控制台包含 Start、Stop、Reset Stats、Statistics、Charts、Failures、Exceptions 和 Download Data。
- 前端不存在 `window.open`、iframe 或外部 Locust URL。
- 页面状态根据服务端状态渲染。

### 10.2 后端测试

- 运行会话创建受权限控制，重复提交不会意外创建重复进程。
- Locust 运行启动、停止、重置统计行为正确。
- 运行状态在刷新和服务恢复后可读取。
- 统计、图表、失败和异常数据来自 Locust 事件与统计对象。
- 运行失败和取消状态可持久化。
- 下载接口拒绝跨项目访问和路径穿越。
- 同一性能测试可以创建多次独立运行。

### 10.3 集成验收

1. 从性能测试列表新建任务。
2. 完成脚本审核并确认脚本版本。
3. 显式创建运行会话并进入项目内 Locust 控制台。
4. 在 Locust 原生启动面板输入参数并启动。
5. 查看 Statistics、Charts、Failures、Exceptions。
6. 点击 Stop 并确认运行结束。
7. 下载 CSV、JSON 和 HTML 结果。
8. 刷新页面并恢复运行状态。
9. 再次运行同一性能测试并确认生成新的 `runId`。

## 11. 验收标准

- 页面流程唯一：列表 → 新建 → 脚本审核 → Locust 控制台。
- 不存在独立性能测试详情页面。
- 脚本审核不会自动启动压测。
- Locust 控制台完全在本项目内渲染。
- Locust 原生启动、停止、重置统计、统计表、图表、失败、异常和下载均可用。
- 统计口径来自 Locust，不由平台重复计算。
- 页面刷新不会丢失运行上下文。
- 同一性能测试支持多次运行和独立结果。
- 运行失败、停止、取消和完成均有明确状态。
- 所有 API 和下载均执行项目权限校验。
- 代码中不再出现 iframe、`window.open` 或外部 Locust 页面依赖。
