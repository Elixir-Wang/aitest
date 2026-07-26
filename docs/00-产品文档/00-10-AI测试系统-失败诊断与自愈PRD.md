# 00-10 AI测试系统 - 失败诊断与自愈 PRD

## 0. 基线与事实源

- 基线日期：2026-07-26
- 事实源：当前工作区源码，以以下文件为准：
  - 后端自愈服务：`apps/backend/app/services/api_automation/self_healing.py`（`ApiSelfHealingService` 类）
  - 后端 API 路由：`apps/backend/app/api/v1/api_automation.py`（修复会话、审批、应用、放弃、驳回、回滚端点）
  - 性能修复服务：`apps/backend/app/services/performance_testing/repair_service.py`（`apply_and_rerun`）
  - 性能分析 API：`apps/backend/app/api/v1/performance_runs.py`（`/ai-analysis` 与 `/apply-and-rerun`）
  - 前端：`apps/frontend/src/components/ai-testing/api-automation/api-run-detail.tsx`、`apps/frontend/src/components/ai-testing/performance-testing/performance-analysis-report.tsx`
  - 数据库：`apps/backend/app/seed/schema.py`（`api_repair_sessions / api_repair_attempts / performance_analysis_sessions`）
- 状态标签：【已实现】

---

## 1. 适用范围与目标

### 1.1 系统边界

| 自动化类型 | 失败诊断 | 自愈/修复复测 | 说明 |
|---|---|---|---|
| 接口自动化 | ✅ | ✅ | 完整修复会话（repair session）+ 多轮 attempt |
| 性能测试 | ✅（智能分析） | ✅（修复复测） | 独立 AI 分析会话 + apply_and_rerun |
| UI 自动化 | ✅（仅展示日志） | ❌ | 无自愈模块，仅展示失败日志/截图/Trace |

**关键说明：**
- 自愈能力**仅覆盖接口自动化**，通过修复会话（repair session）机制实现。
- 性能测试通过独立的智能分析会话提供诊断，通过 `apply_and_rerun` 实现修复复测。
- UI 自动化**不接入自愈**，失败时仅展示失败日志、截图、Trace；如需调整，走"重新生成 → 重新执行"流程。
- 所有自愈与修复复测动作均需**人工触发**（点击"AI 分析与修复"或"应用并重跑"），不自动自愈。

### 1.2 本 PRD 覆盖

- 接口自动化运行（`api_automation_runs`，`target_type='scripts'`）失败的诊断与脚本级修复全流程。
- 性能测试运行（`performance_test_runs`）的智能分析 + 修复复测。
- 相关数据库表、API 路由、前端页面与验收规则。

### 1.3 本 PRD 不覆盖

- UI 自动化修复（无实现）。
- 业务系统代码本身的修改（修复智能体硬约束不得修改业务系统）。
- 报告中心的"失败聚合 / 内部缺陷"视图（00-13 占位）。
- 性能测试 AI 分析的详细诊断 Agent 逻辑（详见 00-17）。

---

## 2. 入口与路由概览

### 2.1 接口自动化自愈

- 后端 API 前缀：`/api/v1/projects/{project_id}`
- 前端入口：`apps/frontend/src/components/ai-testing/api-automation/api-run-detail.tsx` 中的 `ApiRepairDrawer`
- 客户端封装：`lib/api-client.ts` 中 `createApiRepairSession / getApiRepairSession / createApiRepairAttempt / approveApiRepairAttempt / applyApiRepairAttempt / discardApiRepairAttempt / rejectApiRepairAttempt / getApiRepairAttemptDiff`

### 2.2 性能测试智能分析 + 修复复测

- 后端 API：`/api/v1/projects/{project_id}/performance-analysis/{analysis_id}/apply-and-rerun`
- 前端入口：`apps/frontend/src/app/(main)/projects/[projectId]/performance-tests/[testId]/runs/[runId]/analysis/[analysisId]/page.tsx`（`PerformanceAnalysisReport` 组件）

---

## 3. 接口自动化自愈全流程

### 3.1 状态机

```
attempt 级别：
  queued → collecting_context → diagnosing → { waiting_approval | proposal_ready }
  waiting_approval → candidate_generating → candidate_validating → ready_to_apply
  ready_to_apply → { superseded | completed } （apply 后自动 rerunning）
  proposal_ready → { proposal_rejected | superseded | failed }
  异常路径：failed

终态终态（终态均无可用动作）：
  completed / proposal_rejected / rejected / failed / superseded
```

session 级别：`active`（通过 rollback 回 active）；`passed` / `closed` / `failed`。

### 3.2 触发：人工启用修复会话

1. 接口自动化运行处于 `failed` 或 `observed` 状态（`target_type='scripts'`）。
2. 用户在运行详情页点击"AI 分析与修复"按钮（`ApiRepairDrawer` 打开）。
3. 后端 `create_repair_session`：
   - 校验 run 存在且属于该项目；校验 run status 为 `failed` 或 `observed`；校验 target_type 为 `scripts`。
   - 同一 run 已有活跃 session 时直接返回最近 attempt。
   - 否则创建 `apirepair-<hex>` session 与 attempt 1。
   - 立即对 pytest 套件根执行 `create_revision_snapshot(project_id, session_id, 0, suite_path)` 建立基线快照。
4. 返回 `{session_id, attempt_id, status:'queued'}`；后端 `BackgroundTasks` 调度 `execute_repair_attempt(attempt_id)`。

### 3.3 诊断 attempt（`execute_repair_attempt`）

1. 状态依次：`queued → collecting_context → diagnosing`。
2. 用 `build_failure_context` 汇总：API run 序列化、stdout/stderr、JSON 报告 + `observations`、套件目录结构、历史 attempt 列表、用户上下文。
3. 选取 `api_test_generation` 模型（`resolve_model_selection` + `build_agent_model`，关闭 thinking）。
4. `diagnose_failure`：输出包含 `summary / issues / proposal`。
5. `enforce_uncertain_oracle_policy`：当 `generated_cases` 中存在 `oracle_status in {"inferred","needs_confirmation"}` 且实际响应与之冲突时，生成 `test_data_issue` 类型的 proposal（`script_repair_allowed=true`），用于校准用例状态码。
6. 写入 `attempt_dir/diagnosis.json`；如 `proposal.script_repair_allowed=true` → `waiting_approval`；否则 → `proposal_ready`。
7. 任何异常：attempt 状态置 `failed`，`error_message` 截断 2000 字符。

### 3.4 提案内容

诊断结果 `diagnosis`（`FailureDiagnosis`）包含：
- `summary`：总览摘要。
- `issues`：失败问题列表（含 severity / level / title / statement / confidence / missing_evidence 等）。
- `proposal`：修复提案，含 `script_repair_allowed` 标志、`case_updates` 列表、`target`、`reason`。

候选修复结果 `validation.repair_result`（`RepairResult`）包含：
- `summary` / `case_updates` / `changed_source_files`。

差异：`changes.diff`（unified diff 格式），`changed_files` 列表。

### 3.5 审批（`approve_repair_attempt`）

- 仅 `waiting_approval` 可用。
- 校验 `script_repair_allowed=true`；否则 `409 API_REPAIR_SCRIPT_CHANGE_NOT_ALLOWED`。
- 通过后 attempt → `candidate_generating`，`decision='proposal_approved'`。
- `BackgroundTasks` 调度 `execute_candidate_repair(attempt_id)`。

### 3.6 候选修复生成（`execute_candidate_repair`）

1. 在沙盒内创建 `workspace`（`api_automation/repairs/repair-<session>/attempts/attempt-<NNNN>/workspace`）。
2. 若诊断包含 `case_updates`（多见于 `enforce_uncertain_oracle_policy`）：直接按 `expected_status_code -> actual_status_code` 覆写 `cases.yaml` 的 `status_code` 断言，`oracle_status` 标记为 `confirmed`。
3. 否则调用 `repair_failure`（deepagent），由 deepagent 重写测试代码/工具/配置并在 `.repair-result.json` 落 `RepairResult`。
4. `collect_script_suite` 校验语法。
5. 基于原始环境参数 `run_script_suite` 验证一次（`run_id=repair-validation-<attempt_id>`）。
6. 对比 `rev-<base_revision>` 快照与沙盒 workspace，写入 `changes.diff`（unified diff）。
7. 状态变为 `ready_to_apply`，`available_actions=["view_diff","apply","discard"]`；异常则 `failed`。

### 3.7 应用（`apply_repair_attempt`）

- 仅 `ready_to_apply` 可用。
- 校验 `session.current_revision == attempt.base_revision` 且套件文件清单一致；否则 attempt → `superseded`，返回 `409 REPAIR_BASE_CHANGED`。
- 在 `project_workspace_lock` 内原子替换套件目录 → 落 `rev-<next_revision>` 快照 → 创建 `api_automation_runs`（`parent_run_id=base_run_id`、`source_repair_attempt_id=attempt_id`），状态 `rerunning`。
- 异常时自动回退到 `backup`。
- 返回 `{session_id, attempt_id, run_id, status:'rerunning'}`；后端触发重跑。

### 3.8 放弃 / 驳回

- **discard（`discard_repair_attempt`）**：仅 `ready_to_apply` 可用；删除 workspace，状态 → `proposal_ready`（重置后可重新分析），`decision='candidate_discarded'`。
- **reject（`reject_repair_attempt`）**：不受状态限制；直接置 `proposal_rejected`，`decision='rejected'`。

### 3.9 重新分析（`create_next_repair_attempt`）

- 仅 session `active` 时可用；上一个 attempt 状态必须为 `proposal_ready`。
- 创建 `attempt_number+1` 的新 attempt（`base_run_id=session.current_run_id`、`base_revision=session.current_revision`），并 `execute_repair_attempt`。

### 3.10 回滚（`rollback_repair_session`）

- 校验 session `active` 与目标 revision 存在。
- 拷贝 `rev-<revision>` → 原子替换 `suite_path` → 落新快照 → 创建 `api_automation_runs`（`command_summary` 含 `回退到 Revision <rev>: <reason>`），session 保持 `active`。
- 任意失败自动回退到 `backup`。

---

## 4. 性能测试修复复测

### 4.1 入口

性能测试运行详情 → AI 分析 → 智能分析报告页面（`runs/{runId}/analysis/{analysisId}`）→ `PerformanceAnalysisReport` 组件。

### 4.2 分析会话状态机

分析会话状态（`performance_analysis_sessions.status`）：`collecting → analyzing → { waiting_approval | failed | rejected }`

`repair_status`（派生字段）：
- `not_applicable` / `available` / `rejected` / `preflighting` / `rerunning`

`application_status`：
- `not_requested` → `preflighting` → `preflight_failed` / `rerunning` → `completed` / `apply_failed`

### 4.3 修复复测流程（`apply_and_rerun`）

1. 分析状态为 `waiting_approval` 且 `repair_status='available'` 时可用。
2. 用户在分析报告中选择修复建议（change_ids），点击"应用并重跑"。
3. 后端 `apply_and_rerun`：
   - 校验 `application_status` 为 `not_requested | preflight_failed | apply_failed`。
   - 校验选中的 change 均在安全白名单中（`is_supported_change`），排除 `target_type='platform_code'`。
   - 构建候选配置（`_candidate_configuration`），合并 `before -> after` 变更；校验基线未变化。
   - 执行预检（`_send_preflight`）：单次 HTTP 请求验证配置有效性（status_code + jsonpath 断言）。
   - **预检通过**：更新 `performance_tests` 配置 → 创建新 script（`generation_source='ai_plan'`）→ 确认 script → 调度 `headless_worker.create_run_session` + `start_headless_run` → `application_status='rerunning'` → `completed`。
   - **预检失败**：`application_status='preflight_failed'`，配置未修改，未启动压测。
   - **重跑启动失败**：`application_status='apply_failed'`，配置已修改但压测未启动。

### 4.4 支持的修复变更目标

白名单（`ALLOWED_TARGETS`）：
- `request_config.path_parameters / query_parameters / headers / body / random_seed`
- `load_config.request_timeout_seconds / wait_time_min_seconds / wait_time_max_seconds`
- `data_config / data_config.json_rows`
- `success_rules`

不支持：`target_type='platform_code'`（平台源码修改）。

---

## 5. UI 自动化失败处理

### 5.1 失败展示

- 入口：`ui_automation_run_detail` 页面。
- 展示内容：失败日志（stdout/stderr）、截图（screenshot_paths）、Trace（trace_path）。
- **无修复会话按钮、无 patch、无 apply / rollback 机制**。

### 5.2 调整流程

如需调整 UI 自动化脚本：重新生成（`ui_automation_generation_runs`）→ 重新执行（`ui_automation_execution_runs`）。

---

## 6. 审计与数据模型

### 6.1 接口自动化自愈审计

| 数据库表 | 说明 |
|---|---|
| `api_repair_sessions` | 修复会话：id / project_id / source_run_id / current_run_id / current_revision / status / created_by |
| `api_repair_attempts` | 修复轮次：id / session_id / attempt_number / base_run_id / base_revision / status / diagnosis_json / validation_json / decision / applied_run_id / error_message |
| `api_test_case_versions` | 用例版本快照：id / case_id / version / snapshot_json / change_source='ai_repair' |
| `api_endpoint_oracle_facts` | 端点 Oracle 事实（approve 后沉淀） |
| `api_oracle_proposals` | Oracle 提案（approve / reject） |
| `api_automation_runs` | 运行记录：parent_run_id / source_repair_attempt_id（溯源） |

产物存储（`storage.PROJECT_FILE_STORAGE_ROOT/<project_id>/api_automation/repairs/repair-<session>/`）：
- `revisions/rev-<NNNN>/`：套件快照。
- `attempts/attempt-<NNNN>/workspace/`：沙盒。
- `attempts/attempt-<NNNN>/diagnosis.json`。
- `attempts/attempt-<NNNN>/validation/{stdout,stderr,report.json}`。
- `attempts/attempt-<NNNN>/changes.diff`。

### 6.2 性能测试修复复测审计

| 数据库表 | 说明 |
|---|---|
| `performance_analysis_sessions` | 分析会话：id / run_id / status / repair_status / application_status / preflight / applied_script_id / applied_run_id / applied_by / applied_at |

---

## 7. API 路由清单

### 7.1 接口自动化自愈（`/api/v1/projects/{project_id}`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api-runs/{run_id}/repair-session` | 创建修复会话（admin） |
| GET | `/api-repair-sessions/{session_id}` | 会话详情（含 attempts） |
| POST | `/api-repair-sessions/{session_id}/attempts` | 新增一轮 attempt（admin） |
| GET | `/api-repair-attempts/{attempt_id}` | attempt 详情 |
| GET | `/api-repair-attempts/{attempt_id}/diff` | unified diff |
| GET | `/api-repair-attempts/{attempt_id}/logs` | 验证日志 stdout/stderr |
| GET | `/api-repair-attempts/{attempt_id}/report` | validation/report.json |
| POST | `/api-repair-attempts/{attempt_id}/approve` | 审批 proposal（admin） |
| POST | `/api-repair-attempts/{attempt_id}/apply` | 应用候选修复（admin） |
| POST | `/api-repair-attempts/{attempt_id}/discard` | 丢弃候选（admin） |
| POST | `/api-repair-attempts/{attempt_id}/reject` | 驳回（admin） |
| POST | `/api-repair-sessions/{session_id}/rollback` | 回滚到指定 revision（admin） |

### 7.2 性能测试智能分析（`/api/v1/projects/{project_id}`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/performance-tests/{test_id}/runs/{run_id}/ai-analysis` | 创建智能分析 |
| GET | `/performance-tests/{test_id}/runs/{run_id}/ai-analysis` | 获取分析列表 |
| POST | `/performance-analysis/{analysis_id}/reject` | 拒绝分析 |
| POST | `/performance-analysis/{analysis_id}/apply-and-rerun` | 应用修复并重跑 |

### 7.3 错误码

自愈：`API_RUN_NOT_FOUND` / `API_REPAIR_RUN_NOT_FAILED` / `API_REPAIR_TARGET_UNSUPPORTED` / `API_REPAIR_SESSION_NOT_FOUND` / `API_REPAIR_SESSION_NOT_ACTIVE` / `API_REPAIR_ATTEMPT_NOT_FOUND` / `API_REPAIR_ATTEMPT_NOT_APPROVABLE` / `API_REPAIR_SCRIPT_CHANGE_NOT_ALLOWED` / `API_REPAIR_ATTEMPT_NOT_APPLICABLE` / `API_REPAIR_WORKSPACE_NOT_FOUND` / `API_REPAIR_COLLECTION_FAILED` / `API_REPAIR_REVISION_NOT_FOUND` / `API_REPAIR_ARTIFACT_NOT_FOUND` / `REPAIR_BASE_CHANGED`。

性能修复：`PERFORMANCE_REPAIR_CHANGES_REQUIRED` / `PERFORMANCE_ANALYSIS_NOT_FOUND` / `PERFORMANCE_REPAIR_NOT_APPROVABLE` / `PERFORMANCE_REPAIR_ALREADY_APPLIED` / `PERFORMANCE_REPAIR_CHANGE_UNSUPPORTED` / `PERFORMANCE_RUN_NOT_FOUND` / `PERFORMANCE_TEST_NOT_FOUND` / `PERFORMANCE_REPAIR_SCRIPT_INVALID` / `PERFORMANCE_REPAIR_STATE_CHANGED` / `PERFORMANCE_REPAIR_BASELINE_CHANGED` / `PERFORMANCE_REPAIR_RERUN_FAILED`。

---

## 8. 前端页面清单

| 页面 | 路径 | 功能 |
|---|---|---|
| 接口自动化运行详情 | `/projects/{projectId}/automation/api/runs/{runId}` | 展示运行结果；失败时显示"AI 分析与修复"按钮 |
| 接口自动化修复抽屉 | `ApiRepairDrawer` 组件 | 修复会话状态、attempt 时间线、diff 对话框 |
| 性能测试智能分析报告 | `/projects/{projectId}/performance-tests/{testId}/runs/{runId}/analysis/{analysisId}` | 展示分析报告；`apply_and_rerun` 按钮 |
| 性能测试运行详情 | `/projects/{projectId}/performance-tests/{testId}/runs/{runId}` | 展示运行结果；进入 AI 分析入口 |

---

## 9. 验收规则

### 9.1 接口自动化自愈

- 失败 run 发起会话返回 `{session_id, attempt_id, status:'queued'}`；同 run 重复请求复用已有 session。
- 诊断结果 `diagnosis` 字段符合 `FailureDiagnosis`；`proposal.script_repair_allowed=false` 时 attempt 落在 `proposal_ready`。
- `approve → candidate_generating → candidate_validating → ready_to_apply` 计时日志可在 `validation.logs` 中看到验证 stdout/stderr。
- `apply` 成功后新 run id 写入 `attempt.applied_run_id`，session.current_revision 自增，套件目录被替换为 attempt workspace 内容。
- `apply` 期间发生异常会自动恢复原套件，attempt 状态置 `failed`。
- `discard` 仅作用于 `ready_to_apply`；`reject` 写入 `decision='rejected'`、状态 `proposal_rejected`，不删除 workspace。
- `rollback` 自动触发新 run（`command_summary` 含 `回退到 Revision <rev>: <reason>`），session 保持 `active`。
- 修复产物（diagnosis / validation / diff / logs）按 attempt 目录隔离，跨项目不可访问。
- UI 自动化运行详情页**不**展示修复抽屉或修复按钮。

### 9.2 性能测试修复复测

- 分析状态为 `waiting_approval` 且 `repair_status='available'` 时才显示"应用并重跑"按钮。
- 选中的 change 必须在安全白名单内；`target_type='platform_code'` 的 change 不可选。
- 预检通过：`application_status='completed'`，配置已更新，新 script 已创建，新压测运行已启动。
- 预检失败：`application_status='preflight_failed'`，配置未变化，未启动压测。
- 重新压测完成后，`applied_run_id` 写入分析会话，可在分析报告中查看修复后的运行结果。

---

## 10. 实现依据

- **后端自愈服务**：`apps/backend/app/services/api_automation/self_healing.py`
- **后端性能修复服务**：`apps/backend/app/services/performance_testing/repair_service.py`
- **路由**：`apps/backend/app/api/v1/api_automation.py`（自愈 11 个端点）、`apps/backend/app/api/v1/performance_runs.py`（分析 + 修复复测端点）
- **数据库**：`apps/backend/app/seed/schema.py`（`api_repair_sessions / api_repair_attempts / performance_analysis_sessions / api_test_case_versions / api_endpoint_oracle_facts / api_oracle_proposals`）
- **前端**：
  - `apps/frontend/src/components/ai-testing/api-automation/api-run-detail.tsx`
  - `apps/frontend/src/components/ai-testing/api-automation/api-repair-drawer.tsx`
  - `apps/frontend/src/app/(main)/projects/[projectId]/performance-tests/[testId]/runs/[runId]/analysis/[analysisId]/page.tsx`
  - `apps/frontend/src/components/ai-testing/performance-testing/performance-analysis-report.tsx`
- **客户端封装**：`apps/frontend/src/lib/api-client.ts`（修复 API + 性能分析 API）
