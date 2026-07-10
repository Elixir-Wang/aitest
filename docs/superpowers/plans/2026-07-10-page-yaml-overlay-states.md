# Page YAML Overlay States Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep root and overlay elements in separate nested page YAML states while making live actions overlay-first and persisting verified reusable overlay-scoped locators for POM generation.

**Architecture:** The Playwright runner owns live scope detection and produces an overlay descriptor plus verified complete locator chains. The Python runtime context remembers the last successful action and an active state stack. The snapshot checkpoint writer consumes that metadata and updates one locator-rich nested state tree without copying overlay controls into the root.

**Tech Stack:** Node.js, Playwright, Python 3.12, Pydantic, PyYAML, pytest, Node test runner.

## Global Constraints

- Root and overlay elements must never share a state.
- Persist only complete locators verified with `match_count == 1` and `visible == true` as POM-ready.
- `action_locator` is transient and must never appear in page YAML.
- Active overlays forbid fallback to same-name page elements.
- Reuse existing `children` and `triggered_by` state semantics; do not add a parallel overlay artifact model.
- Existing flattened artifacts are corrected by re-exploration, not heuristic migration.

---

### Task 1: Overlay-First Runner Contract

**Files:**
- Modify: `apps/backend/runners/playwright/browser-session.mjs`
- Test: `apps/backend/runners/playwright/browser-session.test.mjs`

**Interfaces:**
- Produces: `observe` result fields `interaction_scope`, `overlay`, and `elements[].primary_selector` containing overlay-scoped reusable locators where available.
- Produces: action resolution invariant that an active overlay is mandatory scope, not merely preferred scope.

- [ ] **Step 1: Add failing runner tests**

Add tests that create a page button and same-name overlay button, assert the overlay button receives a complete container chain, assert a missing overlay target does not click the page target, and assert two same-name overlay controls remain `locator_not_unique`.

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
node --test --test-name-pattern "overlay scoped locator|never falls back outside|ambiguous inside overlay" browser-session.test.mjs
```

Expected: at least one FAIL because snapshots do not yet expose a reusable overlay container chain and live resolution still falls back when no overlay match exists.

- [ ] **Step 3: Implement the minimal runner changes**

Return one active overlay descriptor:

```js
{
  type: "dialog" | "popover" | "menu" | "drawer",
  role: "dialog",
  name: "创建智能体",
  primary_selector: { code, verification },
  fallback_selector: { code, verification } | null,
}
```

For each overlay-owned element, verify the complete container-plus-target candidate and promote it above the global target candidate. Change visible-match resolution so an active overlay with zero matching descendants returns `not_visible` rather than page matches.

- [ ] **Step 4: Run runner tests**

Run:

```powershell
node --test browser-session.test.mjs
```

Expected: all tests PASS. If the full file exceeds the command timeout, run all test-name groups and confirm their pass counts sum to the file's declared tests.

---

### Task 2: Runtime State Transition Metadata

**Files:**
- Modify: `apps/backend/app/agents/page_exploration/playwright/schemas.py`
- Modify: `apps/backend/app/agents/page_exploration/tools/runtime_context.py`
- Modify: `apps/backend/app/agents/page_exploration/tools/extraction_tools.py`
- Test: `apps/backend/tests/agents/page_exploration/tools/test_extraction_tools.py`
- Test: `apps/backend/tests/agents/page_exploration/tools/test_navigation_tools.py`

**Interfaces:**
- Consumes: runner `interaction_scope` and `overlay` descriptor from Task 1.
- Produces: snapshot fields `state_context = {state_id, state_type, parent_state_id, triggered_by}` and `overlay`.

- [ ] **Step 1: Add failing Python contract tests**

Use a fake browser session to execute a successful click followed by an overlay snapshot. Assert the snapshot contains a child state context whose `triggered_by.element_key` identifies the clicked parent element. Add a close-overlay observation and assert the state context returns to the direct parent.

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/agents/page_exploration/tools/test_extraction_tools.py tests/agents/page_exploration/tools/test_navigation_tools.py -q
```

Expected: new assertions FAIL because runtime context currently does not retain transition metadata.

- [ ] **Step 3: Implement one session-local state tracker**

Keep the tracker private to `runtime_context.py` and reset it in `browser_session_context`. It records the most recent successful action, current state ID, and direct-parent stack. It derives stable state IDs from page ID, overlay type, parent state ID, trigger element key, and container identity. Do not expose additional mutation methods to callers.

- [ ] **Step 4: Pass state metadata through the snapshot tool**

Extend `SnapshotResult` and `playwright_snap_tool` output with `overlay` and `state_context`. Do not include either field in the per-element persisted source contract.

- [ ] **Step 5: Run Python contracts**

Run the Step 2 command. Expected: all tests PASS.

---

### Task 3: Locator-Rich Nested YAML Persistence

**Files:**
- Modify: `apps/backend/app/services/page_exploration/output_registry.py`
- Test: `apps/backend/tests/test_page_exploration_artifact_snapshot.py`
- Test: `apps/backend/tests/services/page_exploration/test_dialog_association_contract.py`
- Test: `apps/backend/tests/services/page_exploration/test_snapshot_element_artifact_contract.py`

**Interfaces:**
- Consumes: `playwright_snap_tool` output `state_context`, `overlay`, `elements`, and verified selectors.
- Produces: page YAML with root `states[]`, nested `children[]`, `triggered_by`, optional `container`, locator-rich state elements, and no `action_locator`.

- [ ] **Step 1: Add failing artifact tests**

Feed a root snapshot followed by an overlay snapshot for the same URL. Assert:

```python
root["elements"] == [root_button]
overlay = root["children"][0]
overlay["triggered_by"]["element_key"] == root_button["id"]
overlay["elements"] == [overlay_button]
"action_locator" not in yaml.safe_dump(page)
```

Also assert the overlay button's persisted primary locator contains the verified overlay container chain.

- [ ] **Step 2: Run artifact tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_page_exploration_artifact_snapshot.py tests/services/page_exploration/test_dialog_association_contract.py tests/services/page_exploration/test_snapshot_element_artifact_contract.py -q
```

Expected: new nested-state assertions FAIL against the current `snapshot-current` replacement behavior.

- [ ] **Step 3: Replace snapshot root replacement with state upsert**

Implement private helpers in `output_registry.py` to find a nested state by ID and upsert the observed state under its direct parent. A page snapshot updates a root; an overlay snapshot updates only its child. Reject overlay writes with missing or unresolved trigger metadata.

- [ ] **Step 4: Persist overlay container and assertions locally**

Write the verified overlay descriptor to `state.container`. Compute `assertion_texts` from only that state's elements and visible text evidence. Strip transient `action_locator` before locator conversion.

- [ ] **Step 5: Run artifact contracts**

Run the Step 2 command. Expected: all tests PASS.

---

### Task 4: End-to-End Contract Verification

**Files:**
- Modify only if a verified defect is found in Tasks 1-3.

**Interfaces:**
- Consumes: all prior task interfaces.
- Produces: evidence that runtime and persisted contracts agree.

- [ ] **Step 1: Run all affected Node tests**

```powershell
node --test browser-session.test.mjs locator-parser.test.mjs selector-generator.test.mjs selector-validator.test.mjs page-facts.test.mjs
```

Expected: all tests PASS, or all declared tests pass when grouped to stay within the command timeout.

- [ ] **Step 2: Run all affected Python tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/agents/page_exploration/tools tests/agents/page_exploration/integration/test_nested_states.py tests/services/page_exploration/test_artifact_reusability_contract.py tests/services/page_exploration/test_snapshot_element_artifact_contract.py tests/services/page_exploration/test_dialog_association_contract.py tests/test_page_exploration_artifact_snapshot.py -q
```

Expected: all tests PASS.

- [ ] **Step 3: Inspect a generated fixture artifact**

Confirm root and overlay names appear in separate state element lists, `triggered_by` points to the direct parent element, reusable locator chains have successful verification, and no `data-ai-testing-action-ref` appears.

- [ ] **Step 4: Review the final diff**

Run:

```powershell
git diff --check
git diff --stat
```

Expected: no whitespace errors; changes remain within the page exploration runner, runtime, persistence, tests, and approved docs.
