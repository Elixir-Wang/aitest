# Exploration Foreign Key Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permanently repair exploration child-table foreign keys without data loss and prevent future `exploration_runs` upgrades from rewriting those foreign keys to a temporary table.

**Architecture:** Keep the existing schema-introspection migration model. Make the parent-table rebuild safe with `legacy_alter_table`, add an idempotent one-time repair that rebuilds only child tables whose foreign key target is wrong, and move the global integrity assertion to the end of system migrations with readable diagnostics.

**Tech Stack:** Python 3.13, sqlite3, pytest.

## Global Constraints

- Preserve all existing exploration rows.
- Do not mutate healthy databases beyond schema inspection.
- Repair must be transactional and idempotent.
- `PRAGMA foreign_key_check` must be empty after migration.
- Do not depend on a manually maintained migration marker.

---

### Task 1: Add Migration Regression Coverage

**Files:**
- Create: `apps/backend/tests/test_exploration_loop_mode_migration.py`

**Interfaces:**
- Consumes: `app.seed.seeds.seed_system_defaults(sqlite3.Connection)`.
- Produces: Regression coverage for legacy upgrade, damaged-schema repair, and idempotence.

- [x] Build an old schema whose `exploration_runs` CHECK constraint lacks `loop` and whose child tables contain rows.
- [x] Run `seed_system_defaults` and assert child foreign keys still reference `exploration_runs`.
- [x] Build the currently damaged schema with six child tables referencing `exploration_runs_legacy_loop_mode`.
- [x] Run `seed_system_defaults` and assert all rows survive and all six foreign keys are corrected.
- [x] Run the migration twice and assert schema SQL and row contents remain unchanged on the second run.
- [x] Run the focused tests and confirm they fail before production changes.

### Task 2: Make Parent Rebuild Safe

**Files:**
- Modify: `apps/backend/app/seed/seeds.py:33`

**Interfaces:**
- Consumes: SQLite connection with an existing `exploration_runs` table.
- Produces: `_ensure_exploration_loop_mode(db)` that never rewrites child foreign keys to its temporary table.

- [x] Commit any active transaction before changing SQLite PRAGMAs.
- [x] Enable `legacy_alter_table` before renaming the parent table.
- [x] Rebuild and copy the parent table in an explicit transaction.
- [x] Restore both PRAGMAs in `finally` even when migration fails.
- [x] Verify the old-schema upgrade regression test passes.

### Task 3: Add One-Time Schema Repair

**Files:**
- Modify: `apps/backend/app/seed/seeds.py:6`

**Interfaces:**
- Produces: `_repair_exploration_run_foreign_keys(db)` with no changes when all targets are already correct.

- [x] Detect affected tables through `PRAGMA foreign_key_list`.
- [x] Discover every affected child table through its actual SQLite foreign-key metadata.
- [x] Rebuild from each table's stored `sqlite_master` definition only when a wrong target exists.
- [x] Copy every writable column and preserve historical columns, keys, defaults, checks, unique constraints, indexes, and triggers.
- [x] Repair tables inside one transaction with foreign keys disabled.
- [x] Validate the repaired tables and roll back on any violation.
- [x] Verify damaged-schema and idempotence regression tests pass.

### Task 4: Improve Integrity Diagnostics

**Files:**
- Modify: `apps/backend/app/seed/seeds.py:6`

**Interfaces:**
- Produces: A final whole-database integrity assertion with readable violation dictionaries.

- [x] Remove the misleading whole-database assertion from the API-generation-specific migration.
- [x] Add one final `PRAGMA foreign_key_check` after all system migrations.
- [x] Format each violation as table, rowid, parent, and foreign-key id.
- [x] Run focused migration tests.
- [x] Run the relevant backend test suite and startup initialization against a copied database.
