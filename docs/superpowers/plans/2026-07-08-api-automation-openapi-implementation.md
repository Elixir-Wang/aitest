# 接口自动化与 OpenAPI 解析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目级接口自动化从 Soon 占位升级为可导入 OpenAPI、维护接口资产、生成接口自动化用例、生成 `pytest + requests` 代码、执行并读取 `pytest-json-report` 的完整闭环。

**Architecture:** 后端遵循当前 `api/v1 + schemas + repositories + services + agents` 分层，接口自动化状态全部落 sqlite，文件产物落 `apps/backend/data/projects/<project_id>/api_automation/`。生成链路先保存结构化 `api_test_cases`，再生成独立 pytest 工程；执行链路由 Runner 固定命令调用 uv/pytest，不允许前端传 shell。前端只改造当前 `/projects/[projectId]/automation/api` 页面，第一版使用表单式 UI 和 `Textarea` 脚本编辑。

**Tech Stack:** FastAPI / sqlite3 / Pydantic v2 / BackgroundTasks / uv / pytest / requests / pytest-json-report / Next.js App Router / React / lucide-react / shadcn-style local UI components.

---

## Source Spec

`docs/superpowers/specs/2026-07-08-api-automation-openapi-design.md`

## Global Decisions

1. 第一版导入来源只支持 OpenAPI/Swagger JSON/YAML。
2. 第一版实现表单式接口场景编排。
3. 第一版报告只使用 `pytest-json-report`，不使用 Allure、pytest-html、junitxml。
4. 每个项目维护独立 `api_test_environments`，不复用 UI 环境作为主对象。
5. 鉴权第一版支持 `none`、`static_bearer`、`static_headers`、`cookie`、`login_request`。
6. Secret 复用 `app/core/environment_credentials.py` 的 Fernet key、加密/解密、hash 校验思路，扩展支持接口环境。
7. 权限复用 `current_user`、`require_admin`、service 层 `_require_visible_project` 风格；写操作第一版要求 admin。
8. 后台任务复用 `BackgroundTasks + generation_runs + startup recover`，并纳入 `task_service`。
9. 前端 API 请求继续追加到 `apps/frontend/src/lib/api-client.ts`，本轮不拆新 client 文件。
10. 参考项目 `backend/app/services/openapi_parser.py` 不能整文件直接复制；只移植其 `paths` 遍历、HTTP method 过滤、tag 分组、endpoint 字段抽取逻辑。数据库写入、Folder 创建、Attachment/MinIO 读取、SQLAlchemy AsyncSession、UUID/JSONB model 全部按当前项目重写。

---

## File Structure

| 类别 | 路径 | 任务 |
|---|---|---|
| DB schema | `apps/backend/app/seed/schema.py` | T1 |
| Backend schemas | `apps/backend/app/schemas/api_automation.py` | T1 |
| Repository | `apps/backend/app/repositories/api_automation_repo.py` | T1 |
| API router | `apps/backend/app/api/v1/api_automation.py` | T2-T7 |
| Router registry | `apps/backend/app/api/v1/__init__.py` | T2 |
| OpenAPI parser | `apps/backend/app/services/api_automation/openapi_parser.py` | T2 |
| Service package | `apps/backend/app/services/api_automation/__init__.py` | T1 |
| Main service | `apps/backend/app/services/api_automation/service.py` | T2-T7 |
| Environment secrets | `apps/backend/app/core/environment_credentials.py` | T3 |
| Agent package | `apps/backend/app/agents/api_automation/*` | T4 |
| AI capabilities | `apps/backend/app/agents/capabilities.py` | T4 |
| Script generator | `apps/backend/app/services/api_automation/script_generator.py` | T5 |
| Runner | `apps/backend/app/services/api_automation/runner.py` | T6 |
| Reporting | `apps/backend/app/services/api_automation/reporting.py` | T6 |
| Task center | `apps/backend/app/services/task_service.py` | T7 |
| Startup | `apps/backend/app/main.py` | T7 |
| Frontend page | `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx` | T8 |
| Frontend components | `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/_components/*.tsx` | T8 |
| Frontend API client | `apps/frontend/src/lib/api-client.ts` | T8 |
| Backend tests | `apps/backend/tests/test_api_automation_*.py` | T1-T7 |

---

## Task 1: Schema, Pydantic Contracts, Repository

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Create: `apps/backend/app/schemas/api_automation.py`
- Create: `apps/backend/app/repositories/api_automation_repo.py`
- Create: `apps/backend/app/services/api_automation/__init__.py`
- Test: `apps/backend/tests/test_api_automation_schema_repo.py`

- [ ] **Step 1: Write repository/schema tests**

Create `apps/backend/tests/test_api_automation_schema_repo.py` with tests that initialize a temp DB, insert a project, create an API document, upsert endpoints by `method + normalized_path`, create generation run/case/script/run records, and verify foreign-key project scoping.

```python
from pathlib import Path
import sqlite3

import pytest

from app.core import settings
from app.core.db import connect
from app.seed.init_db import init_db
from app.repositories import api_automation_repo


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(settings, "DB_PATH", db_path)
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path / "projects")
    init_db()


def _seed_project() -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, ?, ?, ?)",
            ("project-1", "项目一", "", "active", "u-admin"),
        )


def test_upsert_endpoint_uses_method_and_normalized_path(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    with connect() as db:
        document_id = api_automation_repo.create_document(
            db,
            document_id="apidoc-1",
            project_id="project-1",
            name="Petstore",
            source_type="file",
            source_url="",
            file_path="documents/apidoc-1/openapi.yaml",
            version="3.0.3",
            endpoint_count=0,
            created_by="u-admin",
        )
        first = api_automation_repo.upsert_endpoint(
            db,
            endpoint_id="apiend-1",
            project_id="project-1",
            document_id=document_id,
            method="GET",
            path="/pets/{petId}",
            normalized_path="/pets/{petId}",
            summary="Get pet",
            description="",
            tags=["pet"],
            parameters=[],
            request_body={},
            responses={"200": {"description": "ok"}},
            auth={},
            source={"operationId": "getPet"},
            created_by="u-admin",
        )
        second = api_automation_repo.upsert_endpoint(
            db,
            endpoint_id="apiend-2",
            project_id="project-1",
            document_id=document_id,
            method="GET",
            path="/pets/{petId}",
            normalized_path="/pets/{petId}",
            summary="Get pet v2",
            description="updated",
            tags=["pet"],
            parameters=[],
            request_body={},
            responses={"404": {"description": "missing"}},
            auth={},
            source={"operationId": "getPetV2"},
            created_by="u-admin",
        )
        rows = api_automation_repo.list_endpoints(db, "project-1")
    assert first == second
    assert len(rows) == 1
    assert rows[0]["summary"] == "Get pet v2"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_schema_repo.py -q
```

Expected: FAIL because `api_automation_repo` and new tables do not exist.

- [ ] **Step 3: Add sqlite schema**

Append tables and indexes in `apps/backend/app/seed/schema.py` after related project/test-case tables:

```sql
CREATE TABLE IF NOT EXISTS api_documents (...);
CREATE TABLE IF NOT EXISTS api_endpoints (... UNIQUE(project_id, method, normalized_path));
CREATE TABLE IF NOT EXISTS api_generation_runs (...);
CREATE TABLE IF NOT EXISTS api_test_cases (...);
CREATE TABLE IF NOT EXISTS api_test_scripts (...);
CREATE TABLE IF NOT EXISTS api_automation_runs (...);
CREATE TABLE IF NOT EXISTS api_test_environments (... UNIQUE(project_id, name));
CREATE TABLE IF NOT EXISTS api_scenarios (...);
CREATE TABLE IF NOT EXISTS api_scenario_steps (...);
```

Use the exact column contract from the spec. Add indexes for:

```sql
CREATE INDEX IF NOT EXISTS idx_api_documents_project_created ON api_documents(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_api_endpoints_project_method ON api_endpoints(project_id, method);
CREATE INDEX IF NOT EXISTS idx_api_generation_runs_project_created ON api_generation_runs(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_api_test_cases_project_endpoint ON api_test_cases(project_id, endpoint_id);
CREATE INDEX IF NOT EXISTS idx_api_scripts_project_updated ON api_test_scripts(project_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_api_runs_project_created ON api_automation_runs(project_id, created_at);
```

- [ ] **Step 4: Add Pydantic schemas**

Create `apps/backend/app/schemas/api_automation.py` with input/output models for document import, endpoint CRUD, environment CRUD, generation request/result, API test case update, script update, run create/result, scenario/step CRUD. Use `field_validator` to normalize blank strings and enforce non-empty `name`, `method`, `path`, `api_base_url`.

- [ ] **Step 5: Add repository functions**

Create `apps/backend/app/repositories/api_automation_repo.py`. Include JSON helpers and functions used by later tasks:

```python
def dumps_json(value) -> str: ...
def loads_json(value: str, default): ...
def create_document(db, *, document_id: str, project_id: str, ...): ...
def update_document_status(db, document_id: str, *, status: str, endpoint_count: int, error_message: str = "") -> None: ...
def upsert_endpoint(db, *, endpoint_id: str, project_id: str, method: str, normalized_path: str, ...) -> str: ...
def list_endpoints(db, project_id: str, *, method: str = "", tag: str = "", search: str = "") -> list: ...
def find_endpoint(db, endpoint_id: str): ...
def create_generation_run(db, *, run_id: str, task_id: str, project_id: str, ...): ...
def update_generation_run(db, run_id: str, *, status: str, result_summary: dict | None = None, error_message: str = "", finished: bool = False): ...
def create_api_test_case(db, *, case_id: str, project_id: str, endpoint_id: str | None, ...): ...
def list_api_test_cases(db, project_id: str, *, endpoint_id: str = "", status: str = "") -> list: ...
def update_api_test_case(db, case_id: str, **fields) -> None: ...
def create_script(db, *, script_id: str, project_id: str, ...): ...
def create_api_run(db, *, run_id: str, task_id: str, project_id: str, ...): ...
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_schema_repo.py -q
```

Expected: PASS.

---

## Task 2: OpenAPI Import and Endpoint Asset APIs

**Files:**
- Create: `apps/backend/app/services/api_automation/openapi_parser.py`
- Create/Modify: `apps/backend/app/services/api_automation/service.py`
- Create: `apps/backend/app/api/v1/api_automation.py`
- Modify: `apps/backend/app/api/v1/__init__.py`
- Test: `apps/backend/tests/test_api_automation_openapi_import.py`

- [ ] **Step 1: Write parser/import tests**

Create tests for OpenAPI 3 JSON/YAML, Swagger 2, missing `paths`, duplicate import upsert, and guest read/admin write permission. Use a tiny spec:

```python
OPENAPI = {
    "openapi": "3.0.3",
    "info": {"title": "Petstore", "version": "1.0.0"},
    "paths": {
        "/pets/{petId}": {
            "get": {
                "summary": "Get pet",
                "tags": ["pet"],
                "parameters": [{"name": "petId", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "ok"}},
            }
        }
    },
}
```

- [ ] **Step 2: Run parser tests to verify failure**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_openapi_import.py -q
```

Expected: FAIL because parser/router do not exist.

- [ ] **Step 3: Implement parser**

`openapi_parser.py` should expose:

```python
class OpenAPIParseError(ValueError): ...

def parse_openapi_document(raw: str, *, source_name: str = "") -> dict:
    """Return {title, version, endpoints[]} or raise OpenAPIParseError."""
```

Support JSON first, then YAML via existing dependency if available. Normalize method to uppercase and path unchanged except trimming. Endpoint dict must include `method`, `path`, `normalized_path`, `summary`, `description`, `tags`, `parameters`, `request_body`, `responses`, `auth`, `source`.

Reference-porting rule: take the extraction shape from the target project's `OpenAPIParser._group_endpoints_by_tag`, but implement it as pure functions with no database session. Do not copy `_create_tag_folder`, `_create_endpoint_folder`, `parse_and_create_structure`, or `parse_openapi_from_attachment`, because those are coupled to SQLAlchemy models, folders, attachments, UUIDs, and storage choices that do not exist in the current project.

- [ ] **Step 4: Implement service functions**

In `service.py`, add:

```python
def import_openapi_text(project_id: str, payload, actor) -> dict: ...
def list_project_endpoints(project_id: str, actor, *, method="", tag="", search="") -> list[dict]: ...
def get_project_endpoint(project_id: str, endpoint_id: str, actor) -> dict: ...
def create_project_endpoint(project_id: str, payload, actor) -> dict: ...
def update_project_endpoint(project_id: str, endpoint_id: str, payload, actor) -> dict: ...
def delete_project_endpoint(project_id: str, endpoint_id: str, actor) -> None: ...
```

Copy `_require_visible_project` and `_require_admin` style from `test_case_service.py`, but keep local to `api_automation/service.py` until a shared helper exists.

- [ ] **Step 5: Implement router**

`api_automation.py` routes:

```python
router = APIRouter(prefix="/projects/{project_id}", tags=["api-automation"])
POST /api-documents/import
GET /api-endpoints
POST /api-endpoints
GET /api-endpoints/{endpoint_id}
PATCH /api-endpoints/{endpoint_id}
DELETE /api-endpoints/{endpoint_id}
```

Register in `api/v1/__init__.py`:

```python
from app.api.v1 import api_automation
v1_router.include_router(api_automation.router)
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_openapi_import.py tests/test_api_automation_schema_repo.py -q
```

Expected: PASS.

---

## Task 3: API Environment and Secret Reuse

**Files:**
- Modify: `apps/backend/app/core/environment_credentials.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Test: `apps/backend/tests/test_api_automation_environment.py`

- [ ] **Step 1: Write environment tests**

Cover create/update/list/delete, encrypted password/token storage, no plaintext serialization, and `login_request` config validation.

- [ ] **Step 2: Extend credential helpers**

Add table-aware helpers without breaking current UI environment functions:

```python
def save_api_environment_secret(environment_id: str, *, field: str, value: str) -> str:
    encrypted = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return encrypted

def decrypt_api_environment_secret(value: str) -> str | None:
    return _decrypt_secret(value)
```

Do not expose decrypted secret in normal API serializers.

- [ ] **Step 3: Add environment service/router**

Routes:

```http
GET    /api-environments
POST   /api-environments
PATCH  /api-environments/{environment_id}
DELETE /api-environments/{environment_id}
```

Validation:
- `auth_type=none` allows empty secret.
- `static_bearer` requires encrypted token value in auth config.
- `static_headers` requires at least one encrypted/static header.
- `cookie` requires cookie name and encrypted value.
- `login_request` requires method, login path, token/cookie extract path, inject target.

- [ ] **Step 4: Run tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_environment.py -q
```

Expected: PASS.

---

## Task 4: Agent API Test Case Generation

**Files:**
- Create: `apps/backend/app/agents/api_automation/__init__.py`
- Create: `apps/backend/app/agents/api_automation/schemas.py`
- Create: `apps/backend/app/agents/api_automation/prompts.py`
- Create: `apps/backend/app/agents/api_automation/agent.py`
- Create: `apps/backend/app/agents/api_automation/service.py`
- Create: `apps/backend/app/agents/api_automation/skills/api-test-generation/SKILL.md`
- Create: `apps/backend/app/agents/api_automation/skills/api-test-generation/references/*.md`
- Modify: `apps/backend/app/agents/capabilities.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Test: `apps/backend/tests/test_api_automation_generation_agent.py`

- [ ] **Step 1: Write generation tests**

Mock the agent service to return two structured cases: one `ready`, one `needs_input`. Assert service saves `api_generation_runs`, `api_test_cases`, and does not generate script for `needs_input`.

- [ ] **Step 2: Add structured schemas**

`agents/api_automation/schemas.py`:

```python
class ApiAssertion(BaseModel):
    type: Literal["status_code", "jsonpath_equals", "jsonpath_exists", "schema_contains"]
    path: str = ""
    expected: Any = None

class ApiGeneratedCase(BaseModel):
    title: str
    priority: str = "P2"
    endpoint_id: str
    source: Literal["ai_generated", "manual", "approved_test_case"] = "ai_generated"
    request: dict
    expected: dict
    assertions: list[ApiAssertion]
    variables: dict = Field(default_factory=dict)
    data_origin: dict = Field(default_factory=dict)
    status: Literal["draft", "ready", "needs_input"] = "draft"
    notes: str = ""

class ApiAutomationGenerationResult(BaseModel):
    summary: str
    cases: list[ApiGeneratedCase]
```

- [ ] **Step 3: Add agent service**

Follow `agents/test_case_generation/service.py` pattern. Capability id: `api_test_generation`. It should accept endpoint definitions, environment summary without secrets, user goal, and source test cases. Return `ApiAutomationGenerationResult`.

- [ ] **Step 4: Add skill references**

Create reference files:
- `pytest-requests-style.md`
- `project-test-layout.md`
- `data-separation.md`
- `json-report-contract.md`

Keep them short and directive: code/data separation, `requests.Session`, no hardcoded base URL/token, pytest-json-report metadata.

- [ ] **Step 5: Add generation API**

Routes:

```http
POST /api-automation/generate
GET  /api-automation/generation-runs/{run_id}
GET  /api-test-cases
PATCH /api-test-cases/{case_id}
```

Use `BackgroundTasks` like test-case generation.

- [ ] **Step 6: Run tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_generation_agent.py -q
```

Expected: PASS.

---

## Task 5: Pytest Script Generator

**Files:**
- Create: `apps/backend/app/services/api_automation/script_generator.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Test: `apps/backend/tests/test_api_automation_script_generator.py`

- [ ] **Step 1: Write generator tests**

Given a ready API test case, assert generator creates:

```text
pytest.ini
pyproject.toml
conftest.py
tests/test_api_<slug>.py
data/test_api_<slug>.json
support/client.py
support/auth.py
support/assertions.py
README.md
```

Assert test file uses data file and does not contain base URL or token literals.

- [ ] **Step 2: Implement generator**

Expose:

```python
def generate_pytest_suite(*, project_id: str, suite_id: str, cases: list[dict], output_root: Path) -> dict:
    """Return {suite_path, test_file_path, data_file_path, script_name}."""
```

Generated `pyproject.toml` must include:

```toml
[project]
dependencies = ["pytest", "requests", "pytest-json-report"]
```

Generated test should be simple:

```python
def test_case(api_client, case_data):
    response = api_client.request(case_data["request"])
    assert response.status_code == case_data["expected"]["status_code"]
    assert_json_assertions(response, case_data["assertions"])
```

- [ ] **Step 3: Add regenerate script API**

Route:

```http
POST /api-automation/scripts/generate
```

Reject any selected `api_test_cases.status != "ready"` with 400 and explicit message.

- [ ] **Step 4: Add script view/edit APIs**

Routes:

```http
GET   /api-scripts/{script_id}
PATCH /api-scripts/{script_id}
```

Patch only writes within the stored `test_file_path`; validate resolved path is under `apps/backend/data/projects/<project_id>/api_automation/generated/`.

- [ ] **Step 5: Run tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_script_generator.py -q
```

Expected: PASS.

---

## Task 6: Runner and JSON Reporting

**Files:**
- Create: `apps/backend/app/services/api_automation/runner.py`
- Create: `apps/backend/app/services/api_automation/reporting.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Test: `apps/backend/tests/test_api_automation_runner.py`

- [ ] **Step 1: Write runner tests**

Use a temp generated suite with a tiny pytest file. Assert runner:
- deletes stale `report.json`, `stdout.txt`, `stderr.txt`;
- writes runtime `env.json` without secrets;
- calls fixed uv/pytest command;
- parses `report.json` summary;
- marks failed when report is missing.

- [ ] **Step 2: Implement reporting parser**

`reporting.py`:

```python
def parse_pytest_json_report(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    return {
        "total": summary.get("total", 0),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 0),
        "duration": data.get("duration", 0),
        "exitcode": data.get("exitcode"),
        "tests": data.get("tests", []),
    }
```

- [ ] **Step 3: Implement runner**

`runner.py`:

```python
def run_script_suite(*, run_id: str, project_id: str, suite_path: Path, run_dir: Path, environment: dict, timeout: int) -> dict:
    clear_previous_outputs(run_dir)
    write_runtime_env(run_dir, environment)
    subprocess.run(["uv", "sync"], cwd=suite_path, ...)
    subprocess.run(["uv", "run", "pytest", "tests", "--json-report", f"--json-report-file={run_dir / 'report.json'}"], cwd=suite_path, ...)
```

Capture stdout/stderr to files. Redact `authorization`, `cookie`, `token`, `password`, `secret` before writing logs.

- [ ] **Step 4: Add run APIs**

Routes:

```http
POST /api-runs
GET  /api-runs/{run_id}
GET  /api-runs/{run_id}/logs
GET  /api-runs/{run_id}/report
```

Execution uses `BackgroundTasks`.

- [ ] **Step 5: Run tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_runner.py -q
```

Expected: PASS.

---

## Task 7: Scenarios and Task Center Integration

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Modify: `apps/backend/app/services/task_service.py`
- Modify: `apps/backend/app/main.py`
- Test: `apps/backend/tests/test_api_automation_scenarios_tasks.py`
- Test: `apps/backend/tests/test_task_service.py`

- [ ] **Step 1: Write scenario/task tests**

Assert:
- create scenario;
- add two ordered steps;
- update extractor/assertion config;
- list scenario details;
- `task_service.list_running_tasks` includes active `api_automation_generation_run` and `api_automation_run`;
- startup recovery marks queued/running API automation tasks interrupted.

- [ ] **Step 2: Add scenario APIs**

Routes:

```http
GET    /api-scenarios
POST   /api-scenarios
GET    /api-scenarios/{scenario_id}
PATCH  /api-scenarios/{scenario_id}
DELETE /api-scenarios/{scenario_id}
POST   /api-scenarios/{scenario_id}/steps
PATCH  /api-scenarios/{scenario_id}/steps/{step_id}
DELETE /api-scenarios/{scenario_id}/steps/{step_id}
```

Step JSON includes endpoint id, order, request overrides, extractors, assertions.

- [ ] **Step 3: Integrate task_service**

Add source types:

```python
"api_automation_generation_run"
"api_automation_run"
```

Map statuses:

```python
API_AUTOMATION_GENERATION_STATUS = {
    "queued": (RUNNING_GROUP, "排队中"),
    "running": (RUNNING_GROUP, "生成中"),
    "completed": (COMPLETED_GROUP, "生成完成"),
    "failed": (FAILED_GROUP, "生成失败"),
    "cancelled": (COMPLETED_GROUP, "已取消"),
    "interrupted": (COMPLETED_GROUP, "已中断"),
}
```

Add collectors that join project id/name and respect visible projects.

- [ ] **Step 4: Add startup recovery**

In `main.py` startup, call:

```python
api_automation_service.recover_interrupted_api_automation_tasks()
```

Function marks active generation/runs as `interrupted` with clear error message.

- [ ] **Step 5: Run tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_scenarios_tasks.py tests/test_task_service.py -q
```

Expected: PASS.

---

## Task 8: Frontend API Automation Workbench

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx`
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/_components/api-document-import-dialog.tsx`
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/_components/api-endpoint-list.tsx`
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/_components/api-endpoint-detail.tsx`
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/_components/api-test-artifacts-panel.tsx`
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/_components/api-script-editor-dialog.tsx`
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/_components/api-run-panel.tsx`

- [ ] **Step 1: Add API client types/functions**

Append types for endpoints, environments, cases, scripts, runs, scenarios. Add functions:

```ts
listApiEndpoints(projectId, filters)
importOpenApiDocument(projectId, payload)
generateApiAutomation(projectId, payload)
listApiTestCases(projectId, filters)
generateApiScripts(projectId, payload)
getApiScript(projectId, scriptId)
updateApiScript(projectId, scriptId, payload)
createApiRun(projectId, payload)
getApiRun(projectId, runId)
```

- [ ] **Step 2: Replace Soon page**

`page.tsx` should render:
- top actions: import OpenAPI, generate cases/scripts, execute;
- metric strip: endpoint count, script count, recent run, failed count;
- tabs: 接口资产 / 测试脚本 / 运行记录 / 场景编排.

- [ ] **Step 3: Add import dialog**

Support URL and file modes. First version can submit URL/text payload; file upload uses `FormData` if backend route accepts multipart.

- [ ] **Step 4: Add endpoint list/detail**

List filters method/tag/search. Detail drawer/panel shows params, request body, responses, auth, scripts/cases.

- [ ] **Step 5: Add generation/artifacts panel**

Allow selected endpoints + environment + goal + `generate_code`. Show `ready` and `needs_input` counts from generation result.

- [ ] **Step 6: Add script editor**

Use local `Textarea`; no Monaco. Save via PATCH.

- [ ] **Step 7: Add run panel**

Select environment and scripts, call create run, poll run detail, show stdout/stderr summary and JSON summary.

- [ ] **Step 8: Run frontend checks**

Run:

```powershell
cd apps/frontend
npm run lint
npm run build
```

Expected: lint/build pass. If build is too slow locally, at least run `npm run lint` and document build blocker.

---

## Task 9: End-to-End Verification

**Files:**
- Test: `apps/backend/tests/test_api_automation_e2e_minimal.py`
- Existing frontend/backend touched files from Tasks 1-8.

- [ ] **Step 1: Add minimal backend E2E test**

The test should:
1. create project and API environment;
2. import tiny OpenAPI;
3. create a ready API test case without calling real LLM;
4. generate pytest suite;
5. run runner against a mocked/local script;
6. assert `report.json` summary is saved.

- [ ] **Step 2: Run focused backend tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_api_automation_*.py -q
```

Expected: PASS.

- [ ] **Step 3: Run existing regression slices**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_test_case_set_service.py tests/test_task_service.py tests/test_environment_service.py -q
```

Expected: PASS.

- [ ] **Step 4: Manual smoke**

Start backend/frontend:

```powershell
cd apps/backend
uv run uvicorn app.main:app --reload --port 8000
```

```powershell
cd apps/frontend
npm run dev
```

Smoke path:
1. Open `/projects/<projectId>/automation/api`.
2. Import a tiny OpenAPI JSON.
3. Confirm endpoint list/detail.
4. Create API environment.
5. Generate cases/scripts.
6. Open script editor.
7. Execute script.
8. Confirm run summary reads `report.json`.

---

## Self-Review Checklist

- [ ] Spec coverage: OpenAPI import, endpoints, environment, generation, scripts, runner, report JSON, scenario, task center, frontend are each mapped to a task.
- [ ] No Allure, pytest-html, or junitxml introduced.
- [ ] No Postman/capture import introduced.
- [ ] No frontend report visualization introduced beyond JSON summary.
- [ ] No hardcoded base URL/token/password in generated scripts.
- [ ] All write APIs use admin permission in V1.
- [ ] All paths written by runner/script editor are constrained under the project api_automation directory.
- [ ] Tests use `cd apps/backend; uv run pytest ...` and frontend uses `npm run lint/build`.
