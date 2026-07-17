# API Automation DeepAgents Design

## 1. Background

The current API automation generator mixes project scaffolding and endpoint code generation. It uses an `is_first_time` branch to decide which files to render. Existing projects can therefore contain test files that import shared modules such as `utils.data_loader` even when those modules are missing. Pytest then fails during collection before any API test runs.

The current implementation also wraps a deterministic renderer in `ExecutableSkill`; it does not give a DeepAgents agent a project filesystem on which the agent can inspect, modify, and validate an existing suite.

## 2. Goals

- Give each business project exactly one persistent `pytest + requests` project.
- Bind DeepAgents directly to that project's configured suite directory.
- Initialize the complete suite structure before generating endpoint tests.
- Let the agent inspect existing files and repair missing or inconsistent dependencies.
- Support incremental endpoint generation without recreating a second suite.
- Run `pytest --collect-only` during generation and let the agent repair collection errors.
- Keep runtime URLs, authentication, secrets, and files outside generated source code.
- Preserve project-level concurrency, path safety, execution reporting, and audit state.
- Migrate existing incomplete suites instead of requiring manual deletion.

## 3. Non-goals

- Do not create one virtual environment or pytest project per endpoint.
- Do not create a temporary workspace as a required generation layer.
- Do not let the model infer or invent the physical output directory.
- Do not make the backend renderer the authority for the complete project structure.
- Do not execute real API requests during collection validation.

## 4. Project Ownership Model

One business project owns one persistent suite:

```text
data/projects/<project_id>/api_automation/pytest_requests/
```

All selected endpoints for that business project are added to this suite. Each endpoint owns its own test module and test data file, while shared client, fixture, loading, authentication, and assertion code is shared by the suite.

```text
pytest_requests/
├── AGENTS.md
├── pyproject.toml
├── pytest.ini
├── conftest.py
├── api/
│   ├── __init__.py
│   └── client.py
├── testcases/
│   ├── __init__.py
│   └── conftest.py
├── utils/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── assertions.py
│   └── assert_utils.py
├── support/
│   ├── __init__.py
│   ├── auth.py
│   └── client.py
├── config/
│   ├── __init__.py
│   └── settings.py
├── data/
│   └── __init__.py
└── .deepagents/
    ├── generation-state.json
    └── last-collection.json
```

The suite directory is the DeepAgents filesystem root. No separate workspace is required.

## 5. DeepAgents Boundary

The backend resolves the physical suite path and configures the agent backend with it. The path is not supplied as a prompt instruction for the model to interpret.

```text
project_id
    ↓
project_suite_path(project_id)
    ↓
FilesystemBackend(root_dir=suite_path, virtual_mode=True)
    ↓
DeepAgents reads and writes only this suite
```

The agent may use filesystem operations to:

- inspect the suite;
- read endpoint and case inputs supplied by the backend;
- create or edit Python, YAML, TOML, INI, and Markdown files;
- search imports and references;
- run collection validation;
- read failures and repair the suite;
- write generation and collection state under `.deepagents/`.

The backend remains responsible for authentication, project authorization, path validation, concurrency locking, runtime secret injection, and persistence of generation records.

## 6. Two-Phase Generation

### Phase A: Suite Initialization

Before endpoint generation, an initialization task ensures the complete shared framework exists. It is idempotent: missing files are created, compatible files are preserved, and incompatible framework files are repaired through the agent's inspection and validation flow.

The required initialization files include:

- `pytest.ini`;
- `pyproject.toml`;
- root and testcase `conftest.py` files;
- `api/client.py`;
- `utils/data_loader.py`;
- `utils/assertions.py`;
- `utils/assert_utils.py`;
- required package `__init__.py` files;
- authentication and environment configuration modules.

Initialization must validate an empty or currently existing suite with `pytest --collect-only`. An empty suite may report no tests, but it must not produce an import error.

### Phase B: Endpoint Generation

Using the same suite root, the endpoint generation task:

1. reads the existing suite instructions and structure;
2. reads only the selected endpoint definitions and stored cases;
3. reuses shared client, fixtures, loaders, and assertions;
4. creates or updates the selected endpoint's test module and data file;
5. runs collection for the changed files;
6. reads collection errors and repairs the project;
7. runs whole-suite collection before reporting success;
8. records changed files and validation output.

The agent must not create a new suite directory for each click or endpoint.

## 7. Collection Repair Loop

Generation validation follows this loop:

```text
generate or edit files
    ↓
pytest --collect-only changed targets
    ↓
success → collect entire suite
failure → read traceback and affected files
    ↓
repair files
    ↓
retry within bounded attempts
```

Collection validation must not send real API requests. It verifies imports, syntax, fixtures, parameterization, and test discovery.

The bounded retry count and final error must be stored in `.deepagents/last-collection.json` and returned to the API caller. A final collection failure is a failed generation, not a successful script record.

## 8. Input Contract

The backend provides the agent with structured context:

- project identity and authorization context;
- selected endpoint IDs;
- verified endpoint definitions;
- stored cases belonging to those endpoints;
- generation mode: initialize, add, or update;
- runtime contract for environment variables;
- collection and execution commands;
- suite-level file and security rules.

The agent must not infer endpoints, invent cases, embed secrets, or use unverified requirements as API behavior.

## 9. File Ownership Rules

- Shared framework files are owned by the suite initialization task and may be repaired when imports or collection expose an inconsistency.
- Endpoint test files and adjacent data files are owned by their stable endpoint identity.
- Regenerating an endpoint updates only that endpoint's files plus required shared repairs.
- Unselected endpoint files must be preserved.
- Every generated path must be relative to the suite root and pass resolved-path containment checks.
- Files are written atomically where possible.

The `is_first_time` renderer branch is not the source of truth for project completeness. Completeness is determined by inspecting the actual suite and running validation.

## 10. Runtime Environment

The backend environment and project test environment remain separate:

```text
apps/backend/.venv
    backend service and DeepAgents orchestration

<project>/api_automation/pytest_requests/.venv
    pytest, requests, YAML support, and report plugins
```

The project test environment is shared by collection and execution for that business project. The runner must not pass the backend `VIRTUAL_ENV` into the suite process. Runtime values are injected through environment variables or controlled runtime files.

## 11. Concurrency and Recovery

Generation and execution for the same project must use a project-level lock. The lock prevents concurrent agents from overwriting one another's suite changes.

Direct-write generation intentionally keeps the agent's changes in the persistent suite when collection fails. The generation state records:

```json
{
  "generation_id": "...",
  "status": "collection_failed",
  "changed_files": [],
  "attempts": 0,
  "error": "...",
  "updated_at": "..."
}
```

The UI or API can then offer a retry/repair action against the same suite. A separate workspace or automatic rollback is not required for the initial implementation.

## 12. Existing Suite Migration

Before generating new endpoint code, the service must inspect existing suites. If a suite has `pytest.ini` but is missing required shared files, it enters initialization/repair mode instead of being treated as complete.

The current failure is migrated by ensuring at least:

```text
utils/__init__.py
utils/data_loader.py
utils/assertions.py
utils/assert_utils.py
```

The migration must run collection before the next endpoint generation continues.

## 13. Component Responsibilities

### Backend orchestration service

- resolve the project suite path;
- acquire the project lock;
- prepare structured endpoint and case inputs;
- construct the DeepAgents backend and agent;
- start initialization or endpoint generation;
- expose collection and execution results;
- persist generation state and records.

### DeepAgents agent

- inspect the actual suite;
- initialize or repair the framework;
- generate endpoint code and data;
- execute collection validation;
- repair import and collection failures;
- report changed files and final status.

### Suite runtime manager

- ensure the project test environment exists;
- synchronize project dependencies when required;
- remove inherited backend `VIRTUAL_ENV`;
- execute collection and real pytest runs.

### Existing renderer

The current renderer may be reused for small deterministic snippets during migration, but it must not remain the authority for complete suite initialization or incremental project state.

## 14. Acceptance Criteria

1. Creating a project with no suite produces the complete directory and shared framework.
2. An empty initialized project can run `pytest --collect-only` without import errors.
3. Generating one endpoint creates its test module and adjacent case data under the existing suite.
4. Generating a second endpoint preserves the first endpoint's files.
5. A missing `utils/data_loader.py` is detected and repaired before generation succeeds.
6. Existing suites with only `pytest.ini` are repaired instead of treated as initialized.
7. Collection failure returns the actual traceback and records changed files.
8. The agent cannot write outside the project suite root.
9. Runtime secrets and absolute local paths are not embedded in generated files.
10. The project test environment is reused for collection and execution, without inheriting the backend `VIRTUAL_ENV`.
11. A project-level lock prevents concurrent generation corruption.
12. Whole-suite collection succeeds before a generation request is marked successful.

## 15. Implementation Sequence

1. Add a real DeepAgents API automation agent with a project-root filesystem backend.
2. Add suite initialization instructions and the required project `AGENTS.md`.
3. Implement suite completeness checks and migration for existing projects.
4. Move endpoint generation from renderer-only output to direct agent file operations.
5. Add bounded collection repair and generation-state persistence.
6. Keep the existing runner for real execution, using the project test environment.
7. Add focused tests for initialization, missing shared files, incremental endpoint updates, path containment, collection repair, and whole-suite validation.

