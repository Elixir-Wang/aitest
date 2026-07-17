# API Automation One Endpoint Folder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every generated API endpoint own `testcases/<normalized-path>/<method>/test_api.py` and `cases.yaml`, with backend-owned paths validated before pytest collection.

**Architecture:** Add one deterministic path function in the pytest suite module, attach its artifact manifest to each endpoint before invoking DeepAgents, and validate the exact files before collection and persistence. Keep one project-level pytest suite and shared support modules; only endpoint test/data assets move to the one-endpoint-folder layout.

**Tech Stack:** Python 3, pytest, pathlib, DeepAgents filesystem backend, SQLite repositories, uv.

## Global Constraints

- One business project owns one persistent `pytest_requests` suite.
- One endpoint is identified for artifact ownership by normalized path plus HTTP method.
- Physical paths must not contain endpoint-key or endpoint database IDs.
- The backend is the only source of truth for artifact paths.
- Endpoint generation must preserve unselected endpoint files.
- Collection must not send real API requests.
- Do not commit changes unless the user explicitly requests a commit.

---

### Task 1: Canonical Endpoint Artifact Paths

**Files:**
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/suite.py`
- Modify: `apps/backend/tests/test_api_automation_suite.py`

**Interfaces:**
- Consumes: endpoint dictionaries containing `method`, `normalized_path` or `path`.
- Produces: `endpoint_artifact_paths(endpoint: dict) -> tuple[str, str, str]`, returning endpoint directory, test file key, and data file key.

- [ ] **Step 1: Replace the stable endpoint-key test with canonical path tests**

Add tests asserting:

```python
def test_endpoint_artifact_paths_use_full_normalized_path_and_method() -> None:
    endpoint_dir, test_file, data_file = endpoint_artifact_paths(
        {
            "id": "apiend-1",
            "method": "POST",
            "path": "/ignored/path/",
            "normalized_path": "/openapi/v1/agent/analysis/",
        }
    )

    assert endpoint_dir == "testcases/openapi/v1/agent/analysis/post"
    assert test_file == f"{endpoint_dir}/test_api.py"
    assert data_file == f"{endpoint_dir}/cases.yaml"
```

Also cover path parameters, root paths, different methods on one path, unsafe segments, and unsupported methods.

- [ ] **Step 2: Run the focused suite tests and verify RED**

Run:

```powershell
rtk uv run pytest tests/test_api_automation_suite.py -q
```

Expected: FAIL because `endpoint_artifact_paths` does not exist and the old algorithm returns `test_v1.py`.

- [ ] **Step 3: Implement the canonical path function**

Implement a deterministic helper that:

```python
SUPPORTED_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def endpoint_artifact_paths(endpoint: dict) -> tuple[str, str, str]:
    method = str(endpoint.get("method", "")).strip().lower()
    normalized_path = str(endpoint.get("normalized_path") or endpoint.get("path") or "")
    segments = _normalized_endpoint_segments(normalized_path)
    endpoint_dir = "/".join(["testcases", *(segments or ["root"]), method])
    return endpoint_dir, f"{endpoint_dir}/test_api.py", f"{endpoint_dir}/cases.yaml"
```

Path parameter segments such as `{user_id}` become `by_user_id`. Reject unsafe `.` and `..` segments and unsupported methods with `ValueError`.

- [ ] **Step 4: Run the focused suite tests and verify GREEN**

Run:

```powershell
rtk uv run pytest tests/test_api_automation_suite.py -q
```

Expected: all suite tests pass.

---

### Task 2: Backend-Owned Agent Artifact Manifest

**Files:**
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/agent.py`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/AGENTS.md`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/SKILL.md`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/references/project-structure.md`
- Modify: `apps/backend/tests/test_api_automation_deepagents_agent.py`

**Interfaces:**
- Consumes: endpoint payloads containing `artifacts.directory`, `artifacts.test_file`, and `artifacts.data_file`.
- Produces: an Agent prompt that treats those paths as mandatory output targets.

- [ ] **Step 1: Add failing prompt-contract tests**

Extend the DeepAgents tests with a fake agent and assert the endpoint-generation message contains the exact artifact manifest and explicitly forbids alternative endpoint files.

- [ ] **Step 2: Run the Agent tests and verify RED**

Run:

```powershell
rtk uv run pytest tests/test_api_automation_deepagents_agent.py -q
```

Expected: FAIL because the current prompt does not declare backend-provided artifact paths mandatory.

- [ ] **Step 3: Update Agent and generated-suite instructions**

State that:

```text
testcases/<normalized-path>/<method>/test_api.py
testcases/<normalized-path>/<method>/cases.yaml
```

are backend-owned targets, each selected endpoint must write only its supplied files, and alternative names such as `test_agent.py` or `test_v1.py` are invalid.

- [ ] **Step 4: Run the Agent tests and verify GREEN**

Run the same focused test command and expect all tests to pass.

---

### Task 3: Service Artifact Validation and Collection

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py`
- Create: `apps/backend/tests/test_api_automation_script_generation_paths.py`

**Interfaces:**
- Consumes: `endpoint_artifact_paths()` and generated suite files.
- Produces: `_validate_generated_endpoint_artifacts(...)` and canonical collection targets.

- [ ] **Step 1: Add failing service regression tests**

Cover:

```python
def test_generation_passes_canonical_artifacts_to_agent(...): ...
def test_generation_fails_before_collection_when_test_file_missing(...): ...
def test_generation_fails_before_collection_when_data_file_missing(...): ...
def test_generation_collects_canonical_test_api_path(...): ...
def test_same_prefix_endpoints_receive_distinct_artifact_paths(...): ...
```

The missing-file assertions must expect `API_SCRIPT_ARTIFACT_MISSING`, not `API_SCRIPT_COLLECTION_FAILED`.

- [ ] **Step 2: Run the new service tests and verify RED**

Run:

```powershell
rtk uv run pytest tests/test_api_automation_script_generation_paths.py -q
```

Expected: FAIL because the service currently calculates `test_v1.py`, does not pass artifact targets to the Agent, and invokes pytest before checking files.

- [ ] **Step 3: Build canonical endpoint payloads before Agent invocation**

For every changed endpoint:

```python
endpoint_dir, test_file_key, data_file_key = endpoint_artifact_paths(endpoint)
endpoint["artifacts"] = {
    "directory": endpoint_dir,
    "test_file": test_file_key,
    "data_file": data_file_key,
}
```

Use these paths for `artifacts_by_endpoint`, collection targets, and persisted script paths. Use a readable script name such as `POST /openapi/v1/agent/analysis/`; do not persist an endpoint-key.

- [ ] **Step 4: Validate generated files before collection**

Add a helper that verifies both canonical files are regular files under the suite root. Raise:

```text
API_SCRIPT_ARTIFACT_MISSING
API_SCRIPT_ARTIFACT_PATH_INVALID
```

with the endpoint ID and expected relative path when validation fails.

- [ ] **Step 5: Run the service regression tests and verify GREEN**

Run the focused service test file and expect all tests to pass.

---

### Task 4: Existing Script Canonicalization and Regression Verification

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/tests/test_api_automation_script_generation_paths.py`

**Interfaces:**
- Consumes: existing script records and canonical endpoint artifact paths.
- Produces: regeneration when persisted paths are missing or non-canonical.

- [ ] **Step 1: Add failing stale-path tests**

Create an existing script record whose source hash is unchanged but whose paths point to `testcases/v1/agent/test_agent.py` and `test_agent.yaml`. Assert the endpoint remains in `changed_endpoint_ids` and is regenerated into the canonical folder.

- [ ] **Step 2: Run the stale-path test and verify RED**

Expected: FAIL because current change detection checks only `source_hash`.

- [ ] **Step 3: Add canonical artifact health to change detection**

An endpoint is unchanged only when source hash matches, persisted paths match the canonical paths, and both files exist. Otherwise regenerate the endpoint.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
rtk uv run pytest \
  tests/test_api_automation_suite.py \
  tests/test_api_automation_deepagents_agent.py \
  tests/test_api_automation_script_generation_paths.py \
  tests/test_api_automation_runner.py \
  -q
```

Expected: all focused tests pass.

---

### Task 5: Generated Project Collection Verification

**Files:**
- Modify only if validation reveals a framework incompatibility: project suite shared files under `apps/backend/data/projects/project-75fec50973f2adf6/api_automation/pytest_requests/`

**Interfaces:**
- Consumes: the canonical endpoint folder generated by the service.
- Produces: successful changed-file and whole-suite pytest collection.

- [ ] **Step 1: Generate or migrate the failed endpoint through the service path**

Expected target:

```text
testcases/openapi/v1/agent/analysis/post/test_api.py
testcases/openapi/v1/agent/analysis/post/cases.yaml
```

- [ ] **Step 2: Collect the changed endpoint**

Run:

```powershell
rtk uv run pytest --collect-only testcases/openapi/v1/agent/analysis/post/test_api.py -q
```

Expected: collection succeeds and reports the endpoint's parameterized cases.

- [ ] **Step 3: Collect the whole generated suite**

Run:

```powershell
rtk uv run pytest --collect-only testcases -q
```

Expected: collection succeeds without sending real API requests.

- [ ] **Step 4: Run final backend verification**

Run focused API automation tests followed by `rtk git diff --check`. Record unrelated failures without modifying unrelated modules.
