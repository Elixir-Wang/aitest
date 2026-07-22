# API Generated Response Contract Assertions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every newly generated API test case preserves deterministic response-contract assertions compiled from the endpoint OpenAPI response definition.

**Architecture:** Add a pure response-contract compiler beside the existing case planner. The generation service attaches compiled assertions to planned test points, merges them into model output before validation and persistence, and rejects conflicts. Existing pytest generation receives the final persisted assertions without any historical data migration.

**Tech Stack:** Python 3, Pydantic, pytest, FastAPI service layer, SQLite repository data.

## Global Constraints

- Apply the behavior only to newly generated API test cases.
- Do not migrate, scan, or modify historical API test cases.
- Do not add a database migration.
- Do not infer undocumented response fields or business values.
- Preserve approved Oracle assertions exactly.
- Generate JSONPath assertions only for JSON-compatible responses.
- Use TDD and run tests from the backend virtual environment.
- Do not create git commits unless the user explicitly requests them.

---

### Task 1: Response Contract Compiler

**Files:**
- Create: `apps/backend/app/agents/api_automation/case_generation/response_contract.py`
- Create: `apps/backend/tests/test_api_automation_response_contract.py`

**Interfaces:**
- Consumes: serialized endpoint dictionaries containing `responses`.
- Produces: `compile_response_contract(endpoint, expected_status_code=None) -> list[ApiAssertion]`.

- [ ] Write failing tests for nested JSON properties, fixed success code, dynamic examples, arrays, binary responses, and unresolved references.
- [ ] Run the focused tests and verify they fail because the compiler does not exist.
- [ ] Implement response selection, media-type selection, recursive JSON property traversal, fixed-value detection, normalization, and binary handling.
- [ ] Run the focused tests and verify they pass.

### Task 2: Assertion Merge and Conflict Detection

**Files:**
- Modify: `apps/backend/app/agents/api_automation/case_generation/response_contract.py`
- Modify: `apps/backend/tests/test_api_automation_response_contract.py`

**Interfaces:**
- Consumes: backend-required assertions and model-generated assertions.
- Produces: `merge_response_assertions(required, generated) -> list[ApiAssertion]`.

- [ ] Write failing tests for missing assertion completion, deduplication, status conflicts, fixed-value conflicts, and JSONPath/media-type conflicts.
- [ ] Run the focused tests and verify the expected failures.
- [ ] Implement deterministic merge, ordering, deduplication, and explicit conflict errors.
- [ ] Run the focused tests and verify they pass.

### Task 3: Generation Input and Persistence Integration

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/tests/test_api_automation_generation_agent.py`
- Modify: `apps/backend/tests/test_api_automation_case_generation_validation.py`

**Interfaces:**
- Consumes: `plan_api_test_points()` output and compiled endpoint response contracts.
- Produces: planned points with `required_assertions` and persisted cases containing merged assertions.

- [ ] Write failing tests proving planned success points receive required assertions and persisted model output is completed before validation.
- [ ] Run focused service and validation tests and verify failures.
- [ ] Attach `required_assertions` in `_build_generation_item_input()`.
- [ ] Merge required assertions in `_persist_generation_item_cases()` before strict validation and persistence.
- [ ] Preserve approved Oracle equality validation independently from required contract assertions.
- [ ] Run focused tests and verify they pass.

### Task 4: Validation Contract

**Files:**
- Modify: `apps/backend/app/agents/api_automation/case_generation/validation.py`
- Modify: `apps/backend/tests/test_api_automation_case_generation_validation.py`

**Interfaces:**
- Consumes: generated cases after assertion merging and planned points with `required_assertions`.
- Produces: precise errors for incomplete or conflicting response contracts.

- [ ] Write failing tests for missing required paths, `needs_confirmation` contract preservation, and exact approved Oracle behavior.
- [ ] Run focused tests and verify failures.
- [ ] Add required-assertion coverage validation with precise assertion labels.
- [ ] Run focused tests and verify they pass.

### Task 5: Generation and Runtime Rules

**Files:**
- Modify: `apps/backend/app/agents/api_automation/case_generation/skills/api-automation-case-generation/SKILL.md`
- Modify: `apps/backend/app/agents/api_automation/case_generation/skills/api-automation-case-generation/references/assertion-guidelines.md`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/SKILL.md`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/references/assertion-mapping.md`
- Modify: `apps/backend/tests/test_api_automation_generation_agent.py`
- Modify: `apps/backend/tests/test_api_automation_deepagents_agent.py`

**Interfaces:**
- Consumes: persisted final assertion lists.
- Produces: generated pytest suites that execute every supported assertion type.

- [ ] Write or update contract tests requiring immutable `required_assertions` and executable `jsonpath_exists` behavior.
- [ ] Run the focused contract tests and verify failures.
- [ ] Update generation instructions and assertion reference implementation.
- [ ] Run the focused tests and verify they pass.

### Task 6: Verification

**Files:**
- Verify all files changed by Tasks 1-5.

**Interfaces:**
- Consumes: completed implementation.
- Produces: fresh test evidence.

- [ ] Run response-contract compiler and validation tests.
- [ ] Run API automation generation, planner, Oracle, and script-generation tests.
- [ ] Run the broader backend API automation test subset.
- [ ] Review the final diff for historical-data writes, database migrations, unrelated edits, and unresolved placeholders.
