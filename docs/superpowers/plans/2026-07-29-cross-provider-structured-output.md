# Cross-Provider Structured Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a provider-agnostic structured-output gateway and route page exploration action decisions through tool calling with validated JSON fallback.

**Architecture:** Business code supplies messages and a Pydantic schema. The gateway first attempts a single schema-backed tool call, validates any tool arguments or textual JSON response, and falls back to a minimal JSON-only request with one corrective retry. Provider-specific `response_format` parameters are intentionally excluded until endpoint capabilities are explicitly configured.

**Tech Stack:** Python 3.12, LangChain Core, Pydantic 2, pytest.

---

### Task 1: Define gateway behavior with tests

**Files:**
- Create: `apps/backend/tests/agents/shared/test_structured_output.py`

- [ ] Test successful schema tool-call parsing.
- [ ] Test fenced JSON parsing when a tool-capable model returns text.
- [ ] Test fallback when tool binding is unsupported.
- [ ] Test one corrective retry after invalid JSON.
- [ ] Run the focused test and confirm it fails before implementation.

### Task 2: Implement the shared gateway

**Files:**
- Create: `apps/backend/app/agents/shared/structured_output.py`

- [ ] Build a compact single-tool schema from the Pydantic model.
- [ ] Parse standardized LangChain tool calls without provider-specific payload assumptions.
- [ ] Parse plain and fenced JSON and validate with Pydantic.
- [ ] Fall back to a minimal JSON-only prompt and retry validation once.
- [ ] Run the focused gateway tests until green.

### Task 3: Route ActionDecision through the gateway

**Files:**
- Modify: `apps/backend/app/agents/page_exploration_loop/agent.py`
- Modify: `apps/backend/tests/agents/page_exploration_loop/test_agent.py`

- [ ] Replace direct `with_structured_output` usage with the gateway runnable.
- [ ] Verify the decider preserves the existing `ainvoke(messages)` interface.
- [ ] Run page exploration loop agent and runtime tests.

### Task 4: Verify the integration

**Files:**
- Verify only; no broad refactors.

- [ ] Run focused structured-output and page-exploration tests.
- [ ] Run formatting or compile checks for changed Python files.
- [ ] Review the final diff and confirm unrelated user changes remain untouched.
