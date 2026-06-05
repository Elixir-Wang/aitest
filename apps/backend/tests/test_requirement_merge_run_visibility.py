import asyncio

import pytest

from app.core import db as core_db
from app.core import settings
from app.core import storage
from app.seed.init_db import init_db
from app.services import task_service
from app.services.document import merge_orchestrator


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def _use_temp_storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    projects_dir = data_dir / "projects"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", projects_dir)
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", projects_dir)
    monkeypatch.setattr(merge_orchestrator, "project_requirement_dir", storage.project_requirement_dir)
    init_db()


def _seed_mergeable_document() -> None:
    standard_path = storage.project_requirement_dir("project-1", "doc-1") / "standard" / "map-1.md"
    standard_path.parent.mkdir(parents=True, exist_ok=True)
    standard_path.write_text("# 登录需求\n\n## 登录\n\n系统应支持验证码登录。\n", encoding="utf-8")
    with core_db.connect() as db:
        db.execute("INSERT INTO projects (id, name, status, description) VALUES ('project-1', '测试项目', 'active', '')")
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
            VALUES ('doc-1', 'project-1', '登录需求', 'PRD', 'pending_merge', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_document_file_mappings
              (id, document_id, source_file_path, original_filename, file_format, markdown_file_path,
               conversion_status, mapping_status, created_by)
            VALUES ('map-1', 'doc-1', 'raw/login.md', 'login.md', 'md', ?, 'success', 'pending_merge', 'u-admin')
            """,
            ("project-1/requirements/doc-1/standard/map-1.md",),
        )


@pytest.mark.anyio
async def test_requirement_merge_run_is_visible_while_agent_work_is_running(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_storage(monkeypatch, tmp_path)
    _seed_mergeable_document()
    merge_started = asyncio.Event()
    allow_merge_to_finish = asyncio.Event()

    async def fake_run_outline_merge(**kwargs):
        merge_started.set()
        await allow_merge_to_finish.wait()
        return {
            "status": "merged",
            "markdown_content": "# 登录需求\n\n系统应支持验证码登录。\n",
            "merge_summary": "归并 1 个标准文件。",
            "diff_summary": "生成最终需求稿。",
            "affected_modules": ["登录"],
            "source_file_ids": ["map-1"],
            "coverage_items": [
                {
                    "mapping_id": "map-1",
                    "source_heading": "登录",
                    "source_excerpt": "系统应支持验证码登录。",
                    "target_module": "登录",
                    "target_heading": "登录",
                    "coverage_status": "merged",
                    "reason": "已合并",
                }
            ],
            "quality_result": "passed",
            "quality_issues": [],
            "machine_artifacts": {},
        }

    monkeypatch.setattr(merge_orchestrator, "_run_outline_merge", fake_run_outline_merge)

    merge_task = asyncio.create_task(
        merge_orchestrator.merge_document_markdown("project-1", "doc-1", ACTOR, force_rebuild=True)
    )
    await asyncio.wait_for(merge_started.wait(), timeout=1)

    running_tasks = task_service.list_running_tasks(ACTOR, project_id="project-1")

    allow_merge_to_finish.set()
    result = await merge_task

    assert [task["source_type"] for task in running_tasks] == ["requirement_merge"]
    assert running_tasks[0]["status"] == "running"
    assert running_tasks[0]["title"] == "登录需求"
    assert result["status"] == "merged"
