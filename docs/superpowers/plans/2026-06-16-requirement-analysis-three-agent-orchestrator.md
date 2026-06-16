# Requirement Analysis Three Agent Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the LangGraph runtime path with a simple sequential orchestrator that calls the existing understanding, quality, and clarification agents.

**Architecture:** Keep the existing three agent files and add `orchestrator.py` as the main entrypoint. Use lightweight brief and evidence models to keep downstream prompts small, while retaining full outputs for the final `RequirementAnalysisResultV2`.

**Tech Stack:** Python 3.13, Pydantic, pytest, existing LangChain agent wrappers.

---

### Task 1: Add Orchestrator Contract Tests

**Files:**
- Create: `apps/backend/tests/agents/requirement_analysis/test_three_agent_orchestrator.py`

- [ ] Write tests proving the orchestrator calls understanding, quality, and clarification in order.
- [ ] Assert the old workflow import still works.
- [ ] Run focused tests and verify they fail before production code exists.

### Task 2: Add Brief and Evidence Schemas

**Files:**
- Modify: `apps/backend/app/agents/requirement_analysis/core/schemas.py`

- [ ] Add `EvidenceSnippet`, `RequirementUnderstandingBrief`, `QualityIssueBrief`, and `QualityAssessmentBrief`.
- [ ] Export the new classes in `__all__`.
- [ ] Run focused schema import tests.

### Task 3: Add Context Builder Helpers

**Files:**
- Create: `apps/backend/app/agents/requirement_analysis/utils/context.py`

- [ ] Add helpers to build understanding brief, quality brief, and evidence snippets.
- [ ] Keep helpers deterministic and non-LLM.

### Task 4: Update Agent Runner Inputs

**Files:**
- Modify: `apps/backend/app/agents/requirement_analysis/agents/quality.py`
- Modify: `apps/backend/app/agents/requirement_analysis/agents/clarification.py`

- [ ] Allow quality runner to consume `requirement_evidence` and `understanding_brief`.
- [ ] Allow clarification runner to consume `quality_brief` and `evidence_snippets`.
- [ ] Preserve old keyword compatibility during migration.

### Task 5: Add Sequential Orchestrator

**Files:**
- Create: `apps/backend/app/agents/requirement_analysis/orchestrator.py`
- Modify: `apps/backend/app/agents/requirement_analysis/__init__.py`
- Modify: `apps/backend/app/agents/requirement_analysis/workflow/workflow.py`
- Modify: `apps/backend/app/agents/requirement_analysis/workflow/__init__.py`

- [ ] Implement `run_requirement_analysis(input_data)`.
- [ ] Generate final report and enhanced requirement deterministically.
- [ ] Keep workflow imports as compatibility shims.

### Task 6: Verify

**Files:**
- Test: `apps/backend/tests/agents/requirement_analysis/test_three_agent_orchestrator.py`
- Test: `apps/backend/tests/test_workflow_v3.py`

- [ ] Run focused tests with `uv run pytest`.
- [ ] Run compile check for the requirement analysis package.
