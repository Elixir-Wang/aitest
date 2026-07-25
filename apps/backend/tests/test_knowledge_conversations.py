import asyncio
import io
from pathlib import Path

import pytest
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Path:
    from app.core import db as core_db
    from app.core import storage
    from app.seed.init_db import init_db

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    init_db()
    return data_dir


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


def _upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename, headers=Headers({}))


def test_knowledge_query_persists_conversation_and_uses_deepagents_thread(monkeypatch, tmp_path) -> None:
    from app.schemas.knowledge import KnowledgeQueryOutput
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)
    captured_questions: list[str] = []
    captured_thread_ids: list[str] = []

    async def fake_run_knowledge_agent(input_data, *, thread_id=None):
        captured_questions.append(input_data.question)
        captured_thread_ids.append(thread_id)
        return KnowledgeQueryOutput(
            answer=f"检索：{input_data.question}",
            used_requirement_versions=["version-1"],
            knowledge_queried=True,
        )

    monkeypatch.setattr(service.knowledge_agent_service, "run_knowledge_agent", fake_run_knowledge_agent)
    actor = {"id": "u-admin", "username": "admin", "nickname": "平台管理员"}

    async def run_queries():
        first_result = await service.query_project_knowledge(
            "project-1",
            actor,
            service.KnowledgeQueryRequest(question="登录规则是什么？", ),
        )
        second_result = await service.query_project_knowledge(
            "project-1",
            actor,
            service.KnowledgeQueryRequest(
                question="这个模块还要补哪些测试？",
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
    assert captured_thread_ids == [conversation_id, conversation_id]
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant", "user", "assistant"]

    delete_result = service.delete_project_knowledge_conversation("project-1", conversation_id, actor)
    assert delete_result == {"deleted": True}
    assert service.list_project_knowledge_conversations("project-1", actor) == []


def test_knowledge_query_uses_agent_direct_reply_without_querying_sources(monkeypatch, tmp_path) -> None:
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)
    captured_questions: list[str] = []

    async def fake_run_knowledge_agent(input_data, *, thread_id=None):
        captured_questions.append(input_data.question)
        return service.KnowledgeQueryOutput(answer="你好，有什么可以帮你？", knowledge_queried=False)

    monkeypatch.setattr(service.knowledge_agent_service, "run_knowledge_agent", fake_run_knowledge_agent)
    actor = {"id": "u-admin", "username": "admin", "nickname": "平台管理员"}

    result = asyncio.run(
        service.query_project_knowledge(
            "project-1",
            actor,
            service.KnowledgeQueryRequest(question="你好", ),
        )
    )

    assert captured_questions == ["你好"]
    assert result["answer"] == "你好，有什么可以帮你？"
    assert "used_requirement_versions" not in result


def test_project_knowledge_query_collects_company_knowledge_by_default(monkeypatch, tmp_path) -> None:
    from app.services.knowledge import global_service, service
    from app.schemas.knowledge import KnowledgeQueryOutput

    data_dir = _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)
    base = global_service.create_base(name="测试规范", description="", actor={"id": "u-admin", "role": "admin"})
    uploaded = asyncio.run(
        global_service.upload_files_to_folder(
            base["id"],
            base["root_folder_id"],
            [_upload("login.md", b"# Login Test\n\nCover success and failure.")],
            actor={"id": "u-admin", "role": "admin"},
        )
    )
    company_file_id = uploaded["files"][0]["id"]
    stored_file = global_service.get_vault_file(base["id"], company_file_id, {"id": "u-admin", "role": "admin"})
    assert Path(stored_file["raw_path"]).is_relative_to(data_dir)
    assert Path(stored_file["markdown_path"]).is_relative_to(data_dir)
    captured_sources: list[list[str]] = []

    async def fake_run_knowledge_agent(input_data, *, thread_id=None):
        captured_sources.append([doc.source_type for doc in input_data.source_documents])
        return KnowledgeQueryOutput(
            answer="已结合项目需求和公司知识库。",
            used_requirement_versions=["version-1"],
            used_company_knowledge_files=[company_file_id],
            knowledge_queried=True,
        )

    monkeypatch.setattr(service.knowledge_agent_service, "run_knowledge_agent", fake_run_knowledge_agent)
    actor = {"id": "u-admin", "username": "admin", "nickname": "平台管理员", "role": "admin"}

    result = asyncio.run(
        service.query_project_knowledge(
            "project-1",
            actor,
            service.KnowledgeQueryRequest(question="登录测试怎么设计？"),
        )
    )

    assert captured_sources == [["requirement", "company_knowledge"]]
    assert result["answer"] == "已结合项目需求和公司知识库。"
    assert "used_requirement_versions" not in result


def test_project_knowledge_stream_timeout_persists_conversation(monkeypatch, tmp_path) -> None:
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)

    class ImmediateTimeout:
        async def __aenter__(self):
            raise TimeoutError

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(service.asyncio, "timeout", lambda _seconds: ImmediateTimeout())
    actor = {"id": "u-admin", "username": "admin", "nickname": "平台管理员"}

    events = asyncio.run(
        _collect_async_events(
            service.stream_project_knowledge_query(
                "project-1",
                actor,
                service.KnowledgeQueryRequest(question="这个需求有哪些规则？", include_requirements=False),
            )
        )
    )

    assert events == [
        {
            "type": "error",
            "code": "KNOWLEDGE_AGENT_TIMEOUT",
            "message": service.KNOWLEDGE_QUERY_TIMEOUT_MESSAGE,
            "result": events[0]["result"],
        }
    ]
    result = events[0]["result"]
    conversation_id = result["conversation"]["id"]
    assert result["answer"] == service.KNOWLEDGE_QUERY_TIMEOUT_MESSAGE
    assert [message["role"] for message in result["messages"]] == ["user", "assistant"]
    assert [message["content"] for message in result["messages"]] == [
        "这个需求有哪些规则？",
        service.KNOWLEDGE_QUERY_TIMEOUT_MESSAGE,
    ]

    detail = service.get_project_knowledge_conversation("project-1", conversation_id, actor)
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == service.KNOWLEDGE_QUERY_TIMEOUT_MESSAGE


def test_all_project_knowledge_query_collects_active_project_sources(monkeypatch, tmp_path) -> None:
    from app.core import db as core_db
    from app.schemas.knowledge import KnowledgeQueryOutput
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

    async def fake_stream_knowledge_agent(input_data, **_kwargs):
        captured_project_names.append([doc.project_name for doc in input_data.source_documents])
        references = "\n".join(
            f"- [需求] {doc.project_name} / {doc.document_name}" for doc in input_data.source_documents
        )
        output = KnowledgeQueryOutput(
            answer=f"已查询全部项目。\n\n参考来源：\n{references}",
            used_requirement_versions=[doc.version_id for doc in input_data.source_documents],
            knowledge_queried=True,
        )
        yield {"type": "message_delta", "delta": output.answer}
        yield {"type": "metadata", "output": output}

    monkeypatch.setattr(service.knowledge_agent_service, "stream_knowledge_agent", fake_stream_knowledge_agent)
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
                service.KnowledgeQueryRequest(question="有哪些需求？", ),
            )
        )
    )

    assert captured_project_names == [["测试项目", "订单项目"]]
    assert [event["type"] for event in events] == ["message_delta", "metadata", "done"]
    result = events[1]["result"]
    assert result["conversation"] is not None
    assert len(result["messages"]) == 2
    assert result["answer"] == (
        "已查询全部项目。\n\n"
        "参考来源：\n"
        "- [需求] 测试项目 / 最终需求\n"
        "- [需求] 订单项目 / 订单需求"
    )
    assert result["messages"][1]["content"] == result["answer"]
    assert "used_requirement_versions" not in result
    assert "used_requirement_versions" not in result["messages"][1]

    conversations = service.list_all_project_knowledge_conversations(actor)
    assert len(conversations) == 1
    detail = service.get_all_project_knowledge_conversation(conversations[0]["id"], actor)
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]


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

    async def fake_stream_knowledge_agent(input_data, **_kwargs):
        captured_project_names.append([doc.project_name for doc in input_data.source_documents])
        output = KnowledgeQueryOutput(
            answer="已使用可用项目来源回答。",
            used_requirement_versions=[doc.version_id for doc in input_data.source_documents],
            knowledge_queried=True,
        )
        yield {"type": "metadata", "output": output}

    monkeypatch.setattr(service.knowledge_agent_service, "stream_knowledge_agent", fake_stream_knowledge_agent)
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
                service.KnowledgeQueryRequest(question="有哪些可用需求？", ),
            )
        )
    )

    assert captured_project_names == [["测试项目", "有效项目"]]
    result = events[0]["result"]
    assert result["answer"] == "已使用可用项目来源回答。"
    assert "无法查询项目知识库" not in result["answer"]
    assert result["conversation"] is not None
    assert "used_requirement_versions" not in result
    assert events[-1] == {"type": "done"}


def test_all_project_knowledge_query_persists_conversation_and_uses_deepagents_thread(monkeypatch, tmp_path) -> None:
    from app.schemas.knowledge import KnowledgeQueryOutput
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)
    captured_thread_ids: list[str] = []

    async def fake_stream_knowledge_agent(input_data, *, thread_id=None, **_kwargs):
        captured_thread_ids.append(thread_id)
        output = KnowledgeQueryOutput(
            answer=f"检索：{input_data.question}",
            used_requirement_versions=["version-1"],
            knowledge_queried=True,
        )
        yield {"type": "metadata", "output": output}

    monkeypatch.setattr(service.knowledge_agent_service, "stream_knowledge_agent", fake_stream_knowledge_agent)
    actor = {
        "id": "u-admin",
        "username": "admin",
        "nickname": "平台管理员",
        "role": "admin",
        "project_scope": "全部项目",
    }

    async def run_queries():
        first_events = await _collect_async_events(
            service.stream_all_project_knowledge_query(
                actor,
                service.KnowledgeQueryRequest(question="登录规则是什么？", ),
            )
        )
        first_result = first_events[-2]["result"]
        second_events = await _collect_async_events(
            service.stream_all_project_knowledge_query(
                actor,
                service.KnowledgeQueryRequest(
                    question="这个模块还要补哪些测试？",
                                        conversation_id=first_result["conversation"]["id"],
                ),
            )
        )
        second_result = second_events[-2]["result"]
        return first_result, second_result

    first, second = asyncio.run(run_queries())
    conversation_id = first["conversation"]["id"]

    detail = service.get_all_project_knowledge_conversation(conversation_id, actor)
    assert first["conversation"]["title"] == "登录规则是什么？"
    assert second["conversation"]["id"] == conversation_id
    assert captured_thread_ids == [conversation_id, conversation_id]
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant", "user", "assistant"]

    delete_result = service.delete_all_project_knowledge_conversation(conversation_id, actor)
    assert delete_result == {"deleted": True}
    assert service.list_all_project_knowledge_conversations(actor) == []


def test_all_project_knowledge_query_forwards_visible_thinking(monkeypatch, tmp_path) -> None:
    from app.schemas.knowledge import KnowledgeQueryOutput
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)

    captured_show_thinking: list[bool] = []

    async def fake_stream_knowledge_agent(input_data, *, show_thinking=False, thread_id=None):
        assert input_data.project_name == "全部项目"
        captured_show_thinking.append(show_thinking)
        yield {"type": "thinking_delta", "delta": "先判断是否需要查询。"}
        yield {"type": "metadata", "output": KnowledgeQueryOutput(answer="不需要查询。", knowledge_queried=False)}

    monkeypatch.setattr(service.knowledge_agent_service, "stream_knowledge_agent", fake_stream_knowledge_agent)
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
                service.KnowledgeQueryRequest(question="登录规则是什么？", show_thinking=True),
            )
        )
    )

    assert captured_show_thinking == [True]
    assert events[0] == {"type": "thinking_delta", "delta": "先判断是否需要查询。"}
    assert events[1]["type"] == "metadata"
    assert events[1]["result"]["answer"] == "不需要查询。"


def test_project_knowledge_stream_uses_agent_structured_answer_without_service_filter(monkeypatch, tmp_path) -> None:
    from app.schemas.knowledge import KnowledgeQueryOutput
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)

    async def fake_stream_knowledge_agent(input_data, *, show_thinking=False, thread_id=None):
        assert show_thinking is False
        yield {"type": "message_delta", "delta": "百工集成到钉钉需要先完成钉钉应用配置。"}
        yield {
            "type": "metadata",
            "output": KnowledgeQueryOutput(
                answer="百工集成到钉钉需要先完成钉钉应用配置。",
                knowledge_queried=True,
                used_requirement_versions=["version-1"],
            ),
        }

    monkeypatch.setattr(service.knowledge_agent_service, "stream_knowledge_agent", fake_stream_knowledge_agent)
    actor = {"id": "u-admin", "username": "admin", "nickname": "平台管理员"}

    events = asyncio.run(
        _collect_async_events(
            service.stream_project_knowledge_query(
                "project-1",
                actor,
                service.KnowledgeQueryRequest(question="百工如何集成到钉钉"),
            )
        )
    )

    visible_deltas = [event["delta"] for event in events if event["type"] == "message_delta"]
    assert visible_deltas == ["百工集成到钉钉需要先完成钉钉应用配置。"]
    metadata = next(event for event in events if event["type"] == "metadata")
    assert metadata["result"]["answer"] == "百工集成到钉钉需要先完成钉钉应用配置。"
    assert metadata["result"]["messages"][1]["content"] == "百工集成到钉钉需要先完成钉钉应用配置。"


def test_project_knowledge_stream_without_metadata_returns_empty_result_message(monkeypatch, tmp_path) -> None:
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)

    async def fake_stream_knowledge_agent(input_data, *, show_thinking=False, thread_id=None):
        yield {"type": "done"}

    monkeypatch.setattr(service.knowledge_agent_service, "stream_knowledge_agent", fake_stream_knowledge_agent)
    actor = {"id": "u-admin", "username": "admin", "nickname": "平台管理员"}

    events = asyncio.run(
        _collect_async_events(
            service.stream_project_knowledge_query(
                "project-1",
                actor,
                service.KnowledgeQueryRequest(question="知识库里有没有火星基地验收规则？"),
            )
        )
    )

    visible_deltas = [event["delta"] for event in events if event["type"] == "message_delta"]
    assert visible_deltas == [service.KNOWLEDGE_QUERY_EMPTY_MESSAGE]
    metadata = next(event for event in events if event["type"] == "metadata")
    assert metadata["result"]["answer"] == service.KNOWLEDGE_QUERY_EMPTY_MESSAGE
    assert "knowledge_queried" not in metadata["result"]
    assert "used_company_knowledge_files" not in metadata["result"]


def test_project_knowledge_stream_uses_agent_direct_reply(monkeypatch, tmp_path) -> None:
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)
    captured_questions: list[str] = []

    async def fake_stream_knowledge_agent(input_data, *, show_thinking=False, thread_id=None):
        captured_questions.append(input_data.question)
        yield {"type": "message_delta", "delta": "你好，有什么可以帮你？"}
        yield {
            "type": "metadata",
            "output": service.KnowledgeQueryOutput(answer="你好，有什么可以帮你？", knowledge_queried=False),
        }

    monkeypatch.setattr(service.knowledge_agent_service, "stream_knowledge_agent", fake_stream_knowledge_agent)
    actor = {"id": "u-admin", "username": "admin", "nickname": "平台管理员"}

    events = asyncio.run(
        _collect_async_events(
            service.stream_project_knowledge_query(
                "project-1",
                actor,
                service.KnowledgeQueryRequest(question="hi"),
            )
        )
    )

    visible_deltas = [event["delta"] for event in events if event["type"] == "message_delta"]
    assert captured_questions == ["hi"]
    assert visible_deltas == ["你好，有什么可以帮你？"]
    metadata = next(event for event in events if event["type"] == "metadata")
    assert metadata["result"]["answer"] == "你好，有什么可以帮你？"
    assert "used_requirement_versions" not in metadata["result"]
    assert "knowledge_queried" not in metadata["result"]
    assert "used_company_knowledge_files" not in metadata["result"]


def test_knowledge_agent_payload_uses_deepagents_file_data_format() -> None:
    from app.agents.knowledge import service as knowledge_agent_service
    from app.schemas.knowledge import KnowledgeQueryInput, KnowledgeSourceDocumentInput

    payload = knowledge_agent_service._agent_payload(
        KnowledgeQueryInput(
            project_id="project-1",
            project_name="测试项目",
            question="登录规则是什么？",
            source_documents=[
                KnowledgeSourceDocumentInput(
                    source_type="requirement",
                    source_id="version-1",
                    source_title="最终需求 v1",
                    project_id="project-1",
                    project_name="测试项目",
                    document_id="doc-1",
                    document_name="最终需求",
                    version_id="version-1",
                    version_no=1,
                    markdown_content="# 登录\n用户可以登录。",
                )
            ],
        )
    )

    files = payload["files"]
    assert files["/README.md"]["encoding"] == "utf-8"
    requirement_file = next(path for path in files if path.startswith("/final-requirements/"))
    assert files[requirement_file]["content"].startswith("<!-- source_metadata:")
    assert isinstance(files[requirement_file]["content"], str)


def test_knowledge_agent_stream_uses_structured_response_not_message_tokens(monkeypatch) -> None:
    from app.agents.knowledge import service as knowledge_agent_service
    from app.schemas.knowledge import KnowledgeQueryInput, KnowledgeQueryOutput

    class FakeAgent:
        async def astream(self, payload, config=None, stream_mode=None):
            yield (
                "messages",
                {
                    "type": "assistant",
                    "content": '```json\n{"answer":"错误的可见 JSON","used_requirement_versions":[]}\n```',
                },
            )
            yield (
                "values",
                {
                    "structured_response": KnowledgeQueryOutput(
                        answer="正确的结构化答案",
                        knowledge_queried=True,
                    ),
                },
            )

    monkeypatch.setattr(
        knowledge_agent_service,
        "resolve_model_selection",
        lambda capability_id: object(),
    )
    monkeypatch.setattr(
        knowledge_agent_service,
        "build_agent_model",
        lambda selection, *, extra_body=None: object(),
    )
    monkeypatch.setattr(knowledge_agent_service, "knowledge_agent", lambda model: FakeAgent())

    events = asyncio.run(
        _collect_async_events(
            knowledge_agent_service.stream_knowledge_agent(
                KnowledgeQueryInput(
                    project_id="project-1",
                    project_name="测试项目",
                    question="知识库上传文件大小限制",
                )
            )
        )
    )

    assert events[0] == {"type": "message_delta", "delta": "正确的结构化答案"}
    assert events[1]["type"] == "metadata"
    assert events[1]["output"].answer == "正确的结构化答案"
    assert events[2] == {"type": "done"}


def test_knowledge_agent_stream_filters_plain_structured_field_lines(monkeypatch) -> None:
    from app.agents.knowledge import service as knowledge_agent_service
    from app.schemas.knowledge import KnowledgeQueryInput, KnowledgeQueryOutput

    class FakeAgent:
        async def astream(self, payload, config=None, stream_mode=None):
            yield ("messages", {"type": "assistant", "content": "我是 MiniMax-M3。"})
            yield ("messages", {"type": "assistant", "content": "\n\nknowledge_queried: false"})
            yield (
                "values",
                {
                    "structured_response": KnowledgeQueryOutput(
                        answer="我是 MiniMax-M3。",
                        knowledge_queried=False,
                    )
                },
            )

    monkeypatch.setattr(
        knowledge_agent_service,
        "resolve_model_selection",
        lambda capability_id: object(),
    )
    monkeypatch.setattr(
        knowledge_agent_service,
        "build_agent_model",
        lambda selection, *, extra_body=None: object(),
    )
    monkeypatch.setattr(knowledge_agent_service, "knowledge_agent", lambda model: FakeAgent())

    events = asyncio.run(
        _collect_async_events(
            knowledge_agent_service.stream_knowledge_agent(
                KnowledgeQueryInput(
                    project_id="project-1",
                    project_name="测试项目",
                    question="你是什么模型",
                )
            )
        )
    )

    assert [event for event in events if event["type"] == "message_delta"] == [
        {"type": "message_delta", "delta": "我是 MiniMax-M3。"}
    ]
    assert events[-1] == {"type": "done"}


def test_knowledge_agent_stream_filters_xml_structured_wrappers(monkeypatch) -> None:
    from app.agents.knowledge import service as knowledge_agent_service
    from app.schemas.knowledge import KnowledgeQueryInput, KnowledgeQueryOutput

    class FakeAgent:
        async def astream(self, payload, config=None, stream_mode=None):
            yield ("messages", {"type": "assistant", "content": "<KnowledgeQueryOutput><answer>"})
            yield ("messages", {"type": "assistant", "content": "我是 MiniMax-M3。"})
            yield ("messages", {"type": "assistant", "content": "</answer><knowledge_queried>false</knowledge_queried>"})
            yield (
                "values",
                {
                    "structured_response": KnowledgeQueryOutput(
                        answer="我是 MiniMax-M3。",
                        knowledge_queried=False,
                    )
                },
            )

    monkeypatch.setattr(
        knowledge_agent_service,
        "resolve_model_selection",
        lambda capability_id: object(),
    )
    monkeypatch.setattr(
        knowledge_agent_service,
        "build_agent_model",
        lambda selection, *, extra_body=None: object(),
    )
    monkeypatch.setattr(knowledge_agent_service, "knowledge_agent", lambda model: FakeAgent())

    events = asyncio.run(
        _collect_async_events(
            knowledge_agent_service.stream_knowledge_agent(
                KnowledgeQueryInput(
                    project_id="project-1",
                    project_name="测试项目",
                    question="你是什么模型",
                )
            )
        )
    )

    message_deltas = [event for event in events if event["type"] == "message_delta"]
    assert message_deltas == [
        {"type": "message_delta", "delta": "我是 MiniMax-M3。"}
    ]
    assert all("KnowledgeQueryOutput" not in str(event) for event in message_deltas)
    assert all("<answer>" not in str(event) for event in message_deltas)
    assert events[-1] == {"type": "done"}


def test_knowledge_agent_stream_accepts_direct_ai_reply_without_tool_use(monkeypatch) -> None:
    from app.agents.knowledge import service as knowledge_agent_service
    from app.schemas.knowledge import KnowledgeQueryInput

    class FakeAgent:
        async def astream(self, payload, config=None, stream_mode=None):
            yield ("messages", {"type": "assistant", "content": "你好，"})
            yield ("messages", {"type": "assistant", "content": "有什么可以帮你？"})

    monkeypatch.setattr(
        knowledge_agent_service,
        "resolve_model_selection",
        lambda capability_id: object(),
    )
    monkeypatch.setattr(
        knowledge_agent_service,
        "build_agent_model",
        lambda selection, *, extra_body=None: object(),
    )
    monkeypatch.setattr(knowledge_agent_service, "knowledge_agent", lambda model: FakeAgent())

    events = asyncio.run(
        _collect_async_events(
            knowledge_agent_service.stream_knowledge_agent(
                KnowledgeQueryInput(
                    project_id="project-1",
                    project_name="测试项目",
                    question="hi",
                )
            )
        )
    )

    assert events[0] == {"type": "message_delta", "delta": "你好，"}
    assert events[1] == {"type": "message_delta", "delta": "有什么可以帮你？"}
    assert events[2]["type"] == "metadata"
    assert events[2]["output"].answer == "你好，有什么可以帮你？"
    assert events[2]["output"].knowledge_queried is False
    assert events[3] == {"type": "done"}


def test_knowledge_agent_stream_rejects_tool_result_without_structured_response(monkeypatch) -> None:
    from app.agents.knowledge import service as knowledge_agent_service
    from app.schemas.knowledge import KnowledgeQueryInput

    class FakeAgent:
        async def astream(self, payload, config=None, stream_mode=None):
            yield (
                "messages",
                {
                    "type": "assistant",
                    "content": "",
                    "tool_calls": [{"name": "read_file", "args": {"path": "/README.md"}}],
                },
            )
            yield ("messages", {"type": "tool", "content": "# 知识库文件清单"})
            yield ("messages", {"type": "assistant", "content": "这个答案缺少结构化结果。"})

    monkeypatch.setattr(
        knowledge_agent_service,
        "resolve_model_selection",
        lambda capability_id: object(),
    )
    monkeypatch.setattr(
        knowledge_agent_service,
        "build_agent_model",
        lambda selection, *, extra_body=None: object(),
    )
    monkeypatch.setattr(knowledge_agent_service, "knowledge_agent", lambda model: FakeAgent())

    with pytest.raises(ValueError, match="结构化结果"):
        asyncio.run(
            _collect_async_events(
                knowledge_agent_service.stream_knowledge_agent(
                    KnowledgeQueryInput(
                        project_id="project-1",
                        project_name="测试项目",
                        question="登录规则是什么？",
                    )
                )
            )
        )


def test_knowledge_agent_stream_without_thinking_uses_astream(monkeypatch) -> None:
    from app.agents.knowledge import service as knowledge_agent_service
    from app.schemas.knowledge import KnowledgeQueryInput, KnowledgeQueryOutput

    captured: dict[str, object] = {}

    class FakeAgent:
        async def astream(self, payload, config=None, stream_mode=None):
            captured["payload"] = payload
            captured["config"] = config
            yield ("messages", {"type": "assistant", "content": "你好，"})
            yield ("messages", {"type": "assistant", "content": "我是项目知识库 AI。"})
            yield (
                "values",
                {
                    "structured_response": KnowledgeQueryOutput(
                        answer="你好，我是项目知识库 AI。",
                        knowledge_queried=False,
                    )
                },
            )

    monkeypatch.setattr(
        knowledge_agent_service,
        "resolve_model_selection",
        lambda capability_id: object(),
    )
    monkeypatch.setattr(
        knowledge_agent_service,
        "build_agent_model",
        lambda selection, *, extra_body=None: object(),
    )
    monkeypatch.setattr(knowledge_agent_service, "knowledge_agent", lambda model: FakeAgent())

    events = asyncio.run(
        _collect_async_events(
            knowledge_agent_service.stream_knowledge_agent(
                KnowledgeQueryInput(
                    project_id="project-1",
                    project_name="测试项目",
                    question="hi",
                ),
                thread_id="conversation-1",
            )
        )
    )

    assert captured["config"] == {"configurable": {"thread_id": "conversation-1"}}
    assert events[0] == {"type": "message_delta", "delta": "你好，"}
    assert events[1] == {"type": "message_delta", "delta": "我是项目知识库 AI。"}
    assert events[2]["type"] == "metadata"
    assert events[2]["output"].knowledge_queried is False
    assert events[3] == {"type": "done"}


def test_knowledge_agent_stream_can_forward_thinking_without_visible_message_tokens(monkeypatch) -> None:
    from app.agents.knowledge import service as knowledge_agent_service
    from app.schemas.knowledge import KnowledgeQueryInput, KnowledgeQueryOutput

    class FakeAgent:
        async def astream(self, payload, config=None, stream_mode=None):
            assert stream_mode == ["messages", "values"]
            yield (
                "messages",
                {
                    "type": "assistant",
                    "reasoning_content": "先读取知识库。",
                    "content": "这段正文 token 不应直接展示。",
                },
            )
            yield (
                "values",
                {
                    "structured_response": KnowledgeQueryOutput(
                        answer="最终答案",
                        knowledge_queried=True,
                    )
                },
            )

    monkeypatch.setattr(
        knowledge_agent_service,
        "resolve_model_selection",
        lambda capability_id: object(),
    )
    monkeypatch.setattr(
        knowledge_agent_service,
        "build_agent_model",
        lambda selection, *, extra_body=None: object(),
    )
    monkeypatch.setattr(knowledge_agent_service, "knowledge_agent", lambda model: FakeAgent())

    events = asyncio.run(
        _collect_async_events(
            knowledge_agent_service.stream_knowledge_agent(
                KnowledgeQueryInput(
                    project_id="project-1",
                    project_name="测试项目",
                    question="知识库上传文件大小限制",
                ),
                show_thinking=True,
            )
        )
    )

    assert events[0] == {"type": "thinking_delta", "delta": "先读取知识库。"}
    assert events[1] == {"type": "message_delta", "delta": "最终答案"}
    assert events[2]["type"] == "metadata"
