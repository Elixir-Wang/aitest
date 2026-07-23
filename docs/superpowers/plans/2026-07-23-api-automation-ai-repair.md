# 接口自动化 AI 分析与修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有接口自动化失败运行详情中增加手动触发、人工审批、可连续迭代的 AI 诊断与 suite 修复能力。

**Architecture:** 以失败的 `api_automation_runs` 为起点创建独立 `api_repair_sessions` 和 `api_repair_attempts`。Diagnosis Agent 只输出结构化诊断，Repair Agent 只在临时 workspace 修改并运行完整回归；确定性的 `self_healing` Service 负责脱敏、Diff、审批、Revision、数据库用例同步和正式重跑。前端继续复用现有运行详情和轮询模式。

**Tech Stack:** FastAPI、SQLite、Pydantic v2、DeepAgents、FilesystemBackend、pytest-json-report、Next.js、React、TypeScript、Biome、Node `node:test`。

## Global Constraints

- 失败后必须由用户手动点击“AI 分析与修复”。
- AI 只能修改临时 workspace；正式 suite 必须人工审批后更新。
- AI 可以修改整个 `pytest_requests` suite，但不能修改被测业务系统代码。
- `cases.yaml/json` 是数据库用例快照；正式应用必须先更新数据库，再重新生成数据文件。
- 审批前必须在临时副本执行完整接口回归。
- 修复轮数不设固定上限，但每轮必须有工具调用、时间、Diff 和上下文限制。
- 不提供通用 Shell；只提供 collection 和完整回归受控工具。
- 必须脱敏 Authorization、Cookie、Token、API Key、密码、Secret 和敏感业务字段。
- 必须复用现有项目级 `project_workspace_lock`、pytest Runner、运行日志、JSON 报告和 operation log。
- 不新增 Celery、Redis、LangGraph、通用 Pipeline 或独立 Repair Repository。
- 不删除失败用例，不使用 `skip`、`xfail`、吞异常或弱化断言来制造通过。
- 不回滚用户选择保留的失败变更；提供显式历史 Revision 回退。
- 不修改用户当前未请求的业务模块和现有未提交文件。

---

## Task 1: Persist repair sessions, attempts, and run lineage

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/app/repositories/api_automation_repo.py`
- Modify: `apps/backend/app/schemas/api_automation.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_repo.py`
- Test: `apps/backend/tests/test_api_automation_schema_repo.py`

**Interfaces:**
- Repository: `create_repair_session`, `find_repair_session`, `update_repair_session`, `create_repair_attempt`, `find_repair_attempt`, `list_repair_attempts`, `update_repair_attempt`.
- Schemas: `ApiRepairSessionCreateIn`, `ApiRepairSessionOut`, `ApiRepairAttemptOut`, `ApiRepairAttemptCreateIn`, `ApiRepairApprovalIn`, `ApiRepairRejectIn`, `ApiRepairRollbackIn`.
- Serialized API runs expose `parent_run_id` and `source_repair_attempt_id`.

- [ ] **Step 1: Write failing persistence tests**

Use the existing temporary database helper and assert the new tables and run columns exist:

```python
def test_repair_tables_and_run_lineage_columns_exist(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    with connect() as db:
        session_columns = {row["name"] for row in db.execute(
            "PRAGMA table_info(api_repair_sessions)"
        ).fetchall()}
        attempt_columns = {row["name"] for row in db.execute(
            "PRAGMA table_info(api_repair_attempts)"
        ).fetchall()}
        run_columns = {row["name"] for row in db.execute(
            "PRAGMA table_info(api_automation_runs)"
        ).fetchall()}
    assert {"id", "project_id", "source_run_id", "current_run_id", "status", "current_revision"} <= session_columns
    assert {"id", "session_id", "attempt_number", "base_run_id", "base_revision", "status"} <= attempt_columns
    assert {"parent_run_id", "source_repair_attempt_id"} <= run_columns
```

Add repository round-trip coverage for JSON fields, status updates, unique `(session_id, attempt_number)`, and project ownership.

- [ ] **Step 2: Run focused tests and verify failure**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_repo.py tests/test_api_automation_schema_repo.py -q
```

Expected: FAIL because tables, columns, Repository methods, and schemas do not exist.

- [ ] **Step 3: Add schema and idempotent upgrade logic**

Add `api_repair_sessions` and `api_repair_attempts` to `schema.py` with foreign keys to projects/runs, session status `active|passed|closed|failed`, Attempt status values from the design, and `UNIQUE(session_id, attempt_number)`. Add idempotent `ALTER TABLE` checks in `seeds.py` for `parent_run_id` and `source_repair_attempt_id`, matching `_ensure_api_automation_run_columns`.

- [ ] **Step 4: Implement Repository and Pydantic contracts**

Place the methods next to existing API run methods. Use existing `dumps_json`/`loads_json` helpers and `_StrippedModel` with `extra="forbid"`. Bound `user_context` and comments to 20,000 characters and validate rollback revisions as non-negative.

- [ ] **Step 5: Extend API run serialization**

Update `create_api_run`, `update_api_run`, `find_api_run`, and `_serialize_api_run` so lineage fields round-trip while existing callers continue to pass `None`.

- [ ] **Step 6: Run focused tests**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_repo.py tests/test_api_automation_schema_repo.py -q
```

Expected: PASS for fresh initialization and idempotent upgrade of an existing database.

- [ ] **Step 7: Commit the persistence slice**

```powershell
cd D:\project\test_project
git add apps/backend/app/seed/schema.py apps/backend/app/seed/seeds.py apps/backend/app/repositories/api_automation_repo.py apps/backend/app/schemas/api_automation.py apps/backend/app/services/api_automation/service.py apps/backend/tests/test_api_automation_ai_repair_repo.py apps/backend/tests/test_api_automation_schema_repo.py
git commit -m "feat: persist api automation repair sessions"
```

---

## Task 2: Add revision, workspace, manifest, and redaction utilities

**Files:**
- Create: `apps/backend/app/services/api_automation/self_healing_artifacts.py`
- Create: `apps/backend/app/services/api_automation/self_healing_context.py`
- Modify: `apps/backend/app/services/api_automation/artifact_storage.py`
- Modify: `apps/backend/app/services/api_automation/runner.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_artifacts.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_context.py`
- Test: `apps/backend/tests/test_api_automation_runner.py`

**Interfaces:**
- `repair_root(project_id: str, session_id: str) -> Path`
- `create_attempt_workspace(project_id: str, session_id: str, attempt_number: int, suite_path: Path) -> Path`
- `create_revision_snapshot(project_id: str, session_id: str, revision: int, suite_path: Path) -> Path`
- `build_manifest(root: Path) -> dict[str, dict[str, Any]]`
- `redact_sensitive(value: Any) -> Any`
- `build_failure_context(run, logs, report, suite_path, history, user_context) -> dict[str, Any]`
- `run_full_regression` returns a redacted summary with collection, passed, failed, errors, resolved, remaining, and new failures.

- [ ] **Step 1: Write failing artifact and redaction tests**

Assert manifests hash source files but ignore `__pycache__`, `.pytest_cache`, reports, logs, and runtime output. Assert nested Authorization, Cookie, Token, Secret, Password, API Key, and bearer values are redacted. Assert context includes failure nodeids, stack traces, case IDs, user context, and bounded historical summaries without raw credentials.

- [ ] **Step 2: Run tests and verify failure**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_artifacts.py tests/test_api_automation_ai_repair_context.py -q
```

Expected: FAIL because the utilities do not exist.

- [ ] **Step 3: Implement fixed repair paths and manifests**

Use `PROJECT_FILE_STORAGE_ROOT / project_id / "api_automation" / "repairs" / f"repair-{session_id}"`. Resolve every path and require it to stay under the repair root. Copy formal suites into `attempts/attempt-N/workspace` and snapshots into `revisions/rev-N`. Store SHA-256 manifests and exclude runtime artifacts.

- [ ] **Step 4: Implement recursive redaction and bounded context**

Redact sensitive keys case-insensitively and redact bearer/key-like string values. Cap every log/report/file snippet at 50,000 characters with an explicit truncation marker. Preserve request/response structure while removing secrets.

- [ ] **Step 5: Add fixed full-regression runner**

Extend `runner.py` with a wrapper that internally builds the pytest command, validates suite/report paths, stores stdout/stderr/report under the Attempt directory, and never accepts arbitrary commands or pytest arguments.

- [ ] **Step 6: Run artifact, context, and runner tests**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_artifacts.py tests/test_api_automation_ai_repair_context.py tests/test_api_automation_runner.py -q
```

Expected: PASS without changing existing runner behavior.

- [ ] **Step 7: Commit the artifact slice**

```powershell
cd D:\project\test_project
git add apps/backend/app/services/api_automation/self_healing_artifacts.py apps/backend/app/services/api_automation/self_healing_context.py apps/backend/app/services/api_automation/artifact_storage.py apps/backend/app/services/api_automation/runner.py apps/backend/tests/test_api_automation_ai_repair_artifacts.py apps/backend/tests/test_api_automation_ai_repair_context.py apps/backend/tests/test_api_automation_runner.py
git commit -m "feat: add api repair workspaces and redaction"
```

---

## Task 3: Implement structured Diagnosis Agent

**Files:**
- Create: `apps/backend/app/agents/api_automation/self_healing/__init__.py`
- Create: `apps/backend/app/agents/api_automation/self_healing/schemas.py`
- Create: `apps/backend/app/agents/api_automation/self_healing/diagnosis_agent.py`
- Create: `apps/backend/app/agents/api_automation/self_healing/skills/api-failure-diagnosis/SKILL.md`
- Create: `apps/backend/app/agents/api_automation/self_healing/skills/api-failure-diagnosis/references/classification-rules.md`
- Create: `apps/backend/app/agents/api_automation/self_healing/skills/api-failure-diagnosis/references/evidence-priority.md`
- Test: `apps/backend/tests/test_api_automation_ai_repair_diagnosis.py`

**Interfaces:**
- `FailureIssue`, `FailureDiagnosis`, `CaseUpdate`, and `RepairResult` are strict Pydantic models.
- `create_diagnosis_agent(*, model)` returns a read-only structured-output Agent.
- `async diagnose_failure(*, model, context: dict[str, Any]) -> FailureDiagnosis` uses the existing `api_test_generation` model selection.

- [ ] **Step 1: Write failing schema tests**

Test rejection of unknown classifications, confidence outside `[0, 1]`, empty failure IDs, and unknown top-level fields. Add a mixed fixture containing import error, inferred status assertion, timeout, and explicit 500 response.

- [ ] **Step 2: Run diagnosis tests and verify failure**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_diagnosis.py -q
```

Expected: FAIL because the models and Agent do not exist.

- [ ] **Step 3: Implement strict diagnosis and repair result models**

Use classifications `test_code_issue`, `test_data_issue`, `environment_issue`, `interface_bug`, `contract_ambiguity`, and `unknown`. Require non-empty evidence, root cause, and recommendation for every issue. Keep `CaseUpdate.changes` JSON-compatible.

- [ ] **Step 4: Implement read-only Diagnosis Agent**

Reuse `resolve_model_selection("api_test_generation")`, `build_agent_model`, and `thinking_disabled_extra_body`. The prompt must include evidence priority, business-code prohibition, no-speculative-repair rules, and explicit uncertainty. Parse output into `FailureDiagnosis`; invalid structured output becomes a controlled Attempt failure.

- [ ] **Step 5: Add diagnosis skills and references**

Document concrete ImportError, timeout, auth, assertion, schema, 5xx, and contract ambiguity examples. Require the Agent to inspect actual report evidence before inferring and to group failures by root cause.

- [ ] **Step 6: Run diagnosis tests**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_diagnosis.py -q
```

Expected: PASS with model calls mocked and no network access.

- [ ] **Step 7: Commit the diagnosis slice**

```powershell
cd D:\project\test_project
git add apps/backend/app/agents/api_automation/self_healing apps/backend/tests/test_api_automation_ai_repair_diagnosis.py
git commit -m "feat: add structured api failure diagnosis agent"
```

---

## Task 4: Implement constrained Repair Agent and validation tools

**Files:**
- Create: `apps/backend/app/agents/api_automation/self_healing/repair_agent.py`
- Create: `apps/backend/app/agents/api_automation/self_healing/validation.py`
- Create: `apps/backend/app/agents/api_automation/self_healing/skills/pytest-suite-repair/SKILL.md`
- Create: `apps/backend/app/agents/api_automation/self_healing/skills/pytest-suite-repair/references/repair-boundaries.md`
- Create: `apps/backend/app/agents/api_automation/self_healing/skills/pytest-suite-repair/references/case-data-updates.md`
- Create: `apps/backend/app/agents/api_automation/self_healing/skills/pytest-suite-repair/references/validation-rules.md`
- Modify: `apps/backend/app/agents/api_automation/self_healing/__init__.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_agent.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_validation.py`

**Interfaces:**
- `create_repair_agent(*, model, workspace: Path, validation_config: ValidationConfig)` returns a FilesystemBackend Agent rooted at workspace.
- `async repair_failure(*, model, workspace: Path, diagnosis: FailureDiagnosis, context: dict[str, Any]) -> RepairResult`.
- `validate_workspace_path(workspace: Path, candidate: str) -> Path` rejects absolute paths, `..`, links, `.git`, runtime artifacts, and paths outside workspace.
- `run_collection_tool` and `run_full_regression_tool` expose only fixed runner operations.

- [ ] **Step 1: Write failing security and Agent contract tests**

Test path traversal, absolute paths, `.git`, symlink/Junction escape, arbitrary command parameters, deleted test files, `pytest.skip`, `pytest.xfail`, and broad exception swallowing. Mock the Agent and subprocess.

- [ ] **Step 2: Run tests and verify failure**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_agent.py tests/test_api_automation_ai_repair_validation.py -q
```

Expected: FAIL because the Repair Agent and tools do not exist.

- [ ] **Step 3: Implement workspace and mutation checks**

Compare pre/post manifests and reject changes outside workspace, links escaping workspace, generated binaries, runtime artifacts, deleted tests, skipped tests, removed critical assertions, and hard-coded secrets.

- [ ] **Step 4: Implement controlled validation tools**

Tools accept only trusted workspace, test paths, environment, and timeout values. Build pytest commands internally and return bounded summaries. Do not expose a generic subprocess or Shell tool.

- [ ] **Step 5: Implement Repair Agent with existing DeepAgents patterns**

Use `FilesystemBackend(root_dir=str(workspace), virtual_mode=True)`, `InvalidToolCallRecoveryMiddleware`, `ToolCallLimitMiddleware`, the structured Diagnosis, and historical context. The system prompt must allow suite code/data/config changes but prohibit business-code changes and formal-suite writes.

- [ ] **Step 6: Run Agent and validation tests**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_agent.py tests/test_api_automation_ai_repair_validation.py -q
```

Expected: PASS with model, subprocess, and filesystem calls mocked.

- [ ] **Step 7: Commit the Repair Agent slice**

```powershell
cd D:\project\test_project
git add apps/backend/app/agents/api_automation/self_healing apps/backend/tests/test_api_automation_ai_repair_agent.py apps/backend/tests/test_api_automation_ai_repair_validation.py
git commit -m "feat: add constrained api suite repair agent"
```

---

## Task 5: Orchestrate session creation, diagnosis, repair, and history

**Files:**
- Create: `apps/backend/app/services/api_automation/self_healing.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/services/api_automation/artifact_storage.py`
- Modify: `apps/backend/app/services/task_service.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_service.py`

**Interfaces:**
- `create_repair_session(project_id: str, run_id: str, user_context: str, actor: dict) -> dict`
- `get_repair_session(project_id: str, session_id: str, actor: dict) -> dict`
- `create_repair_attempt(project_id: str, session_id: str, user_context: str, actor: dict) -> dict`
- `execute_repair_attempt(attempt_id: str) -> None`
- `build_repair_history(session_id: str) -> list[dict[str, Any]]`

- [ ] **Step 1: Write failing lifecycle and idempotency tests**

Test that a failed script run creates Session + Attempt-1 + `rev-0000`, repeated creation reuses the active Session, a passed run is rejected, another active project repair returns `409 API_REPAIR_PROJECT_ACTIVE`, and an active Attempt blocks another continue request. Test optional `user_context` and history inclusion with Agents and subprocess mocked.

- [ ] **Step 2: Run service tests and verify failure**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_service.py -q
```

Expected: FAIL because orchestration does not exist.

- [ ] **Step 3: Implement Session and Attempt creation**

Validate project visibility/admin permission through existing helpers. Require a terminal failed/observed script run with a real suite path. Create the initial Revision, Session, and Attempt in one database transaction. For the first implementation, explicitly reject scenario runs with `409 API_REPAIR_TARGET_UNSUPPORTED` rather than guessing how scenario assets map to a suite.

- [ ] **Step 4: Implement background Attempt execution**

Implement this deterministic sequence:

```text
collecting_context
→ diagnosing
→ generating_patch
→ validating
→ waiting_approval
```

Build redacted context, invoke Diagnosis Agent, save `diagnosis.json`, copy the current Revision to workspace, invoke Repair Agent, compute the real manifest/Diff, validate `case_updates`, run collection and full regression, save artifacts, and serialize `validation_json`. Do not hold the formal workspace write lock while model inference or full regression is running.

- [ ] **Step 5: Handle non-repairable diagnoses**

If all issues are `interface_bug`, `environment_issue`, `contract_ambiguity`, or `unknown` and no safe suite patch exists, save the structured report and return Session to `active` with no approval action. The user may add context and create another Attempt; do not close the Session automatically.

- [ ] **Step 6: Build bounded history and no-improvement warnings**

History summaries must contain Attempt number, diagnosis summary, changed files, before/after counts, resolved/new failures, user context, decision, and applied run ID. Add warnings for two rounds without improvement, repeated root causes, repeated same-file changes, and repeated low confidence. Never block the user solely because of these warnings.

- [ ] **Step 7: Run service tests**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_service.py -q
```

Expected: PASS with no real model or API calls.

- [ ] **Step 8: Commit the orchestration slice**

```powershell
cd D:\project\test_project
git add apps/backend/app/services/api_automation/self_healing.py apps/backend/app/services/api_automation/service.py apps/backend/app/services/api_automation/artifact_storage.py apps/backend/app/services/task_service.py apps/backend/tests/test_api_automation_ai_repair_service.py
git commit -m "feat: orchestrate api repair attempts"
```

---

## Task 6: Implement approval, revision application, rollback, and formal rerun

**Files:**
- Modify: `apps/backend/app/services/api_automation/self_healing.py`
- Modify: `apps/backend/app/repositories/api_automation_repo.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/services/api_automation/artifact_storage.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_apply.py`

**Interfaces:**
- `approve_repair_attempt(project_id: str, attempt_id: str, comment: str, actor: dict) -> dict`
- `reject_repair_attempt(project_id: str, attempt_id: str, comment: str, actor: dict) -> dict`
- `rollback_repair_session(project_id: str, session_id: str, revision: int, reason: str, actor: dict) -> dict`
- `apply_case_updates(db, project_id: str, case_updates: list[CaseUpdate]) -> None`
- `recover_incomplete_apply(project_id: str, session_id: str) -> None`

- [ ] **Step 1: Write failing approval and rollback tests**

Cover baseline drift returning `409 REPAIR_BASE_CHANGED`, case database updates followed by canonical YAML regeneration, source-file application, new Revision creation, formal run lineage, rejection without mutation, rollback as a new Revision, database failure compensation, directory-swap failure compensation, and interrupted `apply-state.json` recovery.

- [ ] **Step 2: Run apply tests and verify failure**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_apply.py -q
```

Expected: FAIL because approval and Revision application do not exist.

- [ ] **Step 3: Implement baseline consistency checks**

Under `project_workspace_lock`, compare the formal suite manifest with the Attempt's `base_revision`. On any drift, mark the Attempt `superseded`, preserve its artifacts, and return `409 REPAIR_BASE_CHANGED`.

- [ ] **Step 4: Validate and apply database-owned case updates**

Require every `case_id` to belong to the project and restrict changes to request, test data, assertions, expected values, and notes. Reject identifiers, endpoint ownership, project ownership, creator, timestamps, method, and path ownership. Update through existing test-case Service/Repository logic and regenerate canonical data files.

- [ ] **Step 5: Implement staged filesystem/database commit**

Create staging from the current formal suite, apply approved source changes and canonical case data, run collection, write `apply-state.json`, open the database transaction, update cases, atomically swap formal/staging directories on the same volume, create the next Revision manifest, update Session/Attempt, and commit. Restore both database and formal suite on failure.

- [ ] **Step 6: Create formal run lineage after approval**

Only after the apply transaction succeeds, create a normal `api_run` using the original environment and script scope. Set `parent_run_id=base_run_id` and `source_repair_attempt_id=attempt_id`, enqueue existing `execute_api_run`, and set Attempt `rerunning`. A pytest failure keeps the applied Revision and returns Session to `active`.

- [ ] **Step 7: Implement rejection and rollback**

Rejection records comment/decision and leaves formal assets unchanged. Rollback copies a historical Revision into staging, synchronizes database-owned case records, creates a new Revision number, and creates a formal verification run. Never delete historical Revisions.

- [ ] **Step 8: Run apply and existing regression tests**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_apply.py tests/test_api_automation_schema_repo.py tests/test_api_automation_runner.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit approval and rollback**

```powershell
cd D:\project\test_project
git add apps/backend/app/services/api_automation/self_healing.py apps/backend/app/repositories/api_automation_repo.py apps/backend/app/services/api_automation/service.py apps/backend/app/services/api_automation/artifact_storage.py apps/backend/tests/test_api_automation_ai_repair_apply.py
git commit -m "feat: approve and rollback api repair revisions"
```

---

## Task 7: Expose FastAPI repair endpoints and task visibility

**Files:**
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Modify: `apps/backend/app/schemas/api_automation.py`
- Modify: `apps/backend/app/services/task_service.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_api.py`

**Interfaces:**
- `POST /projects/{project_id}/api-runs/{run_id}/repair-session`
- `GET /projects/{project_id}/api-repair-sessions/{session_id}`
- `POST /projects/{project_id}/api-repair-sessions/{session_id}/attempts`
- `GET /projects/{project_id}/api-repair-attempts/{attempt_id}`
- `GET /projects/{project_id}/api-repair-attempts/{attempt_id}/diff`
- `GET /projects/{project_id}/api-repair-attempts/{attempt_id}/logs`
- `GET /projects/{project_id}/api-repair-attempts/{attempt_id}/report`
- `POST /projects/{project_id}/api-repair-attempts/{attempt_id}/approve`
- `POST /projects/{project_id}/api-repair-attempts/{attempt_id}/reject`
- `POST /projects/{project_id}/api-repair-sessions/{session_id}/rollback`

- [ ] **Step 1: Write failing API contract tests**

Assert read permission for visible project users, admin-only mutation, project mismatch isolation, active Session reuse, duplicate active Attempt `409`, missing artifact `404`, and correct BackgroundTasks dispatch for create, continue, approve, and rollback.

- [ ] **Step 2: Run API tests and verify failure**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_api.py -q
```

Expected: FAIL because routes are absent.

- [ ] **Step 3: Register routes using existing FastAPI patterns**

Use `require_admin` for mutations, `current_user` for reads, `BackgroundTasks.add_task` for long-running workflows, and the existing `api_error` response format. Return `available_actions` from the backend so the frontend does not infer invalid state combinations.

- [ ] **Step 4: Add repair Attempts to the global task list**

Reuse the existing task-service response shape and status mapping. Do not create a separate task table. Include project, Session, Attempt, current phase, and navigation metadata.

- [ ] **Step 5: Run API and backend regression tests**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_api.py tests/test_api_automation_schema_repo.py tests/test_api_automation_runner.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the API slice**

```powershell
cd D:\project\test_project
git add apps/backend/app/api/v1/api_automation.py apps/backend/app/schemas/api_automation.py apps/backend/app/services/task_service.py apps/backend/tests/test_api_automation_ai_repair_api.py
git commit -m "feat: expose api repair endpoints"
```

---

## Task 8: Add frontend client contracts and repair panel

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-run-detail.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-repair-panel.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-repair-diff-dialog.tsx`
- Test: `apps/frontend/tests/api-automation-ai-repair-contract.test.mjs`

**Interfaces:**
- Types: `ApiRepairSession`, `ApiRepairAttempt`, `ApiRepairDiagnosis`, `ApiRepairValidation`, `ApiRepairChangedFile`, `ApiRepairAvailableAction`.
- Client functions for create/get Session, create/get Attempt, Diff/log/report, approve, reject, and rollback.
- `ApiRepairPanel` receives `projectId`, `run`, and `onRunChanged`.

- [ ] **Step 1: Write failing frontend contract tests**

Using existing source-contract tests, assert the failed run exposes “AI 分析与修复”, the panel contains “完整接口回归”, “补充信息并重新生成”, “批准并应用”, “继续修复”, interface-bug evidence, new-failure warning, Diff files, and repair history. Assert the API client contains all exact route functions.

- [ ] **Step 2: Run frontend test and verify failure**

```powershell
cd D:\project\test_project\apps\frontend
node --test tests/api-automation-ai-repair-contract.test.mjs
```

Expected: FAIL because no repair UI/client exists.

- [ ] **Step 3: Add typed API client contracts**

Match existing `apiRequest` patterns and backend paths exactly. Treat `available_actions` as authoritative. Keep structured diagnosis and validation fields typed; use `Record<string, unknown>` only for raw report payloads.

- [ ] **Step 4: Add manual trigger confirmation**

Show the trigger only for terminal failed/observed script runs. Before creation, display environment name/base URL, case count, full-regression warning, possible data-writing requests, and the fact that formal suite changes still require approval.

- [ ] **Step 5: Implement polling and state rendering**

Render phase progress, diagnosis groups, confidence/evidence/recommendation, before/after counts, resolved/remaining/new failures, changed files, per-file Diff dialog, sanitized logs/report, and historical Attempts. Do not render model chain-of-thought.

- [ ] **Step 6: Implement optional context, approval, rejection, continue, and rollback**

Allow empty user context with an explicit notice that only current failure/history will be used. Refresh Session and run detail after actions. Keep rejected and superseded Attempts visible.

- [ ] **Step 7: Run frontend tests and checks**

```powershell
cd D:\project\test_project\apps\frontend
node --test tests/api-automation-ai-repair-contract.test.mjs
npx biome check src/lib/api-client.ts src/components/ai-testing/api-automation/api-run-detail.tsx src/components/ai-testing/api-automation/api-repair-panel.tsx src/components/ai-testing/api-automation/api-repair-diff-dialog.tsx tests/api-automation-ai-repair-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 8: Commit the frontend slice**

```powershell
cd D:\project\test_project
git add apps/frontend/src/lib/api-client.ts apps/frontend/src/components/ai-testing/api-automation/api-run-detail.tsx apps/frontend/src/components/ai-testing/api-automation/api-repair-panel.tsx apps/frontend/src/components/ai-testing/api-automation/api-repair-diff-dialog.tsx apps/frontend/tests/api-automation-ai-repair-contract.test.mjs
git commit -m "feat: add api repair approval panel"
```

---

## Task 9: Add audit logs, recovery, and end-to-end regression coverage

**Files:**
- Modify: `apps/backend/app/services/api_automation/self_healing.py`
- Modify: `apps/backend/app/services/api_automation/artifact_storage.py`
- Modify: `apps/backend/app/services/operation_log_service.py` only if existing helpers are insufficient
- Test: `apps/backend/tests/test_api_automation_ai_repair_e2e.py`
- Test: `apps/backend/tests/test_agent_architecture_boundaries.py`
- Test: `apps/frontend/tests/api-automation-ai-repair-contract.test.mjs`

- [ ] **Step 1: Write a mocked end-to-end repair chain test**

Create a temporary project suite and fake failed report. Mock Diagnosis Agent and Repair Agent so Attempt-1 proposes a case update, approval creates Revision + run-2, run-2 still fails, and Attempt-2 receives user context plus Attempt-1 history. Assert:

```text
source run → session → attempt-1 → revision-1 → run-2 → attempt-2
```

- [ ] **Step 2: Add malicious and drift regression cases**

Test path traversal, secret leakage, `skip/xfail`, deleted tests, arbitrary commands, project mismatch, duplicate active Attempts, changed formal suite, and database/filesystem compensation.

- [ ] **Step 3: Add incomplete apply recovery**

Create an interrupted `apply-state.json` with backup/staging directories, invoke recovery, and assert the formal suite is restored and the Attempt becomes failed with an actionable error.

- [ ] **Step 4: Add operation logs and architecture boundaries**

Record Session creation, Attempt creation, approval, rejection, rollback, and close through `operation_log_service.record_change`. Extend architecture tests so Diagnosis Agent cannot import database/formal mutation functions and Repair Agent cannot call arbitrary subprocesses.

- [ ] **Step 5: Run focused verification**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_ai_repair_e2e.py tests/test_agent_architecture_boundaries.py -q

cd D:\project\test_project\apps\frontend
node --test tests/api-automation-ai-repair-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Run broader regression**

```powershell
cd D:\project\test_project\apps\backend
uv run pytest tests/test_api_automation_*.py -q

cd D:\project\test_project\apps\frontend
npx biome check src/lib/api-client.ts src/components/ai-testing/api-automation tests/api-automation-ai-repair-contract.test.mjs
npm run build
```

Expected: API automation backend tests and frontend build pass. Do not fix unrelated pre-existing failures.

- [ ] **Step 7: Commit the verification slice**

```powershell
cd D:\project\test_project
git add apps/backend/app/services/api_automation/self_healing.py apps/backend/app/services/api_automation/artifact_storage.py apps/backend/app/services/operation_log_service.py apps/backend/tests/test_api_automation_ai_repair_e2e.py apps/backend/tests/test_agent_architecture_boundaries.py apps/frontend/tests/api-automation-ai-repair-contract.test.mjs
git commit -m "test: verify api automation ai repair flow"
```

---

## Task 10: Final consistency review and execution handoff

**Files:**
- Reference: `docs/superpowers/specs/2026-07-23-api-automation-ai-repair-design.md`
- Modify only if an approved clarification is needed: `docs/superpowers/specs/2026-07-23-api-automation-ai-repair-design.md`
- Plan: `docs/superpowers/plans/2026-07-23-api-automation-ai-repair.md`

- [ ] **Step 1: Scan for placeholders and whitespace errors**

```powershell
cd D:\project\test_project
$patterns = @('T'+'BD', 'TO'+'DO', 'implement'+' later', 'add'+' validation', 'handle'+' edge cases', 'write tests for'+' the above', 'Similar to'+' Task'); rtk rg -n ($patterns -join '|') docs/superpowers/plans/2026-07-23-api-automation-ai-repair.md
rtk git diff --check -- docs/superpowers/specs/2026-07-23-api-automation-ai-repair-design.md docs/superpowers/plans/2026-07-23-api-automation-ai-repair.md
```

Expected: no placeholder matches and no whitespace errors.

- [ ] **Step 2: Verify spec coverage**

Confirm explicit tasks exist for manual trigger, human approval, whole-suite temporary edits, business-code prohibition, database-owned case synchronization, full pre-approval regression, optional user context, continuous repair history, Revision rollback, redaction, command restrictions, no speculative repairs, audit logs, and frontend repair history.

- [ ] **Step 3: Verify type and route consistency**

Check that Session/Attempt statuses, `parent_run_id`, `source_repair_attempt_id`, API route names, Pydantic fields, TypeScript fields, and `available_actions` are spelled identically across tasks.

- [ ] **Step 4: Handoff execution mode**

Do not edit implementation files in the planning turn. Offer:

1. subagent-driven execution with per-task review checkpoints;
2. inline execution in this session using the plan task-by-task.

---

## Execution Notes

- Start with Task 1; do not begin Agent implementation until persistence tests pass.
- Mock model, subprocess, and external API calls in unit/contract tests. Real model/API verification requires an explicitly configured non-production integration environment.
- Inspect `git status --short` before implementation and do not revert, stage, or overwrite unrelated user changes.
- Reuse `api_test_generation` model selection in the first implementation; do not add a separate capability setting without a new product decision.
- Commit commands are plan checkpoints, not authorization to commit during this planning turn. Do not create commits unless the user explicitly requests them.
