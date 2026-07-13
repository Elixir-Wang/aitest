# API Automation Endpoint Folder Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目级 pytest + Requests 生成套件调整为“一个接口一个目录，目录内固定 `test_api.py` 与 `cases.json`”，并保证增量生成、脚本删除、脚本 Tab 展示和 pytest 收集验证保持正确。

**Architecture:** 每个项目仍只有一个 `pytest_requests` 套件，共享配置和 `support/` 保持项目级；每个 endpoint 独占 `endpoints/<endpoint-key>/` 目录。生成器只返回逻辑相对路径，Service/Storage 负责原子落盘和删除；生成完成后对真实套件运行 `pytest --collect-only`，避免再次写出无法导入或无法收集的项目。

**Tech Stack:** Python 3.12+ / FastAPI / sqlite3 / pytest / Requests / pytest-json-report / uv

## Global Constraints

- 一个项目只维护一个 `api_automation/pytest_requests/` 套件。
- 一个 endpoint 只对应一条 `api_test_scripts` 记录。
- 一个 endpoint 只拥有 `endpoints/<endpoint-key>/test_api.py` 和 `endpoints/<endpoint-key>/cases.json`。
- `<endpoint-key>` 必须包含稳定 endpoint ID；method/path 只提供可读性。
- 只更新本次选择的 endpoint 目录，不删除未选择 endpoint 的制品。
- base URL、认证、密钥、timeout、TLS 和文件路径继续通过运行环境注入，不写入生成代码。
- 生成后的真实套件必须通过 `pytest --collect-only` 才能标记为生成成功。
- 当前百工项目脚本记录和业务测试文件已清空，不实现旧 `tests/`、`data/` 目录迁移逻辑。

---

## File Map

- Modify: `apps/backend/app/agents/api_automation/pytest_requests/renderer.py` — 生成 endpoint 目录、固定文件名和相邻数据读取逻辑。
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/SKILL.md` — 更新生成约束和质量门。
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/references/project-structure.md` — 更新目标目录契约。
- Modify: `apps/backend/app/services/api_automation/artifact_storage.py` — 从新逻辑 key 返回 endpoint 目录和脚本名。
- Modify: `apps/backend/app/services/api_automation/service.py` — 删除脚本时清理空 endpoint 目录，并在生成后执行收集验证。
- Modify: `apps/backend/app/services/api_automation/runner.py` — 提供不执行真实接口请求的 suite collection helper，复用 uv 套件环境。
- Modify: `apps/backend/tests/test_api_automation_pytest_requests_agent.py` — 锁定新逻辑路径与测试代码读取方式。
- Modify: `apps/backend/tests/test_api_automation_script_generator.py` — 锁定真实落盘、增量更新和删除目录语义。
- Modify: `apps/backend/tests/test_api_automation_runner.py` — 锁定 `--collect-only` 命令、报告和失败输出。

---

### Task 1: Generate One Directory Per Endpoint

**Files:**
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/renderer.py:7`
- Test: `apps/backend/tests/test_api_automation_pytest_requests_agent.py`

**Interfaces:**
- Consumes: `PytestRequestsGenerationInput.endpoint` and `PytestRequestsGenerationInput.cases`.
- Produces: `GeneratedCodeFile.key` values `endpoints/<endpoint-key>/test_api.py` and `endpoints/<endpoint-key>/cases.json`.

- [ ] **Step 1: Write failing path-contract test**

Add a focused test asserting one generated endpoint owns exactly these keys:

```python
def test_generation_groups_test_and_data_under_endpoint_directory() -> None:
    result = generate_pytest_requests_code(_input())

    endpoint_files = {
        file.key
        for file in result.files
        if file.kind in {"test", "data"}
    }

    assert endpoint_files == {
        "endpoints/post_login_apiend_login/test_api.py",
        "endpoints/post_login_apiend_login/cases.json",
    }
```

Use the actual `slugify()` output when finalizing the expected endpoint key; do not introduce a second slug algorithm in the test.

- [ ] **Step 2: Write failing adjacent-data test**

Assert the generated test module reads its data from the same directory:

```python
test_file = next(file for file in result.files if file.kind == "test")
assert 'Path(__file__).with_name("cases.json")' in test_file.content
assert 'parents[1] / "data"' not in test_file.content
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
cd apps/backend
.venv\Scripts\python.exe -m pytest tests/test_api_automation_pytest_requests_agent.py -q
```

Expected: FAIL because renderer still emits `tests/test_<endpoint-key>.py` and `data/test_<endpoint-key>.json`.

- [ ] **Step 4: Implement endpoint directory rendering**

In `render_pytest_requests_files()` derive:

```python
endpoint_dir = f"endpoints/{endpoint_key}"
data_key = f"{endpoint_dir}/cases.json"
test_key = f"{endpoint_dir}/test_api.py"
```

Generate `cases.json` at `data_key` and test code at `test_key`. Change `_test_py()` to accept no filename argument and load:

```python
CASES = json.loads(
    Path(__file__).with_name("cases.json").read_text(encoding="utf-8")
)["cases"]
```

Keep root `conftest.py`, `support/`, `pyproject.toml`, `pytest.ini`, and `README.md` unchanged except for discovery configuration required below.

- [ ] **Step 5: Update pytest discovery configuration**

Render:

```ini
[pytest]
addopts = --import-mode=importlib
pythonpath = .
testpaths = endpoints
python_files = test_*.py
```

Do not create endpoint-level `conftest.py` files.

- [ ] **Step 6: Run agent tests and verify GREEN**

Run the Task 1 test command again.

Expected: all tests pass.

---

### Task 2: Persist and Delete Endpoint Directories Safely

**Files:**
- Modify: `apps/backend/app/services/api_automation/artifact_storage.py:29`
- Modify: `apps/backend/app/services/api_automation/service.py:830`
- Test: `apps/backend/tests/test_api_automation_script_generator.py`

**Interfaces:**
- Consumes: Task 1 logical file keys.
- Produces: script records whose `test_file_path` and `data_file_path` point into the same endpoint directory.

- [ ] **Step 1: Write failing materialization test**

Extend the existing generation service test to assert:

```python
assert test_file.name == "test_api.py"
assert data_file.name == "cases.json"
assert test_file.parent == data_file.parent
assert test_file.parent.parent.name == "endpoints"
```

Also assert `script["name"]` remains endpoint-readable and stable. Do not allow every record to be named only `test_api`.

- [ ] **Step 2: Run materialization test and verify RED**

Run:

```powershell
cd apps/backend
.venv\Scripts\python.exe -m pytest tests/test_api_automation_script_generator.py::test_generate_scripts_creates_pytest_project_without_hardcoded_environment -q
```

Expected: FAIL because current files are split between top-level `tests/` and `data/`.

- [ ] **Step 3: Preserve readable script naming**

In `materialize_generation_result()`, do not derive `script_name` from `Path(test_key).stem`, because it would always become `test_api`. Return `result.endpoint_key` as `script_name`:

```python
"script_name": result.endpoint_key,
```

Continue returning exact absolute paths for `test_file_path` and `data_file_path`.

- [ ] **Step 4: Write failing directory-delete test**

Update the existing delete test to assert:

```python
endpoint_dir = test_file.parent
service.delete_api_script("project-1", script["id"], ACTOR)

assert not test_file.exists()
assert not data_file.exists()
assert not endpoint_dir.exists()
assert suite_path.exists()
assert (suite_path / "support" / "client.py").exists()
```

Also create an unrelated endpoint directory before deletion and assert it remains untouched.

- [ ] **Step 5: Run delete test and verify RED**

Run:

```powershell
cd apps/backend
.venv\Scripts\python.exe -m pytest tests/test_api_automation_script_generator.py::test_delete_script_removes_record_and_generated_files -q
```

Expected: FAIL because the current service deletes only the two files and leaves the endpoint directory.

- [ ] **Step 6: Implement safe endpoint-directory cleanup**

After deleting both stored files in `delete_api_script()`:

1. Resolve both paths under `suite_path` using the existing path-containment checks.
2. Calculate their common parent.
3. Delete the parent directory only when:
   - both files have the same parent;
   - parent is directly below `suite_path / "endpoints"`;
   - parent contains no remaining files.
4. Never recursively delete a computed path before validating its resolved location.
5. Never delete `endpoints/`, `support/`, suite root, or another endpoint directory.

Use `Path.rmdir()` after confirming the directory is empty; do not use broad `shutil.rmtree()` here.

- [ ] **Step 7: Run script generator tests and verify GREEN**

Run:

```powershell
cd apps/backend
.venv\Scripts\python.exe -m pytest tests/test_api_automation_script_generator.py -q
```

Expected: all tests pass.

---

### Task 3: Add Real Pytest Collection Quality Gate

**Files:**
- Modify: `apps/backend/app/services/api_automation/runner.py:17`
- Modify: `apps/backend/app/services/api_automation/service.py:670`
- Test: `apps/backend/tests/test_api_automation_runner.py`
- Test: `apps/backend/tests/test_api_automation_script_generator.py`

**Interfaces:**
- Produces: `collect_script_suite(*, suite_path: Path, timeout: int) -> dict[str, Any]`.
- Consumes: generated suite after all selected endpoint files are materialized.

- [ ] **Step 1: Write failing collection-command test**

Add a runner test that mocks `subprocess.run` and asserts the helper executes exactly:

```python
["uv", "sync"]
["uv", "run", "pytest", "--collect-only", "endpoints"]
```

The command must run with `cwd=suite_path`, capture stdout/stderr, and use the provided timeout.

- [ ] **Step 2: Write failing collection-result test**

Assert the helper returns:

```python
{
    "ok": False,
    "exitcode": 4,
    "stdout": "...",
    "stderr": "ModuleNotFoundError: ...",
}
```

when pytest collection fails. Apply existing secret redaction before returning or persisting output.

- [ ] **Step 3: Run runner tests and verify RED**

Run:

```powershell
cd apps/backend
.venv\Scripts\python.exe -m pytest tests/test_api_automation_runner.py -q
```

Expected: FAIL because no collection helper exists.

- [ ] **Step 4: Implement collection helper**

Add `collect_script_suite()` in `runner.py` that:

1. Runs `uv sync` once.
2. If sync fails, returns failure immediately with sync output.
3. Runs `uv run pytest --collect-only endpoints`.
4. Returns redacted stdout/stderr and exit code.
5. Does not require API environment values and does not execute endpoint requests.

Do not create a `report.json` for collection; collection success is determined by exit code `0`.

- [ ] **Step 5: Write failing service rollback test**

Add a service test that makes collection fail after files are written and asserts:

- generation raises the existing API error mechanism with a specific code such as `API_SCRIPT_COLLECTION_FAILED`;
- no new `api_test_scripts` record is persisted;
- files written for the failed selected endpoint are removed;
- pre-existing unselected endpoint files and records remain untouched.

- [ ] **Step 6: Run rollback test and verify RED**

Run the new focused service test.

Expected: FAIL because current generation marks files successful without collection.

- [ ] **Step 7: Integrate collection into generation transaction boundary**

In `generate_project_scripts()`:

1. Hold `project_workspace_lock(project_id)` while writing changed endpoint artifacts.
2. Track only files/directories created or replaced in this request.
3. Run `collect_script_suite()` once after all changed endpoints are written.
4. On success, persist/upsert script records as today.
5. On failure, restore replaced files or remove newly created endpoint directories before raising `API_SCRIPT_COLLECTION_FAILED` with concise stderr.

Prefer a small artifact rollback helper in `artifact_storage.py` if rollback logic cannot remain readable in `service.py`; do not introduce a second workspace abstraction.

- [ ] **Step 8: Run runner and service tests and verify GREEN**

Run:

```powershell
cd apps/backend
.venv\Scripts\python.exe -m pytest tests/test_api_automation_runner.py tests/test_api_automation_script_generator.py -q
```

Expected: all tests pass.

---

### Task 4: Synchronize Skill, Documentation, and Full Contracts

**Files:**
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/SKILL.md`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/references/project-structure.md`
- Modify: `D:/project/test_project/.agents/skills/pytest-requests-api-automation/SKILL.md`
- Test: `apps/backend/tests/test_api_automation_pytest_requests_agent.py`
- Test: `apps/backend/tests/test_api_automation_script_generator.py`
- Test: `apps/backend/tests/test_api_automation_runner.py`
- Test: `apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs`

**Interfaces:**
- Documents the final generated suite contract used by renderer and service tests.

- [ ] **Step 1: Update internal generation Skill**

Replace the old `tests/` plus `data/` wording with:

```text
endpoints/<endpoint-key>/
├── test_api.py
└── cases.json
```

State explicitly:

- endpoint key contains the stable endpoint ID;
- test code reads adjacent `cases.json`;
- root `conftest.py` and `support/` are shared;
- generation is unsuccessful until real `pytest --collect-only` passes.

- [ ] **Step 2: Update internal project structure reference**

Document the complete target structure:

```text
pytest_requests/
├── pyproject.toml
├── uv.lock
├── pytest.ini
├── conftest.py
├── README.md
├── support/
└── endpoints/
    └── <endpoint-key>/
        ├── test_api.py
        └── cases.json
```

- [ ] **Step 3: Update project-level automation Skill contract**

Change the generated suite contract in `.agents/skills/pytest-requests-api-automation/SKILL.md` to the same endpoint-folder structure. Preserve the existing rules for endpoint selection, stable identity, environment injection, atomic writes, and incremental updates.

- [ ] **Step 4: Verify frontend requires no API change**

Run the frontend contract test. The existing API still returns `kind`, `path`, and `content` for the test and data files, so no page change should be required.

Run:

```powershell
cd apps/frontend
node --test tests/api-automation-interface-set-copy-contract.test.mjs
```

Expected: PASS. If it fails only because a test hardcodes `tests/` or `data/` paths, update that contract to expect the endpoint-folder paths; do not change the API shape.

- [ ] **Step 5: Run full focused backend regression**

Run:

```powershell
cd apps/backend
.venv\Scripts\python.exe -m pytest \
  tests/test_api_automation_pytest_requests_agent.py \
  tests/test_api_automation_runner.py \
  tests/test_api_automation_script_generator.py \
  tests/test_api_automation_schema_repo.py \
  tests/test_api_automation_scenarios_tasks.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 6: Perform real generated-suite verification**

Generate one endpoint into a temporary project storage root, then run:

```powershell
uv sync
uv run pytest --collect-only endpoints
```

Expected:

- pytest finds every case under `endpoints/<endpoint-key>/test_api.py`;
- `support` imports succeed;
- no API request is executed;
- no top-level business files are created under `tests/` or `data/`.

- [ ] **Step 7: Verify deletion boundary manually**

Using a temporary suite containing two endpoint directories:

1. Delete one script through `delete_api_script()`.
2. Confirm only its endpoint directory disappears.
3. Confirm the other endpoint directory, root config, `support/`, and suite environment remain.

---

## Acceptance Criteria

- Generated business artifacts exist only under `endpoints/<endpoint-key>/`.
- Each endpoint directory contains exactly `test_api.py` and `cases.json` before runtime caches are created.
- Script records continue storing exact test and data file paths without schema changes.
- Regenerating one endpoint does not modify or remove unselected endpoint directories.
- Deleting one script removes its database record and empty endpoint directory only.
- Generation fails and rolls back selected endpoint changes when `pytest --collect-only` fails.
- Runtime execution continues using the suite-local `uv sync + uv run pytest` model.
- No migration code is added for the already-cleared legacy `tests/` and `data/` business files.

