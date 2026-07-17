# API Automation One Endpoint Folder Design

## 1. Background

The API automation script generator currently has two independent sources of truth for endpoint artifact paths:

- the backend calculates an expected test file and data file through `endpoint_artifact_keys()`;
- the DeepAgents generator inspects the existing pytest project and chooses files based on the current directory structure and prompt instructions.

This mismatch caused script generation run `apiscriptgen-1e631ab2c35b4abd` to fail on July 17, 2026. For endpoint `POST /openapi/v1/agent/analysis/`, the backend attempted to collect:

```text
testcases/openapi/v1/test_v1.py
```

while the project actually contained and updated:

```text
testcases/v1/agent/test_agent.py
testcases/v1/agent/test_agent.yaml
```

The existing backend path algorithm also uses only the first two URL path segments for the file path. Multiple endpoints below `/openapi/v1/` can therefore resolve to the same `test_v1.py`, which violates the existing ownership rule that one endpoint owns one test module and one data file.

This design replaces inferred or endpoint-key-based artifact paths with a deterministic **one endpoint, one folder** structure derived from the endpoint's normalized path and HTTP method.

## 2. Relationship to Existing Designs

This specification refines the endpoint artifact ownership and physical layout portions of:

- `docs/superpowers/specs/2026-07-16-api-automation-deepagents-design.md`;
- `docs/superpowers/specs/2026-07-14-api-script-workspace-simplification-design.md`.

The following existing decisions remain unchanged:

- one business project owns one persistent `pytest_requests` suite;
- DeepAgents operates directly on the project suite root;
- shared client, fixtures, authentication, loaders, and assertions remain project-level assets;
- generation is incremental and must preserve unselected endpoints;
- collection validation must not send real API requests;
- runtime URLs, authentication values, secrets, and upload paths remain outside generated source code.

## 3. Goals

- Give every endpoint an independent and human-readable folder.
- Derive the folder deterministically from verified endpoint data.
- Remove `endpoint-key` and database IDs from physical file paths.
- Make the backend the single source of truth for endpoint artifact paths.
- Prevent collisions between endpoints that share path prefixes.
- Prevent collisions between different HTTP methods on the same path.
- Let regeneration replace only the selected endpoint's files.
- Validate artifact existence before invoking pytest.
- Support safe migration of existing generated suites.
- Persist the exact files that were generated and collected.

## 4. Non-goals

- Do not create a separate pytest project or virtual environment per endpoint.
- Do not create an endpoint-specific copy of shared clients, fixtures, or assertion utilities.
- Do not expose internal endpoint database IDs in generated paths.
- Do not let the model choose a different output folder from the backend-provided target.
- Do not reorganize scenario automation files in this change.
- Do not redesign API case generation or assertion semantics.
- Do not execute endpoint requests as part of generation validation.

## 5. Endpoint Identity

For artifact ownership, an endpoint is identified by:

```text
normalized_path + HTTP method
```

Examples:

```text
GET  /openapi/v1/agent/analysis/
POST /openapi/v1/agent/analysis/
```

These are two different endpoints and must own two different folders.

The database `endpoint_id` remains the persistent record identity and is stored in script records and case data, but it is not part of the physical path.

The backend must reject or resolve duplicate active endpoint records with the same project, normalized path, and HTTP method before generation. Physical paths must not be made unique by appending opaque IDs.

## 6. Canonical Folder Layout

The endpoint artifact layout is:

```text
testcases/<normalized-path-segments>/<method>/
├── test_api.py
└── cases.yaml
```

For:

```text
POST /openapi/v1/agent/analysis/
```

the canonical relative paths are:

```text
testcases/openapi/v1/agent/analysis/post/test_api.py
testcases/openapi/v1/agent/analysis/post/cases.yaml
```

The full project path is:

```text
data/projects/<project_id>/api_automation/pytest_requests/
└── testcases/openapi/v1/agent/analysis/post/
    ├── test_api.py
    └── cases.yaml
```

Different methods on the same path remain isolated:

```text
testcases/openapi/v1/agent/analysis/get/
├── test_api.py
└── cases.yaml

testcases/openapi/v1/agent/analysis/post/
├── test_api.py
└── cases.yaml
```

The endpoint folder contains only files owned by that endpoint. Shared imports continue to resolve from the suite root.

## 7. Canonical Path Algorithm

The backend owns one deterministic function that receives the verified endpoint method and normalized path and returns:

```text
endpoint_directory
test_file_key
data_file_key
```

Conceptual result:

```json
{
  "endpoint_directory": "testcases/openapi/v1/agent/analysis/post",
  "test_file_key": "testcases/openapi/v1/agent/analysis/post/test_api.py",
  "data_file_key": "testcases/openapi/v1/agent/analysis/post/cases.yaml"
}
```

### 7.1 Path normalization rules

- Use `normalized_path` as the source when available; otherwise normalize `path` through the existing OpenAPI path normalization flow.
- Strip leading and trailing `/` characters.
- Split the path into non-empty segments.
- Lowercase the HTTP method and allow only supported method names.
- Convert literal path segments to lowercase filesystem-safe slugs.
- Replace unsupported characters with `_` and collapse repeated `_` characters.
- Reject `.` and `..` segments.
- Resolve the final path and verify that it remains under the suite root.
- Do not use an LLM to calculate or reinterpret the target path.

### 7.2 Path parameter rules

OpenAPI path parameters use readable `by_<parameter>` segments.

```text
GET /users/{user_id}
```

becomes:

```text
testcases/users/by_user_id/get/
├── test_api.py
└── cases.yaml
```

Multiple parameters retain their path position:

```text
GET /organizations/{org_id}/users/{user_id}
```

becomes:

```text
testcases/organizations/by_org_id/users/by_user_id/get/
├── test_api.py
└── cases.yaml
```

Parameter names are normalized using the same filesystem-safe slug rules. Empty or invalid parameter names must fail validation rather than producing an ambiguous folder.

### 7.3 Root path rule

An endpoint whose normalized path is `/` uses a reserved root segment:

```text
testcases/root/get/test_api.py
testcases/root/get/cases.yaml
```

### 7.4 Collision rule

Before generation, the backend must calculate all selected endpoint paths and reject the request if two different endpoint records resolve to the same endpoint directory.

The error must identify both endpoint IDs and the conflicting normalized method/path values. The backend must not silently append a database ID to resolve the collision.

## 8. Backend Generation Contract

The backend calculates artifact paths before invoking DeepAgents and includes them in the structured endpoint payload.

Example:

```json
{
  "id": "apiend-6434c35096aa611b",
  "method": "POST",
  "path": "/openapi/v1/agent/analysis/",
  "normalized_path": "/openapi/v1/agent/analysis/",
  "artifacts": {
    "directory": "testcases/openapi/v1/agent/analysis/post",
    "test_file": "testcases/openapi/v1/agent/analysis/post/test_api.py",
    "data_file": "testcases/openapi/v1/agent/analysis/post/cases.yaml"
  }
}
```

The endpoint payload and its stored cases remain the only endpoint behavior inputs. The artifact fields define file ownership, not API behavior.

The backend must:

1. authorize the project and selected endpoint IDs;
2. load verified endpoint definitions and stored cases;
3. calculate and validate canonical paths;
4. acquire the project suite lock;
5. initialize or repair the shared suite when required;
6. invoke DeepAgents with the exact artifact targets;
7. verify the required files exist;
8. collect each changed `test_api.py`;
9. collect the whole suite;
10. persist the exact canonical paths only after successful validation.

## 9. DeepAgents Contract

DeepAgents may inspect and repair the shared suite, but endpoint output locations are not discretionary.

For each selected endpoint, the agent must:

- write endpoint test code only to the provided `artifacts.test_file`;
- write endpoint case data only to the provided `artifacts.data_file`;
- create missing parent directories for those paths;
- read and preserve unselected endpoint folders;
- reuse project-level clients, fixtures, loaders, authentication, and assertions;
- avoid creating alternative endpoint files such as `test_agent.py` or `test_v1.py` outside the provided folder;
- report the files it changed;
- run collection through the provided collection tool without sending real requests.

The prompt and bundled generation skill must state that backend-provided artifact paths are mandatory.

Agent output is advisory for audit information. The backend-calculated artifact manifest remains authoritative and must be verified against the filesystem.

## 10. Generated Endpoint Files

### 10.1 `test_api.py`

Each endpoint folder contains exactly one collected endpoint module named `test_api.py`.

The module must:

- load `cases.yaml` from its own directory;
- parameterize stored cases so pytest reports them independently;
- use stable case IDs derived from case IDs or titles;
- reuse shared request and assertion behavior;
- avoid module-import-time network requests;
- avoid embedded base URLs, credentials, cookies, tokens, and local upload paths.

Conceptual structure:

```python
TEST_CASES = load_cases(__file__, "cases.yaml")


@pytest.mark.parametrize("case", TEST_CASES, ids=case_ids(TEST_CASES))
def test_api(api_client, case):
    response = api_client.request_case(case)
    assert_response(response, case["assertions"])
```

The exact helper names follow the existing project framework and are not redefined by this specification.

### 10.2 `cases.yaml`

The adjacent data file contains only cases belonging to the folder's endpoint.

Each case must retain its stable case ID and endpoint ID. The endpoint ID provides traceability but does not determine the physical path.

## 11. Artifact Validation

The backend must validate generated artifacts before pytest collection.

For every selected endpoint:

- the canonical endpoint directory must remain under the suite root;
- `test_api.py` must exist and be a regular file;
- `cases.yaml` must exist and be a regular file;
- both paths must equal the backend-calculated canonical paths;
- the data file must contain only cases belonging to the selected endpoint;
- the set of persisted case IDs must match the stored cases selected for generation;
- no two selected endpoints may own the same file;
- no unexpected Python or YAML endpoint file may be accepted as a substitute.

Missing or misplaced files must fail with a specific artifact error before pytest is invoked:

```text
API_SCRIPT_ARTIFACT_MISSING
```

Path mismatch or containment violations must fail with:

```text
API_SCRIPT_ARTIFACT_PATH_INVALID
```

The error message must include the endpoint ID and expected relative path, but not host secrets or unrelated absolute paths.

## 12. Collection Validation

Collection runs in two stages while holding the project suite lock.

### 12.1 Changed endpoint collection

For each changed endpoint, collect its canonical test module:

```text
uv run pytest --collect-only testcases/openapi/v1/agent/analysis/post/test_api.py
```

The runner receives backend-calculated relative paths. It must not reconstruct endpoint paths.

### 12.2 Whole-suite collection

After changed endpoint collection succeeds, collect the complete endpoint suite:

```text
uv run pytest --collect-only testcases
```

Generation succeeds only when both stages pass. Collection must run without runtime API credentials and must not send real requests.

## 13. Persistence Model

One script record continues to represent one endpoint executable artifact.

Persist:

- `endpoint_id`;
- canonical `suite_path`;
- canonical `test_file_path`;
- canonical `data_file_path`;
- source hash;
- case count;
- generation run ID;
- collection status and timestamps.

Do not derive persisted paths again when reading or executing a script. Execution uses the paths stored after successful generation.

Regenerating an unchanged endpoint may return `unchanged` only when:

- the source hash is unchanged;
- the persisted canonical paths match the current path algorithm;
- both persisted files still exist;
- no migration is pending.

Otherwise the endpoint must be regenerated or migrated even when its source hash is unchanged.

## 14. Existing Suite Migration

Existing suites may contain layouts such as:

```text
testcases/v1/agent/test_agent.py
testcases/v1/agent/test_agent.yaml
```

or:

```text
testcases/openapi/v1/test_v1.py
testcases/openapi/v1/test_v1.yaml
```

Migration is performed per endpoint under the project suite lock.

### 14.1 Discovery

The migration process uses persisted script records first. If a script record is missing or incomplete, it may inspect adjacent case data for a verified `endpoint_id`.

Filename similarity, directory names, summaries, and LLM inference are not sufficient to claim ownership.

If ownership cannot be established unambiguously, migration must leave the legacy files untouched and require regeneration for that endpoint.

### 14.2 Migration behavior

For an unambiguous legacy endpoint:

1. calculate the canonical endpoint folder;
2. stage the canonical `test_api.py` and `cases.yaml` atomically;
3. update imports and adjacent data-file references when necessary;
4. run changed-file collection;
5. run whole-suite collection;
6. update the script record;
7. remove the legacy endpoint files only after successful validation;
8. remove empty legacy directories without deleting shared or unowned files.

If validation fails, retain the legacy files and do not update persisted paths.

### 14.3 Current failed project

For project `project-75fec50973f2adf6` and endpoint `apiend-6434c35096aa611b`, the target canonical folder is:

```text
testcases/openapi/v1/agent/analysis/post/
```

The existing `testcases/v1/agent/test_agent.py` and `test_agent.yaml` must not simply be copied based on their names. Migration must first verify that the data belongs exclusively to this endpoint. After migration, collection must target:

```text
testcases/openapi/v1/agent/analysis/post/test_api.py
```

## 15. Incremental Generation and Deletion

### 15.1 Create

Generating a new endpoint creates only its canonical endpoint folder and files, plus required shared framework repairs.

### 15.2 Update

Regenerating an endpoint replaces only:

```text
<endpoint-folder>/test_api.py
<endpoint-folder>/cases.yaml
```

Unselected endpoint folders must remain unchanged.

### 15.3 Delete

Deleting a generated endpoint script may delete its canonical endpoint folder only when:

- the folder resolves under `testcases`;
- the persisted endpoint owns the folder;
- no other script record references files inside it;
- the folder contains no unowned files.

The endpoint definition and test cases are not deleted by removing generated script artifacts unless a separate product action explicitly requests it.

## 16. Concurrency and Atomicity

- Hold the existing project workspace lock while calculating migration state, writing endpoint files, collecting, and persisting script records.
- Write `test_api.py` and `cases.yaml` through atomic replacement where the filesystem backend supports it.
- Do not expose a state where one new endpoint file exists without its adjacent data file.
- Concurrent generation requests for the same project must serialize.
- Concurrent generation for different projects may proceed independently.

## 17. API and UI Behavior

The public generation request continues to use selected endpoint IDs. Callers do not send filesystem paths.

Generation responses and task details return the canonical changed files:

```json
{
  "changed_files": [
    "testcases/openapi/v1/agent/analysis/post/test_api.py",
    "testcases/openapi/v1/agent/analysis/post/cases.yaml"
  ]
}
```

The UI may display these relative paths for diagnostics. It must not allow users to edit backend-owned artifact paths as part of generation.

Artifact validation errors should be surfaced directly rather than converted into a generic pytest collection failure.

## 18. Testing Strategy

### 18.1 Canonical path unit tests

Cover:

- literal paths;
- trailing and repeated slashes;
- uppercase methods;
- different methods on the same path;
- path parameters;
- multiple path parameters;
- root path;
- unsafe segments;
- unsupported characters;
- resolved-path containment;
- duplicate canonical path detection.

Required regression assertion for the current endpoint:

```text
POST /openapi/v1/agent/analysis/
→ testcases/openapi/v1/agent/analysis/post/test_api.py
→ testcases/openapi/v1/agent/analysis/post/cases.yaml
```

### 18.2 Agent contract tests

Use a filesystem-backed fake or controlled agent result to verify:

- exact backend-provided paths are created;
- alternative paths are rejected;
- unselected endpoint folders are preserved;
- the adjacent `cases.yaml` is loaded by `test_api.py`;
- collection repair cannot move endpoint artifacts outside their assigned folder.

### 18.3 Service tests

Cover:

- artifact paths are calculated before Agent invocation;
- artifact targets are included in the structured Agent payload;
- missing `test_api.py` fails before pytest collection;
- missing `cases.yaml` fails before pytest collection;
- a path mismatch fails with `API_SCRIPT_ARTIFACT_PATH_INVALID`;
- two endpoints with a shared prefix get different folders;
- GET and POST on the same path get different folders;
- script records persist exact collected paths;
- an unchanged source with missing files is regenerated;
- failed validation does not create a successful script record.

### 18.4 Runner tests

Verify:

- changed endpoint collection receives canonical `test_api.py` paths;
- whole-suite collection targets `testcases`;
- backend `VIRTUAL_ENV` is not inherited;
- secrets are redacted from errors;
- collection does not require runtime API environment values.

### 18.5 Migration tests

Cover:

- migration from a legacy file with one verified endpoint;
- refusal to migrate a shared legacy file containing multiple endpoints;
- refusal to infer ownership from filename alone;
- rollback or preservation when migrated collection fails;
- removal of empty legacy directories only after success.

### 18.6 End-to-end regression

Create a project suite containing the current legacy layout, run generation for `POST /openapi/v1/agent/analysis/`, and verify:

1. canonical files are present;
2. changed-file collection succeeds;
3. whole-suite collection succeeds;
4. the generation run completes successfully;
5. the persisted script paths are canonical;
6. no `testcases/openapi/v1/test_v1.py` path is requested;
7. no endpoint-key or endpoint ID appears in the filesystem path.

## 19. Acceptance Criteria

- Every generated endpoint owns exactly one folder under `testcases`.
- The folder is derived from normalized path segments and lowercase HTTP method.
- Each endpoint folder contains `test_api.py` and `cases.yaml`.
- Physical paths contain neither endpoint-key nor endpoint database ID.
- Backend and Agent use one backend-provided artifact manifest.
- Missing or misplaced files fail before pytest invocation.
- Different methods on the same path cannot collide.
- Endpoints sharing `/openapi/v1/` cannot overwrite one another.
- Regeneration modifies only selected endpoint folders and required shared repairs.
- Existing suites can be migrated when ownership is unambiguous.
- Changed-file and whole-suite collection both pass before generation is marked successful.
- The July 17, 2026 failure is covered by an automated regression test.

## 20. Rollout

Implement and release in this order:

1. add canonical path calculation and collision tests;
2. add the backend artifact manifest to Agent inputs;
3. update Agent instructions to require exact targets;
4. add pre-collection artifact validation;
5. persist and execute canonical paths;
6. add legacy migration support;
7. migrate or force-regenerate the failed project endpoint;
8. run focused backend tests and generated-suite collection;
9. enable the new layout for all subsequent endpoint generation.

Do not migrate production project suites until canonical path, artifact validation, and migration regression tests pass together.
