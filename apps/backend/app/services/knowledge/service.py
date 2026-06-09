import json
import re
import uuid
from pathlib import Path

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path
from app.repositories import document_repo, exploration_repo, knowledge_conversation_repo, project_repo
from app.schemas.knowledge import (
    KnowledgeConversation,
    KnowledgeConversationDetail,
    KnowledgeConversationHistoryMessage,
    KnowledgeConversationMessage,
    KnowledgeExplorationInput,
    KnowledgeQueryInput,
    KnowledgeQueryOutput,
    KnowledgeQueryRequest,
    KnowledgeSourceDocumentInput,
    KnowledgeSourceRef,
)
from app.services import operation_log_service
from app.services.exploration import service as exploration_service
from app.services.knowledge import query_service as knowledge_query_service

READY_EXPLORATION_STATUSES = {"completed", "partial"}
MAX_HISTORY_MESSAGES = 12


async def query_project_knowledge(project_id: str, actor, request: KnowledgeQueryRequest) -> dict:
    question = request.question.strip()
    if not question:
        raise api_error(400, "KNOWLEDGE_QUERY_REQUIRED", "请输入要查询的问题。")
    actor_id = actor["id"]
    conversation = _get_or_create_conversation(project_id, actor_id, request.conversation_id, question)
    history = _conversation_history(conversation["id"])
    input_data, source_version_ids, exploration_run_ids, blockers = _collect_query_input(project_id, request, history)
    if blockers:
        answer = "无法查询项目知识库：\n\n" + "\n".join(f"- {item}" for item in blockers)
        output = KnowledgeQueryOutput(answer=answer)
    else:
        try:
            output = await knowledge_query_service.run_knowledge_query(input_data)
        except Exception:
            output = _fallback_query_output(input_data)

    user_message, assistant_message = _append_query_messages(
        conversation["id"],
        question,
        output,
        output.used_requirement_versions or source_version_ids,
        output.used_exploration_runs or exploration_run_ids,
    )
    operation_log_service.record_success(
        module="knowledge",
        action="query",
        object_type="project_knowledge",
        object_id=project_id,
        object_name=input_data.project_name,
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary="查询项目知识库。",
        after={
            "question": question,
            "conversation_id": conversation["id"],
            "source_versions": source_version_ids,
            "exploration_runs": exploration_run_ids,
        },
    )
    return {
        "conversation": _conversation_to_schema(conversation).model_dump(),
        "messages": [_message_to_schema(user_message).model_dump(), _message_to_schema(assistant_message).model_dump()],
        "answer": output.answer,
        "source_refs": [ref.model_dump() for ref in output.source_refs],
        "used_requirement_versions": output.used_requirement_versions or source_version_ids,
        "used_exploration_runs": output.used_exploration_runs or exploration_run_ids,
    }


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
    history: list[KnowledgeConversationHistoryMessage] | None = None,
) -> tuple[KnowledgeQueryInput, list[str], list[str], list[str]]:
    with connect() as db:
        project = _require_project(db, project_id)

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
                        document_id=doc["id"],
                        document_name=doc["name"],
                        version_id=version["id"],
                        version_no=version["version_no"],
                        markdown_content=markdown_path.read_text(encoding="utf-8"),
                    )
                )

        explorations: list[KnowledgeExplorationInput] = []
        exploration_run_ids: list[str] = []
        if request.include_explorations:
            for run in exploration_repo.list_by_project(db, project_id):
                if run["status"] not in READY_EXPLORATION_STATUSES:
                    continue
                exploration_run_ids.append(run["id"])
                artifact_pages, artifact_elements, artifact_blockers = exploration_service._load_run_artifacts(run)
                modules = []
                for module in exploration_repo.list_module_coverages(db, run["id"]):
                    module_dict = dict(module)
                    module_dict["pages"] = [page for page in artifact_pages if page["module_key"] == module["module_key"]]
                    module_dict["elements"] = [
                        element for element in artifact_elements if element["module_key"] == module["module_key"]
                    ]
                    module_dict["blockers"] = [
                        blocker for blocker in artifact_blockers if blocker["module_key"] == module["module_key"]
                    ]
                    modules.append(module_dict)
                explorations.append(
                    KnowledgeExplorationInput(
                        exploration_run_id=run["id"],
                        title=run["title"],
                        status=run["status"],
                        result_summary=run["result_summary"],
                        modules=modules,
                    )
                )

    if not source_documents and not explorations:
        if request.include_requirements:
            blockers.append("当前项目没有可用于查询的最终需求文档版本。")
        if request.include_explorations:
            blockers.append("当前项目没有已完成或部分完成的探索结果。")
        if not request.include_requirements and not request.include_explorations:
            blockers.append("项目知识库查询至少需要最终需求文档，或已完成/部分完成的探索结果。")
    return (
        KnowledgeQueryInput(
            project_id=project_id,
            project_name=project["name"],
            question=request.question.strip(),
            conversation_history=history or [],
            source_documents=source_documents,
            explorations=explorations,
        ),
        source_version_ids,
        exploration_run_ids,
        blockers,
    )


def _require_project(db, project_id: str):
    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "PROJECT_NOT_FOUND", "项目不存在。")
    return project


def _get_or_create_conversation(project_id: str, actor_id: str, conversation_id: str | None, question: str):
    with connect() as db:
        _require_project(db, project_id)
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


def _conversation_history(conversation_id: str) -> list[KnowledgeConversationHistoryMessage]:
    with connect() as db:
        rows = knowledge_conversation_repo.list_messages(db, conversation_id)
    recent_rows = rows[-MAX_HISTORY_MESSAGES:]
    return [
        KnowledgeConversationHistoryMessage(role=row["role"], content=row["content"])
        for row in recent_rows
        if row["content"].strip()
    ]


def _append_query_messages(
    conversation_id: str,
    question: str,
    output: KnowledgeQueryOutput,
    used_requirement_versions: list[str],
    used_exploration_runs: list[str],
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
            content=output.answer,
            source_refs=[ref.model_dump() for ref in output.source_refs],
            used_requirement_versions=used_requirement_versions,
            used_exploration_runs=used_exploration_runs,
        )
    return user_message, assistant_message


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
        source_refs=[KnowledgeSourceRef.model_validate(item) for item in _loads_json_array(row["source_refs_json"])],
        used_requirement_versions=[str(item) for item in _loads_json_array(row["used_requirement_versions_json"])],
        used_exploration_runs=[str(item) for item in _loads_json_array(row["used_exploration_runs_json"])],
        created_at=row["created_at"],
    )


def _loads_json_array(value: str) -> list:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _fallback_query_output(input_data: KnowledgeQueryInput) -> KnowledgeQueryOutput:
    terms = [term for term in re.split(r"\s+", input_data.question.strip()) if len(term) >= 2]
    refs: list[KnowledgeSourceRef] = []
    sections: list[str] = []
    for doc in input_data.source_documents:
        excerpt = _matching_excerpt(doc.markdown_content, terms) or _first_non_empty_line(doc.markdown_content)
        if not excerpt:
            continue
        refs.append(
            KnowledgeSourceRef(
                source_type="requirement",
                source_id=doc.version_id,
                source_title=f"{doc.document_name} v{doc.version_no}",
                location="最终需求文档",
                excerpt=excerpt,
            )
        )
        sections.append(f"- 需求「{doc.document_name} v{doc.version_no}」：{excerpt}")
    for exploration in input_data.explorations:
        excerpt = _matching_excerpt(json.dumps(exploration.model_dump(), ensure_ascii=False), terms) or exploration.result_summary
        if not excerpt:
            continue
        refs.append(
            KnowledgeSourceRef(
                source_type="exploration",
                source_id=exploration.exploration_run_id,
                source_title=exploration.title,
                location="探索记录",
                excerpt=excerpt,
            )
        )
        sections.append(f"- 探索「{exploration.title}」：{excerpt}")
    if not sections:
        answer = "没有在当前最终需求文档或探索记录中找到足够依据回答该问题。请补充更具体的模块、页面或业务关键词。"
    else:
        answer = "Codex agentic search 暂不可用，已基于当前来源做确定性检索摘要：\n\n" + "\n".join(sections[:12])
    return KnowledgeQueryOutput(
        answer=answer,
        source_refs=refs[:12],
        used_requirement_versions=[doc.version_id for doc in input_data.source_documents],
        used_exploration_runs=[item.exploration_run_id for item in input_data.explorations],
    )


def _first_non_empty_line(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip().strip("#").strip()
        if stripped:
            return stripped[:160]
    return ""


def _matching_excerpt(text: str, terms: list[str]) -> str:
    lines = [line.strip().strip("#").strip() for line in text.splitlines()]
    for line in lines:
        if not line:
            continue
        if not terms or any(term in line for term in terms):
            return line[:240]
    return ""
