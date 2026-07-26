# 00-15 AI测试系统 - 系统设置 PRD

> **基线日期**：2026-07-26
>
> **事实源**：
>
> - 前端占位页：`apps/frontend/src/app/(main)/settings/system/page.tsx`
> - 侧边栏配置：`apps/frontend/src/navigation/sidebar/sidebar-items.ts`
> - 后端环境变量：`apps/backend/app/core/settings.py`
> - 后端日志配置：`apps/backend/app/core/logging.py`
> - 操作日志保留策略种子：`apps/backend/app/seed/seeds.py`
>
> **状态标签**：`部分实现`

---

## 1. 范围与目标

系统设置模块负责 AI 测试系统全局基础设施的配置与管理，包括：

- **Web UI 设置**：用户通过浏览器访问 `/settings/system` 页面配置系统参数（当前为占位，待实现）。
- **环境变量配置**：全局基础设置通过后端环境变量（`.env`）管理，不经过 Web UI。
- **已完成的分散设置**：部分系统级功能已通过独立设置页面实现（模型配置、用户与权限、系统日志）。

---

## 2. 当前实现边界

### 2.1 `/settings/system` — 占位页

| 项目 | 内容 |
| --- | --- |
| **URL** | `/settings/system` |
| **页面内容** | `SoonPage` 组件，显示"系统设置暂不开放" |
| **源码路径** | `apps/frontend/src/app/(main)/settings/system/page.tsx` |
| **侧边栏** | **不展示** `/settings/system` 入口（未注册到 `sidebar-items.ts`），但可通过 URL 直接访问 |
| **说明** | 占位页，待后续接入真实存储、Runner、Allure 和安全策略后实现具体配置功能 |

### 2.2 全局配置 — 环境变量

系统全局基础配置**不通过 Web UI**，统一由后端 `apps/backend/app/core/settings.py` 通过环境变量管理。开发者需在部署环境配置 `.env` 文件。

### 2.3 已完成的分散设置

以下功能已通过独立设置页面实现，属于系统设置的一部分：

| 页面 | URL | 功能 |
| --- | --- | --- |
| 模型配置 | `/settings/models` | 模型 Provider CRUD、API Key 显示/隐藏、健康状态、连通性测试 |
| 模型分配 | `/settings/models/assignments` | 按 `capability_id` 映射模型能力分配 |
| 用户与权限 | `/settings/users` | 账号 CRUD、admin/tester/guest 角色、`project_scope` 范围管理 |
| 系统日志 | `/settings/logs` | 操作日志查询（按模块、actor、结果过滤）、保留策略管理 |

---

## 3. 已有设置能力清单

### 3.1 `/settings/models` — 模型配置

| 功能 | 说明 |
| --- | --- |
| Provider 列表 | 展示所有已注册模型提供商 |
| 新增模型 | 表单填写 provider、model、base_url、description、api_key |
| 编辑模型 | 修改已有模型配置 |
| 删除模型 | 批量删除 |
| API Key 显示/隐藏 | 前端 `Input type="password"` + Eye/EyeOff 切换 |
| 健康状态 | `healthy` / `unhealthy` / `testing` / `unknown` 四态，显示为 StatusBadge |
| 连通性测试 | POST `/models/providers/{id}/test`，实时显示测试中状态 |

### 3.2 `/settings/models/assignments` — 模型分配

| 功能 | 说明 |
| --- | --- |
| 能力列表 | 按 `capability_id` 展示系统定义的所有能力节点 |
| 模型映射 | 每个能力可分配一个模型 Provider，支持按 capability 路由调用 |

### 3.3 `/settings/users` — 用户与权限

| 功能 | 说明 |
| --- | --- |
| 用户列表 | 展示所有账号（username、role、project_scope、status、last_login_at） |
| 新增用户 | 表单填写 username（非中文）、email、description、password、role、project_scope、status |
| 编辑用户 | 修改除 username 以外的字段；密码留空则不修改 |
| 删除用户 | 批量删除 |
| 密码显示/隐藏 | 前端 Eye/EyeOff 切换加密显示 |
| 角色 | admin（管理员）/ tester（测试工程师）/ guest（访客） |
| 项目范围 | `project_scope` 支持"全部项目"或指定项目名称 |
| 状态 | 启用 / 禁用 |

### 3.4 `/settings/logs` — 系统日志

| 功能 | 说明 |
| --- | --- |
| 日志列表 | 展示所有 operation_log 记录 |
| 过滤条件 | 支持按 module（模块）、actor（操作人）、result（结果）过滤 |
| 项目筛选 | `showProjectFilter` 支持按 project_id 过滤（系统级日志不受限） |
| 保留策略 | `operation_log_retention_policy` 表管理，默认硬上限 **10 天 / 100k 行** |
| 保留策略更新 | 可通过 API 调整 retention_days 和 max_rows |
| 清理执行 | 支持 dry_run 和实际清理，变更记入 operation_log |

---

## 4. 未来规划 — 系统设置 Web UI 化

以下配置项计划通过 `/settings/system` Web UI 提供，当前均通过环境变量管理：

### 4.1 文件存储

| 配置项 | 说明 | 当前环境变量 |
| --- | --- | --- |
| 文件根目录 | 上传文件、转换产物、知识库、自动化代码、报告的根路径 | `AI_TESTING_PROJECT_FILE_STORAGE_DIR` |
| 上传文件目录 | 原始需求文档、附件 | 含于上述根目录 |
| Markdown 目录 | 转换后的需求文档和探索文档 | 含于上述根目录 |
| 知识库目录 | llm-wiki 产物 | 含于上述根目录 |
| 自动化代码目录 | pytest + Playwright 代码 | 含于上述根目录 |
| 报告目录 | Allure results 和 Allure report | 含于上述根目录 |

### 4.2 SQLite 数据库

| 配置项 | 说明 | 当前环境变量 |
| --- | --- | --- |
| 数据库路径 | SQLite 文件路径 | `AI_TESTING_DB_PATH` |
| 数据目录 | 所有持久化数据的根目录 | `AI_TESTING_DATA_DIR` |
| 备份目录 | 手动或定期备份位置 | 暂未暴露（需新增） |
| WAL 模式 | SQLite 默认开启 WAL | 由 SQLite 引擎控制 |

### 4.3 日志

| 配置项 | 说明 | 当前环境变量 |
| --- | --- | --- |
| 日志根目录 | 所有日志文件根路径 | `AI_TESTING_LOGS_DIR` |
| 日志级别 | app/error/access/agent 各频道级别 | 通过 `setup_logging(level)` 调用控制 |
| 轮转策略 | 每天 00:00 轮转，保留 10 天，zip 压缩，异步写入 | 代码硬编码在 `core/logging.py` |
| 操作日志保留 | 硬上限 10 天 / 100k 行 | `operation_log_retention_policy` 表 |

### 4.4 本地 Runner

| 配置项 | 说明 | 当前环境变量 |
| --- | --- | --- |
| Playwright Runner 目录 | 自动化执行工作区 | `AI_TESTING_PLAYWRIGHT_RUNNER_DIR` |
| Playwright CLI 命令 | 本地 playwright 可执行文件名 | `AI_TESTING_PLAYWRIGHT_CLI_COMMAND` |
| Playwright CLI 打开超时 | 浏览器打开最大等待时间（秒） | `AI_TESTING_PLAYWRIGHT_CLI_OPEN_TIMEOUT_SECONDS` |
| Playwright Goto 超时 | 页面导航超时（秒） | `AI_TESTING_PLAYWRIGHT_CLI_GOTO_TIMEOUT_SECONDS` |
| Playwright 快照超时 | 页面快照等待超时（秒） | `AI_TESTING_PLAYWRIGHT_CLI_SNAPSHOT_TIMEOUT_SECONDS` |
| Playwright Click 超时 | 点击操作超时（秒） | `AI_TESTING_PLAYWRIGHT_CLI_CLICK_TIMEOUT_SECONDS` |
| Playwright Fill 超时 | 表单填充超时（秒） | `AI_TESTING_PLAYWRIGHT_CLI_FILL_TIMEOUT_SECONDS` |
| Playwright 浏览器通道 | 浏览器类型 | `AI_TESTING_PLAYWRIGHT_BROWSER_CHANNEL` |

### 4.5 验证码识别

| 配置项 | 说明 | 当前环境变量 |
| --- | --- | --- |
| 验证码识别配置 | Captcha solver 配置 | 暂未暴露（需新增） |

### 4.6 Agent 安全策略

| 配置项 | 说明 | 当前环境变量 |
| --- | --- | --- |
| 目录访问控制 | Agent 允许读/写目录隔离 | 暂未 Web UI 化 |
| 高风险动作确认 | 自愈补丁、删除资产、覆盖知识库等必须人工确认 | 暂未 Web UI 化 |
| 敏感信息脱敏 | 密码、token、验证码日志脱敏 | 暂未 Web UI 化 |

### 4.7 全局提示

| 配置项 | 说明 | 当前环境变量 |
| --- | --- | --- |
| 系统公告 / Banner | 顶部公告或提示文案 | 暂未暴露（需新增） |

### 4.8 需求上传限制

| 配置项 | 默认值 | 说明 | 当前环境变量 |
| --- | --- | --- | --- |
| 最大文件数 | 10 | 一次上传最多文件数 | `AI_TESTING_REQUIREMENT_UPLOAD_MAX_FILES` |
| 单文件大小上限 | 20 MB | 单个文件最大体积 | `AI_TESTING_REQUIREMENT_UPLOAD_MAX_FILE_SIZE_MB` |
| 批量大小上限 | 200 MB | 一次上传批次总体积上限 | `AI_TESTING_REQUIREMENT_UPLOAD_MAX_BATCH_SIZE_MB` |
| 分片大小 | 5 MB | 上传分片大小 | `AI_TESTING_REQUIREMENT_UPLOAD_CHUNK_SIZE_MB` |
| 并发上传数 | 3 | 分片并发上传数 | `AI_TESTING_REQUIREMENT_UPLOAD_CONCURRENCY` |
| 每用户最大活跃会话 | 2 | 同一用户同时进行的最大上传会话数 | `AI_TESTING_REQUIREMENT_UPLOAD_MAX_ACTIVE_SESSIONS_PER_USER` |
| 上传会话 TTL | 24 小时 | 会话超时时间 | `AI_TESTING_REQUIREMENT_UPLOAD_SESSION_TTL_HOURS` |

### 4.9 性能测试限制

| 配置项 | 默认值 | 说明 | 当前环境变量 |
| --- | --- | --- | --- |
| 最大并发用户数 | 1000 | 单次运行最大模拟用户数 | `AI_TESTING_PERFORMANCE_MAX_USERS` |
| 最大 Spawn 速率 | 100 | 用户每秒增长速率 | `AI_TESTING_PERFORMANCE_MAX_SPAWN_RATE` |
| 最大运行时长 | 3600 秒 | 单次运行最大持续时间 | `AI_TESTING_PERFORMANCE_MAX_DURATION_SECONDS` |
| 最大并发运行数 | 2 | 同一项目同时运行的最大任务数 | `AI_TESTING_PERFORMANCE_MAX_CONCURRENT_RUNS` |

---

## 5. 当前已实现在代码侧的环境变量配置

`apps/backend/app/core/settings.py` 中所有通过环境变量配置的关键变量如下：

### 5.1 目录与路径

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AI_TESTING_DATA_DIR` | `BACKEND_ROOT / "data"` | 所有持久化数据的根目录 |
| `AI_TESTING_LOGS_DIR` | `BACKEND_ROOT / "logs"` | 日志文件根目录 |
| `AI_TESTING_DB_PATH` | `DATA_DIR / "ai_testing.db"` | SQLite 数据库文件路径 |
| `AI_TESTING_PROJECT_FILE_STORAGE_DIR` | `DATA_DIR / "projects"` | 项目文件存储根目录 |
| `AI_TESTING_PLAYWRIGHT_RUNNER_DIR` | `BACKEND_ROOT / "runners" / "playwright"` | Playwright 本地 Runner 工作目录 |

### 5.2 Playwright CLI

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AI_TESTING_PLAYWRIGHT_CLI_COMMAND` | `"playwright"` | Playwright CLI 可执行文件名 |
| `AI_TESTING_PLAYWRIGHT_BROWSER_CHANNEL` | `"chrome"` | 浏览器通道（chrome/firefox/webkit） |

### 5.3 Playwright 超时（秒）

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AI_TESTING_PLAYWRIGHT_CLI_OPEN_TIMEOUT_SECONDS` | `30` | 浏览器打开超时 |
| `AI_TESTING_PLAYWRIGHT_CLI_GOTO_TIMEOUT_SECONDS` | `30` | 页面导航超时 |
| `AI_TESTING_PLAYWRIGHT_CLI_SNAPSHOT_TIMEOUT_SECONDS` | `10` | 快照等待超时 |
| `AI_TESTING_PLAYWRIGHT_CLI_CLICK_TIMEOUT_SECONDS` | `5` | 点击操作超时 |
| `AI_TESTING_PLAYWRIGHT_CLI_FILL_TIMEOUT_SECONDS` | `5` | 表单填充超时 |

### 5.4 性能测试上限

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AI_TESTING_PERFORMANCE_MAX_USERS` | `1000` | 最大并发用户数 |
| `AI_TESTING_PERFORMANCE_MAX_SPAWN_RATE` | `100` | 最大 Spawn 速率（用户/秒） |
| `AI_TESTING_PERFORMANCE_MAX_DURATION_SECONDS` | `3600` | 最大运行时长（秒） |
| `AI_TESTING_PERFORMANCE_MAX_CONCURRENT_RUNS` | `2` | 最大并发运行数 |

### 5.5 需求上传

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AI_TESTING_REQUIREMENT_UPLOAD_MAX_FILES` | `10` | 单次上传最大文件数 |
| `AI_TESTING_REQUIREMENT_UPLOAD_MAX_FILE_SIZE_MB` | `20` | 单文件大小上限（MB） |
| `AI_TESTING_REQUIREMENT_UPLOAD_MAX_BATCH_SIZE_MB` | `200` | 批次大小上限（MB） |
| `AI_TESTING_REQUIREMENT_UPLOAD_CHUNK_SIZE_MB` | `5` | 分片大小（MB） |
| `AI_TESTING_REQUIREMENT_UPLOAD_CONCURRENCY` | `3` | 并发上传数 |
| `AI_TESTING_REQUIREMENT_UPLOAD_MAX_ACTIVE_SESSIONS_PER_USER` | `2` | 每用户最大活跃会话 |
| `AI_TESTING_REQUIREMENT_UPLOAD_SESSION_TTL_HOURS` | `24` | 会话 TTL（小时） |

### 5.6 其他

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AI_TESTING_REJECTED_CASE_KNOWLEDGE_BASE_ID` | `""` | 拒绝用例知识库 ID（可选） |

---

## 6. 权限规则

| 操作 | 管理员 | 测试工程师 | 访客 |
| --- | --- | --- | --- |
| 查看模型配置 | 是 | 是（只读） | 是（只读） |
| 管理模型配置 | 是 | 否 | 否 |
| 查看用户列表 | 是 | 是（只读） | 是（只读） |
| 管理用户 | 是 | 否 | 否 |
| 查看系统日志 | 是 | 是（只读） | 是（只读） |
| 管理系统日志保留策略 | 是 | 否 | 否 |
| 访问系统设置页（占位） | 是（URL 直接访问） | 是（URL 直接访问） | 是（URL 直接访问） |
| 修改系统设置 | 否（占位页） | 否 | 否 |

---

## 7. 验收规则

### 7.1 占位页验收

| 检查项 | 核对路径 |
| --- | --- |
| `/settings/system` 页面内容为 SoonPage 占位 | `apps/frontend/src/app/(main)/settings/system/page.tsx` |
| 侧边栏不展示"系统设置"入口 | `apps/frontend/src/navigation/sidebar/sidebar-items.ts` 中 `id: 4` 分组 |

### 7.2 环境变量配置验收

| 检查项 | 核对路径 |
| --- | --- |
| 所有全局配置均通过 `core/settings.py` 环境变量读取 | `apps/backend/app/core/settings.py` |
| 关键目录变量存在默认值 | `DATA_DIR`、`LOGS_DIR`、`DB_PATH`、`PROJECT_FILE_STORAGE_ROOT` |
| Playwright 超时变量存在 | `PLAYWRIGHT_CLI_*_TIMEOUT_SECONDS` 系列变量 |
| 性能测试上限变量存在 | `PERFORMANCE_MAX_*` 系列变量 |
| 需求上传限制变量存在 | `REQUIREMENT_UPLOAD_*` 系列变量 |

### 7.3 已有设置能力验收

| 检查项 | 核对路径 |
| --- | --- |
| `/settings/models` 页面支持 CRUD 和连通性测试 | `apps/frontend/src/app/(main)/settings/models/page.tsx` |
| `/settings/models/assignments` 页面存在 | `apps/frontend/src/app/(main)/settings/models/assignments/page.tsx` |
| `/settings/users` 页面支持账号和权限管理 | `apps/frontend/src/app/(main)/settings/users/page.tsx` |
| `/settings/logs` 页面展示操作日志 | `apps/frontend/src/app/(main)/settings/logs/page.tsx` |
| 操作日志保留策略硬上限 10 天 / 100k 行 | `apps/backend/app/seed/seeds.py` `_seed_operation_log_retention_policy` 函数 |
| 日志轮转保留 10 天、zip 压缩、异步写入 | `apps/backend/app/core/logging.py` `setup_logging` 函数 |
