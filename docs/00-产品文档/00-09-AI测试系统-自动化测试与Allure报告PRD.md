# 00-09 AI 测试系统 - UI 自动化测试 PRD

> **文件名历史说明**：文件名"自动化测试与 Allure 报告"为历史遗留。**本系统 UI 自动化不接入 Allure**，`pyproject.toml` 无 Allure 依赖；执行报告为 pytest 原生日志、Playwright trace、截图、视频（详见第 7 章）。

---

## 0. 事实源

- **基线日期**：2026-07-26
- **唯一事实源**：工作区源码（含未提交代码）。不再参考旧 PRD 内容或口头描述。

| 事实维度 | 源码路径 |
| --- | --- |
| 前端列表页 | `apps/frontend/src/app/(main)/automation/ui/page.tsx` |
| 前端资产详情页 | `apps/frontend/src/app/(main)/projects/[projectId]/automation/ui/assets/[assetId]/page.tsx` |
| 前端运行详情页 | `apps/frontend/src/app/(main)/projects/[projectId]/automation/ui/assets/[assetId]/runs/[runId]/page.tsx` |
| 前端组件 | `apps/frontend/src/components/ai-testing/ui-automation/ui-automation-asset-detail.tsx`、`ui-automation-run-detail.tsx` |
| 前端 API 客户端 | `apps/frontend/src/lib/api-client.ts:1904–1967`（`UiAutomation*` 函数） |
| 后端 API | `apps/backend/app/api/v1/ui_automation.py` |
| 后端服务 | `apps/backend/app/services/ui_automation/service.py` |
| 后端 Agent | `apps/backend/app/agents/ui_automation/pytest_playwright/agent.py` |
| 数据库 Schema | `apps/backend/app/seed/schema.py:1356–1431` |
| CHECK 约束 | `schema.py:1377`（`test_case_id XOR manual_test_case_id`）及 `schema.py:1401`（同上） |

---

## 1. 范围与目标

### 1.1 范围

本模块定义 **UI 自动化**（pytest + Playwright）的完整生命周期：

- **生成**：基于已采纳测试用例（`test_cases.status='approved'`）或手工用例（`manual_test_cases`），结合项目站点探索证据，生成可执行的 pytest 资产。
- **资产**：pytest 套件目录，包含测试文件、页面对象文件、数据文件、计划文件。
- **执行**：在选定的项目运行环境中执行 pytest，用 Playwright 进行浏览器自动化。
- **监控**：实时浏览器画面（MJPEG live-view）、浏览器录像回放。
- **报告**：pytest 原生日志、Playwright trace、失败截图、录屏视频；**不接入 Allure**。
- **清理**：批量删除已完成运行及其关联的日志、截图、录像、trace。

### 1.2 目标

- 用例（已采纳或手工）→ 一键生成可执行 UI 自动化资产。
- 资产有版本（`source_version`），但同一来源用例重复生成时 upsert，不维护历史版本。
- 失败有证据（截图、trace、录像），无自动修复/自愈子系统。
- 运行可实时监控，执行完成后可回放录像、下载证据。

### 1.3 本模块不负责

- 接口自动化测试（00-16）。
- Allure 报告生成与展示（**未接入**）。
- UI 自动化自愈/自动修复（00-10 范围外）。
- 元素 locator 运行时自学习、外部 patch 应用。
- 跨项目自动化执行、独立 CI/CD 调度。

---

## 2. UI 自动化生成

### 2.1 来源用例约束

每条生成任务必须关联 **且仅关联** 以下来源之一：

| 来源 | 字段 | 准入条件 |
| --- | --- | --- |
| 已采纳测试用例 | `test_case_id` | `test_cases.status = 'approved'` |
| 手工测试用例 | `manual_test_case_id` | 任意（无需评审） |

数据库层通过 `CHECK ((test_case_id IS NOT NULL) != (manual_test_case_id IS NOT NULL))` 强制互斥（`schema.py:1377`）。

### 2.2 生成流程

1. **任务创建**：调用 `POST /projects/{project_id}/ui-automation/generation-runs`，传入 `test_case_id`（统一字段，实际传 `test_case_id` 或 `manual_test_case_id`），返回 `uigen-<hex>` ID，状态为 `queued`。
2. **探索证据解析**：后端 `service.schedule_generation_run` 用后台线程执行 `_execute_generation_run_in_workspace`：
   - 若请求带 `exploration_run_id` 且匹配同项目+环境，则使用指定探索任务；
   - 否则按项目+环境匹配一个具有非空 `evidence["artifacts"]` 的探索任务；
   - 都没有则记录空探索 ID，生成任务直接进入 `waiting_manual`，不创建资产。
3. **文件写入**：写入 `testcases/<project_key>/cases/<id>.yaml`（用例数据），由 AI Agent 生成 `plan.json` + `test_*.py` + 页面对象文件。
4. **资产校验**：用 `collect_suite` 沙盒运行 `pytest --collect`，语法/导入错误会回滚到生成前快照，run 状态写为 `failed`。
5. **资产创建**：校验通过后 `upsert_asset` 写入 `ui_automation_assets`（状态 `ready`）。
6. **错误处理**：任何异常均回滚目标文件，生成 run 状态写 `failed`，`error_message` 记录原因。

### 2.3 重新生成

资产详情页"重新生成"按当前资产的来源用例、最近一次生成环境、最近一次探索 ID 重新发起生成任务。同来源用例的第二次生成会 upsert 现有资产，旧资产被替换。

---

## 3. UI 自动化资产

### 3.1 资产结构

每个资产对应一个项目独立套件目录（`data/projects/<project_id>/ui_automation/<asset_id>/`），包含：

| 文件类型 | 路径（相对套件根） | 说明 |
| --- | --- | --- |
| pytest 测试文件 | `suite/test_<sanitized_id>.py` | 生成的 Playwright 测试用例 |
| 页面对象文件 | `suite/pages/` | 页面对象类（pytest-playwright 规范） |
| 数据文件 | `suite/data/<asset_id>.yaml` | 用例数据 |
| 计划文件 | `suite/plan.json` | 资产元数据、locator 摘要、`pytest_node_id` |

### 3.2 资产字段

| 字段 | 说明 |
| --- | --- |
| `id` | `uiasset-<hex>` |
| `project_id` | 所属项目 |
| `test_case_id` / `manual_test_case_id` | 二选一，与生成 run 一致的 CHECK 约束（`schema.py:1401`） |
| `source_version` | 当前实现固定为 1 |
| `generation_run_id` | 关联的成功生成任务 |
| `status` | `ready`（生成成功） / `creating`（生成中）/ `failed`（生成失败） |
| `pytest_node_id` | 形如 `test_file.py::test_<sanitized_id>`，定位单个用例 |
| `suite_path` / `test_file_path` / `data_file_path` / `plan_file_path` | 相对套件根目录的路径 |
| `source_hash` | 内容 hash（变更检测用） |
| `latest_generation_run` / `latest_execution_run` | 最近一次生成/执行记录（API 附带） |
| `locator_summary` | `{required, available, missing: string[]}`（当前 `available == required`，缺失不可枚举） |

### 3.3 资产列表页

`/automation/ui` 聚合所有项目的资产与进行中的生成任务，支持按测试用例名称、操作用例、文件路径搜索。

---

## 4. UI 自动化执行

### 4.1 执行入口

从资产详情页或执行记录列表点击"执行测试"，选择 `environment_id`，创建 `ui_automation_execution_runs`（状态 `queued`），调度后台执行线程。

### 4.2 执行引擎

`service.execute_execution_run` 启动 pytest 子进程，关键参数：

- `pytest --tracing=retain-on-failure --video=on --output=<run_dir>/browser`
- 环境变量注入：`UI_BASE_URL`、`UI_RESULT_PATH`、`UI_STORAGE_STATE`（当环境启用了 `reuse_auth_state`）
- 敏感信息脱敏：stdout/stderr 中屏蔽 `authorization:bearer` / `token=` / `password=` / `cookie:` 字段

### 4.3 产物收集

执行完成后在 `runs/<run_id>/browser/` 目录收集：

- `trace.zip`：Playwright trace（可通过 trace viewer 回放）
- `*.webm` / `*.mp4`：浏览器录屏视频
- `*.png`：失败截图

子进程 stdout/stderr 写入 `runs/<run_id>/stdout.txt` / `stderr.txt`，解析后生成 `result.json`。

### 4.4 停止执行

监听 `_STOP_REQUESTED` 集合，对 `queued` 状态直接置 `cancelled`，对 `running` 状态先置 `stopping` 再对子进程发 SIGTERM，3 秒未退则 SIGKILL。

### 4.5 超时

执行超时默认 600 秒，超时后写入 `error_message` 并强制终止子进程。

---

## 5. 实时监控（MJPEG Live View）

### 5.1 架构

- `start_session`：临时分配本地端口，启动 CDP Screencast 线程（默认 1440×900）。
- `get_execution_live_view`：返回会话状态枚举：
  - `waiting`：执行尚未开始
  - `starting`：CDP 会话初始化中
  - `ready`：画面可用
  - `unavailable`：CDP 无画面（30 秒无帧或无 Chromium 进程）
  - `ended`：执行已结束

### 5.2 流协议

- `GET /runs/{run_id}/live-view`：返回 `{status, stream_path}`，前端据此渲染"实时画面"按钮。
- `GET /runs/{run_id}/live-view/stream?token=<32位token>`：返回 `multipart/x-mixed-replace;boundary=frame` 的 MJPEG 流，需 token 鉴权。
- CDP 30 秒无帧自动降级为 `unavailable`，执行不中断。

### 5.3 会话清理

`_prune_ended_sessions` 每 5 分钟清理已结束的 live-view 会话。

---

## 6. 报告与证据（无 Allure）

### 6.1 Allure 不接入声明

- `pyproject.toml` **无** `allure-pytest` / `allure-playwright` 依赖。
- UI 自动化**不生成** `allure-results` / `allure-report`。
- 前端**无**跳转 Allure 入口。

### 6.2 证据类型

| 证据类型 | 来源 | 下载路径 |
| --- | --- | --- |
| pytest stdout | `runs/<run_id>/stdout.txt`（脱敏后） | `GET /runs/{run_id}/logs` |
| pytest stderr | `runs/<run_id>/stderr.txt`（脱敏后） | `GET /runs/{run_id}/logs` |
| Playwright trace | `runs/<run_id>/browser/trace.zip` | `GET /runs/{run_id}/artifacts/trace?index=0` |
| 浏览器录屏 | `runs/<run_id>/browser/*.webm` / `*.mp4` | `GET /runs/{run_id}/artifacts/video?index=0` |
| 失败截图 | `runs/<run_id>/browser/*.png` | `GET /runs/{run_id}/artifacts/screenshot?index=<n>` |

### 6.3 浏览器录像回放

- 运行详情页在执行完成后加载录屏视频（`videoUrl`）。
- Playwright trace 可通过 trace viewer 回放交互步骤。

---

## 7. 状态机

### 7.1 生成任务（`ui_automation_generation_runs`）

```
queued → running → completed
                  ↘ failed
                  ↘ waiting_manual  （探索证据为空时）
```

重启恢复：`recover_interrupted_ui_automation_tasks` 将所有 `queued/running` 状态标记为 `failed`。

### 7.2 资产（`ui_automation_assets`）

```
creating → ready
         ↘ failed
```

### 7.3 执行任务（`ui_automation_execution_runs`）

```
queued → running → passed
                  ↘ failed
                  ↘ interrupted（超时）
queued → cancelled（直接 stop）
running → stopping → cancelled（stop + SIGTERM/SIGKILL）
```

重启恢复：执行任务被收敛为 `failed`（`stopping` 则 `cancelled`）。

---

## 8. 批量清理

### 8.1 清理范围

删除执行任务时，联动清理以下文件：

- `runs/<run_id>/`（整个运行目录）
  - `stdout.txt` / `stderr.txt`（日志）
  - `browser/` 子目录（截图、录像、trace）

### 8.2 清理约束

- 仅非活跃状态的运行可删除：`queued` / `running` / `stopping` 状态禁止删除。
- 违反约束返回 `409 UI_EXECUTION_RUN_ACTIVE`。

### 8.3 路径安全

删除前校验 `run_dir` 必须属于当前资产套件目录（`runs_root`），且目录名等于 `run_id`，防止路径穿越。

---

## 9. 数据模型

### 9.1 `ui_automation_generation_runs`

```sql
CREATE TABLE IF NOT EXISTS ui_automation_generation_runs (
  id TEXT PRIMARY KEY,                    -- uigen-<hex>
  project_id TEXT NOT NULL,
  test_case_id TEXT,                      -- 已采纳用例
  manual_test_case_id TEXT,                -- 手工用例
  environment_id TEXT NOT NULL,
  exploration_run_id TEXT NOT NULL DEFAULT '',
  task_id TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'queued',  -- queued/running/completed/failed/waiting_manual
  suite_path TEXT NOT NULL DEFAULT '',
  changed_files_json TEXT NOT NULL DEFAULT '[]',
  error_message TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(test_case_id) REFERENCES test_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(manual_test_case_id) REFERENCES manual_test_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE CASCADE,
  CHECK ((test_case_id IS NOT NULL) != (manual_test_case_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_ui_generation_project_created ON ui_automation_generation_runs(project_id, created_at);
```

### 9.2 `ui_automation_assets`

```sql
CREATE TABLE IF NOT EXISTS ui_automation_assets (
  id TEXT PRIMARY KEY,                    -- uiasset-<hex>
  project_id TEXT NOT NULL,
  test_case_id TEXT,                      -- 已采纳用例
  manual_test_case_id TEXT,               -- 手工用例
  source_version INTEGER NOT NULL DEFAULT 1,
  generation_run_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ready',   -- creating/ready/failed
  pytest_node_id TEXT NOT NULL,           -- <test_file>::test_<sanitized_id>
  suite_path TEXT NOT NULL,
  test_file_path TEXT NOT NULL,
  data_file_path TEXT NOT NULL,
  plan_file_path TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(test_case_id) REFERENCES test_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(manual_test_case_id) REFERENCES manual_test_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(generation_run_id) REFERENCES ui_automation_generation_runs(id) ON DELETE CASCADE,
  CHECK ((test_case_id IS NOT NULL) != (manual_test_case_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_ui_assets_project_updated ON ui_automation_assets(project_id, updated_at);
```

### 9.3 `ui_automation_execution_runs`

```sql
CREATE TABLE IF NOT EXISTS ui_automation_execution_runs (
  id TEXT PRIMARY KEY,                    -- uirun-<hex>
  project_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  environment_id TEXT NOT NULL,
  task_id TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'queued',  -- queued/running/stopping/passed/failed/cancelled/interrupted
  run_dir TEXT NOT NULL DEFAULT '',
  result_json TEXT NOT NULL DEFAULT '{}',
  stdout_path TEXT NOT NULL DEFAULT '',
  stderr_path TEXT NOT NULL DEFAULT '',
  trace_path TEXT NOT NULL DEFAULT '',
  video_path TEXT NOT NULL DEFAULT '',
  screenshot_paths_json TEXT NOT NULL DEFAULT '[]',
  error_message TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(asset_id) REFERENCES ui_automation_assets(id) ON DELETE CASCADE,
  FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ui_execution_project_created ON ui_automation_execution_runs(project_id, created_at);
```

---

## 10. API 路由清单

前缀：`/api/v1/projects/{project_id}/ui-automation`，由 `app/api/v1/ui_automation.py` 暴露。

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/generation-runs` | 新建生成任务 | admin |
| GET | `/generation-runs` | 生成任务列表 | user |
| GET | `/generation-runs/{run_id}` | 生成任务详情 | user |
| GET | `/assets` | 资产列表 | user |
| GET | `/assets/{asset_id}` | 资产详情（含 locator_summary） | user |
| GET | `/assets/{asset_id}/generation-runs` | 资产关联的生成运行 | user |
| GET | `/assets/{asset_id}/runs` | 资产关联的执行运行 | user |
| POST | `/assets/{asset_id}/runs` | 创建执行运行 | admin |
| GET | `/runs/{run_id}` | 执行运行详情 | user |
| POST | `/runs/{run_id}/stop` | 停止执行 | admin |
| DELETE | `/runs/{run_id}` | 删除执行运行（仅非活跃） | admin |
| GET | `/runs/{run_id}/logs` | stdout / stderr（含脱敏） | user |
| GET | `/runs/{run_id}/live-view` | live-view 状态 + stream 路径 | user |
| GET | `/runs/{run_id}/live-view/stream?token=...` | MJPEG 视频流 | token 鉴权 |
| GET | `/runs/{run_id}/artifacts/{trace\|video\|screenshot}?index={n}` | 证据文件下载 | user |

**错误码**：`UI_AUTOMATION_INPUT_REQUIRED`、`UI_TEST_CASE_NOT_FOUND`、`UI_TEST_CASE_NOT_APPROVED`、`UI_ENVIRONMENT_NOT_FOUND`、`UI_EXPLORATION_RUN_NOT_FOUND`、`UI_EXPLORATION_ENVIRONMENT_MISMATCH`、`UI_GENERATION_RUN_NOT_FOUND`、`UI_ASSET_NOT_FOUND`、`UI_EXECUTION_RUN_NOT_FOUND`、`UI_EXECUTION_RUN_ACTIVE`、`UI_EXECUTION_RUN_DIR_INVALID`、`UI_LIVE_VIEW_NOT_FOUND`、`UI_ARTIFACT_KIND_INVALID`、`UI_ARTIFACT_NOT_FOUND`、`PERMISSION_DENIED`。

---

## 11. 前端页面清单

| 页面 | 路由 | 核心组件 |
| --- | --- | --- |
| UI 自动化列表 | `/automation/ui` | `page.tsx`（聚合所有项目资产+生成任务） |
| 资产详情 | `/projects/{projectId}/automation/ui/assets/{assetId}` | `ui-automation-asset-detail.tsx` |
| 运行详情 | `/projects/{projectId}/automation/ui/assets/{assetId}/runs/{runId}` | `ui-automation-run-detail.tsx` |

---

## 12. 验收规则

| # | 规则 | 预期结果 |
| --- | --- | --- |
| 1 | 来源用例既非已采纳也非手工用例 | `404 UI_TEST_CASE_NOT_FOUND` 或 `409 UI_TEST_CASE_NOT_APPROVED` |
| 2 | 运行环境与探索任务不属于当前项目 | `404 UI_ENVIRONMENT_NOT_FOUND` / `404 UI_EXPLORATION_RUN_NOT_FOUND` / `409 UI_EXPLORATION_ENVIRONMENT_MISMATCH` |
| 3 | 无结构化探索证据时生成 | run 状态 `waiting_manual`，不创建资产 |
| 4 | 生成成功后 | 资产状态 `ready`，详情接口返回 `locator_summary` |
| 5 | 活跃状态（`queued/running/stopping`）执行运行无法删除 | `409 UI_EXECUTION_RUN_ACTIVE` |
| 6 | 停止执行后 | `queued` 直接 `cancelled`；`running` → `stopping` → `cancelled` |
| 7 | Live-view token 校验失败或会话已结束 | `404 UI_LIVE_VIEW_NOT_FOUND` |
| 8 | `/runs/{id}/logs` 返回的文本中 | `authorization:bearer` / `token=` / `password=` / `cookie:` 被脱敏 |
| 9 | 服务重启后 | 所有 `queued/running` 生成与执行任务被收敛为 `failed`/`cancelled` |
| 10 | 执行完成后 | 运行详情页展示录屏视频、失败截图列表、trace 下载入口 |
| 11 | 浏览器录像回放 | 运行详情页可播放 `runs/<run_id>/browser/*.webm` 或 `*.mp4` |
| 12 | UI 自动化**不接入 Allure** | `pyproject.toml` 无 allure 依赖，前端无跳转 Allure 入口 |
