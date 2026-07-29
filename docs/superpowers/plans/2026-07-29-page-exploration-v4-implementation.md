# Page Exploration V4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Schema 3.0 exploration artifacts with a compact Schema 4.0 model and let autonomous and Loop exploration share simple cross-run page, state, action, and collection-group coverage.

**Architecture:** A focused `coverage_registry` service owns the project-level `exploration-coverage.yaml`. Snapshot normalization in `output_registry` writes compact page facts, while Loop and autonomous exploration consume the shared registry through small adapters. Repeated cards are grouped by type and status, with one representative explored unless the visible action list differs.

**Tech Stack:** Python 3.12, Pydantic 2, PyYAML, pytest 9, existing Playwright exploration schemas and file locking.

## Global Constraints

- Work directly on the current `main` workspace as explicitly requested.
- Do not modify detailed test case generation or UI automation generation.
- Do not add fingerprints, expiry rules, automatic invalidation, environment matrices, or database tables.
- Do not preserve or convert Schema 3.0 project artifacts.
- Use stable semantic keys; never invent locators without snapshot evidence.
- Keep existing unrelated workspace changes untouched.
- Do not commit changes unless explicitly requested.

---

### Task 1: Shared Coverage Registry

**Files:**
- Create: `apps/backend/app/services/page_exploration/coverage_registry.py`
- Create: `apps/backend/tests/services/page_exploration/test_coverage_registry.py`

**Interfaces:**
- Produces: `load_coverage(root: Path, project_id: str) -> dict`
- Produces: `is_page_complete(coverage: dict, page_id: str) -> bool`
- Produces: `is_state_completed(coverage: dict, page_id: str, state_id: str) -> bool`
- Produces: `is_action_completed(coverage: dict, page_id: str, element_key: str, action: str) -> bool`
- Produces: `is_collection_group_completed(coverage: dict, page_id: str, collection_key: str, group_key: str) -> bool`
- Produces: `build_autonomous_coverage_summary(coverage: dict) -> dict`
- Produces: `update_coverage(root: Path, project_id: str, run_id: str, mode: str, pages: list[dict], completed_actions: list[dict], collection_groups: list[dict]) -> dict`
- Produces: `clear_page_coverage(root: Path, project_id: str, page_id: str) -> None`

- [ ] **Step 1: Write failing registry tests**

Cover missing-file defaults, completed/pending lookups, action keys, collection groups, completed-not-downgraded semantics, autonomous summary, page clearing, file locking, and atomic persistence.

- [ ] **Step 2: Run registry tests and confirm RED**

Run: `uv run pytest tests/services/page_exploration/test_coverage_registry.py -q`

Expected: FAIL because `coverage_registry` does not exist.

- [ ] **Step 3: Implement minimal registry service**

Use `FileLock`, YAML safe loading, an in-directory temporary file, and `Path.replace()` for atomic writes. Keep the persisted schema limited to page `complete/partial` and state/action/group `completed/pending`.

- [ ] **Step 4: Run registry tests and confirm GREEN**

Run: `uv run pytest tests/services/page_exploration/test_coverage_registry.py -q`

Expected: all tests pass.

---

### Task 2: Loop Coverage Reuse

**Files:**
- Modify: `apps/backend/app/services/page_exploration/loop/service.py`
- Modify: `apps/backend/app/agents/page_exploration_loop/services/frontier.py`
- Modify: `apps/backend/app/services/page_exploration/runner.py`
- Modify: `apps/backend/tests/services/page_exploration/test_loop_service_runtime.py`
- Modify: `apps/backend/tests/agents/page_exploration_loop/test_state_and_orchestrator.py`

**Interfaces:**
- Consumes: Task 1 coverage lookup functions.
- Produces: Loop candidates filtered by completed action coverage.
- Produces: optional `force_reexplore: bool = False` execution argument.
- Produces: verified transitions converted to coverage action updates after artifact merge.

- [ ] **Step 1: Write failing Loop reuse tests**

Cover completed action filtering, pending action enqueue, missing coverage behavior, force re-explore bypass, complete page reuse, and verified-only coverage updates.

- [ ] **Step 2: Run Loop tests and confirm RED**

Run: `uv run pytest tests/services/page_exploration/test_loop_service_runtime.py tests/agents/page_exploration_loop/test_state_and_orchestrator.py -q`

Expected: new tests fail because Loop does not consume project coverage.

- [ ] **Step 3: Add coverage-aware frontier filtering**

Load coverage once at Loop start, pass a completed-action predicate into candidate enqueue, skip completed candidates unless forced, and record concise reuse events.

- [ ] **Step 4: Update coverage after verified Loop results**

After page artifact merge, map verified transitions to `{page_id, element_key, action, from_state, to_state}` and persist them through Task 1.

- [ ] **Step 5: Run Loop tests and confirm GREEN**

Run: `uv run pytest tests/services/page_exploration/test_loop_service_runtime.py tests/agents/page_exploration_loop/test_state_and_orchestrator.py -q`

Expected: all tests pass.

---

### Task 3: Autonomous Coverage Context

**Files:**
- Modify: `apps/backend/app/services/page_exploration/runner.py`
- Modify: `apps/backend/app/agents/page_exploration/prompts/autonomous_system_prompt.py`
- Create: `apps/backend/tests/services/page_exploration/test_autonomous_coverage_context.py`
- Modify: `apps/backend/tests/agents/page_exploration/test_agent_modes.py`

**Interfaces:**
- Consumes: `build_autonomous_coverage_summary()` from Task 1.
- Produces: a bounded `exploration_coverage` payload in autonomous run context.
- Produces: prompt rules to skip completed pages, states, actions, and collection groups unless forced.

- [ ] **Step 1: Write failing autonomous context tests**

Cover summary injection, absence of full historical run data, pending-first guidance, force re-explore behavior, and shared visibility of Loop-completed actions.

- [ ] **Step 2: Run autonomous tests and confirm RED**

Run: `uv run pytest tests/services/page_exploration/test_autonomous_coverage_context.py tests/agents/page_exploration/test_agent_modes.py -q`

Expected: new context assertions fail.

- [ ] **Step 3: Inject compact coverage context**

Build the summary deterministically before invoking the autonomous agent and append explicit prompt rules. Do not let the model read or compare full historical artifacts.

- [ ] **Step 4: Persist autonomous verified coverage**

After autonomous output registration, update coverage from successfully persisted states and transitions using the same Task 1 service.

- [ ] **Step 5: Run autonomous tests and confirm GREEN**

Run: `uv run pytest tests/services/page_exploration/test_autonomous_coverage_context.py tests/agents/page_exploration/test_agent_modes.py -q`

Expected: all tests pass.

---

### Task 4: Compact Schema 4.0 Artifacts

**Files:**
- Create: `apps/backend/app/services/page_exploration/artifact_normalizer.py`
- Modify: `apps/backend/app/services/page_exploration/output_registry.py`
- Modify: `apps/backend/app/services/page_exploration/artifact_merge_service.py`
- Modify: `apps/backend/app/services/page_exploration/loop/loop_artifact_merge_service.py`
- Create: `apps/backend/tests/services/page_exploration/test_artifact_normalizer.py`
- Modify: `apps/backend/tests/services/page_exploration/test_snapshot_element_artifact_contract.py`
- Modify: `apps/backend/tests/test_page_exploration_artifact_snapshot.py`

**Interfaces:**
- Produces: `normalize_snapshot_artifact(snapshot: dict, existing: dict | None = None) -> dict`
- Produces: Schema 4.0 `page`, `objects`, `states`, `elements`, `collections`, `transitions`, and `quality`.
- Consumes: existing stable-key and locator extraction helpers.

- [ ] **Step 1: Write failing Schema 4.0 tests**

Cover removal of `assertion_texts`, `merge_history`, long context, empty arrays, duplicate parent/child elements, background elements in overlays, structured locators, flat states, transition referential integrity, and compact quality output.

- [ ] **Step 2: Run artifact tests and confirm RED**

Run: `uv run pytest tests/services/page_exploration/test_artifact_normalizer.py tests/services/page_exploration/test_snapshot_element_artifact_contract.py tests/test_page_exploration_artifact_snapshot.py -q`

Expected: Schema 4.0 assertions fail against current Schema 3.0 output.

- [ ] **Step 3: Implement the normalizer**

Move snapshot-to-artifact transformation into a focused module. Reuse current observed selectors, map them to structured locator fields, and reject unresolved transition references instead of guessing.

- [ ] **Step 4: Route checkpoint and final writes through Schema 4.0**

Update project page writes and merge logic to accept only Schema 4.0 output. Remove `assertion_texts` and artifact `merge_history` writes.

- [ ] **Step 5: Run artifact tests and confirm GREEN**

Run: `uv run pytest tests/services/page_exploration/test_artifact_normalizer.py tests/services/page_exploration/test_snapshot_element_artifact_contract.py tests/test_page_exploration_artifact_snapshot.py -q`

Expected: all selected tests pass.

---

### Task 5: Representative Collection Exploration

**Files:**
- Create: `apps/backend/app/services/page_exploration/collection_groups.py`
- Modify: `apps/backend/app/services/page_exploration/artifact_normalizer.py`
- Modify: `apps/backend/app/services/page_exploration/loop/service.py`
- Create: `apps/backend/tests/services/page_exploration/test_collection_groups.py`
- Modify: `apps/backend/tests/services/page_exploration/test_loop_service_runtime.py`

**Interfaces:**
- Produces: `group_collection_items(items: list[dict]) -> list[dict]`
- Produces: group keys based on `{type}:{status}` with a numeric suffix only when visible actions differ.
- Produces: one representative candidate per pending group.
- Consumes: Task 1 collection-group coverage lookup.

- [ ] **Step 1: Write failing collection grouping tests**

Cover same type/status/action deduplication, different type or status separation, different visible-action separation, representative selection, and omission of duplicate instance names.

- [ ] **Step 2: Run collection tests and confirm RED**

Run: `uv run pytest tests/services/page_exploration/test_collection_groups.py -q`

Expected: FAIL because grouping support does not exist.

- [ ] **Step 3: Implement minimal grouping**

Use only normalized `type`, `status`, and sorted visible action names. Do not create fingerprints or generic feature vectors.

- [ ] **Step 4: Filter Loop representatives and persist groups**

When snapshot elements expose collection metadata, enqueue one representative per pending group and write compact `collections` entries plus coverage completion.

- [ ] **Step 5: Run collection and Loop tests and confirm GREEN**

Run: `uv run pytest tests/services/page_exploration/test_collection_groups.py tests/services/page_exploration/test_loop_service_runtime.py -q`

Expected: all tests pass.

---

### Task 6: Cutover Cleanup and Regression Verification

**Files:**
- Create: `apps/backend/app/services/page_exploration/cutover_cleanup.py`
- Create: `apps/backend/tests/services/page_exploration/test_cutover_cleanup.py`
- Modify: `apps/backend/app/services/page_exploration/service.py` only if an explicit cleanup entry point is needed.

**Interfaces:**
- Produces: `clear_legacy_exploration_artifacts(root: Path, project_id: str) -> dict`
- Deletes only verified paths inside `<root>/<project_id>/page_exploration`.
- Does not delete project configuration, environment configuration, or authentication state.

- [ ] **Step 1: Write failing cleanup safety tests**

Cover exact deletion scope for `pages`, `runs`, `page_edges.yaml`, `operations.yaml`, lock files, `subgoals.yaml`, and coverage while preserving unrelated project files.

- [ ] **Step 2: Run cleanup tests and confirm RED**

Run: `uv run pytest tests/services/page_exploration/test_cutover_cleanup.py -q`

Expected: FAIL because cleanup service does not exist.

- [ ] **Step 3: Implement path-safe cleanup**

Resolve every target, verify it remains under the project exploration root, and use native `Path.unlink()` / `shutil.rmtree()` without shell-built delete commands.

- [ ] **Step 4: Run cleanup tests and confirm GREEN**

Run: `uv run pytest tests/services/page_exploration/test_cutover_cleanup.py -q`

Expected: all tests pass.

- [ ] **Step 5: Run focused exploration regression suite**

Run: `uv run pytest tests/services/page_exploration tests/agents/page_exploration tests/agents/page_exploration_loop tests/test_page_exploration_artifact_snapshot.py -q`

Expected: all selected tests pass with zero failures.

- [ ] **Step 6: Run formatting and static syntax checks**

Run: `uv run python -m compileall app/services/page_exploration app/agents/page_exploration app/agents/page_exploration_loop`

Expected: exit code 0.

