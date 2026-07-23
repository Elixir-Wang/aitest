# UI Automation Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first backend version of platform-shared pytest + Playwright generation for one accepted test case, using DeepAgents, structured AutomationPlan validation, deterministic rendering, separated test data, and manually triggered execution.

**Architecture:** The platform owns one suite under `data/ui_automation/pytest_playwright`. Business projects and cases are isolated inside `project_key` namespaces for pages, tests, and data. The backend creates canonical case data and evidence context, DeepAgents may refine that data and produce a constrained AutomationPlan inside the shared FilesystemBackend, and deterministic Python renderers own POM/test code changes. Generation and execution are separate persisted background tasks.

**Tech Stack:** Python 3.12+, FastAPI, SQLite, Pydantic 2, DeepAgents, pytest, Playwright Python, PyYAML-compatible project helpers.

## Global Constraints

- First version accepts exactly one `test_case_id` per generation run.
- Do not add Allure or a downloadable pytest project.
- Reuse existing exploration artifacts and targeted exploration services; never invent locators.
- Initialize the platform-shared pytest_playwright suite only when the first UI automation case is generated.
- DeepAgent may modify derived UI automation data files but must never update the source test case.
- AutomationPlan models use `extra="forbid"`; arbitrary Python expressions are not accepted.
- Rendered files must remain inside the shared suite and the backend-selected business-project namespace.
- Generation performs compile and pytest collection only; real execution requires a separate user-triggered run.
- Existing unrelated working-tree changes must not be reverted.

---

### Task 1: AutomationPlan and Suite Core

**Files:**
- Create: `apps/backend/app/agents/ui_automation/__init__.py`
- Create: `apps/backend/app/agents/ui_automation/pytest_playwright/__init__.py`
- Create: `apps/backend/app/agents/ui_automation/pytest_playwright/schemas.py`
- Create: `apps/backend/app/agents/ui_automation/pytest_playwright/suite.py`
- Create: `apps/backend/tests/test_ui_automation_plan.py`
- Create: `apps/backend/tests/test_ui_automation_suite.py`

**Interfaces:**
- Produces: `AutomationPlan`, `PageObjectPlan`, `StepPlan`, `AssertionPlan`.
- Produces: shared `project_suite_path(project_id)`, `ensure_suite_root(path)`, `resolve_suite_file(path, relative_path)`, and project-namespaced `case_artifact_paths(...)`.

- [ ] **Step 1: Write failing plan validation tests**

```python
def test_automation_plan_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        AutomationPlan.model_validate({"schema_version": "v1", "unknown": True})

def test_locator_requires_evidence():
    with pytest.raises(ValidationError):
        LocatorPlan(strategy="role", role="button", name="提交", evidence_refs=[])
```

- [ ] **Step 2: Run the plan tests and verify import/validation failures**

Run: `python -m pytest tests/test_ui_automation_plan.py -q`
Expected: FAIL because the UI automation models do not exist.

- [ ] **Step 3: Implement strict Pydantic models and path helpers**

Implement fixed action/assertion literals, source-step mapping, locator evidence requirements, backend-owned artifact paths, root containment checks, one shared suite path, and project namespaces.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_ui_automation_plan.py tests/test_ui_automation_suite.py -q`
Expected: PASS.

### Task 2: Deterministic Suite Initialization and Rendering

**Files:**
- Create: `apps/backend/app/agents/ui_automation/pytest_playwright/renderer.py`
- Create: `apps/backend/app/agents/ui_automation/pytest_playwright/collection.py`
- Create: `apps/backend/tests/test_ui_automation_renderer.py`

**Interfaces:**
- Consumes: `AutomationPlan`, `case_artifact_paths`.
- Produces: `initialize_suite(suite_path) -> list[Path]`.
- Produces: `render_automation_plan(suite_path, plan) -> dict[str, Path]`.
- Produces: `collect_suite(suite_path, test_paths=None) -> dict`.

- [ ] **Step 1: Write failing renderer tests**

Test that shared initialization creates `pytest.ini`, `conftest.py`, config, base page, loaders, waiters, assertion helpers, and the local DeepAgent skill; test that rendering creates project-namespaced POM and test modules without embedding data values.

- [ ] **Step 2: Run renderer tests and verify failures**

Run: `python -m pytest tests/test_ui_automation_renderer.py -q`
Expected: FAIL because renderer functions do not exist.

- [ ] **Step 3: Implement deterministic templates and incremental POM merge**

Use fixed templates, semantic Playwright locators, YAML data loading, environment-variable resolution, source/evidence metadata, atomic writes, and marker-bounded generated sections for safe POM updates.

- [ ] **Step 4: Run renderer tests**

Run: `python -m pytest tests/test_ui_automation_renderer.py -q`
Expected: PASS.

### Task 3: DeepAgents Project Writer

**Files:**
- Create: `apps/backend/app/agents/ui_automation/pytest_playwright/agent.py`
- Create: `apps/backend/app/agents/ui_automation/pytest_playwright/skill.py`
- Create: `apps/backend/app/agents/ui_automation/pytest_playwright/skills/pytest-playwright-ui-generation/SKILL.md`
- Create: `apps/backend/app/agents/ui_automation/pytest_playwright/skills/pytest-playwright-ui-generation/references/automation-plan.md`
- Create: `apps/backend/app/agents/ui_automation/pytest_playwright/skills/pytest-playwright-ui-generation/references/pom-rules.md`
- Create: `apps/backend/app/agents/ui_automation/pytest_playwright/skills/pytest-playwright-ui-generation/references/locator-rules.md`
- Create: `apps/backend/tests/test_ui_automation_deepagent.py`

**Interfaces:**
- Consumes: shared suite path, backend-owned project-namespaced case data path, evidence context, allowed artifact paths.
- Produces: `create_pytest_playwright_agent(...)` and `generate_pytest_playwright_case(...)`.

- [ ] **Step 1: Write failing DeepAgent contract tests**

Assert the agent uses `FilesystemBackend(root_dir=suite_path, virtual_mode=True)`, includes validation/render/collection tools, loads `.deepagents/skills`, and its prompt forbids source-case writes, invented locators, alternate paths, secrets, and real test execution.

- [ ] **Step 2: Run the contract tests**

Run: `python -m pytest tests/test_ui_automation_deepagent.py -q`
Expected: FAIL because the agent module does not exist.

- [ ] **Step 3: Implement the DeepAgent and materialize its skill**

Follow the existing pytest-requests DeepAgent pattern, but permit changes to the specified derived data file and require the Agent to call deterministic plan validation/rendering before collection.

- [ ] **Step 4: Run the contract tests**

Run: `python -m pytest tests/test_ui_automation_deepagent.py -q`
Expected: PASS.

### Task 4: Persistence, Context, and Generation Service

**Files:**
- Create: `apps/backend/app/repositories/ui_automation_repo.py`
- Create: `apps/backend/app/services/ui_automation/__init__.py`
- Create: `apps/backend/app/services/ui_automation/artifact_storage.py`
- Create: `apps/backend/app/services/ui_automation/context.py`
- Create: `apps/backend/app/services/ui_automation/service.py`
- Modify: `apps/backend/app/repositories/__init__.py`
- Modify: `apps/backend/app/seed/schema.py`
- Create: `apps/backend/tests/test_ui_automation_repo.py`
- Create: `apps/backend/tests/test_ui_automation_generation_service.py`

**Interfaces:**
- Produces generation-run, asset, and execution-run repository CRUD.
- Produces `create_generation_run`, `execute_generation_run`, `get_generation_run`, `list_assets`.
- Consumes existing project, environment, test-case, exploration-run, and artifact repositories.

- [ ] **Step 1: Write failing repository and service tests**

Cover one-case input, accepted-case enforcement, project/environment ownership, shared suite initialization, project namespace isolation, canonical derived data creation, Agent invocation, source hash reuse, changed-file persistence, rollback, and no source-test-case update.

- [ ] **Step 2: Run focused tests and verify failures**

Run: `python -m pytest tests/test_ui_automation_repo.py tests/test_ui_automation_generation_service.py -q`
Expected: FAIL because persistence and service modules do not exist.

- [ ] **Step 3: Implement schema, repository, artifact storage, context, and generation orchestration**

Add SQLite tables with guarded startup migrations, use one shared automation workspace lock and atomic writes, summarize relevant exploration YAML, support a deterministic fallback plan for tests, and isolate DeepAgent invocation behind a patchable function.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_ui_automation_repo.py tests/test_ui_automation_generation_service.py -q`
Expected: PASS.

### Task 5: Manual Execution Runner

**Files:**
- Create: `apps/backend/app/services/ui_automation/runner.py`
- Extend: `apps/backend/app/services/ui_automation/service.py`
- Create: `apps/backend/tests/test_ui_automation_runner.py`

**Interfaces:**
- Produces: `create_execution_run`, `execute_execution_run`, `get_execution_run`.
- Produces: raw `result.json`, stdout, stderr, trace, screenshots, and optional video paths.

- [ ] **Step 1: Write failing runner tests**

Test exact pytest node selection, environment injection, secret redaction, isolated run directories, JSON result fallback, and artifact path persistence without Allure.

- [ ] **Step 2: Run runner tests and verify failures**

Run: `python -m pytest tests/test_ui_automation_runner.py -q`
Expected: FAIL because the UI runner does not exist.

- [ ] **Step 3: Implement the runner and execution orchestration**

Invoke `python -m pytest <node-id>` in the shared suite, set base URL/auth-state/result variables, capture output, redact secrets, and persist generic run evidence.

- [ ] **Step 4: Run runner tests**

Run: `python -m pytest tests/test_ui_automation_runner.py -q`
Expected: PASS.

### Task 6: FastAPI Contracts and Recovery

**Files:**
- Create: `apps/backend/app/schemas/ui_automation.py`
- Create: `apps/backend/app/api/v1/ui_automation.py`
- Modify: `apps/backend/app/api/v1/__init__.py`
- Modify: `apps/backend/app/main.py`
- Create: `apps/backend/tests/test_ui_automation_api.py`

**Interfaces:**
- Produces business-project-scoped generation, asset, and execution endpoints backed by the shared suite.
- Produces `recover_interrupted_ui_automation_tasks()`.

- [ ] **Step 1: Write failing API contract tests**

Verify admin-only generation/execution, one-case request schema, background task scheduling, project scoping, run lookup, asset listing/detail, and startup recovery registration.

- [ ] **Step 2: Run API tests and verify failures**

Run: `python -m pytest tests/test_ui_automation_api.py -q`
Expected: FAIL because schemas and routes do not exist.

- [ ] **Step 3: Implement schemas, routes, registration, and recovery**

Use the existing API response middleware conventions and BackgroundTasks pattern from API automation.

- [ ] **Step 4: Run API tests**

Run: `python -m pytest tests/test_ui_automation_api.py -q`
Expected: PASS.

### Task 7: Integrated Verification

**Files:**
- Modify only files required by failures attributable to Tasks 1-6.

**Interfaces:**
- Verifies the complete backend UI automation generation and manual execution slice.

- [ ] **Step 1: Run all UI automation tests**

Run: `python -m pytest tests/test_ui_automation_*.py -q`
Expected: PASS.

- [ ] **Step 2: Run architecture and route regression tests**

Run: `python -m pytest tests/test_agent_architecture_boundaries.py tests/test_ai_agents_architecture.py tests/test_api_response_middleware.py -q`
Expected: PASS.

- [ ] **Step 3: Run backend collection**

Run: `python -m pytest --collect-only -q`
Expected: exit code 0.

- [ ] **Step 4: Review the diff against the design**

Confirm one shared suite, project namespace isolation, DeepAgents restrictions, data/code separation, no Allure, no download endpoint, locator evidence enforcement, deterministic rendering, separate execution, and no unrelated file reversal.
