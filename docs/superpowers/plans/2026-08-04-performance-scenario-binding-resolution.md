# Performance Scenario Binding Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent unresolved scenario bindings from overwriting valid environment request headers during performance runs.

**Architecture:** Keep HTTP header names unchanged in compiled plans. Concentrate variable-name compatibility and missing-value behavior inside the generated scenario binding helpers, refresh scenario variables from the selected runtime environment using their original names, and use the existing script validator for static required-binding preflight.

**Tech Stack:** Python 3.13, Pydantic, Locust, pytest.

## Global Constraints

- Preserve exact variable-name matches before normalized `_`/`-` matching.
- Never log or include resolved secret values in errors.
- Required unresolved bindings fail before an HTTP request is sent.
- Optional unresolved bindings preserve the existing request value.
- Refresh `scenario_variables` with current environment values without creating normalized aliases.

---

### Task 1: Binding Resolution Contract

**Files:**
- Modify: `apps/backend/tests/test_performance_script_generation.py`
- Modify: `apps/backend/app/services/performance_testing/script_renderer.py`

**Interfaces:**
- Consumes: scenario binding dictionaries containing `source`, `target`, `transform`, and `required`.
- Produces: `_scenario_variable(variables, key)` and `_scenario_binding_value(binding, variables, outputs)` behavior embedded in generated Locust scripts.

- [ ] **Step 1: Write failing tests** for exact-match priority, normalized-name collisions, required missing bindings, and optional missing bindings.
- [ ] **Step 2: Run focused tests** with `uv run pytest -q tests/test_performance_script_generation.py -k "scenario"` and verify the new tests fail for the intended reasons.
- [ ] **Step 3: Implement minimal binding helpers** so collisions raise `ValueError`, required missing values raise before request execution, and optional missing values skip pointer assignment.
- [ ] **Step 4: Run focused tests** and verify they pass.

### Task 2: Runtime Environment Refresh

**Files:**
- Modify: `apps/backend/tests/test_performance_run_repo.py`
- Modify: `apps/backend/app/services/performance_testing/locust_runtime.py`

**Interfaces:**
- Consumes: `runtime.json` environment headers.
- Produces: current environment variables and headers overlaid with their original names, plus the existing request header overlay.

- [ ] **Step 1: Change the runtime-source test** to reject normalized alias injection while requiring original-name environment refresh and preserving header overlay assertions.
- [ ] **Step 2: Run the focused runtime test** and verify it fails while alias injection remains.
- [ ] **Step 3: Replace runtime alias injection** with original-name `variables` and `headers` updates.
- [ ] **Step 4: Run the focused runtime test** and verify it passes.

### Task 3: Static Binding Preflight

**Files:**
- Modify: `apps/backend/tests/test_performance_script_generation.py`
- Modify: `apps/backend/app/services/performance_testing/validator.py`

**Interfaces:**
- Consumes: rendered `LocustScriptPlan` scenario bindings.
- Produces: validation errors for unresolved required `scenario`, `environment`, `secret`, and `literal` sources while leaving dynamic `user_input` and `step_output` sources to runtime.

- [ ] **Step 1: Write a failing validator test** for an unresolved required static binding.
- [ ] **Step 2: Run the focused validator test** and verify the existing validator incorrectly accepts the plan.
- [ ] **Step 3: Add static required-binding validation** without exposing resolved values.
- [ ] **Step 4: Add and pass a dynamic `user_input` regression test** to prevent false positives.

### Task 4: Regression Verification

**Files:**
- Verify: `apps/backend/tests/test_performance_script_generation.py`
- Verify: `apps/backend/tests/test_performance_run_repo.py`

**Interfaces:**
- Consumes: rendered scenario scripts and runtime wrapper source.
- Produces: evidence that historical hyphenated environment headers resolve without silent empty-header overwrite.

- [ ] **Step 1: Run both related test files** with `uv run pytest -q tests/test_performance_run_repo.py tests/test_performance_script_generation.py`.
- [ ] **Step 2: Run `git diff --check`** for all modified files.
- [ ] **Step 3: Review the final diff** to ensure unrelated SSE changes already present in the working tree remain untouched.
