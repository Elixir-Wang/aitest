# Locust UI 项目内置迁移设计

## 文档状态

- 状态：待评审
- 日期：2026-07-16
- 基准版本：Locust 2.45.0
- 目标：将 Locust 原 Web UI 的功能迁移到本项目，适配现有 UI 风格并提供中文界面

## 背景

当前性能测试流程通过后端启动独立 Locust Web UI，再由前端获取 UI 地址并打开新窗口。该方案需要维护 Locust 进程、端口、会话注册表、Cookie、反向代理和浏览器新窗口，导致以下问题：

- Windows 下 Python 父子进程 PID 不稳定，容易出现僵尸会话和 PID 复用。
- Locust UI 端口与项目后端 API 之间存在额外代理链路。
- 前端无法统一使用项目权限、导航、错误处理和操作日志。
- Locust 原 UI 的英文内容与项目中文界面不一致。
- 性能测试执行状态与页面状态分离，用户需要在两个界面之间切换。

本设计保留 Locust 作为压测执行引擎，但移除对 Locust Web UI 的产品依赖，将 Locust UI 的功能迁移为项目自己的页面和 API。

## 设计目标

1. 覆盖 Locust 2.45.0 原 Web UI 的核心页面和交互能力。
2. 所有用户操作在本项目内完成，不能要求用户打开独立 Locust UI。
3. UI 适配本项目现有布局、组件、权限和中文文案体系。
4. Locust 执行进程与 FastAPI 主进程隔离，避免压测阻塞业务 API。
5. 运行状态、统计数据、失败请求、异常和报告可持久化查询。
6. 支持单机 Worker，并为后续 Locust Master/Worker 扩展保留边界。
7. 失败时返回明确错误，不再使用无法定位原因的通用提示。
8. 保留现有性能测试脚本生成和确认流程，减少无关改造。

## 非目标

本期不包含以下内容：

- 像素级复制 Locust 原 Web UI 的 React 页面。
- 修改 Locust 核心库或维护 Locust 的前端源码。
- 在 FastAPI 事件循环内直接运行长时间压测任务。
- 首期实现跨机器自动扩缩容的 Worker 集群。
- 首期支持 Locust 原 UI 中与分布式部署运维相关的所有内部调试选项。
- 修改已有性能测试计划、脚本生成规则和目标接口引用模型。

## 用户范围

### 管理员和测试人员

- 查看项目内的性能测试。
- 启动、停止和重置压测运行。
- 查看实时统计、失败和异常。
- 下载运行报告。
- 查看历史运行结果。

### 访客

- 复用项目现有只读权限规则。
- 只能查看被授权项目的测试配置和历史结果。
- 不能启动、停止或重置运行。

权限判断沿用当前项目和用户权限模型，不在性能测试模块内重新定义角色体系。

## 总体架构

```text
┌─────────────────────────────┐
│ 项目 React 前端              │
│ 中文性能测试运行页           │
│ Overview / Statistics /      │
│ Charts / Failures / Reports  │
└──────────────┬──────────────┘
               │ HTTP + SSE
┌──────────────▼──────────────┐
│ FastAPI 控制面               │
│ 创建任务 / 控制任务 / 查询   │
│ 权限 / 持久化 / 报告下载     │
└──────────────┬──────────────┘
               │ Task Queue
┌──────────────▼──────────────┐
│ Performance Worker           │
│ 独立 Python 进程             │
│ Locust Environment / Runner  │
└──────────────┬──────────────┘
               │ HTTP
               ▼
           目标接口系统
```

### 关键边界

- FastAPI 是控制面，不承载压测用户任务。
- Worker 是执行面，负责加载生成脚本并运行 Locust。
- 前端只访问项目 API，不访问 Locust Web UI 端口。
- 统计数据由 Worker 采集并写入项目存储。
- 项目页面不依赖 Locust 的 HTML、JavaScript 或静态资源。

## 页面设计

运行详情页面沿用项目现有性能测试路由，在创建运行后进入运行详情：

```text
/projects/{project_id}/performance-tests/{test_id}/runs/{run_id}
```

页面结构：

```text
运行详情
├── 顶部运行控制栏
│   ├── 状态
│   ├── 运行时间
│   ├── 启动压测
│   ├── 停止压测
│   ├── 重置统计
│   └── 下载报告
├── 概览
│   ├── 当前用户数
│   ├── RPS
│   ├── 失败率
│   ├── 平均响应时间
│   ├── P95
│   └── P99
├── Statistics
├── Charts
├── Failures
├── Exceptions
├── 用户与任务
├── 运行日志
└── 报告与导出
```

### 运行控制栏

保留 Locust 原 UI 的主要控制语义，但适配项目按钮和确认交互：

- `启动压测`：使用已确认脚本和当前性能测试负载配置创建运行。
- `停止压测`：要求确认，发送停止任务命令。
- `重置统计`：仅清理当前运行的统计数据，不删除脚本和运行记录。
- `下载报告`：根据运行状态展示可用的 CSV、HTML 和 JSON 文件。
- `返回测试详情`：保留当前运行记录，不自动停止已完成运行。

按钮状态由服务端运行状态决定，不能仅由前端本地 loading 状态决定。

### 概览

实时展示：

- 当前状态：准备中、启动中、运行中、停止中、已完成、已停止、失败。
- 当前用户数和目标用户数。
- 当前 RPS。
- 总请求数。
- 成功请求数。
- 失败请求数。
- 失败率。
- 平均响应时间。
- 最小响应时间。
- 最大响应时间。
- P50、P95、P99 响应时间。
- 已运行时间和预计剩余时间。

### Statistics

统计表按 Locust 的请求统计语义展示：

- 请求名称。
- 请求方法。
- 请求数量。
- 失败数量。
- 失败率。
- 平均响应时间。
- 最小响应时间。
- 最大响应时间。
- 中位数响应时间。
- P95 响应时间。
- P99 响应时间。
- 平均 Content Size。
- 当前 RPS。
- 当前失败率。

支持：

- 按请求名称排序。
- 按请求数量、失败率、P95 排序。
- 搜索请求名称。
- 查看请求统计时间点。
- 显示总计行。

### Charts

首期图表：

- RPS 趋势。
- 失败率趋势。
- 平均响应时间趋势。
- P95 响应时间趋势。
- 当前用户数趋势。

图表数据以固定时间窗口采样，默认每 1 秒生成一个点；服务端保存完整采样数据，前端只请求当前运行所需窗口。

### Failures

展示失败请求聚合信息：

- 请求名称。
- 失败原因。
- 失败次数。
- 最近发生时间。
- 示例响应状态码。
- 示例响应内容摘要。

支持展开查看失败样本，但必须对响应内容进行长度限制和敏感信息脱敏。

### Exceptions

展示执行过程中的异常：

- 异常类型。
- 异常消息。
- 发生次数。
- 最近发生时间。
- 关联请求名称。
- Worker 日志引用。

### 用户与任务

展示：

- Locust 用户类。
- 用户类当前数量。
- 用户类目标数量。
- 用户类任务名称。
- 任务执行次数。
- 任务失败次数。

首期不允许在运行过程中动态修改任务代码和用户类；运行参数只在启动前配置。

### 运行日志

展示 Worker 和 Locust 的结构化日志：

- 时间。
- 日志级别。
- 运行阶段。
- 消息。
- 异常类型。
- Trace ID。

原始 stdout/stderr 作为附件保存，不直接拼接到 HTML 页面中。

## 运行状态机

```text
created
  ↓
starting
  ├── failed
  └── running
        ├── stopping
        │     ├── stopped
        │     └── failed
        ├── completed
        └── failed
```

状态定义：

| 状态 | 含义 | 可执行操作 |
|---|---|---|
| `created` | 已创建运行记录，尚未提交 Worker | 启动、取消 |
| `starting` | Worker 正在加载脚本和初始化 Locust | 取消 |
| `running` | Locust 正在执行任务 | 停止、查看统计 |
| `stopping` | 已发送停止命令，等待 Worker 结束 | 查看日志 |
| `completed` | 正常完成 | 查看、下载、重置统计 |
| `stopped` | 用户主动停止 | 查看、下载、重新运行 |
| `failed` | 启动或执行失败 | 查看错误、重新运行 |
| `cancelled` | 任务尚未执行即被取消 | 重新运行 |

所有状态迁移由后端确认，前端不得自行将运行标记为完成或失败。

## 数据模型

### performance_test_runs

建议字段：

```text
id
project_id
performance_test_id
script_id
status
worker_id
load_config_json
runtime_config_json
started_at
finished_at
created_at
error_code
error_message
trace_id
report_directory
```

### performance_test_run_stats

用于保存总览和请求级采样数据：

```text
id
run_id
sampled_at
user_count
request_count
failure_count
requests_per_second
failure_rate
average_response_time_ms
p50_response_time_ms
p95_response_time_ms
p99_response_time_ms
stats_json
```

### performance_test_run_failures

```text
id
run_id
request_name
method
reason
count
last_occurred_at
sample_status_code
sample_response_excerpt
```

### performance_test_run_exceptions

```text
id
run_id
request_name
exception_type
message
count
last_occurred_at
```

### performance_test_run_events

用于审计和日志时间线：

```text
id
run_id
event_type
level
message
payload_json
created_at
trace_id
```

`active_sessions.json` 不再作为产品级运行状态来源。迁移期可以保留读取能力，但新运行必须写入数据库。

## API 设计

### 创建运行

```text
POST /projects/{project_id}/performance-tests/{test_id}/runs
```

行为：

1. 校验项目权限。
2. 校验性能测试引用、环境和已确认脚本。
3. 创建 `performance_test_runs` 记录，状态为 `created`。
4. 提交 Worker 任务。
5. 返回 `run_id` 和状态。

响应示例：

```json
{
  "id": "perfrun-xxx",
  "status": "created"
}
```

该接口不能等待整个压测完成。

### 查询运行

```text
GET /projects/{project_id}/performance-test-runs/{run_id}
```

返回运行配置、状态、错误、最新统计和可用报告。

### 查询实时统计

```text
GET /projects/{project_id}/performance-test-runs/{run_id}/stats
```

返回：

- 最新总览。
- 请求统计表。
- 最新失败。
- 最新异常。
- 图表采样点。

### 实时事件流

首期使用 SSE：

```text
GET /projects/{project_id}/performance-test-runs/{run_id}/events
```

事件类型：

- `run_status_changed`
- `stats_updated`
- `failure_updated`
- `exception_recorded`
- `worker_log`
- `run_finished`

SSE 断开时前端回退到 1 秒轮询，不影响最终结果。

### 停止运行

```text
POST /projects/{project_id}/performance-test-runs/{run_id}/stop
```

只允许 `starting` 或 `running` 状态执行。后端先将状态改为 `stopping`，再向 Worker 发送停止命令。

### 重置统计

```text
POST /projects/{project_id}/performance-test-runs/{run_id}/reset-stats
```

只清理当前运行统计和图表数据，不删除运行配置、脚本和日志。

### 报告列表和下载

```text
GET /projects/{project_id}/performance-test-runs/{run_id}/reports
GET /projects/{project_id}/performance-test-runs/{run_id}/reports/{report_name}
```

报告文件必须通过项目权限校验，不允许直接暴露本地文件路径。

## Worker 设计

### Worker 职责

- 读取运行配置和脚本。
- 创建 Locust `Environment` 和 Runner。
- 启动本地或分布式执行模式。
- 订阅 Locust 请求、失败、异常和运行结束事件。
- 周期性写入统计采样。
- 生成 CSV、HTML、JSON 报告。
- 捕获 stdout、stderr 和 Python 异常。
- 更新运行最终状态。

### Worker 隔离

- Worker 不监听 Locust Web UI 端口。
- Worker 不暴露 Locust Web UI。
- Worker 使用独立 Python 进程。
- Worker 通过任务 ID关联运行，不使用 PID 作为业务主键。
- Worker 崩溃后由后端超时检测将运行标记为 `failed`。
- Worker 必须支持优雅停止和强制停止两级策略。

### 任务调度

首期可以使用项目已有的后台任务机制；如果现有机制无法保证长任务隔离，则新增轻量 Worker 进程和数据库任务轮询。

任务至少包含：

```text
run_id
project_id
script_path
runtime_config_path
requested_by
created_at
```

## 错误处理和日志

所有运行错误必须同时写入：

1. `performance_test_runs.error_code`。
2. `performance_test_runs.error_message`。
3. `performance_test_run_events`。
4. Worker 原始日志文件。
5. 服务端 Trace ID。

错误分类：

| 错误码 | 含义 |
|---|---|
| `PERFORMANCE_SCRIPT_NOT_CONFIRMED` | 脚本未确认 |
| `PERFORMANCE_ENDPOINT_INVALID` | 接口引用失效 |
| `PERFORMANCE_ENVIRONMENT_INVALID` | 环境引用失效 |
| `PERFORMANCE_WORKER_UNAVAILABLE` | Worker 无法接收任务 |
| `PERFORMANCE_SCRIPT_LOAD_FAILED` | Locust 脚本加载失败 |
| `PERFORMANCE_RUN_START_FAILED` | Runner 启动失败 |
| `PERFORMANCE_RUN_TIMEOUT` | Worker 超时无心跳 |
| `PERFORMANCE_RUN_STOP_FAILED` | 停止任务失败 |
| `PERFORMANCE_REPORT_FAILED` | 报告生成失败 |
| `PERFORMANCE_TARGET_UNAVAILABLE` | 目标接口不可用 |
| `PERFORMANCE_RUN_INTERNAL_ERROR` | 未分类内部错误 |

前端必须优先显示服务端 `message` 和 `trace_id`，只有无法解析错误响应时才使用兜底提示。

## 安全要求

- 所有运行和报告接口必须校验项目权限。
- 运行日志中的 Authorization、Cookie、Token、密码和密钥必须脱敏。
- 目标环境凭据只在 Worker 运行时解密，不写入前端响应。
- 失败响应摘要限制最大长度。
- 报告下载使用运行 ID和权限校验，不接受任意文件路径。
- Worker 任务不能允许用户提交任意 Python 文件路径。
- 运行目录必须位于项目配置的性能测试存储根目录内。

## 迁移策略

### 第一阶段：数据和 Worker 基础

- 新增运行、统计、失败、异常和事件模型。
- 抽象 Locust Worker 接口。
- 支持启动、停止、状态和报告。
- 保留当前旧 Locust UI 代码作为兼容路径，但不再作为新页面入口。

### 第二阶段：项目内置运行页

- 新增运行详情路由。
- 实现概览、Statistics、Failures、Exceptions 和日志。
- 接入 SSE，断线回退轮询。
- 加入中文文案和项目权限。

### 第三阶段：Charts 和报告

- 实现 RPS、失败率、响应时间和用户数图表。
- 接入 CSV、HTML、JSON 报告下载。
- 增加历史运行结果和对比入口。

### 第四阶段：移除 UI 依赖

- 删除前端 `window.open(session.url)`。
- 停止创建 Locust Web UI 会话。
- 停止使用 Locust UI 反向代理。
- 清理 `active_sessions.json` 的产品级依赖。
- 保留必要的旧运行数据迁移和兼容清理脚本。

## 测试策略

### 后端单元测试

- 状态机迁移合法性。
- Worker 启动和停止。
- Locust 事件转换为项目统计。
- 失败和异常聚合。
- 统计采样计算。
- 报告生成和下载权限。
- Worker 心跳超时。
- Worker 崩溃恢复。
- 敏感信息脱敏。

### API 测试

- 创建运行立即返回，不等待压测完成。
- 未确认脚本不能启动。
- 无权限用户不能操作运行。
- 停止运行幂等。
- 重置统计不删除脚本和运行配置。
- SSE 断线后可通过轮询恢复。
- 报告路径不能越权访问。

### 前端测试

- 各运行状态按钮可用性。
- Statistics 表排序和搜索。
- Charts 数据刷新。
- Failures 和 Exceptions 展示。
- SSE 断线回退轮询。
- 中文文案完整性。
- 不再调用 `window.open` 或 Locust UI session API。

### 验收场景

1. 用户在性能测试详情页点击启动，进入项目内置运行页。
2. 页面显示启动中，随后显示运行中和实时统计。
3. 用户点击停止，运行最终状态显示已停止。
4. 目标接口返回错误时，Failures 显示失败原因和次数。
5. Locust 发生 Python 异常时，Exceptions 显示异常类型和消息。
6. Worker 崩溃时，页面最终显示明确错误码和 Trace ID。
7. 测试完成后可以下载 CSV、HTML 和 JSON 报告。
8. 用户刷新页面后，仍能恢复运行状态和历史统计。
9. 无权限用户无法查看其他项目的运行数据。
10. 整个流程不打开独立 Locust UI，不依赖 Locust UI 端口。

## 可观测性

- 每个运行拥有唯一 `run_id` 和 `trace_id`。
- 记录运行创建、Worker 接收、启动、首个统计、停止、完成和失败事件。
- 记录 Worker 心跳时间。
- 记录运行耗时、请求数、失败数、报告生成耗时。
- 记录 Worker 崩溃、超时和强制停止次数。
- 后端日志必须包含 `run_id`，前端错误必须包含 `trace_id`。

## 设计决策

1. 不嵌入 Locust 原 Web UI 静态资源，避免继续依赖 Locust UI 的端口、路由和版本内部实现。
2. 不在 FastAPI 主进程内运行长时间压测任务，使用独立 Worker。
3. 首期使用 SSE 推送实时数据，并保留轮询回退。
4. 运行状态以数据库为准，文件只保存脚本、日志和报告附件。
5. 先完成单机 Worker，Worker 接口为后续 Master/Worker 扩展保留。
6. 功能对齐 Locust 原 UI，视觉、权限和文案遵循本项目规范。

## 待评审事项

- 当前项目已有后台任务机制是否满足长时间 Worker 任务隔离。
- 首期是否直接支持 SSE，还是先完成轮询版本。
- 报告文件保留周期和单次运行大小限制。
- 是否需要历史运行对比作为第一期功能。
- 是否需要首期支持 Master/Worker 分布式执行。

以上事项不影响总体架构；若未单独确认，默认采用：独立单机 Worker、SSE 加轮询回退、报告保留 30 天、历史对比放入第二期、不在第一期启用分布式执行。
