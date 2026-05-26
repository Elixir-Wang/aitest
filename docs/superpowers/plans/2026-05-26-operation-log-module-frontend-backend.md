# Operation Log Module Frontend/Backend Plan

> **For agentic workers:** implement task-by-task. Do not skip verification. Keep changes additive and reuse existing API/service/repository patterns.

**Goal:** Implement the 日志模块 from PRD `00-23`, including backend persistence/query/write helpers and frontend system/project log pages.

**Architecture:** Add `operation_log` as a shared infrastructure module. Business services call `operation_log_service`; API pages read logs through dedicated endpoints. SQLite stores structured summaries; filesystem artifacts remain linked by path.

**Tech Stack:** FastAPI, SQLite, Pydantic, pytest/unittest, Next.js App Router, React, shadcn/ui, Biome.

---

## References

- Spec: `docs/superpowers/specs/2026-05-26-operation-log-module-frontend-backend-spec.md`
- PRD: `docs/00-产品文档/00-23-AI测试系统-日志模块PRD.md`
- Backend architecture: `docs/03-后端架构与数据/03-01-AI测试系统-后端架构PRD.md`
- Data model: `docs/03-后端架构与数据/03-02-AI测试系统-数据模型PRD.md`
- Frontend plan: `docs/05-前端方案/05-01-AI测试系统-前端总体方案PRD.md`

---

## Task 1: Add Backend Data Model

**Files:**

- Modify: `apps/backend/app/seed/init_db.py`
- Create: `apps/backend/app/schemas/operation_log.py`
- Create: `apps/backend/app/repositories/operation_log_repo.py`
- Create: `apps/backend/tests/test_operation_log_service.py`

- [ ] Add `operation_logs` table with indexes from the Spec.
- [ ] Add `operation_log_retention_policy` table with a default row.
- [ ] Create Pydantic schemas for list item, detail, create payload, query filters, retention policy, cleanup result.
- [ ] Create repository helpers:
  - `create_log`
  - `list_logs`
  - `get_log`
  - `get_retention_policy`
  - `update_retention_policy`
  - `cleanup_logs`
- [ ] Add tests for table initialization and repository filter behavior.

Verification:

```bash
cd apps/backend
python -m pytest tests/test_operation_log_service.py -q
```

---

## Task 2: Add Log Service And Desensitization

**Files:**

- Create: `apps/backend/app/services/operation_log_service.py`
- Modify: `apps/backend/tests/test_operation_log_service.py`

- [ ] Implement `record_success`.
- [ ] Implement `record_failure`.
- [ ] Implement `record_change`.
- [ ] Implement `record_task_event`.
- [ ] Implement `record_agent_run`.
- [ ] Implement recursive desensitization for dict/list/string values.
- [ ] Ensure sensitive keys are masked: password, token, api_key, secret, authorization, cookie, captcha, verification_code, access_key.
- [ ] Make ordinary log write failure non-blocking.
- [ ] Add tests for masking nested dicts and strings.
- [ ] Add tests proving normal write failure does not break the caller contract.

Verification:

```bash
cd apps/backend
python -m pytest tests/test_operation_log_service.py -q
```

---

## Task 3: Add Backend APIs

**Files:**

- Create: `apps/backend/app/api/v1/operation_logs.py`
- Modify: `apps/backend/app/api/v1/__init__.py`
- Modify: `apps/backend/app/main.py` or existing router registration file
- Create: `apps/backend/tests/test_operation_log_api.py`

- [ ] Add `GET /api/v1/operation-logs`.
- [ ] Add `GET /api/v1/operation-logs/{log_id}`.
- [ ] Add `GET /api/v1/projects/{project_id}/operation-logs` or mount equivalent project route following existing conventions.
- [ ] Add `GET /api/v1/operation-logs/export`.
- [ ] Add `GET /api/v1/operation-logs/retention-policy`.
- [ ] Add `PUT /api/v1/operation-logs/retention-policy`.
- [ ] Add `POST /api/v1/operation-logs/cleanup`.
- [ ] Enforce admin-only access for global logs/export/retention/cleanup.
- [ ] Enforce project authorization for project logs and detail.
- [ ] Add API tests for admin, test engineer, visitor, and unauthorized project access.

Verification:

```bash
cd apps/backend
python -m pytest tests/test_operation_log_api.py -q
```

---

## Task 4: Wire First-Batch Business Events

**Files:**

- Modify: `apps/backend/app/services/auth_service.py`
- Modify: `apps/backend/app/services/project_service.py`
- Modify: `apps/backend/app/services/document_service.py`
- Modify: `apps/backend/app/services/requirement_merge_service.py` if merge logic is already separated
- Modify: `apps/backend/app/services/model_service.py`
- Modify: `apps/backend/app/services/environment_service.py` or system setting service if present
- Modify related tests

- [ ] Record login success/failure and logout if logout exists.
- [ ] Record project create/update/delete/archive/restore.
- [ ] Record requirement create, append/upload file, delete.
- [ ] Record merge start, preview generation, confirm, cancel.
- [ ] Record model provider create/update/delete/connectivity check.
- [ ] Record system setting update/connectivity check.
- [ ] Record task create/start/success/failed/cancel/retry where task events already exist.
- [ ] Add assertions in existing tests that logs are created for representative actions.

Verification:

```bash
cd apps/backend
python -m pytest tests -q
```

---

## Task 5: Add Frontend API Client Types

**Files:**

- Modify or create API helpers under `apps/frontend/src/lib` following current project conventions.
- Create component-local types if there is no central API type location.

- [ ] Add `OperationLogListItem` type.
- [ ] Add `OperationLogDetail` type.
- [ ] Add filter/query type.
- [ ] Add retention policy type.
- [ ] Add fetch helpers for global logs, project logs, detail, export, retention, cleanup.
- [ ] Add enum-to-Chinese label helpers for module/action/result/source.

Verification:

```bash
cd apps/frontend
npm run lint
```

If no lint script exists, run the existing project validation command from `package.json`.

---

## Task 6: Build Shared Log UI Components

**Files:**

- Create: `apps/frontend/src/components/ai-testing/operation-logs/operation-log-table.tsx`
- Create: `apps/frontend/src/components/ai-testing/operation-logs/operation-log-filters.tsx`
- Create: `apps/frontend/src/components/ai-testing/operation-logs/operation-log-detail-drawer.tsx`
- Create: `apps/frontend/src/components/ai-testing/operation-logs/operation-log-retention-dialog.tsx`

- [ ] Build dense table with stable columns: time, module, action, object, actor, result, summary, operation.
- [ ] Build filter bar: date range, module, action, object type, actor, result, project when global.
- [ ] Build detail drawer showing base info, change diff summary, failure reason, task/artifact links, request info.
- [ ] Build retention policy dialog for admin-only use.
- [ ] Keep empty/loading/error states explicit and consistent with existing AI testing pages.

Verification:

```bash
cd apps/frontend
npm run lint
```

---

## Task 7: Add System And Project Pages

**Files:**

- Create: `apps/frontend/src/app/(main)/settings/logs/page.tsx`
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/logs/page.tsx`
- Modify navigation/sidebar/project detail entry files as needed.

- [ ] Add system logs page using global query endpoint.
- [ ] Add project logs page using project-scoped endpoint.
- [ ] Add settings navigation entry for “日志”.
- [ ] Add project detail module entry for “项目日志”.
- [ ] Hide export/retention/cleanup actions for non-admin users.
- [ ] Handle 403 with existing unauthorized page or message pattern.

Verification:

```bash
cd apps/frontend
npm run lint
```

---

## Task 8: End-To-End Verification

- [ ] Start backend.
- [ ] Start frontend.
- [ ] Create a project, edit it, delete a temporary project.
- [ ] Create or upload a requirement and run a representative merge action if available.
- [ ] Change a safe system/model setting in a test environment.
- [ ] Open system logs and confirm entries appear.
- [ ] Open a project log page and confirm only that project appears.
- [ ] Confirm sensitive values are masked in detail.
- [ ] Confirm unauthorized user cannot open global logs.

Verification:

```bash
cd apps/backend
python -m pytest tests -q
```

```bash
cd apps/frontend
npm run lint
```

Use Browser to inspect the local frontend pages after significant frontend changes.

---

## Rollout Notes

- Ship backend schema/service/API first, with tests.
- Wire project and requirement logs before lower-priority modules.
- Keep second-batch modules behind incremental follow-up tasks.
- Do not block existing business actions on ordinary log write failure.
- Do not persist full model prompts, full Runner output, or full document Markdown in `operation_logs`.
