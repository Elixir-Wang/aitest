# Exploration Report Timeline Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove tool-call execution timelines from newly generated exploration reports while preserving runtime timeline events and live progress views.

**Architecture:** Keep the existing report API and `timeline_events` input unchanged because other report sections consume those events. Remove only the final Mermaid Gantt rendering path and its private, now-unused timing helpers from the report writer.

**Tech Stack:** Python 3.12, pytest, Markdown, Mermaid

## Global Constraints

- Do not modify historical `report.md` files.
- Do not change `timeline_events.jsonl`, `raw_events.jsonl`, event projection, or live execution views.
- Do not add a configuration switch.
- Do not modify unrelated working-tree changes.

---

### Task 1: Remove the execution timeline from reports

**Files:**
- Modify: `apps/backend/tests/test_page_exploration_artifact_snapshot.py:1200`
- Modify: `apps/backend/app/services/page_exploration/report_writer.py:328`

**Interfaces:**
- Consumes: `_write_exploration_report(..., timeline_events: list[dict] | None, ...) -> Path`
- Produces: The same report path and API contract, without the execution timeline Markdown section.

- [ ] **Step 1: Add the failing report assertions**

Add these assertions to `test_write_exploration_report_includes_goal_failures_and_quality_warnings`:

```python
assert "## 执行时间线" not in content
assert "工具调用顺序与结果" not in content
assert "\ngantt\n" not in content
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
rtk pytest -q tests/test_page_exploration_artifact_snapshot.py::test_write_exploration_report_includes_goal_failures_and_quality_warnings
```

Expected: FAIL because the generated report still contains `## 执行时间线`.

- [ ] **Step 3: Remove the report timeline implementation**

In `report_writer.py`:

- Delete `_render_mermaid_gantt`.
- Delete `_build_tool_timing_map` and its unused assignment.
- Remove the fifth “执行时间线” item from `_write_exploration_report` documentation.
- Delete the final block that appends `## 执行时间线`, its description, and Mermaid output.
- Keep all `timeline_events` processing used by summaries, goals, paths, and failure diagnostics.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```powershell
rtk pytest -q tests/test_page_exploration_artifact_snapshot.py::test_write_exploration_report_includes_goal_failures_and_quality_warnings
```

Expected: PASS.

- [ ] **Step 5: Run the report regression scope**

Run:

```powershell
rtk pytest -q tests/test_page_exploration_artifact_snapshot.py -k "write_exploration_report or register_exploration_outputs"
```

Expected: all selected tests pass.

- [ ] **Step 6: Check formatting and residual references**

Run:

```powershell
rtk rg -n "_render_mermaid_gantt|_build_tool_timing_map|工具调用顺序与结果|title 探索执行时间线" apps/backend/app/services/page_exploration/report_writer.py
rtk git diff --check -- apps/backend/app/services/page_exploration/report_writer.py apps/backend/tests/test_page_exploration_artifact_snapshot.py
```

Expected: the search returns no matches and `git diff --check` succeeds.
