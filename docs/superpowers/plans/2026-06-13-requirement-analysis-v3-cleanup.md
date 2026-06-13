# Requirement Analysis V3 Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make requirement analysis use only the v3 runtime package and remove stale v2 implementation paths.

**Architecture:** Keep the existing document-service entrypoint, but route it to `app.agents.requirement_analysis.v3.workflow`. Move active understanding and quality agents into the v3 package, keep shared workflow schemas in non-versioned `schemas.py`, and remove old v2 service/router/agent packages.

**Tech Stack:** Python, FastAPI service layer, LangGraph, LangChain structured output, pytest.

---

### Task 1: Add Architecture Guardrails

**Files:**
- Modify: `apps/backend/tests/test_ai_agents_architecture.py`

- [x] **Step 1: Add tests for v3-only runtime**

Check that `app/agents/requirement_analysis` contains `v3`, `schemas.py`, and `utils`, while old `agent_v2.py`, `service_v2.py`, `router_v2.py`, `schemas_v2.py`, old child packages, and old v2 skill directory do not exist.

- [x] **Step 2: Verify red**

Run: `uv run pytest tests/test_ai_agents_architecture.py::test_requirement_analysis_package_only_contains_v3_runtime tests/test_ai_agents_architecture.py::test_requirement_analysis_service_uses_codex_agent_directly -q`

Expected before implementation: fail on missing `schemas.py` and old auxiliary enhancement import.

### Task 2: Move Active V3 Agent Logic

**Files:**
- Create: `apps/backend/app/agents/requirement_analysis/v3/agents/analysis.py`
- Modify: `apps/backend/app/agents/requirement_analysis/v3/nodes/understand_node.py`
- Modify: `apps/backend/app/agents/requirement_analysis/v3/nodes/quality_node.py`

- [x] **Step 1: Move understanding and quality agent functions into v3**

Copy the active understanding and quality prompt/runner logic out of the old v2 module into `v3/agents/analysis.py`.

- [x] **Step 2: Point v3 nodes at v3 agents**

Update node imports from `app.agents.requirement_analysis.agent_v2` to `app.agents.requirement_analysis.v3.agents.analysis`.

### Task 3: Rename Shared Workflow Schemas

**Files:**
- Create: `apps/backend/app/agents/requirement_analysis/schemas.py`
- Delete: `apps/backend/app/agents/requirement_analysis/schemas_v2.py`
- Modify: `apps/backend/app/agents/requirement_analysis/v3/workflow.py`
- Modify: `apps/backend/app/agents/requirement_analysis/v3/state.py`
- Modify: `apps/backend/app/agents/requirement_analysis/v3/nodes/clarify_node.py`
- Modify: `apps/backend/app/agents/requirement_analysis/v3/nodes/enhance_node.py`
- Modify: `apps/backend/app/agents/requirement_analysis/utils/*.py`
- Modify: `apps/backend/app/services/document/service.py`
- Modify: `apps/backend/tests/test_workflow_v3.py`

- [x] **Step 1: Replace `schemas_v2` imports**

Use `app.agents.requirement_analysis.schemas` as the canonical schema path.

- [x] **Step 2: Remove v2 suffix from workflow input/result types**

Rename `RequirementAnalysisInputV2` to `RequirementAnalysisInput` and `RequirementAnalysisResultV2` to `RequirementAnalysisResult`.

### Task 4: Remove Old Runtime Packages

**Files:**
- Delete: `apps/backend/app/agents/requirement_analysis/agent_v2.py`
- Delete: `apps/backend/app/agents/requirement_analysis/service_v2.py`
- Delete: `apps/backend/app/agents/requirement_analysis/router_v2.py`
- Delete: `apps/backend/app/agents/requirement_analysis/__init___v2.py`
- Delete: `apps/backend/app/agents/requirement_analysis/primary_analysis/`
- Delete: `apps/backend/app/agents/requirement_analysis/auxiliary_enhancement/`
- Delete: `apps/backend/app/agents/requirement_analysis/skills/requirement-analysis-v2/`
- Delete: `apps/backend/tests/agents/requirement_analysis/`

- [x] **Step 1: Remove files after import scan is clean**

Run `rg` for old import paths, then delete old files and tests.

### Task 5: Verify

**Files:**
- No production files.

- [x] **Step 1: Run targeted workflow/search/architecture tests**

Run: `uv run pytest tests/test_workflow_v3.py tests/test_agentic_search_v3.py tests/test_ai_agents_architecture.py::test_requirement_analysis_package_only_contains_v3_runtime tests/test_ai_agents_architecture.py::test_requirement_analysis_service_uses_codex_agent_directly -q`

Expected: pass.

- [ ] **Step 2: Run broader requirement analysis tests**

Run: `uv run pytest tests/test_agentic_search_v3.py tests/test_workflow_v3.py tests/test_requirement_analysis_agent.py tests/test_model_selection.py tests/test_ai_agents_architecture.py -q`

Expected: pass.
