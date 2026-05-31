# Site Exploration Log Server Pagination Implementation Plan

> **For agentic workers:** implement task-by-task. Keep `logs/run.log` as the only log fact source. Do not add a log table, do not add `events.jsonl`, and do not move exploration process logs into `operation_logs`.

**Goal:** Change exploration logs from full-file frontend pagination to backend parsed, filtered, paginated log loading.

**Architecture:** The existing `GET /api/v1/projects/{project_id}/exploration-runs/{run_id}/log` endpoint remains the contract. Backend reads `logs/run.log`, parses lines into structured items, applies filters, slices the requested page, and returns `items/total/page/page_size`. Frontend requests pages from the backend and stops relying on full `log_content` except as a compatibility fallback.

**Primary Spec:** `docs/superpowers/specs/2026-05-30-site-exploration-log-server-pagination-spec.md`

---

## File Map

- Modify: `apps/backend/app/schemas/exploration.py`
  - Add `ExplorationLogItemOut`.
  - Extend `ExplorationLogOut` with `items`, `total`, `page`, `page_size`.
- Modify: `apps/backend/app/api/v1/exploration.py`
  - Add query params to `get_project_run_log`.
- Modify: `apps/backend/app/services/exploration_service.py`
  - Parse `run.log`, filter, paginate, and return structured response.
- Modify: `apps/backend/tests/test_exploration_service.py`
  - Cover parser, filters, pagination, and raw-content compatibility.
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
  - Change log loading to query backend by page/filter.
  - Use backend `items` and `total`.
  - Keep `log_content` fallback only for old backend responses.
- Optional: `apps/frontend/src/lib/api-client.ts`
  - Add shared DTOs only if project conventions favor central types.

---

## Design Decisions

- Default `page_size` is `10`.
- Backend defaults `include_raw_content=false`, so `log_content` is normally empty.
- `items` is the primary frontend data source.
- Existing permissions remain unchanged.
- Unknown or malformed log lines still appear as `raw` items.
- Filtering happens before pagination.
- `type` accepts both exact event names and broad categories.
- The first implementation can read the whole file into memory, parse, filter, and slice. Streaming optimization is deferred.

---

## Task 1: Backend Schema

**Files:**
- `apps/backend/app/schemas/exploration.py`

- [ ] Add `ExplorationLogItemOut`.
- [ ] Extend `ExplorationLogOut` with:
  - `items: list[ExplorationLogItemOut] = []`
  - `total: int = 0`
  - `page: int = 1`
  - `page_size: int = 10`
- [ ] Keep `log_content`, `log_path`, `updated_at` for compatibility.
- [ ] Use `dict = {}` only if existing schema style allows it; otherwise use `Field(default_factory=dict)`.

Expected item fields:

```python
class ExplorationLogItemOut(BaseModel):
    id: str
    timestamp: str = ""
    event: str = "raw"
    event_label: str = "原始日志"
    category: str = "raw"
    level: str = "info"
    page_id: str = ""
    page_title: str = ""
    url: str = ""
    action_name: str = ""
    result: str = ""
    artifact_path: str = ""
    summary: str = ""
    raw: str = ""
    payload: dict = Field(default_factory=dict)
```

Verification:

```bash
cd apps/backend
python -m pytest tests/test_exploration_service.py -q
```

Expected initially: may fail until service changes are implemented.

---

## Task 2: Backend Parser Helpers

**Files:**
- `apps/backend/app/services/exploration_service.py`
- `apps/backend/tests/test_exploration_service.py`

- [ ] Add focused helper `parse_exploration_log_entries(log_content: str) -> list[dict]`.
- [ ] Parse JSON Lines safely.
- [ ] Preserve original parsed JSON in `payload`.
- [ ] Convert malformed/non-JSON lines into `raw` entries.
- [ ] Generate stable row IDs such as `log-000001`.
- [ ] Add event label mapping matching frontend labels.
- [ ] Add category inference:
  - run
  - page
  - action
  - artifact
  - blocked
  - safety
  - error
  - raw
- [ ] Add level inference:
  - explicit `level`
  - `event=error` or `status=failed`
  - warning for `blocked`, `safety_blocked`, `skipped`
  - raw line keyword detection for errors
- [ ] Format timestamps as full date-time in local display format or ISO-derived stable string.

Tests:

- [ ] JSON line `run_started` returns event/category/summary/url.
- [ ] JSON line `page_captured` returns page fields and artifact path.
- [ ] JSON line `edge_created` returns source/target summary.
- [ ] Plain text stack trace returns `event=raw`, `category=error`, `level=error`.
- [ ] Malformed JSON does not raise.

Verification:

```bash
cd apps/backend
python -m pytest tests/test_exploration_service.py -q
```

---

## Task 3: Backend Filtering And Pagination

**Files:**
- `apps/backend/app/services/exploration_service.py`
- `apps/backend/tests/test_exploration_service.py`

- [ ] Add `filter_exploration_log_entries(entries, filters)`.
- [ ] Add `paginate_exploration_log_entries(entries, page, page_size)`.
- [ ] Clamp `page` to minimum `1`.
- [ ] Clamp `page_size` to range `1..100`.
- [ ] Apply filters before pagination.
- [ ] `keyword` searches:
  - summary
  - raw
  - url
  - page_title
  - page_id
  - action_name
  - result
  - artifact_path
- [ ] `type` matches exact `event` or `category`.
- [ ] `level` matches exact level.
- [ ] `page_ref` matches `page_id`, `page_title`, or `url`.

Tests:

- [ ] page 1/page size 2 returns first two items and total.
- [ ] page 2 returns next slice.
- [ ] page size over 100 clamps to 100.
- [ ] keyword filter changes total.
- [ ] type filter works for exact event and category.
- [ ] level filter returns error rows.
- [ ] page_ref filter returns matching page rows.

Verification:

```bash
cd apps/backend
python -m pytest tests/test_exploration_service.py -q
```

---

## Task 4: Backend Service Contract

**Files:**
- `apps/backend/app/services/exploration_service.py`
- `apps/backend/tests/test_exploration_service.py`

- [ ] Change `get_project_run_log(...)` signature to accept:
  - `page`
  - `page_size`
  - `keyword`
  - `type_filter`
  - `level`
  - `page_ref`
  - `include_raw_content`
- [ ] Keep authorization and not-found behavior unchanged.
- [ ] Read `artifacts["log_content"]`.
- [ ] Parse entries.
- [ ] Filter entries.
- [ ] Paginate entries.
- [ ] Return:
  - `run_id`
  - `log_path`
  - `updated_at`
  - `items`
  - `total`
  - `page`
  - `page_size`
  - `log_content` only when `include_raw_content=True`, otherwise `""`

Tests:

- [ ] Existing `test_get_project_run_log_reads_yaml_artifact_log` is updated to assert paginated items.
- [ ] `include_raw_content=False` returns empty `log_content`.
- [ ] `include_raw_content=True` returns full content.
- [ ] Missing log returns empty `items`, `total=0`, no exception.

Verification:

```bash
cd apps/backend
python -m pytest tests/test_exploration_service.py -q
```

---

## Task 5: Backend API Query Params

**Files:**
- `apps/backend/app/api/v1/exploration.py`

- [ ] Add query parameters to `get_project_run_log`.
- [ ] Avoid using parameter name `type` internally if it shadows builtins; map API `type` to `type_filter`.
- [ ] Pass all params to service.

Expected route shape:

```python
@router.get("/{project_id}/exploration-runs/{run_id}/log", response_model=ExplorationLogOut)
def get_project_run_log(
    project_id: str,
    run_id: str,
    page: int = 1,
    page_size: int = 10,
    keyword: str = "",
    type: str = "",
    level: str = "",
    page_ref: str = "",
    include_raw_content: bool = False,
    actor=Depends(current_user),
) -> dict:
    return exploration_service.get_project_run_log(
        project_id,
        run_id,
        actor,
        page=page,
        page_size=page_size,
        keyword=keyword,
        type_filter=type,
        level=level,
        page_ref=page_ref,
        include_raw_content=include_raw_content,
    )
```

Verification:

```bash
cd apps/backend
python -m pytest tests/test_exploration_service.py -q
```

If API tests exist for exploration logs, run them too:

```bash
cd apps/backend
python -m pytest tests/test_exploration_api.py -q
```

---

## Task 6: Frontend DTO And Loading State

**Files:**
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Extend `ExplorationLog` type:
  - `items?: ParsedLogEntry[]`
  - `total?: number`
  - `page?: number`
  - `page_size?: number`
- [ ] Align frontend parsed-entry field names with backend item fields.
- [ ] Keep local `parseLogEntries` only as fallback for old backend responses.
- [ ] Add log query state at the parent or panel level:
  - page
  - pageSize
  - keyword
  - category/type
  - level
  - pageRef
- [ ] Ensure `loadLog` accepts query params.

---

## Task 7: Frontend Server-Side Pagination

**Files:**
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Build query string for `/log`.
- [ ] Default request uses `page=1&page_size=10`.
- [ ] On page change, request backend page.
- [ ] On page size change, set page to 1 and request backend.
- [ ] On keyword/type/level/page filter change, set page to 1 and request backend.
- [ ] Use backend `items` as the table rows.
- [ ] Use backend `total` for pagination.
- [ ] Stop slicing full `entries` locally when `items` exists.
- [ ] Fallback only when response lacks `items` and has `log_content`.

Acceptance:

- Network request changes when clicking next page.
- The page does not fetch full raw `run.log` by default.
- Pagination total matches backend `total`.

Verification:

```bash
cd apps/frontend
npx biome check 'src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx'
npm run build
```

---

## Task 8: Frontend Filter Options

**Files:**
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Keep event type options static from known categories.
- [ ] For page filter, avoid requiring full log scan.
- [ ] Use current page items to populate page options only as a convenience, or remove page select until backend exposes a page facet.
- [ ] If keeping page select, label it as current-page derived or use text input instead.

Recommended V1:

- Keep type, level, keyword.
- Replace page dropdown with a `page_ref` text input if page facet is not available.

Reason:

- A full page dropdown requires scanning all log entries or a separate facet endpoint, which conflicts with the server pagination goal.

---

## Task 9: Regression Checks

- [ ] Existing exploration plan tab still renders.
- [ ] Existing exploration overview tab still renders.
- [ ] Exploration report tab still loads.
- [ ] Log detail dialog opens from a paginated row.
- [ ] Old backend response with only `log_content` still displays via fallback.
- [ ] Empty log returns empty table state.
- [ ] Error stack logs show as raw/error rows.
- [ ] System logs page is unchanged.

---

## Completion Criteria

- Backend `/log` endpoint returns paginated `items`.
- Default `page_size` is 10.
- Frontend no longer fetches complete `run.log` for normal log tab display.
- Pagination, page size, and filters trigger backend requests.
- Full `log_content` is not returned unless explicitly requested.
- Backend tests for parsing/filtering/pagination pass.
- Frontend single-file check and build pass.

