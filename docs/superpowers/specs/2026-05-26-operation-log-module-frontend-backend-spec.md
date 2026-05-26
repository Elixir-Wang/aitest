# 日志模块前后端实施 Spec

## 背景

产品文档 `docs/00-产品文档/00-23-AI测试系统-日志模块PRD.md` 已定义日志模块范围：操作审计、配置变更、任务生命周期、Agent 调用摘要、日志保留与脱敏。

当前项目形态：

- 后端：FastAPI + SQLite + repository/service/schema/api 分层。
- 前端：Next.js App Router + React + shadcn/ui 风格组件。
- 第一版本地单机使用，不接 ELK、SIEM、外部审计系统。

本 Spec 只规划前后端落地边界，不直接实现代码。

## 目标

- 新增统一操作日志能力，覆盖系统配置、项目、需求、归并、任务、模型配置等关键动作。
- 新增系统级日志页面：管理员查看全局日志、筛选、详情、导出入口、保留策略入口。
- 新增项目级日志页面：在项目详情中查看当前项目相关日志。
- 后端提供结构化日志写入、查询、详情、保留策略和手动清理能力。
- 日志写入统一复用服务，避免各业务模块散落拼 SQL。

## 非目标

- 不接入外部日志平台。
- 不保存 Playwright trace、Allure、Runner stdout/stderr 全量内容，只保存关联路径和摘要。
- 不记录普通列表浏览、分页、排序、搜索输入等低价值行为。
- 不修改已有业务版本日志的语义，日志模块只提供审计视角。

## 后端设计

### 数据表

新增 `operation_logs`。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT PRIMARY KEY | 日志 ID |
| log_type | TEXT | audit、config、task、agent |
| module | TEXT | project、requirement、system_setting、model、task 等 |
| action | TEXT | create、update、delete、merge、confirm、cancel、run、retry、export、login、logout |
| object_type | TEXT | project、requirement、setting、task、model_provider 等 |
| object_id | TEXT NULL | 被操作对象 ID |
| object_name | TEXT | 被操作对象名称 |
| project_id | TEXT NULL | 项目内日志必须有 |
| actor_id | TEXT | 操作人 ID，系统动作为 system |
| actor_name | TEXT | 操作人展示名 |
| source | TEXT | web、api、agent、runner、system |
| result | TEXT | success、failed、partial_success、cancelled |
| failure_reason | TEXT | 失败摘要 |
| summary | TEXT | 人可读摘要 |
| before_json | TEXT | 脱敏后的变更前摘要 JSON |
| after_json | TEXT | 脱敏后的变更后摘要 JSON |
| task_id | TEXT NULL | 关联任务 |
| artifact_path | TEXT | 关联产物路径，可为 JSON 字符串数组 |
| request_id | TEXT | 请求 ID |
| ip_address | TEXT | 来源 IP |
| user_agent | TEXT | 来源浏览器 |
| created_at | TEXT | 创建时间 |

索引：

- `idx_operation_logs_created_at`
- `idx_operation_logs_project_id_created_at`
- `idx_operation_logs_actor_id_created_at`
- `idx_operation_logs_module_action`
- `idx_operation_logs_object`
- `idx_operation_logs_result`

新增 `operation_log_retention_policy`。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT PRIMARY KEY | 固定单行或策略 ID |
| retention_days | INTEGER | 默认 180 |
| max_rows | INTEGER | 默认 100000 |
| protect_high_risk | INTEGER | 删除、权限、系统配置类日志默认保护 |
| updated_by | TEXT | 修改人 |
| updated_at | TEXT | 更新时间 |

### 后端文件

新增：

- `apps/backend/app/schemas/operation_log.py`
- `apps/backend/app/repositories/operation_log_repo.py`
- `apps/backend/app/services/operation_log_service.py`
- `apps/backend/app/api/v1/operation_logs.py`
- `apps/backend/tests/test_operation_log_service.py`
- `apps/backend/tests/test_operation_log_api.py`

修改：

- `apps/backend/app/seed/init_db.py`
- `apps/backend/app/api/v1/__init__.py`
- `apps/backend/app/main.py` 或现有 router 注册位置
- 按阶段修改项目、需求、系统设置、模型、任务等服务，接入日志写入

### Schema

主要请求/响应：

- `OperationLogListQuery`
- `OperationLogListItem`
- `OperationLogDetail`
- `OperationLogCreate`
- `OperationLogRetentionPolicyOut`
- `OperationLogRetentionPolicyUpdate`
- `OperationLogCleanupRequest`
- `OperationLogCleanupResult`

枚举建议：

- `log_type`: `audit`、`config`、`task`、`agent`
- `result`: `success`、`failed`、`partial_success`、`cancelled`
- `source`: `web`、`api`、`agent`、`runner`、`system`

### API

系统级接口：

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/api/v1/operation-logs` | 查询全局日志 | 管理员 |
| GET | `/api/v1/operation-logs/{log_id}` | 日志详情 | 管理员或项目授权用户 |
| GET | `/api/v1/operation-logs/export` | 导出筛选结果 | 管理员 |
| GET | `/api/v1/operation-logs/retention-policy` | 查询保留策略 | 管理员 |
| PUT | `/api/v1/operation-logs/retention-policy` | 修改保留策略 | 管理员 |
| POST | `/api/v1/operation-logs/cleanup` | 手动清理日志 | 管理员 |

项目级接口：

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/api/v1/projects/{project_id}/operation-logs` | 查询项目日志 | 管理员、项目授权测试工程师、访客只读 |

查询参数：

- `page`
- `page_size`
- `project_id`
- `module`
- `action`
- `object_type`
- `actor_id`
- `result`
- `log_type`
- `keyword`
- `start_time`
- `end_time`

返回结构保持现有 API 风格，列表包含 `items`、`total`、`page`、`page_size`。

### 日志写入服务

`operation_log_service` 提供统一方法：

- `record_success(...)`
- `record_failure(...)`
- `record_change(...)`
- `record_task_event(...)`
- `record_agent_run(...)`

服务职责：

- 生成日志 ID 和时间。
- 脱敏 `before_json`、`after_json`、`summary` 中的敏感字段。
- 将 Python dict 序列化为 JSON。
- 对日志写入失败做降级处理：普通业务日志不阻断主流程，高风险日志失败时返回可提示错误。

敏感字段匹配：

- `password`
- `token`
- `api_key`
- `secret`
- `authorization`
- `cookie`
- `captcha`
- `verification_code`
- `access_key`

脱敏输出统一为 `******`。

### 接入顺序

第一批必须接入：

- 登录成功/失败、登出。
- 项目创建、编辑、删除、归档、恢复。
- 需求新建、追加文件、删除、归并发起、确认归并、取消归并。
- 系统设置修改、连通性检查。
- 模型 Provider 新增、编辑、删除、连通性检查。
- 任务创建、开始、成功、失败、取消、重试。

第二批接入：

- 站点探索。
- 知识库。
- 测试用例。
- 测试计划、测试集。
- UI 自动化、报告、失败诊断、自愈。

## 前端设计

### 页面与路由

新增系统日志页：

- `apps/frontend/src/app/(main)/settings/logs/page.tsx`

新增项目日志页：

- `apps/frontend/src/app/(main)/projects/[projectId]/logs/page.tsx`

可选组件目录：

- `apps/frontend/src/components/ai-testing/operation-logs/operation-log-table.tsx`
- `apps/frontend/src/components/ai-testing/operation-logs/operation-log-filters.tsx`
- `apps/frontend/src/components/ai-testing/operation-logs/operation-log-detail-drawer.tsx`
- `apps/frontend/src/components/ai-testing/operation-logs/operation-log-retention-dialog.tsx`

### 系统日志页面

位置：

- 系统设置下新增“日志”入口或页签。

能力：

- 列表展示时间、模块、动作、对象、操作人、结果、摘要。
- 筛选时间范围、模块、动作、对象类型、操作人、结果、项目。
- 关键词搜索对象名称、摘要、失败原因。
- 点击行打开详情抽屉。
- 管理员可打开保留策略弹窗。
- 管理员可导出当前筛选结果。

### 项目日志页面

位置：

- 项目详情模块入口新增“项目日志”。

能力：

- 固定按当前 `projectId` 查询。
- 不展示项目筛选。
- 支持模块、动作、操作人、结果、时间范围、关键词筛选。
- 日志详情支持跳转关联对象；对象已删除时不显示跳转。

### 展示文案映射

动作枚举：

| 枚举 | 中文 |
| --- | --- |
| create | 新增 |
| update | 编辑 |
| delete | 删除 |
| archive | 归档 |
| restore | 恢复 |
| merge | 归并 |
| confirm | 确认 |
| cancel | 取消 |
| run | 执行 |
| retry | 重试 |
| export | 导出 |
| upload | 上传 |
| login | 登录 |
| logout | 登出 |

结果枚举：

| 枚举 | 中文 |
| --- | --- |
| success | 成功 |
| failed | 失败 |
| partial_success | 部分成功 |
| cancelled | 已取消 |

### 权限表现

- 管理员：系统日志、项目日志、导出、保留策略、清理。
- 测试工程师：仅授权项目日志，无导出、无清理、无系统日志。
- 访客：仅项目内只读日志，隐藏敏感配置详情。

前端必须以后端权限结果为准；无权限返回 403 时跳转或展示无权限页。

## 验收标准

- 管理员可以进入系统日志页面并筛选日志。
- 项目详情可以进入项目日志页面，只展示当前项目日志。
- 创建、编辑、删除项目后能查到对应日志。
- 新建需求、追加文件、需求归并确认后能查到对应日志。
- 系统设置修改和模型配置修改能查到配置变更日志。
- 日志详情展示变更前后摘要、失败原因、关联任务和产物路径。
- 日志中不出现明文密码、token、API Key、验证码。
- 测试工程师不能访问全局日志；未授权项目日志返回 403。
- 后端单元测试覆盖脱敏、筛选、权限、写入失败降级。
- 前端 lint/typecheck 不因新增页面产生错误。
