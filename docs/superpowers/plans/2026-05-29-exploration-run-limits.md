# Exploration Run Limits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `max_pages = 50`, `max_actions = 1000`, and `timeout_minutes = 120` to new exploration tasks, persist them through the backend, and show the same values in the exploration plan.

**Architecture:** Treat the three execution-boundary values as task-level settings on `exploration_runs`, not as system configuration. The frontend creation/edit forms own the user-visible defaults, the backend validates and stores them, and the detail page reads the saved values instead of rendering hard-coded “系统默认” text.

**Tech Stack:** Next.js/React frontend, FastAPI/Pydantic backend, SQLite schema bootstrap/migration, Python unittest, frontend lint/build checks, browser smoke test.

---

## File Structure

- Modify: `apps/backend/app/seed/init_db.py`
  - Add `max_pages`, `max_actions`, `timeout_minutes` columns to `exploration_runs`.
  - Add `_ensure_column` calls for existing SQLite databases.
  - Include the columns in the table rebuild path.
- Modify: `apps/backend/app/schemas/exploration.py`
  - Add the three fields to `ExplorationRunOut`, `ExplorationRunCreateIn`, and `ExplorationRunUpdateIn`.
  - Use defaults: `50`, `1000`, `120`.
- Modify: `apps/backend/app/repositories/exploration_repo.py`
  - Insert the three values when creating exploration runs.
- Modify: `apps/backend/app/presentation/serializers.py`
  - Return the persisted values to the frontend.
- Modify: `apps/backend/app/services/exploration_service.py`
  - Validate values on create/update.
  - Store values and include them in operation-log snapshots.
  - Keep planned module generation unchanged except it now has access to the saved limits through `run`.
- Modify: `apps/backend/tests/test_exploration_service.py`
  - Cover default creation values.
  - Cover custom creation values.
  - Cover update values.
  - Cover invalid non-positive values.
- Modify: `apps/frontend/src/components/ai-testing/exploration-workspace.tsx`
  - Add the three fields to `ExplorationRun` and `ExplorationForm`.
  - Put them into the new/edit exploration dialog under an “执行边界” block.
  - Use the frontend “more” defaults: `50`, `1000`, `120`.
  - Remove any “系统配置” choice/copy from this dialog if present.
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
  - Add the three fields to detail typing and edit form typing.
  - Show saved values in `探索计划 -> 执行边界`.
  - Remove “系统默认” wording.
  - Send changed values on edit.

---

### Task 1: Backend Contract And Storage

**Files:**
- Modify: `apps/backend/app/seed/init_db.py`
- Modify: `apps/backend/app/schemas/exploration.py`
- Modify: `apps/backend/app/repositories/exploration_repo.py`
- Modify: `apps/backend/app/presentation/serializers.py`
- Modify: `apps/backend/app/services/exploration_service.py`

- [ ] **Step 1: Write backend service tests first**

Add tests to `apps/backend/tests/test_exploration_service.py`:

```python
    def test_create_run_uses_default_execution_limits(self):
        with isolated_exploration_store():
            seed_project_environment()

            run = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(environment_id="env-1", title="后台探索"),
                admin_actor(),
            )

            self.assertEqual(run["max_pages"], 50)
            self.assertEqual(run["max_actions"], 1000)
            self.assertEqual(run["timeout_minutes"], 120)

    def test_create_run_persists_custom_execution_limits(self):
        with isolated_exploration_store():
            seed_project_environment()

            run = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(
                    environment_id="env-1",
                    title="后台探索",
                    max_pages=25,
                    max_actions=300,
                    timeout_minutes=45,
                ),
                admin_actor(),
            )

            self.assertEqual(run["max_pages"], 25)
            self.assertEqual(run["max_actions"], 300)
            self.assertEqual(run["timeout_minutes"], 45)

    def test_update_run_persists_execution_limits(self):
        with isolated_exploration_store():
            seed_project_environment()
            created = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(environment_id="env-1", title="后台探索"),
                admin_actor(),
            )

            updated = exploration_service.update_project_run(
                "project-1",
                created["id"],
                ExplorationRunUpdateIn(max_pages=80, max_actions=1500, timeout_minutes=180),
                admin_actor(),
            )

            self.assertEqual(updated["max_pages"], 80)
            self.assertEqual(updated["max_actions"], 1500)
            self.assertEqual(updated["timeout_minutes"], 180)

    def test_create_run_rejects_invalid_execution_limits(self):
        with isolated_exploration_store():
            seed_project_environment()

            with self.assertRaises(Exception) as context:
                exploration_service.create_project_run(
                    "project-1",
                    ExplorationRunCreateIn(
                        environment_id="env-1",
                        title="后台探索",
                        max_pages=0,
                        max_actions=1000,
                        timeout_minutes=120,
                    ),
                    admin_actor(),
                )

            self.assertEqual(context.exception.status_code, 400)
            self.assertEqual(context.exception.detail["code"], "INVALID_EXPLORATION_LIMIT")
```

- [ ] **Step 2: Run tests and confirm red**

Run:

```powershell
python -m unittest apps.backend.tests.test_exploration_service
```

Expected: FAIL because schema/output fields do not exist yet.

- [ ] **Step 3: Add schema fields**

In `apps/backend/app/schemas/exploration.py`, add:

```python
    max_pages: int = 50
    max_actions: int = 1000
    timeout_minutes: int = 120
```

to `ExplorationRunOut` after `description`, to `ExplorationRunCreateIn` after `description`, and to `ExplorationRunUpdateIn` as nullable fields:

```python
    max_pages: int | None = None
    max_actions: int | None = None
    timeout_minutes: int | None = None
```

- [ ] **Step 4: Add SQLite columns and migration guards**

In `apps/backend/app/seed/init_db.py`, extend `exploration_runs` creation and rebuild schema with:

```sql
max_pages INTEGER NOT NULL DEFAULT 50,
max_actions INTEGER NOT NULL DEFAULT 1000,
timeout_minutes INTEGER NOT NULL DEFAULT 120,
```

Add migration guards near the existing `exploration_runs` `_ensure_column` calls:

```python
        _ensure_column(db, "exploration_runs", "max_pages", "INTEGER NOT NULL DEFAULT 50")
        _ensure_column(db, "exploration_runs", "max_actions", "INTEGER NOT NULL DEFAULT 1000")
        _ensure_column(db, "exploration_runs", "timeout_minutes", "INTEGER NOT NULL DEFAULT 120")
```

Also include the columns in the `exploration_runs_new` `INSERT OR IGNORE` column list and `SELECT` list so existing rebuilds preserve values.

- [ ] **Step 5: Store and serialize values**

Update `apps/backend/app/repositories/exploration_repo.py` `create(...)` signature to accept:

```python
    max_pages: int,
    max_actions: int,
    timeout_minutes: int,
```

Add those columns to the insert statement and values tuple.

Update `apps/backend/app/presentation/serializers.py` `serialize_exploration_run(...)`:

```python
        "max_pages": row["max_pages"] if "max_pages" in row.keys() else 50,
        "max_actions": row["max_actions"] if "max_actions" in row.keys() else 1000,
        "timeout_minutes": row["timeout_minutes"] if "timeout_minutes" in row.keys() else 120,
```

- [ ] **Step 6: Validate in service layer**

In `apps/backend/app/services/exploration_service.py`, add:

```python
def _validate_execution_limits(*, max_pages: int | None, max_actions: int | None, timeout_minutes: int | None) -> None:
    values = {
        "max_pages": max_pages,
        "max_actions": max_actions,
        "timeout_minutes": timeout_minutes,
    }
    if any(value is not None and value < 1 for value in values.values()):
        raise api_error(400, "INVALID_EXPLORATION_LIMIT", "探索执行边界必须大于 0。")
```

Call it in `create_project_run(...)` before `exploration_repo.create(...)`, and pass:

```python
            max_pages=payload.max_pages,
            max_actions=payload.max_actions,
            timeout_minutes=payload.timeout_minutes,
```

In `update_project_run(...)`, call validation with `updates.get(...)` and add these keys to `_build_update_assignments(...)` field map.

Add the three fields to `_run_snapshot(...)`.

- [ ] **Step 7: Run backend tests and confirm green**

Run:

```powershell
python -m unittest apps.backend.tests.test_exploration_service
```

Expected: PASS.

---

### Task 2: Frontend Create/Edit Forms

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/exploration-workspace.tsx`
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] **Step 1: Add frontend types and defaults**

In both files, add to `ExplorationRun`:

```ts
  max_pages: number;
  max_actions: number;
  timeout_minutes: number;
```

Add to `ExplorationForm`:

```ts
  maxPages: string;
  maxActions: string;
  timeoutMinutes: string;
```

Set `emptyExplorationForm` defaults:

```ts
  maxPages: "50",
  maxActions: "1000",
  timeoutMinutes: "120",
```

- [ ] **Step 2: Populate edit forms from persisted values**

When opening edit dialogs, set:

```ts
      maxPages: String(run.max_pages ?? 50),
      maxActions: String(run.max_actions ?? 1000),
      timeoutMinutes: String(run.timeout_minutes ?? 120),
```

- [ ] **Step 3: Send values in create/update payloads**

Add a local parser helper in each file:

```ts
function parsePositiveInteger(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}
```

Before saving, compute:

```ts
    const maxPages = parsePositiveInteger(explorationForm.maxPages);
    const maxActions = parsePositiveInteger(explorationForm.maxActions);
    const timeoutMinutes = parsePositiveInteger(explorationForm.timeoutMinutes);
    if (!maxPages || !maxActions || !timeoutMinutes) {
      toast.error("请填写大于 0 的执行边界");
      return;
    }
```

Add to payload:

```ts
        max_pages: maxPages,
        max_actions: maxActions,
        timeout_minutes: timeoutMinutes,
```

- [ ] **Step 4: Add dialog controls**

In the new/edit exploration dialog, after `探索目标`, add:

```tsx
            <Field className="sm:col-span-2">
              <FieldLabel>执行边界</FieldLabel>
              <div className="grid gap-3 sm:grid-cols-3">
                <Input
                  aria-label="页面上限"
                  inputMode="numeric"
                  min={1}
                  onChange={(event) => setExplorationForm((current) => ({ ...current, maxPages: event.target.value }))}
                  placeholder="50"
                  type="number"
                  value={explorationForm.maxPages}
                />
                <Input
                  aria-label="操作上限"
                  inputMode="numeric"
                  min={1}
                  onChange={(event) =>
                    setExplorationForm((current) => ({ ...current, maxActions: event.target.value }))
                  }
                  placeholder="1000"
                  type="number"
                  value={explorationForm.maxActions}
                />
                <Input
                  aria-label="超时时间（分钟）"
                  inputMode="numeric"
                  min={1}
                  onChange={(event) =>
                    setExplorationForm((current) => ({ ...current, timeoutMinutes: event.target.value }))
                  }
                  placeholder="120"
                  type="number"
                  value={explorationForm.timeoutMinutes}
                />
              </div>
            </Field>
```

Use visible labels/placeholders around the inputs if the existing local style requires label text. Do not add a `系统配置` option, switch, select item, or hint.

- [ ] **Step 5: Update exploration-plan display**

In `ExplorationTaskPanel`, replace:

```tsx
          <InfoRow label="页面上限" value="50 页（系统默认）" />
          <InfoRow label="操作上限" value="1000 次（系统默认）" />
          <InfoRow label="超时时间" value="2 小时（系统默认）" />
```

with:

```tsx
          <InfoRow label="页面上限" value={run ? `${run.max_pages ?? 50} 页` : "-"} />
          <InfoRow label="操作上限" value={run ? `${run.max_actions ?? 1000} 次` : "-"} />
          <InfoRow label="超时时间" value={run ? `${run.timeout_minutes ?? 120} 分钟` : "-"} />
```

- [ ] **Step 6: Run frontend checks**

Run:

```powershell
pnpm --dir apps/frontend lint
pnpm --dir apps/frontend build
```

Expected: both commands pass.

---

### Task 3: Frontend/Backend Integration Verification

**Files:**
- Verify only: running frontend and backend services.

- [ ] **Step 1: Start or restart services**

Use the repo's normal commands. If ports are occupied, inspect and clear stale listeners before relaunching.

- [ ] **Step 2: Create an exploration task from UI**

Open the exploration page, click `新建探索任务`, and confirm the dialog shows:

```text
页面上限: 50
操作上限: 1000
超时时间: 120
```

Confirm there is no `系统配置` option.

- [ ] **Step 3: Save and inspect the API result**

Create the task and confirm the network response contains:

```json
{
  "max_pages": 50,
  "max_actions": 1000,
  "timeout_minutes": 120
}
```

- [ ] **Step 4: Verify exploration plan display**

Open the created task detail page, switch to `探索计划`, and confirm `执行边界` displays:

```text
页面上限 50 页
操作上限 1000 次
超时时间 120 分钟
```

No value should say `系统默认`.

- [ ] **Step 5: Verify custom value round trip**

Edit the task to:

```text
页面上限: 12
操作上限: 34
超时时间: 56
```

Save, refresh the detail page, and confirm the exploration plan displays `12 页`, `34 次`, `56 分钟`.

---

## Self-Review

- Spec coverage: The plan covers new task creation, backend persistence, edit round trip, exploration-plan display, and removal of the system-configuration option/copy.
- Placeholder scan: No task relies on `TBD` or unspecified implementation.
- Type consistency: Backend API uses snake_case (`max_pages`, `max_actions`, `timeout_minutes`); frontend form state uses camelCase strings for input control and converts to snake_case in API payloads.
