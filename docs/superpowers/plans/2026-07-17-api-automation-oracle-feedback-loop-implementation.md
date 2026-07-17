# API Automation Oracle Feedback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make API test generation deterministic at the test-point level and add executable Oracle states that can be calibrated through real execution and human approval.

**Architecture:** A pure planner derives stable `test_point_key` values from endpoint facts. The LLM fills content for the planned points, while the service validates completeness, identity, request semantics, and duplicates before persistence. Execution and Oracle feedback are introduced after generation stability, with `oracle_status` stored on each case and observation-mode results handled separately from assertion results.

**Tech Stack:** Python 3.12+, FastAPI service layer, SQLite, Pydantic, pytest, existing API automation runner and repository patterns.

**Implementation Status (2026-07-17):** Completed. The deterministic planner, generation validation, Oracle metadata migration, observation execution, automatic proposal creation, approval workflow, endpoint-fact feedback, and focused regression suite are implemented. The final focused regression completed with 67 passing tests.

## Global Constraints

- LLM must not decide the number of generated cases.
- Every generated case must map to exactly one stable `test_point_key`.
- `confirmed`, `inferred`, and `needs_confirmation` are executable states with different result semantics.
- `needs_confirmation` records observations and never becomes an automatic failure solely because an Oracle is unavailable.
- Approval is the only path that changes a formal Oracle or endpoint asset.
- Existing generated artifacts and unrelated workspace changes must be preserved.
- No commit is created during implementation.

---

### Task 1: Add deterministic test-point planner

**Files:**
- Create: `apps/backend/app/agents/api_automation/case_generation/planner.py`
- Test: `apps/backend/tests/test_api_automation_case_planner.py`

**Interfaces:**
- Produces `ApiTestPoint` and `plan_api_test_points(endpoint) -> list[ApiTestPoint]`.
- Produces stable keys for success, required body fields, request-body absence, date relations, and executable authentication overrides.

- [x] Write failing tests for the analysis endpoint fixture: required fields, one success baseline, body absence, date format/relation, and one empty case per executable auth header.
- [x] Run the focused tests and confirm the planner module is missing.
- [x] Implement the pure planner without model calls or database access.
- [x] Add duplicate-key and deterministic-order assertions.
- [x] Run the focused planner tests and confirm they pass.

### Task 2: Extend generation schema with point identity and Oracle state

**Files:**
- Modify: `apps/backend/app/agents/api_automation/case_generation/schemas.py`
- Modify: `apps/backend/app/agents/api_automation/case_generation/service.py`
- Test: `apps/backend/tests/test_api_automation_generation_agent.py`

**Interfaces:**
- `ApiGeneratedCase` gains `test_point_key` and `oracle_status`.
- `ApiAutomationGenerationInput` carries a planned test-point list.
- The model prompt requires one output case per planned key and forbids silent omission.

- [x] Add failing schema tests for valid Oracle states, invalid states, and required test-point identity.
- [x] Run those tests and verify the current schema fails them.
- [x] Add the fields and planned-point input contract.
- [x] Update prompt assembly to include the deterministic plan rather than relying on a free-form coverage request.
- [x] Run generation-agent tests and update only contract assertions affected by the new input.

### Task 3: Add generation completeness and semantic validation

**Files:**
- Create: `apps/backend/app/agents/api_automation/case_generation/validation.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Test: `apps/backend/tests/test_api_automation_case_generation_validation.py`

**Interfaces:**
- Produces `validate_generated_cases(endpoint, planned_points, cases) -> None`.
- Rejects missing or duplicate point keys, endpoint mismatches, duplicate success baselines, invalid body-absence semantics, and invalid Oracle states.

- [x] Write failing tests for missing keys, duplicate keys, duplicate success requests, and `{}` incorrectly used for missing body.
- [x] Run the tests and confirm validation functions are missing.
- [x] Implement deterministic validation with actionable error messages.
- [x] Integrate validation before any case insert and before attempt status becomes completed.
- [x] Run focused validation and generation tests.

### Task 4: Persist Oracle metadata and point identity

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/app/repositories/api_automation_repo.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Test: `apps/backend/tests/test_api_automation_schema_repo.py`
- Test: `apps/backend/tests/test_api_automation_generation_agent.py`

**Interfaces:**
- `api_test_cases` stores `test_point_key` and `oracle_status`.
- Existing rows migrate to `legacy.<case_id>` and `confirmed`.
- API case serialization exposes both fields.

- [x] Add failing migration tests against a legacy `api_test_cases` table.
- [x] Run migration tests and confirm the columns are absent before implementation.
- [x] Add idempotent schema migration and repository insert/serialization support.
- [x] Persist planner identity and Oracle state for generated cases.
- [x] Run schema and generation persistence tests.

### Task 5: Add observation-mode execution semantics

**Files:**
- Modify: `apps/backend/app/services/api_automation/runner.py`
- Modify: `apps/backend/app/services/api_automation/reporting.py`
- Modify: `apps/backend/app/schemas/api_automation.py`
- Test: `apps/backend/tests/test_api_automation_runner.py`

**Interfaces:**
- `confirmed` uses assertion mode.
- `inferred` uses assertion mode with calibration metadata.
- `needs_confirmation` uses observation mode and produces `observed` rather than `failed` for missing Oracle.

- [x] Write failing tests for each Oracle state and expected execution result.
- [x] Run focused runner tests and verify observation behavior is absent.
- [x] Implement mode selection without changing request construction or secret handling.
- [x] Preserve response evidence through the existing run/report path.
- [x] Run runner tests and the API automation regression subset.

### Task 6: Add Oracle proposal and approval workflow

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/app/repositories/api_automation_repo.py`
- Create: `apps/backend/app/services/api_automation/oracle.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Test: `apps/backend/tests/test_api_automation_oracle.py`

**Interfaces:**
- Adds proposal creation from execution evidence.
- Adds approve/reject operations with `case_only` and `case_and_endpoint_asset` scopes.
- Approval creates a new case version or audited update and never mutates the original evidence.

- [x] Write failing tests for proposal creation, approval, rejection, idempotency, and scope behavior.
- [x] Run focused Oracle tests and verify endpoints and persistence are absent.
- [x] Implement proposal persistence and review transitions.
- [x] Implement versioned case updates and endpoint asset update hooks.
- [x] Run Oracle tests and API route contract tests.

### Task 7: Final regression and documentation

**Files:**
- Modify: `docs/superpowers/specs/2026-07-17-api-automation-oracle-feedback-loop-spec.md`
- Modify: `apps/backend/app/agents/api_automation/case_generation/skills/api-automation-case-generation/SKILL.md`
- Test: `apps/backend/tests/test_api_automation_generation_agent.py`
- Test: `apps/backend/tests/test_api_automation_runner.py`

- [x] Add the analysis-endpoint regression proving stable point keys and no duplicate success baseline.
- [x] Remove contradictory Oracle-gate language from the generation skill.
- [x] Run focused planner, generation, schema, runner, and Oracle tests.
- [x] Run `rtk git diff --check` and inspect the final diff for unrelated changes.
