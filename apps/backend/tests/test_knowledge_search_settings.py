from pathlib import Path

import pytest

from app.core import db as core_db
from app.repositories import knowledge_search_source_settings_repo
from app.seed.init_db import init_db
from app.services.knowledge import service as knowledge_service
from app.schemas.knowledge import KnowledgeSearchSettingsUpdate, KnowledgeSearchSourceSetting
from app.agents.knowledge.schemas import KnowledgeQueryInput, KnowledgeSourceDocumentInput
from app.agents.knowledge.service import _document_path, _manifest


def test_project_settings_inherit_global_and_allow_sparse_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()
    with core_db.connect() as db:
        knowledge_search_source_settings_repo.replace_scope(
            db,
            "__all_projects__",
            {
                "final_requirements": True,
                "explorations": True,
                "test_cases": False,
                "api_information": False,
                "company_knowledge": True,
            },
            actor_id="admin",
        )
        knowledge_search_source_settings_repo.replace_scope(
            db,
            "project-1",
            {"test_cases": True},
            actor_id="admin",
        )

        resolved = knowledge_service.resolve_knowledge_search_settings(db, "project-1")

        assert resolved["final_requirements"] == {"enabled": True, "origin": "global", "inherited": True}
        assert resolved["test_cases"] == {"enabled": True, "origin": "project", "inherited": False}
        assert resolved["company_knowledge"] == {"enabled": True, "origin": "global", "inherited": True}

        knowledge_search_source_settings_repo.delete_scope(db, "project-1")

        restored = knowledge_service.resolve_knowledge_search_settings(db, "project-1")
        assert restored["test_cases"] == {"enabled": False, "origin": "global", "inherited": True}


def test_settings_reject_all_sources_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()

    with pytest.raises(Exception) as exc_info:
        knowledge_service.update_knowledge_search_settings(
            "__all_projects__",
            KnowledgeSearchSettingsUpdate(
                sources=[KnowledgeSearchSourceSetting(source_type="final_requirements", enabled=False)],
            ),
            {"id": "admin", "role": "admin"},
        )

    assert "请至少启用一个检索来源" in str(exc_info.value)


@pytest.mark.parametrize(
    ("source_type", "expected_prefix"),
    [
        ("exploration", "/explorations/"),
        ("test_case", "/test-cases/"),
        ("api_information", "/api-information/"),
    ],
)
def test_agent_virtual_paths_group_new_sources_by_directory(source_type: str, expected_prefix: str) -> None:
    document = KnowledgeSourceDocumentInput(
        source_type=source_type,
        source_id=f"{source_type}-1",
        source_title="示例来源",
        project_id="project-1",
        project_name="示例项目",
        markdown_content="# 示例\n",
    )

    assert _document_path(1, document).startswith(expected_prefix)


def test_agent_manifest_describes_enabled_roots_without_listing_files() -> None:
    documents = [
        KnowledgeSourceDocumentInput(
            source_type=source_type,
            source_id=f"{source_type}-1",
            source_title="示例来源",
            project_id="project-1",
            project_name="示例项目",
            markdown_content="# 示例\n",
        )
        for source_type in ("requirement", "exploration", "test_case", "api_information", "company_knowledge")
    ]

    manifest = _manifest(
        KnowledgeQueryInput(
            project_id="project-1",
            project_name="示例项目",
            question="查询测试范围",
            source_documents=documents,
        )
    )

    assert "/requirements/" not in manifest
    assert "`/final-requirements/`：1 个文件" in manifest
    assert "`/explorations/`：1 个文件" in manifest
    assert "`/test-cases/`：1 个文件" in manifest
    assert "`/api-information/`：1 个文件" in manifest
    assert "`/company-knowledge/`：1 个文件" in manifest
    assert "先使用 glob 或 grep" in manifest
