import asyncio
import json
import sqlite3
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.agents.test_case_generation.schemas import (
    TestCase as AgentTestCase,
    TestCaseGenerationResult as AgentTestCaseGenerationResult,
    TestCaseModule as AgentTestCaseModule,
    TestCaseStep as AgentTestCaseStep,
)
from app.core import db as core_db
from app.core import storage
from app.core import settings
from app.seed.init_db import init_db
from app.seed.seeds import _ensure_test_case_display_order
from app.schemas.test_case import ManualTestCaseCreateIn, TestCaseReviewIn, TestCaseSetCreateIn
from app.services import task_service, test_case_service
from app.services.knowledge import global_service as global_knowledge_service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}
GUEST = {"id": "u-guest", "role": "guest", "nickname": "访客", "username": "guest", "project_scope": "全部项目"}


def _agent_steps(*actions: str) -> list[AgentTestCaseStep]:
    expected_by_action = {
        "打开登录页": "展示登录表单。",
        "输入正确账号密码": "账号密码填写完成。",
        "提交登录": "进入系统首页。",
        "输入账号密码": "账号密码填写完成。",
    }
    return [
        AgentTestCaseStep(action=action, expected_result=expected_by_action.get(action, f"{action}完成。"))
        for action in actions
    ]


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    init_db()
    knowledge_base = global_knowledge_service.create_base(
        name="测试知识库",
        description="测试用不采纳知识库",
        actor=ACTOR,
    )
    monkeypatch.setattr(settings, "REJECTED_CASE_KNOWLEDGE_BASE_ID", knowledge_base["id"])


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
            VALUES (?, ?, 1, ?, ?, 'requirement_analysis_finalize', '确认最终需求', ?)
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


def test_manual_test_case_create_list_and_delete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()

    created = test_case_service.create_manual_test_case(
        "project-1",
        ManualTestCaseCreateIn(
            title="登录成功",
            preconditions="用户账号已注册",
            steps=[
                {"action": "输入正确账号密码", "expected_result": "账号密码填写完成"},
                {"action": "点击登录", "expected_result": "进入系统首页"},
            ],
            notes="手工回归用例",
        ),
        ACTOR,
    )

    assert created["project_id"] == "project-1"
    assert created["project_name"] == "测试项目"
    assert created["title"] == "登录成功"
    assert created["steps"][1]["expected_result"] == "进入系统首页"
    assert created["notes"] == "手工回归用例"

    listed = test_case_service.list_manual_test_cases("project-1", ACTOR)
    assert [item["id"] for item in listed] == [created["id"]]

    detail = test_case_service.get_manual_test_case("project-1", created["id"], ACTOR)
    assert detail == created

    with pytest.raises(HTTPException) as exc_info:
        test_case_service.get_manual_test_case("missing-project", created["id"], ACTOR)
    assert exc_info.value.status_code == 404

    test_case_service.delete_manual_test_case("project-1", created["id"], ACTOR)
    assert test_case_service.list_manual_test_cases("project-1", ACTOR) == []


def test_manual_test_case_requires_action_and_expected_result() -> None:
    with pytest.raises(ValidationError):
        ManualTestCaseCreateIn(
            title="登录失败",
            steps=[{"action": "点击登录", "expected_result": ""}],
        )


def test_existing_cases_are_backfilled_to_persisted_module_priority_order() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        """
        CREATE TABLE test_cases (
          id TEXT PRIMARY KEY,
          test_case_set_id TEXT NOT NULL,
          module TEXT NOT NULL,
          priority TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
        """
    )
    db.executemany(
        "INSERT INTO test_cases (id, test_case_set_id, module, priority, created_at) VALUES (?, 'set-1', ?, ?, ?)",
        [
            ("tc-001", "登录", "P2", "2026-01-01 00:00:01"),
            ("tc-002", "登录", "P0", "2026-01-01 00:00:02"),
            ("tc-003", "账户", "P1", "2026-01-01 00:00:03"),
            ("tc-004", "登录", "P0", "2026-01-01 00:00:04"),
            ("tc-005", "账户", "P0", "2026-01-01 00:00:05"),
        ],
    )

    _ensure_test_case_display_order(db)

    rows = db.execute("SELECT id, display_order FROM test_cases ORDER BY display_order").fetchall()
    assert [(row["id"], row["display_order"]) for row in rows] == [
        ("tc-002", 0),
        ("tc-004", 1),
        ("tc-001", 2),
        ("tc-005", 3),
        ("tc-003", 4),
    ]
    db.close()


def test_create_test_case_set_defaults_to_requirement_only_generation(
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
    assert "exploration_run_id" not in created
    assert "exploration_run_title" not in created
    assert "include_company_knowledge" not in created
    assert created["generation_scope_type"] == "all"
    assert created["generation_scope_text"] == ""
    assert created["status"] == "generating"
    assert created["case_count"] == 0
    assert created["generation_run"]["status"] == "queued"
    assert "use_exploration_artifacts" not in created["generation_run"]["input_snapshot"]
    assert "include_company_knowledge" not in created["generation_run"]["input_snapshot"]


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


def test_create_test_case_set_rejects_removed_generation_source_parameters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()

    with pytest.raises(ValidationError):
        TestCaseSetCreateIn(
            name="登录需求测试用例集",
            requirement_doc_id="doc-1",
            use_exploration_artifacts=True,
            include_company_knowledge=True,
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


def test_create_test_case_set_rejects_requirement_without_final_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description, created_by) VALUES (?, ?, 'active', '', ?)",
            ("project-1", "测试项目", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES (?, ?, ?, 'PRD', 'version-draft', 'versioned', ?)
            """,
            ("doc-draft", "project-1", "未最终需求", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO source_document_versions
              (id, document_id, version_no, markdown_content, file_path, source_action, change_summary, created_by)
            VALUES (?, ?, 1, ?, '', 'upload', '上传原始需求', ?)
            """,
            ("version-draft", "doc-draft", "# 原始需求\n\n尚未转为最终需求。", ACTOR["id"]),
        )

    with pytest.raises(HTTPException) as exc_info:
        test_case_service.create_test_case_set(
            "project-1",
            TestCaseSetCreateIn(name="非法用例集", requirement_doc_id="doc-draft"),
            ACTOR,
        )

    assert exc_info.value.detail["code"] == "NO_FINAL_REQUIREMENT"


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


def test_delete_test_case_set_removes_generation_runs(
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

    test_case_service.delete_test_case_set("project-1", created["id"], ACTOR)

    assert test_case_service.list_project_test_case_sets("project-1", ACTOR) == []
    tasks = task_service.list_running_tasks(ACTOR, project_id="project-1")
    assert all(task["source_id"] != created["generation_run"]["id"] for task in tasks)


def test_guest_cannot_delete_test_case_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()
    created = test_case_service.create_test_case_set(
        "project-1",
        TestCaseSetCreateIn(name="登录需求测试用例集", requirement_doc_id="doc-1"),
        ACTOR,
    )

    with pytest.raises(HTTPException) as exc_info:
        test_case_service.delete_test_case_set("project-1", created["id"], GUEST)

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
    assert items[0]["generation_scope_type"] == "specified"
    assert items[0]["generation_scope_text"] == "这个需求中登录部分的测试用例"
    assert items[0]["generation_run"]["task_id"] == created["generation_run"]["task_id"]


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

    tasks = task_service.list_running_tasks(ACTOR, project_id="project-1")

    assert any(
        task["source_type"] == "test_case_generation_run"
        and task["source_id"] == created["generation_run"]["id"]
        and task["title"] == "登录需求测试用例集"
        and task["status_label"] == "排队中"
        for task in tasks
    )


def test_execute_test_case_generation_run_completes_and_persists_cases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO test_point_generation_runs
              (id, project_id, document_id, requirement_version_id, task_id, status, created_by)
            VALUES ('tpgr-1', 'project-1', 'doc-1', 'version-1', 'test_point_generation:tpgr-1', 'completed', ?)
            """,
            (ACTOR["id"],),
        )
        db.executemany(
            """
            INSERT INTO test_points
              (id, project_id, document_id, requirement_version_id, generation_run_id,
               point_key, title, module, category, priority, description)
            VALUES (?, 'project-1', 'doc-1', 'version-1', 'tpgr-1', ?, ?, '登录', '功能', 'P0', ?)
            """,
            [
                ("tp-1", "TP-LOGIN-001", "正确账号登录", "验证正确账号密码可以登录。"),
                ("tp-2", "TP-LOGIN-002", "错误密码登录", "验证错误密码不能登录。"),
            ],
        )
    created = test_case_service.create_test_case_set(
        "project-1",
        TestCaseSetCreateIn(name="登录需求测试用例集", requirement_doc_id="doc-1"),
        ACTOR,
    )

    async def fake_generate_test_cases(input_data):
        assert input_data.requirement_name == "登录需求"
        assert "用户可以登录系统" in input_data.requirement_content
        assert "原始需求" not in input_data.requirement_content
        assert not hasattr(input_data, "include_company_knowledge")
        assert [point["point_key"] for point in input_data.test_points] == ["TP-LOGIN-001", "TP-LOGIN-002"]
        assert all("status" not in point for point in input_data.test_points)
        return AgentTestCaseGenerationResult(
            summary="覆盖登录成功和失败场景。",
            total_count=1,
            modules=[
                AgentTestCaseModule(
                    module_name="登录",
                    test_cases=[
                        AgentTestCase(
                            id="tc-001",
                            module="登录",
                            title="账号密码登录成功",
                            priority="P0",
                            type="功能测试",
                            precondition="用户已注册。",
                            steps=_agent_steps("打开登录页", "输入正确账号密码", "提交登录"),
                            expected_result="进入系统首页。",
                        )
                    ],
                )
            ],
        )

    monkeypatch.setattr(test_case_service, "generate_test_cases", fake_generate_test_cases)

    asyncio.run(test_case_service.execute_test_case_generation_run(created["generation_run"]["id"]))

    updated = test_case_service.get_test_case_set("project-1", created["id"], ACTOR)
    assert updated["status"] == "ready_for_review"
    assert updated["case_count"] == 1
    assert updated["generation_run"]["status"] == "completed"
    with core_db.connect() as db:
        rows = db.execute("SELECT * FROM test_cases WHERE test_case_set_id = ?", (created["id"],)).fetchall()
    assert len(rows) == 1
    assert rows[0]["title"] == "账号密码登录成功"
    assert rows[0]["status"] == "ready_for_review"
    assert json.loads(rows[0]["steps_json"]) == [
        {"action": "打开登录页", "expected_result": "展示登录表单。"},
        {"action": "输入正确账号密码", "expected_result": "账号密码填写完成。"},
        {"action": "提交登录", "expected_result": "进入系统首页。"},
    ]
    assert rows[0]["source_exploration_refs"] == "[]"


def test_generation_persists_cases_in_module_priority_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()
    created = test_case_service.create_test_case_set(
        "project-1",
        TestCaseSetCreateIn(name="排序测试用例集", requirement_doc_id="doc-1"),
        ACTOR,
    )

    def agent_case(case_id: str, module: str, title: str, priority: str) -> AgentTestCase:
        return AgentTestCase(
            id=case_id,
            module=module,
            title=title,
            priority=priority,
            type="功能测试",
            steps=_agent_steps("打开登录页"),
            expected_result="展示登录表单。",
        )

    async def fake_generate_test_cases(_input_data):
        cases = [
            agent_case("tc-001", "登录", "登录-P2", "P2"),
            agent_case("tc-002", "登录", "登录-P0-先", "P0"),
            agent_case("tc-003", "登录", "登录-P1", "P1"),
            agent_case("tc-004", "登录", "登录-P0-后", "P0"),
            agent_case("tc-005", "账户", "账户-P1", "P1"),
            agent_case("tc-006", "账户", "账户-P0", "P0"),
        ]
        return AgentTestCaseGenerationResult(
            summary="验证持久化排序。",
            total_count=len(cases),
            modules=[AgentTestCaseModule(module_name="业务模块", test_cases=cases)],
        )

    monkeypatch.setattr(test_case_service, "generate_test_cases", fake_generate_test_cases)
    asyncio.run(test_case_service.execute_test_case_generation_run(created["generation_run"]["id"]))

    detail = test_case_service.get_test_case_set("project-1", created["id"], ACTOR)
    assert [(case["module"], case["priority"], case["title"]) for case in detail["cases"]] == [
        ("登录", "P0", "登录-P0-先"),
        ("登录", "P0", "登录-P0-后"),
        ("登录", "P1", "登录-P1"),
        ("登录", "P2", "登录-P2"),
        ("账户", "P0", "账户-P0"),
        ("账户", "P1", "账户-P1"),
    ]
    with core_db.connect() as db:
        stored = db.execute(
            "SELECT title, display_order FROM test_cases WHERE test_case_set_id = ? ORDER BY display_order",
            (created["id"],),
        ).fetchall()
    assert [(row["title"], row["display_order"]) for row in stored] == [
        ("登录-P0-先", 0),
        ("登录-P0-后", 1),
        ("登录-P1", 2),
        ("登录-P2", 3),
        ("账户-P0", 4),
        ("账户-P1", 5),
    ]


def test_get_test_case_set_returns_persisted_case_details(
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
    test_case_service._complete_generation_run(
        {
            "id": created["generation_run"]["id"],
            "test_case_set_id": created["id"],
            "project_id": "project-1",
            "requirement_doc_id": "doc-1",
        },
        AgentTestCaseGenerationResult(
            summary="覆盖登录成功场景。",
            total_count=1,
            modules=[
                AgentTestCaseModule(
                    module_name="登录",
                    test_cases=[
                        AgentTestCase(
                            id="tc-001",
                            module="登录",
                            title="账号密码登录成功",
                            priority="P0",
                            type="功能测试",
                            precondition="用户已注册。",
                            steps=_agent_steps("打开登录页", "输入正确账号密码", "提交登录"),
                            expected_result="进入系统首页。",
                        )
                    ],
                )
            ],
        ),
    )

    detail = test_case_service.get_test_case_set("project-1", created["id"], ACTOR)

    assert detail["cases"] == [
        {
            "id": f"{created['id']}-tc-001",
            "test_case_set_id": created["id"],
            "project_id": "project-1",
            "title": "账号密码登录成功",
            "module": "登录",
            "priority": "P0",
            "preconditions": "用户已注册。",
            "steps": [
                {"action": "打开登录页", "expected_result": "展示登录表单。"},
                {"action": "输入正确账号密码", "expected_result": "账号密码填写完成。"},
                {"action": "提交登录", "expected_result": "进入系统首页。"},
            ],
            "expected_result": "进入系统首页。",
            "status": "ready_for_review",
            "review_feedback": "",
            "reviewed_by": "",
            "reviewed_at": None,
            "created_at": detail["cases"][0]["created_at"],
            "updated_at": detail["cases"][0]["updated_at"],
        }
    ]


def test_export_test_case_set_xmind_uses_legacy_structure_without_description(
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
    test_case_service._complete_generation_run(
        {
            "id": created["generation_run"]["id"],
            "test_case_set_id": created["id"],
            "project_id": "project-1",
            "requirement_doc_id": "doc-1",
        },
        AgentTestCaseGenerationResult(
            summary="覆盖登录成功场景。",
            total_count=1,
            modules=[
                AgentTestCaseModule(
                    module_name="登录",
                    test_cases=[
                        AgentTestCase(
                            id="tc-001",
                            module="登录",
                            title="账号密码登录成功",
                            priority="P0",
                            type="功能测试",
                            precondition="用户已注册。",
                            steps=_agent_steps("打开登录页", "输入正确账号密码"),
                            expected_result="进入系统首页。",
                        )
                    ],
                )
            ],
        ),
    )

    content, filename = test_case_service.export_test_case_set_xmind("project-1", created["id"], ACTOR)

    assert filename == "登录需求测试用例集.xmind"
    xmind_path = tmp_path / filename
    xmind_path.write_bytes(content)
    with zipfile.ZipFile(xmind_path) as archive:
        assert sorted(archive.namelist()) == ["META-INF/manifest.xml", "content.xml"]
        content_xml = archive.read("content.xml")
        archive.read("META-INF/manifest.xml")

    root = ET.fromstring(content_xml)
    titles = [element.text for element in root.iter() if element.tag.endswith("title")]
    assert "登录需求测试用例集测试用例" in titles
    assert "登录需求测试用例集" in titles
    assert "登录" in titles
    assert "tc-p0: 账号密码登录成功" in titles
    assert "pc: 用户已注册。" in titles
    assert "步骤1: 打开登录页" in titles
    assert "结果1: 展示登录表单。" in titles
    assert "步骤2: 输入正确账号密码" in titles
    assert "结果2: 账号密码填写完成。" in titles
    assert all(not (title or "").startswith("tx:") for title in titles)


def test_export_empty_test_case_set_xmind_keeps_root_with_empty_hint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()
    created = test_case_service.create_test_case_set(
        "project-1",
        TestCaseSetCreateIn(name='登录/需求:"测试"', requirement_doc_id="doc-1"),
        ACTOR,
    )

    content, filename = test_case_service.export_test_case_set_xmind("project-1", created["id"], ACTOR)

    assert filename == "登录_需求_测试_.xmind"
    xmind_path = tmp_path / filename
    xmind_path.write_bytes(content)
    with zipfile.ZipFile(xmind_path) as archive:
        content_xml = archive.read("content.xml")

    root = ET.fromstring(content_xml)
    titles = [element.text for element in root.iter() if element.tag.endswith("title")]
    assert "登录/需求:\"测试\"" in titles
    assert "暂无测试用例" in titles


def test_review_test_case_updates_status_feedback_and_stats(
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
    test_case_service._complete_generation_run(
        {
            "id": created["generation_run"]["id"],
            "test_case_set_id": created["id"],
            "project_id": "project-1",
            "requirement_doc_id": "doc-1",
        },
        AgentTestCaseGenerationResult(
            summary="覆盖登录成功场景。",
            total_count=1,
            modules=[
                AgentTestCaseModule(
                    module_name="登录",
                    test_cases=[
                        AgentTestCase(
                            id="tc-001",
                            module="登录",
                            title="账号密码登录成功",
                            priority="P0",
                            type="功能测试",
                            precondition="用户已注册。",
                            steps=_agent_steps("打开登录页", "输入正确账号密码", "提交登录"),
                            expected_result="进入系统首页。",
                        )
                    ],
                )
            ],
        ),
    )
    case_id = f"{created['id']}-tc-001"

    rejected = test_case_service.review_test_case(
        "project-1",
        created["id"],
        case_id,
        TestCaseReviewIn(status="rejected", review_feedback="  预期结果不可验证  "),
        ACTOR,
    )

    assert rejected["case"]["status"] == "rejected"
    assert rejected["case"]["review_feedback"] == "预期结果不可验证"
    assert rejected["case"]["reviewed_by"] == ACTOR["id"]
    assert rejected["case"]["reviewed_at"]
    assert rejected["review_stats"] == {
        "case_count": 1,
        "approved_count": 0,
        "rejected_count": 1,
        "pending_count": 0,
        "reviewed_count": 1,
        "adoption_rate": 0,
        "review_progress": 1,
    }
    reviewed_set = test_case_service.get_test_case_set("project-1", created["id"], ACTOR)
    assert reviewed_set["status"] == "review_completed"
    assert reviewed_set["status_label"] == "评审完成"

    approved = test_case_service.review_test_case(
        "project-1",
        created["id"],
        case_id,
        TestCaseReviewIn(status="approved", review_feedback="这段会被清空"),
        ACTOR,
    )

    assert approved["case"]["status"] == "approved"
    assert approved["case"]["review_feedback"] == ""
    assert approved["review_stats"]["approved_count"] == 1
    assert approved["review_stats"]["adoption_rate"] == 1

    reset = test_case_service.review_test_case(
        "project-1",
        created["id"],
        case_id,
        TestCaseReviewIn(status="ready_for_review"),
        ACTOR,
    )

    assert reset["case"]["status"] == "ready_for_review"
    assert reset["case"]["review_feedback"] == ""
    assert reset["case"]["reviewed_by"] == ""
    assert reset["case"]["reviewed_at"] is None
    assert reset["review_stats"]["pending_count"] == 1
    pending_set = test_case_service.get_test_case_set("project-1", created["id"], ACTOR)
    assert pending_set["status"] == "ready_for_review"
    assert pending_set["status_label"] == "待评审"


def test_review_test_case_rejects_empty_rejection_feedback(
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
    test_case_service._complete_generation_run(
        {
            "id": created["generation_run"]["id"],
            "test_case_set_id": created["id"],
            "project_id": "project-1",
            "requirement_doc_id": "doc-1",
        },
        AgentTestCaseGenerationResult(
            summary="覆盖登录成功场景。",
            total_count=1,
            modules=[
                AgentTestCaseModule(
                    module_name="登录",
                    test_cases=[
                        AgentTestCase(
                            id="tc-001",
                            module="登录",
                            title="账号密码登录成功",
                            priority="P0",
                            type="功能测试",
                            precondition="用户已注册。",
                            steps=_agent_steps("打开登录页"),
                            expected_result="进入系统首页。",
                        )
                    ],
                )
            ],
        ),
    )

    with pytest.raises(ValidationError, match="不采纳原因不能为空"):
        TestCaseReviewIn(status="rejected")


def test_review_test_case_can_update_case_content(
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
    test_case_service._complete_generation_run(
        {
            "id": created["generation_run"]["id"],
            "test_case_set_id": created["id"],
            "project_id": "project-1",
            "requirement_doc_id": "doc-1",
        },
        AgentTestCaseGenerationResult(
            summary="覆盖登录成功场景。",
            total_count=1,
            modules=[
                AgentTestCaseModule(
                    module_name="登录",
                    test_cases=[
                        AgentTestCase(
                            id="tc-001",
                            module="登录",
                            title="账号密码登录成功",
                            priority="P0",
                            type="功能测试",
                            precondition="用户已注册。",
                            steps=_agent_steps("打开登录页"),
                            expected_result="进入系统首页。",
                        )
                    ],
                )
            ],
        ),
    )

    result = test_case_service.review_test_case(
        "project-1",
        created["id"],
        f"{created['id']}-tc-001",
        TestCaseReviewIn(
            status="approved",
            preconditions="  用户已完成短信验证。  ",
            steps=[
                {"action": " 打开登录页 ", "expected_result": " 展示登录表单。 "},
                {"action": "输入账号密码并提交", "expected_result": " 进入工作台首页。 "},
            ],
            expected_result="  进入工作台首页。  ",
        ),
        ACTOR,
    )

    assert result["case"]["status"] == "approved"
    assert result["case"]["preconditions"] == "用户已完成短信验证。"
    assert result["case"]["steps"] == [
        {"action": "打开登录页", "expected_result": "展示登录表单。"},
        {"action": "输入账号密码并提交", "expected_result": "进入工作台首页。"},
    ]
    assert result["case"]["expected_result"] == "进入工作台首页。"


def test_guest_cannot_review_test_case(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()
    created = test_case_service.create_test_case_set(
        "project-1",
        TestCaseSetCreateIn(name="登录需求测试用例集", requirement_doc_id="doc-1"),
        ACTOR,
    )

    with pytest.raises(HTTPException) as exc_info:
        test_case_service.review_test_case(
            "project-1",
            created["id"],
            f"{created['id']}-tc-001",
            TestCaseReviewIn(status="approved"),
            GUEST,
        )

    assert exc_info.value.status_code == 403


def test_execute_test_case_generation_run_marks_failed_on_agent_error(
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

    async def fake_generate_test_cases(_input_data):
        raise RuntimeError("模型调用失败")

    monkeypatch.setattr(test_case_service, "generate_test_cases", fake_generate_test_cases)

    asyncio.run(test_case_service.execute_test_case_generation_run(created["generation_run"]["id"]))

    updated = test_case_service.get_test_case_set("project-1", created["id"], ACTOR)
    assert updated["status"] == "failed"
    assert updated["case_count"] == 0
    assert updated["generation_run"]["status"] == "failed"
    assert "模型调用失败" in updated["generation_run"]["error_message"]


def test_regenerate_test_case_set_creates_new_run_for_existing_set(
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
            generation_scope_type="specified",
            generation_scope_text="登录成功路径",
            notes="优先覆盖主流程",
        ),
        ACTOR,
    )
    test_case_service._complete_generation_run(
        {
            "id": created["generation_run"]["id"],
            "test_case_set_id": created["id"],
            "project_id": "project-1",
            "requirement_doc_id": "doc-1",
        },
        AgentTestCaseGenerationResult(
            summary="旧用例",
            total_count=1,
            modules=[
                AgentTestCaseModule(
                    module_name="登录",
                    test_cases=[
                        AgentTestCase(
                            id="tc-001",
                            module="登录",
                            title="旧登录用例",
                            priority="P1",
                            type="功能测试",
                            precondition="已有账号。",
                            steps=_agent_steps("打开登录页"),
                            expected_result="展示登录页。",
                        )
                    ],
                )
            ],
        ),
    )

    regenerated = test_case_service.regenerate_test_case_set("project-1", created["id"], ACTOR)

    assert regenerated["id"] == created["id"]
    assert regenerated["status"] == "generating"
    assert regenerated["generation_run"]["id"] != created["generation_run"]["id"]
    assert regenerated["generation_run"]["status"] == "queued"
    assert regenerated["generation_run"]["input_snapshot"]["generation_scope_type"] == "specified"
    assert regenerated["generation_run"]["input_snapshot"]["generation_scope_text"] == "登录成功路径"
    assert regenerated["generation_run"]["input_snapshot"]["notes"] == "优先覆盖主流程"


def test_regenerate_test_case_set_uses_knowledge_instead_of_database_feedback_snapshot(
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
    test_case_service._complete_generation_run(
        {
            "id": created["generation_run"]["id"],
            "test_case_set_id": created["id"],
            "project_id": "project-1",
            "requirement_doc_id": "doc-1",
        },
        AgentTestCaseGenerationResult(
            summary="旧用例",
            total_count=1,
            modules=[
                AgentTestCaseModule(
                    module_name="登录",
                    test_cases=[
                        AgentTestCase(
                            id="tc-001",
                            module="登录",
                            title="旧登录用例",
                            priority="P1",
                            type="功能测试",
                            precondition="已有账号。",
                            steps=_agent_steps("打开登录页", "输入账号密码"),
                            expected_result="展示登录页。",
                        )
                    ],
                )
            ],
        ),
    )
    case_id = f"{created['id']}-tc-001"
    test_case_service.review_test_case(
        "project-1",
        created["id"],
        case_id,
        TestCaseReviewIn(status="rejected", review_feedback="缺少异常输入覆盖"),
        ACTOR,
    )

    regenerated = test_case_service.regenerate_test_case_set("project-1", created["id"], ACTOR)
    assert "rejected_case_feedback" not in regenerated["generation_run"]["input_snapshot"]
    records = test_case_service.rejected_case_knowledge.list_records_for_set(
        "project-1", "doc-1", created["id"]
    )
    assert records[case_id].reason == "缺少异常输入覆盖"


def test_recover_interrupted_test_case_generation_runs_marks_active_runs_failed(
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

    test_case_service.recover_interrupted_test_case_generation_runs()

    updated = test_case_service.get_test_case_set("project-1", created["id"], ACTOR)
    assert updated["status"] == "failed"
    assert updated["generation_run"]["status"] == "failed"
    assert "服务已重启" in updated["generation_run"]["error_message"]
