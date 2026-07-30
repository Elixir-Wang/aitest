# Performance Analysis Report Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent AI diagnosis contract errors and provider failures from making an otherwise valid performance report unavailable.

**Architecture:** Keep deterministic metric calculation authoritative, add a focused diagnosis orchestrator for primary invocation and one semantic repair attempt, and fall back to a deterministic report when AI enhancement is unavailable. Persist generation mode and sanitized attempt metadata, then expose degraded status through the existing report APIs and UI.

**Tech Stack:** Python 3.13, FastAPI services, Pydantic, SQLite, pytest, Next.js/React, TypeScript, Node contract tests.

## Global Constraints

- Preserve strict evidence and finding reference validation.
- Never silently delete, guess, or remap invalid references.
- Perform at most one semantic repair model call.
- Generate a deterministic fallback report only after `metric_snapshot` succeeds.
- Do not generate root-cause claims or repair proposals in fallback mode.
- Never persist API keys, authorization headers, or unredacted prompts.
- Preserve unrelated working-tree changes, especially `apps/frontend/src/lib/api-client.ts`.
- Do not create commits unless explicitly requested by the user.

---

### Task 1: Structured Diagnosis Validation

**Files:**
- Create: `apps/backend/app/services/performance_testing/diagnosis_validation.py`
- Modify: `apps/backend/app/services/performance_testing/metric_snapshot_service.py`
- Test: `apps/backend/tests/test_performance_metric_snapshot.py`

**Interfaces:**
- Produces: `DiagnosisValidationResult`, `DiagnosisReferenceError`, and `validate_diagnosis_references(metric_snapshot, diagnosis)`.
- Consumes: `PerformanceDiagnosis` and `metric_snapshot["evidence_index"]`.

- [ ] **Step 1: Write failing tests for complete validation output**

Add tests proving that unknown evidence and finding references are collected without mutating the diagnosis.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `pytest -q tests/test_performance_metric_snapshot.py -k "diagnosis_reference or unknown_metric_evidence_reference"`

Expected: FAIL because the validation module and structured result do not exist.

- [ ] **Step 3: Implement the validation module**

Create immutable validation result data and a dedicated exception carrying the result.

- [ ] **Step 4: Reuse validation from report snapshot construction**

Keep `build_report_snapshot()` as the final defensive gate and raise `DiagnosisReferenceError` on invalid references.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `pytest -q tests/test_performance_metric_snapshot.py`

Expected: PASS.

### Task 2: Evidence Contract and Repairable Model Invocation

**Files:**
- Modify: `apps/backend/app/agents/performance_testing/diagnosis/agent.py`
- Modify: `apps/backend/app/agents/performance_testing/diagnosis/service.py`
- Test: `apps/backend/tests/test_performance_analysis.py`

**Interfaces:**
- Produces: `diagnose_performance(evidence, *, repair_context=None, ...)` with the existing return type.
- Consumes: an optional repair context containing the previous diagnosis, invalid references, and allowed IDs.

- [ ] **Step 1: Write failing prompt-contract tests**

Assert that the primary prompt exposes allowed evidence IDs and empty sections, and that repair mode includes exact invalid and allowed references.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `pytest -q tests/test_performance_analysis.py -k "diagnosis_prompt or repair_prompt"`

- [ ] **Step 3: Add the evidence contract to the primary invocation**

Use `PROMPT_VERSION = "v3-evidence-contract"` and explicitly prohibit field-path references.

- [ ] **Step 4: Add one-shot repair input support**

Reuse the configured model and structured output agent; do not add recursive retry behavior inside the adapter.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `pytest -q tests/test_performance_analysis.py -k "diagnose_performance or diagnosis_prompt or repair_prompt"`

### Task 3: Diagnosis Orchestration and Deterministic Fallback

**Files:**
- Create: `apps/backend/app/services/performance_testing/diagnosis_orchestrator.py`
- Create: `apps/backend/app/services/performance_testing/fallback_report_service.py`
- Modify: `apps/backend/app/schemas/performance_analysis.py`
- Test: `apps/backend/tests/test_performance_analysis.py`

**Interfaces:**
- Produces: `generate_validated_diagnosis(evidence, metric_snapshot, diagnose=diagnose_performance)`.
- Produces: `build_fallback_report_snapshot(metric_snapshot, warnings)`.
- Returns: diagnosis or fallback mode, model metadata, sanitized attempts, and warnings.

- [ ] **Step 1: Write failing orchestration tests**

Cover primary success, invalid primary followed by repaired success, two invalid responses, provider failure, and a strict maximum of two calls.

- [ ] **Step 2: Write failing fallback-report tests**

Assert that deterministic metrics remain unchanged and AI causes, findings, recommendations, and proposals are absent.

- [ ] **Step 3: Run tests and verify RED**

Run: `pytest -q tests/test_performance_analysis.py -k "orchestrator or fallback"`

- [ ] **Step 4: Implement minimal orchestration**

Retry only schema/reference errors; convert provider failures and second validation failures into `deterministic_fallback` results.

- [ ] **Step 5: Implement deterministic fallback report generation**

Build a complete report from the existing metric snapshot without model-derived root-cause claims.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run: `pytest -q tests/test_performance_analysis.py -k "orchestrator or fallback"`

### Task 4: Persistence and Analysis Lifecycle Integration

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/app/repositories/performance_analysis_repo.py`
- Modify: `apps/backend/app/services/performance_testing/analysis_service.py`
- Test: `apps/backend/tests/test_performance_analysis.py`

**Interfaces:**
- Persists: `generation_mode` and `analysis_attempts_json`.
- Serializes: `generation_mode`, `analysis_attempts`, and final report warnings.

- [ ] **Step 1: Write failing repository and lifecycle tests**

Assert new fields serialize correctly and that AI failures complete with fallback mode instead of setting `analysis_status=failed`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `pytest -q tests/test_performance_analysis.py -k "generation_mode or analysis_attempts or deterministic_fallback"`

- [ ] **Step 3: Add compatible SQLite columns**

Extend both fresh schema creation and additive seed migration.

- [ ] **Step 4: Extend repository field mapping and serialization**

Treat `analysis_attempts` as JSON and preserve defaults for historical rows.

- [ ] **Step 5: Integrate the orchestrator into `execute_analysis()`**

Persist prompt/model/attempt data on both full and fallback success paths; reserve failed status for deterministic pipeline failures.

- [ ] **Step 6: Run backend analysis tests and verify GREEN**

Run: `pytest -q tests/test_performance_analysis.py tests/test_performance_metric_snapshot.py`

### Task 5: Report Center and Detail API Semantics

**Files:**
- Modify: `apps/backend/app/services/report_center_service.py`
- Modify: `apps/backend/app/schemas/report_center.py` if response validation requires it
- Test: `apps/backend/tests/test_report_center_service.py`

**Interfaces:**
- Produces report-center fields: `generation_mode` and `generation_status`.
- Maps `deterministic_fallback` to `generation_status="degraded"`.

- [ ] **Step 1: Write failing report-center tests**

Assert AI reports remain generated, fallback reports are degraded, and historical rows remain compatible.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `pytest -q tests/test_report_center_service.py`

- [ ] **Step 3: Implement response mapping**

Read `generation_mode` from the row or report snapshot without changing existing report links.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `pytest -q tests/test_report_center_service.py`

### Task 6: Frontend Degraded Report Status

**Files:**
- Modify carefully: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/app/(main)/reports/page.tsx`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-analysis-report.tsx`
- Modify: `apps/frontend/tests/report-center-contract.test.mjs`
- Modify or create: `apps/frontend/tests/performance-analysis-report-contract.test.mjs`

**Interfaces:**
- Consumes: optional `generation_mode`, `generation_status`, and `generation_warnings`.
- Displays: “基础报告” for deterministic fallback and hides repair actions.

- [ ] **Step 1: Write failing frontend contract tests**

Assert fallback status text, warning banner, retry affordance, and absence of repair actions in fallback mode.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `node --test tests/report-center-contract.test.mjs tests/performance-analysis-report-contract.test.mjs`

- [ ] **Step 3: Extend API types without overwriting unrelated changes**

Add only optional performance-report fields near existing `PerformanceAnalysis` and `ReportCenterItem` definitions.

- [ ] **Step 4: Implement degraded status presentation**

Use text and icon differences, not color alone. Preserve existing successful and failed states.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `node --test tests/report-center-contract.test.mjs tests/performance-analysis-report-contract.test.mjs`

### Task 7: Regression and Quality Verification

**Files:**
- Verify all modified files.

**Interfaces:**
- Consumes all previous task outputs.
- Produces verified implementation evidence.

- [ ] **Step 1: Run backend focused suite**

Run: `pytest -q tests/test_performance_analysis.py tests/test_performance_metric_snapshot.py tests/test_report_center_service.py`

- [ ] **Step 2: Run broader performance backend suite**

Run: `pytest -q tests/test_performance_analysis*.py tests/test_performance_testing.py tests/test_report_center_service.py`

- [ ] **Step 3: Run frontend contract tests**

Run: `node --test tests/report-center-contract.test.mjs tests/performance-analysis-report-contract.test.mjs tests/performance-run-detail-contract.test.mjs`

- [ ] **Step 4: Run configured formatting and type checks**

Use the existing backend and frontend project commands only; do not add new tooling.

- [ ] **Step 5: Review the final diff**

Confirm no credentials, unrelated refactors, generated database changes, or user edits were overwritten.
