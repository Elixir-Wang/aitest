# 00-06 AI测试系统 - 项目管理 PRD

> **基线日期**：2026-07-26
>
> **事实源**（源码为唯一事实源）：
> - 前端项目列表：`apps/frontend/src/app/(main)/projects/page.tsx`
> - 前端项目详情：`apps/frontend/src/app/(main)/projects/[projectId]/page.tsx`
> - 前端项目设置：`apps/frontend/src/app/(main)/projects/[projectId]/settings/page.tsx`
> - 前端项目日志：`apps/frontend/src/app/(main)/projects/[projectId]/logs/page.tsx`
> - 后端路由：`apps/backend/app/api/v1/projects.py`
> - 后端服务：`apps/backend/app/services/project_service.py`
> - 数据库 Repo：`apps/backend/app/repositories/project_repo.py`
> - 数据库 Schema：`apps/backend/app/seed/schema.py`
> - 系统种子：`apps/backend/app/seed/seeds.py`
>
> **状态标签**：`已实现`

---

## 1. 范围与目标

本文细化项目管理。项目是 AI 测试系统第一业务边界，需求文档、站点探索、知识库、测试用例、UI 自动化代码、接口自动化、性能测试、执行记录和报告都必须归属于项目。

权限管理见 `00-02-AI测试系统-权限管理PRD.md`。
控制台见 `00-07-AI测试系统-控制台PRD.md`。

---

## 2. 项目边界

### 2.1 项目负责隔离

- 源文档（需求文档上传、版本管理）
- 需求分析（分析运行、澄清问题、版本记录）
- 站点探索（探索运行、页面事实、locator）
- 项目知识库（项目知识问答、检索设置）
- 公司知识库关联（跨项目独立管理，但可被项目知识问答引用）
- 测试用例（用例集、手工用例、评审状态）
- UI 自动化（生成任务、资产、执行记录）
- 接口自动化（OpenAPI 文档、端点、测试用例、场景、脚本、执行记录）
- 性能测试（测试配置、脚本、执行记录、AI 分析）
- 自动化执行记录（pytest 报告、Locust 报告、Playwright trace、截图、视频）
- 失败诊断和自愈记录
- 项目环境配置（站点地址、登录策略）

### 2.2 项目不负责

- 不负责系统级模型 Provider 配置（系统管理功能）
- 不负责全局用户管理（用户与权限管理功能）
- 公司知识库不归属任何项目，可被多个项目引用

---

## 3. 数据模型

### 3.1 projects

主表，存储项目基本信息。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | TEXT | PK | 项目唯一标识，格式 `project-{hex}` |
| name | TEXT | NOT NULL, UNIQUE | 项目名称 |
| code | TEXT | NOT NULL DEFAULT '' | 项目编码（预留字段，当前不可写） |
| default_site_url | TEXT | NOT NULL DEFAULT '' | 默认站点地址（预留字段，当前不可写） |
| status | TEXT | NOT NULL CHECK('active','archived') | 项目状态：`active`=活跃，`archived`=归档 |
| description | TEXT | NOT NULL DEFAULT '' | 项目描述 |
| created_by | TEXT | NOT NULL DEFAULT 'system' | 创建人 ID |
| created_at | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**业务约束**：系统保留项目（`__all_projects__`）不能被编辑和删除，由 `SYSTEM_RESERVED_PROJECT_IDS = ("__all_projects__",)` 在 `project_repo.py` 中硬编码屏蔽。

### 3.2 project_environments

项目环境表，每个项目可有多个环境（测试、预发、生产等）。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | TEXT | PK | 环境唯一标识 |
| project_id | TEXT | FK → projects(id) ON DELETE CASCADE | 所属项目 |
| name | TEXT | NOT NULL | 环境名称 |
| site_url | TEXT | NOT NULL | 站点 URL |
| username | TEXT | NOT NULL DEFAULT '' | 登录用户名（加密存储） |
| password_encrypted | TEXT | NOT NULL DEFAULT '' | 加密密码（历史字段，已迁移至 password_hash） |
| password_hash | TEXT | NOT NULL DEFAULT '' | bcrypt 密码哈希 |
| login_strategy | TEXT | NOT NULL DEFAULT 'skip_login' | 登录策略 |
| captcha_strategy | TEXT | NOT NULL DEFAULT 'none' | 验证码策略 |
| reuse_auth_state | INTEGER | NOT NULL DEFAULT 1 | 是否复用认证状态 |
| description | TEXT | NOT NULL DEFAULT '' | 环境描述 |
| created_by | TEXT | NOT NULL | 创建人 |
| created_at | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | 更新时间 |
| | | UNIQUE(project_id, name) | 项目内环境名称唯一 |

### 3.3 knowledge_search_source_settings

知识检索来源开关表，控制不同作用域的知识检索来源。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| scope_key | TEXT | PK, NOT NULL | 作用域标识，如 `__all_projects__` 或 `project-{id}` |
| source_type | TEXT | PK, NOT NULL | 来源类型（如 `project_documents`、`company_knowledge` 等） |
| enabled | INTEGER | NOT NULL CHECK(0,1) | 是否启用：0=禁用，1=启用 |
| created_by | TEXT | NOT NULL | 创建人 |
| updated_by | TEXT | NOT NULL | 更新人 |
| created_at | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**复合主键**：(scope_key, source_type)，同一作用域可独立控制每种来源的启用状态。

---

## 4. 项目字段

| 字段 | 必填 | 说明 |
|---|---|---|
| 项目名称（name） | 是 | 页面展示名称，唯一约束 |
| 项目编码（code） | 否 | 预留字段，当前 UI 和 API 均不可写 |
| 项目描述（description） | 否 | 测试项目背景，在项目列表中展示 |
| 默认站点地址（default_site_url） | 否 | 预留字段，当前 UI 和 API 均不可写 |
| 项目状态（status） | 是 | `active`（活跃）或 `archived`（归档） |
| 创建时间 | 是 | 系统生成 |
| 更新时间 | 是 | 系统生成 |

**用户-项目成员关系**：无独立 members 表，通过用户的 `project_scope` 文本字段（`users.project_scope`）实现。

---

## 5. 项目列表

### 5.1 列表字段

| 字段 | 展示规则 |
|---|---|
| 项目名称 | 主标题，超长省略，悬停显示完整名称；已归档项目在名称旁展示"归档"标签 |
| 项目描述 | 超长省略，悬停显示完整内容 |
| 状态 | `active` → "活跃"；`archived` → "归档" |
| 最近更新时间 | 项目最近更新时间 |
| 操作 | 概览、编辑、删除（含批量删除） |

### 5.2 筛选

前端本地搜索，覆盖项目名称、描述、状态标签和更新时间。

### 5.3 权限

- **管理员**（role=`admin`）：调用 `project_repo.list_all()`，看到全部普通项目（不含系统保留项目 `__all_projects__`），可执行所有写操作。
- **测试工程师**（role=`tester`）：调用 `project_repo.list_visible()`，若 `project_scope = '全部项目'` 则看到所有 `status != 'archived'` 的项目，否则只看 `name = project_scope` 的项目。可读但所有写操作不可用。
- **访客**（role=`guest`）：同测试工程师的可见性，所有写操作不可用。

### 5.4 操作

| 操作 | 管理员 | 测试工程师 | 访客 | 说明 |
|---|---|---|---|---|
| 概览 | 可用 | 仅分配项目 | 可用 | 进入项目查看页 |
| 编辑 | 可用 | 不可用 | 不可用 | 编辑项目名称、描述和状态 |
| 删除 | 可用（前提：无资产、无需求） | 不可用 | 不可用 | 删除项目 |
| 批量删除 | 可用 | 不可用 | 不可用 | 批量删除选中的项目 |

**删除前置校验**（`project_service.delete_project`）：
1. 系统保留项目不可删除。
2. 若 `has_project_assets()` 返回 true（存在 source_documents / exploration_runs / test_cases / automation_cases / automation_runs / project_environments / performance_tests 任一记录），拒绝删除。
3. 若存在需求文档名称，提示哪些需求阻塞删除。

---

## 6. 创建、编辑项目

### 6.1 创建项目

- **权限**：仅管理员。
- **入口**：项目列表页工具栏"新建项目"按钮。
- **字段**：项目名称（必填）、项目状态（默认 `active`）、项目描述（选填）。
- **限制**：项目名称全局唯一，重复时报 `409 PROJECT_CONFLICT`。
- **操作日志**：记录 `module=project, action=create`，摘要 `"新建项目：{name}"`。

### 6.2 编辑项目

- **权限**：仅管理员。
- **入口**：项目列表行操作"编辑"按钮，或项目详情页。
- **可编辑字段**：名称（唯一约束）、描述、状态。
- **限制**：系统保留项目不可编辑，尝试编辑时报 `409 PROJECT_SYSTEM_RESERVED`。
- **操作日志**：记录 `module=project, action=update`，摘要 `"编辑项目：{name}"`，before/after 记录名称、描述、状态变化。

### 6.3 归档项目

- **权限**：仅管理员（通过编辑项目状态实现）。
- **效果**：状态改为 `archived` 后，项目从测试工程师的可见列表中隐藏（仍可通过 ID 直接访问）。
- **注意**：当前实现**无后端强制校验**禁止归档项目新建任务，需后续迭代。

---

## 7. 项目成员管理

**当前实现无独立 members 表**，通过用户 `users.project_scope` 文本字段实现：

- `project_scope = '全部项目'`：用户可访问系统内所有非归档项目。
- `project_scope = '{项目名称}'`：用户仅可访问该特定项目（精确匹配）。
- admin 角色的用户不受 `project_scope` 限制（见 `list_visible` 中 `role in {'admin', 'guest'}` 的分支逻辑）。

此设计为**粗粒度**权限模型，适合"用户归属单一项目"的简单场景。精细化成员管理（多人多项目、一人多项目）需独立 members 表，属于后续迭代范围。

---

## 8. `__all_projects__` 虚拟项目

### 8.1 概述

`__all_projects__` 是系统通过种子数据插入的保留项目（id 硬编码，名称为"全部项目知识库"）。

- **用途**：承担跨项目对话的 `knowledge_conversations` 作用域，以及全局知识检索设置（`knowledge_search_source_settings` 的 scope_key = `__all_projects__`）。
- **不显示在项目列表**：`list_projects` 通过 `SYSTEM_RESERVED_PROJECT_IDS` 过滤排除。
- **不可编辑**：尝试编辑或删除时报 `409 PROJECT_SYSTEM_RESERVED`。

### 8.2 种子数据

```python
# seeds.py:_ensure_all_projects_conversation_scope()
INSERT INTO projects (id, name, status, description, created_by)
VALUES ('__all_projects__', '全部项目知识库', 'archived',
        '系统保留项目，用于全部项目知识库对话历史。', 'system')
```

---

## 9. `__global_environments__` 历史虚拟项目

历史版本中曾存在名为 `__global_environments__` 的虚拟项目，用于存放全局环境配置。

**当前状态**：已迁移完成。`seeds.py` 中包含迁移函数 `_migrate_project_environment_scope()`，将原全局环境迁移至各具体项目的 `project_environments` 表。

代码库中已无 `__global_environments__` 相关逻辑，该历史设计不再生效。

---

## 10. AI 探索目标优化

### 10.1 端点

```
POST /projects/{project_id}/exploration-goal/optimize
```

### 10.2 请求与响应

**请求体**（`ExplorationGoalOptimizeRequest`）：

```json
{
  "goal": "原始探索目标文本"
}
```

**响应**（`ExplorationGoalOptimizeResponse`）：

```json
{
  "optimized_goal": "优化后的编号步骤清单"
}
```

### 10.3 实现逻辑

调用方：前端站点探索页面，提交自然语言探索目标。

1. 验证项目存在，不存在返回 `404 NOT_FOUND`。
2. 通过 `resolve_model_selection("page_exploration")` 获取模型配置，未配置时报 `500 MODEL_NOT_CONFIGURED`。
3. 系统提示词要求将目标整理为**编号步骤格式**（1. 2. 3.），每步描述一个可执行操作，保留用户原文关键词。
4. LLM 返回纯文本步骤清单，无 Markdown 格式要求。

### 10.4 权限

所有登录用户可用（`Depends(current_user)`）。

---

## 11. 项目设置（当前边界）

路径：`/projects/{projectId}/settings`

### 11.1 当前状态

项目设置页**主要是静态展示**：

- 展示项目名称、ID、状态、描述（从 `/projects` 接口获取）。
- 展示 3 个 MetricCard：项目资料完整、权限范围已配置、环境配置 3 个。
- 展示 4 个操作按钮：**均未连接写 API**，点击无后端交互：
  - "配置成员权限" → 静态按钮
  - "配置环境变量" → 静态按钮
  - "归档项目" → 静态按钮
  - "保存设置" → 静态按钮

### 11.2 待实现功能

以下功能按钮已规划但**尚未实现后端连接**（属于后续迭代范围）：

- 成员权限配置：管理谁可以访问此项目。
- 环境变量配置：管理项目级密钥或 API 凭证。
- 归档操作：替代通过编辑项目状态归档的路径，提供更明确的操作入口。

---

## 12. 项目日志

### 12.1 端点

```
GET  /projects/{project_id}/operation-logs          # 列表
GET  /projects/{project_id}/operation-logs/export  # CSV 导出
GET  /projects/{project_id}/operation-logs/filter-options  # 过滤下拉项
```

### 12.2 前端页面

路径：`/projects/{projectId}/logs`

使用 `OperationLogView` 组件，`endpoint` 绑定 `/projects/{projectId}/operation-logs`。

### 12.3 功能

- **作用域**：仅展示 `project_id = 当前项目` 的操作日志。
- **过滤条件**：日志类型（audit/config/task/agent）、模块、动作、操作对象、操作人、结果、关键词、时间范围。
- **分页**：默认每页 20 条，最大 200 条。
- **导出**：CSV 格式，最多 200 条。

### 12.4 记录触发方

项目级操作被 `project_service` 中的 `operation_log_service.record_*` 自动记录：

- 新建项目 → `record_success(module=project, action=create)`
- 编辑项目 → `record_change(module=project, action=update)`
- 删除项目 → `record_change(module=project, action=delete)`

---

## 13. API 路由清单

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/projects` | 登录用户 | 项目列表（自动过滤系统保留项目） |
| POST | `/projects` | require_admin | 创建项目 |
| PATCH | `/projects/{project_id}` | require_admin | 编辑项目（系统保留项目除外） |
| DELETE | `/projects/{project_id}` | require_admin | 删除项目（系统保留项目、有资产项目除外） |
| POST | `/projects/{project_id}/exploration-goal/optimize` | current_user | AI 优化探索目标 |
| GET | `/projects/{project_id}/operation-logs` | current_user | 项目操作日志列表 |
| GET | `/projects/{project_id}/operation-logs/export` | current_user | 项目操作日志 CSV 导出 |
| GET | `/projects/{project_id}/operation-logs/filter-options` | current_user | 操作日志过滤下拉项 |

---

## 14. 前端页面清单

| 路径 | 组件文件 | 说明 |
|---|---|---|
| `/projects` | `projects/page.tsx` | 项目列表页，含新建/编辑/删除/批量删除对话框 |
| `/projects/{projectId}` | `projects/[projectId]/page.tsx` | 项目详情页，含概览信息卡片和模块入口按钮 |
| `/projects/{projectId}/settings` | `projects/[projectId]/settings/page.tsx` | 项目设置页（静态展示，按钮未连接 API） |
| `/projects/{projectId}/logs` | `projects/[projectId]/logs/page.tsx` | 项目日志页，使用 OperationLogView 组件 |

---

## 15. 验收规则

### 已实现

- [x] 管理员可以创建项目（项目名称全局唯一，重复报错 `409 PROJECT_CONFLICT`）
- [x] 管理员可以编辑项目名称、描述、状态（系统保留项目除外）
- [x] 管理员可以删除无资产、无需求的普通项目
- [x] 系统保留项目 `__all_projects__` 在项目列表中不显示，编辑/删除时报 `409 PROJECT_SYSTEM_RESERVED`
- [x] `__global_environments__` 历史虚拟项目已迁移，环境数据存在于 `project_environments` 表
- [x] 项目列表展示：项目名称、描述、状态、最近更新时间、操作列
- [x] 项目列表支持前端本地搜索（项目名称、描述、状态、更新时间）
- [x] 管理员可批量删除选中的项目
- [x] 测试工程师只看到通过 `project_scope` 分配给自己的项目；访客可查看全部但不可写
- [x] 项目详情能跳转到：需求、探索、测试用例、项目日志
- [x] `POST /projects/{project_id}/exploration-goal/optimize` 返回 LLM 整理的编号步骤清单
- [x] `GET /projects/{project_id}/operation-logs` 支持分页、过滤和 CSV 导出
- [x] 项目设置页展示项目基本信息（4 个操作按钮当前为静态，未连接 API）

### 待实现

- [ ] 归档项目禁止新建任务的后端强制校验（当前仅通过列表筛选实现前端隐藏）
- [ ] 项目设置页的"配置成员权限"按钮连接后端 API
- [ ] 项目设置页的"配置环境变量"按钮连接后端 API
- [ ] 项目设置页的"归档项目"按钮连接后端 API
- [ ] `projects.code` 和 `projects.default_site_url` 字段的 API 可写支持
- [ ] 精细化成员管理（多用户多项目、一人多项目）独立 members 表
