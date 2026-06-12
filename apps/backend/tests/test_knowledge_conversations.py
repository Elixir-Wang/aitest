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


async def _collect_async_events(iterator):
    return [event async for event in iterator]


def test_knowledge_query_persists_conversation_and_uses_history(monkeypatch, tmp_path) -> None:
    from app.schemas.knowledge import KnowledgeQueryOutput
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)
    captured_questions: list[str] = []
    captured_history_lengths: list[int] = []

    async def fake_run_knowledge_chat(input_data, search_project_knowledge):
        captured_questions.append(input_data.question)
        captured_history_lengths.append(len(input_data.conversation_history))
        output = await search_project_knowledge(input_data.question)
        return KnowledgeQueryOutput(
            answer=f"回答：{input_data.question}",
            source_refs=output.source_refs,
            used_requirement_versions=output.used_requirement_versions,
            used_exploration_runs=output.used_exploration_runs,
            knowledge_queried=output.knowledge_queried,
        )

    async def fake_run_knowledge_query(input_data):
        return KnowledgeQueryOutput(
            answer=f"检索：{input_data.question}",
            used_requirement_versions=["version-1"],
            used_exploration_runs=[],
            knowledge_queried=True,
        )

    monkeypatch.setattr(service.knowledge_chat_service, "run_knowledge_chat", fake_run_knowledge_chat)
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
    assert first["knowledge_queried"] is True
    assert second["knowledge_queried"] is True
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant", "user", "assistant"]

    delete_result = service.delete_project_knowledge_conversation("project-1", conversation_id, actor)
    assert delete_result == {"deleted": True}
    assert service.list_project_knowledge_conversations("project-1", actor) == []


def test_knowledge_chat_can_answer_without_querying_project_sources(monkeypatch, tmp_path) -> None:
    from app.schemas.knowledge import KnowledgeQueryOutput
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)
    query_called = False

    async def fake_run_knowledge_query(_input_data):
        nonlocal query_called
        query_called = True
        raise AssertionError("普通对话不应查询项目知识库。")

    async def fake_run_knowledge_chat(input_data, search_project_knowledge):
        assert input_data.question == "你好"
        assert input_data.source_documents == []
        assert input_data.explorations == []
        return KnowledgeQueryOutput(answer="你好，我是项目知识库 AI。", knowledge_queried=False)

    monkeypatch.setattr(service.knowledge_query_service, "run_knowledge_query", fake_run_knowledge_query)
    monkeypatch.setattr(service.knowledge_chat_service, "run_knowledge_chat", fake_run_knowledge_chat)
    actor = {"id": "u-admin", "username": "admin", "nickname": "平台管理员"}

    result = asyncio.run(
        service.query_project_knowledge(
            "project-1",
            actor,
            service.KnowledgeQueryRequest(question="你好", include_explorations=False),
        )
    )

    assert query_called is False
    assert result["answer"] == "你好，我是项目知识库 AI。"
    assert result["knowledge_queried"] is False
    assert result["source_refs"] == []
    assert result["used_requirement_versions"] == []
    assert result["used_exploration_runs"] == []


def test_all_project_knowledge_query_collects_active_project_sources(monkeypatch, tmp_path) -> None:
    from app.core import db as core_db
    from app.schemas.knowledge import KnowledgeQueryOutput, KnowledgeSourceRef
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)
    order_doc = tmp_path / "order.md"
    order_doc.write_text("# 订单\n用户可以创建订单。", encoding="utf-8")
    archived_doc = tmp_path / "archived.md"
    archived_doc.write_text("# 归档\n归档项目不应参与查询。", encoding="utf-8")
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, status, description, created_by)
            VALUES ('project-2', '订单项目', 'active', '', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES ('doc-2', 'project-2', '订单需求', 'requirement', 'version-2', 'finalized', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_document_versions
              (id, document_id, version_no, markdown_content, file_path, source_action, created_by)
            VALUES ('version-2', 'doc-2', 1, '', ?, 'upload', 'u-admin')
            """,
            (str(order_doc),),
        )
        db.execute(
            """
            INSERT INTO projects (id, name, status, description, created_by)
            VALUES ('project-archived', '归档项目', 'archived', '', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES ('doc-archived', 'project-archived', '归档需求', 'requirement', 'version-archived', 'finalized', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_document_versions
              (id, document_id, version_no, markdown_content, file_path, source_action, created_by)
            VALUES ('version-archived', 'doc-archived', 1, '', ?, 'upload', 'u-admin')
            """,
            (str(archived_doc),),
        )

    captured_project_names: list[list[str]] = []

    async def fake_stream_knowledge_chat(input_data, search_project_knowledge, **_kwargs):
        assert input_data.project_name == "全部项目"
        output = await search_project_knowledge(input_data.question)
        yield {"type": "message_delta", "delta": output.answer}
        yield {"type": "metadata", "output": output}

    async def fake_run_knowledge_query(input_data):
        captured_project_names.append([doc.project_name for doc in input_data.source_documents])
        return KnowledgeQueryOutput(
            answer="已查询全部项目。",
            source_refs=[
                KnowledgeSourceRef(
                    source_type="requirement",
                    source_id=doc.version_id,
                    source_title=doc.document_name,
                    project_id=doc.project_id,
                    project_name=doc.project_name,
                )
                for doc in input_data.source_documents
            ],
            used_requirement_versions=[doc.version_id for doc in input_data.source_documents],
            knowledge_queried=True,
        )

    monkeypatch.setattr(service.knowledge_chat_service, "stream_knowledge_chat", fake_stream_knowledge_chat)
    monkeypatch.setattr(service.knowledge_query_service, "run_knowledge_query", fake_run_knowledge_query)
    actor = {
        "id": "u-admin",
        "username": "admin",
        "nickname": "平台管理员",
        "role": "admin",
        "project_scope": "全部项目",
    }

    events = asyncio.run(
        _collect_async_events(
            service.stream_all_project_knowledge_query(
                actor,
                service.KnowledgeQueryRequest(question="有哪些需求？", include_explorations=False),
            )
        )
    )

    assert captured_project_names == [["测试项目", "订单项目"]]
    assert [event["type"] for event in events] == ["message_delta", "metadata", "done"]
    result = events[1]["result"]
    assert result["conversation"] is None
    assert result["messages"] == []
    assert result["answer"] == "已查询全部项目。"
    assert [ref["project_name"] for ref in result["source_refs"]] == ["测试项目", "订单项目"]
    assert result["used_requirement_versions"] == ["version-1", "version-2"]
    assert result["knowledge_queried"] is True


def test_all_project_knowledge_query_tolerates_partial_missing_files(monkeypatch, tmp_path) -> None:
    from app.core import db as core_db
    from app.schemas.knowledge import KnowledgeQueryOutput
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)
    valid_doc = tmp_path / "valid.md"
    valid_doc.write_text("# 有效需求\n有效项目可以查询。", encoding="utf-8")
    missing_doc = tmp_path / "missing.md"
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, status, description, created_by)
            VALUES ('project-missing', '缺文件项目', 'active', '', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES ('doc-missing', 'project-missing', '缺文件需求', 'requirement', 'version-missing', 'finalized', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_document_versions
              (id, document_id, version_no, markdown_content, file_path, source_action, created_by)
            VALUES ('version-missing', 'doc-missing', 1, '', ?, 'upload', 'u-admin')
            """,
            (str(missing_doc),),
        )
        db.execute(
            """
            INSERT INTO projects (id, name, status, description, created_by)
            VALUES ('project-valid', '有效项目', 'active', '', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES ('doc-valid', 'project-valid', '有效需求', 'requirement', 'version-valid', 'finalized', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_document_versions
              (id, document_id, version_no, markdown_content, file_path, source_action, created_by)
            VALUES ('version-valid', 'doc-valid', 1, '', ?, 'upload', 'u-admin')
            """,
            (str(valid_doc),),
        )

    captured_project_names: list[list[str]] = []

    async def fake_stream_knowledge_chat(input_data, search_project_knowledge, **_kwargs):
        output = await search_project_knowledge(input_data.question)
        yield {"type": "metadata", "output": output}

    async def fake_run_knowledge_query(input_data):
        captured_project_names.append([doc.project_name for doc in input_data.source_documents])
        return KnowledgeQueryOutput(
            answer="已使用可用项目来源回答。",
            used_requirement_versions=[doc.version_id for doc in input_data.source_documents],
            knowledge_queried=True,
        )

    monkeypatch.setattr(service.knowledge_chat_service, "stream_knowledge_chat", fake_stream_knowledge_chat)
    monkeypatch.setattr(service.knowledge_query_service, "run_knowledge_query", fake_run_knowledge_query)
    actor = {
        "id": "u-admin",
        "username": "admin",
        "nickname": "平台管理员",
        "role": "admin",
        "project_scope": "全部项目",
    }

    events = asyncio.run(
        _collect_async_events(
            service.stream_all_project_knowledge_query(
                actor,
                service.KnowledgeQueryRequest(question="有哪些可用需求？", include_explorations=False),
            )
        )
    )

    assert captured_project_names == [["测试项目", "有效项目"]]
    result = events[0]["result"]
    assert result["answer"] == "已使用可用项目来源回答。"
    assert "无法查询项目知识库" not in result["answer"]
    assert result["conversation"] is None
    assert result["used_requirement_versions"] == ["version-1", "version-valid"]
    assert events[-1] == {"type": "done"}


def test_all_project_knowledge_query_forwards_visible_thinking(monkeypatch, tmp_path) -> None:
    from app.schemas.knowledge import KnowledgeQueryOutput
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)

    captured_show_thinking: list[bool] = []

    async def fake_stream_knowledge_chat(input_data, _search_project_knowledge, *, show_thinking=False):
        assert input_data.project_name == "全部项目"
        captured_show_thinking.append(show_thinking)
        yield {"type": "thinking_delta", "delta": "先判断是否需要查询。"}
        yield {"type": "metadata", "output": KnowledgeQueryOutput(answer="不需要查询。", knowledge_queried=False)}

    monkeypatch.setattr(service.knowledge_chat_service, "stream_knowledge_chat", fake_stream_knowledge_chat)
    actor = {
        "id": "u-admin",
        "username": "admin",
        "nickname": "平台管理员",
        "role": "admin",
        "project_scope": "全部项目",
    }

    events = asyncio.run(
        _collect_async_events(
            service.stream_all_project_knowledge_query(
                actor,
                service.KnowledgeQueryRequest(question="你好", show_thinking=True),
            )
        )
    )

    assert captured_show_thinking == [True]
    assert events[0] == {"type": "thinking_delta", "delta": "先判断是否需要查询。"}
    assert events[1]["type"] == "metadata"
    assert events[1]["result"]["answer"] == "不需要查询。"
