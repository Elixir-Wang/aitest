# 00-04 AI 测试系统 · 站点探索 PRD

> 范围声明：本文档描述"页面探索（page exploration）"子能力：从浏览器自动化环境出发，对站点结构、表单、操作、定位符进行结构化抽取与产物化。文档不覆盖需求分析、测试用例生成、知识库生成（这些分别在 PRD 00-03 / 00-21 / 00-05 中定义）。

---

## 0. 事实源

- **基线日期**：2026-07-26
- **事实源**：`apps/frontend/src`、`apps/backend/app`、`apps/backend/tests` 当前工作区源码（含未提交代码）
- **Agent 框架**：deepagents（`deepagents.create_deep_agent`），**不是 OpenAI Agents SDK**
- **状态枚举（9 个）**：`pending / queued / running / stopping / cancelled / interrupted / completed / blocked / failed`

---

## 1. 范围与目标

### 1.1 目标

- 让一个站点在"环境就绪 + 登录策略可控"的前提下，被自动化探索为可追溯的结构化产物（页面 YAML、操作步骤、定位符、截图、追踪）
- 让产物可被下游"知识库检索"（PRD 00-05）、"用例生成"（PRD 00-21）使用
- 让"运行中的长任务"可控：可启动、可停止、可恢复、可清理

### 1.2 边界

- 不做测试用例生成、不做需求抽取
- 不替代生产浏览器；所有运行依赖宿主机上的 Playwright CLI 与浏览器进程
- 仅 admin 可创建/修改/删除环境（见 §10）
- 探索 run 不回写源需求文档；两者关系仅通过 `requirement_doc_id` 做上下文输入

---

## 2. 探索模式

### 2.1 goal（目标驱动）

- 以 `goal` 为主线和完成条件，优先执行目标描述的页面流程
- **第一步必须用 `write_todos` 把探索目标拆成 3-7 个可验证子步骤**，每条包含动词开头的动作描述 + 明确的完成判据
- 后续每完成一个子步骤，必须 `write_todos` 标记 `completed`，再开始下一个
- 子步骤全部 `completed` 或被阻塞时立即停止，输出阶段总结
- 不扩展为全量功能盘点；只探索完成目标所必需的页面、弹窗、字段和状态
- 目标完成、被阻塞或达到预算上限后停止并总结，不要继续无关分支

依据：`runner.py:438-449` `write_todos` 拆目标

### 2.2 autonomous（自主模式 + 模块覆盖度评估）

- 以 `scope` 为覆盖边界，自动识别范围内的主要模块、页面、入口和可测元素
- 如果提供了探索目标，它只是补充关注点，不作为单一路径完成条件
- 按模块盘点，不要因为某个具体动作完成就提前停止
- 达到范围覆盖或预算上限后总结
- 完成后触发 `evaluate_autonomous_coverage` 评估模块覆盖度，结果落库 `exploration_module_coverages`
- 若 `coverage_summary["complete"]` 为 false，run 状态标记为 `partial`

依据：`runner.py:577-580` `evaluate_autonomous_coverage`

---

## 3. 环境管理

### 3.1 自动登录（`auto_auth_service.py`）

- 通过账号密码选择器自动完成登录，支持验证码识别
- **验证码识别优先使用 ddddocr**（开源、稳定、无内容限制），失败时抛出错误让上层重试（不回退到 AI 模型）
- 登录态有效期 10 分钟（`AUTO_AUTH_STALE_AFTER_SECONDS = 600`），超时自动失效
- 登录计划保存到 `<env>/login-plan.json`，可复用
- 状态流：`idle → queued → running → succeeded / failed`
- 错误码：`MISSING_CREDENTIALS / CAPTCHA_SOLVE_FAILED / AUTH_STATE_INVALID / AUTO_LOGIN_FAILED`

### 3.2 手动登录（`manual_auth_service.py`）

- 起一个"手动登录会话"，在外部浏览器完成登录后保存登录态
- 通过 Playwright 打开登录窗口，自动填充用户名和密码（若环境已配置凭据）
- 会话状态：`waiting_human / saved / cancelled / ended / auto_saved`
- 支持从已终止的窗口自动检测登录成功（`auto_saved`）

### 3.3 验证码识别（`captcha_solver_service.py`）

- **主方案：ddddocr**（`import ddddocr`）
- 若 ddddocr 不可用，回退到 AI 模型（`build_captcha_solver_model`）
- `solve_letter_captcha(image_path, expected_length)` 返回识别的字母数字字符串
- 长度不匹配时智能截取（识别结果过长则截取前 N 位）

### 3.4 登录表单分析（`login_form_analyzer_service.py`）

- 通过截图 + 元素列表，让 AI 模型识别登录表单关键控件
- 输出字段：`username_element_id / password_element_id / captcha_image_element_id / captcha_input_element_id / agreement_element_id / login_button_element_id`
- 失败时回退到 `heuristic` 策略（基于文本和 className 推断）

---

## 4. 执行机制

### 4.1 入口：`run_exploration_background`

```
POST /api/v1/page-exploration/runs/:runId/start
  → page_exploration_service.start_exploration_async()
    → threading.Thread(target=_run_exploration_background, daemon=True).start()
      → _exploration_run_repo().update_status(..., "running")
      → _execute_exploration(run_id, run_dict)
        → asyncio.run(_execute_exploration_async(...))
          → page_exploration_agent() 创建 agent
          → await agent.astream(payload, config)
```

依据：`runner.py:235-358`

### 4.2 事件总线（`event_bus.py`）

- **内存 EventBus**，按 `run_id` 维护订阅者队列
- `_MAX_HISTORY = 200`：每个 run 最多保留 200 条历史事件
- 订阅者队列大小：`maxsize=200`（`subscribe` 时初始化 `asyncio.Queue(maxsize=200)`）
- SSE 推送：每个事件通过 `queue.put_nowait(event)` 推送给前端

---

## 5. Agent 框架

### 5.1 deepagents（**不是 OpenAI Agents SDK**）

```python
# agent.py:19-22
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import ToolCallLimitMiddleware

agent = create_deep_agent(
    model=model,
    tools=all_tools,
    system_prompt=SYSTEM_PROMPT if exploration_mode == "goal" else AUTONOMOUS_SYSTEM_PROMPT,
    backend=backend,
    skills=skills,
    middleware=middleware,
)
```

### 5.2 Backend：FilesystemBackend

- `virtual_mode=True`：虚拟文件系统模式
- 用于加载 Skills 和汇总中间件的历史存储

### 5.3 Middleware

```python
# agent.py:82-88
middleware = [
    InvalidToolCallRecoveryMiddleware(max_retries=2),  # 无效工具调用恢复
    ToolCallLimitMiddleware(
        thread_limit=max_actions,
        run_limit=max_actions,
    ),  # 硬截断：单次 run 内最多 max_actions 次工具调用
]
```

### 5.4 Skills

- `goal` 模式：`page-explorer`
- `autonomous` 模式：`autonomous-explorer`
- 两者共用：`locator-best-practices`

---

## 6. 抗卡死熔断

### 6.1 `_ExplorationProgressGuard`（`runner.py:45-150`）

监控 Agent 循环是否陷入重复状态，三层熔断：

| 熔断条件 | 阈值 | 抛出异常 |
| --- | --- | --- |
| 连续快照未变化（同一 URL + 同一 state_signature + 同一 todo） | `stale_snapshot_limit=6` | `ExplorationStalledError` |
| 同一状态连续工具失败 | `failure_limit=3` | `ExplorationStalledError` |
| 同一状态连续无进展动作 | `no_progress_limit=8` | `ExplorationStalledError` |

### 6.2 异常处理

- `ExplorationStalledError` → 状态 `blocked`，推送 `run_failed` 事件
- `ExplorationCancelledError` → 状态 `cancelled`，推送 `run_cancelled` 事件
- 其他 Exception → 状态 `blocked`，推送 `run_failed` 事件

---

## 7. 页面 ID 与元素 Key

### 7.1 页面 ID：`make_page_id`（`utils/page_id.py`）

规则：
- 去除首尾斜杠，空路径 → `home`
- `? & = # % :` → `-`
- `/` → `-`
- 合并连续 `-`
- 过滤空段
- 前缀 `page-`

例：`/workspace/botSetting` → `page-workspace-botSetting`

### 7.2 元素 Key：`build_element_key`（`utils/element_key.py`）

生成顺序：`role+name > role+aria_label > role+label > role+placeholder > role+test_id > role+text`

slugify 规则：
- 小写 + 非 ASCII 字母数字 → `-`
- 折叠连续 `-`
- 截断至 40 字符

---

## 8. 探索产物

### 8.1 产物目录

```
<project>/page_exploration/runs/<run_id>/
  timeline_events.jsonl    # 时间线事件（可读事件流）
  raw_events.jsonl        # 原始事件（agent projection 原始输出）
  pages/                  # 页面快照
  snapshots/              # YAML 快照
  traces/                # Playwright trace
  screenshots/           # 截图
```

### 8.2 产物类型

| 类型 | 表 | 说明 |
| --- | --- | --- |
| `page_yaml` | `exploration_artifacts` | 每个页面的结构化 YAML |
| `operation` | `exploration_artifacts` | 关键操作记录，可单独回放 |
| `screenshot` | `exploration_artifacts` | 探索过程截图 |
| `trace` | `exploration_artifacts` | Playwright trace 文件 |
| `accessibility` | `exploration_artifacts` | 无障碍树快照 |
| `report` | `exploration_artifacts` | Markdown 探索报告 |

---

## 9. 重放（Replay）

### 9.1 永久定位器 + ReplayOperation

- 项目级 UI 操作存储在 `<project>/page_exploration/operations.yaml`
- `ReplayOperation` 包含步骤序列（`navigate / click / fill / press / wait / go_back`）
- 每步引用元素 Key（`element_key`），而非硬编码选择器
- 支持参数化（`parameters`）和断言（`expected`）

### 9.2 执行

```python
# replay/service.py:33-102
ReplayService().execute(
    project_id=...,
    environment_id=...,
    operation_key=...,
    parameters=...,
)
```

- 从 `operations.yaml` 加载操作定义
- 从 `<project>/page_exploration/pages/*.yaml` 加载项目级永久定位器
- 按序执行步骤，遇错重试下一个定位器（若当前失败）
- 支持断言验证（URL / title / overlay / element_value）

### 9.3 产物合并（目标探索）

- `goal` 模式完成后，触发 `merge_goal_run_artifacts`
- 若存在合并冲突，在 `result_summary` 中注明

---

## 10. 状态机（9 个状态）

```
pending → queued → running → stopping → cancelled
                    ↓
                 completed / partial / blocked / failed
                    ↓
              interrupted（进程重启恢复）
```

| 状态 | 含义 |
| --- | --- |
| `pending` | 已创建，等待启动 |
| `queued` | 已提交，等待 worker 调度 |
| `running` | 后台线程正在执行 |
| `stopping` | 用户停止后写入的瞬时态 |
| `cancelled` | 用户主动停止（不可恢复） |
| `interrupted` | 进程重启后被恢复流程标记的"中断"态 |
| `completed` | 成功完成（达到目标或上限） |
| `partial` | 部分完成（自主模式覆盖度未达 100%） |
| `blocked` | 探索阻塞（卡死熔断或异常） |
| `failed` | 执行异常 |

---

## 11. SSE 事件流

### 11.1 端点

`GET /api/v1/page-exploration/runs/:runId/stream`

### 11.2 主要事件类型

| 事件类型 | 说明 |
| --- | --- |
| `run_started` | 探索开始 |
| `run_completed` / `run_failed` / `run_cancelled` | 终态事件 |
| `run_snapshot` | 快照（定时推送 + 初始连接） |
| `planning_completed` | 规划完成 |
| `agent_plan_updated` | Agent 待办更新 |
| `step_started / step_completed / step_failed` | 步骤事件 |
| `page_discovered` | 发现新页面 |
| `module_coverage_updated` | 模块覆盖度变化 |
| `blocker_detected` | 阻塞检测 |

### 11.3 前端处理

- 连接时先拉取 `run_snapshot`
- 实时事件通过 `applyStreamEvent` 合并到 `monitor` 状态
- 支持 SSE 断线重连（1.5 秒后自动重连）

---

## 12. 数据模型（6 张表）

### 12.1 `exploration_runs`

```sql
CREATE TABLE exploration_runs (
  id TEXT PRIMARY KEY,  -- 'exp_<urlsafe16>'
  project_id TEXT NOT NULL,
  environment_id TEXT NOT NULL,
  requirement_doc_id TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK(status IN ('pending','queued','running','stopping','cancelled',
                     'interrupted','completed','blocked','failed')),
  exploration_mode TEXT NOT NULL DEFAULT 'goal'
    CHECK(exploration_mode IN ('goal','autonomous')),
  scope TEXT NOT NULL DEFAULT '',
  forbidden_paths TEXT NOT NULL DEFAULT '',
  login_strategy TEXT NOT NULL DEFAULT 'skip_login',
  goal TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  max_pages INTEGER NOT NULL DEFAULT 50,
  max_actions INTEGER NOT NULL DEFAULT 1000,
  timeout_minutes INTEGER NOT NULL DEFAULT 120,
  artifact_root TEXT NOT NULL DEFAULT '',
  result_summary TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TEXT,
  finished_at TEXT,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE RESTRICT
);
```

### 12.2 `exploration_module_coverages`

```sql
CREATE TABLE exploration_module_coverages (
  id TEXT PRIMARY KEY,
  exploration_run_id TEXT NOT NULL,
  module_key TEXT NOT NULL,
  module_name TEXT NOT NULL,
  entry_path TEXT NOT NULL DEFAULT '',
  planned_page_count INTEGER NOT NULL DEFAULT 0,
  explored_page_count INTEGER NOT NULL DEFAULT 0,
  blocked_page_count INTEGER NOT NULL DEFAULT 0,
  action_count INTEGER NOT NULL DEFAULT 0,
  field_count INTEGER NOT NULL DEFAULT 0,
  state_transition_count INTEGER NOT NULL DEFAULT 0,
  completion_status TEXT NOT NULL,
  completion_summary TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE,
  UNIQUE(exploration_run_id, module_key)
);
```

### 12.3 `exploration_pages`

```sql
CREATE TABLE exploration_pages (
  id TEXT PRIMARY KEY,
  exploration_run_id TEXT NOT NULL,
  module_key TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '',
  entry_path TEXT NOT NULL DEFAULT '',
  structure_summary TEXT NOT NULL DEFAULT '',
  screenshot_path TEXT NOT NULL DEFAULT '',
  snapshot_path TEXT NOT NULL DEFAULT '',
  trace_path TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE
);
```

### 12.4 `exploration_blockers`

```sql
CREATE TABLE exploration_blockers (
  id TEXT PRIMARY KEY,
  exploration_run_id TEXT NOT NULL,
  module_key TEXT NOT NULL DEFAULT '',
  page_ref TEXT NOT NULL DEFAULT '',
  reason_type TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL,
  evidence_path TEXT NOT NULL DEFAULT '',
  impact_scope TEXT NOT NULL DEFAULT '',
  suggested_action TEXT NOT NULL DEFAULT '',
  is_blocking INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE
);
```

### 12.5 `exploration_artifacts`

```sql
CREATE TABLE exploration_artifacts (
  id TEXT PRIMARY KEY,
  exploration_run_id TEXT NOT NULL,
  artifact_type TEXT NOT NULL,
  file_path TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE
);
```

### 12.6 `exploration_document_versions`

```sql
CREATE TABLE exploration_document_versions (
  id TEXT PRIMARY KEY,
  exploration_run_id TEXT NOT NULL,
  version_no INTEGER NOT NULL,
  markdown_path TEXT NOT NULL,
  change_summary TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE,
  UNIQUE(exploration_run_id, version_no)
);
```

---

## 13. API 路由清单

### 13.1 runs（`page_exploration/runs.py`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/page-exploration/runs` | 创建探索任务 |
| GET | `/api/v1/page-exploration/runs/:run_id` | 获取任务详情 |
| GET | `/api/v1/page-exploration/runs?project_id=...` | 列出项目任务 |
| PATCH | `/api/v1/page-exploration/runs/:run_id` | 更新任务配置 |
| DELETE | `/api/v1/page-exploration/runs/:run_id` | 删除任务 |
| POST | `/api/v1/page-exploration/runs/:run_id/start` | 启动/重新启动任务 |
| POST | `/api/v1/page-exploration/runs/:run_id/stop` | 停止任务 |
| GET | `/api/v1/page-exploration/runs-all` | 跨项目列出任务 |

### 13.2 pages（`page_exploration/pages.py`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/page-exploration/runs/:run_id/pages` | 列出任务页面 |
| GET | `/api/v1/page-exploration/projects/:project_id/pages` | 列出项目页面 |
| GET | `/api/v1/page-exploration/projects/:project_id/pages/:page_id/yaml` | 获取页面 YAML |

### 13.3 artifacts（`page_exploration/artifacts.py`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/page-exploration/runs/:run_id/artifacts` | 获取探索报告 |
| GET | `/api/v1/page-exploration/artifacts/:artifact_id/content` | 获取产物内容 |
| GET | `/api/v1/page-exploration/artifacts` | 列出产物 |
| DELETE | `/api/v1/page-exploration/projects/:project_id/artifacts` | 清空项目产物 |
| GET | `/api/v1/page-exploration/projects/:project_id/operations` | 列出项目操作 |
| PUT | `/api/v1/page-exploration/projects/:project_id/operations/:operation_key` | 保存操作 |
| POST | `/api/v1/page-exploration/projects/:project_id/replay` | 执行重放 |
| GET | `/api/v1/page-exploration/projects/:project_id/replay-runs/:run_id` | 获取重放状态 |
| POST | `/api/v1/page-exploration/projects/:project_id/replay-runs/:run_id/stop` | 停止重放 |
| POST | `/api/v1/page-exploration/projects/:project_id/replay-runs/:run_id/retry` | 重试重放 |

### 13.4 events（`page_exploration/events.py`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/page-exploration/runs/:run_id/stream` | SSE 实时进度流 |

---

## 14. 前端页面清单

| 页面 | 路由 | 说明 |
| --- | --- | --- |
| 全局探索工作台 | `/exploration` | 展示所有可见项目的探索 run / 环境 / 产物 |
| 全局新建 | `/exploration/new` | 创建新的探索任务 |
| 项目内探索工作台 | `/projects/:projectId/exploration` | 限定项目范围 |
| 项目内新建 | `/projects/:projectId/exploration/new` | 在项目内创建探索任务 |
| 项目内编辑 | `/projects/:projectId/exploration/:runId/edit` | 编辑探索任务配置 |
| 项目内详情 | `/projects/:projectId/exploration/:runId` | 探索任务详情 + SSE 实时进度 + 报告 |

组件：
- `apps/frontend/src/components/ai-testing/exploration-workspace.tsx`
- `apps/frontend/src/components/ai-testing/exploration-run-create-page.tsx`

---

## 15. 验收规则

- **AC-01**：新建环境 → 触发自动登录 → `auth_state_status` 从 `running → succeeded` 或 `failed`
- **AC-02**：手动登录会话可 start → 在外部浏览器完成后调用 save，登录态被持久化
- **AC-03**：创建 run → 启动 → 状态依次出现 `pending / queued / running / completed（或 partial）`
- **AC-04**：探索过程中 SSE 收到 `page_discovered / step_completed / module_coverage_updated` 等事件
- **AC-05**：运行中点击"停止"，run 在数秒内进入 `cancelled`，产物列表保留已发现条目
- **AC-06**：再次"启动"同一个 run，上一轮的 `exploration_pages/artifacts/blockers/module_coverages` 被清空
- **AC-07**：选择某个 operation 发起重放，重放 run 独立状态、可停止/重试
- **AC-08**：服务端重启后，正在运行的 run 变为 `interrupted`，操作日志可见原因
- **AC-09**：删除某项目产物，需先确保无运行中 run，否则接口报错
- **AC-10**：Agent 在同一页面状态连续 8 次无进展动作后抛出 `ExplorationStalledError`，run 标 `blocked`
- **AC-11**：目标探索第一步必须调用 `write_todos` 拆解目标，否则 Agent 行为不符合预期
- **AC-12**：自主探索完成后，模块覆盖度评估结果落库 `exploration_module_coverages`

---

## 16. 与其它 PRD 的边界

- 与 PRD 00-03：探索 run 可读取某个 `requirement_doc_id` 作为上下文，但不会回写需求文档
- 与 PRD 00-05：项目级页面 YAML 是知识检索 `explorations` 来源；本 PRD 不定义检索开关
- 与 PRD 00-22：本 PRD 不涉及全局/公司知识库

---

## 17. 实现依据（精确路径）

- **Agent**：`apps/backend/app/agents/page_exploration/agent.py`（deepagents + FilesystemBackend + ToolCallLimitMiddleware）
- **Utils**：`apps/backend/app/agents/page_exploration/utils/{page_id,element_key}.py`
- **Runner**：`apps/backend/app/services/page_exploration/runner.py`
- **Event Bus**：`apps/backend/app/services/page_exploration/event_bus.py`
- **Replay**：`apps/backend/app/services/page_exploration/replay/{service,store,run_service,models}.py`
- **Auth**：`apps/backend/app/services/{auto_auth,manual_auth,captcha_solver,login_form_analyzer}_service.py`
- **路由**：`apps/backend/app/api/v1/page_exploration/{__init__,runs,pages,artifacts,events}.py`
- **前端**：`apps/frontend/src/app/(main)/exploration/{page,new}/page.tsx`、`apps/frontend/src/app/(main)/projects/[projectId]/exploration/{[runId]/{edit,page}.tsx`、`apps/frontend/src/components/ai-testing/{exploration-workspace,exploration-run-create-page}.tsx`
