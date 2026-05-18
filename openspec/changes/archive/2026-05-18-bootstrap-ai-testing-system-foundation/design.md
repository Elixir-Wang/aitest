## Context

本变更是 AI 测试系统的第一阶段系统地基。当前仓库已有完整 PRD 拆分、前端总体方案、导航映射、后端架构和数据模型说明，但尚未形成可编码的 OpenSpec 设计与任务。第一阶段必须先落地用户权限、项目工作区、导航与项目上下文、任务中心、系统设置和统一 API 平台，否则后续需求分析、站点探索、知识库、测试用例、UI 自动化、诊断和自愈都会重复处理权限、项目隔离、任务状态、错误响应和页面壳层。

本设计以 `apps/frontend` 和 `apps/backend` 为目标落地目录，前端参考 `next-shadcn-admin-dashboard-main`，后端使用 FastAPI + SQLite + 本地文件系统 + 本地任务运行封装。所有用户可见文案以中文为主，后端枚举可使用英文。

## Goals / Non-Goals

**Goals:**

- 建立三类角色的登录、当前用户、项目可见性和写操作权限门禁。
- 建立项目列表、项目详情、新建/编辑/归档/恢复、项目成员分配。
- 建立左侧一级导航、页面内二级导航、项目切换器和工作分区规则。
- 建立任务中心基础，包括 TaskRun、TaskEvent、任务列表、详情、状态、事件时间线和操作框架。
- 建立系统设置基础入口，包括文件存储、本地 Runner、Playwright、Allure、Agent 安全策略。
- 建立统一 API 响应、错误结构、`trace_id`、`available_actions`、权限依赖、状态门禁和审计事件。
- 建立 SQLite 基础表，并为后续模块保留项目隔离、任务关联、状态审计和文件路径引用模式。

**Non-Goals:**

- 不实现需求文档分析、澄清写回、需求评审。
- 不实现站点探索、候选需求生成和 Playwright CLI 调度。
- 不实现知识库生成、更新、发布和 llm-wiki 产物管理。
- 不实现测试用例生成、评审、采纳和覆盖矩阵。
- 不实现 UI 自动化代码生成、本地 pytest 执行和 Allure 报告归档。
- 不实现失败诊断、自愈补丁生成、应用和验证。
- 不实现接口自动化；仅保留 Soon 占位。
- 不实现真实 Agent Runtime 编排、模型调用和 Skill 调度。

## Decisions

### 1. 以项目为第一业务隔离边界

后端所有项目内资源和任务必须保存 `project_id`，列表查询必须按当前用户可见项目过滤。管理员和访客可见全部项目，测试工程师只可见分配项目。项目归档后仍可读，但禁止新建任务和写入项目资产。

选择原因：PRD 已明确项目是需求、探索、知识库、用例、自动化、报告和诊断的第一隔离边界。先落地项目隔离，可避免后续模块补权限时返工。

替代方案：使用全局资源加可选项目过滤。该方案会让后续模块容易漏掉项目门禁，放弃。

### 2. 后端按 API / Service / Domain / Repository / Storage / Worker 分层

- API 层负责路由、参数校验、依赖注入和响应包装。
- Service 层负责权限校验、状态门禁、事务控制、`available_actions` 编排和审计事件。
- Domain 层负责枚举、状态规则和领域判断。
- Repository 层只负责 SQLite 读写。
- Storage 层负责文件路径、安全根目录和产物引用，第一阶段只提供配置与基础工具。
- Worker 层负责异步任务执行，第一阶段先实现本地任务状态框架，不接真实 Agent/CLI。

选择原因：PRD 明确要求业务判断不进入 Repository，文件访问不由业务模块拼路径，任务状态和业务对象状态分离。

替代方案：按模块写独立 CRUD 路由。短期快，但会导致权限、响应、状态、错误处理不一致，放弃。

### 3. 统一 API 响应和错误结构

成功响应统一为 `{ data, trace_id }`；列表响应在 `data` 内返回 `items`、`pagination` 和可选 `filters`；详情响应返回 `item`、`source_refs`、`related_tasks`、`available_actions`；错误响应返回 `{ error: { code, message, detail, trace_id } }`。所有 API 使用 `/api/v1` 前缀。

选择原因：前端需要稳定的 API 适配层和统一错误展示，后续 Agent、任务、文件和状态门禁也需要一致 trace。

替代方案：每个模块自定义响应。该方案会增加前端分支和测试成本，放弃。

### 4. `available_actions` 由后端计算

后端根据当前用户、角色、项目、对象状态和业务门禁返回操作项。字段包含 `key`、`label`、`enabled`、`disabled_reason`、`risk_level`、`confirm_required`、`target_url`。前端只根据结果展示按钮、禁用态和确认弹窗，不自行推断核心权限。

选择原因：权限和状态门禁必须以后端为准，访客只读、测试工程师项目范围、归档项目禁止写入等规则不能只依赖前端。

替代方案：前端根据角色和状态自行判断按钮。容易出现显示和后端权限不一致，放弃。

### 5. 前端只保留左侧一级导航，二级功能放页面内

左侧导航采用 `NavGroup -> NavMainItem`，不常驻二级菜单。项目切换器固定在相关页面右上角。模块内二级功能使用 `ModuleTabs`、Segmented Control、卡片入口或面包屑承载。

选择原因：当前系统模块多，如果左侧同时承载项目树和二级功能，会导致后台首屏过载。项目切换器解决数据范围，页面内 Tabs 解决模块内功能切换，两者职责不同。

替代方案：左侧展示完整二级菜单。信息密度过高，且项目上下文不清晰，放弃。

### 6. 第一阶段页面结构

前端落地以下页面和状态：

| 模块 | 路由 | 页面结构 | 第一阶段能力 |
| --- | --- | --- | --- |
| 登录 | `/login` | 登录表单 | 用户名/邮箱、密码、登录失败通用提示 |
| 控制台 | `/dashboard` | PageShell + 项目切换器 | 基础统计占位、最近任务、待处理入口 |
| 项目 | `/projects` | PageShell + DataTable | 项目列表、搜索、新建、查看、编辑、归档/恢复 |
| 项目详情 | `/projects/:projectId` | DetailShell + Tabs | 概览、成员、设置、最近任务、模块入口 |
| 任务中心 | `/tasks` | PageShell + DataTable | 全部任务、等待人工、失败任务、任务详情入口 |
| 任务详情 | `/tasks/:taskId` | RunShell | 状态摘要、事件时间线、输入摘要、输出摘要、日志摘要、操作 |
| 用户与权限 | `/settings/users` | PageShell + DataTable + Dialog | 用户列表、创建用户、启用/禁用、角色修改、项目分配入口 |
| 系统设置 | `/settings/system` | PageShell + Tabs | 文件存储、本地 Runner、Playwright、Allure、Agent 安全策略 |
| 模型配置 | `/settings/models` | PageShell + Soon/配置占位 | Provider 和模型用途配置入口，真实模型调用不在本阶段 |
| 接口自动化 | `/projects/:projectId/automation/api` | SoonPage | 展示 Soon，不允许创建、生成、执行 |

项目强绑定模块如需求、探索、知识库、测试用例、UI 自动化可先提供导航入口和空状态/占位页，不能实现真实业务生成和执行。

### 7. 基础数据模型

第一阶段落地基础表：

| 表 | 目的 |
| --- | --- |
| `users` | 用户账号、邮箱、昵称、角色、状态、密码哈希、最近登录 |
| `sessions` 或等价会话存储 | 登录态和过期时间 |
| `projects` | 项目名称、编码、描述、默认站点、默认环境、负责人、归档时间 |
| `project_members` | 项目与测试工程师分配关系 |
| `task_runs` | 异步任务主记录、状态、类型、来源、项目、进度、结果摘要 |
| `task_events` | 任务事件时间线、阶段摘要、错误摘要、结果跳转 |
| `system_settings` | 系统配置键值，按配置域分组 |
| `audit_events` | 高风险操作、状态变化和权限相关审计 |

枚举建议：

- 用户角色：`admin`、`tester`、`guest`
- 用户状态：`active`、`disabled`
- 项目生命周期：正常项目用 `archived_at = null` 表示，已归档项目用 `archived_at != null` 表示
- 任务状态：`queued`、`running`、`waiting_human`、`success`、`failed`、`cancelled`、`expired`
- 风险等级：`normal`、`warning`、`danger`

### 8. 后端模块设计

| 模块 | API | Service | Repository/Storage | 说明 |
| --- | --- | --- | --- | --- |
| auth | `/auth/login`、`/auth/logout`、`/auth/me` | 登录校验、会话创建、禁用用户拦截 | users、sessions | 不提供公开注册 |
| users | `/users`、`/users/{id}`、`/users/{id}/status`、`/users/{id}/projects` | 用户创建、角色修改、禁用、项目分配 | users、project_members、audit_events | 写操作仅管理员 |
| projects | `/projects`、`/projects/{id}`、`/projects/{id}/archive`、`/projects/{id}/restore` | 项目可见性、唯一编码、归档门禁、成员维护 | projects、project_members、task_runs | 测试工程师只读分配项目，访客只读全部 |
| tasks | `/tasks`、`/tasks/{id}`、`/tasks/{id}/cancel`、`/tasks/{id}/retry` | 任务查询、状态门禁、重试创建、取消请求 | task_runs、task_events | 第一阶段只实现框架任务，不接真实业务 Worker |
| settings | `/settings/system`、`/settings/system/{key}`、`/settings/system/check` | 配置读取、保存、脱敏、检查占位 | system_settings、audit_events、Storage root check | 敏感值不明文返回 |
| platform | middleware/dependencies | trace_id、响应包装、错误转换、权限依赖、available_actions | audit_events | 为所有模块复用 |

### 9. 任务流转

第一阶段任务中心支持以下状态流：

```text
queued -> running -> success
queued -> running -> failed
queued -> cancelled
running -> waiting_human -> running
running -> cancelled
failed -> retry creates new queued task
success/failed/cancelled -> expired only when被新任务替代
```

任务事件至少记录：`task_created`、`task_started`、`task_progress`、`task_waiting_human`、`task_failed`、`task_cancel_requested`、`task_cancelled`、`task_retry_created`、`task_succeeded`。第一阶段事件内容以摘要和跳转为主，高频日志只保存日志路径或摘要字段。

### 10. 权限规则

| 场景 | 管理员 | 测试工程师 | 访客 |
| --- | --- | --- | --- |
| 查看全部项目 | 允许 | 不允许 | 允许 |
| 查看分配项目 | 允许 | 允许 | 允许 |
| 创建/编辑/归档项目 | 允许 | 禁止 | 禁止 |
| 分配项目成员 | 允许 | 禁止 | 禁止 |
| 查看任务 | 全部 | 分配项目 | 全部 |
| 取消/重试任务 | 允许 | 仅分配项目且任务允许 | 禁止 |
| 修改系统设置 | 允许 | 禁止 | 禁止 |
| 查看脱敏系统设置 | 允许 | 可按需要只读 | 允许只读 |

后端必须在每个写接口校验权限；前端禁用按钮只是体验层。

## Risks / Trade-offs

- [Risk] 第一阶段范围仍然偏大，可能拖慢进入编码。→ Mitigation: tasks 按后端平台、前端壳层、用户权限、项目、任务、设置分段，每段可独立验证。
- [Risk] 系统设置涉及敏感路径和密钥，过早设计复杂加密会拖慢地基。→ Mitigation: 第一阶段只实现脱敏返回和本地存储边界，密钥加密可在真实模型/Runner 接入前增强。
- [Risk] 任务中心没有真实业务 Worker，页面可能像空壳。→ Mitigation: 提供框架任务和事件创建能力，后续业务模块复用同一 TaskRun/TaskEvent。
- [Risk] `available_actions` 增加后端实现复杂度。→ Mitigation: 第一阶段只覆盖用户、项目、任务、设置和 Soon 占位的动作，后续模块扩展同一结构。
- [Risk] 前端项目切换器和路由 `:projectId` 同时存在，可能出现上下文不一致。→ Mitigation: 进入项目强绑定路由时以 URL projectId 为准，并同步更新最近项目；全局页面以 ProjectSwitcher 过滤范围为准。

## Migration Plan

当前项目尚未有已上线实现，第一阶段按初始化迁移处理：

1. 初始化 `apps/backend` 和 `apps/frontend` 基础工程结构。
2. 创建 SQLite schema 或迁移脚本。
3. 创建默认管理员账号的初始化机制。
4. 启动后端 API，验证统一响应、错误和 trace_id。
5. 启动前端壳层，验证登录、导航、项目切换器和基础页面。
6. 逐模块接入用户、项目、任务、设置 API。

回滚策略：保留迁移脚本和初始化脚本；若某个模块失败，可回滚该模块路由和前端页面入口，不影响已生成的 OpenSpec artifacts。

## Open Questions

- 会话存储第一阶段使用服务端 session 表还是 JWT Cookie，需要在实现前按现有模板和安全要求确认。
- 密码哈希库、默认管理员初始化方式和本地开发默认账号需要在编码任务中明确。
- `apps/frontend` 是否直接迁移 `next-shadcn-admin-dashboard-main`，还是新建应用后逐步复制壳层，需要编码前检查模板项目实际结构决定。
