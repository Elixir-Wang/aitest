import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path
from app.repositories import document_repo, global_knowledge_repo, knowledge_conversation_repo, project_repo
from app.agents.knowledge.schemas import (
    KnowledgeQueryInput,
    KnowledgeQueryOutput,
    KnowledgeSourceDocumentInput,
    KnowledgeSourceRef,
)
from app.schemas.knowledge import (
    KnowledgeConversation,
    KnowledgeConversationDetail,
    KnowledgeConversationMessage,
    KnowledgeQueryRequest,
)
from app.services import operation_log_service
from app.agents.knowledge import service as knowledge_agent_service

logger = logging.getLogger(__name__)

KNOWLEDGE_QUERY_TIMEOUT_SECONDS = 300
KNOWLEDGE_QUERY_TIMEOUT_MESSAGE = "项目知识库查询超时，请稍后继续。"
KNOWLEDGE_QUERY_FAILED_MESSAGE = "项目知识库查询失败，请稍后重试。"
KNOWLEDGE_QUERY_EMPTY_MESSAGE = "项目知识库未返回有效结果，请换个问法再试。"
ALL_PROJECTS_CONVERSATION_PROJECT_ID = "__all_projects__"


async def query_project_knowledge(project_id: str, actor, request: KnowledgeQueryRequest) -> dict:
    question = request.question.strip()
    if not question:
        raise api_error(400, "KNOWLEDGE_QUERY_REQUIRED", "请输入要查询的问题。")
    actor_id = actor["id"]
    conversation = _get_or_create_conversation(project_id, actor_id, request.conversation_id, question)
    project = _get_project(project_id)
    input_data, source_version_ids, company_file_ids, blockers = _collect_query_input(project_id, request)
    if blockers and not input_data.source_documents:
        output = KnowledgeQueryOutput(
            answer="无法查询知识库：\n\n" + "\n".join(f"- {item}" for item in blockers),
            knowledge_queried=True,
        )
    else:
        try:
            output = await knowledge_agent_service.run_knowledge_agent(input_data, thread_id=conversation["id"])
        except Exception:
            output = KnowledgeQueryOutput(answer=KNOWLEDGE_QUERY_FAILED_MESSAGE, knowledge_queried=False)
    if output.knowledge_queried:
        source_version_ids = output.used_requirement_versions or source_version_ids
        company_file_ids = output.used_company_knowledge_files or company_file_ids
    else:
        source_version_ids = []
        company_file_ids = []
    user_message, assistant_message = _append_query_messages(
        conversation["id"],
        question,
        output,
        output.used_requirement_versions or source_version_ids,
    )
    operation_log_service.record_success(
        module="knowledge",
        action="query",
        object_type="project_knowledge",
        object_id=project_id,
        object_name=project["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary="查询项目知识库。" if output.knowledge_queried else "项目知识库 AI 普通对话。",
        after={
            "question": question,
            "conversation_id": conversation["id"],
            "knowledge_queried": output.knowledge_queried,
            "source_versions": source_version_ids,
            "company_knowledge_files": company_file_ids,
        },
    )
    return _query_result_payload(
        conversation,
        user_message,
        assistant_message,
    )


async def stream_project_knowledge_query(
    project_id: str,
    actor,
    request: KnowledgeQueryRequest,
) -> AsyncIterator[dict[str, Any]]:
    question = request.question.strip()
    if not question:
        raise api_error(400, "KNOWLEDGE_QUERY_REQUIRED", "请输入要查询的问题。")
    actor_id = actor["id"]
    conversation = _get_or_create_conversation(project_id, actor_id, request.conversation_id, question)
    project = _get_project(project_id)
    input_data, source_version_ids, company_file_ids, blockers = _collect_query_input(project_id, request)
    logger.info(
        "[knowledge-query] request project_id=%s conversation_id=%s show_thinking=%s question=%s blockers=%s sources=%s",
        project_id,
        conversation["id"],
        request.show_thinking,
        question[:120],
        bool(blockers),
        len(input_data.source_documents),
    )
    final_output: KnowledgeQueryOutput | None = None

    try:
        async with asyncio.timeout(KNOWLEDGE_QUERY_TIMEOUT_SECONDS):
            if blockers and not input_data.source_documents:
                final_output = KnowledgeQueryOutput(
                    answer="无法查询知识库：\n\n" + "\n".join(f"- {item}" for item in blockers),
                    knowledge_queried=True,
                )
                yield {"type": "message_delta", "delta": final_output.answer}
            else:
                async for event in knowledge_agent_service.stream_knowledge_agent(
                    input_data,
                    show_thinking=request.show_thinking,
                    thread_id=conversation["id"],
                ):
                    event_type = event.get("type")
                    if event_type == "message_delta":
                        yield event
                    elif event_type == "thinking_delta":
                        yield event
                    elif event_type == "metadata":
                        final_output = event["output"]
    except TimeoutError:
        user_message, assistant_message = _append_query_messages(
            conversation["id"],
            question,
            KnowledgeQueryOutput(answer=KNOWLEDGE_QUERY_TIMEOUT_MESSAGE, knowledge_queried=False),
            [],
        )
        yield {
            "type": "error",
            "code": "KNOWLEDGE_AGENT_TIMEOUT",
            "message": KNOWLEDGE_QUERY_TIMEOUT_MESSAGE,
            "result": _query_result_payload(
                conversation,
                user_message,
                assistant_message,
            ),
        }
        return

    if final_output is None:
        final_output = KnowledgeQueryOutput(answer=KNOWLEDGE_QUERY_EMPTY_MESSAGE, knowledge_queried=False)
        yield {"type": "message_delta", "delta": final_output.answer}
    if final_output.knowledge_queried:
        source_version_ids = final_output.used_requirement_versions or source_version_ids
        company_file_ids = final_output.used_company_knowledge_files or company_file_ids
    else:
        source_version_ids = []
        company_file_ids = []
    user_message, assistant_message = _append_query_messages(
        conversation["id"],
        question,
        final_output,
        final_output.used_requirement_versions or source_version_ids,
    )
    operation_log_service.record_success(
        module="knowledge",
        action="query",
        object_type="project_knowledge",
        object_id=project_id,
        object_name=project["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary="查询项目知识库。" if final_output.knowledge_queried else "项目知识库 AI 普通对话。",
        after={
            "question": question,
            "conversation_id": conversation["id"],
            "knowledge_queried": final_output.knowledge_queried,
            "source_versions": source_version_ids,
            "company_knowledge_files": company_file_ids,
        },
    )
    yield {
        "type": "metadata",
        "result": _query_result_payload(
            conversation,
            user_message,
            assistant_message,
        ),
    }
    yield {"type": "done"}


async def stream_all_project_knowledge_query(
    actor,
    request: KnowledgeQueryRequest,
) -> AsyncIterator[dict[str, Any]]:
    question = request.question.strip()
    if not question:
        raise api_error(400, "KNOWLEDGE_QUERY_REQUIRED", "请输入要查询的问题。")
    actor_id = actor["id"]
    conversation = _get_or_create_all_projects_conversation(actor_id, request.conversation_id, question)
    input_data, source_version_ids, company_file_ids, blockers = _collect_all_project_query_input(actor, request)
    logger.info(
        "[knowledge-query] request scope=all conversation_id=%s show_thinking=%s question=%s blockers=%s sources=%s",
        conversation["id"],
        request.show_thinking,
        question[:120],
        bool(blockers),
        len(input_data.source_documents),
    )
    final_output: KnowledgeQueryOutput | None = None

    try:
        async with asyncio.timeout(KNOWLEDGE_QUERY_TIMEOUT_SECONDS):
            if blockers and not input_data.source_documents:
                final_output = KnowledgeQueryOutput(
                    answer="无法查询知识库：\n\n" + "\n".join(f"- {item}" for item in blockers),
                    knowledge_queried=True,
                )
                yield {"type": "message_delta", "delta": final_output.answer}
            else:
                async for event in knowledge_agent_service.stream_knowledge_agent(
                    input_data,
                    show_thinking=request.show_thinking,
                    thread_id=conversation["id"],
                ):
                    event_type = event.get("type")
                    if event_type == "message_delta":
                        yield event
                    elif event_type == "thinking_delta":
                        yield event
                    elif event_type == "metadata":
                        final_output = event["output"]
    except TimeoutError:
        user_message, assistant_message = _append_query_messages(
            conversation["id"],
            question,
            KnowledgeQueryOutput(answer=KNOWLEDGE_QUERY_TIMEOUT_MESSAGE, knowledge_queried=False),
            [],
        )
        yield {
            "type": "error",
            "code": "KNOWLEDGE_AGENT_TIMEOUT",
            "message": KNOWLEDGE_QUERY_TIMEOUT_MESSAGE,
            "result": _query_result_payload(
                conversation,
                user_message,
                assistant_message,
            ),
        }
        return

    if final_output is None:
        final_output = KnowledgeQueryOutput(answer=KNOWLEDGE_QUERY_EMPTY_MESSAGE, knowledge_queried=False)
        yield {"type": "message_delta", "delta": final_output.answer}
    if final_output.knowledge_queried:
        source_version_ids = final_output.used_requirement_versions or source_version_ids
        company_file_ids = final_output.used_company_knowledge_files or company_file_ids
    else:
        source_version_ids = []
        company_file_ids = []
    user_message, assistant_message = _append_query_messages(
        conversation["id"],
        question,
        final_output,
        final_output.used_requirement_versions or source_version_ids,
    )
    operation_log_service.record_success(
        module="knowledge",
        action="query",
        object_type="all_project_knowledge",
        object_id=ALL_PROJECTS_CONVERSATION_PROJECT_ID,
        object_name="全部项目",
        project_id=ALL_PROJECTS_CONVERSATION_PROJECT_ID,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary="查询全部项目知识库。" if final_output.knowledge_queried else "全部项目知识库 AI 普通对话。",
        after={
            "question": question,
            "conversation_id": conversation["id"],
            "knowledge_queried": final_output.knowledge_queried,
            "source_versions": source_version_ids,
            "company_knowledge_files": company_file_ids,
        },
    )
    yield {
        "type": "metadata",
        "result": _query_result_payload(
            conversation,
            user_message,
            assistant_message,
        ),
    }
    yield {"type": "done"}


def list_all_project_knowledge_conversations(actor) -> list[dict]:
    with connect() as db:
        _ensure_all_projects_conversation_scope(db)
        rows = knowledge_conversation_repo.list_by_project(db, ALL_PROJECTS_CONVERSATION_PROJECT_ID, actor["id"])
    return [_conversation_to_schema(row).model_dump() for row in rows]


def get_all_project_knowledge_conversation(conversation_id: str, actor) -> dict:
    with connect() as db:
        _ensure_all_projects_conversation_scope(db)
        conversation = knowledge_conversation_repo.find_by_project_and_id(
            db,
            ALL_PROJECTS_CONVERSATION_PROJECT_ID,
            conversation_id,
            actor["id"],
        )
        if not conversation:
            raise api_error(404, "KNOWLEDGE_CONVERSATION_NOT_FOUND", "对话不存在。")
        messages = knowledge_conversation_repo.list_messages(db, conversation_id)
    return KnowledgeConversationDetail(
        conversation=_conversation_to_schema(conversation),
        messages=[_message_to_schema(message) for message in messages],
    ).model_dump()


def delete_all_project_knowledge_conversation(conversation_id: str, actor) -> dict:
    with connect() as db:
        _ensure_all_projects_conversation_scope(db)
        conversation = knowledge_conversation_repo.find_by_project_and_id(
            db,
            ALL_PROJECTS_CONVERSATION_PROJECT_ID,
            conversation_id,
            actor["id"],
        )
        if not conversation:
            raise api_error(404, "KNOWLEDGE_CONVERSATION_NOT_FOUND", "对话不存在。")
        knowledge_conversation_repo.delete(db, conversation_id)
    operation_log_service.record_success(
        module="knowledge",
        action="delete_conversation",
        object_type="all_project_knowledge_conversation",
        object_id=conversation_id,
        object_name=conversation["title"],
        project_id=ALL_PROJECTS_CONVERSATION_PROJECT_ID,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary="删除全部项目知识库对话。",
    )
    return {"deleted": True}


def list_project_knowledge_conversations(project_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_project(db, project_id)
        rows = knowledge_conversation_repo.list_by_project(db, project_id, actor["id"])
    return [_conversation_to_schema(row).model_dump() for row in rows]


def get_project_knowledge_conversation(project_id: str, conversation_id: str, actor) -> dict:
    with connect() as db:
        _require_project(db, project_id)
        conversation = knowledge_conversation_repo.find_by_project_and_id(db, project_id, conversation_id, actor["id"])
        if not conversation:
            raise api_error(404, "KNOWLEDGE_CONVERSATION_NOT_FOUND", "对话不存在。")
        messages = knowledge_conversation_repo.list_messages(db, conversation_id)
    return KnowledgeConversationDetail(
        conversation=_conversation_to_schema(conversation),
        messages=[_message_to_schema(message) for message in messages],
    ).model_dump()


def delete_project_knowledge_conversation(project_id: str, conversation_id: str, actor) -> dict:
    with connect() as db:
        _require_project(db, project_id)
        conversation = knowledge_conversation_repo.find_by_project_and_id(db, project_id, conversation_id, actor["id"])
        if not conversation:
            raise api_error(404, "KNOWLEDGE_CONVERSATION_NOT_FOUND", "对话不存在。")
        knowledge_conversation_repo.delete(db, conversation_id)
    operation_log_service.record_success(
        module="knowledge",
        action="delete_conversation",
        object_type="project_knowledge_conversation",
        object_id=conversation_id,
        object_name=conversation["title"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary="删除项目知识库对话。",
    )
    return {"deleted": True}


def _collect_query_input(
    project_id: str,
    request: KnowledgeQueryRequest,
) -> tuple[KnowledgeQueryInput, list[str], list[str], list[str]]:
    with connect() as db:
        project = _require_project(db, project_id)
        source_documents, source_version_ids, blockers = _collect_project_sources(
            db,
            project,
            request,
        )
        company_sources, company_file_ids, company_blockers = _collect_company_knowledge_sources(db, request)
        source_documents.extend(company_sources)
        blockers.extend(company_blockers)

    if not source_documents:
        if request.include_requirements:
            blockers.append("当前项目没有可用于查询的最终需求文档版本。")
        if request.include_company_knowledge:
            blockers.append("当前没有可读取的公司知识库文件。")
    return (
        KnowledgeQueryInput(
            project_id=project_id,
            project_name=project["name"],
            question=request.question.strip(),
            source_documents=source_documents,
        ),
        source_version_ids,
        company_file_ids,
        blockers,
    )


def _collect_all_project_query_input(
    actor,
    request: KnowledgeQueryRequest,
) -> tuple[KnowledgeQueryInput, list[str], list[str], list[str]]:
    with connect() as db:
        projects = project_repo.list_visible(db, actor)
        source_documents: list[KnowledgeSourceDocumentInput] = []
        source_version_ids: list[str] = []
        blockers: list[str] = []
        for project in projects:
            (
                project_source_documents,
                project_source_version_ids,
                project_blockers,
            ) = _collect_project_sources(db, project, request)
            source_documents.extend(project_source_documents)
            source_version_ids.extend(project_source_version_ids)
            blockers.extend(project_blockers)
        company_sources, company_file_ids, company_blockers = _collect_company_knowledge_sources(db, request)
        source_documents.extend(company_sources)
        blockers.extend(company_blockers)

    if not source_documents:
        if request.include_requirements:
            blockers.append("当前可见项目没有可用于查询的最终需求文档版本。")
        if request.include_company_knowledge:
            blockers.append("当前没有可读取的公司知识库文件。")
    else:
        blockers = []
    return (
        KnowledgeQueryInput(
            project_id="",
            project_name="全部项目",
            question=request.question.strip(),
            source_documents=source_documents,
        ),
        source_version_ids,
        company_file_ids,
        blockers,
    )


def _collect_project_sources(
    db,
    project,
    request: KnowledgeQueryRequest,
) -> tuple[list[KnowledgeSourceDocumentInput], list[str], list[str]]:
    project_id = project["id"]
    project_name = project["name"]
    source_documents: list[KnowledgeSourceDocumentInput] = []
    source_version_ids: list[str] = []
    blockers: list[str] = []
    if request.include_requirements:
        for doc in document_repo.list_by_project(db, project_id):
            if not doc["current_version_id"]:
                continue
            version = document_repo.find_version(db, doc["current_version_id"])
            if not version:
                continue
            markdown_path = resolve_stored_path(version["file_path"]) or Path(version["file_path"])
            if not markdown_path.exists():
                blockers.append(f"需求文档「{doc['name']}」当前版本文件不存在。")
                continue
            source_version_ids.append(version["id"])
            source_documents.append(
                KnowledgeSourceDocumentInput(
                    source_type="requirement",
                    source_id=version["id"],
                    source_title=f"{doc['name']} v{version['version_no']}",
                    project_id=project_id,
                    project_name=project_name,
                    document_id=doc["id"],
                    document_name=doc["name"],
                    version_id=version["id"],
                    version_no=version["version_no"],
                    markdown_content=markdown_path.read_text(encoding="utf-8"),
                )
            )

    return source_documents, source_version_ids, blockers


def _collect_company_knowledge_sources(
    db,
    request: KnowledgeQueryRequest,
) -> tuple[list[KnowledgeSourceDocumentInput], list[str], list[str]]:
    if not request.include_company_knowledge:
        return [], [], []
    source_documents: list[KnowledgeSourceDocumentInput] = []
    file_ids: list[str] = []
    blockers: list[str] = []
    bases = global_knowledge_repo.list_bases(db)
    for base in bases:
        folders = {row["id"]: row for row in global_knowledge_repo.list_folders_by_base(db, base["id"])}
        for file_row in global_knowledge_repo.list_files_by_base(db, base["id"]):
            if file_row["conversion_status"] not in {"completed", "success", "available"}:
                continue
            markdown = _read_company_knowledge_markdown(file_row)
            if not markdown.strip():
                continue
            file_ids.append(file_row["id"])
            source_documents.append(
                KnowledgeSourceDocumentInput(
                    source_type="company_knowledge",
                    source_id=file_row["id"],
                    source_title=f"{base['name']} / {file_row['display_name']}",
                    base_id=base["id"],
                    base_name=base["name"],
                    folder_path=_folder_path(folders, file_row["folder_id"]),
                    file_id=file_row["id"],
                    file_name=file_row["display_name"],
                    markdown_content=markdown,
                )
            )
    if not source_documents:
        blockers.append("当前没有可读取的公司知识库文件。")
    return source_documents, file_ids, blockers


def _read_company_knowledge_markdown(file_row) -> str:
    markdown_path = resolve_stored_path(file_row["markdown_path"]) or Path(file_row["markdown_path"])
    if markdown_path.exists():
        return markdown_path.read_text(encoding="utf-8")
    return str(file_row["markdown_content"] or "")


def _folder_path(folders: dict[str, Any], folder_id: str) -> str:
    names: list[str] = []
    current = folders.get(folder_id)
    seen: set[str] = set()
    while current and current["id"] not in seen:
        seen.add(current["id"])
        names.append(current["name"])
        parent_id = current["parent_id"]
        current = folders.get(parent_id) if parent_id else None
    return "/".join(reversed(names))


def _require_project(db, project_id: str):
    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "PROJECT_NOT_FOUND", "项目不存在。")
    return project


def _get_project(project_id: str):
    with connect() as db:
        return _require_project(db, project_id)


def _ensure_all_projects_conversation_scope(db) -> None:
    exists = db.execute("SELECT id FROM projects WHERE id = ?", (ALL_PROJECTS_CONVERSATION_PROJECT_ID,)).fetchone()
    if exists:
        return
    project_repo.create(
        db,
        project_id=ALL_PROJECTS_CONVERSATION_PROJECT_ID,
        name="全部项目知识库",
        status="archived",
        description="系统保留项目，用于全部项目知识库对话历史。",
    )


def _get_or_create_conversation(project_id: str, actor_id: str, conversation_id: str | None, question: str):
    with connect() as db:
        _require_project(db, project_id)
        return _get_or_create_conversation_in_db(db, project_id, actor_id, conversation_id, question)


def _get_or_create_all_projects_conversation(actor_id: str, conversation_id: str | None, question: str):
    with connect() as db:
        _ensure_all_projects_conversation_scope(db)
        return _get_or_create_conversation_in_db(
            db,
            ALL_PROJECTS_CONVERSATION_PROJECT_ID,
            actor_id,
            conversation_id,
            question,
        )


def _get_or_create_conversation_in_db(db, project_id: str, actor_id: str, conversation_id: str | None, question: str):
    if conversation_id:
        conversation = knowledge_conversation_repo.find_by_project_and_id(db, project_id, conversation_id, actor_id)
        if not conversation:
            raise api_error(404, "KNOWLEDGE_CONVERSATION_NOT_FOUND", "对话不存在。")
        return conversation
    return knowledge_conversation_repo.create(
        db,
        conversation_id=str(uuid.uuid4()),
        project_id=project_id,
        title=_conversation_title(question),
        created_by=actor_id,
    )


def _append_query_messages(
    conversation_id: str,
    question: str,
    output: KnowledgeQueryOutput,
    used_requirement_versions: list[str],
):
    with connect() as db:
        user_message = knowledge_conversation_repo.create_message(
            db,
            message_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=question,
        )
        assistant_message = knowledge_conversation_repo.create_message(
            db,
            message_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="assistant",
            content=_answer_with_inline_sources(output),
            source_refs=[ref.model_dump() for ref in output.source_refs],
            used_requirement_versions=used_requirement_versions,
        )
    return user_message, assistant_message


def _query_result_payload(
    conversation,
    user_message,
    assistant_message,
) -> dict[str, Any]:
    return {
        "conversation": _conversation_to_schema(conversation).model_dump(),
        "messages": [_message_to_schema(user_message).model_dump(), _message_to_schema(assistant_message).model_dump()],
        "answer": assistant_message["content"],
    }


def _answer_with_inline_sources(output: KnowledgeQueryOutput) -> str:
    answer = output.answer.strip()
    source_lines = [_source_ref_line(ref) for ref in output.source_refs]
    source_lines = [line for line in source_lines if line]
    if not source_lines:
        return answer
    return f"{answer}\n\n参考来源：\n" + "\n".join(source_lines)


def _source_ref_line(ref: KnowledgeSourceRef) -> str:
    label = {
        "requirement": "需求",
        "company_knowledge": "文档",
        "exploration": "探索",
        "manual": "手工",
    }.get(ref.source_type, "来源")
    title_parts = [part for part in (ref.project_name, ref.source_title) if part]
    title = " / ".join(title_parts) or ref.source_id
    line = f"- [{label}] {title}"
    if ref.location:
        line += f" - {ref.location}"
    if ref.excerpt:
        line += f"：{ref.excerpt}"
    return line


def _conversation_title(question: str) -> str:
    title = re.sub(r"\s+", " ", question).strip()
    return title[:28] or "新对话"


def _conversation_to_schema(row) -> KnowledgeConversation:
    return KnowledgeConversation(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _message_to_schema(row) -> KnowledgeConversationMessage:
    return KnowledgeConversationMessage(
        id=row["id"],
        conversation_id=row["conversation_id"],
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
    )


def _loads_json_array(value: str) -> list:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


