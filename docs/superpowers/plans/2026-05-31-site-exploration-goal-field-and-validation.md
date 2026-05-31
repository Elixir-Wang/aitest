# Site Exploration Goal Field And Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or an equivalent task-by-task workflow. Keep each task small, run focused tests after backend changes, and do not preserve `description` as an exploration-run goal alias.

**Goal:** Replace exploration-run `description` with explicit `goal` and `notes` fields, propagate `goal` through APIs, frontend, YAML/report artifacts, and add first-version goal-validation output so run completion can distinguish page collection from goal verification.

**Primary Spec:** `docs/superpowers/specs/2026-05-31-site-exploration-goal-field-and-validation-spec.md`

---

## File Map

- Modify: `apps/backend/app/seed/init_db.py`
  - Rebuild or migrate `exploration_runs` from `description` to `goal` and `notes`.
- Modify: `apps/backend/app/schemas/exploration.py`
  - Replace exploration-run `description` fields with `goal`.
  - Add `notes`.
- Modify: `apps/backend/app/repositories/exploration_repo.py`
  - Replace SQL reads/writes for `description` with `goal`.
  - Add `notes` handling.
- Modify: `apps/backend/app/presentation/serializers.py`
  - Serialize `goal` and `notes`.
  - Stop serializing exploration-run `description`.
- Modify: `apps/backend/app/services/exploration_service.py`
  - Read/write `goal`.
  - Return goal-validation data in detail/report flows if needed.
- Modify: `apps/backend/app/services/site_exploration_orchestrator.py`
  - Pass `goal` into run artifacts and validation.
  - Persist `checks/goal-validation.yaml`.
  - Use goal-validation status in terminal run status.
- Modify: `apps/backend/app/services/exploration_artifact_service.py`
  - Write/read `goal` in `run.yaml`, `summary.yaml`, and report markdown.
  - Load `checks/goal-validation.yaml`.
- Modify: `apps/backend/tests/test_exploration_service.py`
  - Cover create/update/detail/report with `goal`.
  - Cover no `description` response.
- Modify: `apps/backend/tests/test_site_exploration_orchestrator.py`
  - Cover artifact `goal`, goal-validation output, and status impact.
- Modify: `apps/backend/tests/test_exploration_artifact_service.py`
  - Cover report/summary goal-validation rendering.
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
  - Replace `description` with `goal`.
  - Add `notes`.
  - Add target validation summary display if detail API returns it.
- Modify: `apps/frontend/src/components/ai-testing/exploration-workspace.tsx`
  - Replace create/edit payload `description` with `goal`.
  - Add `notes` where applicable.
- Modify: any frontend DTO/shared API types that include exploration-run `description`.

---

## Design Decisions

- Exploration-run `description` is removed, not kept as a compatibility alias.
- Historical `description` values migrate into `goal`.
- `notes` is optional user-facing text and never affects runner behavior.
- `goal` is an execution field. Empty `goal` means no target validation is required.
- First-version goal validation only recognizes the current target pattern:
  - article pages
  - links/buttons
  - must not navigate to login/auth/permission/captcha pages
- Unsafe buttons are not clicked; they produce `unverified` items.
- Buttons named `BUTTON` or empty names cannot silently pass.
- Page collection completion and goal validation completion are separate concepts.

---

## Task 1: Backend Schema And Migration

**Files:**
- `apps/backend/app/seed/init_db.py`
- `apps/backend/app/schemas/exploration.py`

- [ ] Update `exploration_runs` table definition:

```sql
goal TEXT NOT NULL DEFAULT '',
notes TEXT NOT NULL DEFAULT ''
```

- [ ] Remove exploration-run `description` from the canonical table definition.
- [ ] Add migration/backfill logic:
  - If old table has `description`, copy it to `goal`.
  - Set `notes` to `''`.
  - Preserve all existing rows, timestamps, status, limits, and artifact roots.
- [ ] Update Pydantic schemas:
  - `ExplorationRunCreateIn.goal: str = ""`
  - `ExplorationRunCreateIn.notes: str = ""`
  - `ExplorationRunUpdateIn.goal: str | None = None`
  - `ExplorationRunUpdateIn.notes: str | None = None`
  - `ExplorationRunOut.goal: str`
  - `ExplorationRunOut.notes: str`
- [ ] Remove exploration-run `description` from these schemas.
- [ ] If Pydantic currently ignores unknown fields, set behavior so create/update reject `description`.

### Verification

Run:

```bash
cd apps/backend
./.venv/bin/python -m pytest tests/test_exploration_service.py -q
```

Expected at this step: failing tests should only be from repository/service still using `description`.

---

## Task 2: Repository And Serializer Rename

**Files:**
- `apps/backend/app/repositories/exploration_repo.py`
- `apps/backend/app/presentation/serializers.py`

- [ ] Replace INSERT columns:
  - remove `description`
  - add `goal`, `notes`
- [ ] Replace UPDATE handling:
  - `goal`
  - `notes`
- [ ] Replace list/detail row mapping expectations.
- [ ] Serializer returns:

```python
"goal": row["goal"],
"notes": row["notes"],
```

- [ ] Serializer must not return exploration-run `description`.

### Tests To Add

In `apps/backend/tests/test_exploration_service.py`:

- [ ] `test_create_run_persists_goal_and_notes`
- [ ] `test_update_run_persists_goal_and_notes`
- [ ] `test_run_response_does_not_include_description`
- [ ] `test_migrates_legacy_description_to_goal`

### Verification

Run:

```bash
cd apps/backend
./.venv/bin/python -m pytest tests/test_exploration_service.py -q
```

---

## Task 3: Backend Service API Contract

**Files:**
- `apps/backend/app/services/exploration_service.py`
- `apps/backend/app/api/v1/exploration.py` if request validation behavior is controlled there.

- [ ] Replace all exploration-run target reads:

```python
run["description"]
```

with:

```python
run["goal"]
```

- [ ] Create/update service accepts `payload.goal`.
- [ ] Create/update service accepts `payload.notes`.
- [ ] Invalid `description` in request returns 400 or schema validation error.
- [ ] `get_project_run_detail` includes `goal` and `notes` via serializer.
- [ ] `get_project_run_report` uses `goal` through artifact bundle/report generation.

### Verification

Run:

```bash
cd apps/backend
./.venv/bin/python -m pytest tests/test_exploration_service.py tests/test_exploration_api.py -q
```

---

## Task 4: Artifact Goal Contract

**Files:**
- `apps/backend/app/services/exploration_artifact_service.py`
- `apps/backend/app/services/site_exploration_orchestrator.py`

- [ ] `run.yaml` writes:

```yaml
run:
  goal: ...
  notes: ...
```

- [ ] `summary.yaml` writes:

```yaml
goal: ...
goal_validation:
  status: pending
  summary: ''
```

when no validation has run.

- [ ] Report markdown renders:

```md
- 探索目标：{goal}
```

- [ ] Remove run-level `description` from newly generated YAML and reports.
- [ ] Readers tolerate old artifacts where only `description` exists, but newly generated bundles expose `goal`.

### Tests To Add

- [ ] Artifact generation writes `goal`.
- [ ] Report includes `探索目标`.
- [ ] New artifacts do not include run-level `description`.

### Verification

Run:

```bash
cd apps/backend
./.venv/bin/python -m pytest tests/test_exploration_artifact_service.py tests/test_site_exploration_orchestrator.py -q
```

---

## Task 5: Goal Validation Artifact Reader/Writer

**Files:**
- `apps/backend/app/services/exploration_artifact_service.py`
- `apps/backend/app/services/exploration_service.py`
- `apps/backend/app/schemas/exploration.py`

- [ ] Add artifact path:

```text
checks/goal-validation.yaml
```

- [ ] Add helper to build default validation result:

```yaml
goal: ''
status: skipped
summary: 未设置探索目标。
stats:
  page_count: 0
  link_checked_count: 0
  button_checked_count: 0
  failed_count: 0
  unverified_count: 0
items: []
```

- [ ] If `goal` is non-empty and no validation has run, status must be `pending`.
- [ ] Load validation artifact into the run artifact bundle.
- [ ] Expose validation summary in detail API, either:
  - inside `run.goal_validation`, or
  - as top-level `goal_validation`.

Choose one shape and keep frontend/report aligned.

### Suggested DTO

```python
class ExplorationGoalValidationOut(BaseModel):
    goal: str = ""
    status: str = "pending"
    summary: str = ""
    stats: dict = {}
    items: list[dict] = []
```

### Verification

Run:

```bash
cd apps/backend
./.venv/bin/python -m pytest tests/test_exploration_service.py tests/test_exploration_artifact_service.py -q
```

---

## Task 6: First-Version Goal Validator

**Files:**
- `apps/backend/app/services/site_exploration_orchestrator.py`
- Optional new file: `apps/backend/app/services/exploration_goal_validation_service.py`

- [ ] Add a small validator module rather than embedding all logic in the orchestrator.
- [ ] Recognize the target:

```text
每篇文章内容的超链接和按钮，不能跳转到登陆页面
```

using keyword matching:

- `每篇文章`
- `超链接` or `链接`
- `按钮`
- `不能跳转到登陆页面` or `不能跳转到登录页面`

- [ ] For unsupported non-empty goals, write `status: pending` or `skipped` with clear summary. Use `pending` if the system should not claim success.
- [ ] For links:
  - inspect/visit same-domain hrefs where safe.
  - mark login/auth/permission/captcha targets as failed.
- [ ] For buttons:
  - skip dangerous labels.
  - click safe buttons only.
  - record before/after URL and login-page detection.
  - mark empty or `BUTTON` names as `unverified`.
- [ ] Persist `checks/goal-validation.yaml`.

### Login Detection

Fail when any of these are true:

- URL contains `login`, `signin`, `sign-in`, `auth`.
- Title/body contains `登录`, `登陆`, `Login`, `Sign in`.
- Body contains login form signals like `用户名`, `密码`, `验证码`.
- Page status indicates 401/403/permission denied.

### Verification

Add focused unit tests for the validator:

- [ ] link to login -> failed
- [ ] safe same-domain link -> passed
- [ ] `BUTTON` name -> unverified
- [ ] unsupported goal -> pending/skipped according to chosen rule

Run:

```bash
cd apps/backend
./.venv/bin/python -m pytest tests/test_site_exploration_orchestrator.py -q
```

---

## Task 7: Completion Status Integration

**Files:**
- `apps/backend/app/services/site_exploration_orchestrator.py`
- `apps/backend/app/services/exploration_service.py`

- [ ] Update terminal status rules:

| Collection | Goal validation | Run status |
| --- | --- | --- |
| completed | passed | completed |
| completed | partial | partial |
| completed | failed | blocked or partial |
| completed | pending | partial |
| completed | skipped | completed only when goal is empty |
| error | any | blocked |

- [ ] If `goal` is non-empty and validation did not run, do not mark run as clean `completed`.
- [ ] Update `result_summary` to mention goal validation:
  - passed
  - partial/unverified
  - failed
  - pending

### Verification

Tests:

- [ ] non-empty goal + no validation -> partial
- [ ] goal validation passed -> completed
- [ ] goal validation failed -> blocked/partial as selected
- [ ] empty goal + skipped validation -> completed

Run:

```bash
cd apps/backend
./.venv/bin/python -m pytest tests/test_site_exploration_orchestrator.py tests/test_exploration_service.py -q
```

---

## Task 8: Frontend DTO And Forms

**Files:**
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- `apps/frontend/src/components/ai-testing/exploration-workspace.tsx`
- Any shared frontend API type files that define exploration runs.

- [ ] Replace `description` with `goal` in `ExplorationRun`.
- [ ] Add `notes`.
- [ ] Replace form state:

```ts
description -> goal
```

- [ ] Add `notes` field only if there is an existing appropriate place in the form. Keep it compact.
- [ ] Create payloads with `goal`, not `description`.
- [ ] Show plan row:

```text
探索目标    run.goal || "-"
备注        run.notes || "-"
```

- [ ] Search frontend for exploration-run `description` and remove all goal usages.

### Verification

Run:

```bash
cd apps/frontend
npm run lint
npm run build
```

---

## Task 9: Frontend Goal Validation Summary

**Files:**
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Add `goal_validation` to the detail DTO.
- [ ] Add a compact “目标验证” section in 探索概览.
- [ ] Display:
  - goal
  - status
  - summary
  - link/button stats if present
  - failed/unverified counts
- [ ] Use status styles:
  - `passed`: green
  - `partial`: amber
  - `failed`: red
  - `pending`: muted/blue
  - `skipped`: muted
- [ ] Do not show target as achieved when status is `pending`.

### Verification

Run:

```bash
cd apps/frontend
npm run lint
npm run build
```

Manual route:

```text
/projects/{projectId}/exploration/{runId}
```

Check:

- goal is visible.
- goal validation status is visible.
- empty validation does not look like success.

---

## Task 10: Report Goal Validation Section

**Files:**
- `apps/backend/app/services/exploration_artifact_service.py`
- `apps/backend/tests/test_exploration_artifact_service.py`

- [ ] Add report section:

```md
## 目标验证结果

- 目标：...
- 结论：...
- 链接验证：...
- 按钮验证：...
- 失败项：...
- 未验证项：...
```

- [ ] If goal is non-empty but validation is pending, include:

```text
目标验证未执行，当前 completed/partial 状态不能证明探索目标已达成。
```

- [ ] Do not render an empty template as if it were a successful report.

### Verification

Run:

```bash
cd apps/backend
./.venv/bin/python -m pytest tests/test_exploration_artifact_service.py tests/test_exploration_service.py -q
```

---

## Task 11: Search And Cleanup

**Files:**
- Whole repository.

- [ ] Run:

```bash
rg -n "description" apps/backend/app apps/backend/tests apps/frontend/src
```

- [ ] Classify each hit:
  - Other business object description: keep.
  - Exploration-run goal: remove/rename.
  - Artifact compatibility reader: keep only with explicit legacy comment.
- [ ] Run:

```bash
rg -n "run\\[\"description\"\\]|\\.description|description:" apps/backend/app apps/frontend/src
```

- [ ] Ensure no exploration-run goal logic reads or writes `description`.

---

## Task 12: Full Verification

### Backend

Run:

```bash
cd apps/backend
./.venv/bin/python -m pytest tests/test_exploration_service.py tests/test_exploration_artifact_service.py tests/test_site_exploration_orchestrator.py tests/test_exploration_api.py -q
```

### Frontend

Run:

```bash
cd apps/frontend
npm run lint
npm run build
```

### Manual Checks

1. Create a new exploration run with:

```text
scope = 探索全部文章页面
goal = 每篇文章内容的超链接和按钮，不能跳转到登陆页面
```

2. Confirm API response includes `goal`, not `description`.
3. Start exploration.
4. Confirm `run.yaml` contains `goal`.
5. Confirm `summary.yaml` contains `goal_validation`.
6. Confirm `checks/goal-validation.yaml` exists when validation runs.
7. Confirm overview target validation section is visible.
8. Confirm report target validation section is visible.
9. Confirm a non-empty goal without validation cannot be interpreted as clean target success.

---

## Rollback Notes

- If migration fails, restore database backup before table rebuild.
- If goal validator is unstable, keep `goal` field rename and set validation status to `pending`; do not revert to `description`.
- Do not reintroduce `description` as a response alias for exploration runs.

