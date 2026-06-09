import asyncio

import pytest


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from app.core import db as core_db
    from app.seed.init_db import init_db

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()


def _seed_project(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from app.core import db as core_db

    final_doc = tmp_path / "final.md"
    final_doc.write_text("# 登录\n用户可以使用账号密码登录。", encoding="utf-8")
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, status, description, created_by)
            VALUES ('project-1', '测试项目', 'active', '', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES ('doc-1', 'project-1', '最终需求', 'requirement', 'version-1', 'finalized', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_document_versions
              (id, document_id, version_no, markdown_content, file_path, source_action, created_by)
            VALUES ('version-1', 'doc-1', 1, '', ?, 'upload', 'u-admin')
            """,
            (str(final_doc),),
        )


def test_knowledge_query_persists_conversation_and_uses_history(monkeypatch, tmp_path) -> None:
    from app.schemas.knowledge import KnowledgeQueryOutput
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)
    captured_questions: list[str] = []
    captured_history_lengths: list[int] = []

    async def fake_run_knowledge_query(input_data):
        captured_questions.append(input_data.question)
        captured_history_lengths.append(len(input_data.conversation_history))
        return KnowledgeQueryOutput(
            answer=f"回答：{input_data.question}",
            used_requirement_versions=["version-1"],
            used_exploration_runs=[],
        )

    monkeypatch.setattr(service.knowledge_query_service, "run_knowledge_query", fake_run_knowledge_query)
    actor = {"id": "u-admin", "username": "admin", "nickname": "平台管理员"}

    async def run_queries():
        first_result = await service.query_project_knowledge(
            "project-1",
            actor,
            service.KnowledgeQueryRequest(question="登录规则是什么？", include_explorations=False),
        )
        second_result = await service.query_project_knowledge(
            "project-1",
            actor,
            service.KnowledgeQueryRequest(
                question="这个模块还要补哪些测试？",
                include_explorations=False,
                conversation_id=first_result["conversation"]["id"],
            ),
        )
        return first_result, second_result

    first, second = asyncio.run(run_queries())
    conversation_id = first["conversation"]["id"]

    detail = service.get_project_knowledge_conversation("project-1", conversation_id, actor)
    assert first["conversation"]["title"] == "登录规则是什么？"
    assert second["conversation"]["id"] == conversation_id
    assert captured_questions == ["登录规则是什么？", "这个模块还要补哪些测试？"]
    assert captured_history_lengths == [0, 2]
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant", "user", "assistant"]

    delete_result = service.delete_project_knowledge_conversation("project-1", conversation_id, actor)
    assert delete_result == {"deleted": True}
    assert service.list_project_knowledge_conversations("project-1", actor) == []
