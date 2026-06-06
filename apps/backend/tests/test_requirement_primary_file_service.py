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
async def test_review_primary_requirement_file_generates_preliminary_version_with_auxiliary_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        if filename == "main.md":
            return "# 主需求\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"
        return "# 辅助需求\n\n验证码有效期为 5 分钟。\n", "已生成辅助需求标准 Markdown。"

    class FakeQualityGate:
        result = "passed"
        testability_score = 90
        blocking_issues: list[str] = []

    class FakeAnalysisOutput:
        status = "completed"
        analysis_summary = "需求分析完成，补强 1 项。"
        quality_gate = FakeQualityGate()
        preliminary_requirement_markdown = (
            "# 主需求\n\n用户可以使用验证码登录。\n\n"
            "> 辅助补强\n"
            "> 来源：supporting.md\n"
            "> 证据：验证码有效期为 5 分钟。\n"
        )

        def model_dump(self):
            return {
                "status": "completed",
                "analysis_summary": "需求分析完成，补强 1 项。",
                "preliminary_requirement_markdown": self.preliminary_requirement_markdown,
                "applied_supplements": [
                    {
                        "id": "SUP-001",
                        "source_question_id": "Q-001",
                        "module_key": "login",
                        "module_name": "登录",
                        "insertion_anchor": "用户可以使用验证码登录。",
                        "inserted_markdown": "验证码有效期为 5 分钟。",
                        "evidence": {
                            "mapping_id": "supporting-mapping",
                            "filename": "supporting.md",
                            "excerpt": "验证码有效期为 5 分钟。",
                            "section_hint": "",
                        },
                        "reason": "辅助文档明确补充验证码有效期。",
                        "confidence": "high",
                    }
                ],
                "modules": [],
                "clarification_questions": [],
                "conflicts": [],
                "quality_gate": {
                    "result": "passed",
                    "testability_score": 90,
                    "blocking_issues": [],
                    "warning_issues": [],
                    "passed_checks": ["辅助补强已写入初步需求"],
                },
                "next_actions": [],
            }

    async def fake_analyze_requirement(input_data):
        assert input_data.primary_filename == "main.md"
        assert "用户可以使用验证码登录" in input_data.primary_markdown_content
        assert len(input_data.auxiliary_documents) == 1
        assert input_data.auxiliary_documents[0].filename == "supporting.md"
        assert "验证码有效期为 5 分钟" in input_data.auxiliary_documents[0].markdown_content
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main"), _upload_file("supporting.md", "# supporting")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_ids = [item["id"] for item in result["files"]]
    await document_service.convert_pending_file_mappings(mapping_ids)

    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)
    overview = document_service.get_document_overview("project-1", result["document"]["id"], ACTOR)

    assert review["status"] == "completed"
    assert review["analysis_summary"] == "需求分析完成，补强 1 项。"
    assert review["preliminary_requirement_markdown"] == FakeAnalysisOutput.preliminary_requirement_markdown
    assert overview["document"]["current_version"]["version_no"] == 1
    assert "辅助补强" in overview["initial_markdown_content"]
    assert "验证码有效期为 5 分钟" in overview["initial_markdown_content"]
    assert overview["document"]["current_version"]["source_action"] == "requirement_analysis"
