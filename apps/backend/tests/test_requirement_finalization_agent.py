import asyncio
from types import SimpleNamespace

from app.agents.model_selection import ModelSelection


def _model_selection(provider: str = "openai", model: str = "gpt-4o-mini") -> ModelSelection:
    return ModelSelection(provider=provider, model=model, base_url=None, api_key="test-key")


def test_requirement_finalization_input_excludes_no_op_bucket():
    from app.agents.requirement_finalization.schemas import RequirementFinalizationInput

    assert "no_op_clarifications" not in RequirementFinalizationInput.model_fields


def test_requirement_finalization_reuses_requirement_analysis_model(monkeypatch):
    from app.agents.requirement_finalization import service
    from app.agents.requirement_finalization.schemas import RequirementFinalizationInput

    seen = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            seen["payload"] = payload
            return {
                "structured_response": {
                    "final_requirement_markdown": "# 最终需求\n",
                    "change_summary": "已生成最终需求",
                }
            }

    def fake_resolve_model_selection(capability_id):
        seen["capability_id"] = capability_id
        return _model_selection()

    monkeypatch.setattr(service, "resolve_model_selection", fake_resolve_model_selection)
    monkeypatch.setattr(service, "build_agent_model", lambda selection, *, extra_body=None: "model")
    monkeypatch.setattr(service, "requirement_finalization_agent", lambda model: FakeAgent())

    result = asyncio.run(
        service.run_requirement_finalization(
            RequirementFinalizationInput(
                document_name="需求",
                standard_markdown="# 标准需求\n",
                preliminary_markdown="# 初步需求\n",
                primary_document={"filename": "main.md", "markdown_content": "# 标准需求\n"},
            )
        )
    )

    assert seen["capability_id"] == "requirement_analysis"
    assert result.final_requirement_markdown == "# 最终需求\n"


def test_requirement_finalization_agent_uses_schema_response_format(monkeypatch):
    from langchain.agents.structured_output import ToolStrategy

    from app.agents.requirement_finalization import agent
    from app.agents.requirement_finalization.schemas import RequirementFinalizationOutput

    seen = {}

    def fake_create_agent(**kwargs):
        seen.update(kwargs)
        return object()

    monkeypatch.setattr(agent, "create_agent", fake_create_agent)

    agent.requirement_finalization_agent("model", load_references=False)

    assert seen["response_format"] is RequirementFinalizationOutput
    assert not isinstance(seen["response_format"], ToolStrategy)


def test_requirement_finalization_disables_thinking_for_reasoning_models(monkeypatch):
    from app.agents.requirement_finalization import service
    from app.agents.requirement_finalization.schemas import RequirementFinalizationInput

    seen = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            return {
                "structured_response": {
                    "final_requirement_markdown": "# 最终需求\n",
                    "change_summary": "已生成最终需求",
                }
            }

    def fake_build_agent_model(selection, *, extra_body=None):
        seen["extra_body"] = extra_body
        return "model"

    monkeypatch.setattr(
        service,
        "resolve_model_selection",
        lambda capability_id: _model_selection(provider="minimax", model="MiniMax-M1"),
    )
    monkeypatch.setattr(service, "build_agent_model", fake_build_agent_model)
    monkeypatch.setattr(service, "requirement_finalization_agent", lambda model: FakeAgent())

    result = asyncio.run(
        service.run_requirement_finalization(
            RequirementFinalizationInput(
                document_name="需求",
                standard_markdown="# 标准需求\n",
                preliminary_markdown="# 初步需求\n",
                primary_document={"filename": "main.md", "markdown_content": "# 标准需求\n"},
            )
        )
    )

    assert result.final_requirement_markdown == "# 最终需求\n"
    assert seen["extra_body"] == {"thinking": {"type": "disabled"}}


def test_finalize_requirement_analysis_records_finalization_task(monkeypatch, tmp_path):
    from app.core import db as core_db
    from app.core import storage as core_storage
    from app.seed.init_db import init_db
    from app.schemas.document import RequirementAnalysisFinalizeIn
    from app.services.document import service as document_service

    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(core_storage, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    init_db()

    standard_path = tmp_path / "standard.md"
    standard_path.write_text("# 标准需求\n", encoding="utf-8")

    with core_db.connect() as db:
        db.execute("INSERT INTO projects (id, name, status, description) VALUES ('project-1', '测试项目', 'active', '')")
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
            VALUES ('doc-1', 'project-1', '登录需求', 'PRD', 'pending_review', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_document_file_mappings
              (id, document_id, source_file_path, original_filename, file_format, conversion_status,
               markdown_file_path, file_role, created_by)
            VALUES
              ('file-1', 'doc-1', 'uploads/login.docx', 'login.docx', 'docx', 'success', ?, 'primary', 'u-admin')
            """,
            (str(standard_path),),
        )
        db.execute(
            """
            INSERT INTO requirement_analyses
              (id, project_id, document_id, primary_mapping_id, status, analysis_summary,
               output_json, quality_result, draft_content_hash, created_by)
            VALUES
              ('analysis-1', 'project-1', 'doc-1', 'file-1', 'completed', '分析完成',
               '{"understanding_markdown":"# 初步需求\\n","clarification_items":[]}',
               'passed', 'hash-1', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO requirement_analysis_runs
              (id, project_id, document_id, primary_mapping_id, analysis_id, status, summary, created_by)
            VALUES
              ('analysis-run-1', 'project-1', 'doc-1', 'file-1', 'analysis-1', 'completed', '分析完成', 'u-admin')
            """
        )

    async def fake_run_requirement_finalization(_input_data):
        with core_db.connect() as db:
            running_task = db.execute("SELECT status FROM requirement_finalization_runs").fetchone()
            assert running_task["status"] == "running"
        return SimpleNamespace(final_requirement_markdown="# 最终需求\n", change_summary="已生成最终需求")

    monkeypatch.setattr(document_service, "run_requirement_finalization", fake_run_requirement_finalization)

    actor = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}
    result = asyncio.run(
        document_service.finalize_requirement_analysis(
            "project-1",
            "doc-1",
            RequirementAnalysisFinalizeIn(analysis_id="analysis-1"),
            actor,
        )
    )

    assert result["markdown_content"] == "# 最终需求\n"
    with core_db.connect() as db:
        task = db.execute("SELECT status, summary, failure_reason FROM requirement_finalization_runs").fetchone()
    assert task["status"] == "completed"
    assert task["summary"] == "已生成最终需求"
    assert task["failure_reason"] == ""
