# API Scenario Canonical Model V2 Implementation Plan

> **For agentic workers:** Execute task-by-task with the existing workspace. Do not create commits unless the user explicitly requests them.

**Goal:** Replace the split AI/legacy scenario contracts with one canonical V2 compiler and validator so the Multi-Agent SegmentCode/SSE scenario generates zero structural errors.

**Architecture:** Keep the existing strongly typed orchestration model as the canonical contract. Move target normalization, binding deduplication, extractor calibration, and validation behind one preparation entry point; remove the AI path's second pass through the legacy validator. Update the frontend and renderer to consume the same seven source types, then remove conflicting draft data.

**Tech Stack:** Python, Pydantic, FastAPI service layer, pytest, JavaScript/TypeScript frontend, SQLite JSON persistence.

## Global Constraints

- No backward compatibility layer for obsolete scenario bindings or source enums.
- No secret values may enter model prompts, plans, issues, logs, or generated code.
- The compiler, not the model, owns executable target paths and response extraction paths.
- User inputs without runtime values are valid plan structure and fail only during execution preflight.
- Do not commit or create branches unless explicitly requested.

---

### Task 1: Add failing regression coverage

**Files:**
- Modify: `apps/backend/tests/test_api_scenario_ai_orchestration.py`
- Test: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Consume the existing `compile_plan`, `_validate_ai_plan`, and plan-generation helpers.
- Produce regression tests for the exact two-step SegmentCode/SSE plan and the V2 preparation behavior.

- [ ] Write a failing test asserting secret and user_input bindings are accepted by the unified validation path.
- [ ] Write a failing test asserting a form target is normalized to multipart and duplicate targets collapse to one binding.
- [ ] Write a failing test asserting `/segment_code` is calibrated to the asset slot `/data/segment_code`.
- [ ] Write a failing test asserting unresolved SSE metadata is a warning, not a validation error.
- [ ] Write a failing test asserting the full AI plan path does not call the legacy `_validate_scenario_definition` validator.
- [ ] Run the focused tests and capture the expected failures before implementation.

Run: `python -m pytest apps/backend/tests/test_api_scenario_ai_orchestration.py -q`

### Task 2: Implement canonical target and issue preparation

**Files:**
- Modify: `apps/backend/app/agents/api_automation/orchestration/schemas.py`
- Modify: `apps/backend/app/services/api_automation/orchestration_asset_analysis.py`
- Modify: `apps/backend/app/services/api_automation/orchestration_compiler.py`
- Test: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Add a canonical `ValidationIssue` model and a single preparation result shape.
- Add target-location normalization based on endpoint request content type.
- Make `compile_plan()` calibrate existing extractors and deduplicate bindings before returning.

- [ ] Define structured issue codes and severities without adding a second source enum.
- [ ] Expose request and response slot details in the model-safe endpoint projection while preserving redaction.
- [ ] Normalize `form` and `multipart` aliases before calculating binding uniqueness.
- [ ] Apply conflict precedence: identical source dedupe, secret-only sensitive targets, step_output over compiler-added user input, otherwise error.
- [ ] Match extractor names and types against response slots and replace stale paths with the unique asset path.
- [ ] Return unresolved SSE metadata as warning issues when the request remains executable.
- [ ] Run the focused tests and verify the new tests pass.

### Task 3: Remove the legacy second validation path

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/schemas/api_automation.py`
- Test: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- AI plan generation, scenario save, publish, and apply all consume the canonical preparation/validation result.
- No AI plan flow calls `_validate_scenario_definition()` after compilation.

- [ ] Replace the AI plan's legacy scenario-definition validation call with the canonical validator.
- [ ] Remove the old source whitelist that rejects `secret` and `user_input`.
- [ ] Stop adding unresolved items to both warnings and errors.
- [ ] Keep runtime-required user inputs valid during plan validation and move missing values to execution preflight.
- [ ] Reject obsolete target structures instead of converting them.
- [ ] Run backend orchestration tests and API service tests covering generation and apply.

### Task 4: Align runtime renderer and frontend with V2

**Files:**
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/renderer.py`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-model.mjs`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/use-api-scenario-editor.ts`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`
- Test: existing frontend API scenario tests and renderer tests

**Interfaces:**
- Runtime resolves all seven canonical source types.
- Frontend renders V2 structured bindings and validation issues without its own conflicting enum.

- [ ] Keep renderer resolution keys consistent with `source_to_runtime()` for environment and secret references.
- [ ] Ensure runtime input lookup distinguishes declared input names from missing runtime values.
- [ ] Replace frontend hard-coded source validation with the V2 source discriminant list or server-provided contract.
- [ ] Render secret references as configured/missing metadata only.
- [ ] Render warnings, errors, info issues, and runtime-required inputs in separate states.
- [ ] Run targeted frontend checks and renderer tests.

### Task 5: Clean conflicting data and verify the complete flow

**Files:**
- Modify: `apps/backend/data/ai_testing.db` only through a scoped cleanup script/transaction
- Add if needed: `scripts/cleanup-api-scenario-v1.py`
- Test: backend and frontend targeted suites

**Interfaces:**
- Remove obsolete AI plans and scenario drafts with V1/legacy bindings only within the affected API automation scope.
- Preserve endpoint assets, API documents, environments, and unrelated test cases.

- [ ] Query and report the exact records selected for deletion before mutation.
- [ ] Delete the known failed AI plans and conflicting un-applied drafts in a transaction.
- [ ] Recreate the SegmentCode/SSE plan from the current endpoint assets.
- [ ] Verify expected bindings, extractor path, input count, issues, and confidence/plan metadata.
- [ ] Run focused backend tests, frontend checks, and the complete relevant API automation test suite.
- [ ] Inspect `git diff` and `git status`; report unrelated pre-existing changes without modifying them.
