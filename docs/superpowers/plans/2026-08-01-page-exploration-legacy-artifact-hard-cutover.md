# Page Exploration Legacy Artifact Hard Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Schema 2.0/3.0 page-exploration artifacts, APIs, runtime dependencies, prototypes, and stale tests so production uses only Schema 4.0 pages and shared coverage.

**Architecture:** Keep the current `goal`/`autonomous` Agent and deterministic `loop` runtime, but make both read the same Schema 4.0 page index and `exploration-coverage.yaml`. Remove the parallel Operations/Replay product surface and old Loop/Coverage prototypes. Add a manifest-gated cleanup command that deletes only verified legacy artifacts after a dry run.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, PyYAML, pytest, Next.js/TypeScript, Node test runner.

## Global Constraints

- Do not modify unrelated UI automation or API automation working-tree changes.
- Do not convert Schema 2.0/3.0 artifacts to Schema 4.0.
- Do not preserve compatibility endpoints for Operations/Replay.
- Preserve Schema 4.0 pages, `exploration-coverage.yaml`, current run evidence, reports, screenshots, snapshots, and traces.
- Actual cleanup requires a previously generated manifest; default behavior is dry-run.
- Use TDD for every behavior change.

---

### Task 1: Switch Runtime to Schema 4 Coverage

**Files:**
- Modify: `apps/backend/tests/agents/page_exploration/tools/test_url_tools.py`
- Modify: `apps/backend/tests/services/page_exploration/test_timeline_tool_output_blocks.py`
- Modify: `apps/backend/tests/test_page_exploration_artifact_snapshot.py`
- Modify: `apps/backend/app/agents/page_exploration/tools/url_tools.py`
- Modify: `apps/backend/app/services/page_exploration/timeline_projection.py`
- Modify: `apps/backend/app/services/page_exploration/service.py`

**Interfaces:**
- Consumes: `load_coverage(root: Path, project_id: str) -> dict`, Schema 4.0 project page YAML.
- Produces: `check_explored_url(normalized_path, project_id, base_dir, force_reexplore=False) -> dict`.

- [ ] **Step 1: Add failing Schema 4.0 coverage tests**

Add tests proving a Schema 4.0 page and completed coverage return `explored=True`, pending operations are counted, and `force_reexplore=True` returns `explored=False`.

- [ ] **Step 2: Run URL tests and verify RED**

Run: `python -m pytest -q tests/agents/page_exploration/tools/test_url_tools.py`

Expected: FAIL because the current implementation only accepts Schema 2.0/3.0 and has no `force_reexplore` argument.

- [ ] **Step 3: Implement Schema 4.0 coverage lookup**

Read only `schema_version: "4.0"` pages, match `page.normalized_path`, load shared coverage, and return page/state/action counts. Remove all `subgoals.yaml` reading and writing helpers.

- [ ] **Step 4: Add failing no-subgoals timeline test**

Assert a completed `write_todos` projection produces plan events without creating `page_exploration/subgoals.yaml`.

- [ ] **Step 5: Run timeline test and verify RED**

Run: `python -m pytest -q tests/services/page_exploration/test_timeline_tool_output_blocks.py`

Expected: FAIL because the current projection writes `subgoals.yaml`.

- [ ] **Step 6: Remove subgoal persistence**

Delete the dynamic `write_subgoals_snapshot` import and file-write block while preserving readable plan events.

- [ ] **Step 7: Add failing artifact version assertions**

Assert run detail and report payloads expose `artifact_schema_version == 4`.

- [ ] **Step 8: Run version tests and verify RED**

Run the exact new tests; expect `3 != 4`.

- [ ] **Step 9: Return Schema version 4**

Replace both hard-coded version 3 values in `service.py` with 4.

- [ ] **Step 10: Verify Task 1 GREEN**

Run the three affected test files and expect all tests to pass.

---

### Task 2: Remove Operations and Replay

**Files:**
- Modify: `apps/backend/tests/test_page_exploration_artifact_snapshot.py`
- Modify: `apps/backend/tests/test_manual_test_case_exploration_context.py`
- Delete: `apps/backend/tests/services/page_exploration/test_replay_service.py`
- Modify: `apps/backend/app/api/v1/page_exploration/artifacts.py`
- Modify: `apps/backend/app/api/v1/page_exploration/schemas.py`
- Delete: `apps/backend/app/services/page_exploration/replay/__init__.py`
- Delete: `apps/backend/app/services/page_exploration/replay/models.py`
- Delete: `apps/backend/app/services/page_exploration/replay/run_service.py`
- Delete: `apps/backend/app/services/page_exploration/replay/service.py`
- Delete: `apps/backend/app/services/page_exploration/replay/store.py`
- Modify: `apps/backend/app/services/manual_test_case_generation/exploration_context_builder.py`
- Modify: `apps/backend/app/agents/manual_test_case_generation/schemas.py`
- Modify: manual-test-case generation prompts/tests that reference `operations`.

**Interfaces:**
- Produces: `ExplorationContext` containing only `pages` and page-derived facts.
- Removes: Operations/Replay HTTP and Python interfaces.

- [ ] **Step 1: Add failing route-removal test**

Assert the page-exploration router no longer contains routes ending in `/operations`, `/replay`, or `/replay-runs/{run_id}`.

- [ ] **Step 2: Add failing manual-context test**

Create an `operations.yaml` beside valid pages and assert generated exploration context does not expose or consume operations.

- [ ] **Step 3: Verify RED**

Run the two affected test files and confirm failures come from existing Replay routes and operation context.

- [ ] **Step 4: Delete API routes and request models**

Remove Replay imports, endpoints, and request schemas while preserving coverage/artifact/report endpoints.

- [ ] **Step 5: Delete Replay service package**

Remove all Replay implementation files and their dedicated tests.

- [ ] **Step 6: Remove operation context**

Delete `_operations_path`, `_read_operations`, operation context models, prompt rendering, and output fields.

- [ ] **Step 7: Verify Task 2 GREEN**

Run page-exploration API snapshot tests and manual-test-case exploration-context tests.

---

### Task 3: Delete Replaced Prototypes and Dead Code

**Files:**
- Modify: `apps/backend/app/agents/page_exploration_loop/__init__.py`
- Modify: `apps/backend/app/agents/page_exploration_loop/agent.py`
- Delete: `apps/backend/app/agents/page_exploration_loop/prompts/__init__.py`
- Delete: `apps/backend/app/agents/page_exploration_loop/prompts/system_prompt.py`
- Delete: `apps/backend/app/agents/page_exploration_loop/services/orchestrator.py`
- Delete: `apps/backend/app/agents/page_exploration_loop/tools/__init__.py`
- Delete: `apps/backend/app/agents/page_exploration_loop/tools/loop_tools.py`
- Delete: `apps/backend/app/agents/page_exploration/state/coverage_state.py`
- Delete: `apps/backend/app/agents/page_exploration/utils/dom_signature.py`
- Delete: `apps/backend/app/agents/page_exploration/utils/state_id.py`
- Modify: `apps/backend/app/agents/page_exploration/utils/__init__.py`
- Modify: `apps/backend/app/agents/page_exploration/prompts/system_prompt.py`
- Modify: `apps/backend/app/agents/page_exploration/tools/extraction_tools.py`
- Modify: `apps/backend/app/services/page_exploration/output_registry.py`
- Modify: `apps/backend/app/services/page_exploration/service.py`
- Modify: `apps/backend/app/api/v1/page_exploration/schemas.py`
- Delete/modify corresponding obsolete tests.

**Interfaces:**
- Preserves: `loop_action_decider(model: BaseChatModel)`.
- Removes: `page_exploration_loop_agent`, `LoopOrchestrator`, `CoverageState`, obsolete signature utilities and unreferenced helpers.

- [ ] **Step 1: Add/adjust production-path tests**

Ensure Loop runtime tests patch/use only `loop_action_decider` and deterministic service callbacks.

- [ ] **Step 2: Verify tests pass before deletion**

Run current Loop runtime and coverage-registry tests to establish the retained path.

- [ ] **Step 3: Delete prototype code and prototype-only tests**

Remove the files listed above and simplify package exports.

- [ ] **Step 4: Delete unreferenced helpers**

Remove `build_system_prompt`, `_build_match_groups`, `_find_snapshot_state`, `_upsert_snapshot_state`, `_snapshot_overlay_container`, `_snapshot_assertion_texts`, `normalize_url`, `list_run_artifacts`, and `ExplorationRunResponse` after confirming no remaining references.

- [ ] **Step 5: Verify Task 3 GREEN**

Run Loop runtime, coverage registry, extraction tools, snapshot artifact, and report Schema 4 tests.

---

### Task 4: Add Manifest-Gated Legacy Cleanup

**Files:**
- Replace: `apps/backend/app/services/page_exploration/cutover_cleanup.py`
- Create: `apps/backend/scripts/cleanup_page_exploration_legacy_artifacts.py`
- Modify: `apps/backend/tests/services/page_exploration/test_cutover_cleanup.py`

**Interfaces:**
- Produces: `build_legacy_cleanup_manifest(storage_root: Path, project_id: str | None = None) -> dict`.
- Produces: `apply_legacy_cleanup_manifest(storage_root: Path, manifest: dict) -> dict`.

- [ ] **Step 1: Write failing manifest tests**

Cover dry-run immutability, old file detection, Schema 2/3 page detection, Schema 4 preservation, project filtering, and deterministic manifest output.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q tests/services/page_exploration/test_cutover_cleanup.py`

Expected: FAIL because manifest functions do not exist.

- [ ] **Step 3: Implement manifest generation**

Resolve every path beneath `storage_root`, classify delete/rewrite/preserve entries, calculate file size and SHA-256, and never mutate the filesystem.

- [ ] **Step 4: Write failing apply tests**

Cover manifest requirement, hash/size revalidation, path traversal rejection, idempotency, Schema 4 preservation, and atomic index/coverage rewrites.

- [ ] **Step 5: Verify RED**

Run only apply tests and confirm they fail because apply is missing.

- [ ] **Step 6: Implement guarded apply**

Validate manifest storage root and every target, stage rewrite files, apply project changes atomically where possible, and report deleted/rewritten/skipped/errors.

- [ ] **Step 7: Add CLI wrapper**

Support `--dry-run`, `--apply --manifest <path>`, optional `--project-id`, JSON stdout, and non-zero exit on validation errors.

- [ ] **Step 8: Verify Task 4 GREEN**

Run cleanup tests and manually execute the CLI against a temporary storage root.

---

### Task 5: Update Frontend Contracts and Verify Cutover

**Files:**
- Modify: `apps/frontend/tests/exploration-linkable-requirement-contract.test.mjs`
- Modify: `apps/frontend/src/lib/exploration-types.ts` only if obsolete exports remain.
- Modify/delete any tests that reference removed Replay contracts.

**Interfaces:**
- Preserves exploration table actions in `exploration-runs-table.tsx`.

- [ ] **Step 1: Update stale source-contract assertions**

Read `exploration-runs-table.tsx` for edit/start/restart actions instead of requiring those actions inside `exploration-workspace.tsx`.

- [ ] **Step 2: Run frontend exploration contracts**

Run all `apps/frontend/tests/exploration-*.test.mjs`; expect all tests to pass.

- [ ] **Step 3: Run backend exploration tests**

Run agent page-exploration tests, Loop tests, page-exploration service tests, API artifact snapshot tests, and manual-test exploration-context tests.

- [ ] **Step 4: Run static residual scan**

Confirm legacy terms occur only in the cleanup implementation/tests and design/history docs:

```text
operations.yaml
subgoals.yaml
ReplayRunService
ReplayService
CoverageState
LoopOrchestrator
artifact_schema_version: 3
```

- [ ] **Step 5: Run formatting and diff checks**

Run Python compilation, relevant frontend Biome checks, and `git diff --check` without touching unrelated modified files.

- [ ] **Step 6: Review cleanup dry-run only**

Generate a manifest against configured project storage but do not run `--apply` without a separate explicit confirmation of the manifest.

