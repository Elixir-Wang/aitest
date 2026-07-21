# Test Points Markdown Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render all test points as one Markdown document and support whole-document manual editing and AI editing while keeping structured test-point rows synchronized for downstream test-case generation.

**Architecture:** Structured `test_points` rows remain persistent canonical data. The backend owns deterministic Markdown serialization and strict parsing; the frontend displays and edits the returned Markdown, reuses `/agents/document-editor/run` for AI edits, and saves the full document through one transactional batch endpoint.

**Tech Stack:** FastAPI, Pydantic, SQLite, pytest, Next.js 16, React 19, TypeScript, Biome.

## Global Constraints

- Reuse the existing `/agents/document-editor/run` AI interface.
- Keep current structured test-point storage and downstream test-case generation compatible.
- Reject the entire save when any Markdown test point is invalid.
- Preserve existing IDs by `point_key`; create IDs for new keys and delete omitted keys.
- Match the final-requirement preview/edit/AI-edit interaction as closely as practical.
- Do not modify or revert unrelated working-tree changes.

---

### Task 1: Markdown Codec

**Files:**
- Create: `apps/backend/app/services/test_point_markdown.py`
- Create: `apps/backend/tests/test_test_point_markdown.py`

**Interfaces:**
- Produces: `serialize_test_points(points: list[dict]) -> str`
- Produces: `parse_test_points(markdown_content: str) -> list[dict]`

- [ ] Write failing round-trip, add/delete, duplicate-key, missing-section, and invalid-enum tests.
- [ ] Run `pytest tests/test_test_point_markdown.py -q` and verify failures are caused by missing codec functions.
- [ ] Implement the fixed Markdown template, strict parser, enum validation, and readable `ValueError` messages.
- [ ] Run the focused codec tests and verify they pass.

### Task 2: Transactional Batch Save API

**Files:**
- Modify: `apps/backend/app/schemas/test_point.py`
- Modify: `apps/backend/app/repositories/test_point_repo.py`
- Modify: `apps/backend/app/services/test_point_service.py`
- Modify: `apps/backend/app/api/v1/requirements/test_points.py`
- Create: `apps/backend/tests/test_test_point_markdown_api.py`

**Interfaces:**
- Produces: `TestPointMarkdownUpdateIn(markdown_content: str)`
- Produces: `PUT /projects/{project_id}/requirements/{document_id}/test-points/markdown`
- Extends: `TestPointOverviewOut.markdown_content: str`

- [ ] Write failing service/API tests for overview Markdown, successful batch sync, ID preservation, deletion, authorization, and invalid Markdown rollback.
- [ ] Run the focused API tests and verify expected failures.
- [ ] Add overview serialization and repository replacement that reuses IDs by `point_key` inside one SQLite transaction.
- [ ] Add the admin-only PUT route returning the refreshed overview.
- [ ] Run focused codec and API tests until green.

### Task 3: Final-Requirement-Style Frontend

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/components/ai-testing/test-points-panel.tsx`

**Interfaces:**
- Consumes: `ApiTestPointOverview.markdown_content`
- Consumes: `PUT .../test-points/markdown`
- Reuses: `AiEditInput`, `StandardMarkdownEditor`, `MarkdownPreview`, `/agents/document-editor/run`

- [ ] Extend the API types with `markdown_content` and the document-editor response shape used by the panel.
- [ ] Replace the editable table with preview, editing, saving, canceling, and AI-edit states matching the final-requirement page.
- [ ] Show “修改”和“AI 修改” only when test points exist and the user can edit.
- [ ] Preserve the current loading, generation-running, failed-run, and empty-state behavior.
- [ ] Run Biome lint on the changed frontend files and fix only introduced issues.

### Task 4: Integrated Verification

**Files:**
- Verify all files changed by Tasks 1–3.

- [ ] Run focused backend tests for the codec and API.
- [ ] Run broader related backend test-point/test-case tests if present.
- [ ] Run frontend Biome lint and TypeScript/build validation.
- [ ] Run `git diff --check` and review the final diff for unrelated edits.
- [ ] If the local app is available, open the requirement test-points tab and verify empty, preview, manual edit, cancel, save, AI edit, and error states.
