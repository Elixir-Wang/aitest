import asyncio
from pathlib import Path

import pytest

from app.agents.rejected_case_search.schemas import (
    RejectedCaseReference,
    RejectedCaseSearchInput,
    RejectedCaseSearchResult,
    SearchTestPoint,
)
from app.core import db as core_db
from app.core import settings, storage
from app.repositories import global_knowledge_repo
from app.seed.init_db import init_db
from app.services.knowledge import global_service
from app.services.rejected_case_knowledge import markdown_codec
from app.services.rejected_case_knowledge import service as rejected_service
from app.services.rejected_case_knowledge.schemas import (
    RejectedCaseKnowledgeDocument,
    RejectedCaseRecord,
)
from scripts.migrate_rejected_case_knowledge_base import (
    migrate as migrate_rejected_case_knowledge_base,
)

ACTOR = {"id": "u-admin", "role": "admin"}


def _record(**updates) -> RejectedCaseRecord:
    values = {
        "record_id": "rjc-1234567890abcdef",
        "project_id": "project-1",
        "project_name": "测试项目",
        "requirement_id": "doc-1",
        "requirement_name": "登录需求",
        "requirement_version_id": "version-1",
        "requirement_version_no": 1,
        "generation_run_id": "run-1",
        "test_case_set_id": "set-1",
        "test_case_id": "case-1",
        "title": "错误密码登录",
        "module": "登录",
        "priority": "P1",
        "steps": [{"action": "输入错误密码", "expected_result": "提示错误"}],
        "expected_result": "登录失败",
        "reason_type": "重复用例",
        "reason": "与已有错误密码用例重复",
        "handling": "block_duplicate",
        "reviewed_by": "u-admin",
        "reviewed_at": "2026-07-24T12:00:00+00:00",
    }
    values.update(updates)
    return RejectedCaseRecord.model_validate(values)


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    init_db()
    base = global_service.create_base(name="百工", actor=ACTOR)
    monkeypatch.setattr(settings, "REJECTED_CASE_KNOWLEDGE_BASE_ID", "")
    return base["id"]


def test_markdown_codec_upserts_and_deactivates_by_record_id() -> None:
    first = _record()
    content = markdown_codec.upsert_record("", first)
    content = markdown_codec.upsert_record(content, first.model_copy(update={"reason": "更新后的原因"}))

    _, records = markdown_codec.parse_document(content)
    assert len(records) == 1
    assert records[0].reason == "更新后的原因"
    assert "# 登录需求" in content
    assert "测试项目 · **1 条有效反馈**" in content
    assert "## 1. 错误密码登录" in content
    assert "RJC-1234567890ABCDEF" not in content
    assert "> **不采纳原因：** 更新后的原因" in content
    assert "有效 · 登录 · P1 · V1" in content
    assert "| 步骤 | 操作 | 预期结果 |" not in content
    assert "### 原用例" not in content
    assert "### 后续生成规则" not in content
    assert "原生成运行 ID" not in content

    inactive_content, inactive = markdown_codec.deactivate(
        content,
        first.record_id,
        deactivated_at="2026-07-24T13:00:00+00:00",
    )
    assert inactive is not None
    assert markdown_codec.parse_document(inactive_content)[1][0].status == "inactive"


def test_global_knowledge_upsert_preserves_file_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base_id = _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        base = db.execute("SELECT * FROM global_knowledge_bases WHERE id = ?", (base_id,)).fetchone()
    folder = global_service.create_folder(
        base_id,
        parent_id=base["root_folder_id"],
        name="测试目录",
        actor=ACTOR,
    )
    created = global_service.upsert_markdown_file(
        base_id,
        folder["id"],
        display_name="登录需求.md",
        markdown_content="# 第一版\n",
        actor=ACTOR,
    )
    updated = global_service.upsert_markdown_file(
        base_id,
        folder["id"],
        display_name="登录需求.md",
        markdown_content="# 第二版\n",
        actor=ACTOR,
    )

    assert updated["id"] == created["id"]
    assert updated["markdown_content"] == "# 第二版\n"
    assert Path(updated["markdown_path"]).read_text(encoding="utf-8") == "# 第二版\n"


def test_rejected_case_service_is_idempotent_and_collects_registered_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    baigong_base_id = _use_temp_db(monkeypatch, tmp_path)
    assert rejected_service.collect_project_documents("project-1") == []
    kwargs = {
        "project": {"id": "project-1", "name": "测试项目"},
        "requirement": {"id": "doc-1", "name": "登录需求"},
        "requirement_version": {"id": "version-1", "version_no": 1},
        "generation_run_id": "run-1",
        "test_case_set_id": "set-1",
        "test_case": {
            "id": "case-1",
            "title": "错误密码登录",
            "module": "登录",
            "priority": "P1",
            "preconditions": "账号存在",
            "steps": [{"action": "输入错误密码", "expected_result": "提示错误"}],
            "expected_result": "登录失败",
        },
        "reason": "与已有错误密码用例重复",
        "actor": ACTOR,
    }
    first = rejected_service.upsert_rejected_case(**kwargs)
    second = rejected_service.upsert_rejected_case(**kwargs)
    documents = rejected_service.collect_project_documents("project-1")

    assert second == first
    assert first["file_name"] == "登录需求.md"
    assert len(documents) == 1
    assert [record.record_id for record in documents[0].records] == [first["record_id"]]
    with core_db.connect() as db:
        rejected_base = global_knowledge_repo.find_base_by_name(db, "不采纳用例库")
        baigong = global_knowledge_repo.find_base(db, baigong_base_id)
        legacy_folder = global_knowledge_repo.find_folder_by_parent_and_name(
            db,
            baigong_base_id,
            baigong["root_folder_id"],
            "不采纳用例库",
        )
        project_folder = rejected_service._find_project_folder(rejected_base["id"], "project-1")

    assert rejected_base["id"] != baigong_base_id
    assert legacy_folder is None
    assert project_folder["parent_id"] == rejected_base["root_folder_id"]
    assert project_folder["name"] == "测试项目"


def test_legacy_folder_migrates_to_a_sibling_knowledge_base(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    baigong_base_id = _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        baigong = global_knowledge_repo.find_base(db, baigong_base_id)
    legacy_root = global_service.create_folder(
        baigong_base_id,
        parent_id=baigong["root_folder_id"],
        name="不采纳用例库",
        actor=ACTOR,
    )
    project_folder = global_service.create_folder(
        baigong_base_id,
        parent_id=legacy_root["id"],
        name="project-1-测试项目",
        actor=ACTOR,
    )
    global_service.upsert_markdown_file(
        baigong_base_id,
        project_folder["id"],
        display_name="doc-1-登录需求.md",
        markdown_content=markdown_codec.upsert_record("", _record()),
        actor=ACTOR,
    )

    report = migrate_rejected_case_knowledge_base(apply=True)
    documents = rejected_service.collect_project_documents("project-1")

    assert report == {
        "mode": "apply",
        "legacy_roots": 1,
        "folders": 1,
        "files": 1,
        "deleted_legacy_roots": 1,
        "renamed_folders": 1,
        "renamed_files": 1,
        "reformatted_files": 0,
    }
    assert len(documents) == 1
    assert documents[0].file_name == "登录需求.md"
    assert documents[0].records[0].record_id == "rjc-1234567890abcdef"
    with core_db.connect() as db:
        assert global_knowledge_repo.find_folder(db, legacy_root["id"]) is None
        rejected_base = global_knowledge_repo.find_base_by_name(db, "不采纳用例库")
        migrated_folder = rejected_service._find_project_folder(rejected_base["id"], "project-1")
    assert migrated_folder["name"] == "测试项目"


def test_missing_coverage_reason_requires_correction_instead_of_blocking() -> None:
    assert rejected_service._classify_reason("缺少异常输入覆盖") == (
        "预期结果错误",
        "generate_with_correction",
    )


def test_rejected_case_search_validates_record_and_file_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.rejected_case_search import service

    record = _record()
    document = RejectedCaseKnowledgeDocument(
        file_id="gkfile-1",
        file_name="doc-1-登录需求.md",
        markdown_content=markdown_codec.upsert_record("", record),
        records=[record],
    )
    input_data = RejectedCaseSearchInput(
        project_id="project-1",
        project_name="测试项目",
        requirement_id="doc-2",
        requirement_name="登录改造",
        requirement_version_id="version-2",
        requirement_version_no=2,
        requirement_content="# 登录改造",
        test_points=[SearchTestPoint(point_key="TP-1", title="错误密码", module="登录")],
        source_documents=[document],
    )

    class FakeAgent:
        async def ainvoke(self, _payload):
            return {
                "structured_response": RejectedCaseSearchResult(
                    matches=[
                        RejectedCaseReference(
                            record_id=record.record_id,
                            source_file_id="gkfile-1",
                            source_file_name="ignored.md",
                            source_requirement_id="ignored",
                            matched_test_point_keys=["TP-1", "invented"],
                            title="ignored",
                            reason_type="ignored",
                            reason="ignored",
                            handling="warning_only",
                            relevance="high",
                        )
                    ]
                )
            }

    monkeypatch.setattr(service, "resolve_model_selection", lambda _capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda *_args, **_kwargs: "model")
    monkeypatch.setattr(service, "thinking_disabled_extra_body", lambda _selection: None)
    monkeypatch.setattr(service, "rejected_case_search_agent", lambda _model: FakeAgent())

    result = asyncio.run(service.search_rejected_cases(input_data))

    assert result.matches[0].matched_test_point_keys == ["TP-1"]
    assert result.matches[0].reason == record.reason
    assert result.matches[0].handling == "block_duplicate"
