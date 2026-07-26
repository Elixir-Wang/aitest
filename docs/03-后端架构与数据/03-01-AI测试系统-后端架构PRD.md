# 03-01 AI测试系统 - 后端架构 PRD

> **实现基线**: `apps/backend/pyproject.toml`、`apps/backend/app/`（含 `agents/`、`services/`、`api/`、`repositories/`）
> **事实源更新日期**: 2026-07-26
> **本版本为源码对齐版，删除了旧 PRD 中未实现的 OpenAI Agents SDK、Allure 等口径，并按 2026-07-26 实际实现补齐任务运行架构、SSE/流、启动恢复、清理与日志、API 路由总览、AI 能力枚举、文件系统布局等章节。**

---

## 1. 范围与目标

本文档以 2026-07-26 代码仓库为唯一事实源，描述 AI 测试系统后端架构。后端使用 Python 3.12 + FastAPI 0.124.2 + SQLite + 本地文件系统，支撑：项目管理、需求文档处理、站点探索、知识库对话、测试用例生成（手动/AI）、UI 自动化（pytest + Playwright）、接口自动化（pytest + requests）、性能测试（Locust）、失败自愈诊断、任务中心、操作日志、报告中心、模型配置。

---

## 2. 技术栈

| 技术 | 版本/包 | 用途 |
| --- | --- | --- |
| Python | >= 3.12 | 后端语言（`pyproject.toml`: `requires-python = ">=3.12"`） |
| FastAPI | 0.124.2 | HTTP API 框架 |
| Uvicorn | 0.50.2 | ASGI 服务器 |
| SQLAlchemy | 2.x | 通过 `sqlite3` 原生模块 + 仓库层（`app/repositories/`）访问，SQLAlchemy 2.x 兼容 SQL |
| Pydantic | 2.12.5 | 请求/响应模型、配置校验 |
| LangChain | >= 1.3.13 | Agent 编排基础（`langchain-core`、`langchain-openai`、`langchain-deepseek`） |
| deepagents | >= 0.6.7 | **实际使用的 Agent 框架**（替代 OpenAI Agents SDK） |
| pytest | >= 9.0.1 | 测试与执行框架（UI/API 自动化、性能脚本运行） |
| pytest-playwright | >= 0.7.0 | UI 自动化浏览器驱动 |
| pytest-json-report | >= 1.5.0 | JSON 报告输出 |
| requests | 2.34.2 | 接口自动化 HTTP 客户端 |
| locust | 2.45.0 | 性能测试负载生成（子进程 headless 模式） |
| Loguru | 0.7.3 | 日志（含敏感字段掩码） |
| httpx | 0.28.1 | 异步 HTTP 客户端 |
| python-multipart | 0.0.20 | 文件上传 |
| pymupdf | 1.26.7 | PDF 解析 |
| python-docx | 1.2.0 | Word 文档解析 |
| ddddocr | >= 1.6.1 | 验证码识别 |

**验收规则**: `pyproject.toml` 中未列的依赖（如 Allure CLI、OpenAI Agents SDK）不得在 PRD 中描述为已实现。

---

## 3. 核心模块边界

| 模块 | 源码路径 | 职责 |
| --- | --- | --- |
| auth | `app/api/v1/auth.py` | 登录、会话（SQLite `sessions` 表）、JWT token |
| users | `app/api/v1/users.py`、`app/repositories/` | 用户、角色（admin / tester / guest）、项目分配 |
| projects | `app/api/v1/projects.py` | 项目管理、项目成员 |
| documents | `app/api/v1/documents.py`、`app/services/document/` | 源文档上传、格式转换（PDF/Word → Markdown）、版本管理 |
| requirements | `app/api/v1/requirements/`、`app/agents/requirement_analysis/` | 需求分析、澄清问答、模块评审、候选需求 |
| knowledge | `app/api/v1/knowledge.py`、`app/api/v1/global_knowledge.py`、`app/agents/knowledge/` | llm-wiki 知识库生成与更新、全局知识库、项目知识库对话（含流式问答） |
| test_cases | `app/api/v1/test_cases.py`、`app/agents/test_case_generation/` | 用例生成、用例评审（采纳/拒绝）、覆盖矩阵 |
| manual_test_cases | `app/api/v1/test_cases.py`（manual router） | 手动用例 CRUD |
| exploration | `app/api/v1/page_exploration.py`、`app/services/page_exploration/`（`runner.py`、`event_bus.py`）、`app/agents/page_exploration/` | Playwright 站点探索、页面快照、模块覆盖、冲突项、抗卡死熔断 |
| ui_automation | `app/api/v1/ui_automation.py`、`app/services/ui_automation/`、`app/agents/ui_automation/` | UI 自动化代码生成（pytest + Playwright）、套件管理、执行 |
| api_automation | `app/api/v1/api_automation.py`、`app/services/api_automation/`、`app/agents/api_automation/`、`app/services/api_automation/self_healing.py` | 接口自动化：端点导入、测试用例生成（pytest + requests）、场景编排、自愈修复状态机 |
| performance_testing | `app/api/v1/performance_tests.py`、`app/api/v1/performance_runs.py`（含 SSE）、`app/api/v1/performance_scenarios.py`、`app/services/performance_testing/`（`headless_worker.py`、`run_repo`）、`app/agents/performance_testing/` | 性能测试：Locust 脚本生成、子进程 headless 运行、SSE 状态流、质量门控、智能分析（deepagents） |
| reports | `app/api/v1/reports.py` | 报告中心 API |
| diagnosis | `app/services/api_automation/self_healing.py` | 失败诊断、自愈修复（repair session + attempt 状态机） |
| models | `app/api/v1/models.py` | 模型 Provider、模型分配（capability → model mapping） |
| agents | `app/agents/`、`app/api/v1/agents.py` | Agent Runtime（LangChain / deepagents）、Skill 调用 |
| tasks | `app/api/v1/tasks.py`、`app/services/task_service.py` | 统一任务中心、任务事件 |
| operation_logs | `app/api/v1/operation_logs/`（`query.py` / `retention.py` / `client_errors.py` / `project_query.py`）、`app/services/operation_log_service.py` | 操作审计日志、保留策略、客户端错误上报 |
| settings | `app/core/settings.py` | 文件存储路径、Playwright 配置、性能测试参数 |

---

## 4. 任务运行架构

### 4.1 异步机制

后端使用两种异步机制：

1. **FastAPI `BackgroundTasks`**：适用于短时后台任务（文件转换、日志写入、监控启动），在请求生命周期内完成。
2. **子进程（`subprocess`） + SQLite 任务表**：适用于长时间运行任务：
   - **UI 自动化**：`app/services/ui_automation/service.py` + `runners/playwright/`
   - **性能测试**：`app/services/performance_testing/headless_worker.py`（`python -m locust -f locustfile.py --headless …`）
   - **站点探索**：`app/services/page_exploration/runner.py` 启动 deepagents 后台协程

子进程状态通过 SQLite 任务表持久化（`performance_test_runs`、`ui_automation_execution_runs`、`exploration_runs` 等）。

**关键管理结构**（`headless_worker.py:21-24`）：

```python
_PROCESSES: dict[str, subprocess.Popen] = {}
_STOP_REQUESTED: set[str] = set()
_MONITOR_FINISHED: dict[str, threading.Event] = {}
_PROCESS_LOCK = threading.Lock()
```

**Locust 启动命令**（`headless_worker.py:31-51`）：

```
python -m locust -f locustfile.py --headless --users <N> --spawn-rate <R> --run-time <S>s \
  --csv <prefix> --csv-full-history --html <result.html>
```

**验收规则**：UI 自动化 / 性能测试 / 站点探索三类的长时任务必须在子进程或后台协程中执行，禁止在 HTTP 请求线程中阻塞等待。

### 4.2 SSE / 流

| 流 | 路径 | 事件 | 实现 |
| --- | --- | --- | --- |
| 性能测试运行 | `GET /projects/{project_id}/performance-test-runs/{run_id}/stream` | `status` / `stats` / `summary` / `error` | `app/api/v1/performance_runs.py:245-287` `stream_performance_run`（`text/event-stream`） |
| 站点探索 | `app/services/page_exploration/event_bus.py`（内存 EventBus）+ `runner.py` `publish()` | 实时 exploration 事件 | `_ExplorationProgressGuard` 抗卡死熔断 |
| 知识库流式问答 | `POST /projects/{project_id}/knowledge/query/stream`、`POST /global-knowledge/query/stream` | 流式问答 | `app/api/v1/knowledge.py:55-78`（`StreamingResponse`） |

### 4.3 Runner 技术栈边界

| Runner | 技术栈 | 入口 |
| --- | --- | --- |
| UI 自动化 | `pytest` + `pytest-playwright`（Browser） | `app/services/ui_automation/runner.py`、`runners/playwright/` |
| 接口自动化 | `pytest` + `requests` | `app/services/api_automation/runner.py` |
| 性能测试 | `locust`（子进程 headless） | `app/services/performance_testing/headless_worker.py`、`app/services/performance_testing/locust_runtime.py` |
| 站点探索 | Playwright（Python sync API，deepagents 工具）| `app/services/page_exploration/runner.py`、`app/agents/page_exploration/` |

**验收规则**：UI 自动化不导出 Allure 报告（`pyproject.toml` 无 Allure 依赖），性能测试报告由 Locust HTML 报告承载。

---

## 5. 启动、恢复、清理与日志

### 5.1 启动

`app/main.py` 入口：`uvicorn app.main:app` 启动；`main.py:22` `FastAPI(title="AI Testing System API", version="0.1.0")`。

CORS 默认仅允许本机前端（`http://localhost:3000` / `http://127.0.0.1:3000` / `http://172.16.187.149:3000`），通过环境变量 `CORS_ALLOW_ORIGINS` 追加。

中间件顺序：`ApiUnhandledExceptionMiddleware` → `CORSMiddleware` → `ApiResponseMiddleware`。

### 5.2 启动恢复（`main.py:50-65` `startup()`）

`on_event("startup")` 顺序调用：

| # | 入口 | 含义 |
| --- | --- | --- |
| 1 | `setup_logging()` | 初始化 Loguru |
| 2 | `init_db()` | 执行 `CREATE_SCHEMA_SQL` + `seed_system_defaults` + `seed_admin_user` |
| 3 | `run_repo.recover_stale_runs(db)` | 恢复卡死的性能测试运行 |
| 4 | `page_exploration_service.recover_interrupted_exploration_runs()` | 恢复中断的探索任务 |
| 5 | `task_service.recover_interrupted_requirement_analysis_runs()` | 恢复需求分析任务 |
| 6 | `test_case_service.recover_interrupted_test_case_generation_runs()` | 恢复用例生成任务 |
| 7 | `test_point_service.recover_interrupted_generation_runs()` | 恢复测试点生成任务 |
| 8 | `api_automation_service.recover_interrupted_api_automation_tasks()` | 恢复接口自动化任务 |
| 9 | `ui_automation_service.recover_interrupted_ui_automation_tasks()` | 恢复 UI 自动化任务 |
| 10 | `ui_automation_service.prepare_background_tasks()` | 准备 UI 自动化后台任务 |
| 11 | `retention_cleanup_service.schedule_cleanup()` | 启动周期清理任务 |

### 5.3 清理（`app/services/retention_cleanup_service.py`）

- **任务名**：`system-log-retention`
- **调度**：`threading.Timer`，启动后 **`DEFAULT_STARTUP_DELAY_SECONDS = 30.0` 秒** 首次执行；之后每 `ELIGIBILITY_CHECK_INTERVAL_SECONDS = 1 小时` 复查一次。清理条件：本地时区（`Asia/Shanghai`）当日尚未成功执行。
- **保留策略**：`MAX_RETENTION_DAYS = 10`（即便策略配置更高也按 10 天封顶）。`retention_days` 最小 1。删除数据库日志与 `LOGS_DIR/{app,error,access,agent}` 四个子目录下的过期文件。
- **批量删除**：`DELETE_BATCH_SIZE = 1000`。
- **重试**：失败可重试 (`MAX_ATTEMPTS = 3`，重试间隔 `RETRY_DELAY_SECONDS = 60.0` 秒)。
- **shutdown**：`shutdown_cleanup()` 取消定时器；`on_event("shutdown")` 同时调用 `event_bus.close_all()`、`ui_automation_service.shutdown_background_tasks()`、兜底 `subprocess.run` 杀掉残留的 `browser-session.mjs` Node 进程。

**不清理**：已发布的知识库、已采纳的用例、已确认的探索结果。

### 5.4 日志（`app/core/logging.py`）

- **库**：Loguru（`loguru==0.7.3`）。
- **位置**：`LOGS_DIR`（`apps/backend/logs/`，可由 `AI_TESTING_LOGS_DIR` 覆盖）。
- **子目录**：`app` / `error` / `access` / `agent`（`LOG_SUBDIRECTORIES`）。
- **敏感字段掩码**（`app/services/operation_log_service.py`）：通过 `SENSITIVE_KEYS` + `SENSITIVE_PATTERN` 对 `password` / `token` / `api_key` / `secret` / `authorization` / `cookie` / `captcha` / `verification_code` / `access_key` 等键名与 `key=value` 模式进行打码（`******`），写入日志前由 `_mask_sensitive()` 统一处理。

---

## 6. API 设计原则（与实现一致）

### 6.1 统一响应格式

成功响应：

```json
{
  "data": { ... },
  "trace_id": "trace_xxx"
}
```

错误响应：

```json
{
  "detail": {
    "code": "AUTH_REQUIRED",
    "message": "请先登录",
    "trace_id": "trace_xxx"
  }
}
```

- **统一中间件**：`ApiResponseMiddleware`（成功响应包装）、`ApiUnhandledExceptionMiddleware`（异常统一包装）。
- **trace_id**：`app/core/logging.py:get_trace_id()` 贯穿日志与响应。

### 6.2 API 路由总览（`app/api/v1/__init__.py` 30 个 `include_router`）

| 路由 | Source File | 备注 |
| --- | --- | --- |
| `/auth/*` | `api/v1/auth.py` | 认证 |
| `/dashboard/*` | `api/v1/dashboard.py` | 控制台 |
| `/reports/*` | `api/v1/reports.py` | 报告中心 |
| `/users/*` | `api/v1/users.py` | 用户管理 |
| `/ai/*` | `api/v1/ai.py` | AI 能力枚举 |
| `/ai/model-assignments/*` | `ai.model_assignment_router` | 模型分配 |
| `/models/*` | `api/v1/models.py` | 模型 Provider |
| `/projects/*` | `api/v1/projects.py` | 项目 |
| `/operation-logs/*` | `api/v1/operation_logs/query.py`（+ `retention.py` + `client_errors.py`） | 系统级日志 |
| `/projects/{project_id}/operation-logs/*` | `api/v1/operation_logs/project_query.py` | 项目级日志 |
| `/environments/*` | `api/v1/environments.py` | 环境配置 |
| `/knowledge/global/*` | `knowledge.global_router` | 全局知识库 |
| `/projects/{project_id}/knowledge/*` | `api/v1/knowledge.py` | 项目知识库（含 `/query/stream`） |
| `/global-knowledge/*` | `api/v1/global_knowledge.py` | 全局知识库（含 `/query/stream`） |
| `/requirements/global/*` | `requirements.global_router` | 全局需求 |
| `/projects/{project_id}/requirements/*` | `api/v1/requirements.py` | 项目需求 |
| `/projects/{project_id}/requirement-files/*` | `api/v1/requirement_files.py` | 需求文件上传 |
| `/projects/{project_id}/test-cases/*` | `api/v1/test_cases.py` | 用例 |
| `/projects/{project_id}/manual-test-cases/*` | `test_cases.manual_router` | 手动用例 |
| `/projects/{project_id}/api-.../*` | `api/v1/api_automation.py` | 接口自动化（端点 / 环境 / 文档 / 用例 / 脚本 / 运行 / 场景 / 修复 / 测试集） |
| `/projects/{project_id}/ui-automation/*` | `api/v1/ui_automation.py` | UI 自动化 |
| `/projects/{project_id}/performance-tests/*` | `api/v1/performance_tests.py` | 性能测试定义 |
| `/projects/{project_id}/performance-tests/{test_id}/runs/*` | `performance_runs.test_router` | 性能测试运行 |
| `/projects/{project_id}/performance-test-runs/*` | `performance_runs.run_router` | 性能测试运行（含 `/{run_id}/stream` SSE、`/{run_id}/ai-analysis/*` 智能分析） |
| `/projects/{project_id}/performance-test-runs/{run_id}/analysis/*` | `performance_runs.analysis_router` | 智能分析 |
| `/projects/{project_id}/performance-scenarios/*` | `api/v1/performance_scenarios.py` | 性能场景 |
| `/projects/{project_id}/performance-scenarios/{id}/runs/*` | `performance_scenarios.run_router` | 性能场景运行 |
| `/tasks/*` | `api/v1/tasks.py` | 任务中心 |
| `/projects/{project_id}/documents/*` | `api/v1/documents.py` | 文档管理 |
| `/agents/*` | `api/v1/agents.py` | Agent 运行时 |
| `/projects/{project_id}/page-exploration/*`（`/exploration/*`） | `api/v1/page_exploration.py` | 站点探索（基于 `event_bus` SSE） |

### 6.3 AI 能力枚举（`app/agents/capabilities.py:11-72` 12 项）

| capability_id | 名称 | 描述 |
| --- | --- | --- |
| `document_editor` | 文档修改 | 根据用户指令修改 Markdown 文档，返回修改后的文档、修改摘要和风险提示 |
| `requirement_standardization` | 需求标准化 | 将上传的 PDF / Word / TXT / Markdown 需求文件标准化为结构稳定的标准 Markdown |
| `requirement_analysis` | 需求分析 | 基于主需求 Markdown 工作稿生成模块分析、澄清问题、可测试性检查和质量门禁结果 |
| `knowledge_query` | 项目知识库查询 | 基于最终需求文档执行 agentic 检索，返回带来源引用的项目知识库答案 |
| `test_case_generation` | 测试用例生成 | 根据最终需求文档生成完整、系统、可执行的测试用例集 |
| `test_point_generation` | 测试点生成 | 根据指定最终需求版本生成结构化、可追溯、可评审的业务测试点 |
| `api_test_generation` | 接口自动化用例生成 | 根据 OpenAPI 接口定义、接口环境摘要和测试重点生成结构化接口自动化用例 |
| `api_scenario_orchestration` | 接口自动化场景编排 | 根据业务目标和当前项目接口资产生成可审阅的接口自动化场景计划 |
| `ui_test_generation` | UI 自动化代码生成 | 根据已采纳测试用例和站点探索证据生成受控 pytest + Playwright UI 自动化代码 |
| `page_exploration` | 站点探索 | 自动化探索 Web 应用，包括页面分析、元素识别、登录表单分析和验证码识别等多模态任务 |
| `performance_script_generation` | 性能测试脚本计划生成 | 根据脱敏后的单接口配置生成受控 `LocustScriptPlan` |
| `performance_report_analysis` | 性能测试报告分析 | 根据脱敏后的 Locust 统计事实生成性能问题、证据和优化建议 |

### 6.4 available_actions 规范

- 每个详情接口返回 `available_actions`，前端只负责渲染。
- 字段结构：`{ key, label, enabled, disabled_reason, risk_level, confirm_required }`。
- 自愈状态机示意（`app/services/api_automation/self_healing.py`：attempt 状态演变）：`queued → collecting_context → diagnosing → waiting_approval / proposal_ready → candidate_generating → candidate_validating → ready_to_apply → rerunning / completed / failed / superseded / proposal_rejected`；session 终止状态：`active / passed / closed / failed`。

---

## 7. 文件系统布局

```
apps/backend/
├── app/                    # FastAPI、Services、Agents、Repositories
├── data/                   # DATA_DIR（默认，由 AI_TESTING_DATA_DIR 覆盖）
│   ├── ai_testing.db       # SQLite（DB_PATH）
│   └── projects/           # PROJECT_FILE_STORAGE_ROOT
│       └── project-{id}/
│           ├── requirements/        # 需求文档原始文件、Markdown 版本
│           ├── exploration/         # 探索产物（screenshot / trace / snapshot）
│           ├── knowledge/           # llm-wiki 产物
│           ├── ui-automation/       # pytest + Playwright 代码、结果
│           ├── api-automation/      # pytest + requests 脚本、结果、repairs
│           └── performance-testing/
│               └── runs/{perfrun-*}/
│                   ├── locustfile.py
│                   ├── generated_locustfile.py
│                   ├── runtime.json
│                   ├── result.html
│                   ├── result_stats.csv / result_stats_history.csv
│                   ├── result_failures.csv / result_exceptions.csv
│                   └── stdout.log / stderr.log / locust-events.jsonl
└── logs/                   # LOGS_DIR（默认，由 AI_TESTING_LOGS_DIR 覆盖）
    ├── app/                # 应用日志
    ├── error/              # 错误日志
    ├── access/             # 访问日志
    └── agent/              # Agent 日志
```

**SQLite 与文件系统边界**：

- **SQLite 保存**：结构化元数据、状态、索引、外键关系（用户、模型、项目、需求、用例、运行、修复会话、知识库、日志、清理状态等，见 `app/seed/schema.py`）。
- **文件系统保存**：Markdown 正文、自动化脚本、Locust 报告、截图、trace、screenshot、video、运行时变量（`runtime.json`）。

---

## 8. 安全边界

- JWT Bearer Token 认证（`Authorization: Bearer <token>`）。
- 角色：`admin` / `tester` / `guest`。
- 项目隔离：所有项目资源 API 必须带 `project_id` 并校验用户项目分配；`guest` 默认可访问全部项目，`tester` 仅可访问其 `project_scope` 命名的项目。
- 密码加密存储：`app/core/security.py` 中 `hash_secret()`（bcrypt / scrypt 兼容）。
- 敏感配置（API Key）加密存储：`app/core/environment_credentials.py`。
- 操作日志敏感字段掩码：`app/services/operation_log_service.py:_mask_sensitive()`。

---

## 9. 验收 / 核对规则

| 规则 | 依据路径 |
| --- | --- |
| 技术栈与 `pyproject.toml` 一致 | `apps/backend/pyproject.toml` |
| Agent 框架为 LangChain / deepagents（非 OpenAI Agents SDK） | `pyproject.toml`、`app/agents/` |
| 12 个 AI capability_id 与 `agents/capabilities.py` 一致 | `app/agents/capabilities.py` |
| Locust 用于性能测试，子进程 headless 运行 | `app/services/performance_testing/headless_worker.py:31-51` |
| `_PROCESSES` 子进程池结构 | `app/services/performance_testing/headless_worker.py:21-24` |
| 性能测试 SSE 流路径 | `app/api/v1/performance_runs.py:245-287` |
| 站点探索抗卡死熔断 | `app/services/page_exploration/runner.py:45-150` |
| 站点探索事件总线 | `app/services/page_exploration/event_bus.py` |
| 启动恢复链路（7 个 `recover_interrupted_*` + `prepare_background_tasks`） | `app/main.py:50-65` |
| 周期清理策略（10 天 / 1 小时 / Asia/Shanghai / 4 个日志子目录） | `app/services/retention_cleanup_service.py` |
| 启动恢复 + 清理调度 + 兜底杀 Node 进程 | `app/main.py:50-92` |
| 30 个 `include_router` 注册 | `app/api/v1/__init__.py` |
| 4 个操作日志子路由（query / retention / client_errors / project_query） | `app/api/v1/operation_logs/*.py` |
| 敏感字段掩码 | `app/services/operation_log_service.py` |
| API 统一响应 / 错误格式 | `app/core/response.py`、`app/api/v1/__init__.py` |
| 文件系统布局与 `app/core/settings.py` 路径一致 | `app/core/settings.py` |
| 数据库初始化走 `seed_system_defaults` + 数据迁移 | `app/seed/init_db.py`、`app/seed/seeds.py:1-30`、`app/seed/schema.py` |
| 启动初始化建表 SQL 完整 | `app/seed/schema.py:1-1432` |
