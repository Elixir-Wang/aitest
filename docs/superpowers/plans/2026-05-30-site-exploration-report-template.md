# Site Exploration Report Template Implementation Plan

> **For agentic workers:** implement task-by-task. The exploration report is a derived summary only; do not turn it into a fact source, a knowledge base document, or a test-case generator input.

**Goal:** Replace the current exploration report with a standardized 11-section summary template that is generated from structured exploration artifacts.

**Architecture:** Read `run.yaml`, `summary.yaml`, `graph.yaml`, `blockers.yaml`, `pages/*.yaml`, and `logs/run.log`; render a Markdown report under `documents/exploration-v1.md`; keep the report lightweight and strictly derivative. Do not add report action buttons or process controls.

**Primary Spec:** `docs/superpowers/specs/2026-05-30-site-exploration-report-template-spec.md`

---

## File Map

- Modify: `apps/backend/app/services/exploration_artifact_service.py`
  - Add a report builder that composes the 11-section Markdown template from YAML artifacts.
  - Keep artifact writing for `run.yaml`, `summary.yaml`, `graph.yaml`, `blockers.yaml`, `pages/*.yaml`, and `logs/run.log`.
- Modify: `apps/backend/app/services/exploration_service.py`
  - Update `get_project_run_report` to return the derived report Markdown from the artifact bundle.
  - Remove dependence on report-as-source semantics.
- Modify: `apps/backend/tests/test_exploration_artifact_service.py`
  - Add coverage for report generation from structured artifacts.
- Modify: `apps/backend/tests/test_exploration_service.py`
  - Add coverage for report retrieval from YAML artifact bundle.
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
  - Keep the report tab as a Markdown renderer only.
  - Ensure no report actions/buttons are introduced.
- Optional modify: `apps/backend/app/agents/site_exploration/skills/site_exploration/SKILL.md`
  - Align the agent-side report wording if it still references the older summary shape.

---

## Design Decisions

- The report is a derived artifact, not an authoritative source.
- The report must be regenerated from structured YAML facts.
- The report template is fixed to 11 sections:
  - 报告摘要
  - 探索结论
  - 探索范围与边界
  - 覆盖概览
  - 模块覆盖矩阵
  - 页面事实摘要
  - 页面关系与路径
  - 阻塞与跳过
  - 风险与缺口
  - 待人工确认事项
  - 证据索引
- The report must not include full YAML dumps, full logs, full locator data, or test-case drafts.
- The report must not create or update knowledge-base content.
- The report must not be the main input to test-case generation.
- Evidence references should point to artifact paths only.
- If report content and YAML facts disagree, YAML wins.

---

## Task 1: Confirm Current Report Entry Points

**Files:**
- `apps/backend/app/services/exploration_service.py`
- `apps/backend/app/services/exploration_artifact_service.py`
- `apps/backend/tests/test_exploration_service.py`
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Confirm how the report tab currently fetches and renders `markdown_content`.
- [ ] Confirm whether `summary.yaml` already stores the old report Markdown.
- [ ] Confirm whether any other code path still reads `exploration_document_versions` for exploration reports.

Verification:

```bash
rg -n "get_project_run_report|markdown_content|exploration_document_versions|探索报告" apps/backend apps/frontend
```

---

## Task 2: Build Derived Report Markdown

**Files:**
- Modify: `apps/backend/app/services/exploration_artifact_service.py`

- [ ] Add a helper such as `build_exploration_report_markdown(...)`.
- [ ] Accept the loaded artifact bundle (`run`, `summary`, `graph`, `blockers`, `pages`, `log_content`).
- [ ] Render the 11 report sections from the spec.
- [ ] Use compact tables for module coverage, page facts, page relations, blockers, and confirmations.
- [ ] Generate evidence references from file paths only.
- [ ] Keep the output deterministic for the same artifact bundle.
- [ ] Keep the report English/Chinese wording aligned with the existing product style.

Acceptance:

- A run with complete YAML artifacts produces a report with all 11 sections.
- Missing YAML files degrade gracefully to empty tables or short warnings, not exceptions.
- The report stays short enough to be readable as a summary.

---

## Task 3: Update Report Retrieval

**Files:**
- Modify: `apps/backend/app/services/exploration_service.py`

- [ ] Update `get_project_run_report` to call the new report builder from the artifact bundle.
- [ ] Return the derived Markdown content as the report payload.
- [ ] Preserve existing response fields expected by the frontend where possible.
- [ ] Do not read a legacy report document as the primary source.

Acceptance:

- `GET /api/v1/projects/{project_id}/exploration-runs/{run_id}/report` returns the derived report.
- Runs without summary artifacts still return a safe fallback message.

---

## Task 4: Add Backend Tests

**Files:**
- Modify: `apps/backend/tests/test_exploration_artifact_service.py`
- Modify: `apps/backend/tests/test_exploration_service.py`

- [ ] Test that report generation includes the expected 11 sections.
- [ ] Test that evidence paths are rendered from artifact paths, not fabricated text.
- [ ] Test that missing artifact files do not crash report generation.
- [ ] Test that `get_project_run_report` returns derived content from the YAML bundle.

Verification:

```bash
cd apps/backend
python -m pytest tests/test_exploration_artifact_service.py tests/test_exploration_service.py -q
```

Expected: PASS.

---

## Task 5: Keep Frontend Report Tab Read-Only

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Keep the report tab as Markdown rendering only.
- [ ] Do not add report action buttons.
- [ ] Do not add editing or generation controls in the tab.
- [ ] Ensure the tab remains consistent with the rest of the exploration workspace shell.

Acceptance:

- The report tab displays the derived Markdown.
- No new actions appear in the report area.

---

## Task 6: Add Report Coverage Tests

**Files:**
- Modify: `apps/backend/tests/test_exploration_service.py`
- Optional: frontend smoke test if the current suite already covers the exploration page

- [ ] Confirm the report tab still renders the Markdown body.
- [ ] Confirm the tab does not require extra inputs or controls.

---

## Task 7: Validate Against Spec

- [ ] Verify the report contains only summary-level content.
- [ ] Verify the report does not duplicate log-view responsibilities.
- [ ] Verify the report does not try to become knowledge-base content.
- [ ] Verify the report still points readers to `run.yaml`, `summary.yaml`, `pages/*.yaml`, `graph.yaml`, `blockers.yaml`, and `logs/run.log`.

---

## Out of Scope

- Report edit workflows
- Report generation buttons
- Knowledge-base writes from the report
- Test-case generation from the report
- Full YAML dumps
- Full log replay
- Locator dumps
- Screenshot or HTML embedding

