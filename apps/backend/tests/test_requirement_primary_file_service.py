from pathlib import Path

import pytest

from app.core import db as core_db
from app.seed.init_db import init_db
from app.services.document import service as document_service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()


def _seed_project() -> None:
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description) VALUES ('project-1', '测试项目', 'active', '')"
        )


class FakeUploadFile:
    def __init__(self, filename: str, content: str) -> None:
        self.filename = filename
        self._content = content.encode("utf-8")

    async def read(self) -> bytes:
        return self._content


def _upload_file(filename: str, content: str) -> FakeUploadFile:
    return FakeUploadFile(filename, content)


@pytest.mark.anyio
async def test_primary_upload_marks_first_file_without_generating_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return f"# {filename}\n\n主需求内容。\n", "已生成标准 Markdown。"

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]

    await document_service.convert_pending_file_mappings([mapping_id])

    overview = document_service.get_document_overview("project-1", result["document"]["id"], ACTOR)
    assert overview["document"]["current_version_id"] is None
    assert overview["files"][0]["file_role"] == "primary"
    assert overview["files"][0]["version_no"] is None
    assert overview["initial_markdown_content"] == ""


@pytest.mark.anyio
async def test_setting_supporting_file_as_primary_only_changes_roles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return f"# {filename}\n\n标准内容。\n", "已生成标准 Markdown。"

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main"), _upload_file("supplement.md", "# supplement")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_ids = [item["id"] for item in result["files"]]
    main_mapping_id = next(item["id"] for item in result["files"] if item["original_filename"] == "main.md")
    supplement_mapping_id = next(item["id"] for item in result["files"] if item["original_filename"] == "supplement.md")
    await document_service.convert_pending_file_mappings(mapping_ids)

    overview = document_service.set_primary_requirement_file(
        "project-1",
        result["document"]["id"],
        supplement_mapping_id,
        ACTOR,
    )

    roles = {item["id"]: item["file_role"] for item in overview["files"]}
    assert roles[supplement_mapping_id] == "primary"
    assert roles[main_mapping_id] == "supporting"
    assert overview["document"]["current_version_id"] is None
    assert overview["initial_markdown_content"] == ""


@pytest.mark.anyio
async def test_review_primary_requirement_file_generates_version_and_analysis(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return f"# {filename}\n\n标准内容。\n", "已生成标准 Markdown。"

    class FakeQualityGate:
        result = "passed"
        testability_score = 90
        blocking_issues: list[str] = []

    class FakeAnalysisOutput:
        status = "completed"
        analysis_summary = "需求评审完成。"
        quality_gate = FakeQualityGate()

        def model_dump(self):
            return {
                "status": "completed",
                "analysis_summary": "需求评审完成。",
                "modules": [],
                "clarification_questions": [],
                "quality_gate": {
                    "result": "passed",
                    "testability_score": 90,
                    "blocking_issues": [],
                    "warnings": [],
                },
                "traceability": [],
            }

    async def fake_run_requirement_analysis(input_data):
        assert "# main.md" in input_data.markdown_content
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.run_requirement_analysis", fake_run_requirement_analysis)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])

    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)
    overview = document_service.get_document_overview("project-1", result["document"]["id"], ACTOR)

    assert review["status"] == "completed"
    assert review["analysis_summary"] == "需求评审完成。"
    assert overview["document"]["current_version"]["version_no"] == 1
    assert "# main.md" in overview["initial_markdown_content"]
    assert overview["files"][0]["version_no"] == 1
