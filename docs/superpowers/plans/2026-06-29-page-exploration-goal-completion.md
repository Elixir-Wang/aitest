# Page Exploration Goal Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make page exploration stop and report based on observable progress instead of treating LangGraph recursion limits as business completion.

**Architecture:** Implement this incrementally. First add event persistence, technical recursion configuration, and human-readable page docs without replacing the current DeepAgent runtime. Later phases can move to a fully service-controlled decision loop and template completion evaluator.

**Tech Stack:** Python, FastAPI service layer, LangChain/DeepAgents, Playwright exploration tools, pytest.

---

### Task 1: Persist Agent Events and Configure Recursion Guard

**Files:**
- Modify: `apps/backend/app/services/exploration/page_exploration_service.py`
- Test: `apps/backend/tests/test_page_exploration_artifact_snapshot.py`

- [x] **Step 1: Write failing test**

Add `test_invoke_agent_writes_event_log_and_passes_recursion_config` to verify `events.jsonl` is written under `data/projects/{project_id}/page_exploration/runs/{run_id}/events.jsonl` and `astream_events` receives `config.recursion_limit`.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests\test_page_exploration_artifact_snapshot.py::test_invoke_agent_writes_event_log_and_passes_recursion_config -q`

Expected: fails because `_invoke_agent_with_realtime_events` does not accept `project_id` and does not persist events.

- [x] **Step 3: Implement event log and config**

Add `_ExplorationEventLog`, `_agent_recursion_config`, `_compact_agent_event`, and pass `config` into Agent invocation.

- [x] **Step 4: Verify tests pass**

Run: `uv run pytest tests\test_page_exploration_artifact_snapshot.py -q`

Expected: all tests pass.

### Task 2: Generate Human-Readable Page Docs

**Files:**
- Modify: `apps/backend/app/agents/page_exploration/tools/artifact_tools.py`
- Test: `apps/backend/tests/agents/page_exploration/tools/test_artifact_tools.py`

- [x] **Step 1: Write failing test**

Extend `test_write_page_artifact_tool_basic` to assert `page_id.md` exists next to `page_id.yaml` and includes page title, page sections, element names, and recommended locator text.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests\agents\page_exploration\tools\test_artifact_tools.py::test_write_page_artifact_tool_basic -q`

Expected: fails because Markdown doc is not created.

- [x] **Step 3: Implement doc rendering**

Add `_render_human_page_doc` and `_first_locator_code`, and write `file_path.with_suffix(".md")` whenever page YAML is written.

- [x] **Step 4: Verify tests pass**

Run: `uv run pytest tests\agents\page_exploration\tools\test_artifact_tools.py -q`

Expected: all tests pass.

### Task 3: Future Controlled Exploration Loop

**Files:**
- Create: `apps/backend/app/services/exploration/goal_classifier.py`
- Create: `apps/backend/app/services/exploration/goal_completion.py`
- Create: `apps/backend/app/services/exploration/templates.py`
- Modify: `apps/backend/app/services/exploration/page_exploration_service.py`

- [ ] **Step 1: Add template classifier**

Classify clear goals into template IDs and ambiguous goals into `page_inventory`.

- [ ] **Step 2: Add completion evaluator**

Evaluate completed, partial, and blocked states from observed page facts, written artifacts, blockers, and budgets.

- [ ] **Step 3: Replace one-shot Agent execution**

Move from one `agent.astream_events(...)` call to a service-controlled loop where each iteration requests one structured decision, executes one action, writes facts, and evaluates completion.

