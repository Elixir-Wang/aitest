# 00-23 AI测试系统 - 日志模块 PRD

> **事实源日期**：2026-07-26
>
> **事实源**：
>
> - 后端 API：`apps/backend/app/api/v1/operation_logs/{__init__.py, query.py, retention.py, client_errors.py, project_query.py}`
> - 后端服务：`apps/backend/app/services/operation_log_service.py`（`SENSITIVE_KEYS` / `SENSITIVE_PATTERN` 掩码、`record_*`、`list_logs / list_project_logs / export_logs / get_retention_policy / update_retention_policy / cleanup_logs`）
> - 后端清理：`apps/backend/app/services/retention_cleanup_service.py`（`schedule_cleanup / shutdown_cleanup / run_cleanup_if_due`，每天本地时间 0 点后第一次到期清理）
> - 后端日志框架：`apps/backend/app/core/logging.py`（Loguru）
> - 前端：`apps/frontend/src/app/(main)/settings/logs/{page.tsx, [logId]/page.tsx}`
> - 数据库：`apps/backend/app/seed/schema.py`（`operation_logs` / `operation_log_retention_policy` / `retention_cleanup_state`）
>
> **状态标签**：`已实现`

---

## 1. 范围与目标

### 1.1 问题

日志模块用于记录 AI 测试系统内关键业务对象和系统配置的增删改查、执行、确认、取消、失败等动作，帮助管理员追踪"谁在什么时间对什么对象做了什么、结果如何、变更了哪些关键内容"。

### 1.2 目标

- 支持系统配置、项目、需求、知识库、测试资产、任务、报告等关键操作可追溯
- 支持问题排查、权限审计、误操作定位和版本变更回溯
- 支持按用户、项目、模块、对象、动作、结果、时间范围筛选
- 敏感信息脱敏，避免日志成为密码、token、模型 key、验证码等敏感数据泄露入口
- 运营可配置日志保留策略，但受硬上限约束

---

## 2. 日志类型与字段

### 2.1 log_type（4 类）

| 值 | 说明 |
| --- | --- |
| `audit` | 审计日志：用户或系统对业务对象的关键动作记录 |
| `config` | 配置变更日志：系统设置、模型配置、用户权限等变更记录 |
| `task` | 任务生命周期日志：任务创建、开始、成功、失败、取消、重试等摘要 |
| `agent` | Agent 调用日志：Agent 执行输入摘要、输出摘要、状态、耗时、产物路径 |

### 2.2 source（5 类）

| 值 | 说明 |
| --- | --- |
| `web` | Web 前端用户操作 |
| `api` | API 客户端调用 |
| `agent` | AI Agent 自动执行 |
| `runner` | 本地 Runner 自动执行 |
| `system` | 系统定时任务/后端内部触发 |

### 2.3 result（4 类）

| 值 | 说明 |
| --- | --- |
| `success` | 操作成功 |
| `failed` | 操作失败 |
| `partial_success` | 部分成功 |
| `cancelled` | 操作取消 |

### 2.4 operation_logs 字段全集

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | TEXT | 日志 ID，系统唯一，格式 `oplog-{8字节hex}` |
| `log_type` | TEXT | 日志类型：`audit / config / task / agent` |
| `module` | TEXT | 模块：`project / requirement / knowledge / test_case / automation / report / user / permission / system / model / task / exploration / frontend / api / operation_log` 等 |
| `action` | TEXT | 动作：`create / update / delete / archive / restore / confirm / cancel / run / retry / export / download / login / logout / api_error / client_error / cleanup / update_retention_policy` 等 |
| `object_type` | TEXT | 对象类型：`project / requirement / document_version / knowledge_base / test_case / automation_suite / run / user / role / setting / model_provider / operation_log / client_error` 等 |
| `object_id` | TEXT | 被操作对象 ID，可空 |
| `object_name` | TEXT | 被操作对象名称或标题（已脱敏） |
| `project_id` | TEXT | 项目内操作必须记录；系统级操作可空 |
| `actor_id` | TEXT | 操作人 ID；系统自动动作为 `system`；匿名客户端错误为 `anonymous` |
| `actor_name` | TEXT | 展示名称（已脱敏） |
| `source` | TEXT | 操作来源：`web / api / agent / runner / system` |
| `result` | TEXT | 操作结果：`success / failed / partial_success / cancelled` |
| `failure_reason` | TEXT | 失败原因摘要（已脱敏） |
| `summary` | TEXT | 人可读摘要（已脱敏） |
| `before_json` | TEXT | 变更前值，脱敏后 JSON |
| `after_json` | TEXT | 变更后值，脱敏后 JSON |
| `task_id` | TEXT | 异步任务 ID，可空 |
| `artifact_path` | TEXT | 产物路径列表，JSON 数组（已脱敏） |
| `request_id` | TEXT | 请求追踪 ID（trace_id） |
| `ip_address` | TEXT | Web/API 操作来源 IP |
| `user_agent` | TEXT | Web/API 操作来源浏览器信息（已脱敏） |
| `created_at` | TEXT | 创建时间，ISO 8601 格式 |

### 2.5 数据库索引

| 索引名 | 字段 |
| --- | --- |
| `idx_operation_logs_created_at` | `created_at` |
| `idx_operation_logs_project_id_created_at` | `project_id, created_at` |
| `idx_operation_logs_actor_id_created_at` | `actor_id, created_at` |
| `idx_operation_logs_module_action` | `module, action` |
| `idx_operation_logs_object` | `object_type, object_id` |
| `idx_operation_logs_result` | `result` |

---

## 3. 审计日志 vs 文件日志

AI 测试系统存在两套独立的日志体系：

### 3.1 审计日志（SQLite：`operation_logs` 表）

- **用途**：业务操作可追溯，记录"谁对什么对象做了什么"
- **存储**：SQLite 数据库文件 `data/ai_testing.db`
- **写入**：通过 `operation_log_service.record_*` 系列函数，业务代码调用
- **保留**：受 `operation_log_retention_policy` 约束，由 `retention_cleanup_service` 定时清理
- **访问**：通过 `GET /operation-logs` 和 `GET /projects/{project_id}/operation-logs` API 访问
- **脱敏**：写入前在服务端对 `SENSITIVE_KEYS` / `SENSITIVE_PATTERN` 匹配字段做掩码

### 3.2 文件日志（Loguru：`logs/` 目录）

- **用途**：技术运行日志，记录应用层、错误、HTTP 访问和 AI Agent 执行详情
- **目录结构**：

```
logs/
  app/YYYY-MM-DD.log      — INFO+  通用应用日志
  error/YYYY-MM-DD.log    — WARNING+ 错误日志，快速定位问题
  access/YYYY-MM-DD.log   — 每个 HTTP 请求的进出记录
  agent/YYYY-MM-DD.log   — AI Agent 执行全程记录
```

- **轮转策略**：每天 00:00 轮转，保留 10 天，旧文件 zip 压缩，异步写入不阻塞主线程
- **trace_id 注入**：通过 `contextvars` 在同一请求的所有日志行中自动注入 `trace_id`
- **清理**：由 `retention_cleanup_service` 在保留期超过时删除 `logs/{app,error,access,agent}/` 下的过期文件
- **stdin/stdout**：Loguru 也负责将 uvicorn、FastAPI、httpx 等框架日志统一路由到 Loguru sink

### 3.3 两者边界

| 维度 | 审计日志 | 文件日志 |
| --- | --- | --- |
| 目标 | 业务可追溯性 | 技术排查 |
| 存储 | SQLite | 文件 |
| 格式 | 结构化字段 | 文本行 |
| 保留 | 可配置（默认 10 天） | 固定 10 天 |
| 访问 | API 查询 | 文件直接读取 |
| 脱敏 | 是（服务端） | 否 |

---

## 4. 保留策略硬上限

### 4.1 硬上限常量

| 常量 | 值 | 说明 |
| --- | --- | --- |
| `MAX_RETENTION_DAYS` | `10` | 无论运营配置多少，实际保留天数不超过 10 天 |
| `max_rows` | `100000` | SQLite 保留策略表的默认硬上限，运营可配置但建议不超过此值 |

清理时取 `min(MAX_RETENTION_DAYS, max(1, policy.retention_days))`，即：

- 运营配置 ≤ 0 → 实际按 1 天清理
- 运营配置 > 10 天 → 实际按 10 天清理

### 4.2 operation_log_retention_policy 表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | TEXT | 主键 |
| `retention_days` | INTEGER | 保留天数（运营配置，默认 10，受硬上限约束） |
| `max_rows` | INTEGER | 最大行数硬上限（默认 100000） |
| `protect_high_risk` | INTEGER | 是否保护高风险日志（0/1） |
| `updated_by` | TEXT | 最后修改人 ID |
| `updated_at` | TEXT | 最后修改时间 |

### 4.3 运营可配置项

管理员可通过 `PUT /operation-logs/retention-policy` 修改：

- `retention_days`：保留天数（受 10 天硬上限约束）
- `max_rows`：最大行数（建议不超过 100000）
- `protect_high_risk`：是否启用高风险日志保护

每次策略变更会写入一条 `log_type=audit, action=update_retention_policy` 日志。

---

## 5. 清理调度

### 5.1 调度机制

- **触发时机**：每天本地时间（`Asia/Shanghai`）0 点之后，**第一次有资格清理时**执行
- **防重复**：通过 `retention_cleanup_state` 表，`job_name="system-log-retention"`，同一天内不会重复清理
- **实现**：`retention_cleanup_service.schedule_cleanup` 在应用启动时调用，启动延迟 30 秒
- **重试**：最多 3 次，每次失败后等待 60 秒重试；之后每小时检查一次是否到期

### 5.2 retention_cleanup_state 表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `job_name` | TEXT | 任务名，当前固定为 `"system-log-retention"` |
| `last_success_at` | TEXT | 上次成功清理时间（ISO 8601） |
| `updated_at` | TEXT | 最后更新时间 |

### 5.3 清理流程

1. 查询 `retention_cleanup_state`，若当天已清理则跳过（`skipped`）
2. 取 `operation_log_retention_policy` 中的 `retention_days`，取 `min(MAX_RETENTION_DAYS, max(1, value))`
3. 计算 `cutoff = now - retention_days`，删除数据库中早于 cutoff 的记录（分批，每批 1000 条）
4. 删除 `logs/{app,error,access,agent}/` 下修改时间早于 cutoff 的文件
5. 更新 `retention_cleanup_state.last_success_at`

### 5.4 手动清理

管理员可通过 `POST /operation-logs/cleanup` 手动触发清理：

- 支持按 `log_type / module / action / result / created_before` 等条件过滤
- 支持 `dry_run=true` 试算
- 清理结果写入 `action=cleanup` 日志

---

## 6. 敏感字段掩码

### 6.1 SENSITIVE_KEYS

以下字段名在字典中会被直接替换为 `"******"`：

```
password, token, api_key, apikey, secret, authorization,
cookie, captcha, verification_code, access_key
```

匹配时将 `-` 替换为 `_` 后再做归一化匹配（支持 `api-key` / `api_key` 变体）。

### 6.2 SENSITIVE_PATTERN

正则匹配字符串值中形如 `key=value` 的模式：

```
(?i)(password|token|api[_-]?key|secret|authorization|cookie|captcha|verification[_-]?code|access[_-]?key)(\s*[:=]\s*)([^\s,;]+)
```

匹配到的第三个分组（实际值）替换为 `******`。

### 6.3 脱敏应用范围

以下字段写入数据库前均经过 `_mask_sensitive` 脱敏：

- `object_name`
- `actor_name`
- `failure_reason`
- `summary`
- `before_json`（字典/列表内递归脱敏）
- `after_json`（字典/列表内递归脱敏）
- `artifact_path`（JSON 数组内递归脱敏）
- `user_agent`

### 6.4 客户端错误上报中的脱敏

`record_client_error` 在写入 `before_json` 前对以下字段做 `_safe_text` 截断（不超过指定长度）：

| 字段 | 限制 |
| --- | --- |
| `page_url` | 1000 字符 |
| `action_label` | 120 字符 |
| `occurred_at` | 80 字符 |
| `path` | 500 字符 |
| `method` | 12 字符 |

---

## 7. 客户端上报（前端 JS 错误捕获）

### 7.1 端点

```
POST /operation-logs/client-errors
```

### 7.2 上报时机

前端浏览器发生未捕获异常或 API 请求错误时，自动上报。

### 7.3 请求体（ClientErrorReport）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | str | 错误标题 |
| `message` | str | 错误消息 |
| `code` | str | 错误码（可选） |
| `status` | int | HTTP 状态码（API 错误时有） |
| `method` | str | HTTP 方法 |
| `path` | str | 请求路径 |
| `page_url` | str | 页面 URL |
| `action_label` | str | 触发错误的操作名称（可选） |
| `occurred_at` | str | 发生时间（可选） |
| `trace_id` | str | 后端 trace_id（可选，优先使用） |

### 7.4 自动分类逻辑

| 条件 | action | module |
| --- | --- | --- |
| 有 `status` 且有 `path` | `api_error` | 根据路径推断（`/requirements` → `requirement`；`/projects` → `project`；`/knowledge` → `knowledge`；`/models` → `model`；`/users` → `user`；`/auth` → `auth`；`/operation-logs` → `operation_log`；默认 `api`） |
| 无 status/path | `client_error` | `frontend` |

### 7.5 权限与上下文

- 登录用户上报：记录 `actor_id`、`actor_name`
- 未登录用户上报：`actor_id=anonymous`、`actor_name=匿名用户`
- `project_id` 通过 URL 中 `/projects/{project_id}` 提取，并验证当前用户是否有权访问该项目
- IP 和 User-Agent 从请求头提取

---

## 8. 管理员导出 / 详情 / 过滤项

### 8.1 全局日志列表

```
GET /operation-logs
```

- **权限**：`require_admin`（仅管理员）
- **过滤参数**：`page, page_size, project_id, log_type, module, action, object_type, actor_id, result, keyword, start_time, end_time`
- **keyword 搜索**：匹配 `object_name`、`summary`、`failure_reason`

### 8.2 全局日志详情

```
GET /operation-logs/{log_id}
```

- **权限**：管理员可查看所有日志；非管理员只能查看有项目归属且有权访问的日志
- **返回**：包含 `before`（字典）、`after`（字典）、`artifact_path`（数组）、`request_id`、`ip_address`、`user_agent`

### 8.3 全局日志 CSV 导出

```
GET /operation-logs/export
```

- **权限**：`require_admin`
- **导出字段**：日志ID、时间、类型、模块、动作、对象类型、对象ID、对象名称、项目ID、操作人ID、操作人、来源、结果、摘要、失败原因、任务ID、请求ID、IP、User-Agent
- **限制**：最多导出 10000 条（`page_size=10000`）

### 8.4 过滤下拉项

```
GET /operation-logs/filter-options
```

- **权限**：管理员
- **返回**：`modules`、`actions`、`results`、`log_types` 四个下拉列表选项

---

## 9. 项目日志

### 9.1 项目日志列表

```
GET /projects/{project_id}/operation-logs
```

- **权限**：`current_user`（所有登录用户），但受项目访问权限约束
  - `admin` / `guest` / `project_scope=全部项目`：可访问所有项目日志
  - 其他角色：只能访问 `project_scope` 匹配的项目
- **过滤参数**：与全局日志相同（`project_id` 由路径自动注入）

### 9.2 项目日志 CSV 导出

```
GET /projects/{project_id}/operation-logs/export
```

- 文件名格式：`{project_id}-operation-logs.csv`

### 9.3 项目日志过滤下拉项

```
GET /projects/{project_id}/operation-logs/filter-options
```

- 仅返回当前项目内已有的过滤选项

---

## 10. 数据模型

### 10.1 operation_logs

详见第 2.4 节字段全集。

### 10.2 operation_log_retention_policy

详见第 4.2 节。

### 10.3 retention_cleanup_state

详见第 5.2 节。

---

## 11. API 路由清单

| 方法 | 路径 | 权限 | 功能 |
| --- | --- | --- | --- |
| `GET` | `/operation-logs` | admin | 全局日志列表（分页） |
| `GET` | `/operation-logs/{log_id}` | admin/项目权限 | 全局日志详情 |
| `GET` | `/operation-logs/export` | admin | 全局日志 CSV 导出 |
| `GET` | `/operation-logs/filter-options` | admin | 全局过滤下拉项 |
| `GET` | `/operation-logs/retention-policy` | admin | 查询保留策略 |
| `PUT` | `/operation-logs/retention-policy` | admin | 更新保留策略 |
| `POST` | `/operation-logs/cleanup` | admin | 手动清理日志 |
| `POST` | `/operation-logs/client-errors` | current_user | 客户端错误上报 |
| `GET` | `/projects/{project_id}/operation-logs` | current_user+项目权限 | 项目日志列表 |
| `GET` | `/projects/{project_id}/operation-logs/export` | current_user+项目权限 | 项目日志导出 |
| `GET` | `/projects/{project_id}/operation-logs/filter-options` | current_user+项目权限 | 项目过滤下拉项 |

---

## 12. 前端页面清单

| 路径 | 说明 |
| --- | --- |
| `/settings/logs` | 系统日志列表页（管理员专属），展示全局审计日志，支持按时间、模块、动作、对象类型、操作人、结果、项目筛选，支持关键词搜索 |
| `/settings/logs/{logId}` | 系统日志详情页，展示单条日志的完整上下文（变更前后、失败原因、trace_id、IP、User-Agent） |
| `/projects/{projectId}/logs` | 项目日志入口（第一版尚未独立实现，前端通过 `OperationLogView` 组件的 `endpoint` prop 指向 `/projects/{project_id}/operation-logs`） |

---

## 13. 验收规则

### 13.1 功能验收

- [ ] 管理员能在 `/settings/logs` 查看全局日志列表
- [ ] 管理员能按 `log_type / module / action / object_type / actor_id / result / keyword / start_time / end_time / project_id` 筛选日志
- [ ] 管理员能导出日志为 CSV
- [ ] 非管理员能访问 `/projects/{project_id}/operation-logs`，但只能访问有权访问的项目
- [ ] 日志详情展示 `before_json`、`after_json`、`artifact_path`、`request_id`、`ip_address`、`user_agent`
- [ ] 前端 JS 错误能通过 `POST /operation-logs/client-errors` 上报到服务端并持久化
- [ ] 客户端错误能自动归类（`api_error` vs `client_error`）和推断模块
- [ ] `PUT /operation-logs/retention-policy` 受硬上限约束：`retention_days` 实际不超过 10 天
- [ ] `POST /operation-logs/cleanup` 支持 `dry_run` 试算

### 13.2 脱敏验收

- [ ] `before_json` / `after_json` 中 `SENSITIVE_KEYS` 匹配字段值替换为 `******`
- [ ] `summary`、`failure_reason`、`actor_name`、`object_name` 中 `key=value` 模式被掩码
- [ ] `user_agent` 中的敏感字段被掩码
- [ ] 客户端错误 `before_json` 中 `page_url` 截断至 1000 字符以内

### 13.3 清理验收

- [ ] `retention_cleanup_service.schedule_cleanup` 在应用启动时调用
- [ ] 每天本地时间 0 点后第一次到期执行清理，不会同一天重复执行
- [ ] 数据库清理和文件清理同步进行
- [ ] 清理后更新 `retention_cleanup_state.last_success_at`

### 13.4 记录规则验收

- [ ] `record_success`：记录 `result=success` 日志
- [ ] `record_failure`：记录 `result=failed` 日志
- [ ] `record_change`：记录变更前后快照（已脱敏）
- [ ] `record_task_event`：记录 `log_type=task` 日志
- [ ] `record_agent_run`：记录 `log_type=agent` 日志
- [ ] 保留策略变更写入 `action=update_retention_policy` 日志
- [ ] 手动清理写入 `action=cleanup` 日志

### 13.5 日志写入可靠性

- [ ] 日志写入失败不阻断主业务成功（写入在 `try/except` 中，失败仅记录 warning）
- [ ] 日志写入后返回 `oplog-{8字节hex}` 格式 ID
- [ ] `request_id` 贯穿日志和任务链路，通过 `trace_id` 串联
