# Performance Script Single-Record Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove runtime endpoint validation and replace performance-script version history with one mutable current script per performance test.

**Architecture:** A performance test owns at most one script row with a stable `script_id`. Generation creates the row once and overwrites that same row on subsequent generations; confirmation and edits update it in place. Runtime consumes the confirmed script, environment, and load configuration without querying the source endpoint.

**Tech Stack:** FastAPI, SQLite, Pydantic, pytest, Next.js, TypeScript.

## Global Constraints

- Do not retain compatibility fields or fallback branches for versioned scripts.
- Do not migrate historical script versions; the new schema is the only supported model.
- Keep `script_id` because runs, analyses, and routes identify the current script by ID.
- Keep runtime environment validation because credentials and base URL are resolved at run creation.

---

### Task 1: Define single-script persistence

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/repositories/performance_script_repo.py`
- Test: `apps/backend/tests/test_performance_testing.py`

- [ ] Add failing schema and repository tests for one row per performance test.
- [ ] Remove `version`, `template_version`, `input_hash`, and superseded-state storage.
- [ ] Replace create/list/version helpers with current-script lookup and overwrite operations.
- [ ] Run focused repository and schema tests.

### Task 2: Replace versioned script service API

**Files:**
- Modify: `apps/backend/app/services/performance_testing/script_service.py`
- Modify: `apps/backend/app/api/v1/performance_tests.py`
- Modify: `apps/backend/app/schemas/performance_test.py`
- Test: `apps/backend/tests/test_performance_testing.py`

- [ ] Add failing tests proving repeated generation overwrites the stable script.
- [ ] Return one current script instead of a script-version list.
- [ ] Allow confirmed current scripts to be regenerated and edited in place.
- [ ] Remove version metadata and superseded behavior from serialized responses.
- [ ] Run focused service/API tests.

### Task 3: Remove runtime endpoint dependency

**Files:**
- Modify: `apps/backend/app/api/v1/performance_runs.py`
- Test: `apps/backend/tests/test_performance_testing.py`

- [ ] Add a failing test that creates a run after its source endpoint is deleted.
- [ ] Remove endpoint lookup and `PERFORMANCE_ENDPOINT_INVALID` from run creation.
- [ ] Keep script ownership, confirmation, and environment checks.
- [ ] Run focused run-creation tests.

### Task 4: Remove frontend version compatibility

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/script-review.tsx`
- Modify: affected performance-test pages and tests.

- [ ] Remove version fields and version-list response types.
- [ ] Load and render the single current script directly.
- [ ] Remove “new version”, version labels, and superseded-state branches.
- [ ] Run focused frontend tests and type checking.

### Task 5: Verify direct replacement

**Files:**
- Modify: all tests and seed fixtures that insert versioned script columns.

- [ ] Search for removed script-version identifiers and compatibility branches.
- [ ] Run backend performance-test suites.
- [ ] Run frontend tests and type checking.
- [ ] Inspect the final diff for unrelated changes.
