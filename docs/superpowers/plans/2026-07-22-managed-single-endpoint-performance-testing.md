# Managed Single-Endpoint Performance Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the deleted legacy performance-test implementation with a managed, single-endpoint Locust performance-scenario system that produces immutable run snapshots, real circuit-breaker stops, and auditable quality-gate conclusions.

**Architecture:** Persist a scenario as one V1 persona containing exactly one HTTP step, then materialize every execution into an immutable snapshot. Generate a managed Locust script from that snapshot; use a runtime observer for warmup reset and circuit breaking; import Locust results and evaluate quality gates in a separate service. The UI remains a single-endpoint workflow while consuming the new `/performance-scenarios` and `/performance-runs` contracts.

**Tech Stack:** FastAPI, Pydantic v2, SQLite, Python `csv`, Locust, `pytest`, Next.js, TypeScript, React, existing SSE stream helpers.

## Global Constraints

- Implement only V1: exactly one persona and exactly one HTTP step per scenario.
- Use new `performance_scenarios*` tables and new `/performance-scenarios` API routes; do not add migrations, compatibility adapters, dual writes, or old route aliases.
- Treat the scenario definition as editable; execute only the immutable `run_snapshot_json` stored at run creation.
- Do not store credentials, tokens, cookies, or raw sensitive headers in snapshots, events, logs, or reports.
- Only managed scripts can receive `passed` or `failed` quality-gate conclusions; no editable Python script path is part of V1.
- Use `rtk` as the prefix for all command examples.
- Do not create Git commits unless the user explicitly asks for one.

---

## File Structure

### Backend: create

- `apps/backend/app/schemas/performance_scenario.py` — Pydantic contracts for V1 scenario definitions, load profiles, run snapshots, outcomes, and gate results.
- `apps/backend/app/repositories/performance_scenario_repo.py` — SQLite persistence for scenarios and serialization.
- `apps/backend/app/services/performance_testing/snapshot_builder.py` — scenario/environment validation, load-duration calculation, secret-safe snapshot construction.
- `apps/backend/app/services/performance_testing/quality_gate.py` — pure quality-rule evaluation and normalized outcome construction.
- `apps/backend/app/services/performance_testing/managed_renderer.py` — render one managed Locust script from a snapshot.
- `apps/backend/app/services/performance_testing/runtime_observer.py` — generate the Locust wrapper source for warmup reset, circuit breaking, and structured events.
- `apps/backend/app/services/performance_testing/scenario_service.py` — scenario CRUD, request preview, and run-session creation orchestration.
- `apps/backend/app/api/v1/performance_scenarios.py` — scenario CRUD/request-preview/run-creation endpoints.
- `apps/backend/tests/test_performance_scenario_schema.py` — schema and duration-contract tests.
- `apps/backend/tests/test_performance_snapshot_builder.py` — snapshot immutability and secret-redaction tests.
- `apps/backend/tests/test_performance_quality_gate.py` — quality-gate and circuit-breaker decision tests.
- `apps/backend/tests/test_performance_scenario_api.py` — scenario and run API tests.

### Backend: modify or replace

- `apps/backend/app/seed/schema.py` — replace legacy `performance_tests*` tables with scenario, run, stats, failure, exception, event, and gate-result tables.
- `apps/backend/app/services/performance_testing/run_repo.py` — persist process status, stop reason, quality status, snapshots, gate results, and phase timestamps.
- `apps/backend/app/services/performance_testing/headless_worker.py` — start only from snapshots, calculate normalized exit codes, collect results, and invoke gate evaluation.
- `apps/backend/app/api/v1/performance_runs.py` — expose new run status, stats, events, reports, and start/stop endpoints without runtime overrides.
- `apps/backend/app/main.py` — register `performance_scenarios` router and remove legacy performance-test router registration.
- `apps/backend/tests/test_performance_run_api.py` and `apps/backend/tests/test_performance_run_repo.py` — replace legacy route/status assumptions.

### Backend: remove after replacements pass

- `apps/backend/app/schemas/performance_test.py`
- `apps/backend/app/repositories/performance_test_repo.py`
- `apps/backend/app/api/v1/performance_tests.py`
- `apps/backend/app/services/performance_testing/service.py`
- `apps/backend/app/services/performance_testing/script_renderer.py`
- `apps/backend/app/services/performance_testing/locust_runtime.py`
- `apps/backend/app/services/performance_testing/script_service.py`
- `apps/backend/app/services/performance_testing/validator.py`
- `apps/backend/app/agents/performance_testing/script_generation/`
- legacy performance script tests under `apps/backend/tests/test_performance_script_*.py`

### Frontend: modify or replace

- `apps/frontend/src/lib/api-client.ts` — replace performance-test/script contracts with scenario/run snapshot contracts.
- `apps/frontend/src/components/ai-testing/performance-testing/performance-test-form.tsx` — replace with the V1 scenario form.
- `apps/frontend/src/components/ai-testing/performance-testing/load-stage-editor.tsx` — add measured/warmup stage behavior and duration-preview display.
- `apps/frontend/src/components/ai-testing/performance-testing/performance-data-editor.tsx` — keep UI selection only; remove browser CSV parsing.
- `apps/frontend/src/components/ai-testing/performance-testing/performance-run-detail.tsx` — show process status, stop reason, quality status, phase timestamps, gates, reports, and event stream.
- `apps/frontend/src/components/ai-testing/performance-testing/performance-test-list.tsx` — consume scenario summaries and link directly to scenario/run pages.
- `apps/frontend/src/app/(main)/projects/[projectId]/performance-tests/new/page.tsx` — use the scenario form.
- `apps/frontend/src/app/(main)/projects/[projectId]/performance-tests/[testId]/scripts/[scriptId]/page.tsx` — remove; managed scripts are not user-reviewed in V1.
- `apps/frontend/tests/performance-testing-contract.test.mjs` and `apps/frontend/tests/performance-run-detail-contract.test.mjs` — replace old route and script-review assertions.

## Task 1: Define scenario, load, outcome, and snapshot contracts

**Files:**
- Create: `apps/backend/app/schemas/performance_scenario.py`
- Test: `apps/backend/tests/test_performance_scenario_schema.py`

**Interfaces:**
- Produces `PerformanceScenarioCreateIn`, `PerformanceScenarioUpdateIn`, `ScenarioDefinition`, `ManagedPersona`, `HttpStep`, `FixedLoadProfile`, `StagedLoadProfile`, `QualityGate`, `SafetyPolicy`, `RunSnapshot`, and `PerformanceRunOut`.
- Consumed by `scenario_service.py`, `snapshot_builder.py`, `managed_renderer.py`, routes, repositories, and frontend API serialization.

- [ ] **Step 1: Write failing schema tests**

```python
from pydantic import ValidationError

from app.schemas.performance_scenario import PerformanceScenarioCreateIn


def test_v1_rejects_more_than_one_persona() -> None:
    payload = valid_payload()
    payload["scenario_definition"]["personas"].append(payload["scenario_definition"]["personas"][0])

    with pytest.raises(ValidationError, match="exactly one persona"):
        PerformanceScenarioCreateIn.model_validate(payload)


def test_staged_load_requires_measured_stage_and_computes_runtime() -> None:
    payload = valid_payload(load_profile={
        "mode": "staged",
        "stages": [
            {"name": "warmup", "target_users": 10, "spawn_rate": 5, "hold_seconds": 30, "record_metrics": False},
            {"name": "measure", "target_users": 20, "spawn_rate": 5, "hold_seconds": 60, "record_metrics": True},
        ],
    })

    scenario = PerformanceScenarioCreateIn.model_validate(payload)

    assert scenario.load_profile.total_run_seconds == 94
```

- [ ] **Step 2: Run the focused schema test and verify failure**

Run: `rtk pytest tests/test_performance_scenario_schema.py -q`

Expected: FAIL because `app.schemas.performance_scenario` does not exist.

- [ ] **Step 3: Implement the Pydantic contract**

```python
class ManagedPersona(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Literal["default"] = "default"
    name: str = Field(default="默认用户", min_length=1, max_length=80)
    wait_time: WaitTime
    steps: list[HttpStep] = Field(min_length=1, max_length=1)


class ScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    personas: list[ManagedPersona] = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def require_v1_shape(self) -> "ScenarioDefinition":
        if len(self.personas) != 1:
            raise ValueError("V1 requires exactly one persona")
        if len(self.personas[0].steps) != 1:
            raise ValueError("V1 requires exactly one HTTP step")
        return self
```

Implement `FixedLoadProfile.total_run_seconds` as `ceil(target_users / spawn_rate) + warmup_seconds + measurement_seconds`. Implement `StagedLoadProfile.total_run_seconds` as the sum of each stage ramp plus hold time and reject stage sets without `record_metrics=True`.

- [ ] **Step 4: Run focused and adjacent contract tests**

Run: `rtk pytest tests/test_performance_scenario_schema.py -q`

Expected: PASS.

## Task 2: Replace legacy storage with scenario and immutable-run tables

**Files:**
- Modify: `apps/backend/app/seed/schema.py:725`
- Create: `apps/backend/app/repositories/performance_scenario_repo.py`
- Modify: `apps/backend/app/services/performance_testing/run_repo.py:23`
- Test: `apps/backend/tests/test_performance_run_repo.py`

**Interfaces:**
- Consumes contracts from Task 1.
- Produces `create_scenario`, `get_scenario`, `list_scenarios`, `update_scenario`, `create_run`, `update_run_phase`, `save_gate_results`, and `get_run`.

- [ ] **Step 1: Write failing repository tests**

```python
def test_run_snapshot_is_immutable_and_gate_results_are_queryable(db: Connection) -> None:
    scenario_repo.create_scenario(db, scenario_id="scenario-1", project_id="project-1", definition=definition())
    run_repo.create_run(db, run_id="run-1", project_id="project-1", scenario_id="scenario-1", snapshot=snapshot())

    scenario_repo.update_scenario(db, "scenario-1", {"name": "changed"})
    stored = run_repo.get_run(db, "run-1")
    run_repo.save_gate_results(db, "run-1", [gate_result("p95_response_time_ms", "failed")])

    assert json.loads(stored["run_snapshot_json"])["scenario"]["name"] == "original"
    assert run_repo.list_gate_results(db, "run-1")[0]["status"] == "failed"
```

- [ ] **Step 2: Run test and verify failure**

Run: `rtk pytest tests/test_performance_run_repo.py -q`

Expected: FAIL because scenario tables and repository functions do not exist.

- [ ] **Step 3: Replace performance schema and repositories**

Replace the legacy `performance_tests`, `performance_test_scripts`, and `performance_test_runs` DDL section with:

```sql
CREATE TABLE IF NOT EXISTS performance_scenarios (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  definition_version INTEGER NOT NULL DEFAULT 1,
  scenario_definition_json TEXT NOT NULL,
  load_profile_json TEXT NOT NULL,
  data_source_json TEXT NOT NULL,
  quality_gate_json TEXT NOT NULL,
  safety_policy_json TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS performance_run_gate_results (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  metric TEXT NOT NULL,
  operator TEXT NOT NULL,
  threshold REAL,
  actual REAL,
  status TEXT NOT NULL CHECK(status IN ('passed', 'failed', 'not_evaluated')),
  reason TEXT NOT NULL DEFAULT '',
  evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(run_id) REFERENCES performance_runs(id) ON DELETE CASCADE
);
```

Create `performance_runs` with `scenario_id`, `run_snapshot_json`, `process_status`, `stop_reason`, `quality_status`, `script_hash`, `locust_version`, phase timestamps, normalized `exit_code`, and existing report/error fields. Keep the existing stats/failure/exception/event tables but point their foreign keys to `performance_runs`.

- [ ] **Step 4: Run repository tests**

Run: `rtk pytest tests/test_performance_run_repo.py -q`

Expected: PASS.

## Task 3: Build snapshot creation and request-preview service

**Files:**
- Create: `apps/backend/app/services/performance_testing/snapshot_builder.py`
- Create: `apps/backend/app/services/performance_testing/scenario_service.py`
- Test: `apps/backend/tests/test_performance_snapshot_builder.py`

**Interfaces:**
- Consumes scenario contracts and environment/endpoint repositories.
- Produces `build_run_snapshot(scenario, environment, *, locust_version: str) -> RunSnapshot` and `create_run_session(project_id, scenario_id, actor) -> PerformanceRunOut`.

- [ ] **Step 1: Write failing snapshot tests**

```python
def test_snapshot_redacts_environment_secrets_and_freezes_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = build_run_snapshot(scenario(), environment(headers={"Authorization": "Bearer secret"}), locust_version="2.x")

    assert snapshot.runtime_environment.headers == {"Authorization": "<redacted>"}
    assert snapshot.execution.total_run_seconds == 370
    assert snapshot.script_hash


def test_snapshot_rejects_environment_concurrency_limit() -> None:
    with pytest.raises(ValueError, match="max concurrent users"):
        build_run_snapshot(scenario(target_users=101), environment(max_concurrent_users=100), locust_version="2.x")
```

- [ ] **Step 2: Run test and verify failure**

Run: `rtk pytest tests/test_performance_snapshot_builder.py -q`

Expected: FAIL because snapshot builder does not exist.

- [ ] **Step 3: Implement snapshot construction**

```python
def build_run_snapshot(scenario: PerformanceScenario, environment: ApiEnvironment, *, locust_version: str) -> RunSnapshot:
    execution = calculate_execution_plan(scenario.load_profile)
    enforce_environment_limits(environment, execution)
    runtime_environment = RuntimeEnvironment(
        api_base_url=environment.base_url,
        headers=redact_headers(environment.headers),
        credential_refs=credential_refs(environment.headers),
    )
    return RunSnapshot(
        scenario=scenario.model_copy(deep=True),
        execution=execution,
        runtime_environment=runtime_environment,
        data_hash=hash_data_source(scenario.data_source),
        locust_version=locust_version,
    )
```

`scenario_service.py` must resolve the endpoint/environment from the project, reject user-supplied sensitive headers, and persist the returned snapshot before any process starts.

- [ ] **Step 4: Run snapshot and existing endpoint-preview tests**

Run: `rtk pytest tests/test_performance_snapshot_builder.py tests/test_performance_testing.py -q`

Expected: PASS after old legacy tests are replaced in Task 8.

## Task 4: Implement managed rendering, warmup reset, and circuit breaker

**Files:**
- Create: `apps/backend/app/services/performance_testing/managed_renderer.py`
- Create: `apps/backend/app/services/performance_testing/runtime_observer.py`
- Test: `apps/backend/tests/test_performance_managed_runtime.py`

**Interfaces:**
- Consumes `RunSnapshot`.
- Produces `render_managed_locustfile(snapshot: RunSnapshot) -> str` and `render_runtime_observer(snapshot: RunSnapshot) -> str`.

- [ ] **Step 1: Write failing renderer/runtime tests**

```python
def test_managed_script_uses_one_http_user_with_snapshot_assertions() -> None:
    source = render_managed_locustfile(snapshot())

    assert "class ManagedPerformanceUser(HttpUser):" in source
    assert "catch_response=True" in source
    assert "response.failure" in source


def test_runtime_resets_once_then_stops_on_consecutive_failure_windows() -> None:
    source = render_runtime_observer(snapshot(warmup_seconds=30, circuit_breaker=policy()))

    assert "environment.runner.stats.reset_all()" in source
    assert "environment.runner.quit()" in source
    assert "circuit_breaker_triggered" in source
```

- [ ] **Step 2: Run test and verify failure**

Run: `rtk pytest tests/test_performance_managed_runtime.py -q`

Expected: FAIL because managed renderer/runtime observer do not exist.

- [ ] **Step 3: Implement source generation**

Render a single `HttpUser` with a single `@task` from `snapshot.scenario.scenario_definition.personas[0].steps[0]`. Use real JSONPath evaluation in generated source or a vetted project dependency; do not implement a dotted-path substitute.

Generate an observer that:

```python
if not state.measurement_started and elapsed >= snapshot.execution.measurement_start_seconds:
    environment.runner.stats.reset_all()
    emit_event("measurement_started", {"elapsed_seconds": elapsed})
    state.measurement_started = True

if state.measurement_started and failure_ratio_exceeded(window_stats, policy):
    state.consecutive_failure_windows += 1
    if state.consecutive_failure_windows >= policy.consecutive_windows:
        emit_event("circuit_breaker_triggered", window_stats)
        environment.runner.quit()
```

- [ ] **Step 4: Run renderer/runtime tests**

Run: `rtk pytest tests/test_performance_managed_runtime.py -q`

Expected: PASS.

## Task 5: Add independent quality-gate evaluation

**Files:**
- Create: `apps/backend/app/services/performance_testing/quality_gate.py`
- Test: `apps/backend/tests/test_performance_quality_gate.py`

**Interfaces:**
- Consumes final measured aggregate and `QualityGate`.
- Produces `evaluate_quality_gate(gate: QualityGate, summary: MeasuredSummary, *, stop_reason: str) -> QualityGateOutcome`.

- [ ] **Step 1: Write failing quality-gate tests**

```python
def test_quality_gate_returns_failed_rule_details() -> None:
    outcome = evaluate_quality_gate(
        gate(max_p95_response_time_ms=800, max_fail_ratio=0.01),
        summary(request_count=500, failure_count=9, average_response_time_ms=300, p95_response_time_ms=1280, average_rps=50),
        stop_reason="completed",
    )

    assert outcome.status == "failed"
    assert outcome.results[0].metric == "max_fail_ratio"
    assert {result.metric for result in outcome.results if result.status == "failed"} == {"max_p95_response_time_ms"}


def test_zero_measurement_requests_are_not_evaluated() -> None:
    outcome = evaluate_quality_gate(gate(max_fail_ratio=0.01), MeasuredSummary.empty(), stop_reason="completed")

    assert outcome.status == "not_evaluated"
    assert outcome.results[0].reason == "measurement window contains no requests"
```

- [ ] **Step 2: Run test and verify failure**

Run: `rtk pytest tests/test_performance_quality_gate.py -q`

Expected: FAIL because evaluator does not exist.

- [ ] **Step 3: Implement evaluator and normalized exit mapping**

```python
def normalized_exit_code(*, stop_reason: str, quality_status: str) -> int:
    if stop_reason == "circuit_breaker":
        return 11
    if stop_reason in {"engine_error", "validation_error", "timeout"}:
        return 12
    if stop_reason == "manual_stop":
        return 13
    return 10 if quality_status == "failed" else 0
```

Evaluate only measured-window data. If `stop_reason != "completed"`, return `not_evaluated` even when individual rules can be calculated. Persist one result row per configured rule.

- [ ] **Step 4: Run evaluator tests**

Run: `rtk pytest tests/test_performance_quality_gate.py -q`

Expected: PASS.

## Task 6: Rework run coordination around snapshots and outcomes

**Files:**
- Modify: `apps/backend/app/services/performance_testing/headless_worker.py:29`
- Modify: `apps/backend/app/services/performance_testing/run_repo.py:23`
- Modify: `apps/backend/app/api/v1/performance_runs.py:32`
- Test: `apps/backend/tests/test_performance_run_api.py`

**Interfaces:**
- Consumes `RunSnapshot`, managed source, observer source, and evaluator from Tasks 3–5.
- Produces immutable run creation, no-override start, event/status streams, final `QualityGateOutcome` persistence, and normalized exit codes.

- [ ] **Step 1: Write failing run API tests**

```python
def test_start_rejects_runtime_overrides(client: TestClient, created_run: str) -> None:
    response = client.post(f"/projects/project-1/performance-runs/{created_run}/start", json={"users": 500})

    assert response.status_code == 422


def test_completed_run_persists_quality_gate_failure(monkeypatch: pytest.MonkeyPatch, client: TestClient, created_run: str) -> None:
    monkeypatch.setattr(headless_worker, "collect_measured_summary", lambda *_: failed_summary())
    finish_run(created_run, return_code=0)

    response = client.get(f"/projects/project-1/performance-runs/{created_run}")

    assert response.json()["quality_status"] == "failed"
    assert response.json()["exit_code"] == 10
```

- [ ] **Step 2: Run test and verify failure**

Run: `rtk pytest tests/test_performance_run_api.py -q`

Expected: FAIL because the old run route accepts override payloads and does not persist gate results.

- [ ] **Step 3: Implement snapshot-only execution**

Build the Locust command from `snapshot.execution` only:

```python
def build_headless_command(run_dir: Path, snapshot: RunSnapshot) -> list[str]:
    return [
        sys.executable, "-m", "locust", "-f", "locustfile.py", "--headless",
        "--users", str(snapshot.execution.initial_users),
        "--spawn-rate", str(snapshot.execution.initial_spawn_rate),
        "--run-time", f"{snapshot.execution.total_run_seconds}s",
        "--stop-timeout", str(snapshot.execution.stop_timeout_seconds),
        "--exit-code-on-error", "12",
        "--csv", str(run_dir / "result"), "--csv-full-history",
        "--html", str(run_dir / "result.html"),
    ]
```

At process completion, collect reports, derive the terminal stop reason from events/process return code, evaluate gates, save gate results, save normalized exit code, and emit `quality_evaluated`.

- [ ] **Step 4: Run run API and repository tests**

Run: `rtk pytest tests/test_performance_run_api.py tests/test_performance_run_repo.py -q`

Expected: PASS.

## Task 7: Expose new scenario and run routes

**Files:**
- Create: `apps/backend/app/api/v1/performance_scenarios.py`
- Modify: `apps/backend/app/main.py`
- Test: `apps/backend/tests/test_performance_scenario_api.py`

**Interfaces:**
- Consumes `scenario_service.py` and run coordinator.
- Produces `/projects/{project_id}/performance-scenarios` CRUD, request preview, run creation, and `/projects/{project_id}/performance-runs/{run_id}` read/start/stop/stat/report/stream routes.

- [ ] **Step 1: Write failing API contract tests**

```python
def test_create_scenario_then_create_run_returns_execution_preview(client: TestClient) -> None:
    scenario = client.post("/projects/project-1/performance-scenarios", json=valid_payload()).json()
    response = client.post(f"/projects/project-1/performance-scenarios/{scenario['id']}/runs")

    assert response.status_code == 201
    assert response.json()["run"]["process_status"] == "created"
    assert response.json()["execution_preview"]["total_run_seconds"] == 370
```

- [ ] **Step 2: Run test and verify failure**

Run: `rtk pytest tests/test_performance_scenario_api.py -q`

Expected: FAIL because new routes do not exist.

- [ ] **Step 3: Implement routes and register router**

```python
router = APIRouter(prefix="/projects/{project_id}/performance-scenarios", tags=["performance-scenarios"])

@router.post("", status_code=status.HTTP_201_CREATED)
def create_scenario(project_id: str, payload: PerformanceScenarioCreateIn, actor=Depends(current_user)) -> dict:
    return scenario_service.create_scenario(project_id, payload, actor)

@router.post("/{scenario_id}/runs", status_code=status.HTTP_201_CREATED)
def create_run(project_id: str, scenario_id: str, actor=Depends(current_user)) -> dict:
    return scenario_service.create_run_session(project_id, scenario_id, actor)
```

Register the new router in `main.py`; remove the old `performance_tests` router registration and delete unused imports.

- [ ] **Step 4: Run scenario and run API tests**

Run: `rtk pytest tests/test_performance_scenario_api.py tests/test_performance_run_api.py -q`

Expected: PASS.

## Task 8: Remove the legacy performance-test and editable-script implementation

**Files:**
- Delete: legacy backend files listed in File Structure.
- Modify: imports in `apps/backend/app/api/v1/__init__.py`, `apps/backend/app/main.py`, and affected tests.
- Test: `apps/backend/tests/test_performance_scenario_api.py`

**Interfaces:**
- Leaves only new scenario/run contracts in the performance-testing package.

- [ ] **Step 1: Write import-surface regression test**

```python
def test_application_registers_scenario_routes_not_legacy_test_routes(client: TestClient) -> None:
    assert client.get("/openapi.json").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]

    assert any("/performance-scenarios" in path for path in paths)
    assert not any("/performance-tests" in path for path in paths)
```

- [ ] **Step 2: Run test and verify failure**

Run: `rtk pytest tests/test_performance_scenario_api.py::test_application_registers_scenario_routes_not_legacy_test_routes -q`

Expected: FAIL while legacy router remains registered.

- [ ] **Step 3: Delete legacy implementation and references**

Delete only the files named in File Structure after confirming the new renderer, runtime observer, scenario service, and routes cover their responsibilities. Remove imports and deleted script tests in the same change.

- [ ] **Step 4: Run backend performance suite**

Run: `rtk pytest tests/test_performance_scenario_schema.py tests/test_performance_snapshot_builder.py tests/test_performance_managed_runtime.py tests/test_performance_quality_gate.py tests/test_performance_scenario_api.py tests/test_performance_run_api.py tests/test_performance_run_repo.py -q`

Expected: PASS.

## Task 9: Replace frontend API contracts and scenario form

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts:980`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-test-form.tsx:68`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/load-stage-editor.tsx`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-data-editor.tsx:19`
- Test: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Produces TypeScript `PerformanceScenario`, `PerformanceScenarioPayload`, `PerformanceRun`, `QualityGateResult`, and API functions for the new routes.

- [ ] **Step 1: Write failing frontend contract tests**

```javascript
test("scenario form submits configurable fixed load and managed quality gates", () => {
  const source = read("src/components/ai-testing/performance-testing/performance-test-form.tsx");

  assert.match(source, /target_users/);
  assert.match(source, /warmup_seconds/);
  assert.match(source, /max_p95_response_time_ms/);
  assert.match(source, /createPerformanceScenario/);
  assert.doesNotMatch(source, /generatePerformanceScript/);
});

test("CSV data is uploaded to the backend rather than parsed with split", () => {
  const source = read("src/components/ai-testing/performance-testing/performance-data-editor.tsx");

  assert.doesNotMatch(source, /split\(","\)/);
  assert.match(source, /uploadPerformanceData/);
});
```

- [ ] **Step 2: Run test and verify failure**

Run: `rtk node --test apps/frontend/tests/performance-testing-contract.test.mjs`

Expected: FAIL because the existing form uses fixed legacy fields and browser CSV parsing.

- [ ] **Step 3: Replace types, functions, and form payload**

Implement the canonical create payload:

```ts
type PerformanceScenarioPayload = {
  name: string;
  description: string;
  api_environment_id: string;
  scenario_definition: { personas: [ManagedPersona] };
  load_profile: FixedLoadProfile | StagedLoadProfile;
  data_source: PerformanceDataSource;
  quality_gate: QualityGate;
  safety_policy: SafetyPolicy;
};
```

For fixed load render inputs for target users, spawn rate, warmup, measurement, and stop timeout. For staged load render stage rows with `record_metrics`. Display the server-returned execution preview before enabling create. Upload CSV through a backend endpoint and persist only the returned dataset reference in form state.

- [ ] **Step 4: Run frontend contract tests**

Run: `rtk node --test apps/frontend/tests/performance-testing-contract.test.mjs`

Expected: PASS.

## Task 10: Replace run workspace and remove script-review navigation

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-run-detail.tsx:5`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-test-list.tsx`
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/performance-tests/new/page.tsx`
- Delete: `apps/frontend/src/app/(main)/projects/[projectId]/performance-tests/[testId]/scripts/[scriptId]/page.tsx`
- Test: `apps/frontend/tests/performance-run-detail-contract.test.mjs`

**Interfaces:**
- Consumes scenario/run contracts from Task 9.
- Produces a direct scenario-to-run workflow with no script confirmation page.

- [ ] **Step 1: Write failing run workspace tests**

```javascript
test("run workspace shows normalized outcome and gate results", () => {
  const source = read("src/components/ai-testing/performance-testing/performance-run-detail.tsx");

  assert.match(source, /stop_reason/);
  assert.match(source, /quality_status/);
  assert.match(source, /gate_results/);
  assert.match(source, /measurement_started_at/);
});

test("new scenario flow does not navigate to script review", () => {
  const source = read("src/components/ai-testing/performance-testing/performance-test-form.tsx");

  assert.doesNotMatch(source, /\/scripts\//);
  assert.match(source, /performance-scenarios/);
});
```

- [ ] **Step 2: Run test and verify failure**

Run: `rtk node --test apps/frontend/tests/performance-run-detail-contract.test.mjs`

Expected: FAIL because the current workspace is script-centric.

- [ ] **Step 3: Implement result-focused workspace**

Show process status, stop reason, quality status, start/measurement/finish timestamps, execution preview, gate result table, failure/exception tables, streamed events, and report downloads. Use visual severity order: `passed` success, `failed` warning/error, `not_evaluated` neutral warning. Start requests have no payload; create a run first, then start its snapshot.

- [ ] **Step 4: Run run-workspace tests**

Run: `rtk node --test apps/frontend/tests/performance-run-detail-contract.test.mjs`

Expected: PASS.

## Task 11: Full verification and documentation alignment

**Files:**
- Modify: `docs/superpowers/specs/2026-07-22-managed-single-endpoint-performance-testing-spec.md` only if implementation revealed an approved specification contradiction.
- Test: backend and frontend suites below.

**Interfaces:**
- Verifies all deliverables from Tasks 1–10 as one V1 workflow.

- [ ] **Step 1: Execute backend performance suite**

Run: `rtk pytest tests/test_performance_scenario_schema.py tests/test_performance_snapshot_builder.py tests/test_performance_managed_runtime.py tests/test_performance_quality_gate.py tests/test_performance_scenario_api.py tests/test_performance_run_api.py tests/test_performance_run_repo.py -q`

Expected: PASS with no legacy performance-test imports.

- [ ] **Step 2: Execute frontend performance suite**

Run: `rtk node --test apps/frontend/tests/performance-testing-contract.test.mjs apps/frontend/tests/performance-run-detail-contract.test.mjs`

Expected: PASS.

- [ ] **Step 3: Execute focused type and application checks**

Run: `rtk npm --prefix apps/frontend run lint`

Expected: PASS.

Run: `rtk pytest tests/test_performance_scenario_api.py -q`

Expected: PASS.

- [ ] **Step 4: Perform manual acceptance run against a non-production test environment**

1. Create a fixed scenario with 10 users, 2 users/s, 5-second warmup, and 20-second measurement.
2. Confirm the preview reports 30 total seconds.
3. Run it and confirm warmup samples do not affect gate metrics.
4. Create a scenario whose target returns repeated 500 responses; confirm circuit breaker produces exit code `11` and `not_evaluated` quality status.
5. Create a scenario with P95 threshold lower than observed latency; confirm completed run produces exit code `10` and a failed P95 gate result.

Expected: all five outcomes match the stored run events, API payload, and reports.

## Plan Self-Review

### Spec coverage

- Single persona/single HTTP step: Task 1.
- No migration or legacy compatibility: Tasks 2 and 8.
- Immutable run snapshot and secret safety: Tasks 2 and 3.
- Fixed/staged duration correctness and warmup metric reset: Tasks 1, 3, and 4.
- Real circuit breaking: Task 4 and Task 6.
- Independent quality-gate conclusions and normalized exit codes: Tasks 5 and 6.
- Managed-script-only quality conclusions: Tasks 4 and 8.
- New API/UI contracts, backend CSV handling, and run result workspace: Tasks 7, 9, and 10.
- Tests and manual acceptance evidence: Task 11.

### Placeholder scan

The plan contains no `TODO`, `TBD`, legacy compatibility work, or unspecified test steps. Every task names concrete files, produced interfaces, focused commands, and expected outcomes.

### Type consistency

`RunSnapshot` is created in Task 3, rendered in Task 4, persisted/used in Task 6, returned in Task 7, and consumed by Task 9/10. `QualityGateOutcome` is created in Task 5, persisted in Task 6, exposed in Task 7, and displayed in Task 10.
