# API Automation Batch Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate test cases for up to 100 selected API endpoints through globally bounded five-way concurrency, persist each successful endpoint immediately, report partial success, and allow manual retry of failed endpoints only.

**Architecture:** Keep `api_generation_runs` as the parent task and add endpoint-level items plus attempt history. The existing synchronous FastAPI background entry remains, while an async gather loop uses a process-wide `threading.BoundedSemaphore(5)` so separate event loops and separate parent runs share the same limit. Each endpoint owns one model call and one database transaction; run summaries are derived from item rows.

**Tech Stack:** Python 3.12+, FastAPI, asyncio, threading, SQLite, Pydantic 2, pytest 9, Next.js 16, React 19, TypeScript, Node test runner.

## Global Constraints

- Accept at most 100 endpoint IDs per generation request.
- Execute at most 5 API generation items globally, including across different parent runs.
- Do not automatically retry a failed item.
- Commit all cases for one endpoint atomically as soon as that endpoint succeeds.
- Preserve successful endpoint results when sibling endpoints fail.
- Expose `completed`, `partial_success`, and `failed` parent outcomes.
- “Retry failed items” must not queue completed endpoints or duplicate their cases.
- Do not add Celery, Redis, a message broker, or another dependency.

---

### Task 1: Persist Endpoint Items and Attempt History

**Files:**
- Modify: `apps/backend/app/seed/schema.py:370`
- Modify: `apps/backend/app/seed/seeds.py:1`
- Modify: `apps/backend/app/repositories/api_automation_repo.py:213`
- Modify: `apps/backend/app/schemas/api_automation.py:146`
- Test: `apps/backend/tests/test_api_automation_schema_repo.py`

**Interfaces:**
- Consumes: existing `connect()`, `dumps_json()`, and `api_generation_runs` rows.
- Produces: `create_generation_items(db, run_id: str, endpoint_ids: list[str]) -> None`, `list_generation_items(db, run_id: str) -> list[Row]`, `start_generation_item_attempt(db, item_id: str, attempt_id: str) -> None`, `finish_generation_item_attempt(db, item_id: str, attempt_id: str, *, status: str, generated_case_count: int = 0, error_message: str = "") -> None`, and serialized `ApiGenerationItemOut` fields used by Tasks 2-6.

- [ ] **Step 1: Write failing repository tests**

Add tests that initialize a temporary database, create one generation run with two endpoints, and assert item and attempt persistence:

```python
def test_generation_items_and_attempts_are_persisted(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoints(["apiend-1", "apiend-2"])
    with connect() as db:
        api_automation_repo.create_generation_run(
            db,
            run_id="apigen-1",
            task_id="api_automation_generation:apigen-1",
            project_id="project-1",
            api_environment_id=None,
            endpoint_ids=["apiend-1", "apiend-2"],
            source_test_case_ids=[],
            generation_goal="批量生成",
            options={},
            created_by="u-admin",
        )
        api_automation_repo.create_generation_items(db, "apigen-1", ["apiend-1", "apiend-2"])
        items = api_automation_repo.list_generation_items(db, "apigen-1")
        api_automation_repo.start_generation_item_attempt(db, items[0]["id"], "attempt-1")
        api_automation_repo.finish_generation_item_attempt(
            db,
            items[0]["id"],
            "attempt-1",
            status="completed",
            generated_case_count=3,
        )

    assert [item["endpoint_id"] for item in items] == ["apiend-1", "apiend-2"]
    with connect() as db:
        item = api_automation_repo.find_generation_item(db, items[0]["id"])
        attempts = api_automation_repo.list_generation_item_attempts(db, items[0]["id"])
    assert item["status"] == "completed"
    assert item["attempt_count"] == 1
    assert attempts[0]["id"] == "attempt-1"
```

Also assert that initializing an existing database adds the new tables and nullable `generation_item_id` / `generation_attempt_id` columns without deleting existing `api_test_cases`.

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_schema_repo.py -q
```

Expected: FAIL because generation item repository functions and tables do not exist.

- [ ] **Step 3: Add the tables and output schemas**

Add `api_generation_items` with a unique `(generation_run_id, endpoint_id)` constraint and `api_generation_item_attempts` with a unique `(generation_item_id, attempt_no)` constraint. Add nullable `generation_item_id` and `generation_attempt_id` foreign keys to `api_test_cases`. Extend the parent status check to include `partial_success` for new databases.

Add these Pydantic contracts:

```python
class ApiGenerationAttemptOut(BaseModel):
    id: str
    attempt_no: int
    status: str
    generated_case_count: int
    error_message: str
    started_at: str
    finished_at: str | None = None


class ApiGenerationItemOut(BaseModel):
    id: str
    endpoint_id: str
    method: str
    path: str
    status: str
    attempt_count: int
    generated_case_count: int
    error_message: str
    started_at: str | None = None
    finished_at: str | None = None
    attempts: list[ApiGenerationAttemptOut] = Field(default_factory=list)
```

Extend `ApiGenerationRunOut` with exact integer fields `total_count`, `completed_count`, `success_count`, `failed_count`, `generated_case_count` and `items: list[ApiGenerationItemOut]`.

- [ ] **Step 4: Add narrowly scoped repository functions**

Implement these exact signatures:

- `create_generation_items(db: Connection, run_id: str, endpoint_ids: list[str]) -> None`
- `find_generation_item(db: Connection, item_id: str) -> Row | None`
- `list_generation_items(db: Connection, run_id: str) -> list[Row]`
- `list_failed_generation_items(db: Connection, run_id: str) -> list[Row]`
- `start_generation_item_attempt(db: Connection, item_id: str, attempt_id: str) -> None`
- `finish_generation_item_attempt(db: Connection, item_id: str, attempt_id: str, *, status: str, generated_case_count: int = 0, error_message: str = "") -> None`
- `list_generation_item_attempts(db: Connection, item_id: str) -> list[Row]`

`start_generation_item_attempt` increments `attempt_count`, sets the item and attempt to `running`, and clears the item’s latest error. `finish_generation_item_attempt` updates both rows in the caller’s transaction.

- [ ] **Step 5: Add a safe existing-database migration**

In `seed_system_defaults()`, call `_ensure_api_generation_batch_structure(db)`. It must use `PRAGMA table_info` / `sqlite_master`, create missing child tables and columns, and rebuild `api_generation_runs` only when its original SQL does not contain `partial_success`. Preserve every existing row and run `PRAGMA foreign_key_check` after the rebuild.

- [ ] **Step 6: Run the repository tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_schema_repo.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/backend/app/seed/schema.py apps/backend/app/seed/seeds.py apps/backend/app/repositories/api_automation_repo.py apps/backend/app/schemas/api_automation.py apps/backend/tests/test_api_automation_schema_repo.py
git commit -m "feat: persist API generation items"
```

---

### Task 2: Execute Endpoint Generation with a Global Limit of Five

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py:357`
- Modify: `apps/backend/app/repositories/api_automation_repo.py:337`
- Test: `apps/backend/tests/test_api_automation_generation_agent.py`

**Interfaces:**
- Consumes: Task 1 repository functions and existing `generate_api_test_cases(input_data)`.
- Produces: preserved public `execute_generation_run(run_id: str) -> dict`, internal `_execute_generation_run_async(run_id: str) -> dict`, `_execute_generation_item(run_id: str, item_id: str) -> None`, and immediate case rows associated with item/attempt IDs.

- [ ] **Step 1: Replace the single-endpoint fixture with reusable endpoint seeding**

Add:

```python
def _seed_project_endpoints(endpoint_ids: list[str]) -> None:
    _seed_project()
    with connect() as db:
        for endpoint_id in endpoint_ids:
            api_automation_repo.upsert_endpoint(
                db,
                endpoint_id=endpoint_id,
                project_id="project-1",
                document_id=None,
                method="GET",
                path=f"/{endpoint_id}",
                normalized_path=f"/{endpoint_id}",
                summary=endpoint_id,
                description="",
                tags=[],
                parameters=[],
                request_body={},
                responses={"200": {"description": "ok"}},
                auth={},
                source={"source_type": "manual"},
                created_by=ACTOR["id"],
            )
```

- [ ] **Step 2: Write failing concurrency and partial-success tests**

Use an async fake that counts active calls under a lock. Seed 12 endpoints, fail `apiend-7`, and assert:

```python
assert max_active_calls == 5
assert result["status"] == "partial_success"
assert result["total_count"] == 12
assert result["success_count"] == 11
assert result["failed_count"] == 1
assert len(api_automation_repo.list_api_test_cases(db, "project-1")) == 11
assert calls["apiend-7"] == 1
```

Add a second test where one fake call blocks while another succeeds; query the database before releasing the blocked call and assert the successful endpoint’s case already exists.

- [ ] **Step 3: Run the focused tests to verify failure**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_generation_agent.py -q
```

Expected: FAIL because the service still sends all endpoints in one model call.

- [ ] **Step 4: Create child items with the parent run**

Inside the existing `create_generation_run()`, call:

```python
api_automation_repo.create_generation_items(db, run_id, payload.endpoint_ids)
```

Keep the existing parent run ID, task ID, request payload, and background task route.

- [ ] **Step 5: Implement the process-wide execution slot**

At module scope:

```python
import threading

API_GENERATION_CONCURRENCY = 5
_api_generation_slots = threading.BoundedSemaphore(API_GENERATION_CONCURRENCY)


async def _acquire_generation_slot() -> None:
    await asyncio.to_thread(_api_generation_slots.acquire)
```

Every `_execute_generation_item` acquires this semaphore immediately before the model call and releases it in `finally`. Do not use a module-level `asyncio.Semaphore`, because separate FastAPI background threads can own separate event loops.

- [ ] **Step 6: Implement one model call and one transaction per item**

Use this control flow:

```python
async def _execute_generation_item(run_id: str, item_id: str) -> None:
    attempt_id = f"apiattempt-{secrets.token_hex(8)}"
    with connect() as db:
        api_automation_repo.start_generation_item_attempt(db, item_id, attempt_id)
        input_data = _build_generation_item_input(db, run_id, item_id)

    await _acquire_generation_slot()
    try:
        result = await api_generation_agent_service.generate_api_test_cases(input_data)
    except Exception as exc:
        with connect() as db:
            api_automation_repo.finish_generation_item_attempt(
                db, item_id, attempt_id, status="failed", error_message=_generation_error_message(exc)
            )
        return
    finally:
        _api_generation_slots.release()

    with connect() as db:
        _persist_generation_item_cases(db, run_id, item_id, attempt_id, result)
        api_automation_repo.finish_generation_item_attempt(
            db, item_id, attempt_id, status="completed", generated_case_count=len(result.cases)
        )
```

`_persist_generation_item_cases` must reject a generated case whose `endpoint_id`, request method, or request path does not match the item endpoint before inserting any case. Add `generation_item_id` and `generation_attempt_id` parameters to `create_api_test_case()`.

- [ ] **Step 7: Aggregate the parent outcome after all items settle**

`execute_generation_run()` remains synchronous and calls `asyncio.run(_execute_generation_run_async(run_id))`. The async function uses `asyncio.gather` over queued item IDs. Derive:

```python
status = (
    "completed"
    if success_count == total_count
    else "failed"
    if failed_count == total_count
    else "partial_success"
)
```

Store `summary`, `total_count`, `success_count`, `failed_count`, and `generated_case_count` in `result_summary_json`; set `finished_at` only after all items are terminal.

- [ ] **Step 8: Convert model truncation into the real item error**

`_generation_error_message(exc)` must return `模型输出超出长度限制` when the exception or model metadata identifies `finish_reason=length`. Other errors use their original message. Never feed an `invalid_tool_calls` assistant message back to the model.

- [ ] **Step 9: Run the focused backend tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_generation_agent.py tests/test_api_automation_schema_repo.py -q
```

Expected: PASS, including global concurrency, no automatic retry, partial success, and immediate persistence.

- [ ] **Step 10: Commit**

```powershell
git add apps/backend/app/services/api_automation/service.py apps/backend/app/repositories/api_automation_repo.py apps/backend/tests/test_api_automation_generation_agent.py
git commit -m "feat: batch API case generation by endpoint"
```

---

### Task 3: Expose Run Progress and Retry Failed Items

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py:547`
- Modify: `apps/backend/app/api/v1/api_automation.py:173`
- Modify: `apps/backend/app/schemas/api_automation.py:155`
- Test: `apps/backend/tests/test_api_automation_generation_agent.py`

**Interfaces:**
- Consumes: terminal item state from Task 2.
- Produces: `retry_failed_generation_items(project_id: str, run_id: str, actor) -> dict`, complete `get_generation_run()` output, and `POST /api/v1/projects/{project_id}/api-automation/generation-runs/{run_id}/retry-failed`.

- [ ] **Step 1: Write failing serialization and retry tests**

Create a parent with one completed and two failed items. Assert `get_generation_run()` returns endpoint method/path, all attempts, and exact counters. Then call retry and assert only failed item IDs return to `queued`, the completed item and its cases are unchanged, and the parent becomes `running`.

Add a conflict test:

```python
with pytest.raises(ApiError) as exc_info:
    service.retry_failed_generation_items("project-1", run_id, ACTOR)
assert exc_info.value.status_code == 409
```

The conflict applies while any item is `queued` or `running`, and when no failed item exists.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_generation_agent.py -q
```

Expected: FAIL because retry and item serialization do not exist.

- [ ] **Step 3: Serialize progress from item rows**

Add `_generation_run_counts(items)` and `_serialize_generation_item(db, row)`. `get_generation_run()` must return:

```python
{
    **_serialize_generation_run(row),
    **_generation_run_counts(items),
    "items": [_serialize_generation_item(db, item) for item in items],
    "test_cases": [
        _serialize_api_test_case(case)
        for case in api_automation_repo.list_api_test_cases(db, row["project_id"])
        if case["generation_run_id"] == row["id"]
    ],
}
```

`list_generation_runs()` may omit `attempts` but must include the five counters.

- [ ] **Step 4: Implement failed-only retry**

`retry_failed_generation_items()` must:

1. require admin access and project ownership;
2. reject active runs;
3. reject runs with no failed items;
4. reset only failed items to `queued` without changing `attempt_count`;
5. set parent status to `running`, clear `finished_at`, and preserve previous attempts;
6. return the refreshed parent run.

Add:

```python
@router.post(
    "/api-automation/generation-runs/{run_id}/retry-failed",
    response_model=ApiGenerationRunOut,
)
def retry_failed_api_generation_items(
    project_id: str,
    run_id: str,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    run = service.retry_failed_generation_items(project_id, run_id, actor)
    background_tasks.add_task(service.execute_generation_run, run_id)
    return run
```

- [ ] **Step 5: Update restart recovery**

`recover_interrupted_api_automation_tasks()` must mark active child attempts/items `failed`, preserve completed items, and finalize the parent as `partial_success` or `failed` from the resulting counts. The error message must say the service restarted and the failed items can be retried.

- [ ] **Step 6: Run backend tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_generation_agent.py tests/test_api_automation_scenarios_tasks.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/backend/app/services/api_automation/service.py apps/backend/app/api/v1/api_automation.py apps/backend/app/schemas/api_automation.py apps/backend/tests/test_api_automation_generation_agent.py
git commit -m "feat: retry failed API generation items"
```

---

### Task 4: Publish Accurate Task-Center Progress

**Files:**
- Modify: `apps/backend/app/services/task_service.py:65`
- Test: `apps/backend/tests/test_api_automation_scenarios_tasks.py`

**Interfaces:**
- Consumes: `api_generation_items` state.
- Produces: task-center `status_label` and `summary` strings consumed by the top indicator and task list.

- [ ] **Step 1: Write failing task summary tests**

Seed a running 100-item parent with 45 completed, 3 failed, and 52 queued items. Assert:

```python
assert task["status_label"] == "生成中"
assert task["summary"] == "已完成 48/100，成功 45，失败 3"
```

Then finalize it as partial success and assert:

```python
assert task["status_label"] == "生成完成"
assert task["summary"] == "成功 93，失败 7，共 100"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_scenarios_tasks.py::test_task_service_includes_api_automation_tasks -q
```

Expected: FAIL because the task summary only exposes `error_message`.

- [ ] **Step 3: Add partial-success metadata and aggregate SQL**

Add:

```python
"partial_success": (COMPLETED_GROUP, "生成完成"),
```

Update `_api_automation_generation_tasks()` to left join an item aggregate grouped by `generation_run_id`, then build the summary through:

```python
def _api_generation_task_summary(row) -> str:
    if row["status"] in {"queued", "running"}:
        return f"已完成 {row['completed_count']}/{row['total_count']}，成功 {row['success_count']}，失败 {row['failed_count']}"
    return f"成功 {row['success_count']}，失败 {row['failed_count']}，共 {row['total_count']}"
```

Keep `error_message` as fallback for legacy runs without item rows.

- [ ] **Step 4: Run task tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_scenarios_tasks.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/backend/app/services/task_service.py apps/backend/tests/test_api_automation_scenarios_tasks.py
git commit -m "feat: report API generation progress"
```

---

### Task 5: Show All Endpoint Results and Retry Failures on the API Page

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts:653`
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx:318`
- Modify: `apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs:197`

**Interfaces:**
- Consumes: Task 3 run/item JSON and retry endpoint.
- Produces: typed client API, complete endpoint result log, progress copy, and failed-only retry command.

- [ ] **Step 1: Write failing frontend contract assertions**

Assert that the client type contains run counters, item attempts, and:

```typescript
export function retryFailedApiAutomationGeneration(projectId: string, runId: string)
```

Assert the page contains progress copy, every item’s method/path/status/case count/error, and a `RefreshCw` retry button visible only when `failed_count > 0` and the run is terminal.

- [ ] **Step 2: Run the contract test to verify failure**

Run:

```powershell
cd apps/frontend
node --test tests/api-automation-interface-set-copy-contract.test.mjs
```

Expected: FAIL because run item types and retry UI do not exist.

- [ ] **Step 3: Add exact client types and retry call**

Add `ApiAutomationGenerationAttempt`, `ApiAutomationGenerationItem`, and these fields to `ApiAutomationGenerationRun`:

```typescript
total_count: number;
completed_count: number;
success_count: number;
failed_count: number;
generated_case_count: number;
items: ApiAutomationGenerationItem[];
```

Add:

```typescript
export function retryFailedApiAutomationGeneration(projectId: string, runId: string) {
  return apiRequest<ApiAutomationGenerationRun>(
    `/projects/${projectId}/api-automation/generation-runs/${runId}/retry-failed`,
    { method: "POST" },
  );
}
```

- [ ] **Step 4: Render progress and the complete result log**

In the existing “接口用例” workflow, show a constrained result section when `generationRun` exists. The header copy is:

```typescript
const generationProgressText = API_GENERATION_ACTIVE_STATUSES.has(generationRun.status)
  ? `接口用例生成中：已完成 ${generationRun.completed_count}/${generationRun.total_count}，成功 ${generationRun.success_count}，失败 ${generationRun.failed_count}`
  : `接口用例生成已完成：成功 ${generationRun.success_count}，失败 ${generationRun.failed_count}，共 ${generationRun.total_count}`;
```

Render every item in a table or list with method, path, status, attempt count, generated case count, elapsed time, and full error text. Do not truncate errors without a tooltip or expandable text.

- [ ] **Step 5: Add failed-only retry interaction**

`handleRetryFailedGeneration()` calls the client function, applies the returned run, calls `notifyAiTaskStarted()`, and shows `失败接口已重新加入生成队列`. Disable the button while the request is in flight; do not reuse the initial generate spinner state.

- [ ] **Step 6: Run frontend checks**

Run:

```powershell
cd apps/frontend
node --test tests/api-automation-interface-set-copy-contract.test.mjs
npx biome check src/lib/api-client.ts "src/app/(main)/projects/[projectId]/automation/api/page.tsx"
```

Expected: tests pass and Biome reports no errors.

- [ ] **Step 7: Commit**

```powershell
git add apps/frontend/src/lib/api-client.ts "apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx" apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs
git commit -m "feat: show API generation item results"
```

---

### Task 6: Keep the Top Monitor Through Terminal Completion

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/task-running-indicator.tsx:25`
- Modify: `apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs:241`
- Test: `apps/backend/tests/test_api_automation_generation_agent.py`

**Interfaces:**
- Consumes: Task 4 `ApiTaskItem.summary` and status groups.
- Produces: visible running progress and a short terminal completion state for the tracked API generation task.

- [ ] **Step 1: Write failing top-monitor contract assertions**

Assert the indicator maps `summary`, renders it beneath the task title, remembers tracked API generation task IDs, fetches `/tasks?page=1&page_size=100` when a tracked task leaves `/tasks/running`, and displays the terminal item for 8 seconds.

- [ ] **Step 2: Add summary to the local task type**

Extend `RunningTaskItem` and `toRunningTask()` with `summary: string`. Render `task.summary` under the status row when non-empty.

- [ ] **Step 3: Resolve recently completed tracked tasks**

Keep a `Set<string>` of source IDs seen while running. When `/tasks/running` no longer returns a tracked API generation task, request `ApiTaskList` from `/tasks?page=1&page_size=100&module=api_automation`, find the same `source_id`, and retain its terminal status and summary for `TASK_START_GRACE_MS` (8 seconds). Use `CheckCircle2` for `completed` / `partial_success` and `AlertCircle` for `failed`.

Do not retain unrelated completed tasks and do not change the behavior of other task source types.

- [ ] **Step 4: Add a 100-endpoint backend regression**

Create 100 endpoint items with a fake generator that returns one case per endpoint. Assert the final run has `total_count == 100`, `completed_count == 100`, and no more than five simultaneous fake calls. This is the runnable acceptance check for the original request.

- [ ] **Step 5: Run the complete focused verification**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_generation_agent.py tests/test_api_automation_schema_repo.py tests/test_api_automation_scenarios_tasks.py -q

cd ../frontend
node --test tests/api-automation-interface-set-copy-contract.test.mjs
npx biome check src/components/ai-testing/task-running-indicator.tsx src/lib/api-client.ts "src/app/(main)/projects/[projectId]/automation/api/page.tsx"
```

Expected: all backend and frontend tests pass; Biome reports no errors.

- [ ] **Step 6: Commit**

```powershell
git add apps/frontend/src/components/ai-testing/task-running-indicator.tsx apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs apps/backend/tests/test_api_automation_generation_agent.py
git commit -m "feat: show API generation completion in task monitor"
```

---

## Final Verification

- [ ] Run all focused backend tests:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_generation_agent.py tests/test_api_automation_schema_repo.py tests/test_api_automation_scenarios_tasks.py tests/test_task_service.py -q
```

- [ ] Run the API automation frontend contract test and formatting checks:

```powershell
cd apps/frontend
node --test tests/api-automation-interface-set-copy-contract.test.mjs
npx biome check src/components/ai-testing/task-running-indicator.tsx src/lib/api-client.ts "src/app/(main)/projects/[projectId]/automation/api/page.tsx"
```

- [ ] Manually submit 100 endpoints in a non-production environment and verify:

```text
global active model calls <= 5
each successful endpoint appears before the parent finishes
failed endpoints are attempted once
terminal summary includes success, failure, and total counts
retry failed items leaves successful endpoint cases unchanged
top monitor displays terminal summary before hiding
```

- [ ] Confirm `git status --short` is clean.
