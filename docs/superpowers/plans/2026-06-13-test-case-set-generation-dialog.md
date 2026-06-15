# Test Case Set Generation Dialog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the test case module flow for creating a test case set from one requirement, with auto-selected related exploration, default company knowledge, and full-or-specified generation scope.

**Architecture:** Add a focused backend test case set slice: schemas, repository, service, API router, SQLite tables, and task-center status mapping. The first implementation creates the test case set and generation run in a queued/generating state, records the generation input snapshot, and exposes list/detail data for the frontend; the real LLM generation worker can be added as a later slice. Frontend updates `/test-cases` to use the same Dialog structure as the existing exploration task dialog and to call the new API.

**Tech Stack:** FastAPI, Pydantic v2, SQLite repositories, existing task service, Next.js React, existing shadcn/radix UI wrappers, Node contract tests, backend pytest via `apps/backend/.venv`.

---

## Scope Check

This plan implements one cohesive slice: create and list test case sets from the `测试用例` page. It does not implement UI automation sets, UI automation code generation, or real LLM test case generation. The generated run is created as a task-like record and can be shown as `生成中`; a later plan can add the agent that turns the input snapshot into `test_cases` rows.

## File Structure

- Create `apps/backend/app/schemas/test_case.py`
  - Pydantic request/response models for test case sets and generation runs.
- Create `apps/backend/app/repositories/test_case_repo.py`
  - SQLite access for `test_case_sets`, `test_case_generation_runs`, and future `test_cases`.
- Create `apps/backend/app/services/test_case_service.py`
  - Permission checks, project/requirement/exploration validation, default related exploration lookup, create/list/detail orchestration.
- Create `apps/backend/app/api/v1/test_cases.py`
  - Project-scoped REST endpoints.
- Modify `apps/backend/app/api/v1/__init__.py`
  - Include the new router.
- Modify `apps/backend/app/seed/init_db.py`
  - Create the new tables and indexes.
- Modify `apps/backend/app/services/task_service.py`
  - Include `test_case_generation_run` in task center collection/status mapping.
- Create `apps/backend/tests/test_test_case_set_service.py`
  - Backend behavior tests for create/list/validation/task collection.
- Modify `apps/frontend/src/lib/api-client.ts`
  - Add API types for requirements, exploration runs, test case sets, and generation request.
- Modify `apps/frontend/src/app/(main)/test-cases/page.tsx`
  - Replace placeholder empty table with real state, list loading, search, and create dialog.
- Create `apps/frontend/tests/test-case-set-dialog-contract.test.mjs`
  - Source-level contract checks for required labels, default company knowledge, related exploration auto-selection, and specified scope behavior.

## Task 1: Backend Schema, Tables, and Repository

**Files:**
- Create: `apps/backend/app/schemas/test_case.py`
- Create: `apps/backend/app/repositories/test_case_repo.py`
- Modify: `apps/backend/app/seed/init_db.py`
- Test: `apps/backend/tests/test_test_case_set_service.py`

- [ ] **Step 1: Write failing backend schema/storage test**

Create `apps/backend/tests/test_test_case_set_service.py` with this initial content:

```python
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core import db as core_db
from app.core import storage
from app.seed.init_db import init_db
from app.schemas.test_case import TestCaseSetCreateIn
from app.services import test_case_service, task_service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}
GUEST = {"id": "u-guest", "role": "guest", "nickname": "访客", "username": "guest", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    init_db()


def _seed_project_requirement_and_exploration() -> None:
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description, created_by) VALUES (?, ?, 'active', '', ?)",
            ("project-1", "测试项目", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES (?, ?, ?, 'PRD', 'version-1', 'finalized', ?)
            """,
            ("doc-1", "project-1", "登录需求", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO source_document_versions
              (id, document_id, version_no, markdown_content, file_path, source_action, change_summary, created_by)
            VALUES (?, ?, 1, ?, ?, 'finalize_requirement_analysis', '确认最终需求', ?)
            """,
            ("version-1", "doc-1", "# 登录需求\n\n用户可以登录系统。", "project-1/requirements/doc-1/versions/v1.md", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO project_environments (id, project_id, name, site_url, login_strategy, created_by)
            VALUES (?, ?, ?, ?, 'skip_login', ?)
            """,
            ("env-1", "project-1", "测试环境", "https://example.test", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO exploration_runs
              (id, project_id, environment_id, requirement_doc_id, title, status, scope, goal, created_by, updated_at)
            VALUES (?, ?, ?, ?, ?, 'completed', '登录', '采集登录页面事实', ?, CURRENT_TIMESTAMP)
            """,
            ("explore-1", "project-1", "env-1", "doc-1", "登录探索", ACTOR["id"]),
        )


def test_create_test_case_set_defaults_company_knowledge_and_related_exploration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()

    created = test_case_service.create_test_case_set(
        "project-1",
        TestCaseSetCreateIn(
            name="登录需求测试用例集",
            requirement_doc_id="doc-1",
            generation_scope_type="all",
        ),
        ACTOR,
    )

    assert created["name"] == "登录需求测试用例集"
    assert created["requirement_doc_id"] == "doc-1"
    assert created["requirement_doc_title"] == "登录需求"
    assert created["exploration_run_id"] == "explore-1"
    assert created["exploration_run_title"] == "登录探索"
    assert created["include_company_knowledge"] is True
    assert created["generation_scope_type"] == "all"
    assert created["generation_scope_text"] == ""
    assert created["status"] == "generating"
    assert created["case_count"] == 0
    assert created["generation_run"]["status"] == "queued"
    assert created["generation_run"]["input_snapshot"]["company_knowledge_role"] == "testing_guidance_only"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_test_case_set_service.py::test_create_test_case_set_defaults_company_knowledge_and_related_exploration -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.test_case'`.

- [ ] **Step 3: Add backend schemas**

Create `apps/backend/app/schemas/test_case.py`:

```python
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


GenerationScopeType = Literal["all", "specified"]


class TestCaseSetCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    requirement_doc_id: str = Field(min_length=1)
    exploration_run_id: str = ""
    include_company_knowledge: bool = True
    generation_scope_type: GenerationScopeType = "all"
    generation_scope_text: str = ""
    notes: str = ""

    @field_validator("name", "requirement_doc_id", "exploration_run_id", "generation_scope_text", "notes", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("generation_scope_text")
    @classmethod
    def _validate_scope_text(cls, value: str, info) -> str:
        if info.data.get("generation_scope_type") == "specified" and not value:
            raise ValueError("指定范围模式下必须填写生成范围。")
        return value


class TestCaseGenerationRunOut(BaseModel):
    id: str
    test_case_set_id: str
    task_id: str
    status: str
    input_snapshot: dict[str, Any]
    error_message: str
    created_at: str
    finished_at: str | None = None


class TestCaseSetOut(BaseModel):
    id: str
    project_id: str
    project_name: str = ""
    name: str
    requirement_doc_id: str
    requirement_doc_title: str = ""
    exploration_run_id: str = ""
    exploration_run_title: str = ""
    include_company_knowledge: bool
    generation_scope_type: GenerationScopeType
    generation_scope_text: str
    notes: str
    status: str
    status_label: str
    case_count: int
    created_by: str
    created_at: str
    updated_at: str
    generation_run: TestCaseGenerationRunOut | None = None
```

- [ ] **Step 4: Add tables in `init_db.py`**

In `apps/backend/app/seed/init_db.py`, inside the large `db.executescript("""...""")` block after `dashboard_daily_stats`, add:

```sql
            CREATE TABLE IF NOT EXISTS test_case_sets (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              name TEXT NOT NULL,
              requirement_doc_id TEXT NOT NULL,
              exploration_run_id TEXT NOT NULL DEFAULT '',
              include_company_knowledge INTEGER NOT NULL DEFAULT 1,
              generation_scope_type TEXT NOT NULL CHECK(generation_scope_type IN ('all', 'specified')),
              generation_scope_text TEXT NOT NULL DEFAULT '',
              notes TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL CHECK(status IN ('generating', 'ready_for_review', 'failed', 'archived')) DEFAULT 'generating',
              case_count INTEGER NOT NULL DEFAULT 0,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              FOREIGN KEY(requirement_doc_id) REFERENCES source_documents(id) ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS idx_test_case_sets_project_updated
              ON test_case_sets(project_id, updated_at);
            CREATE INDEX IF NOT EXISTS idx_test_case_sets_requirement
              ON test_case_sets(requirement_doc_id);

            CREATE TABLE IF NOT EXISTS test_case_generation_runs (
              id TEXT PRIMARY KEY,
              test_case_set_id TEXT NOT NULL,
              task_id TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed')) DEFAULT 'queued',
              input_json TEXT NOT NULL DEFAULT '{}',
              error_message TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              finished_at TEXT,
              FOREIGN KEY(test_case_set_id) REFERENCES test_case_sets(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_test_case_generation_runs_set
              ON test_case_generation_runs(test_case_set_id, created_at);

            CREATE TABLE IF NOT EXISTS test_cases (
              id TEXT PRIMARY KEY,
              test_case_set_id TEXT NOT NULL,
              project_id TEXT NOT NULL,
              case_no TEXT NOT NULL,
              title TEXT NOT NULL,
              module_name TEXT NOT NULL DEFAULT '',
              scenario_type TEXT NOT NULL DEFAULT '',
              priority TEXT NOT NULL DEFAULT 'P1',
              risk_level TEXT NOT NULL DEFAULT 'medium',
              preconditions TEXT NOT NULL DEFAULT '',
              steps_json TEXT NOT NULL DEFAULT '[]',
              expected_results TEXT NOT NULL DEFAULT '',
              source_refs_json TEXT NOT NULL DEFAULT '[]',
              automation_feasibility TEXT NOT NULL DEFAULT 'needs_review',
              review_status TEXT NOT NULL DEFAULT 'pending_review',
              version_no INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(test_case_set_id) REFERENCES test_case_sets(id) ON DELETE CASCADE,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              UNIQUE(project_id, case_no)
            );
```

- [ ] **Step 5: Add repository**

Create `apps/backend/app/repositories/test_case_repo.py`:

```python
from sqlite3 import Connection, Row


BASE_SET_SELECT = """
SELECT tcs.*,
       p.name AS project_name,
       d.name AS requirement_doc_title,
       COALESCE(er.title, '') AS exploration_run_title
FROM test_case_sets tcs
JOIN projects p ON p.id = tcs.project_id
JOIN source_documents d ON d.id = tcs.requirement_doc_id
LEFT JOIN exploration_runs er ON er.id = tcs.exploration_run_id
"""


def list_by_project(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        f"""
        {BASE_SET_SELECT}
        WHERE tcs.project_id = ?
        ORDER BY tcs.updated_at DESC, tcs.created_at DESC
        """,
        (project_id,),
    ).fetchall()


def find_set_by_id(db: Connection, set_id: str) -> Row | None:
    return db.execute(f"{BASE_SET_SELECT} WHERE tcs.id = ?", (set_id,)).fetchone()


def create_set(
    db: Connection,
    *,
    set_id: str,
    project_id: str,
    name: str,
    requirement_doc_id: str,
    exploration_run_id: str,
    include_company_knowledge: bool,
    generation_scope_type: str,
    generation_scope_text: str,
    notes: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO test_case_sets
          (id, project_id, name, requirement_doc_id, exploration_run_id, include_company_knowledge,
           generation_scope_type, generation_scope_text, notes, status, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'generating', ?)
        """,
        (
            set_id,
            project_id,
            name,
            requirement_doc_id,
            exploration_run_id,
            1 if include_company_knowledge else 0,
            generation_scope_type,
            generation_scope_text,
            notes,
            created_by,
        ),
    )


def create_generation_run(
    db: Connection,
    *,
    run_id: str,
    test_case_set_id: str,
    task_id: str,
    input_json: str,
) -> None:
    db.execute(
        """
        INSERT INTO test_case_generation_runs
          (id, test_case_set_id, task_id, status, input_json)
        VALUES (?, ?, ?, 'queued', ?)
        """,
        (run_id, test_case_set_id, task_id, input_json),
    )


def latest_generation_run(db: Connection, test_case_set_id: str) -> Row | None:
    return db.execute(
        """
        SELECT *
        FROM test_case_generation_runs
        WHERE test_case_set_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (test_case_set_id,),
    ).fetchone()


def latest_related_exploration(db: Connection, project_id: str, requirement_doc_id: str) -> Row | None:
    return db.execute(
        """
        SELECT id, title, status
        FROM exploration_runs
        WHERE project_id = ?
          AND requirement_doc_id = ?
          AND status IN ('completed', 'partial')
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
        """,
        (project_id, requirement_doc_id),
    ).fetchone()
```

- [ ] **Step 6: Run focused test**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_test_case_set_service.py::test_create_test_case_set_defaults_company_knowledge_and_related_exploration -q
```

Expected: still FAIL because `app.services.test_case_service` does not exist. That failure is correct for this task.

- [ ] **Step 7: Commit**

```powershell
git add apps/backend/app/schemas/test_case.py apps/backend/app/repositories/test_case_repo.py apps/backend/app/seed/init_db.py apps/backend/tests/test_test_case_set_service.py
git commit -m "feat: add test case set storage contracts"
```

## Task 2: Backend Service and API

**Files:**
- Create: `apps/backend/app/services/test_case_service.py`
- Create: `apps/backend/app/api/v1/test_cases.py`
- Modify: `apps/backend/app/api/v1/__init__.py`
- Modify: `apps/backend/tests/test_test_case_set_service.py`

- [ ] **Step 1: Extend backend tests for validation and listing**

Append these tests to `apps/backend/tests/test_test_case_set_service.py`:

```python
def test_create_test_case_set_requires_specified_scope_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()

    with pytest.raises(ValueError):
        TestCaseSetCreateIn(
            name="登录需求测试用例集",
            requirement_doc_id="doc-1",
            generation_scope_type="specified",
            generation_scope_text="",
        )


def test_create_test_case_set_rejects_requirement_from_other_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description, created_by) VALUES (?, ?, 'active', '', ?)",
            ("project-2", "其他项目", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
            VALUES (?, ?, ?, 'PRD', 'finalized', ?)
            """,
            ("doc-2", "project-2", "其他需求", ACTOR["id"]),
        )

    with pytest.raises(HTTPException) as exc_info:
        test_case_service.create_test_case_set(
            "project-1",
            TestCaseSetCreateIn(name="非法用例集", requirement_doc_id="doc-2"),
            ACTOR,
        )

    assert exc_info.value.detail["code"] == "INVALID_REQUIREMENT_DOCUMENT"


def test_guest_cannot_create_test_case_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()

    with pytest.raises(HTTPException) as exc_info:
        test_case_service.create_test_case_set(
            "project-1",
            TestCaseSetCreateIn(name="登录需求测试用例集", requirement_doc_id="doc-1"),
            GUEST,
        )

    assert exc_info.value.status_code == 403


def test_list_test_case_sets_returns_latest_generation_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()
    created = test_case_service.create_test_case_set(
        "project-1",
        TestCaseSetCreateIn(
            name="登录部分测试用例集",
            requirement_doc_id="doc-1",
            generation_scope_type="specified",
            generation_scope_text="这个需求中登录部分的测试用例",
        ),
        ACTOR,
    )

    items = test_case_service.list_project_test_case_sets("project-1", ACTOR)

    assert [item["id"] for item in items] == [created["id"]]
    assert items[0]["generation_scope_text"] == "这个需求中登录部分的测试用例"
    assert items[0]["generation_run"]["task_id"].startswith("test_case_generation:")
```

- [ ] **Step 2: Run tests to verify failures**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_test_case_set_service.py -q
```

Expected: FAIL because service functions and router do not exist yet.

- [ ] **Step 3: Implement service**

Create `apps/backend/app/services/test_case_service.py`:

```python
import json
from uuid import uuid4

from fastapi import HTTPException

from app.core.db import connect
from app.repositories import exploration_repo, test_case_repo
from app.schemas.test_case import TestCaseSetCreateIn


TEST_CASE_SET_STATUS_LABELS = {
    "generating": "生成中",
    "ready_for_review": "待评审",
    "failed": "生成失败",
    "archived": "已归档",
}


def list_project_test_case_sets(project_id: str, actor) -> list[dict]:
    _ensure_can_view_project(project_id, actor)
    with connect() as db:
        rows = test_case_repo.list_by_project(db, project_id)
        return [_serialize_set(db, row) for row in rows]


def get_project_test_case_set(project_id: str, set_id: str, actor) -> dict:
    _ensure_can_view_project(project_id, actor)
    with connect() as db:
        row = test_case_repo.find_set_by_id(db, set_id)
        if not row or row["project_id"] != project_id:
            raise _api_error(404, "TEST_CASE_SET_NOT_FOUND", "测试用例集不存在。")
        return _serialize_set(db, row)


def create_test_case_set(project_id: str, payload: TestCaseSetCreateIn, actor) -> dict:
    _ensure_can_create(actor)
    _ensure_can_view_project(project_id, actor)
    with connect() as db:
        requirement = db.execute(
            "SELECT id, project_id, name, current_version_id, status FROM source_documents WHERE id = ?",
            (payload.requirement_doc_id,),
        ).fetchone()
        if not requirement or requirement["project_id"] != project_id:
            raise _api_error(400, "INVALID_REQUIREMENT_DOCUMENT", "需求不属于当前项目。")

        exploration_run_id = payload.exploration_run_id
        if exploration_run_id:
            exploration = exploration_repo.find_by_id(db, exploration_run_id)
            if not exploration or exploration["project_id"] != project_id:
                raise _api_error(400, "INVALID_EXPLORATION_RUN", "探索任务不属于当前项目。")
        else:
            related = test_case_repo.latest_related_exploration(db, project_id, payload.requirement_doc_id)
            exploration_run_id = related["id"] if related else ""

        set_id = f"tcs-{uuid4().hex[:16]}"
        run_id = f"tcgr-{uuid4().hex[:16]}"
        task_id = f"test_case_generation:{run_id}"
        input_snapshot = _generation_input_snapshot(
            project_id=project_id,
            payload=payload,
            exploration_run_id=exploration_run_id,
            actor=actor,
        )
        test_case_repo.create_set(
            db,
            set_id=set_id,
            project_id=project_id,
            name=payload.name,
            requirement_doc_id=payload.requirement_doc_id,
            exploration_run_id=exploration_run_id,
            include_company_knowledge=payload.include_company_knowledge,
            generation_scope_type=payload.generation_scope_type,
            generation_scope_text=payload.generation_scope_text if payload.generation_scope_type == "specified" else "",
            notes=payload.notes,
            created_by=actor["id"],
        )
        test_case_repo.create_generation_run(
            db,
            run_id=run_id,
            test_case_set_id=set_id,
            task_id=task_id,
            input_json=json.dumps(input_snapshot, ensure_ascii=False, separators=(",", ":")),
        )
        row = test_case_repo.find_set_by_id(db, set_id)
        if not row:
            raise _api_error(500, "TEST_CASE_SET_CREATE_FAILED", "测试用例集创建失败。")
        return _serialize_set(db, row)


def _generation_input_snapshot(*, project_id: str, payload: TestCaseSetCreateIn, exploration_run_id: str, actor) -> dict:
    return {
        "project_id": project_id,
        "requirement_doc_id": payload.requirement_doc_id,
        "exploration_run_id": exploration_run_id,
        "include_company_knowledge": payload.include_company_knowledge,
        "company_knowledge_role": "testing_guidance_only",
        "generation_scope_type": payload.generation_scope_type,
        "generation_scope_text": payload.generation_scope_text if payload.generation_scope_type == "specified" else "",
        "notes": payload.notes,
        "created_by": actor["id"],
    }


def _serialize_set(db, row) -> dict:
    generation_run = test_case_repo.latest_generation_run(db, row["id"])
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "project_name": row["project_name"],
        "name": row["name"],
        "requirement_doc_id": row["requirement_doc_id"],
        "requirement_doc_title": row["requirement_doc_title"],
        "exploration_run_id": row["exploration_run_id"],
        "exploration_run_title": row["exploration_run_title"],
        "include_company_knowledge": bool(row["include_company_knowledge"]),
        "generation_scope_type": row["generation_scope_type"],
        "generation_scope_text": row["generation_scope_text"],
        "notes": row["notes"],
        "status": row["status"],
        "status_label": TEST_CASE_SET_STATUS_LABELS.get(row["status"], row["status"]),
        "case_count": row["case_count"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "generation_run": _serialize_generation_run(generation_run),
    }


def _serialize_generation_run(row) -> dict | None:
    if not row:
        return None
    return {
        "id": row["id"],
        "test_case_set_id": row["test_case_set_id"],
        "task_id": row["task_id"],
        "status": row["status"],
        "input_snapshot": json.loads(row["input_json"] or "{}"),
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
    }


def _ensure_can_create(actor) -> None:
    if actor["role"] == "guest":
        raise _api_error(403, "PERMISSION_DENIED", "访客不能创建测试用例集。")


def _ensure_can_view_project(project_id: str, actor) -> None:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return
    with connect() as db:
        row = db.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not row or row["name"] != actor["project_scope"]:
        raise _api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
```

- [ ] **Step 4: Add API router**

Create `apps/backend/app/api/v1/test_cases.py`:

```python
from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user
from app.schemas.test_case import TestCaseSetCreateIn, TestCaseSetOut
from app.services import test_case_service

router = APIRouter(prefix="/projects/{project_id}/test-case-sets", tags=["test-cases"])


@router.get("", response_model=list[TestCaseSetOut])
def list_project_test_case_sets(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return test_case_service.list_project_test_case_sets(project_id, actor)


@router.post("", response_model=TestCaseSetOut)
def create_project_test_case_set(
    project_id: str,
    payload: TestCaseSetCreateIn,
    actor=Depends(current_user),
) -> dict:
    return test_case_service.create_test_case_set(project_id, payload, actor)


@router.get("/{set_id}", response_model=TestCaseSetOut)
def get_project_test_case_set(project_id: str, set_id: str, actor=Depends(current_user)) -> dict:
    return test_case_service.get_project_test_case_set(project_id, set_id, actor)
```

Modify `apps/backend/app/api/v1/__init__.py`:

```python
from app.api.v1 import agents, ai, auth, dashboard, documents, environments, exploration, global_knowledge, knowledge, models, operation_logs, projects, requirement_exploration, requirements, tasks, test_cases, users
```

Then add the router include near other project workspace routers:

```python
v1_router.include_router(test_cases.router)
```

- [ ] **Step 5: Run backend tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_test_case_set_service.py -q
```

Expected: PASS for all tests in this file.

- [ ] **Step 6: Commit**

```powershell
git add apps/backend/app/services/test_case_service.py apps/backend/app/api/v1/test_cases.py apps/backend/app/api/v1/__init__.py apps/backend/tests/test_test_case_set_service.py
git commit -m "feat: add test case set creation api"
```

## Task 3: Task Center Integration

**Files:**
- Modify: `apps/backend/app/services/task_service.py`
- Modify: `apps/backend/tests/test_test_case_set_service.py`

- [ ] **Step 1: Add failing task-center test**

Append to `apps/backend/tests/test_test_case_set_service.py`:

```python
def test_test_case_generation_run_appears_in_task_center(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()
    created = test_case_service.create_test_case_set(
        "project-1",
        TestCaseSetCreateIn(name="登录需求测试用例集", requirement_doc_id="doc-1"),
        ACTOR,
    )

    tasks = task_service.list_tasks(ACTOR, project_id="project-1", module="test_case")

    assert len(tasks["items"]) == 1
    task = tasks["items"][0]
    assert task["source_type"] == "test_case_generation_run"
    assert task["source_id"] == created["generation_run"]["id"]
    assert task["module"] == "test_case"
    assert task["module_label"] == "测试用例"
    assert task["title"] == "登录需求测试用例集"
    assert task["status"] == "queued"
    assert task["status_label"] == "排队中"
    assert task["status_group"] == "waiting"
    assert task["detail_url"] == f"/test-cases?set={created['id']}"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_test_case_set_service.py::test_test_case_generation_run_appears_in_task_center -q
```

Expected: FAIL because task service does not collect test case generation runs.

- [ ] **Step 3: Modify task service**

In `apps/backend/app/services/task_service.py`, add:

```python
TEST_CASE_GENERATION_STATUS = {
    "queued": (WAITING_GROUP, "排队中"),
    "running": (RUNNING_GROUP, "生成中"),
    "completed": (COMPLETED_GROUP, "生成完成"),
    "failed": (FAILED_GROUP, "生成失败"),
}
```

Add `"test_case_generation_run"` to `RUNNING_INDICATOR_SOURCE_TYPES` only if queued/running should show in the top running indicator. For parity with requirements, include it:

```python
RUNNING_INDICATOR_SOURCE_TYPES = {
    "exploration_run",
    "requirement_file",
    "requirement_analysis_run",
    "test_case_generation_run",
}
```

Add to `STATUS_META_BY_SOURCE_TYPE`:

```python
    "test_case_generation_run": TEST_CASE_GENERATION_STATUS,
```

In `_collect_visible_tasks`, include:

```python
            *_test_case_generation_tasks(db, project_names),
```

Define before `_task`:

```python
def _test_case_generation_tasks(db, project_names: dict[str, str]) -> list[dict]:
    if not project_names:
        return []
    rows = db.execute(
        """
        SELECT r.id, r.task_id, r.status, r.error_message, r.created_at, r.updated_at,
               s.id AS set_id, s.project_id, s.name AS set_name
        FROM test_case_generation_runs r
        JOIN test_case_sets s ON s.id = r.test_case_set_id
        WHERE s.project_id IN ({})
        """.format(_placeholders(project_names)),
        tuple(project_names),
    ).fetchall()
    return [
        _task(
            task_id=row["task_id"],
            source_type="test_case_generation_run",
            source_id=row["id"],
            project_id=row["project_id"],
            project_name=project_names[row["project_id"]],
            module="test_case",
            module_label="测试用例",
            title=row["set_name"],
            status=row["status"],
            status_meta=TEST_CASE_GENERATION_STATUS,
            summary=row["error_message"] if row["status"] == "failed" else "",
            created_at=row["created_at"],
            updated_at=row["updated_at"] or row["created_at"],
            detail_url=f"/test-cases?set={row['set_id']}",
        )
        for row in rows
    ]
```

- [ ] **Step 4: Run backend tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_test_case_set_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/backend/app/services/task_service.py apps/backend/tests/test_test_case_set_service.py
git commit -m "feat: surface test case generation tasks"
```

## Task 4: Frontend API Types and Contract Test

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Create: `apps/frontend/tests/test-case-set-dialog-contract.test.mjs`

- [ ] **Step 1: Write frontend contract test**

Create `apps/frontend/tests/test-case-set-dialog-contract.test.mjs`:

```javascript
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/test-cases/page.tsx", import.meta.url), "utf8");
const apiSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("test case page exposes create test case set dialog labels", () => {
  assert.match(pageSource, /createLabel="新建测试用例集"/);
  assert.match(pageSource, /<DialogTitle>新建测试用例集<\/DialogTitle>/);
  assert.match(pageSource, /选择一个需求，配置探索、公司知识库和生成范围后生成测试用例。/);
  assert.match(pageSource, />用例集名称</);
  assert.match(pageSource, />需求</);
  assert.match(pageSource, />关联探索</);
  assert.match(pageSource, />使用公司知识库</);
  assert.match(pageSource, />生成范围</);
});

test("test case set form defaults company knowledge and all scope", () => {
  assert.match(pageSource, /includeCompanyKnowledge: true/);
  assert.match(pageSource, /generationScopeType: "all"/);
  assert.match(pageSource, /setValue=\{\(value\) => setForm\(\(current\) => \(\{ \.\.\.current, generationScopeType: value as TestCaseGenerationScopeType \}\)\)\}/);
});

test("specified scope shows the required natural language range input", () => {
  assert.match(pageSource, /form\.generationScopeType === "specified"/);
  assert.match(pageSource, /这个需求中登录部分的测试用例/);
  assert.match(pageSource, /请填写要生成的需求范围/);
});

test("requirement selection auto-selects related exploration but keeps it editable", () => {
  assert.match(pageSource, /function relatedExplorationForRequirement\(requirementId: string\)/);
  assert.match(pageSource, /explorationRunId: relatedExplorationForRequirement\(value\)\?\.id \?\? ""/);
  assert.match(pageSource, /<SelectOption value=\{NO_EXPLORATION_VALUE\}>不使用探索<\/SelectOption>/);
  assert.match(pageSource, /已根据所选需求自动选择关联探索，可手动调整。/);
});

test("api client defines test case set contracts", () => {
  assert.match(apiSource, /export type ApiTestCaseSet = \{/);
  assert.match(apiSource, /export type ApiTestCaseSetCreate = \{/);
  assert.match(apiSource, /generation_scope_type: "all" \| "specified"/);
  assert.match(apiSource, /include_company_knowledge: boolean/);
});
```

- [ ] **Step 2: Run frontend contract test to verify failure**

Run:

```powershell
cd apps/frontend
node --test tests/test-case-set-dialog-contract.test.mjs
```

Expected: FAIL because the page and API types do not yet contain the required contracts.

- [ ] **Step 3: Add API types**

In `apps/frontend/src/lib/api-client.ts`, after the task types, add:

```ts
export type ApiRequirementDocument = {
  id: string;
  project_id: string;
  name: string;
  document_type: string;
  current_version_id: string | null;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type ApiExplorationRun = {
  id: string;
  project_id: string;
  project_name: string;
  environment_id: string;
  environment_name: string;
  requirement_doc_id: string;
  requirement_doc_title: string;
  title: string;
  status: string;
  scope: string;
  goal: string;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type ApiTestCaseGenerationRun = {
  id: string;
  test_case_set_id: string;
  task_id: string;
  status: "queued" | "running" | "completed" | "failed";
  input_snapshot: Record<string, unknown>;
  error_message: string;
  created_at: string;
  finished_at: string | null;
};

export type ApiTestCaseSet = {
  id: string;
  project_id: string;
  project_name: string;
  name: string;
  requirement_doc_id: string;
  requirement_doc_title: string;
  exploration_run_id: string;
  exploration_run_title: string;
  include_company_knowledge: boolean;
  generation_scope_type: "all" | "specified";
  generation_scope_text: string;
  notes: string;
  status: "generating" | "ready_for_review" | "failed" | "archived";
  status_label: string;
  case_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  generation_run: ApiTestCaseGenerationRun | null;
};

export type ApiTestCaseSetCreate = {
  name: string;
  requirement_doc_id: string;
  exploration_run_id: string;
  include_company_knowledge: boolean;
  generation_scope_type: "all" | "specified";
  generation_scope_text: string;
  notes: string;
};
```

- [ ] **Step 4: Run contract test**

Run:

```powershell
cd apps/frontend
node --test tests/test-case-set-dialog-contract.test.mjs
```

Expected: still FAIL until the page is implemented.

- [ ] **Step 5: Commit**

```powershell
git add apps/frontend/src/lib/api-client.ts apps/frontend/tests/test-case-set-dialog-contract.test.mjs
git commit -m "test: add test case set frontend contracts"
```

## Task 5: Frontend Test Case Page Dialog

**Files:**
- Modify: `apps/frontend/src/app/(main)/test-cases/page.tsx`
- Test: `apps/frontend/tests/test-case-set-dialog-contract.test.mjs`

- [ ] **Step 1: Replace test case page imports**

In `apps/frontend/src/app/(main)/test-cases/page.tsx`, replace the imports with:

```tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ClipboardCheck, Loader2, Play, Search } from "lucide-react";
import { toast } from "sonner";

import { Field, FieldGroup, FieldLabel } from "@/components/ai-testing/field";
import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectOption } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableLoadingRow, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  type ApiExplorationRun,
  type ApiProject,
  type ApiRequirementDocument,
  type ApiTestCaseSet,
  type ApiTestCaseSetCreate,
  apiRequest,
  formatDateTime,
} from "@/lib/api-client";
import { useProjectContextStore } from "@/stores/project-context-store";
```

If `Field`, `Select`, or `TableLoadingRow` names differ in the current branch, use the exact names already imported by `exploration-workspace.tsx`.

- [ ] **Step 2: Add form types and constants**

Below imports, add:

```tsx
type TestCaseGenerationScopeType = "all" | "specified";

type TestCaseSetForm = {
  name: string;
  projectId: string;
  requirementDocId: string;
  explorationRunId: string;
  includeCompanyKnowledge: boolean;
  generationScopeType: TestCaseGenerationScopeType;
  generationScopeText: string;
  notes: string;
};

const NO_EXPLORATION_VALUE = "__none__";

const emptyForm: TestCaseSetForm = {
  name: "",
  projectId: "",
  requirementDocId: "",
  explorationRunId: "",
  includeCompanyKnowledge: true,
  generationScopeType: "all",
  generationScopeText: "",
  notes: "",
};
```

- [ ] **Step 3: Implement page state and data loading**

Inside `Page()`, replace placeholder local array logic with:

```tsx
export default function Page() {
  const { mode: projectScope, projectId, projectName } = useProjectContextStore();
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [rows, setRows] = useState<ApiTestCaseSet[]>([]);
  const [requirements, setRequirements] = useState<ApiRequirementDocument[]>([]);
  const [explorations, setExplorations] = useState<ApiExplorationRun[]>([]);
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<TestCaseSetForm>({ ...emptyForm, projectId: projectId ?? "" });

  const selectedProjectId = projectScope === "project" ? (projectId ?? "") : form.projectId;
  const selectedProjectName =
    projectScope === "project" ? (projectName ?? "") : projects.find((item) => item.id === form.projectId)?.name ?? "";

  const filteredRows = rows.filter((item) =>
    [item.name, item.requirement_doc_title, item.exploration_run_title, item.status_label, item.generation_scope_text].some(
      (value) => value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  const relatedExplorations = useMemo(
    () => explorations.filter((item) => item.requirement_doc_id === form.requirementDocId),
    [explorations, form.requirementDocId],
  );

  function relatedExplorationForRequirement(requirementId: string) {
    return explorations.find(
      (item) => item.requirement_doc_id === requirementId && ["completed", "partial"].includes(item.status),
    );
  }
```

Add data loaders:

```tsx
  const loadProjects = useCallback(async () => {
    const data = await apiRequest<ApiProject[]>("/projects");
    setProjects(data);
  }, []);

  const loadProjectInputs = useCallback(async (nextProjectId: string) => {
    if (!nextProjectId) {
      setRequirements([]);
      setExplorations([]);
      return;
    }
    const [nextRequirements, nextExplorations] = await Promise.all([
      apiRequest<ApiRequirementDocument[]>(`/projects/${nextProjectId}/requirements`),
      apiRequest<ApiExplorationRun[]>(`/projects/${nextProjectId}/exploration-runs`),
    ]);
    setRequirements(nextRequirements);
    setExplorations(nextExplorations);
  }, []);

  const loadSets = useCallback(async (nextProjectId: string) => {
    if (!nextProjectId) {
      setRows([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await apiRequest<ApiTestCaseSet[]>(`/projects/${nextProjectId}/test-case-sets`);
      setRows(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    const nextProjectId = projectScope === "project" ? (projectId ?? "") : projects[0]?.id ?? "";
    setForm((current) => ({ ...current, projectId: nextProjectId }));
  }, [projectId, projectScope, projects]);

  useEffect(() => {
    void loadProjectInputs(selectedProjectId);
    void loadSets(selectedProjectId);
  }, [loadProjectInputs, loadSets, selectedProjectId]);
```

- [ ] **Step 4: Add open, requirement change, and save handlers**

Continue inside `Page()`:

```tsx
  function openCreateDialog() {
    const nextProjectId = projectScope === "project" ? (projectId ?? "") : form.projectId || projects[0]?.id || "";
    setForm({ ...emptyForm, projectId: nextProjectId });
    setDialogOpen(true);
  }

  function handleRequirementChange(value: string) {
    const requirement = requirements.find((item) => item.id === value);
    const related = relatedExplorationForRequirement(value);
    setForm((current) => ({
      ...current,
      requirementDocId: value,
      name: current.name || (requirement ? `${requirement.name}测试用例集` : current.name),
      explorationRunId: related?.id ?? "",
    }));
  }

  async function saveTestCaseSet() {
    if (!selectedProjectId) {
      toast.error("请选择项目");
      return;
    }
    if (!form.name.trim()) {
      toast.error("请填写用例集名称");
      return;
    }
    if (!form.requirementDocId) {
      toast.error("请选择需求");
      return;
    }
    if (form.generationScopeType === "specified" && !form.generationScopeText.trim()) {
      toast.error("请填写要生成的需求范围");
      return;
    }
    setSaving(true);
    try {
      const payload: ApiTestCaseSetCreate = {
        name: form.name.trim(),
        requirement_doc_id: form.requirementDocId,
        exploration_run_id: form.explorationRunId,
        include_company_knowledge: form.includeCompanyKnowledge,
        generation_scope_type: form.generationScopeType,
        generation_scope_text: form.generationScopeType === "specified" ? form.generationScopeText.trim() : "",
        notes: form.notes.trim(),
      };
      const created = await apiRequest<ApiTestCaseSet>(`/projects/${selectedProjectId}/test-case-sets`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setRows((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setDialogOpen(false);
      toast.success("测试用例生成任务已创建");
    } finally {
      setSaving(false);
    }
  }
```

- [ ] **Step 5: Replace JSX with list and dialog**

Use this return shape:

```tsx
  return (
    <PageShell
      breadcrumbs={["项目工作区", "测试用例"]}
      description="查看测试用例集、生成状态和用例数量。"
      projectScope={projectScope}
      title="测试用例"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="当前项目测试用例集数量" icon={ClipboardCheck} label="测试用例集" value={String(rows.length)} />
        <MetricCard
          helper="生成完成后展示待评审用例"
          icon={ClipboardCheck}
          label="测试用例"
          value={String(rows.reduce((total, item) => total + item.case_count, 0))}
        />
        <MetricCard
          helper="生成中的用例集"
          icon={Loader2}
          label="生成中"
          value={String(rows.filter((item) => item.status === "generating").length)}
        />
      </div>
      <ShellSection>
        <ListToolbar
          createLabel="新建测试用例集"
          onCreate={openCreateDialog}
          onSearch={setSearchText}
          placeholder="搜索用例集、需求或探索"
          title="测试用例集列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>用例集名称</TableHead>
                <TableHead>需求</TableHead>
                <TableHead>关联探索</TableHead>
                <TableHead>生成范围</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>用例数量</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? <TableLoadingRow colSpan={8} label="测试用例集加载中" /> : null}
              {!loading
                ? filteredRows.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">{item.name}</TableCell>
                      <TableCell>{item.requirement_doc_title}</TableCell>
                      <TableCell>{item.exploration_run_title || "不使用探索"}</TableCell>
                      <TableCell>{item.generation_scope_type === "all" ? "全部需求内容" : item.generation_scope_text}</TableCell>
                      <TableCell>
                        <Badge variant={item.status === "generating" ? "outline" : "secondary"}>{item.status_label}</Badge>
                      </TableCell>
                      <TableCell>{item.case_count}</TableCell>
                      <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                      <TableCell>
                        <RowActions actions={[{ label: "查看", href: `/test-cases?set=${item.id}`, icon: Search }]} label="打开操作菜单" />
                      </TableCell>
                    </TableRow>
                  ))
                : null}
              {!loading && filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={8}>
                    暂无测试用例。可新建测试用例集，选择需求后生成测试用例。
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </ShellSection>
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-3xl">
          <DialogHeader className="shrink-0 gap-3 px-6 pt-6">
            <DialogTitle>新建测试用例集</DialogTitle>
            <DialogDescription>选择一个需求，配置探索、公司知识库和生成范围后生成测试用例。</DialogDescription>
          </DialogHeader>
          <FieldGroup className="grid min-h-0 gap-x-6 gap-y-5 overflow-y-auto px-6 py-5 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="test-case-set-name">用例集名称</FieldLabel>
              <Input id="test-case-set-name" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
            </Field>
            <Field>
              <FieldLabel htmlFor="test-case-set-project">项目</FieldLabel>
              <Select
                disabled={projectScope === "project"}
                id="test-case-set-project"
                placeholder={projectScope === "project" ? projectName || "当前项目" : "选择项目"}
                value={form.projectId}
                setValue={(value) =>
                  setForm((current) => ({ ...current, projectId: value, requirementDocId: "", explorationRunId: "" }))
                }
              >
                {projectScope === "project" && projectId ? (
                  <SelectOption value={projectId}>{projectName}</SelectOption>
                ) : (
                  projects.map((project) => (
                    <SelectOption key={project.id} value={project.id}>
                      {project.name}
                    </SelectOption>
                  ))
                )}
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="test-case-set-requirement">需求</FieldLabel>
              <Select id="test-case-set-requirement" placeholder="选择需求" value={form.requirementDocId} setValue={handleRequirementChange}>
                {requirements.map((requirement) => (
                  <SelectOption key={requirement.id} value={requirement.id}>
                    {requirement.name}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="test-case-set-exploration">关联探索</FieldLabel>
              <Select
                id="test-case-set-exploration"
                placeholder="选择探索或不使用"
                value={form.explorationRunId || NO_EXPLORATION_VALUE}
                setValue={(value) => setForm((current) => ({ ...current, explorationRunId: value === NO_EXPLORATION_VALUE ? "" : value }))}
              >
                <SelectOption value={NO_EXPLORATION_VALUE}>不使用探索</SelectOption>
                {(relatedExplorations.length > 0 ? relatedExplorations : explorations).map((exploration) => (
                  <SelectOption key={exploration.id} value={exploration.id}>
                    {exploration.title}
                  </SelectOption>
                ))}
              </Select>
              {relatedExplorations.length > 0 ? (
                <p className="text-muted-foreground text-xs">已根据所选需求自动选择关联探索，可手动调整。</p>
              ) : (
                <p className="text-muted-foreground text-xs">未找到关联探索，仍可基于需求和公司知识库生成。</p>
              )}
            </Field>
            <Field>
              <FieldLabel htmlFor="test-case-set-company-knowledge">使用公司知识库</FieldLabel>
              <label className="flex items-start gap-3 rounded-md border p-3 text-sm">
                <Checkbox
                  id="test-case-set-company-knowledge"
                  checked={form.includeCompanyKnowledge}
                  onCheckedChange={(checked) => setForm((current) => ({ ...current, includeCompanyKnowledge: Boolean(checked) }))}
                />
                <span className="grid gap-1">
                  <span>默认开启</span>
                  <span className="text-muted-foreground text-xs">用于查询通用测试规范、模板和术语。不确定的业务规则仍会标记为待确认。</span>
                </span>
              </label>
            </Field>
            <Field>
              <FieldLabel htmlFor="test-case-set-scope-type">生成范围</FieldLabel>
              <Select
                id="test-case-set-scope-type"
                value={form.generationScopeType}
                setValue={(value) => setForm((current) => ({ ...current, generationScopeType: value as TestCaseGenerationScopeType }))}
              >
                <SelectOption value="all">全部需求内容</SelectOption>
                <SelectOption value="specified">指定范围</SelectOption>
              </Select>
            </Field>
            {form.generationScopeType === "specified" ? (
              <Field className="sm:col-span-2">
                <FieldLabel htmlFor="test-case-set-scope-text">指定范围说明</FieldLabel>
                <Textarea
                  className="min-h-20"
                  id="test-case-set-scope-text"
                  placeholder="例如：这个需求中登录部分的测试用例"
                  value={form.generationScopeText}
                  onChange={(event) => setForm((current) => ({ ...current, generationScopeText: event.target.value }))}
                />
              </Field>
            ) : null}
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="test-case-set-notes">备注</FieldLabel>
              <Textarea
                className="min-h-16"
                id="test-case-set-notes"
                placeholder="补充说明，不作为硬性生成范围"
                value={form.notes}
                onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
              />
            </Field>
          </FieldGroup>
          <DialogFooter className="m-0 shrink-0 px-6 py-4">
            <Button onClick={() => setDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={saving} onClick={saveTestCaseSet} type="button">
              {saving ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              生成测试用例
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
```

- [ ] **Step 6: Run frontend contract test**

Run:

```powershell
cd apps/frontend
node --test tests/test-case-set-dialog-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 7: Run frontend lint for touched files**

Run:

```powershell
cd apps/frontend
npx biome check src/app/(main)/test-cases/page.tsx src/lib/api-client.ts tests/test-case-set-dialog-contract.test.mjs
```

Expected: PASS. If PowerShell treats parentheses specially, quote the page path:

```powershell
npx biome check 'src/app/(main)/test-cases/page.tsx' src/lib/api-client.ts tests/test-case-set-dialog-contract.test.mjs
```

- [ ] **Step 8: Commit**

```powershell
git add apps/frontend/src/app/(main)/test-cases/page.tsx apps/frontend/src/lib/api-client.ts apps/frontend/tests/test-case-set-dialog-contract.test.mjs
git commit -m "feat: add test case set creation dialog"
```

## Task 6: Final Verification

**Files:**
- No new files.
- Verify all files changed by Tasks 1-5.

- [ ] **Step 1: Run backend test file**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_test_case_set_service.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend contract test**

Run:

```powershell
cd apps/frontend
node --test tests/test-case-set-dialog-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 3: Run focused frontend lint**

Run:

```powershell
cd apps/frontend
npx biome check 'src/app/(main)/test-cases/page.tsx' src/lib/api-client.ts tests/test-case-set-dialog-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 4: Inspect final diff**

Run:

```powershell
git status --short
git log --oneline -6
```

Expected: current task files are clean after commits. Existing unrelated dirty files may still be present from earlier work; do not revert them.

