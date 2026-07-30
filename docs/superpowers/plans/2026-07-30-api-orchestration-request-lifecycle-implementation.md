# API Orchestration Request Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved compact request-lifecycle editor for API orchestration nodes without replacing the existing scenario, asset, or runtime architecture.

**Architecture:** Reuse the existing `request_overrides`, `bindings`, `extractors`, `assertions`, and `control_config` fields. Add pure frontend model helpers for lifecycle metadata and validation, reorganize the step editor into five lifecycle tabs, and extend the generated pytest runtime only where current fields are not executed.

**Tech Stack:** Next.js 16, React 19, TypeScript, Node test runner, Python, pytest, generated pytest-requests runtime.

## Global Constraints

- Preserve all existing uncommitted workspace changes.
- Do not introduce a second scenario-step API or persistence model.
- Keep the existing canvas, scenario variables, versioning, and run flows compatible.
- Use structured value sources instead of parsing display strings.
- Mask secrets in run output.
- Do not implement Postman import, plugins, collaboration, or template marketplace.
- Do not create Git commits unless explicitly requested.

---

### Task 1: Request Lifecycle Model Contracts

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-model.mjs`
- Test: `apps/frontend/tests/api-scenario-model.test.mjs`

**Interfaces:**
- Produces: expanded `ApiAutomationScenarioBinding` value-source and transform types.
- Produces: `normalizeRequestLifecycleConfig(step)` and lifecycle validation consumed by the editor.

- [ ] Add failing tests for structured source types, request lifecycle defaults, and invalid JSON/script metadata.
- [ ] Run the model tests and confirm the new tests fail.
- [ ] Extend TypeScript value-source types to match the existing backend orchestration schema.
- [ ] Add minimal normalization and validation helpers without changing persisted field names.
- [ ] Run the model tests and confirm they pass.

### Task 2: Lifecycle Step Editor

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-step-config.tsx`
- Test: `apps/frontend/tests/api-scenario-step-config-contract.test.mjs`

**Interfaces:**
- Consumes: lifecycle helpers and existing step fields.
- Produces: five tabs: `请求`, `前置处理`, `响应处理`, `断言`, `执行控制`.

- [ ] Add a failing contract test for the five tabs and request subsections.
- [ ] Run the contract test and confirm it fails.
- [ ] Reorganize the editor tabs without changing utility-step behavior.
- [ ] Add editable URL/Params, Authorization, Headers, Body, and Cookies sections using existing overrides and bindings.
- [ ] Add pre-request actions/script metadata and post-response script metadata under `control_config`.
- [ ] Keep response extraction and assertions compatible with existing saved scenarios.
- [ ] Run the contract and model tests.

### Task 3: Runtime Lifecycle Execution

**Files:**
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/renderer.py`
- Test: `apps/backend/tests/test_api_automation_scenario_runtime.py`

**Interfaces:**
- Consumes: `control_config.pre_request` and `control_config.post_response`.
- Produces: deterministic pre-request actions, post-response actions, execution conditions, retries, and lifecycle logs.

- [ ] Add failing runtime tests for pre-request variable actions, post-response variable actions, conditions, and retries.
- [ ] Run the focused pytest tests and confirm failure.
- [ ] Implement only declarative actions in the generated runtime.
- [ ] Preserve script text as validated metadata; do not execute arbitrary user code in-process.
- [ ] Apply execution condition before dispatch and retry only the configured request failures.
- [ ] Run focused runtime tests.

### Task 4: Validation and Compatibility

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-model.mjs`
- Modify: `apps/backend/app/agents/api_automation/orchestration/schemas.py` only if schema compatibility requires it.
- Test: `apps/frontend/tests/api-scenario-model.test.mjs`
- Test: `apps/backend/tests/test_api_automation_scenario_runtime.py`

**Interfaces:**
- Produces: blocking errors for malformed Body JSON, undefined references, duplicate outputs, and invalid lifecycle configuration.

- [ ] Add missing validation regression tests.
- [ ] Implement minimal validation changes.
- [ ] Run frontend model and contract tests.
- [ ] Run backend scenario runtime tests.
- [ ] Run frontend type checking or build for changed components.
- [ ] Review the final diff against the approved spec and report any intentionally deferred item.
