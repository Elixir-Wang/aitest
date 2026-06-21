import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.agents.test_case_generation.schemas import (
    TestCase as AgentTestCase,
    TestCaseGenerationResult as AgentTestCaseGenerationResult,
    TestCaseModule as AgentTestCaseModule,
)
from app.core import db as core_db
from app.core import storage
from app.seed.init_db import init_db
from app.schemas.test_case import TestCaseSetCreateIn
from app.services import task_service, test_case_service


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
    created = test_case_service.create_test_case_set(
        "project-1",
        TestCaseSetCreateIn(name="登录需求测试用例集", requirement_doc_id="doc-1"),
        ACTOR,
    )

    async def fake_generate_test_cases(input_data):
        assert input_data.requirement_name == "登录需求"
        assert "用户可以登录系统" in input_data.requirement_content
        assert input_data.include_company_knowledge is True
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
                            steps=["打开登录页", "输入正确账号密码", "提交登录"],
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
