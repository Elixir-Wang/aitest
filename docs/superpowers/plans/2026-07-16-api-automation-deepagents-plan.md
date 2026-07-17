# API Automation DeepAgents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace renderer-only API script generation with a project-root DeepAgents workflow that initializes one pytest+requests suite per business project, directly edits that suite, and repairs pytest collection failures before reporting success.

**Architecture:** The backend resolves one persistent suite directory per project and creates a DeepAgents agent with that directory as its filesystem root. An initialization task creates or repairs the shared pytest framework; an endpoint task updates selected endpoint files in the same directory, runs bounded collection repair, and records generation state. The existing runner remains responsible for real pytest execution and project-specific runtime environments.

**Tech Stack:** Python 3.12+, FastAPI service layer, `deepagents`, `pytest`, `requests`, `uv`, Pydantic, existing repository/service tests.

## Global Constraints

- One business project owns one persistent `api_automation/pytest_requests` suite.
- DeepAgents writes directly to the configured suite directory; no required temporary workspace.
- The agent cannot access paths outside the suite root.
- Initialization must create shared files before endpoint files are generated.
- Collection validation must not send real API requests.
- Runtime URLs, credentials, tokens, cookies, and local absolute paths stay outside generated source code.
- The backend virtual environment and project test virtual environment remain separate.
- The suite runner must not inherit the backend `VIRTUAL_ENV`.
- Selected endpoint files may be changed; unselected endpoint artifacts must be preserved.
- Do not commit changes during implementation.

---

### Task 1: Define agent-facing suite instructions

**Files:**
- Create: `apps/backend/app/agents/api_automation/pytest_requests/AGENTS.md`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/SKILL.md`
- Test: `apps/backend/tests/test_api_automation_pytest_requests_agent.py`

**Interfaces:**
- Consumes: existing endpoint and case schemas.
- Produces: explicit initialization, endpoint update, collection-repair, file-ownership, and secret-handling rules for the agent.

- [ ] Write tests that assert the agent instruction contract names the required shared files and direct suite root.
- [ ] Run the focused tests and verify the new assertions fail because the project instructions do not yet exist.
- [ ] Add concise `AGENTS.md` instructions for the suite root: inspect before editing, preserve unselected endpoint files, use environment variables for runtime values, and run collection after edits.
- [ ] Update the skill so `is_first_time` is no longer the authority for project completeness; the agent must inspect the real directory and repair missing shared files.
- [ ] Run the focused agent tests and verify they pass.

### Task 2: Add suite completeness and initialization contracts

**Files:**
- Create: `apps/backend/app/agents/api_automation/pytest_requests/suite.py`
- Modify: `apps/backend/app/services/api_automation/artifact_storage.py`
- Test: `apps/backend/tests/test_api_automation_suite.py`

**Interfaces:**
- Produces `REQUIRED_SUITE_FILES`, `suite_is_initialized(suite_path: Path) -> bool`, and `suite_missing_files(suite_path: Path) -> list[str]`.
- Produces an idempotent `ensure_suite_root(suite_path: Path) -> Path` that creates only the root and state directory; DeepAgents owns framework file creation.

- [ ] Add failing tests for missing `utils/data_loader.py`, missing package initializers, and a complete suite.
- [ ] Run those tests and verify the expected failures.
- [ ] Implement path-contained suite completeness checks without using `pytest.ini` alone.
- [ ] Add tests proving an existing incomplete suite is detected as incomplete and an existing complete suite is not rewritten.
- [ ] Run the suite tests and verify they pass.

### Task 3: Create a real DeepAgents project-root agent

**Files:**
- Create: `apps/backend/app/agents/api_automation/pytest_requests/agent.py`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/__init__.py`
- Test: `apps/backend/tests/test_api_automation_deepagents_agent.py`

**Interfaces:**
- Produces `create_pytest_requests_agent(*, suite_path: Path, model, ...)` configured with the suite path as its filesystem backend root and path isolation enabled.
- Produces an invocation contract for initialization and endpoint generation using structured endpoint/case inputs, not physical paths embedded in prompts.

- [ ] Add tests that patch the DeepAgents constructor and assert the configured backend root equals the project suite path.
- [ ] Run the tests and verify they fail because the current API automation code uses `ExecutableSkill` instead of a filesystem-backed DeepAgents agent.
- [ ] Implement the agent factory using the repository's existing DeepAgents patterns and the installed `deepagents` API.
- [ ] Add the suite instructions and generation skill to the agent configuration.
- [ ] Run the agent factory tests and verify they pass.

### Task 4: Replace renderer-first generation orchestration

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/schemas.py`
- Test: `apps/backend/tests/test_api_automation_script_generator.py`

**Interfaces:**
- Produces a project-level generation entry point that resolves one suite path, locks the project, initializes/repairs the suite, invokes the filesystem-backed agent, and records changed files.
- Endpoint selection remains stable endpoint IDs plus stored cases belonging to those IDs.

- [ ] Add failing service tests for first generation, incremental generation, and an existing suite missing `utils/data_loader.py`.
- [ ] Run the tests and verify they fail under the current `is_first_time` and renderer-only flow.
- [ ] Implement orchestration around the persistent suite path and project lock.
- [ ] Keep deterministic rendering only as a migration fallback, not as the main project-structure authority.
- [ ] Ensure unselected endpoint files remain untouched.
- [ ] Run focused service tests and verify they pass.

### Task 5: Add bounded collection repair and state persistence

**Files:**
- Modify: `apps/backend/app/services/api_automation/runner.py`
- Create: `apps/backend/app/agents/api_automation/pytest_requests/collection.py`
- Modify: `apps/backend/app/services/api_automation/artifact_storage.py`
- Test: `apps/backend/tests/test_api_automation_runner.py`
- Test: `apps/backend/tests/test_api_automation_collection.py`

**Interfaces:**
- Produces `collect_suite(suite_path: Path, test_paths: list[str] | None, timeout: int) -> dict[str, Any]`.
- Produces `repair_collection_with_agent(...)` with a bounded retry count and `.deepagents/last-collection.json` state.

- [ ] Add failing tests for collection failure state, retry limit, successful second collection, and removal of inherited `VIRTUAL_ENV`.
- [ ] Run the tests and verify they fail before the collection service exists.
- [ ] Implement collection subprocess execution with project environment isolation.
- [ ] Implement state persistence for `generation_id`, status, attempts, changed files, and final error output.
- [ ] Connect the agent repair loop to collection results without executing real API requests.
- [ ] Run runner and collection tests and verify they pass.

### Task 6: Migrate existing suites and validate end-to-end generation

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/SKILL.md`
- Test: `apps/backend/tests/test_api_automation_script_generator.py`
- Test: `apps/backend/tests/test_api_automation_pytest_requests_agent.py`

**Interfaces:**
- Existing suites with `pytest.ini` but missing shared files enter initialization/repair mode.
- Successful generation requires whole-suite collection, not only the newly changed test file.

- [ ] Add a regression fixture containing `test_v1.py` importing `utils.data_loader` while the loader is missing.
- [ ] Run the regression and verify it reproduces the collection failure.
- [ ] Run initialization/repair through the project agent and verify the loader and assertion helpers are created.
- [ ] Run changed-file collection followed by whole-suite collection.
- [ ] Verify the generation result reports changed files, collection status, and suite path.
- [ ] Run all focused API automation tests and record any unrelated existing failures without modifying them.

### Task 7: Update documentation and final verification

**Files:**
- Modify: `apps/backend/README.md`
- Modify: `docs/superpowers/specs/2026-07-16-api-automation-deepagents-design.md`

- [ ] Document the one-project-one-suite model, direct DeepAgents root, initialization phase, and collection repair loop.
- [ ] Run `rtk git diff --check`.
- [ ] Run the focused API automation test suite.
- [ ] Run the backend test subset covering the changed service and agent modules.
- [ ] Inspect the final diff and verify no unrelated files are included.

