# Page Exploration Runtime Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent the page-exploration agent from creating project directories from LLM-supplied project or run identifiers.

**Architecture:** Bind the authoritative project ID, run ID, and storage root in the existing page-exploration `ContextVar` runtime. Expose only URL/path business arguments to LLM tools, remove the obsolete LLM-owned explored-URL write tool, and keep all artifact writes on deterministic server-side paths.

**Tech Stack:** Python 3.13, ContextVar, LangChain tools, pytest.

## Global Constraints

- Do not modify `.gitignore`.
- Do not trust LLM-provided project IDs, run IDs, or filesystem roots.
- Reuse the existing page-exploration runtime context module.
- Preserve the pure `check_explored_url` helper for direct service tests.
- Do not modify unrelated working-tree changes.

---

### Task 1: Lock Down Tool Interfaces

**Files:**
- Create: `apps/backend/tests/agents/page_exploration/tools/test_runtime_identity.py`
- Modify: `apps/backend/app/agents/page_exploration/tools/url_tools.py`
- Modify: `apps/backend/app/agents/page_exploration/tools/__init__.py`

**Interfaces:**
- Produces: `check_explored_url_tool(normalized_path: str) -> dict`
- Removes: `update_explored_url_tool` from the agent tool registry

- [ ] Write failing tests proving the check tool schema excludes `project_id` and `run_id`.
- [ ] Write a failing test proving the update tool is unavailable to the agent.
- [ ] Run the focused tests and confirm the current implementation fails.
- [ ] Change the tool interfaces minimally.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Bind Trusted Runtime Identity

**Files:**
- Modify: `apps/backend/app/agents/page_exploration/tools/runtime_context.py`
- Modify: `apps/backend/app/agents/page_exploration/tools/url_tools.py`
- Modify: `apps/backend/app/services/page_exploration/runner.py`
- Test: `apps/backend/tests/agents/page_exploration/tools/test_runtime_identity.py`

**Interfaces:**
- Produces: `exploration_runtime_context(project_id, run_id, storage_root)`
- Produces: `require_exploration_runtime() -> ExplorationRuntime`
- Consumes: authoritative IDs already passed to `_execute_exploration_async`

- [ ] Write failing tests for bound identity, missing context, reset behavior, and async isolation.
- [ ] Run the focused tests and confirm they fail for the expected missing API.
- [ ] Implement the immutable runtime value and context manager.
- [ ] Make the check tool resolve project and storage data only from the bound runtime.
- [ ] Bind the runtime around every agent execution in the runner.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Remove Obsolete Write State

**Files:**
- Delete: `apps/backend/app/agents/page_exploration/tools/state_tools.py`
- Delete: `apps/backend/app/agents/page_exploration/services/explored_urls_service.py`
- Delete: `apps/backend/tests/agents/page_exploration/services/test_explored_urls_service.py`
- Modify: `apps/backend/app/agents/page_exploration/skills/page-explorer/SKILL.md`

**Interfaces:**
- Removes: model-controlled writes to `explored_urls.yaml`
- Preserves: deterministic page YAML and page-index writes in the server output registry

- [ ] Verify no production consumer remains for `ExploredUrlsService`.
- [ ] Remove the obsolete tool, service, and service-only tests.
- [ ] Update skill guidance so the check tool receives only `normalized_path`.
- [ ] Search the codebase for stale imports and references.

### Task 4: Verify and Clean Historical Artifacts

**Files:**
- Delete: `apps/backend/data/projects/cybotstar-agent-exploration/`
- Delete: `apps/backend/data/projects/cybotstar-agentStore/`
- Delete: `apps/backend/data/projects/cybotstar-exploration/`

**Interfaces:**
- Consumes: completed runtime-identity fix
- Produces: repository without invalid historical project directories

- [ ] Run focused page-exploration tool tests.
- [ ] Run runner and artifact regression tests.
- [ ] Run a search proving no LLM tool accepts project or run identity.
- [ ] Delete the three invalid tracked directories.
- [ ] Re-run focused regression tests after cleanup.
