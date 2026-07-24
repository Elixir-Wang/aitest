from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core import db as core_db
from app.core import storage
from app.repositories import test_point_repo
from app.schemas.test_point import TestPointMarkdownUpdateIn as MarkdownUpdateIn
from app.schemas.test_point import TestPointUpdateIn as PointUpdateIn
from app.seed.init_db import init_db
from app.services import test_point_service
from app.services.test_point_markdown import parse_test_points, serialize_test_points


ADMIN = {
    "id": "u-admin",
    "role": "admin",
    "nickname": "管理员",
    "username": "admin",
    "project_scope": "全部项目",
}
TESTER = ADMIN | {"id": "u-tester", "role": "tester", "username": "tester"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    init_db()


def _point(point_key: str, title: str, *, priority: str = "P0") -> dict:
    return {
        "id": f"tp-{point_key}",
        "point_key": point_key,
        "title": title,
        "module": "登录",
        "category": "功能",
        "priority": priority,
        "description": f"{title}的描述",
        "preconditions": ["登录服务正常"],
        "verification_points": [f"验证{title}"],
        "source_refs": ["需求 3.1"],
        "notes": "",
    }


def _seed_test_points() -> None:
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description, created_by) VALUES (?, ?, 'active', '', ?)",
            ("project-1", "测试项目", ADMIN["id"]),
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES (?, ?, ?, 'PRD', 'version-1', 'finalized', ?)
            """,
            ("doc-1", "project-1", "登录需求", ADMIN["id"]),
        )
        db.execute(
            """
            INSERT INTO source_document_versions
              (id, document_id, version_no, markdown_content, file_path, source_action, change_summary, created_by)
            VALUES (?, ?, 1, ?, '', 'requirement_analysis_finalize', '确认最终需求', ?)
            """,
            ("version-1", "doc-1", "# 登录需求", ADMIN["id"]),
        )
        test_point_repo.create_run(
            db,
            run_id="run-1",
            project_id="project-1",
            document_id="doc-1",
            version_id="version-1",
            task_id="test-point-generation:run-1",
            input_json="{}",
            created_by=ADMIN["id"],
        )
        test_point_repo.update_run(db, "run-1", status="completed")
        test_point_repo.replace_points(
            db,
            run_id="run-1",
            project_id="project-1",
            document_id="doc-1",
            version_id="version-1",
            points=[_point("login.success", "登录成功"), _point("login.failure", "登录失败", priority="P1")],
        )


def test_overview_contains_serialized_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_test_points()

    overview = test_point_service.get_overview("project-1", "doc-1", ADMIN)

    assert overview["markdown_content"].startswith("# 测试点\n")
    assert "### [login.success] 登录成功" in overview["markdown_content"]
    assert all("point_key" not in point for point in overview["points"])


def test_save_markdown_preserves_existing_ids_and_syncs_additions_and_deletions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_test_points()
    current = test_point_service.get_overview("project-1", "doc-1", ADMIN)
    edited_points = parse_test_points(current["markdown_content"])
    edited_points = [point for point in edited_points if point["point_key"] != "login.failure"]
    edited_points[0]["title"] = "登录成功并进入首页"
    edited_points.append(
        {
            "point_key": "login.locked",
            "title": "锁定账号禁止登录",
            "module": "登录",
            "category": "权限",
            "priority": "P1",
            "description": "验证锁定账号无法登录。",
            "preconditions": ["账号已锁定"],
            "verification_points": ["登录请求被拒绝"],
            "source_refs": ["需求 3.2"],
            "notes": "",
            "status": "draft",
        }
    )

    updated = test_point_service.save_markdown(
        "project-1",
        "doc-1",
        MarkdownUpdateIn(markdown_content=serialize_test_points(edited_points)),
        ADMIN,
    )

    assert all("point_key" not in point for point in updated["points"])
    with core_db.connect() as db:
        rows = test_point_repo.list_points(db, "doc-1", "version-1")
    by_key = {row["point_key"]: row for row in rows}
    assert set(by_key) == {"login.success", "login.locked"}
    assert by_key["login.success"]["id"] == "tp-login.success"
    assert by_key["login.success"]["title"] == "登录成功并进入首页"
    assert by_key["login.locked"]["id"].startswith("tp-")


def test_save_markdown_rejects_invalid_document_without_changing_points(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_test_points()
    before = test_point_service.get_overview("project-1", "doc-1", ADMIN)
    invalid_markdown = before["markdown_content"].replace("| 优先级 | P0 |", "| 优先级 | P9 |")

    with pytest.raises(ValueError, match="优先级无效"):
        test_point_service.save_markdown(
            "project-1",
            "doc-1",
            MarkdownUpdateIn(markdown_content=invalid_markdown),
            ADMIN,
        )

    after = test_point_service.get_overview("project-1", "doc-1", ADMIN)
    assert after["points"] == before["points"]


def test_update_point_rejects_duplicate_title(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_test_points()

    with pytest.raises(HTTPException) as error:
        test_point_service.update_point(
            "project-1",
            "doc-1",
            "tp-login.failure",
            PointUpdateIn(title="登录成功"),
            ADMIN,
        )

    assert error.value.status_code == 409
    assert error.value.detail["message"] == "测试点标题已存在，请使用能够区分测试目标的唯一标题。"


def test_save_markdown_requires_admin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_test_points()
    overview = test_point_service.get_overview("project-1", "doc-1", ADMIN)

    with pytest.raises(HTTPException) as error:
        test_point_service.save_markdown(
            "project-1",
            "doc-1",
            MarkdownUpdateIn(markdown_content=overview["markdown_content"]),
            TESTER,
        )

    assert error.value.status_code == 403
