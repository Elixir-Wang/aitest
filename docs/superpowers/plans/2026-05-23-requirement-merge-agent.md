# Requirement Merge Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the current deterministic requirement Markdown merge into the 需求归并智能体 workflow, with structured Agent contracts, merge runs, conflict handling, source coverage, incremental preview, and version change logs.

**Architecture:** Keep existing requirement upload and conversion boundaries. `document_service` remains the API-facing orchestrator, while new merge-specific schema/service modules own merge inputs, outputs, fallback logic, persistence, and Agent integration. Existing `/merge` and `/conflicts` routes stay compatible.

**Tech Stack:** FastAPI, SQLite, Python unittest/pytest, existing Agent registry patterns, filesystem Markdown artifacts, Next.js App Router, React, shadcn/ui, Biome.

---

## References

- Spec: `docs/superpowers/specs/2026-05-23-requirement-merge-agent-implementation-spec.md`
- PRD: `docs/00-产品文档/00-03-AI测试系统-需求文档分析与版本管理PRD.md`
- PRD: `docs/00-产品文档/00-05-AI测试系统-知识库生成与更新PRD.md`
- Existing workflow spec: `docs/superpowers/specs/2026-05-22-requirement-overview-workflow-design.md`
- Existing upload spec: `docs/superpowers/specs/2026-05-22-requirement-multi-source-upload-design.md`

---

## File Structure

- Create: `apps/backend/app/schemas/requirement_merge.py`
  - Pydantic contracts for merge input, output, conflicts, coverage, change logs, and preview responses.

- Create: `apps/backend/app/services/requirement_merge_service.py`
  - Owns merge mode detection, deterministic fallback, Agent output validation, conflict result normalization, preview creation, version write preparation, and coverage/change-log preparation.

- Modify: `apps/backend/app/services/document_service.py`
  - Keep public functions but delegate merge logic to `requirement_merge_service`.
  - Keep existing route response compatibility.

- Modify: `apps/backend/app/repositories/document_repo.py`
  - Add merge run CRUD helpers.
  - Add source coverage helpers.
  - Add version change log helpers.
  - Extend conflict helpers while preserving existing fields.

- Modify: `apps/backend/app/seed/init_db.py`
  - Add `requirement_merge_runs`.
  - Add `requirement_source_coverage_items`.
  - Add or migrate `document_version_change_logs` if missing.
  - Extend `source_document_merge_conflicts` with Agent fields through additive migrations.

- Create: `apps/backend/app/agents/requirement_merge/__init__.py`
- Create: `apps/backend/app/agents/requirement_merge/requirement_merge_agent.py`
  - Register or define the 需求归并智能体 boundary.
  - First implementation may call deterministic service fallback if model runtime is not ready.

- Modify: `apps/backend/app/agents/registry.py` or relevant registry module
  - Register `RequirementMergeAgent` if the current registry pattern requires explicit registration.

- Modify: `apps/backend/app/api/v1/requirements.py`
  - Extend `/merge` to accept an optional body without breaking no-body calls.
  - Keep conflict routes unchanged.

- Modify: `apps/backend/app/schemas/document.py`
  - Add merge request body schema if the route keeps document schemas colocated.

- Modify: `apps/backend/tests/test_document_service.py`
  - Keep existing merge/conflict tests passing.
  - Add tests for merge runs, coverage, change logs, incremental preview, and compatibility.

- Create: `apps/backend/tests/test_requirement_merge_service.py`
  - Unit-test merge contracts and fallback behavior outside `document_service`.

- Modify frontend requirement detail page if needed:
  - `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`
  - Add preview state, affected modules, and source coverage display.

---

## Task 1: Lock Current Compatibility

**Files:**
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Add route-compatible service assertions**

Ensure existing service tests assert these fields remain present for successful merge:

```python
self.assertEqual(result["status"], "merged")
self.assertIn("version_id", result)
self.assertIn("version_no", result)
self.assertIn("markdown_content", result)
self.assertIn("merge_summary", result)
self.assertIn("source_file_ids", result)
```

- [ ] **Step 2: Add conflict compatibility assertions**

Ensure conflict responses keep:

```python
self.assertEqual(result["status"], "conflict")
self.assertIn("conflict_count", result)
self.assertIn("conflicts", result)
self.assertIn("id", result["conflicts"][0])
self.assertIn("title", result["conflicts"][0])
self.assertIn("fragment_a", result["conflicts"][0])
self.assertIn("fragment_b", result["conflicts"][0])
```

- [ ] **Step 3: Run current backend tests**

Run:

```bash
cd apps/backend
python -m unittest tests.test_document_service
```

Expected: current tests pass before refactor.

---

## Task 2: Add Merge Schema Contracts

**Files:**
- Create: `apps/backend/app/schemas/requirement_merge.py`
- Modify: `apps/backend/tests/test_requirement_merge_service.py`

- [ ] **Step 1: Create merge contract schemas**

Add Pydantic models:

```python
class RequirementMergeSourceFile(BaseModel):
    mapping_id: str
    original_filename: str
    markdown_content: str
    conversion_status: str
    mapping_status: str


class RequirementMergeBaseVersion(BaseModel):
    id: str
    version_no: int
    markdown_content: str


class RequirementMergeResolvedConflict(BaseModel):
    id: str
    title: str
    resolution: str
    resolution_type: str


class RequirementMergeInput(BaseModel):
    project_id: str
    document_id: str
    document_name: str
    merge_mode: Literal["initial", "incremental", "rebuild"]
    base_version: RequirementMergeBaseVersion | None = None
    source_files: list[RequirementMergeSourceFile]
    resolved_conflicts: list[RequirementMergeResolvedConflict] = []


class RequirementCoverageItem(BaseModel):
    mapping_id: str
    source_heading: str = ""
    source_excerpt: str
    target_module: str = ""
    target_heading: str = ""
    coverage_status: Literal["merged", "duplicate", "conflict", "pending_clarification", "not_testable", "discarded"]
    reason: str


class RequirementMergeConflictOut(BaseModel):
    title: str
    conflict_type: str = "contradiction"
    severity: str = "medium"
    source_refs: list[dict] = []
    fragment_a: str
    fragment_b: str
    agent_suggestion: str = ""


class RequirementMergeOutput(BaseModel):
    status: Literal["merged", "conflict", "preview"]
    markdown_content: str = ""
    markdown_preview: str = ""
    merge_summary: str
    diff_summary: str = ""
    affected_modules: list[str] = []
    source_file_ids: list[str] = []
    coverage_items: list[RequirementCoverageItem] = []
    conflicts: list[RequirementMergeConflictOut] = []
```

- [ ] **Step 2: Add schema validation tests**

Create tests that validate:

- `merged` output accepts coverage items.
- `conflict` output accepts multiple conflicts.
- invalid `status` fails validation.
- invalid `coverage_status` fails validation.

- [ ] **Step 3: Run schema tests**

Run:

```bash
cd apps/backend
python -m pytest tests/test_requirement_merge_service.py -q
```

Expected: schema tests pass.

---

## Task 3: Add Persistence For Merge Runs And Coverage

**Files:**
- Modify: `apps/backend/app/seed/init_db.py`
- Modify: `apps/backend/app/repositories/document_repo.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Add isolated test schema assertions**

Add tests that inspect `PRAGMA table_info` for:

```text
requirement_merge_runs
requirement_source_coverage_items
document_version_change_logs
```

Expected columns:

- `requirement_merge_runs`: `id`, `document_id`, `merge_mode`, `status`, `input_mapping_ids`, `merge_summary`, `affected_modules`
- `requirement_source_coverage_items`: `id`, `run_id`, `document_id`, `mapping_id`, `coverage_status`, `reason`
- `document_version_change_logs`: `id`, `document_id`, `version_id`, `change_summary`, `affected_modules`

- [ ] **Step 2: Add production tables**

In `init_db.py`, add `CREATE TABLE IF NOT EXISTS` statements for:

```sql
CREATE TABLE IF NOT EXISTS requirement_merge_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  base_version_id TEXT,
  output_version_id TEXT,
  merge_mode TEXT NOT NULL,
  status TEXT NOT NULL,
  input_mapping_ids TEXT NOT NULL DEFAULT '[]',
  resolved_conflict_ids TEXT NOT NULL DEFAULT '[]',
  merge_summary TEXT NOT NULL DEFAULT '',
  diff_summary TEXT NOT NULL DEFAULT '',
  affected_modules TEXT NOT NULL DEFAULT '[]',
  output_preview_path TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE
);
```

```sql
CREATE TABLE IF NOT EXISTS requirement_source_coverage_items (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  version_id TEXT,
  mapping_id TEXT NOT NULL,
  source_heading TEXT NOT NULL DEFAULT '',
  source_excerpt TEXT NOT NULL DEFAULT '',
  target_module TEXT NOT NULL DEFAULT '',
  target_heading TEXT NOT NULL DEFAULT '',
  coverage_status TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(run_id) REFERENCES requirement_merge_runs(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE
);
```

If `document_version_change_logs` already exists, migrate additively. If missing, create with:

```sql
CREATE TABLE IF NOT EXISTS document_version_change_logs (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  version_id TEXT NOT NULL,
  source_action TEXT NOT NULL,
  change_summary TEXT NOT NULL DEFAULT '',
  diff_summary TEXT NOT NULL DEFAULT '',
  affected_modules TEXT NOT NULL DEFAULT '[]',
  source_mapping_ids TEXT NOT NULL DEFAULT '[]',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
  FOREIGN KEY(version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE
);
```

- [ ] **Step 3: Extend conflict table additively**

Add nullable/default columns if missing:

```text
run_id
conflict_type
severity
source_refs
agent_suggestion
```

Do not drop existing conflict fields.

- [ ] **Step 4: Add repository helpers**

Add helpers:

```python
create_merge_run(...)
update_merge_run_result(...)
create_source_coverage_items(...)
create_document_version_change_log(...)
find_merge_run(...)
```

- [ ] **Step 5: Run backend tests**

Run:

```bash
cd apps/backend
python -m unittest tests.test_document_service
```

Expected: schema and existing service tests pass.

---

## Task 4: Extract Requirement Merge Service

**Files:**
- Create: `apps/backend/app/services/requirement_merge_service.py`
- Modify: `apps/backend/app/services/document_service.py`
- Create/Modify: `apps/backend/tests/test_requirement_merge_service.py`

- [ ] **Step 1: Move deterministic fallback into merge service**

Create functions:

```python
def detect_merge_mode(current_version_id: str | None, force_rebuild: bool = False) -> str:
    ...


def build_merge_input(... ) -> RequirementMergeInput:
    ...


def run_requirement_merge(input_data: RequirementMergeInput) -> RequirementMergeOutput:
    ...
```

First implementation may reuse the existing deterministic behavior, but it must return `RequirementMergeOutput`.

- [ ] **Step 2: Keep deterministic conflict fallback**

Move `_detect_simple_conflict` into `requirement_merge_service.py` as a private fallback. It should return structured `RequirementMergeConflictOut`.

- [ ] **Step 3: Keep deterministic Markdown fallback**

Move `_merge_markdown_contents` into `requirement_merge_service.py`.

Improve output shape so generated Markdown uses module-like headings and source references, even if the fallback remains simple.

- [ ] **Step 4: Delegate document service**

Update `document_service.merge_document_markdown` to:

1. Validate document.
2. Collect source files.
3. Create merge run.
4. Call `requirement_merge_service.run_requirement_merge`.
5. Persist conflict, preview, or version result.
6. Return the existing-compatible response.

- [ ] **Step 5: Run tests**

Run:

```bash
cd apps/backend
python -m pytest tests/test_requirement_merge_service.py -q
python -m unittest tests.test_document_service
```

Expected: tests pass with no route contract regression.

---

## Task 5: Persist Conflicts, Coverage, And Change Logs

**Files:**
- Modify: `apps/backend/app/services/document_service.py`
- Modify: `apps/backend/app/repositories/document_repo.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Persist structured conflicts**

When merge output is `conflict`:

- Create one row per conflict.
- Include `run_id`, `conflict_type`, `severity`, `source_refs`, and `agent_suggestion`.
- Mark merge run status as `conflict`.
- Do not create `SourceDocumentVersion`.

- [ ] **Step 2: Persist coverage on merged output**

When merge output is `merged`:

- Create coverage items using output `coverage_items`.
- Link them to `run_id`, `document_id`, and output `version_id`.

- [ ] **Step 3: Persist version change log**

When merge output is `merged`:

- Create `document_version_change_logs` row.
- Include `affected_modules` and `source_mapping_ids`.

- [ ] **Step 4: Add tests**

Add service tests:

```python
def test_merge_writes_source_coverage_items(self): ...
def test_merge_writes_document_version_change_log(self): ...
def test_conflict_write_preserves_agent_fields(self): ...
```

- [ ] **Step 5: Run backend tests**

Run:

```bash
cd apps/backend
python -m unittest tests.test_document_service
```

Expected: tests pass.

---

## Task 6: Add Incremental Preview

**Files:**
- Modify: `apps/backend/app/services/requirement_merge_service.py`
- Modify: `apps/backend/app/services/document_service.py`
- Modify: `apps/backend/app/api/v1/requirements.py`
- Modify: `apps/backend/app/schemas/document.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Add optional merge request body**

Add schema:

```python
class RequirementMergeRequestIn(BaseModel):
    merge_mode: str | None = None
    confirm_preview_id: str = ""
    force_rebuild: bool = False
```

Update route to allow omitted body:

```python
def merge_requirement(..., payload: RequirementMergeRequestIn | None = None, ...):
    ...
```

- [ ] **Step 2: Return preview for incremental merge**

When current version exists and pending source files exist:

- First `/merge` call returns `status = preview`.
- Save preview Markdown to merge run `output_preview_path`.
- Do not create a new version.

- [ ] **Step 3: Confirm preview**

When `/merge` receives `confirm_preview_id`:

- Load merge run.
- Write preview Markdown as new `SourceDocumentVersion`.
- Mark pending files merged.
- Create change log and coverage items.
- Return `status = merged`.

- [ ] **Step 4: Add tests**

Add:

```python
def test_incremental_merge_returns_preview_without_creating_version(self): ...
def test_confirm_incremental_preview_creates_new_version(self): ...
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd apps/backend
python -m unittest tests.test_document_service
```

Expected: tests pass.

---

## Task 7: Add 需求归并智能体 Boundary

**Files:**
- Create: `apps/backend/app/agents/requirement_merge/__init__.py`
- Create: `apps/backend/app/agents/requirement_merge/requirement_merge_agent.py`
- Modify: agent registry files as needed
- Modify: `apps/backend/tests/test_skill_loader.py` or create an agent registry test

- [ ] **Step 1: Add agent definition**

Create a definition with:

```text
id: requirement_merge
name: 需求归并智能体
description: 归并多来源标准 Markdown，识别冲突，维护需求工作稿版本。
```

- [ ] **Step 2: Keep implementation replaceable**

Expose a callable boundary such as:

```python
def merge_requirements(input_data: RequirementMergeInput) -> RequirementMergeOutput:
    return requirement_merge_service.run_deterministic_merge(input_data)
```

The first version may use deterministic fallback. Do not fake model behavior as if it were already available.

- [ ] **Step 3: Register agent**

Follow existing `raw_requirement_format_converter` registration style.

- [ ] **Step 4: Add tests**

Assert registry exposes:

```python
self.assertEqual(agent.id, "requirement_merge")
self.assertEqual(agent.name, "需求归并智能体")
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd apps/backend
python -m pytest tests/test_skill_loader.py tests/test_requirement_merge_service.py -q
```

Expected: tests pass.

---

## Task 8: Frontend Preview And Coverage Follow-Up

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`
- Create as needed: `apps/frontend/src/components/ai-testing/requirements/merge-preview-panel.tsx`
- Create as needed: `apps/frontend/src/components/ai-testing/requirements/source-coverage-table.tsx`

- [ ] **Step 1: Extend merge response typing**

Add `preview` fields:

```ts
type MergeResponse =
  | { status: "merged"; version_id: string; version_no: number; markdown_content: string; merge_summary: string; source_file_ids: string[] }
  | { status: "conflict"; conflict_count: number; conflicts: RequirementConflict[] }
  | { status: "preview"; preview_id: string; markdown_preview: string; merge_summary: string; diff_summary: string; affected_modules: string[] };
```

- [ ] **Step 2: Show preview state**

When merge returns `preview`:

- Show merge summary.
- Show affected modules.
- Show Markdown preview.
- Provide confirm button that calls `/merge` with `confirm_preview_id`.

- [ ] **Step 3: Show source coverage**

If backend exposes coverage in overview or merge run detail:

- Render source filename, source heading, target module, coverage status, reason.
- Display Chinese status labels.

- [ ] **Step 4: Verify frontend**

Run:

```bash
cd apps/frontend
npm run lint
npm run build
```

Start dev server and check requirement detail route if data is available.

---

## Task 9: Final Verification

- [ ] **Backend tests**

Run:

```bash
cd apps/backend
python -m pytest tests/test_requirement_merge_service.py tests/test_skill_loader.py -q
python -m unittest tests.test_document_service
```

- [ ] **Frontend checks**

Run if frontend changed:

```bash
cd apps/frontend
npm run lint
npm run build
```

- [ ] **Manual workflow**

Verify:

- Upload or use existing converted Markdown files.
- Trigger initial merge.
- Confirm merged version appears in initial requirement tab.
- Trigger a conflict case.
- Resolve conflict.
- Re-run merge.
- Append new source file.
- Trigger incremental preview.
- Confirm preview creates a new version.

---

## Notes For Implementers

- Do not rename existing public route paths.
- Do not move upload conversion back into an Agent.
- Do not mark pending/conflicting material as confirmed demand.
- Do not overwrite old versions; always create new `SourceDocumentVersion`.
- Keep enum values English in storage and Chinese in UI.
- Prefer additive database migrations because local SQLite data may already exist.
