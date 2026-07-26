# 00-02 AI测试系统 - 权限管理 PRD

> **基线日期**：2026-07-26
>
> **事实源**（源码为唯一事实源）：
>
> - 后端路由：`apps/backend/app/api/v1/auth.py`（`/auth/login`、`/auth/logout`、`/auth/me`）
> - 后端路由：`apps/backend/app/api/v1/users.py`（列表 / 创建 / 更新 / 删除；创建/更新/删除仅管理员）
> - 后端服务：`apps/backend/app/services/auth_service.py`（login / logout / me；失败/成功均经 `operation_log_service.record_*` 落审计）
> - 后端服务：`apps/backend/app/services/user_service.py`（CRUD + 审计）
> - 后端依赖：`apps/backend/app/dependencies/auth.py`（`current_user` / `require_admin` / `get_token`）
> - 数据库：`apps/backend/app/seed/schema.py`（`users` / `sessions` 表定义）
> - 项目过滤：`apps/backend/app/repositories/project_repo.py`（`SYSTEM_RESERVED_PROJECT_IDS = ("__all_projects__",)`；`list_visible`）
> - 项目服务：`apps/backend/app/services/project_service.py`（`list_projects` 按角色过滤 + 屏蔽保留项目）
> - 前端路由过滤：`apps/frontend/src/app/(main)/dashboard/_components/sidebar/nav-main.tsx:33-46,219-223`（`hasRequiredRole` + `visibleItems` 过滤）
> - 侧边栏定义：`apps/frontend/src/navigation/sidebar/sidebar-items.ts`（`requiredRole` 字段）
> - 前端状态：`apps/frontend/src/stores/auth-store.ts`
>
> **状态标签**：`已实现`（登录、登出、账号 CRUD、角色权限矩阵、项目可见性、审计）；`部分实现`（细粒度按钮级权限）

---

## 1. 范围与目标

本文细化 AI 测试系统的用户、登录、账号管理和权限体系。

**角色体系**（与 `00-01` 第 1.3 节对齐）：

| 角色 | 英文标识 | 说明 |
| --- | --- | --- |
| 管理员 | `admin` | 拥有系统和所有项目的完整管理权限 |
| 测试工程师 | `tester` | 只能查看和操作分配给自己的项目 |
| 访客 | `guest` | 全局只读，不能触发任何写操作 |

**关联文档**：

- 项目管理：`00-06-AI测试系统-项目管理PRD.md`
- 控制台：`00-07-AI测试系统-控制台PRD.md`
- 系统日志：`00-15-AI测试系统-系统设置PRD.md`

---

## 2. 三种角色权限矩阵

权限矩阵与 `00-01` 第 1.3 节保持一致，并细化当前实现状态。

| 功能 | 管理员 | 测试工程师 | 访客 | 说明 |
| --- | --- | --- | --- | --- |
| 查看全部项目列表 | ✅ | ❌（仅分配项目） | ✅ | admin/guest 调用 `project_repo.list_all`；tester 调用 `project_repo.list_visible`，按 `project_scope` 精确匹配项目名称 |
| 创建项目 | ✅ | ❌ | ❌ | |
| 编辑项目配置 | ✅ | ❌ | ❌ | |
| 归档/恢复项目 | ✅ | ❌ | ❌ | |
| 配置模型供应商 | ✅ | ❌ | ❌ | |
| 操作用户账号（增/删/改） | ✅ | ❌ | ❌ | |
| 查看用户列表 | ✅ | ✅ | ✅ | 后端 `GET /users` 当前仅要求登录（**缺口**，见第 7.2 节） |
| 上传需求文档 | ✅ | 仅分配项目 | ❌ | |
| 发起需求分析 | ✅ | 仅分配项目 | ❌ | |
| 发起站点探索 | ✅ | 仅分配项目 | ❌ | |
| 生成/更新知识库 | ✅ | 仅分配项目 | ❌ | |
| 生成/编辑测试用例 | ✅ | 仅分配项目 | ❌ | |
| 生成/执行 UI 自动化 | ✅ | 仅分配项目 | ❌ | |
| 查看接口自动化 | ✅ | 仅分配项目 | ✅ | 访客只读 |
| 确认自愈补丁 | ✅ | 仅分配项目 | ❌ | |
| 查看报告与缺陷诊断 | ✅ | 仅分配项目 | ✅ | 访客只读 |
| 查看系统日志 | ✅ | ❌ | ❌ | |

> **注**：tester 和 guest 对分配/授权范围外的项目没有任何访问权限，包括列表级可见性。项目可见性由后端 `project_service.list_projects` 强制过滤，不依赖前端隐藏。

---

## 3. 认证流程

### 3.1 技术方案

采用 **JWT Bearer Token** 方案（实际实现为服务端会话 token，非严格 JWT 规范）：

- 前端存储在 `localStorage`（记住登录）或 `sessionStorage`（会话）
- 每次请求通过 `Authorization: Bearer <token>` Header 传递
- Token 格式：`secrets.token_urlsafe(32)`（48 字符 URL-safe 随机串）
- 会话有效期：7 天（`datetime.now() + timedelta(days=7)`）
- 存储介质：SQLite `sessions` 表

### 3.2 登录流程

```
用户 → POST /auth/login {username, password}
  ├─ 用户不存在或密码错误 → record_failure → 401 "LOGIN_FAILED"
  ├─ 用户状态为 disabled  → record_failure → 401 "LOGIN_FAILED"
  └─ 验证通过
       ├─ 生成 token → 写入 sessions 表
       ├─ 更新 users.last_login_at
       ├─ record_success → 返回 {access_token, current_user}
       └─ 前端写入 localStorage/sessionStorage
```

### 3.3 登出流程

```
用户 → POST /auth/logout (Authorization: Bearer <token>)
  ├─ 通过 get_token 解析 Header
  ├─ 从 sessions 表查到 user
  ├─ 删除 sessions 表中该 token
  └─ record_success(logout) → 前端清除 localStorage/sessionStorage
```

### 3.4 当前用户接口

```
GET /auth/me (current_user 依赖注入)
  返回：
  {
    "user": { id, username, email, nickname, role, status, project_scope, ... },
    "roles": [role],
    "project_permissions": {
      "<project_scope文本>": ["read", "write"]
    }
  }
```

- `role == "admin"`：`actions = ["read", "write"]`（全局）
- `role == "tester"`：`actions = ["read", "write"]`（限 project_scope）
- `role == "guest"`：`actions = ["read"]`（全局只读）

> `project_permissions` 字段的 key 为 `users.project_scope` 的文本值（如 "全部项目" 或具体项目名称），这同时作为前端和后端判断授权边界的依据。

### 3.5 审计日志

所有认证动作均落入 `operation_logs` 表：

| 动作 | 触发条件 | 审计类型 | result |
| --- | --- | --- | --- |
| login（失败） | 用户名/密码错误 或 账号禁用 | audit | failed |
| login（成功） | 登录验证通过 | audit | success |
| logout | 登出请求 | audit | success |

审计字段：

- `module="auth"`, `action="login"` 或 `"logout"`
- `object_type="user"`, `object_id`, `object_name`
- `actor_id`, `actor_name`
- `source="web"`
- `failure_reason`（仅失败时）

---

## 4. 会话管理

### 4.1 sessions 表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| token | TEXT PRIMARY KEY | 48 字符随机串 |
| user_id | TEXT FK → users(id) ON DELETE CASCADE | 所属用户 |
| created_at | TEXT DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| expires_at | TEXT NOT NULL | 过期时间（UTC ISO 字符串） |

### 4.2 会话生命周期

- **创建**：登录成功后写入，token 由 `secrets.token_urlsafe(32)` 生成，有效期 7 天
- **验证**：`session_repo.get_user_by_active_token` 查询 token 对应的有效会话；若 token 不存在或会话已过期（`expires_at` < 当前时间），返回 401
- **删除**：登出时 `session_repo.delete(token)`；用户删除时通过 `ON DELETE CASCADE` 自动清理
- **过期清理**：当前实现依赖请求时惰性检查（查询时过滤过期记录），无独立后台清理任务

### 4.3 账号禁用与会话

禁用用户（`status = "disabled"`）**不会**自动删除其活跃会话。被禁用户下次请求时，`_current_user_for_token` 在第 31 行拦截：

```python
if row["status"] != "enabled":
    raise HTTPException(status_code=403, detail={"code": "PERMISSION_DENIED", "message": "账号已禁用。"})
```

> 缺口：禁用会话中的已有 token 理论上仍存在于 sessions 表，被禁用户若无新请求则会话不会主动失效。如需强制下线，需扩展清理逻辑。

---

## 5. 项目可见性

### 5.1 实现机制

通过 `users.project_scope` 文本字段控制：

- `"全部项目"`：可查看所有非归档、非保留项目（`status != 'archived'`）
- 具体项目名称：仅能查看该名称的项目

### 5.2 list_projects 过滤逻辑

```python
# project_service.list_projects
if actor["role"] == "admin":
    rows = project_repo.list_all(db)          # admin: 全量（排除归档和保留项目）
else:
    rows = project_repo.list_visible(db, actor)  # tester/guest: 按 project_scope 过滤

# 统一过滤：排除 __all_projects__ 保留项目
return [row for row in rows if row["id"] not in SYSTEM_RESERVED_PROJECT_IDS]
```

```python
# project_repo.list_visible
if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
    # admin 和 guest 看到所有非归档项目；tester 若 project_scope=="全部项目" 也如此
    return db.execute("SELECT * FROM projects WHERE status != 'archived' ...").fetchall()
return db.execute(
    "SELECT * FROM projects WHERE status != 'archived' AND name = ?",
    (actor["project_scope"],)
)
```

### 5.3 关键特性

- **tester 的 project_scope 可以是"全部项目"**，此时与 guest 行为一致（全量只读）
- **tester 和 guest 在 project_scope 文本匹配上的行为相同**：`project_scope != "全部项目"` 时，两者都只能看到对应名称的项目
- `project_scope` 值来源于 `projects.name`，而非 `projects.id`——这是当前设计的简化代价，不支持项目重命名后的联动更新

---

## 6. 系统保留项目

### 6.1 保留标识

```python
SYSTEM_RESERVED_PROJECT_IDS = ("__all_projects__",)
```

`__all_projects__` 是数据库中用于聚合统计的虚拟项目 ID，不是真实项目。

### 6.2 屏蔽规则

| 操作 | 规则 |
| --- | --- |
| `project_service.list_projects` | 最终返回前统一过滤：`row["id"] not in SYSTEM_RESERVED_PROJECT_IDS` |
| `project_service.update_project` | 若 project_id 在保留列表，抛 `PROJECT_SYSTEM_RESERVED` |
| `project_service.delete_project` | 若 project_id 在保留列表，抛 `PROJECT_SYSTEM_RESERVED` |

所有用户（包括 admin）都无法通过列表接口看到 `__all_projects__`，也无法编辑或删除它。

---

## 7. 前端权限门禁

### 7.1 侧边栏 requiredRole 过滤

`sidebar-items.ts` 中每个导航项可声明 `requiredRole`：

```typescript
// apps/frontend/src/navigation/sidebar/sidebar-items.ts
{
  title: "模型配置",
  url: "/settings/models",
  icon: Bot,
  requiredRole: "admin",    // admin 专属
},
{
  title: "性能测试",
  url: "/projects/:projectId/performance-tests",
  icon: Gauge,
  projectScoped: true,
  // 无 requiredRole：所有角色可见（具体是否可写由后端判断）
},
```

`nav-main.tsx` 第 219-223 行在渲染前过滤：

```typescript
const visibleItems = group.items.filter(
  (item) => hasRequiredRole(user?.role, item.requiredRole)
);
```

### 7.2 hasRequiredRole 逻辑

```typescript
// ROLE_RANK: admin(3) > tester(2) > guest(1)
const ROLE_RANK = { admin: 3, tester: 2, guest: 1 };

function hasRequiredRole(userRole, requiredRole): boolean {
  if (!requiredRole) return true;   // 无要求：所有角色可见
  if (!userRole) return false;
  return ROLE_RANK[userRole] >= ROLE_RANK[requiredRole];
}
```

> 效果：`requiredRole: "tester"` 时，admin 和 tester 可见，guest 不可见。

### 7.3 available_actions 字段

`GET /auth/me` 返回的 `project_permissions` 即为 `available_actions` 的实现：

```json
{
  "project_permissions": {
    "全部项目": ["read", "write"]    // admin/tester
    // 或
    "全部项目": ["read"]             // guest
    // 或
    "电商后台项目": ["read", "write"] // tester（限 project_scope）
  }
}
```

前端以此判断当前用户在当前项目上下文中是否可写。若 `actions` 不含 `"write"`，隐藏所有新增/编辑/删除/执行/确认按钮。

> 当前实现仅以 `project_scope` 为 key，不支持细粒度到每个功能模块的 action 列表。

---

## 8. 后端权限校验

### 8.1 FastAPI 依赖注入

| 依赖函数 | 文件 | 用途 |
| --- | --- | --- |
| `get_token` | `app/dependencies/auth.py` | 从 `Authorization: Bearer <token>` Header 解析 token；无 token 或格式错误返回 401 |
| `current_user` | `app/dependencies/auth.py` | 调用 `get_token`，再从 sessions 表查用户；未找到会话返回 401；status != "enabled" 返回 403 |
| `require_admin` | `app/dependencies/auth.py` | 在 `current_user` 基础上校验 `role == "admin"`；否则返回 403 |
| `get_token_or_locust_cookie` | `app/dependencies/auth.py` | 兼容 Locust UI session cookie 的 token 解析 |

### 8.2 路由级权限声明

| 接口 | 权限依赖 | 说明 |
| --- | --- | --- |
| `POST /auth/login` | 无（公开） | 登录 |
| `POST /auth/logout` | `get_token` | 登出 |
| `GET /auth/me` | `current_user` | 当前用户信息 |
| `GET /users` | `current_user` | 用户列表（**缺口**：仅要求登录，见 7.2 节） |
| `POST /users` | `require_admin` | 创建用户 |
| `PATCH /users/{user_id}` | `require_admin` | 更新用户 |
| `DELETE /users/{user_id}` | `require_admin` | 删除用户 |
| `POST /projects` | `require_admin` | 创建项目 |
| `PATCH /projects/{project_id}` | `require_admin` | 更新项目 |
| `DELETE /projects/{project_id}` | `require_admin` | 删除项目 |
| `POST /models/providers` | `require_admin` | 创建模型供应商 |
| `PATCH /models/providers/{id}` | `require_admin` | 更新模型供应商 |
| `DELETE /models/providers/{id}` | `require_admin` | 删除模型供应商 |
| `POST /environments` | `require_admin` | 创建环境 |
| `PATCH /environments/{id}` | `require_admin` | 更新环境 |
| `DELETE /environments/{id}` | `require_admin` | 删除环境 |
| `GET /operation-logs` | `require_admin` | 查看操作日志 |

> 更多写操作接口的 `require_admin` 校验详见 `apps/backend/app/api/v1/` 各路由文件。

### 8.3 禁止自删除

`user_service.delete_user` 第 102-103 行：

```python
if user_id == actor["id"]:
    raise api_error(400, "SELF_DELETE_DENIED", "不能删除当前登录账号。")
```

---

## 9. 审计

### 9.1 所有登录/登出/用户管理动作均落审计

| 模块 | 动作 | 触发入口 | record_* 调用 |
| --- | --- | --- | --- |
| auth | login（失败） | `auth_service.login` | `record_failure` |
| auth | login（成功） | `auth_service.login` | `record_success` |
| auth | logout | `auth_service.logout` | `record_success` |
| user | create | `user_service.create_user` | `record_change`（含 after） |
| user | update | `user_service.update_user` | `record_change`（含 before + after） |
| user | delete | `user_service.delete_user` | `record_change`（含 before） |

### 9.2 审计字段

所有审计日志写入 `operation_logs` 表，关键字段：

- `log_type = "audit"`（固定）
- `module`：auth / user
- `action`：login / logout / create / update / delete
- `object_type = "user"`
- `object_id` / `object_name`
- `actor_id` / `actor_name`
- `source = "web"`
- `result`：`success` / `failed`
- `failure_reason`：仅失败时填写
- `summary`：中文摘要
- `before_json` / `after_json`：变更前后快照（仅 change 类型）

---

## 10. 数据模型

### 10.1 users 表

```sql
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL UNIQUE,
  nickname TEXT,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin', 'tester', 'guest')),
  status TEXT NOT NULL CHECK(status IN ('enabled', 'disabled')),
  project_scope TEXT NOT NULL DEFAULT '全部项目',
  description TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at TEXT
);
```

| 字段 | CHECK 约束 | 默认值 | 说明 |
| --- | --- | --- | --- |
| role | `IN ('admin', 'tester', 'guest')` | — | 不可为空 |
| status | `IN ('enabled', 'disabled')` | — | 不可为空；disabled 账号不能登录 |
| project_scope | 无额外约束 | `'全部项目'` | 文本值；精确匹配项目名称 |
| password_hash | — | — | bcrypt 加密存储 |
| last_login_at | — | NULL | 登录成功后由 `user_repo.update_login_time` 更新 |

### 10.2 sessions 表

```sql
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

| 字段 | 说明 |
| --- | --- |
| token | 48 字符 URL-safe 随机串 |
| expires_at | UTC ISO 字符串；请求时惰性检查是否过期 |
| ON DELETE CASCADE | 用户删除时自动清理其所有会话 |

---

## 11. API 路由清单

### 11.1 认证模块（`/auth/*`）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/auth/login` | 公开 | 登录；body: `{username, password}` |
| POST | `/auth/logout` | Bearer Token | 登出；Header: `Authorization: Bearer <token>` |
| GET | `/auth/me` | 登录用户 | 当前用户信息 + `project_permissions` |

### 11.2 用户管理模块（`/users`）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/users` | 登录用户 | 用户列表（**缺口**：未限制为管理员） |
| POST | `/users` | require_admin | 创建用户 |
| PATCH | `/users/{user_id}` | require_admin | 更新用户 |
| DELETE | `/users/{user_id}` | require_admin | 删除用户；禁止自删除 |

---

## 12. 前端组件清单

| 组件路径 | 说明 | 权限关联 |
| --- | --- | --- |
| `src/navigation/sidebar/sidebar-items.ts` | 导航项定义，含 `requiredRole` | `requiredRole: "admin"` 用于系统管理类菜单 |
| `src/app/(main)/dashboard/_components/sidebar/nav-main.tsx` | 侧边栏渲染，含 `hasRequiredRole` 过滤逻辑 | 第 219-223 行过滤不可见菜单组 |
| `src/stores/auth-store.ts` | 认证状态管理（token / user 存储） | `login`/`logout` 方法对应 `/auth/login`/`/auth/logout` |
| `src/app/(main)/settings/users/page.tsx` | 用户管理页面 | 仅管理员可写（`canWrite = role === "admin"`） |

> 所有新增/编辑/删除按钮的可见性由 `GET /auth/me` 返回的 `project_permissions` 中 `actions` 是否含 `"write"` 控制。按钮层面的细粒度 action（如 "confirm_patch"）尚未实现。

---

## 13. 验收规则

### 13.1 已实现

- [ ] 系统存在 admin / tester / guest 三类角色，`users.role` CHECK 约束强制执行
- [ ] `users.status` 支持 `enabled` / `disabled`，禁用账号不能登录（`_current_user_for_token` 拦截）
- [ ] 账号只能由管理员创建，系统不提供公开注册
- [ ] 登录成功写入 `sessions` 表，token 有效期 7 天；登出删除会话
- [ ] 登录失败/成功/登出均写入 `operation_logs`（log_type="audit"）
- [ ] `POST /users`、`PATCH /users/{user_id}`、`DELETE /users/{user_id}` 均通过 `require_admin` 校验
- [ ] `GET /auth/me` 返回 `project_permissions` 字段，格式为 `{project_scope文本: ["read"] 或 ["read","write"]}`
- [ ] 管理员调用 `list_projects` 看到全部非归档项目；tester/guest 按 `project_scope` 精确匹配
- [ ] `__all_projects__` 保留项目在 `list_projects` 最终结果中被过滤，admin 也看不到
- [ ] 侧边栏通过 `requiredRole` + `hasRequiredRole` 过滤 admin 专属菜单项（tester+可见 admin 项目，guest 不可见）
- [ ] 前端根据 `project_permissions` 中 actions 是否含 `"write"` 控制按钮显隐
- [ ] `project_service.update_project` / `delete_project` 对保留项目抛出 `PROJECT_SYSTEM_RESERVED`
- [ ] `user_service.delete_user` 禁止删除当前登录账号（`SELF_DELETE_DENIED`）
- [ ] 用户创建/更新/删除均写入 `operation_logs`（含 before/after 快照）

### 13.2 尚未实现（缺口）

- [ ] `GET /users` 尚未限制为管理员（当前只要求 `current_user` 登录态）
- [ ] 无独立 `GET /users/{user_id}` 详情接口
- [ ] `project_scope` 为文本字段，不支持一个用户分配到多个项目（无 `user_project_members` 关系表）
- [ ] `project_scope` 值关联 `projects.name` 而非 `projects.id`，项目重命名后需同步
- [ ] 禁用用户后其已有 token 不会主动失效（依赖下次请求时拦截，无主动下线）
- [ ] sessions 表无独立过期清理后台任务（依赖惰性检查）
- [ ] 后端尚未返回细粒度按钮级 `available_actions`（如 confirm_patch、regenerate 等独立 action）
- [ ] 用户无自服务个人资料/密码修改页面
- [ ] 超级管理员强制下线（禁用用户时清理其全部会话 token）

---

*文档版本：2026-07-26 基于源码更新。旧版本见 Git 历史。*
