from pathlib import Path
import json

import pytest
from fastapi import HTTPException

from app.core import db as core_db
from app.repositories import document_repo
from app.seed.init_db import init_db
from app.schemas.document import (
    RequirementAnalysisFinalizeIn,
    RequirementClarificationAnswerIn,
    RequirementPreliminaryUpdateIn,
)
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


def _seed_requirement_document(document_id: str = "doc-1") -> None:
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
            VALUES (?, 'project-1', '登录需求', 'PRD', 'uploaded', ?)
            """,
            (document_id, ACTOR["id"]),
        )


class FakeUploadFile:
    def __init__(self, filename: str, content: str) -> None:
        self.filename = filename
        self._content = content.encode("utf-8")

    async def read(self) -> bytes:
        return self._content


def _upload_file(filename: str, content: str) -> FakeUploadFile:
    return FakeUploadFile(filename, content)


def test_v3_requirement_analysis_output_serializes_structured_fields() -> None:
    from app.agents.requirement_analysis.clarification.schemas import (
        ClarificationOutput,
        ClarificationSummary,
    )
    from app.agents.requirement_analysis.schemas import (
        RequirementAnalysisResultV2,
    )
    from app.agents.requirement_analysis.quality.schemas import (
        ClarityAssessment,
        CompletenessAssessment,
        ConsistencyAssessment,
        QualityAssessmentOutput,
        QualityDecision,
        QualityIssueSummary,
        TestabilityAssessment,
    )
    from app.agents.requirement_analysis.understanding.schemas import (
        RequirementUnderstandingOutput,
    )

    analysis_output = RequirementAnalysisResultV2(
        status="completed",
        understanding=RequirementUnderstandingOutput(
            modules=[],
            dependencies=[],
            risks=[],
            assumptions=[],
            understanding_summary="已识别登录需求。",
        ),
        quality_assessment=QualityAssessmentOutput(
            summary=QualityIssueSummary(
                completeness_issues=3,
                clarity_issues=2,
                testability_issues=4,
                consistency_issues=1,
                total_issues=10,
                by_severity={"blocker": 0, "major": 5, "minor": 5},
                has_blocker=False,
                can_proceed=True,
            ),
            decision=QualityDecision(
                result="conditional",
                rationale="需要补齐验证码边界。",
                blocking_issues=[],
                recommended_actions=["补齐验证码错误次数。"],
            ),
            completeness=CompletenessAssessment(),
            clarity=ClarityAssessment(),
            testability=TestabilityAssessment(),
            consistency=ConsistencyAssessment(),
            assessment_summary="质量评估完成。\\n\\n主要优点：\\n1. 主流程清晰。\\n2. 质量保障信息完整。",
        ),
        clarification=ClarificationOutput(
            items=[],
            summary=ClarificationSummary(total=0),
            overall_assessment="无需澄清。",
            generated_at="2026-06-15T00:00:00Z",
        ),
        analysis_report_markdown="# 需求分析报告\n\n主流程已识别。",
        enhanced_requirement_markdown="# 增强版需求\n\n用户可以使用验证码登录。",
    )

    preliminary_markdown, output_data = document_service._output_from_analysis_result(
        analysis_output,
        "# 主需求\n\n用户可以使用验证码登录。",
    )

    assert preliminary_markdown == "# 增强版需求\n\n用户可以使用验证码登录。"
    assert output_data["preliminary_requirement_markdown"] == preliminary_markdown
    assert output_data["enhanced_requirement_markdown"] == preliminary_markdown
    assert output_data["quality_assurance_report_markdown"].startswith("# 质量保障报告")
    assert "\\n" not in output_data["quality_assurance_report_markdown"]
    assert "主要优点：\n1. 主流程清晰。" in output_data["quality_assurance_report_markdown"]
    assert "## 质量问题统计" in output_data["quality_assurance_report_markdown"]
    assert output_data["clarification_report_markdown"].startswith("# 待澄清内容")
    assert output_data["quality_gate"]["result"] == "warning"
    assert output_data["quality_summary"]["total_issues"] == 10
    assert "testability_score" not in output_data["quality_gate"]
    assert "maturity_assessment" not in output_data


def test_latest_requirement_analysis_normalizes_saved_markdown_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    _seed_requirement_document("doc-1")
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO requirement_analyses
              (id, project_id, document_id, status, analysis_summary, output_json, quality_result, created_by)
            VALUES (?, ?, ?, 'completed', ?, ?, 'passed', ?)
            """,
            (
                "analysis-1",
                "project-1",
                "doc-1",
                "需求分析完成。",
                json.dumps(
                    {
                        "preliminary_requirement_markdown": "# 初步需求\\n\\n登录。",
                        "quality_assurance_report_markdown": "# 质量保证报告\\n\\n## 质量摘要\\n\\n主要优点：\\n1. 主流程清晰。",
                    },
                    ensure_ascii=False,
                ),
                ACTOR["id"],
            ),
        )

    result = document_service.get_latest_requirement_analysis("project-1", "doc-1", ACTOR)

    output = result["analysis"]["output"]
    assert output["preliminary_requirement_markdown"] == "# 初步需求\n\n登录。"
    assert output["quality_assurance_report_markdown"].startswith("# 质量保障报告\n\n## 质量摘要")
    assert "\\n" not in output["quality_assurance_report_markdown"]
    assert "主要优点：\n1. 主流程清晰。" in output["quality_assurance_report_markdown"]


def test_update_requirement_preliminary_markdown_updates_analysis_draft(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    _seed_requirement_document("doc-1")
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO requirement_analyses
              (id, project_id, document_id, status, analysis_summary, output_json, quality_result, testability_score,
               draft_content_hash, created_by)
            VALUES (?, ?, ?, 'completed', ?, ?, 'passed', 90, ?, ?)
            """,
            (
                "analysis-1",
                "project-1",
                "doc-1",
                "需求分析完成。",
                json.dumps(
                    {
                        "status": "completed",
                        "analysis_summary": "需求分析完成。",
                        "preliminary_requirement_markdown": "# 初步需求\n\n登录。",
                        "enhanced_requirement_markdown": "# 初步需求\n\n登录。",
                        "quality_gate": {"result": "passed", "testability_score": 90},
                    },
                    ensure_ascii=False,
                ),
                "old-hash",
                ACTOR["id"],
            ),
        )

    result = document_service.update_requirement_preliminary_markdown(
        "project-1",
        "doc-1",
        "analysis-1",
        RequirementPreliminaryUpdateIn(
            markdown_content="# 初步需求\n\n登录支持验证码。",
            change_summary="AI修改：补充验证码",
        ),
        ACTOR,
    )

    output = result["analysis"]["output"]
    assert output["preliminary_requirement_markdown"] == "# 初步需求\n\n登录支持验证码。"
    assert output["enhanced_requirement_markdown"] == "# 初步需求\n\n登录支持验证码。"
    assert result["analysis"]["draft_content_hash"] != "old-hash"


def test_get_version_detail_and_switch_current_final_requirement_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    document_id = "doc-1"
    version_1_path = tmp_path / "v1.md"
    version_2_path = tmp_path / "v2.md"
    version_1_path.write_text("# 最终需求 v1\n\n登录支持验证码。", encoding="utf-8")
    version_2_path.write_text("# 最终需求 v2\n\n登录支持验证码和密码。", encoding="utf-8")

    with core_db.connect() as db:
        document_repo.create_document(
            db,
            document_id=document_id,
            project_id="project-1",
            name="登录需求",
            document_type="PRD",
            status="versioned",
            created_by=ACTOR["id"],
        )
        document_repo.create_version(
            db,
            version_id="docver-1",
            document_id=document_id,
            version_no=1,
            file_path=str(version_1_path),
            source_action="requirement_analysis_finalize",
            change_summary="初步需求转为最终需求",
            diff_summary="第一版最终需求。",
            created_by=ACTOR["id"],
        )
        document_repo.create_version(
            db,
            version_id="docver-2",
            document_id=document_id,
            version_no=2,
            file_path=str(version_2_path),
            source_action="requirement_analysis_finalize",
            change_summary="初步需求转为最终需求",
            diff_summary="第二版最终需求。",
            created_by=ACTOR["id"],
        )
        document_repo.update_current_version(db, document_id, "docver-2", "versioned")

    detail = document_service.get_document_version_detail("project-1", document_id, "docver-1")
    assert detail["version_no"] == 1
    assert detail["is_current"] is False
    assert detail["markdown_content"] == "# 最终需求 v1\n\n登录支持验证码。"

    switch = document_service.switch_document_current_version("project-1", document_id, "docver-1", ACTOR)
    overview = document_service.get_document_overview("project-1", document_id, ACTOR)
    current_detail = document_service.get_document_version_detail("project-1", document_id, "docver-1")

    assert switch["document"]["current_version_id"] == "docver-1"
    assert switch["markdown_content"] == "# 最终需求 v1\n\n登录支持验证码。"
    assert overview["document"]["current_version_id"] == "docver-1"
    assert overview["initial_markdown_content"] == "# 最终需求 v1\n\n登录支持验证码。"
    assert current_detail["is_current"] is True


def test_list_requirement_analysis_runs_marks_importable_preliminary_requirement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    _seed_requirement_document("doc-1")
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO requirement_analyses
              (id, project_id, document_id, status, analysis_summary, output_json, quality_result, created_by)
            VALUES (?, ?, ?, 'completed', ?, ?, 'passed', ?)
            """,
            (
                "analysis-1",
                "project-1",
                "doc-1",
                "需求分析完成。",
                json.dumps({"preliminary_requirement_markdown": "# 初步需求\n\n登录。"}, ensure_ascii=False),
                ACTOR["id"],
            ),
        )
        db.execute(
            """
            INSERT INTO requirement_analysis_runs
              (id, project_id, document_id, analysis_id, status, summary, created_by)
            VALUES (?, ?, ?, ?, 'completed', ?, ?)
            """,
            ("reqrun-1", "project-1", "doc-1", "analysis-1", "需求分析完成。", ACTOR["id"]),
        )

    runs = document_service.list_requirement_analysis_runs("project-1", "doc-1", ACTOR)

    assert runs == [
        {
            "id": "reqrun-1",
            "project_id": "project-1",
            "document_id": "doc-1",
            "analysis_id": "analysis-1",
            "status": "completed",
            "summary": "需求分析完成。",
            "failure_reason": "",
            "created_at": runs[0]["created_at"],
            "updated_at": runs[0]["updated_at"],
            "has_enhanced_requirement": True,
        }
    ]


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
    assert result["document"]["status"] == "pending_review"

    await document_service.convert_pending_file_mappings([mapping_id])

    overview = document_service.get_document_overview("project-1", result["document"]["id"], ACTOR)
    assert overview["document"]["current_version_id"] is None
    assert overview["files"][0]["file_role"] == "primary"
    assert overview["files"][0]["version_no"] is None
    assert overview["initial_markdown_content"] == ""


@pytest.mark.anyio
async def test_new_upload_auto_starts_requirement_analysis_after_conversion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return f"# {filename}\n\n主需求内容。\n", "已生成标准 Markdown。"

    executed_run_ids: list[str] = []

    async def fake_execute_requirement_review_run(run_id: str, actor) -> None:
        executed_run_ids.append(run_id)

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr(
        "app.services.document.service.execute_requirement_review_run",
        fake_execute_requirement_review_run,
    )

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    document_id = result["document"]["id"]

    await document_service.convert_pending_file_mappings([mapping_id], ACTOR, auto_continue=True)

    assert len(executed_run_ids) == 1
    runs = document_service.list_requirement_analysis_runs("project-1", document_id, ACTOR)
    assert len(runs) == 1
    assert runs[0]["id"] == executed_run_ids[0]
    assert runs[0]["status"] == "queued"


@pytest.mark.anyio
async def test_convert_without_auto_continue_does_not_start_requirement_analysis(
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

    runs = document_service.list_requirement_analysis_runs("project-1", result["document"]["id"], ACTOR)
    assert runs == []


@pytest.mark.anyio
async def test_auto_continue_only_starts_once_for_multi_file_new_upload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return f"# {filename}\n\n标准内容。\n", "已生成标准 Markdown。"

    executed_run_ids: list[str] = []

    async def fake_execute_requirement_review_run(run_id: str, actor) -> None:
        executed_run_ids.append(run_id)

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr(
        "app.services.document.service.execute_requirement_review_run",
        fake_execute_requirement_review_run,
    )

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main"), _upload_file("supplement.md", "# supplement")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_ids = [item["id"] for item in result["files"]]

    await document_service.convert_pending_file_mappings(mapping_ids, ACTOR, auto_continue=True)

    assert len(executed_run_ids) == 1
    runs = document_service.list_requirement_analysis_runs("project-1", result["document"]["id"], ACTOR)
    assert len(runs) == 1


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
async def test_review_primary_requirement_file_generates_preliminary_analysis_with_auxiliary_context(
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
        analysis_report_markdown = "# 分析报告\n\n已使用辅助文件补充验证码有效期。"
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
                "analysis_report_markdown": self.analysis_report_markdown,
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
        assert not hasattr(input_data, "auxiliary_documents")
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
    assert review["version_id"] is None
    assert review["finalized_version_id"] is None
    assert overview["document"]["current_version_id"] is None
    assert overview["document"]["current_version"] is None
    assert overview["initial_markdown_content"] == ""

    latest = document_service.get_latest_requirement_analysis("project-1", result["document"]["id"], ACTOR)
    assert latest["analysis"]["id"] == review["id"]
    assert latest["analysis"]["output"]["preliminary_requirement_markdown"] == FakeAnalysisOutput.preliminary_requirement_markdown
    assert latest["analysis"]["output"]["analysis_report_markdown"] == FakeAnalysisOutput.analysis_report_markdown


@pytest.mark.anyio
async def test_finalize_requirement_analysis_creates_current_final_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return "# 主需求\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"

    class FakeQualityGate:
        result = "passed"
        testability_score = 90
        blocking_issues: list[str] = []

    class FakeAnalysisOutput:
        status = "completed"
        analysis_summary = "需求分析完成。"
        quality_gate = FakeQualityGate()
        preliminary_requirement_markdown = "# 主需求\n\n用户可以使用验证码登录。\n"

        def model_dump(self):
            return {
                "status": "completed",
                "analysis_summary": "需求分析完成。",
                "preliminary_requirement_markdown": self.preliminary_requirement_markdown,
                "applied_supplements": [],
                "modules": [],
                "clarification_questions": [],
                "conflicts": [],
                "quality_gate": {
                    "result": "passed",
                    "testability_score": 90,
                    "blocking_issues": [],
                    "warning_issues": [],
                    "passed_checks": ["主需求已分析"],
                },
                "next_actions": [],
            }

    async def fake_analyze_requirement(input_data):
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])

    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)
    finalize = document_service.finalize_requirement_analysis(
        "project-1",
        result["document"]["id"],
        RequirementAnalysisFinalizeIn(analysis_id=review["id"]),
        ACTOR,
    )
    overview = document_service.get_document_overview("project-1", result["document"]["id"], ACTOR)

    assert finalize["version"]["version_no"] == 1
    assert finalize["version"]["source_action"] == "requirement_analysis_finalize"
    assert finalize["analysis"]["finalized_version_id"] == finalize["version"]["id"]
    assert overview["document"]["current_version_id"] == finalize["version"]["id"]
    assert overview["initial_markdown_content"] == FakeAnalysisOutput.preliminary_requirement_markdown

    with core_db.connect() as db:
        version_count = db.execute(
            "SELECT COUNT(*) AS count FROM source_document_versions WHERE document_id = ?",
            (result["document"]["id"],),
        ).fetchone()["count"]
        change_log = db.execute(
            "SELECT source_action, change_summary FROM document_version_change_logs WHERE version_id = ?",
            (finalize["version"]["id"],),
        ).fetchone()

    assert version_count == 1
    assert change_log["source_action"] == "requirement_analysis_finalize"
    assert change_log["change_summary"] == "初步需求转为最终需求"


@pytest.mark.anyio
async def test_start_requirement_review_run_clears_current_final_requirement_and_latest_analysis(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return "# 主需求\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"

    class FakeQualityGate:
        result = "passed"
        testability_score = 90
        blocking_issues: list[str] = []

    class FakeAnalysisOutput:
        status = "completed"
        analysis_summary = "需求分析完成。"
        quality_gate = FakeQualityGate()
        preliminary_requirement_markdown = "# 主需求\n\n用户可以使用验证码登录。\n"

        def model_dump(self):
            return {
                "status": "completed",
                "analysis_summary": "需求分析完成。",
                "preliminary_requirement_markdown": self.preliminary_requirement_markdown,
                "applied_supplements": [],
                "modules": [],
                "clarification_questions": [],
                "conflicts": [],
                "quality_gate": {
                    "result": "passed",
                    "testability_score": 90,
                    "blocking_issues": [],
                    "warning_issues": [],
                    "passed_checks": ["主需求已分析"],
                },
                "next_actions": [],
            }

    async def fake_analyze_requirement(input_data):
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])
    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)
    finalize = document_service.finalize_requirement_analysis(
        "project-1",
        result["document"]["id"],
        RequirementAnalysisFinalizeIn(analysis_id=review["id"]),
        ACTOR,
    )

    task = document_service.start_requirement_review_run("project-1", result["document"]["id"], ACTOR)
    overview = document_service.get_document_overview("project-1", result["document"]["id"], ACTOR)
    latest = document_service.get_latest_requirement_analysis("project-1", result["document"]["id"], ACTOR)

    assert task["status"] == "queued"
    assert overview["document"]["current_version_id"] is None
    assert overview["stats"]["initial_requirement_status"] == "not_generated"
    assert overview["initial_markdown_content"] == ""
    assert latest["analysis"] is None

    with core_db.connect() as db:
        version_count = db.execute(
            "SELECT COUNT(*) AS count FROM source_document_versions WHERE document_id = ?",
            (result["document"]["id"],),
        ).fetchone()["count"]
        previous_version = db.execute(
            "SELECT id FROM source_document_versions WHERE id = ?",
            (finalize["version"]["id"],),
        ).fetchone()

    assert version_count == 1
    assert previous_version is not None


@pytest.mark.anyio
async def test_finalize_requirement_analysis_requires_confirmation_for_unresolved_items(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return "# 主需求\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"

    class FakeQualityGate:
        result = "warning"
        testability_score = 70
        blocking_issues: list[str] = []

    class FakeAnalysisOutput:
        status = "needs_clarification"
        analysis_summary = "存在待确认问题。"
        quality_gate = FakeQualityGate()
        preliminary_requirement_markdown = "# 主需求\n\n用户可以使用验证码登录。\n"

        def model_dump(self):
            return {
                "status": "needs_clarification",
                "analysis_summary": "存在待确认问题。",
                "preliminary_requirement_markdown": self.preliminary_requirement_markdown,
                "applied_supplements": [],
                "modules": [],
                "clarification_questions": [
                    {
                        "id": "Q-001",
                        "module_key": "login",
                        "module_name": "登录",
                        "question": "验证码有效期是多少？",
                        "impact": "无法设计边界用例。",
                        "dimension": "time_related",
                        "severity": "major",
                        "source_excerpt": "用户可以使用验证码登录。",
                    }
                ],
                "conflicts": [],
                "quality_gate": {
                    "result": "warning",
                    "testability_score": 70,
                    "blocking_issues": [],
                    "warning_issues": ["存在待确认问题"],
                    "passed_checks": [],
                },
                "next_actions": [],
            }

    async def fake_analyze_requirement(input_data):
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])
    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)

    with pytest.raises(HTTPException) as exc_info:
        document_service.finalize_requirement_analysis(
            "project-1",
            result["document"]["id"],
            RequirementAnalysisFinalizeIn(analysis_id=review["id"]),
            ACTOR,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "REQUIREMENT_ANALYSIS_CONFIRM_REQUIRED"

    finalize = document_service.finalize_requirement_analysis(
        "project-1",
        result["document"]["id"],
        RequirementAnalysisFinalizeIn(analysis_id=review["id"], confirm_unresolved=True),
        ACTOR,
    )
    assert finalize["version"]["version_no"] == 1

    repeated = document_service.finalize_requirement_analysis(
        "project-1",
        result["document"]["id"],
        RequirementAnalysisFinalizeIn(analysis_id=review["id"], confirm_unresolved=True),
        ACTOR,
    )
    assert repeated["version"]["id"] == finalize["version"]["id"]

    with core_db.connect() as db:
        version_count = db.execute(
            "SELECT COUNT(*) AS count FROM source_document_versions WHERE document_id = ?",
            (result["document"]["id"],),
        ).fetchone()["count"]
    assert version_count == 1


@pytest.mark.anyio
async def test_finalize_requirement_analysis_allows_quality_warning_without_unresolved_items(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return "# 主需求\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"

    class FakeQualityGate:
        result = "warning"
        testability_score = 70
        blocking_issues: list[str] = []

    class FakeAnalysisOutput:
        status = "completed"
        analysis_summary = "存在质量警告，但没有待确认问题。"
        quality_gate = FakeQualityGate()
        preliminary_requirement_markdown = "# 主需求\n\n用户可以使用验证码登录。\n"

        def model_dump(self):
            return {
                "status": "completed",
                "analysis_summary": "存在质量警告，但没有待确认问题。",
                "preliminary_requirement_markdown": self.preliminary_requirement_markdown,
                "applied_supplements": [],
                "modules": [],
                "clarification_questions": [],
                "conflicts": [],
                "quality_gate": {
                    "result": "warning",
                    "testability_score": 70,
                    "blocking_issues": [],
                    "warning_issues": ["存在质量警告"],
                    "passed_checks": [],
                },
                "next_actions": [],
            }

    async def fake_analyze_requirement(input_data):
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])
    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)

    finalize = document_service.finalize_requirement_analysis(
        "project-1",
        result["document"]["id"],
        RequirementAnalysisFinalizeIn(analysis_id=review["id"]),
        ACTOR,
    )

    assert finalize["version"]["version_no"] == 1
    assert finalize["analysis"]["finalized_version_id"] == finalize["version"]["id"]


@pytest.mark.anyio
async def test_clarification_answer_recommended_option_updates_preliminary_requirement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return "# 主需求\n\n## 登录\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"

    class FakeQualityGate:
        result = "warning"
        testability_score = 70
        blocking_issues: list[str] = []

    class FakeAnalysisOutput:
        status = "needs_clarification"
        analysis_summary = "存在待确认问题。"
        quality_gate = FakeQualityGate()
        preliminary_requirement_markdown = "# 主需求\n\n## 登录\n\n用户可以使用验证码登录。\n"

        def model_dump(self):
            return {
                "status": "needs_clarification",
                "analysis_summary": "存在待确认问题。",
                "preliminary_requirement_markdown": self.preliminary_requirement_markdown,
                "applied_supplements": [],
                "modules": [],
                "clarification_questions": [
                    {
                        "id": "Q-001",
                        "module_key": "login",
                        "module_name": "登录",
                        "question": "验证码有效期是多少？",
                        "impact": "无法设计边界用例。",
                        "dimension": "time_related",
                        "severity": "major",
                        "source_excerpt": "用户可以使用验证码登录。",
                        "recommended_options": [
                            {
                                "id": "option-a",
                                "label": "5 分钟有效",
                                "answer_markdown": "验证码有效期为 5 分钟。",
                                "rationale": "常见安全规则。",
                                "confidence": "medium",
                            },
                            {
                                "id": "option-b",
                                "label": "10 分钟有效",
                                "answer_markdown": "验证码有效期为 10 分钟。",
                                "rationale": "兼顾操作时间。",
                                "confidence": "low",
                            },
                        ],
                    }
                ],
                "conflicts": [],
                "quality_gate": {
                    "result": "warning",
                    "testability_score": 70,
                    "blocking_issues": [],
                    "warning_issues": ["存在待确认问题"],
                    "passed_checks": [],
                },
                "next_actions": [],
            }

    async def fake_analyze_requirement(input_data):
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])
    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)

    applied = document_service.save_requirement_clarification_answer(
        "project-1",
        result["document"]["id"],
        review["id"],
        RequirementClarificationAnswerIn(
            question_id="Q-001",
            answer_type="recommended_option",
            selected_option_id="option-a",
        ),
        ACTOR,
    )

    markdown = applied["analysis"]["output"]["preliminary_requirement_markdown"]
    assert applied["answer"]["apply_status"] == "applied"
    assert "验证码有效期为 5 分钟。" in markdown
    assert "clarification-answer:Q-001:start" not in markdown
    assert "人工确认" not in markdown
    assert "## 登录" in markdown
    assert applied["analysis"]["output"]["clarification_questions"][0]["answer"]["selected_option_id"] == "option-a"

    finalize = document_service.finalize_requirement_analysis(
        "project-1",
        result["document"]["id"],
        RequirementAnalysisFinalizeIn(analysis_id=review["id"], confirm_unresolved=True),
        ACTOR,
    )
    assert "验证码有效期为 5 分钟。" in finalize["markdown_content"]


@pytest.mark.anyio
async def test_clarification_answer_custom_replaces_previous_answer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return "# 主需求\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"

    class FakeQualityGate:
        result = "warning"
        testability_score = 70
        blocking_issues: list[str] = []

    class FakeAnalysisOutput:
        status = "needs_clarification"
        analysis_summary = "存在待确认问题。"
        quality_gate = FakeQualityGate()
        preliminary_requirement_markdown = "# 主需求\n\n用户可以使用验证码登录。\n"

        def model_dump(self):
            return {
                "status": "needs_clarification",
                "analysis_summary": "存在待确认问题。",
                "preliminary_requirement_markdown": self.preliminary_requirement_markdown,
                "applied_supplements": [],
                "modules": [],
                "clarification_questions": [
                    {
                        "id": "Q-001",
                        "module_key": "login",
                        "module_name": "登录",
                        "question": "验证码有效期是多少？",
                        "impact": "无法设计边界用例。",
                        "dimension": "time_related",
                        "severity": "major",
                        "source_excerpt": "用户可以使用验证码登录。",
                        "recommended_options": [
                            {
                                "id": "option-a",
                                "label": "5 分钟有效",
                                "answer_markdown": "验证码有效期为 5 分钟。",
                                "rationale": "",
                                "confidence": "medium",
                            }
                        ],
                    }
                ],
                "conflicts": [],
                "quality_gate": {
                    "result": "warning",
                    "testability_score": 70,
                    "blocking_issues": [],
                    "warning_issues": [],
                    "passed_checks": [],
                },
                "next_actions": [],
            }

    async def fake_analyze_requirement(input_data):
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])
    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)

    document_service.save_requirement_clarification_answer(
        "project-1",
        result["document"]["id"],
        review["id"],
        RequirementClarificationAnswerIn(
            question_id="Q-001",
            answer_type="recommended_option",
            selected_option_id="option-a",
        ),
        ACTOR,
    )
    replaced = document_service.save_requirement_clarification_answer(
        "project-1",
        result["document"]["id"],
        review["id"],
        RequirementClarificationAnswerIn(
            question_id="Q-001",
            answer_type="custom",
            custom_answer="验证码有效期为 3 分钟，过期后需重新获取。",
        ),
        ACTOR,
    )

    markdown = replaced["analysis"]["output"]["preliminary_requirement_markdown"]
    assert "验证码有效期为 3 分钟" in markdown
    assert "验证码有效期为 5 分钟" not in markdown
    assert markdown.count("验证码有效期为 3 分钟") == 1
    assert "clarification-answer:Q-001:start" not in markdown


@pytest.mark.anyio
async def test_clarification_answer_defer_does_not_update_preliminary_requirement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return "# 主需求\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"

    class FakeQualityGate:
        result = "warning"
        testability_score = 70
        blocking_issues: list[str] = []

    class FakeAnalysisOutput:
        status = "needs_clarification"
        analysis_summary = "存在待确认问题。"
        quality_gate = FakeQualityGate()
        preliminary_requirement_markdown = "# 主需求\n\n用户可以使用验证码登录。\n"

        def model_dump(self):
            return {
                "status": "needs_clarification",
                "analysis_summary": "存在待确认问题。",
                "preliminary_requirement_markdown": self.preliminary_requirement_markdown,
                "applied_supplements": [],
                "modules": [],
                "clarification_questions": [
                    {
                        "id": "Q-001",
                        "module_key": "login",
                        "module_name": "登录",
                        "question": "验证码有效期是多少？",
                        "impact": "无法设计边界用例。",
                        "dimension": "time_related",
                        "severity": "major",
                        "source_excerpt": "用户可以使用验证码登录。",
                    }
                ],
                "conflicts": [],
                "quality_gate": {
                    "result": "warning",
                    "testability_score": 70,
                    "blocking_issues": [],
                    "warning_issues": [],
                    "passed_checks": [],
                },
                "next_actions": [],
            }

    async def fake_analyze_requirement(input_data):
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])
    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)

    deferred = document_service.save_requirement_clarification_answer(
        "project-1",
        result["document"]["id"],
        review["id"],
        RequirementClarificationAnswerIn(question_id="Q-001", answer_type="defer"),
        ACTOR,
    )

    assert deferred["answer"]["apply_status"] == "not_applicable"
    assert (
        deferred["analysis"]["output"]["preliminary_requirement_markdown"].strip()
        == FakeAnalysisOutput.preliminary_requirement_markdown.strip()
    )
    assert "clarification-answer:Q-001:start" not in deferred["analysis"]["output"]["preliminary_requirement_markdown"]


@pytest.mark.anyio
async def test_clarification_answer_defer_removes_previous_answer_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return "# 主需求\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"

    class FakeQualityGate:
        result = "warning"
        testability_score = 70
        blocking_issues: list[str] = []

    class FakeAnalysisOutput:
        status = "needs_clarification"
        analysis_summary = "存在待确认问题。"
        quality_gate = FakeQualityGate()
        preliminary_requirement_markdown = "# 主需求\n\n用户可以使用验证码登录。\n"

        def model_dump(self):
            return {
                "status": "needs_clarification",
                "analysis_summary": "存在待确认问题。",
                "preliminary_requirement_markdown": self.preliminary_requirement_markdown,
                "applied_supplements": [],
                "modules": [],
                "clarification_questions": [
                    {
                        "id": "Q-001",
                        "module_key": "login",
                        "module_name": "登录",
                        "question": "验证码有效期是多少？",
                        "impact": "无法设计边界用例。",
                        "dimension": "time_related",
                        "severity": "major",
                        "source_excerpt": "用户可以使用验证码登录。",
                        "recommended_options": [
                            {
                                "id": "option-a",
                                "label": "5 分钟有效",
                                "answer_markdown": "验证码有效期为 5 分钟。",
                                "rationale": "",
                                "confidence": "medium",
                            }
                        ],
                    }
                ],
                "conflicts": [],
                "quality_gate": {
                    "result": "warning",
                    "testability_score": 70,
                    "blocking_issues": [],
                    "warning_issues": [],
                    "passed_checks": [],
                },
                "next_actions": [],
            }

    async def fake_analyze_requirement(input_data):
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])
    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)

    applied = document_service.save_requirement_clarification_answer(
        "project-1",
        result["document"]["id"],
        review["id"],
        RequirementClarificationAnswerIn(
            question_id="Q-001",
            answer_type="recommended_option",
            selected_option_id="option-a",
        ),
        ACTOR,
    )
    assert "验证码有效期为 5 分钟。" in applied["analysis"]["output"]["preliminary_requirement_markdown"]

    deferred = document_service.save_requirement_clarification_answer(
        "project-1",
        result["document"]["id"],
        review["id"],
        RequirementClarificationAnswerIn(question_id="Q-001", answer_type="defer"),
        ACTOR,
    )

    markdown = deferred["analysis"]["output"]["preliminary_requirement_markdown"]
    assert deferred["answer"]["apply_status"] == "not_applicable"
    assert "验证码有效期为 5 分钟。" not in markdown
    assert "clarification-answer:Q-001:start" not in markdown
    assert "### 验证码规则" not in markdown
    assert markdown.strip() == FakeAnalysisOutput.preliminary_requirement_markdown.strip()


@pytest.mark.anyio
async def test_clarification_answer_rejects_finalized_analysis(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return "# 主需求\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"

    class FakeQualityGate:
        result = "warning"
        testability_score = 70
        blocking_issues: list[str] = []

    class FakeAnalysisOutput:
        status = "needs_clarification"
        analysis_summary = "存在待确认问题。"
        quality_gate = FakeQualityGate()
        preliminary_requirement_markdown = "# 主需求\n\n用户可以使用验证码登录。\n"

        def model_dump(self):
            return {
                "status": "needs_clarification",
                "analysis_summary": "存在待确认问题。",
                "preliminary_requirement_markdown": self.preliminary_requirement_markdown,
                "applied_supplements": [],
                "modules": [],
                "clarification_questions": [
                    {
                        "id": "Q-001",
                        "module_key": "login",
                        "module_name": "登录",
                        "question": "验证码有效期是多少？",
                        "impact": "无法设计边界用例。",
                        "dimension": "time_related",
                        "severity": "major",
                        "source_excerpt": "用户可以使用验证码登录。",
                    }
                ],
                "conflicts": [],
                "quality_gate": {
                    "result": "warning",
                    "testability_score": 70,
                    "blocking_issues": [],
                    "warning_issues": [],
                    "passed_checks": [],
                },
                "next_actions": [],
            }

    async def fake_analyze_requirement(input_data):
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])
    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)
    document_service.finalize_requirement_analysis(
        "project-1",
        result["document"]["id"],
        RequirementAnalysisFinalizeIn(analysis_id=review["id"], confirm_unresolved=True),
        ACTOR,
    )

    with pytest.raises(HTTPException) as exc_info:
        document_service.save_requirement_clarification_answer(
            "project-1",
            result["document"]["id"],
            review["id"],
            RequirementClarificationAnswerIn(
                question_id="Q-001",
                answer_type="custom",
                custom_answer="验证码有效期为 3 分钟。",
            ),
            ACTOR,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "REQUIREMENT_ANALYSIS_FINALIZED"


@pytest.mark.anyio
async def test_finalize_requirement_analysis_rejects_changed_primary_file(
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
        analysis_summary = "需求分析完成。"
        quality_gate = FakeQualityGate()
        preliminary_requirement_markdown = "# 主需求\n\n标准内容。\n"

        def model_dump(self):
            return {
                "status": "completed",
                "analysis_summary": "需求分析完成。",
                "preliminary_requirement_markdown": self.preliminary_requirement_markdown,
                "applied_supplements": [],
                "modules": [],
                "clarification_questions": [],
                "conflicts": [],
                "quality_gate": {
                    "result": "passed",
                    "testability_score": 90,
                    "blocking_issues": [],
                    "warning_issues": [],
                    "passed_checks": [],
                },
                "next_actions": [],
            }

    async def fake_analyze_requirement(input_data):
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main"), _upload_file("other.md", "# other")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_ids = [item["id"] for item in result["files"]]
    other_mapping_id = next(item["id"] for item in result["files"] if item["original_filename"] == "other.md")
    await document_service.convert_pending_file_mappings(mapping_ids)
    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)

    document_service.set_primary_requirement_file("project-1", result["document"]["id"], other_mapping_id, ACTOR)

    with pytest.raises(HTTPException) as exc_info:
        document_service.finalize_requirement_analysis(
            "project-1",
            result["document"]["id"],
            RequirementAnalysisFinalizeIn(analysis_id=review["id"]),
            ACTOR,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "REQUIREMENT_ANALYSIS_PRIMARY_CHANGED"


@pytest.mark.anyio
async def test_requirement_review_run_lifecycle_creates_task_and_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return "# 主需求\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"

    class FakeQualityGate:
        result = "passed"
        testability_score = 90
        blocking_issues: list[str] = []

    class FakeAnalysisOutput:
        status = "completed"
        analysis_summary = "需求分析完成。"
        quality_gate = FakeQualityGate()
        preliminary_requirement_markdown = "# 主需求\n\n用户可以使用验证码登录。\n"

        def model_dump(self):
            return {
                "status": "completed",
                "analysis_summary": "需求分析完成。",
                "preliminary_requirement_markdown": self.preliminary_requirement_markdown,
                "applied_supplements": [],
                "modules": [],
                "clarification_questions": [],
                "conflicts": [],
                "quality_gate": {
                    "result": "passed",
                    "testability_score": 90,
                    "blocking_issues": [],
                    "warning_issues": [],
                    "passed_checks": ["主需求已分析"],
                },
                "next_actions": [],
            }

    async def fake_analyze_requirement(input_data):
        assert input_data.primary_filename == "main.md"
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])

    task = document_service.start_requirement_review_run("project-1", result["document"]["id"], ACTOR)

    assert task["source_type"] == "requirement_analysis_run"
    assert task["status"] == "queued"
    assert task["status_group"] == "running"

    await document_service.execute_requirement_review_run(task["source_id"], ACTOR)

    with core_db.connect() as db:
        run = db.execute("SELECT * FROM requirement_analysis_runs WHERE id = ?", (task["source_id"],)).fetchone()
        logs = db.execute(
            "SELECT log_type, object_type, task_id FROM operation_logs WHERE task_id = ? ORDER BY created_at ASC, id ASC",
            (task["source_id"],),
        ).fetchall()

    assert run["status"] == "completed"
    assert run["analysis_id"]
    assert any(row["log_type"] == "task" and row["object_type"] == "requirement_analysis_run" for row in logs)
    assert any(row["log_type"] == "agent" and row["object_type"] == "requirement_analysis" for row in logs)


@pytest.mark.anyio
async def test_failed_requirement_review_run_restores_previous_final_requirement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return "# 主需求\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"

    async def fake_analyze_requirement(input_data):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    document_id = result["document"]["id"]
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])

    version_path = tmp_path / "final.md"
    version_path.write_text("# 最终需求\n\n历史最终需求。", encoding="utf-8")
    with core_db.connect() as db:
        document_repo.create_version(
            db,
            version_id="docver-final",
            document_id=document_id,
            version_no=1,
            file_path=str(version_path),
            source_action="requirement_analysis_finalize",
            change_summary="初步需求转为最终需求",
            diff_summary="历史最终需求。",
            created_by=ACTOR["id"],
        )
        document_repo.update_current_version(db, document_id, "docver-final", "versioned")

    task = document_service.start_requirement_review_run("project-1", document_id, ACTOR)
    await document_service.execute_requirement_review_run(task["source_id"], ACTOR)

    with core_db.connect() as db:
        run = db.execute("SELECT * FROM requirement_analysis_runs WHERE id = ?", (task["source_id"],)).fetchone()
        document = db.execute("SELECT status, current_version_id FROM source_documents WHERE id = ?", (document_id,)).fetchone()
        failure_log = db.execute(
            """
            SELECT summary, failure_reason
            FROM operation_logs
            WHERE task_id = ? AND action = 'fail_requirement_analysis'
            """,
            (task["source_id"],),
        ).fetchone()

    assert run["status"] == "failed"
    assert run["summary"] == "需求分析失败。"
    assert "model unavailable" in run["failure_reason"]
    assert failure_log["summary"] == "需求分析失败。"
    assert "model unavailable" not in failure_log["summary"]
    assert "model unavailable" in failure_log["failure_reason"]
    assert document["status"] == "versioned"
    assert document["current_version_id"] == "docver-final"


@pytest.mark.anyio
async def test_stop_queued_requirement_review_run_cancels_and_cleans_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return "# 主需求\n\n用户可以使用验证码登录。\n", "已生成主需求标准 Markdown。"

    async def fake_analyze_requirement(input_data):
        raise AssertionError("queued stop should cancel before agent execution")

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.analyze_requirement_with_agent", fake_analyze_requirement)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    document_id = result["document"]["id"]
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])

    task = document_service.start_requirement_review_run("project-1", document_id, ACTOR)
    stopped = document_service.stop_requirement_analysis_run("project-1", document_id, task["source_id"], ACTOR)

    assert stopped["status"] == "cancelled"

    await document_service.execute_requirement_review_run(task["source_id"], ACTOR)

    run_dir = tmp_path / "data" / "projects" / "project-1" / "requirements" / document_id / "analysis_runs" / task["source_id"]
    with core_db.connect() as db:
        run = db.execute("SELECT * FROM requirement_analysis_runs WHERE id = ?", (task["source_id"],)).fetchone()
        analyses = db.execute(
            "SELECT COUNT(*) AS count FROM requirement_analyses WHERE document_id = ?",
            (document_id,),
        ).fetchone()

    assert run["status"] == "cancelled"
    assert run["summary"] == "用户已停止需求分析。"
    assert analyses["count"] == 0
    assert not run_dir.exists()

