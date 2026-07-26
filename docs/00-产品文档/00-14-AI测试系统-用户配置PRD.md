# 00-14 AI测试系统 - 用户配置 PRD

> **事实源日期**：2026-07-26
>
> **事实源**：
> - 前端：`apps/frontend/src/app/(main)/settings/users/page.tsx`
> - 后端 API：`apps/backend/app/api/v1/users.py`、`apps/backend/app/api/v1/auth.py`
> - 后端服务：`apps/backend/app/services/user_service.py`、`apps/backend/app/services/auth_service.py`
> - 鉴权依赖：`apps/backend/app/dependencies/auth.py`
> - 数据库 Schema：`apps/backend/app/seed/schema.py`（`users` / `sessions` 表）
>
> **状态标签**：`已实现`

---

## 1. 范围与目标

### 1.1 目标

用户配置模块负责 AI 测试系统的账号管理、身份认证与会话管理。包括：

- 管理员对用户账号的增删改查（CRUD）
- 用户登录、登出与会话管理
- 登录失败与账号禁用的审计追踪

### 1.2 当前实现边界

本模块**当前已实现**以下能力：

- 管理员在 `/settings/users` 管理所有用户（创建、编辑、删除、启用、禁用、分配角色和项目范围）
- 所有用户通过 `/auth/v1/login` 登录
- 登录后通过 `/auth/v1/me` 获取当前用户信息与权限
- 通过 `/auth/v1/logout` 登出
- 登录 / 登出 / 用户变更全程记录审计日志

本模块**当前未实现**（占位）：

- 个人资料页（`/settings/profile`）：用户查看 / 修改昵称、邮箱、手机号、头像等个人信息
- 密码自助修改：用户修改自己的登录密码
- 偏好设置：默认项目、默认首页、表格分页大小、通知范围等个人偏好
- 公开注册：`/auth/v1/register` 路由存在但仅显示"管理员创建账号"提示，不开放自助注册

---

## 2. 用户字段

### 2.1 users 表字段

| 字段 | 类型 | 说明 | 约束 |
| --- | --- | --- | --- |
| `id` | TEXT | 主键 | 格式 `u-{8位hex}`，唯一 |
| `username` | TEXT | 登录用户名 | 非空，唯一 |
| `email` | TEXT | 邮箱 | 非空，唯一 |
| `nickname` | TEXT | 昵称（可选） | 可为空 |
| `password_hash` | TEXT | 密码哈希 | 非空，bcrypt/argon2 |
| `role` | TEXT | 角色 | 非空，CHECK IN (`admin`, `tester`, `guest`) |
| `status` | TEXT | 账号状态 | 非空，CHECK IN (`enabled`, `disabled`) |
| `project_scope` | TEXT | 可访问的项目范围 | 非空，默认 `"全部项目"`（也可指定具体项目名） |
| `description` | TEXT | 描述 | 非空，默认空字符串 |
| `created_at` | TEXT | 创建时间 | 非空，默认 CURRENT_TIMESTAMP |
| `updated_at` | TEXT | 更新时间 | 非空，默认 CURRENT_TIMESTAMP |
| `last_login_at` | TEXT | 最近登录时间 | 可为空 |

### 2.2 sessions 表字段

| 字段 | 类型 | 说明 | 约束 |
| --- | --- | --- | --- |
| `token` | TEXT | 会话令牌 | 主键，URL-safe 随机字符串 |
| `user_id` | TEXT | 关联用户 | 非空，外键 → users(id)，ON DELETE CASCADE |
| `created_at` | TEXT | 创建时间 | 非空，默认 CURRENT_TIMESTAMP |
| `expires_at` | TEXT | 过期时间 | 非空，UTC ISO 8601 |

---

## 3. 角色定义

| 角色 | 英文标识 | 说明 |
| --- | --- | --- |
| 管理员 | `admin` | 全局读写，可管理所有用户 |
| 测试工程师 | `tester` | 在 `project_scope` 授权范围内读写 |
| 访客 | `guest` | 全局只读 |

**权限规则**：

- `admin`：全局读写，管理用户、分配角色和项目范围
- `tester`：在 `project_scope` 范围内读写（read/write）
- `guest`：全局只读（read only）

> 注：当前 `project_scope` 为自由文本字段，默认 `"全部项目"`；也可指定具体项目名称。

---

## 4. 登录与认证

### 4.1 认证方式

- 协议：JWT Bearer Token（`Authorization: Bearer <token>`）
- 登录凭证：用户名或邮箱 + 密码
- 会话有效期：7 天（`secrets.token_urlsafe(32)` + `expires_at`）
- 禁用账号登录：返回 401，拒绝访问

### 4.2 登录流程

```
POST /auth/v1/login
Body: { "username": "string", "password": "string" }

成功 → 200
{
  "access_token": "token-string",
  "current_user": { id, username, email, nickname, role, status, project_scope, ... }
}

失败 → 401 { code: "LOGIN_FAILED", message: "账号或密码不正确，请联系管理员确认账号状态。" }
```

### 4.3 获取当前用户

```
GET /auth/v1/me
Header: Authorization: Bearer <token>

成功 → 200
{
  "user": { ... },
  "roles": ["admin"],
  "project_permissions": { "全部项目": ["read", "write"] }
}

未登录 → 401 { code: "AUTH_REQUIRED", message: "请先登录。" }
```

### 4.4 登出

```
POST /auth/v1/logout
Header: Authorization: Bearer <token>

成功 → 200 { "success": true }
```

---

## 5. 注册流程

### 5.1 当前状态：禁止公开注册

- 路由 `/auth/v1/register` 存在，但仅显示提示页面：
  - 标题："账号申请"
  - 提示："AI 测试系统第一版由管理员创建账号，不开放公开注册。"
  - 底部引导："请联系管理员创建账号"
- 后端无对应 POST 处理器

### 5.2 账号创建方式

由管理员在 `/settings/users` 页面手动创建：

- 创建时填写：用户名、邮箱、描述、密码、角色、项目范围、状态
- 用户名创建后不可修改
- 编辑时可选择是否修改密码（留空则保持原密码）

---

## 6. 个人资料 / 偏好

### 6.1 当前状态：未实现

以下功能均为**待实现**占位，不影响当前系统运行：

| 待实现功能 | 说明 |
| --- | --- |
| 查看个人资料 | 昵称、邮箱、手机号、头像、角色、状态、最近登录时间 |
| 修改个人资料 | 修改昵称、邮箱、手机号、头像 |
| 修改密码 | 校验旧密码后设置新密码 |
| 偏好设置 | 默认项目、默认首页、表格分页大小、任务提醒范围、报告打开方式 |

---

## 7. 失败审计 / 启用控制

### 7.1 登录失败审计

登录失败时记录 `operation_logs`：

- 场景 1：用户名不存在或密码错误
  - `actor_id = "anonymous"`
  - `failure_reason = "账号或密码不正确，或账号已禁用。"`
- 场景 2：账号已禁用（`status = disabled`）
  - `actor_id = user["id"]`
  - `failure_reason = "账号已禁用。"`

### 7.2 账号禁用控制

- 管理员可将任意账号状态设为 `disabled`
- 禁用账号再次登录时：
  - 前端提示："账号或密码不正确，请联系管理员确认账号状态。"
  - 后端返回 401，日志记录失败原因
- 被禁用的 `tester` / `guest` 账号无法访问任何受保护 API

### 7.3 密码重置

当前无自助密码重置功能。密码重置由管理员操作：在 `/settings/users` 编辑用户时填写新密码字段。

---

## 8. 数据模型

### 8.1 users 表

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

### 8.2 sessions 表

```sql
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

---

## 9. API 路由清单

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/auth/v1/login` | 公开 | 用户登录 |
| `POST` | `/auth/v1/logout` | Bearer Token | 用户登出 |
| `GET` | `/auth/v1/me` | Bearer Token | 获取当前用户信息与权限 |
| `GET` | `/users` | Bearer Token | 列出所有用户 |
| `POST` | `/users` | `require_admin` | 创建用户 |
| `PATCH` | `/users/{user_id}` | `require_admin` | 更新用户信息 |
| `DELETE` | `/users/{user_id}` | `require_admin` | 删除用户 |

> 注：`require_admin` 依赖项会校验当前用户 `role == "admin"`，否则返回 403。

---

## 10. 前端页面清单

| 路径 | 说明 | 权限 |
| --- | --- | --- |
| `/auth/v1/login` | 登录页 | 公开 |
| `/auth/v1/register` | 注册页（当前仅提示） | 公开 |
| `/settings/users` | 用户与权限管理（列表 + 新增 + 编辑 + 删除） | 仅 `admin` |

---

## 11. 验收规则

### 11.1 已实现验收规则

- [x] 管理员可在 `/settings/users` 查看所有用户列表（用户名、角色、项目范围、状态、最近登录时间）
- [x] 管理员可新增用户（用户名唯一，邮箱唯一，必填密码）
- [x] 管理员可编辑用户（修改邮箱、描述、密码、角色、项目范围、状态；用户名不可修改）
- [x] 管理员可删除用户（删除后 sessions 级联清除；禁止删除自己）
- [x] 管理员可批量删除用户
- [x] 非 admin 用户不可访问 `/settings/users` 的写入操作（`canWrite = currentUser?.role === "admin"`）
- [x] 用户可使用用户名或邮箱 + 密码登录 `/auth/v1/login`
- [x] 登录成功后返回 `access_token` 和 `current_user`
- [x] 禁用账号（`status = disabled`）登录时返回 401
- [x] 登录 / 登出 / 用户 CRUD 操作均记录 `operation_logs`
- [x] 所有 `/users` API 均需有效 Bearer Token
- [x] `POST /users`、`PATCH /users/{id}`、`DELETE /users/{id}` 仅限 admin
- [x] `/auth/v1/register` 页面显示"管理员创建账号"提示，无实际注册功能

### 11.2 待实现验收规则（占位）

- [ ] 用户可在个人资料页查看 / 修改昵称、邮箱、手机号、头像
- [ ] 用户可修改自己的登录密码（需校验旧密码）
- [ ] 用户可设置工作偏好（默认项目、默认首页、表格分页大小、通知范围、报告打开方式）
- [ ] 支持 MFA（多因素认证）
- [ ] 支持登录设备管理
- [ ] 支持密码重置邮件
