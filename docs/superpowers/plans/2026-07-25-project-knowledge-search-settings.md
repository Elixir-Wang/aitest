# Project Knowledge Search Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project/global search-source settings and register the enabled knowledge sources as existing Agentic Search virtual directories.

**Architecture:** Keep the current knowledge query route and `StateBackend` pipeline. Persist sparse source overrides by scope, resolve the effective setting on each query, collect only enabled sources, and expose them through virtual directories. Existing Markdown assets are read directly; database records are minimally serialized into searchable text.

**Tech Stack:** FastAPI, SQLite, Pydantic, DeepAgents `StateBackend`, Next.js, TypeScript, Node test runner, pytest.

## Global Constraints

- Keep the existing company knowledge base and streaming query interfaces working.
- Store settings as `scope_key + source_type + enabled`; `__all_projects__` is the global scope.
- Directly read requirement and company-knowledge Markdown; do not add snapshots, caches, budgets, or a new RAG system.
- Include only final requirements, persisted exploration artifacts, approved test cases, and API assets/scenarios.
- Do not enumerate all virtual file paths in the Agent's initial prompt.

---

### Task 1: Persist and resolve source settings

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Create: `apps/backend/app/repositories/knowledge_search_source_settings_repo.py`
- Modify: `apps/backend/app/schemas/knowledge.py`
- Modify: `apps/backend/app/services/knowledge/service.py`
- Test: `apps/backend/tests/test_knowledge_search_settings.py`

- [ ] Write failing pytest coverage for global defaults, sparse project overrides, reset-to-global, and all-disabled rejection.
- [ ] Add the source-setting table and repository queries/upserts/deletes.
- [ ] Implement one settings resolver in the knowledge module; route and query code consume only its effective result.
- [ ] Run `pytest tests/test_knowledge_search_settings.py -q` and verify it passes.

### Task 2: Expose settings endpoints and source selectors

**Files:**
- Modify: `apps/backend/app/api/v1/knowledge.py`
- Modify: `apps/backend/app/schemas/knowledge.py`
- Modify: `apps/backend/app/services/knowledge/service.py`
- Test: `apps/backend/tests/test_knowledge_search_settings.py`

- [ ] Write failing API tests for global/project GET, PUT, and project DELETE.
- [ ] Add routes using the existing knowledge module's permission and response patterns.
- [ ] Return effective values with origin/inheritance metadata.
- [ ] Run the targeted pytest module and verify it passes.

### Task 3: Add enabled-source virtual directories

**Files:**
- Modify: `apps/backend/app/agents/knowledge/schemas.py`
- Modify: `apps/backend/app/agents/knowledge/service.py`
- Modify: `apps/backend/app/services/knowledge/service.py`
- Modify: existing repositories only when a required read query is missing
- Test: `apps/backend/tests/test_knowledge_search_settings.py`

- [ ] Write failing tests for disabled directories, direct Markdown requirements/company files, approved case filtering, and API asset/scenario serialization.
- [ ] Extend source documents and virtual path creation for requirements, explorations, test cases, API information, and company knowledge.
- [ ] Resolve settings during project and all-project queries before collecting sources.
- [ ] Change the initial agent payload to list roots/counts rather than every file path.
- [ ] Run targeted pytest coverage and verify it passes.

### Task 4: Add the search settings tab

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/app/(main)/knowledge/page.tsx`
- Test: `apps/frontend/tests/knowledge-search-settings-contract.test.mjs`

- [ ] Write failing contract checks for the third tab, current-scope settings request, source toggles, global/project labels, save, and restore behavior.
- [ ] Add typed client helpers and the `检索设置` view using existing Tabs, Switch, Button, and project context patterns.
- [ ] Do not alter company-vault behavior or existing knowledge chat controls.
- [ ] Run `node --test tests/knowledge-search-settings-contract.test.mjs` and verify it passes.

### Task 5: Regression verification

**Files:**
- Test: `apps/backend/tests/test_knowledge_search_settings.py`
- Test: `apps/frontend/tests/knowledge-search-settings-contract.test.mjs`

- [ ] Run backend targeted tests.
- [ ] Run frontend targeted and existing knowledge contract tests.
- [ ] Run `git diff --check` and inspect only files changed for this feature.
