# API Orchestration Editor Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace case-driven API scenarios with endpoint-asset-driven orchestration, a polished structured editor, traceable data bindings, frozen publish snapshots, and step-level run diagnostics.

**Architecture:** Keep the current scenario lifecycle and transactional step replacement API, but make `endpoint_id` the source of truth for API request steps. Preserve the existing JSON storage columns where they already fit, add only `step_type` and `control_config_json`, and freeze endpoint definitions into published snapshots. Split the frontend editor into focused components managed by one editor hook; generated pytest scenario runtime writes a structured step-result artifact consumed by the existing run API.

**Tech Stack:** FastAPI, Pydantic, SQLite, pytest, generated pytest-requests runtime, Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/ui, dnd-kit, lucide-react, Node test runner.

## Global Constraints

- API request steps are created from `ApiAutomationEndpoint`, never from `ApiAutomationTestCase`.
- New scenario steps do not write `api_test_case_id`; the column remains readable only for legacy compatibility.
- Draft scenarios reference current endpoint assets; published revisions freeze endpoint snapshots.
- Default editing uses structured forms; raw JSON is only available through an advanced drawer.
- First release supports `api_request`, `condition`, `wait`, `poll`, and `assign`; cleanup is represented by `on_failure="always_run"`.
- First release does not support arbitrary graph edges, parallel branches, joins, or loop containers.
- Reuse existing dependencies and UI primitives; add no new frontend or backend package.
- Preserve existing scenario list and dedicated new/edit routes.
- Sensitive headers, cookies, tokens, and passwords must be redacted before run artifacts are persisted or returned.
- Commit steps in this plan are checkpoints only; execute them only after the user explicitly authorizes git commits.

---

## Phase 1: Correct the Backend Scenario Semantics

### Task 1: Make endpoint assets the API-step source of truth

**Files:**
- Modify: `apps/backend/app/schemas/api_automation.py:266`
- Modify: `apps/backend/app/services/api_automation/service.py:1616`
- Test: `apps/backend/tests/test_api_automation_scenarios_tasks.py`

**Interfaces:**
- Consumes: existing `ApiScenarioStepIn`, `api_automation_repo.find_endpoint`, and transactional `replace_api_scenario_steps`.
- Produces: `ApiScenarioStepIn.step_type`, `ApiScenarioStepIn.control_config`, and endpoint-driven `_prepare_scenario_step` / `_validate_scenario_definition` behavior used by later tasks.

- [ ] **Step 1: Write failing endpoint-only validation tests**

Add tests proving an API step publishes without any API test case and rejects a missing endpoint:

```python
def test_endpoint_only_scenario_validates_and_publishes(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="资料查询"), ACTOR)
    service.replace_api_scenario_steps(
        "project-1",
        scenario["id"],
        ApiScenarioStepsReplaceIn(
            steps=[
                ApiScenarioStepIn(
                    step_type="api_request",
                    endpoint_id="apiend-1",
                    name="查询资料",
                    request_overrides={"request": {"query": {"expand": "roles"}}},
                    assertions=[{"type": "status_code", "expected": 200}],
                )
            ]
        ),
        ACTOR,
    )

    validation = service.validate_api_scenario("project-1", scenario["id"], ACTOR)
    published = service.publish_api_scenario("project-1", scenario["id"], ACTOR)

    assert validation == {"valid": True, "errors": [], "warnings": []}
    assert published["steps"][0]["endpoint_id"] == "apiend-1"
    assert published["steps"][0]["api_test_case_id"] is None


def test_api_request_step_requires_project_endpoint(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="非法接口"), ACTOR)

    with pytest.raises(Exception) as error:
        service.create_api_scenario_step(
            "project-1",
            scenario["id"],
            ApiScenarioStepIn(step_type="api_request", endpoint_id="missing-endpoint"),
            ACTOR,
        )

    assert "API_ENDPOINT_INVALID" in str(error.value)
```

- [ ] **Step 2: Run the focused tests and confirm the old case requirement fails**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_scenarios_tasks.py -k "endpoint_only or requires_project_endpoint" -v
```

Expected: the endpoint-only test fails because `_validate_scenario_definition` still requires `api_test_case_id`; `step_type` and `control_config` are not yet accepted.

- [ ] **Step 3: Extend the Pydantic input contract**

Change `ApiScenarioStepIn` to:

```python
class ApiScenarioStepIn(_StrippedModel):
    id: str | None = None
    step_type: Literal["api_request", "condition", "wait", "poll", "assign"] = "api_request"
    api_test_case_id: str | None = None
    endpoint_id: str | None = None
    step_order: int = Field(default=0, ge=0)
    name: str = ""
    request_overrides: dict[str, Any] = Field(default_factory=dict)
    bindings: list[dict[str, Any]] = Field(default_factory=list)
    extractors: list[dict[str, Any]] = Field(default_factory=list)
    assertions: list[dict[str, Any]] = Field(default_factory=list)
    control_config: dict[str, Any] = Field(default_factory=dict)
    on_failure: Literal["stop", "continue", "always_run"] = "stop"
    enabled: bool = True
```

- [ ] **Step 4: Make `_prepare_scenario_step` endpoint-driven**

Implement these rules:

```python
endpoint = None
endpoint_id = payload.endpoint_id
if payload.step_type in {"api_request", "poll"}:
    endpoint = api_automation_repo.find_endpoint(db, endpoint_id) if endpoint_id else None
    if not endpoint or endpoint["project_id"] != project_id:
        raise api_error(400, "API_ENDPOINT_INVALID", "接口不存在或不属于当前项目。")
elif endpoint_id:
    raise api_error(400, "API_SCENARIO_STEP_ENDPOINT_FORBIDDEN", "当前步骤类型不能绑定接口资产。")

legacy_case_id = payload.api_test_case_id
if legacy_case_id:
    case = api_automation_repo.find_api_test_case(db, legacy_case_id)
    if not case or case["project_id"] != project_id:
        raise api_error(400, "API_TEST_CASE_INVALID", "接口用例不存在或不属于当前项目。")
    endpoint_id = endpoint_id or str(case["endpoint_id"] or "") or None

return {
    "id": step_id or payload.id or f"apistep-{secrets.token_hex(8)}",
    "step_type": payload.step_type,
    "api_test_case_id": legacy_case_id,
    "endpoint_id": endpoint_id,
    "step_order": step_order,
    "name": payload.name or (str(endpoint["summary"]) if endpoint else payload.step_type),
    "request_overrides": payload.request_overrides,
    "bindings": payload.bindings,
    "extractors": payload.extractors,
    "assertions": payload.assertions,
    "control_config": payload.control_config,
    "on_failure": payload.on_failure,
    "enabled": payload.enabled,
}
```

Do not derive a new step from an API test case. The compatibility branch only permits existing payloads to remain readable during migration.

- [ ] **Step 5: Replace the validation case requirement**

For each enabled step:

```python
if step["step_type"] in {"api_request", "poll"}:
    endpoint = api_automation_repo.find_endpoint(db, step.get("endpoint_id"))
    if not endpoint or endpoint["project_id"] != scenario["project_id"]:
        errors.append(f"{prefix}必须选择当前项目的接口资产。")
if step["step_type"] == "api_request" and not step["assertions"]:
    warnings.append(f"{prefix}没有断言。")
```

Keep the existing forward-reference validation for `bindings` and extractor-name validation.

- [ ] **Step 6: Run the backend scenario tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_scenarios_tasks.py -v
```

Expected: endpoint-only tests pass; legacy tests may still pass because compatibility reads `api_test_case_id`.

- [ ] **Step 7: Commit the semantic correction**

```powershell
git add apps/backend/app/schemas/api_automation.py apps/backend/app/services/api_automation/service.py apps/backend/tests/test_api_automation_scenarios_tasks.py
git commit -m "fix: drive API scenarios from endpoint assets"
```

### Task 2: Persist step types and control configuration

**Files:**
- Modify: `apps/backend/app/seed/schema.py:667`
- Modify: `apps/backend/app/seed/seeds.py:45`
- Modify: `apps/backend/app/services/api_automation/service.py:1632`
- Test: `apps/backend/tests/test_api_automation_schema_repo.py`
- Test: `apps/backend/tests/test_api_automation_scenarios_tasks.py`

**Interfaces:**
- Consumes: `ApiScenarioStepIn.step_type` and `control_config` from Task 1.
- Produces: persisted and serialized `step_type` / `control_config` for frontend and renderer tasks.

- [ ] **Step 1: Add a failing migration and serialization test**

```python
def test_scenario_step_schema_contains_type_and_control_config(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    with connect() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(api_scenario_steps)").fetchall()}
    assert {"step_type", "control_config_json"} <= columns
```

Extend `test_create_scenario_and_steps`:

```python
assert step["step_type"] == "api_request"
assert step["control_config"] == {}
```

- [ ] **Step 2: Verify the new tests fail**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_schema_repo.py tests/test_api_automation_scenarios_tasks.py -k "scenario_step_schema or create_scenario_and_steps" -v
```

Expected: FAIL because SQLite and serialization do not contain the fields.

- [ ] **Step 3: Add columns to fresh schema and migration**

Add to `api_scenario_steps`:

```sql
step_type TEXT NOT NULL DEFAULT 'api_request',
control_config_json TEXT NOT NULL DEFAULT '{}',
```

Add migrations:

```python
"step_type": "ALTER TABLE api_scenario_steps ADD COLUMN step_type TEXT NOT NULL DEFAULT 'api_request'",
"control_config_json": "ALTER TABLE api_scenario_steps ADD COLUMN control_config_json TEXT NOT NULL DEFAULT '{}'",
```

- [ ] **Step 4: Update insert and serialization**

`_insert_scenario_step` must write `step_type` and `control_config_json`. `_serialize_scenario_step` must return:

```python
"step_type": row["step_type"] or "api_request",
"control_config": api_automation_repo.loads_json(row["control_config_json"], {}),
```

- [ ] **Step 5: Run schema and scenario tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_schema_repo.py tests/test_api_automation_scenarios_tasks.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the persistence change**

```powershell
git add apps/backend/app/seed/schema.py apps/backend/app/seed/seeds.py apps/backend/app/services/api_automation/service.py apps/backend/tests/test_api_automation_schema_repo.py apps/backend/tests/test_api_automation_scenarios_tasks.py
git commit -m "feat: persist API scenario step types"
```

### Task 3: Freeze endpoint assets into published snapshots

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py:1756`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/renderer.py:266`
- Test: `apps/backend/tests/test_api_automation_scenarios_tasks.py`
- Test: `apps/backend/tests/test_api_automation_renderer.py`

**Interfaces:**
- Consumes: serialized endpoint-driven steps from Tasks 1-2.
- Produces: snapshot step shape `{endpoint, request_overrides, bindings, extractors, assertions, control_config}` used by generated runtime, plus scenario-level `asset_changes` for the editor header and validation UI.

- [ ] **Step 1: Write a failing snapshot test**

After publishing an endpoint-only scenario, decode `published_snapshot_json` and assert:

```python
snapshot_step = snapshot["steps"][0]
assert snapshot_step["endpoint"] == {
    "id": "apiend-1",
    "method": "GET",
    "path": "/profile",
    "summary": "用户资料",
    "parameters": [],
    "request_body": {},
    "responses": {"200": {"description": "ok"}},
    "auth": {},
}
assert "case" not in snapshot_step
```

- [ ] **Step 2: Run the snapshot test and verify failure**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_scenarios_tasks.py -k "endpoint_only_scenario" -v
```

Expected: FAIL because `_build_scenario_snapshot` still loads an API test case and writes `case`.

- [ ] **Step 3: Replace `_build_scenario_snapshot` endpoint materialization**

For `api_request` and `poll` steps, load the endpoint and add:

```python
"endpoint": {
    "id": endpoint["id"],
    "method": endpoint["method"],
    "path": endpoint["path"],
    "summary": endpoint["summary"],
    "parameters": api_automation_repo.loads_json(endpoint["parameters_json"], []),
    "request_body": api_automation_repo.loads_json(endpoint["request_body_json"], {}),
    "responses": api_automation_repo.loads_json(endpoint["responses_json"], {}),
    "auth": api_automation_repo.loads_json(endpoint["auth_json"], {}),
},
```

For non-API steps, set `endpoint` to `None`. Never read request or assertions from `api_test_cases` when producing new snapshots.

- [ ] **Step 4: Change generated runtime request construction**

Replace `case = step["case"]` with:

```python
endpoint = step.get("endpoint") or {}
state = {
    "request": _deep_merge(
        {"method": endpoint.get("method", "GET"), "path": endpoint.get("path", "")},
        copy.deepcopy(step.get("request_overrides", {}).get("request", step.get("request_overrides", {}))),
    ),
    "test_data": copy.deepcopy(step.get("request_overrides", {}).get("test_data", {})),
}
```

Assertions come only from `step.get("assertions", [])`.

- [ ] **Step 5: Add renderer coverage for endpoint snapshots**

Create a snapshot with one API step, render files, execute the generated `support/scenario.py` module with a fake client, and assert the fake client receives `GET /profile` and the configured query override.

- [ ] **Step 6: Compute endpoint asset changes against the published snapshot**

Add `_list_scenario_asset_changes(db, scenario, steps)` that compares each current endpoint's method, path, parameters, request body, responses, and auth with the matching published snapshot step. Return:

```python
{
    "step_id": step["id"],
    "endpoint_id": step["endpoint_id"],
    "change_type": "modified" | "missing",
    "fields": ["path", "parameters"],
}
```

Expose `asset_changes` from `get_api_scenario` and `validate_api_scenario`. A scenario without a published snapshot returns an empty list. Publishing refreshes the baseline and clears the changes.

- [ ] **Step 7: Require explicit confirmation before publishing changed assets**

Add:

```python
class ApiScenarioPublishIn(_StrippedModel):
    confirm_asset_changes: bool = False
```

Change the publish route and service to accept the payload. If `asset_changes` is non-empty and confirmation is false, raise `409 API_SCENARIO_ASSET_CHANGES_UNCONFIRMED`. Add backend tests for rejection without confirmation and successful publish with confirmation.

- [ ] **Step 8: Support one-time draft execution snapshots**

Extend:

```python
class ApiScenarioExecuteIn(_StrippedModel):
    api_environment_id: str
    source: Literal["published", "draft"] = "published"
```

`source="published"` keeps the current ready-state requirement and hash verification. `source="draft"` validates current steps and builds an in-memory snapshot with `_build_scenario_snapshot` without changing scenario status, revision, published snapshot, or published hash. Record the source in `execution_snapshot["scenario"]["source"]`.

- [ ] **Step 9: Run scenario and renderer tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_scenarios_tasks.py tests/test_api_automation_renderer.py -v
```

Expected: PASS.

- [ ] **Step 10: Commit frozen endpoint snapshots**

```powershell
git add apps/backend/app/services/api_automation/service.py apps/backend/app/agents/api_automation/pytest_requests/renderer.py apps/backend/tests/test_api_automation_scenarios_tasks.py apps/backend/tests/test_api_automation_renderer.py
git commit -m "feat: freeze endpoint assets in scenario revisions"
```

## Phase 2: Build the Structured High-Fidelity Editor

### Task 4: Define frontend scenario domain types and pure helpers

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts:755`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-model.mjs`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-model.d.ts`
- Create: `apps/frontend/tests/api-scenario-model.test.mjs`
- Modify: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`

**Interfaces:**
- Consumes: backend fields from Tasks 1-3.
- Produces: `ApiScenarioStepType`, `createEndpointStep`, `moveScenarioStep`, `validateScenarioDraft`, and variable option helpers used by all editor components.

- [ ] **Step 1: Update the source contract test to reject case-driven loading**

Add assertions:

```javascript
assert.doesNotMatch(scenarioEditorSource, /listApiAutomationTestCases/);
assert.match(scenarioEditorSource, /listApiAutomationEndpoints/);
assert.match(scenarioEditorSource, /ApiScenarioAssetPicker/);
assert.match(scenarioEditorSource, /ApiScenarioStepConfig/);
```

- [ ] **Step 2: Extend API client types**

```typescript
export type ApiAutomationScenarioStepType = "api_request" | "condition" | "wait" | "poll" | "assign";

export type ApiAutomationScenarioStep = {
  id: string;
  scenario_id: string;
  project_id: string;
  step_type: ApiAutomationScenarioStepType;
  endpoint_id: string | null;
  api_test_case_id: string | null;
  step_order: number;
  name: string;
  request_overrides: Record<string, unknown>;
  bindings: ApiScenarioBinding[];
  extractors: ApiScenarioExtractor[];
  assertions: ApiScenarioAssertion[];
  control_config: Record<string, unknown>;
  on_failure: "stop" | "continue" | "always_run";
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type ApiAutomationScenarioAssetChange = {
  step_id: string;
  endpoint_id: string;
  change_type: "modified" | "missing";
  fields: string[];
};
```

Define named `ApiScenarioBinding`, `ApiScenarioExtractor`, and `ApiScenarioAssertion` types instead of `Array<Record<string, unknown>>`.

- [ ] **Step 3: Create pure editor helpers**

Implement pure JavaScript in `api-scenario-model.mjs` so the browser code and Node tests execute the same functions. Declare their TypeScript signatures in `api-scenario-model.d.ts`.

`createEndpointStep(endpoint, projectId, scenarioId)` returns:

```typescript
{
  id: `apistep-${crypto.randomUUID()}`,
  scenario_id: scenarioId,
  project_id: projectId,
  step_type: "api_request",
  endpoint_id: endpoint.id,
  api_test_case_id: null,
  step_order: 0,
  name: endpoint.summary || `${endpoint.method} ${endpoint.path}`,
  request_overrides: { request: {}, test_data: {} },
  bindings: [],
  extractors: [],
  assertions: [],
  control_config: {},
  on_failure: "stop",
  enabled: true,
  created_at: "",
  updated_at: "",
}
```

`validateScenarioDraft` must return issues for missing endpoints, missing names, forward output references, duplicate extractor names, and API steps without assertions.

- [ ] **Step 4: Test pure helpers with Node test runner**

Import `createEndpointStep`, `moveScenarioStep`, `buildVariableOptions`, and `validateScenarioDraft` directly from `api-scenario-model.mjs`. Cover step creation, stable reorder, prior-output options, and forward-reference rejection.

Run:

```powershell
cd apps/frontend
node --test tests/api-scenario-model.test.mjs tests/api-automation-scenario-contract.test.mjs
```

Expected: PASS after implementation.

- [ ] **Step 5: Commit the frontend domain model**

```powershell
git add apps/frontend/src/lib/api-client.ts apps/frontend/src/components/ai-testing/api-automation/api-scenario-model.mjs apps/frontend/src/components/ai-testing/api-automation/api-scenario-model.d.ts apps/frontend/tests/api-scenario-model.test.mjs apps/frontend/tests/api-automation-scenario-contract.test.mjs
git commit -m "feat: define endpoint-driven scenario editor model"
```

### Task 5: Extract editor state into a focused hook

**Files:**
- Create: `apps/frontend/src/components/ai-testing/api-automation/use-api-scenario-editor.ts`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`
- Test: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`

**Interfaces:**
- Consumes: model helpers from Task 4 and existing API client lifecycle functions.
- Produces: `ApiScenarioEditorState` and editor actions consumed by the shell and child components.

- [ ] **Step 1: Add contract expectations for the hook boundary**

```javascript
const editorHookSource = readSource("../src/components/ai-testing/api-automation/use-api-scenario-editor.ts");
assert.match(editorHookSource, /export function useApiScenarioEditor/);
assert.match(editorHookSource, /addEndpointSteps/);
assert.match(editorHookSource, /saveScenario/);
assert.doesNotMatch(editorHookSource, /listApiAutomationTestCases/);
```

- [ ] **Step 2: Implement the hook state**

Return at least:

```typescript
{
  scenario,
  draft: { name, description, variables, steps },
  endpoints,
  environments,
  selectedEnvironmentId,
  activeStepId,
  activeStep,
  validation,
  dirty,
  loading,
  busy,
  loadError,
  actions: {
    setActiveStepId,
    updateScenarioMeta,
    addEndpointSteps,
    addUtilityStep,
    updateStep,
    removeStep,
    reorderSteps,
    saveScenario,
    validateScenario,
    publishScenario,
  executeScenario,
  },
}
```

Load only endpoints, environments, and the selected scenario. Do not load API test cases.

- [ ] **Step 3: Add bounded draft auto-save**

For an existing scenario, debounce dirty changes for 1000 milliseconds and call `saveScenario({ silent: true })`. Skip auto-save while loading, busy, or invalid JSON exists in the advanced drawer. New scenarios still require the first explicit save so navigation does not create empty records.

- [ ] **Step 4: Keep first-save route replacement behavior**

On first save create the scenario, replace steps, then call:

```typescript
router.replace(`/projects/${projectId}/automation/api/scenarios/${saved.id}`);
```

- [ ] **Step 5: Expose published and draft run actions**

`executeScenario(source: "published" | "draft")` sends the exact source to `executeApiAutomationScenario`. The header primary action runs the published revision when available; its adjacent menu offers `运行当前草稿`. A never-published scenario only offers draft execution after it has been saved and validated.

- [ ] **Step 6: Confirm endpoint asset changes before publish**

When publish returns `API_SCENARIO_ASSET_CHANGES_UNCONFIRMED`, open a confirmation dialog listing each affected step and changed field. Retrying publish sends `{ confirm_asset_changes: true }`; cancelling leaves the scenario as draft.

- [ ] **Step 7: Run contract tests and type checks**

```powershell
cd apps/frontend
node --test tests/api-automation-scenario-contract.test.mjs
npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 8: Commit the state boundary**

```powershell
git add apps/frontend/src/components/ai-testing/api-automation/use-api-scenario-editor.ts apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx apps/frontend/tests/api-automation-scenario-contract.test.mjs
git commit -m "refactor: isolate API scenario editor state"
```

### Task 6: Build the polished editor shell and sortable execution chain

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-step-list.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-step-card.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-status-bar.tsx`
- Test: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`

**Interfaces:**
- Consumes: hook state/actions from Task 5.
- Produces: two-column shell and active-step selection for configuration components.

- [ ] **Step 1: Add shell contract assertions**

Require source strings for `从接口资产添加`, `场景变量`, `版本记录`, `场景设置`, `运行场景`, and `DndContext` / `SortableContext`.

- [ ] **Step 2: Implement the high-fidelity shell**

Use:

```tsx
<section className="overflow-hidden rounded-2xl border border-border/90 bg-card shadow-[0_24px_70px_color-mix(in_srgb,var(--primary),transparent_88%)]">
  <ApiScenarioHeader
    assetChanges={assetChanges}
    busy={busy}
    dirty={dirty}
    environments={environments}
    name={draft.name}
    onEnvironmentChange={actions.setSelectedEnvironmentId}
    onNameChange={(name) => actions.updateScenarioMeta({ name })}
    onPublish={actions.publishScenario}
    onRun={actions.executeScenario}
    selectedEnvironmentId={selectedEnvironmentId}
    scenario={scenario}
  />
  <ApiScenarioSecondaryNav activeView={activeView} onViewChange={setActiveView} variableCount={Object.keys(draft.variables).length} />
  <div className="grid min-h-[620px] grid-cols-[minmax(320px,390px)_minmax(0,1fr)]">
    <ApiScenarioStepList
      activeStepId={activeStepId}
      endpoints={endpoints}
      onAddEndpoints={actions.addEndpointSteps}
      onRemoveStep={actions.removeStep}
      onReorderSteps={actions.reorderSteps}
      onSelectStep={actions.setActiveStepId}
      steps={draft.steps}
    />
    <ApiScenarioStepConfig
      activeStep={activeStep}
      endpoints={endpoints}
      environment={selectedEnvironment}
      precedingSteps={precedingSteps}
      scenarioVariables={draft.variables}
      onUpdateStep={actions.updateStep}
    />
  </div>
  <ApiScenarioStatusBar latestRun={latestRun} onExpand={() => setRunDrawerOpen(true)} />
</section>
```

Use project theme variables, not hard-coded mockup colors. HTTP method badges may use small semantic classes.

- [ ] **Step 3: Implement sortable cards with dnd-kit**

Each card displays step number, step type/method, name, path or control summary, output count, binding count, assertion count, enabled state, and overflow actions. Drag completion calls `reorderSteps(active.id, over.id)`.

- [ ] **Step 4: Add responsive behavior**

At widths below the two-column threshold, keep configuration as the main area and expose the step chain through a Sheet. Do not attempt a full mobile authoring UI.

- [ ] **Step 5: Run frontend checks**

```powershell
cd apps/frontend
node --test tests/api-automation-scenario-contract.test.mjs
npm run check -- src/components/ai-testing/api-automation/api-scenario-editor.tsx src/components/ai-testing/api-automation/api-scenario-step-list.tsx src/components/ai-testing/api-automation/api-scenario-step-card.tsx src/components/ai-testing/api-automation/api-scenario-status-bar.tsx
npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 6: Commit the editor shell**

```powershell
git add apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx apps/frontend/src/components/ai-testing/api-automation/api-scenario-step-list.tsx apps/frontend/src/components/ai-testing/api-automation/api-scenario-step-card.tsx apps/frontend/src/components/ai-testing/api-automation/api-scenario-status-bar.tsx apps/frontend/tests/api-automation-scenario-contract.test.mjs
git commit -m "feat: add polished API orchestration workspace"
```

### Task 7: Add the endpoint asset picker

**Files:**
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-asset-picker.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-endpoint-method-badge.tsx`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-step-list.tsx`
- Test: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`

**Interfaces:**
- Consumes: `ApiAutomationEndpoint[]` and `addEndpointSteps(endpointIds: string[])` from Task 5.
- Produces: ordered endpoint selection with document/tag/method/search filtering.

- [ ] **Step 1: Add source contract coverage**

Assert the picker contains `接口文档`, `搜索接口名称或路径`, `全部方法`, `添加到链路`, and receives `endpoints` instead of test cases.

- [ ] **Step 2: Implement filtering and ordered multi-select**

Maintain `selectedIds: string[]`; selecting an endpoint appends its ID, deselecting removes it. Filter by method, document ID, tags, summary, and path. Preserve selection order when calling `onConfirm(selectedIds)`.

- [ ] **Step 3: Implement the three-pane asset preview**

- Left: document and tag filters.
- Center: searchable endpoint rows.
- Right: method, path, description, parameters, request body, responses, auth, and asset updated time.

Use a Dialog on wide screens and a full-height Sheet on narrower screens.

- [ ] **Step 4: Verify no test-case language remains**

Run:

```powershell
cd apps/frontend
rg -n "添加接口用例|listApiAutomationTestCases|apiTestCases" src/components/ai-testing/api-automation
```

Expected: no matches.

- [ ] **Step 5: Run frontend checks and commit**

```powershell
cd apps/frontend
node --test tests/api-automation-scenario-contract.test.mjs
npm run check -- src/components/ai-testing/api-automation/api-scenario-asset-picker.tsx src/components/ai-testing/api-automation/api-endpoint-method-badge.tsx src/components/ai-testing/api-automation/api-scenario-step-list.tsx
npx tsc --noEmit
git add src/components/ai-testing/api-automation tests/api-automation-scenario-contract.test.mjs
git commit -m "feat: add API asset picker for scenarios"
```

### Task 8: Build structured request, variable, extractor, assertion, and control editors

**Files:**
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-step-config.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-request-editor.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-variable-picker.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-extractor-editor.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-assertion-editor.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-control-editor.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-advanced-drawer.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-variable-panel.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-settings-panel.tsx`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/renderer.py:197`
- Test: `apps/backend/tests/test_api_automation_renderer.py`
- Test: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`

**Interfaces:**
- Consumes: active step, endpoint schema, preceding steps, scenario variables, environment variables, and `updateStep`.
- Produces: valid `request_overrides`, `bindings`, `extractors`, `assertions`, and `control_config` payloads.

- [ ] **Step 1: Define binding target conventions**

Use existing JSON Pointer targets:

```text
/request/headers/Authorization
/request/query/page
/request/body/productId
/test_data/orderId
```

Use source shapes:

```typescript
{ type: "literal", value: unknown }
{ type: "scenario", name: string }
{ type: "environment", name: string }
{ type: "step_output", step_id: string, variable: string }
```

- [ ] **Step 2: Implement request fields from endpoint schema**

Normalize endpoint parameters into groups `path`, `query`, `header`, and `cookie`. Render body properties when the OpenAPI request body contains an object schema. Each row edits either a literal in `request_overrides` or a binding in `bindings`; changing source type removes the stale representation from the other collection.

- [ ] **Step 3: Implement the variable picker**

Only expose outputs from steps before the active step. Group options into preceding outputs, scenario variables, environment variables, and built-ins. Display readable labels but persist stable `step_id` and output name.

- [ ] **Step 4: Implement response extractors**

Each row edits:

```typescript
{
  name: string;
  source: "response.body" | "response.header" | "response.status";
  expression: string;
  required: boolean;
}
```

Offer schema-derived response fields first and JSONPath entry as fallback.

- [ ] **Step 5: Implement structured assertions**

Support these exact persisted assertion types:

```text
status_code
jsonpath_exists
jsonpath_equals
jsonpath_type
header_exists
header_equals
content_type
body_not_empty
body_sha256
response_time_max
schema_basic
```

Extend generated `assert_response_assertions` in this task with `jsonpath_type`, `response_time_max`, and `schema_basic`. `schema_basic` validates object/array/scalar types and required object properties using only the standard library; it does not implement the full JSON Schema specification.

- [ ] **Step 6: Implement execution control and advanced drawer**

Control editor covers enabled, timeout, retries, interval, condition, and failure policy. The advanced drawer serializes the current structured payload and validates edited JSON before applying it.

- [ ] **Step 7: Implement scenario variables and settings panels**

`ApiScenarioVariablePanel` edits named scenario variables with type-aware value inputs and duplicate-name validation. `ApiScenarioSettingsPanel` edits name, description, default timeout, and default failure policy. These panels replace the large always-visible metadata fields from the old editor.

- [ ] **Step 8: Replace raw JSON textareas in the main editor**

The default configuration area must not contain direct textareas for `bindings`, `extractors`, or `assertions`. Keep JSON only inside `ApiScenarioAdvancedDrawer`.

- [ ] **Step 9: Run checks and commit**

```powershell
cd apps/frontend
node --test tests/api-automation-scenario-contract.test.mjs tests/api-scenario-model.test.mjs
npm run check -- src/components/ai-testing/api-automation
npx tsc --noEmit
cd ../backend
uv run pytest tests/test_api_automation_renderer.py -k "assertion" -v
cd ../..
git add apps/frontend/src/components/ai-testing/api-automation apps/frontend/tests/api-automation-scenario-contract.test.mjs apps/frontend/tests/api-scenario-model.test.mjs
git add apps/backend/app/agents/api_automation/pytest_requests/renderer.py apps/backend/tests/test_api_automation_renderer.py
git commit -m "feat: add structured API scenario step editors"
```

## Phase 3: Enhanced Nodes and Step-Level Run Diagnostics

### Task 9: Execute enhanced linear step types in generated scenarios

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py:1711`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/renderer.py:299`
- Test: `apps/backend/tests/test_api_automation_scenarios_tasks.py`
- Test: `apps/backend/tests/test_api_automation_renderer.py`

**Interfaces:**
- Consumes: persisted `step_type` / `control_config` from Task 2.
- Produces: deterministic runtime behavior for `condition`, `wait`, `poll`, and `assign`.

- [ ] **Step 1: Add validation tests for each utility type**

Cover:

- `wait` requires `duration_ms` between 0 and 300000.
- `poll` requires an endpoint, `interval_ms`, `timeout_ms`, and at least one assertion.
- `condition` requires a source and supported operator.
- `assign` requires a non-empty variable name and source.

- [ ] **Step 2: Add runtime tests with a fake client and patched sleep**

Build one snapshot containing assign → condition → API request → poll → always-run cleanup. Assert skipped steps, output values, poll attempts, and cleanup execution order.

- [ ] **Step 3: Implement utility-step dispatch**

Inside `run_scenario` dispatch by `step_type`:

```python
if step_type == "assign":
    outputs[step["id"]] = {config["name"]: _resolve_source(config["source"], scenario, outputs)}
elif step_type == "condition":
    if not _evaluate_condition(config, scenario, outputs):
        continue
elif step_type == "wait":
    time.sleep(config["duration_ms"] / 1000)
elif step_type == "poll":
    response = _run_poll(api_client, step, scenario, outputs)
else:
    response = _run_api_request(api_client, step, scenario, outputs)
```

Keep one shared API request builder for `api_request` and `poll`.

- [ ] **Step 4: Run backend tests and commit**

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_scenarios_tasks.py tests/test_api_automation_renderer.py -v
git add app/services/api_automation/service.py app/agents/api_automation/pytest_requests/renderer.py tests/test_api_automation_scenarios_tasks.py tests/test_api_automation_renderer.py
git commit -m "feat: execute enhanced linear API scenario steps"
```

### Task 10: Produce and expose structured step run results

**Files:**
- Modify: `apps/backend/app/seed/schema.py:522`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/app/repositories/api_automation_repo.py:861`
- Modify: `apps/backend/app/services/api_automation/runner.py:51`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/renderer.py:299`
- Modify: `apps/backend/app/services/api_automation/service.py:1030`
- Modify: `apps/backend/app/api/v1/api_automation.py:360`
- Modify: `apps/backend/app/schemas/api_automation.py`
- Test: `apps/backend/tests/test_api_automation_scenarios_tasks.py`
- Test: `apps/backend/tests/test_api_automation_renderer.py`

**Interfaces:**
- Consumes: generated runtime execution from Task 9.
- Produces: `scenario_result_path` in run artifacts and `GET /api-runs/{run_id}/scenario-result` response.

- [ ] **Step 1: Define the result schema**

Add Pydantic output-compatible dictionaries with this shape:

```json
{
  "scenario_id": "apiscn-1",
  "status": "failed",
  "started_at": "2026-07-14T03:00:00Z",
  "finished_at": "2026-07-14T03:00:02Z",
  "duration_ms": 2410,
  "steps": [
    {
      "step_id": "apistep-1",
      "name": "创建订单",
      "step_type": "api_request",
      "status": "passed",
      "duration_ms": 681,
      "request": {},
      "response": {},
      "inputs": {},
      "outputs": {"orderId": "ORD-1"},
      "assertions": [],
      "attempts": [],
      "error": "",
      "skip_reason": ""
    }
  ]
}
```

- [ ] **Step 2: Make the generated runtime always write the artifact**

Read `API_SCENARIO_RESULT_PATH`, collect step records, redact sensitive fields, and write JSON in a `finally` block before raising the combined assertion error.

- [ ] **Step 3: Pass the result path into pytest**

In `run_script_suite`:

```python
scenario_result_path = run_dir / "scenario-result.json"
process_env["API_SCENARIO_RESULT_PATH"] = str(scenario_result_path)
```

Return `scenario_result_path` when the file exists and clear it in `_clear_previous_outputs`.

- [ ] **Step 4: Persist and expose the artifact path**

Add `scenario_result_path TEXT NOT NULL DEFAULT ''` to `api_automation_runs`, add the idempotent SQLite migration, include the field in run repository serialization, and extend `update_api_run(db, run_id, *, status, stdout_path="", stderr_path="", json_report_path="", scenario_result_path="", summary=None, error_message="", finished=False)` to persist it. Add:

```python
@router.get("/api-runs/{run_id}/scenario-result")
def get_api_scenario_run_result(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_scenario_run_result(project_id, run_id, actor)
```

Reject non-scenario runs and missing artifacts with explicit API errors.

- [ ] **Step 5: Test redaction and partial failure output**

Assert Authorization, Cookie, token, and password values do not appear in the persisted result. Assert stopped and always-run steps have distinct statuses.

- [ ] **Step 6: Run backend tests and commit**

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_scenarios_tasks.py tests/test_api_automation_renderer.py -v
git add app/services/api_automation/runner.py app/agents/api_automation/pytest_requests/renderer.py app/services/api_automation/service.py app/api/v1/api_automation.py app/schemas/api_automation.py tests/test_api_automation_scenarios_tasks.py tests/test_api_automation_renderer.py
git add app/seed/schema.py app/seed/seeds.py app/repositories/api_automation_repo.py
git commit -m "feat: expose API scenario step run results"
```

### Task 11: Add the run-results drawer to the editor

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-run-drawer.tsx`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-status-bar.tsx`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/use-api-scenario-editor.ts`
- Test: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`

**Interfaces:**
- Consumes: scenario result endpoint from Task 10.
- Produces: inline waterfall, step request/response/assertion/variable tabs, and jump-to-step action.

- [ ] **Step 1: Add API client method and types**

```typescript
export async function getApiAutomationScenarioRunResult(projectId: string, runId: string) {
  return apiRequest<ApiAutomationScenarioRunResult>(
    `/projects/${projectId}/api-automation/api-runs/${runId}/scenario-result`,
  );
}
```

Match the backend result fields exactly.

- [ ] **Step 2: Poll the created run until terminal status**

After `executeApiAutomationScenario`, poll the existing run detail endpoint with bounded backoff. When terminal, fetch the scenario result and store it in the editor hook.

- [ ] **Step 3: Build the drawer**

Use a bottom Drawer with:

- horizontal step waterfall;
- left step list and duration summary;
- tabs for failure reason, request, response, assertions, variables, and attempts;
- `回到步骤配置` calling `setActiveStepId(stepId)` and closing the drawer.

- [ ] **Step 4: Add status-bar integration**

The collapsed bar shows latest status, completed step count, total duration, and an expand action. During execution it shows live polling state without repeated Toast messages.

- [ ] **Step 5: Run frontend checks and commit**

```powershell
cd apps/frontend
node --test tests/api-automation-scenario-contract.test.mjs
npm run check -- src/components/ai-testing/api-automation src/lib/api-client.ts
npx tsc --noEmit
git add src/components/ai-testing/api-automation src/lib/api-client.ts tests/api-automation-scenario-contract.test.mjs
git commit -m "feat: add API scenario run diagnostics drawer"
```

## Phase 4: Version History, Compatibility, and Final Verification

### Task 12: Add scenario revision history and restore-as-draft

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-version-panel.tsx`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`
- Test: `apps/backend/tests/test_api_automation_scenarios_tasks.py`
- Test: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`

**Interfaces:**
- Consumes: immutable published snapshots from Task 3.
- Produces: revision list and restore endpoints plus the editor's `版本记录` panel.

- [ ] **Step 1: Add revision persistence tests**

Publish two revisions and assert both remain available after the second publish. Restore revision 1 and assert the scenario becomes `draft`, its steps match revision 1, and revision rows remain unchanged.

- [ ] **Step 2: Add `api_scenario_revisions` schema and migration**

```sql
CREATE TABLE IF NOT EXISTS api_scenario_revisions (
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL,
  snapshot_hash TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(scenario_id, revision),
  FOREIGN KEY(scenario_id) REFERENCES api_scenarios(id) ON DELETE CASCADE,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

- [ ] **Step 3: Persist a revision on every successful publish**

Insert the exact serialized snapshot and hash in the same transaction that updates `api_scenarios`. Do not overwrite prior rows.

- [ ] **Step 4: Add revision APIs**

```python
@router.get("/api-scenarios/{scenario_id}/revisions")
def list_api_scenario_revisions(
    project_id: str,
    scenario_id: str,
    actor=Depends(current_user),
) -> list[dict]:
    return service.list_api_scenario_revisions(project_id, scenario_id, actor)

@router.post("/api-scenarios/{scenario_id}/revisions/{revision}/restore")
def restore_api_scenario_revision(
    project_id: str,
    scenario_id: str,
    revision: int,
    actor=Depends(require_admin),
) -> dict:
    return service.restore_api_scenario_revision(project_id, scenario_id, revision, actor)
```

Restore scenario metadata and steps from the snapshot, keep endpoint IDs, set status to `draft`, and do not modify the currently published revision/hash until the user publishes again.

- [ ] **Step 5: Build the version panel**

Show revision number, publish time, author, step count, and current/past badge. `恢复为草稿` requires confirmation and refreshes the editor state after success.

- [ ] **Step 6: Run backend/frontend focused tests and commit**

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_scenarios_tasks.py -k "revision" -v
cd ../frontend
node --test tests/api-automation-scenario-contract.test.mjs
npx tsc --noEmit
cd ../..
git add apps/backend/app/seed/schema.py apps/backend/app/seed/seeds.py apps/backend/app/services/api_automation/service.py apps/backend/app/api/v1/api_automation.py apps/backend/tests/test_api_automation_scenarios_tasks.py
git add apps/frontend/src/lib/api-client.ts apps/frontend/src/components/ai-testing/api-automation/api-scenario-version-panel.tsx apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx apps/frontend/tests/api-automation-scenario-contract.test.mjs
git commit -m "feat: add API scenario revision history"
```

### Task 13: Migrate legacy case-backed scenarios and verify the complete workflow

**Files:**
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/tests/test_api_automation_scenarios_tasks.py`
- Modify: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`
- Modify: `docs/superpowers/specs/2026-07-14-api-orchestration-editor-redesign.md`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: backwards-compatible existing data and final acceptance evidence.

- [ ] **Step 1: Add a legacy migration test**

Seed a step with `api_test_case_id` and no `endpoint_id`, run initialization migration, and assert the step receives the case's endpoint ID while retaining the legacy case ID for audit:

```python
assert migrated["endpoint_id"] == "apiend-1"
assert migrated["api_test_case_id"] == "apitc-legacy"
```

- [ ] **Step 2: Add idempotent endpoint backfill**

In the scenario-step schema ensure function:

```sql
UPDATE api_scenario_steps
SET endpoint_id = (
  SELECT endpoint_id FROM api_test_cases WHERE api_test_cases.id = api_scenario_steps.api_test_case_id
)
WHERE endpoint_id IS NULL AND api_test_case_id IS NOT NULL;
```

Do not delete the legacy column or case records.

- [ ] **Step 3: Run the focused backend suite**

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_schema_repo.py tests/test_api_automation_scenarios_tasks.py tests/test_api_automation_renderer.py -v
```

Expected: PASS.

- [ ] **Step 4: Run frontend contracts, formatting, and type checks**

```powershell
cd apps/frontend
node --test tests/api-automation-scenario-contract.test.mjs tests/api-scenario-model.test.mjs
npm run check -- src/components/ai-testing/api-automation src/lib/api-client.ts
npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 5: Build the frontend production bundle**

```powershell
cd apps/frontend
npm run build
```

Expected: successful Next.js production build. Do not fix unrelated pre-existing failures; report them separately.

- [ ] **Step 6: Verify the workflow in Browser**

Start the frontend and backend using the repository's existing development commands, then verify:

1. Create a scenario without creating an API test case.
2. Open the asset picker and add login, create-order, and query-order endpoints.
3. Configure fixed request values through forms.
4. Extract `token` and `orderId`; reference them downstream.
5. Confirm forward references are blocked before run.
6. Publish and confirm the revision freezes endpoint snapshots.
7. Run the scenario and inspect step-level request, response, assertion, and variable data.
8. Return from a failed result to the matching step configuration.

- [ ] **Step 7: Update implementation notes in the design spec**

Record the final field names, compatibility behavior, and any deliberately deferred visual details. Do not change the approved product scope.

- [ ] **Step 8: Commit compatibility and verification updates**

```powershell
git add apps/backend/app/seed/seeds.py apps/backend/tests/test_api_automation_scenarios_tasks.py apps/frontend/tests/api-automation-scenario-contract.test.mjs docs/superpowers/specs/2026-07-14-api-orchestration-editor-redesign.md
git commit -m "test: verify endpoint-driven API orchestration"
```
