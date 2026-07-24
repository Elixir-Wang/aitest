import hashlib
import re
import secrets
import threading
from datetime import UTC, datetime

from app.core import settings
from app.core.db import connect
from app.repositories import global_knowledge_repo
from app.services.knowledge import global_service
from app.services.rejected_case_knowledge.markdown_codec import (
    deactivate,
    parse_document,
    upsert_record,
)
from app.services.rejected_case_knowledge.schemas import (
    RejectedCaseKnowledgeDocument,
    RejectedCaseRecord,
)

KNOWLEDGE_BASE_NAME = "不采纳用例库"
KNOWLEDGE_BASE_DESCRIPTION = "测试用例评审中未采纳的用例及原因，由系统自动维护。"
_DIRECTORY_LOCK = threading.Lock()


def derive_record_id(project_id: str, requirement_id: str, generation_run_id: str, case_id: str) -> str:
    value = f"{project_id}|{requirement_id}|{generation_run_id}|{case_id}".encode()
    return f"rjc-{hashlib.sha256(value).hexdigest()[:16]}"


def upsert_rejected_case(
    *,
    project,
    requirement,
    requirement_version,
    generation_run_id: str,
    test_case_set_id: str,
    test_case: dict,
    reason: str,
    actor,
) -> dict:
    base_id, project_folder = _ensure_project_folder(project, actor)
    _, file_name, content = _requirement_file_state(
        base_id,
        project_folder["id"],
        requirement["id"],
        requirement["name"],
    )
    reason_type, handling = _classify_reason(reason)
    record = RejectedCaseRecord(
        record_id=derive_record_id(project["id"], requirement["id"], generation_run_id, test_case["id"]),
        project_id=project["id"],
        project_name=project["name"],
        requirement_id=requirement["id"],
        requirement_name=requirement["name"],
        requirement_version_id=requirement_version["id"],
        requirement_version_no=requirement_version["version_no"],
        generation_run_id=generation_run_id,
        test_case_set_id=test_case_set_id,
        test_case_id=test_case["id"],
        title=test_case["title"],
        module=test_case["module"],
        priority=test_case["priority"],
        preconditions=test_case["preconditions"],
        steps=test_case.get("steps", []),
        expected_result=test_case["expected_result"],
        reason_type=reason_type,
        reason=reason,
        handling=handling,
        correction=reason,
        reviewed_by=actor["id"],
        reviewed_at=datetime.now(UTC).isoformat(),
    )
    updated_content = upsert_record(content, record)
    saved = global_service.upsert_markdown_file(
        base_id,
        project_folder["id"],
        display_name=file_name,
        markdown_content=updated_content,
        actor=actor,
    )
    return {
        "record_id": record.record_id,
        "file_id": saved["id"],
        "file_name": saved["display_name"],
        "status": "active",
    }


def deactivate_record(
    *,
    project,
    requirement,
    generation_run_id: str,
    case_id: str,
    actor,
) -> dict | None:
    base_id = _configured_base_id()
    if not base_id:
        return None
    project_folder = _find_project_folder(base_id, project["id"])
    if not project_folder:
        return None
    file_row = _find_requirement_file(project_folder["id"], requirement["id"])
    if not file_row:
        return None
    content = _read_file_content(file_row)
    record_id = derive_record_id(project["id"], requirement["id"], generation_run_id, case_id)
    updated, changed = deactivate(content, record_id, deactivated_at=datetime.now(UTC).isoformat())
    if changed is None:
        return None
    saved = global_service.upsert_markdown_file(
        base_id,
        project_folder["id"],
        display_name=file_row["display_name"],
        markdown_content=updated,
        actor=actor,
    )
    return {
        "record_id": record_id,
        "file_id": saved["id"],
        "file_name": saved["display_name"],
        "status": "inactive",
    }


def collect_project_documents(project_id: str) -> list[RejectedCaseKnowledgeDocument]:
    base_id = _configured_base_id()
    if not base_id:
        return []
    project_folder = _find_project_folder(base_id, project_id)
    if not project_folder:
        return []
    with connect() as db:
        rows = global_knowledge_repo.list_files_by_folder(db, project_folder["id"])
    documents = []
    for row in rows:
        content = _read_file_content(row)
        _, records = parse_document(content)
        documents.append(
            RejectedCaseKnowledgeDocument(
                file_id=row["id"],
                file_name=row["display_name"],
                markdown_content=content,
                records=records,
            )
        )
    return documents


def list_records_for_set(
    project_id: str,
    requirement_id: str,
    test_case_set_id: str,
    generation_run_id: str | None = None,
) -> dict[str, RejectedCaseRecord]:
    try:
        documents = collect_project_documents(project_id)
    except ValueError:
        return {}
    return {
        record.test_case_id: record
        for document in documents
        for record in document.records
        if record.requirement_id == requirement_id and record.test_case_set_id == test_case_set_id
        and (generation_run_id is None or record.generation_run_id == generation_run_id)
    }


def _configured_base_id() -> str | None:
    base_id = settings.REJECTED_CASE_KNOWLEDGE_BASE_ID
    with connect() as db:
        if base_id and not global_knowledge_repo.find_base(db, base_id):
            raise ValueError("配置的不采纳用例知识库不存在。")
        if not base_id:
            base = global_knowledge_repo.find_base_by_name(db, KNOWLEDGE_BASE_NAME)
            base_id = base["id"] if base else None
    return base_id


def _ensure_project_folder(project, actor) -> tuple[str, dict]:
    with _DIRECTORY_LOCK:
        base_id = _configured_base_id()
        if not base_id:
            base = global_service.create_base(
                name=KNOWLEDGE_BASE_NAME,
                description=KNOWLEDGE_BASE_DESCRIPTION,
                actor=actor,
            )
            base_id = base["id"]
        with connect() as db:
            base = global_knowledge_repo.find_base(db, base_id)
        project_folder = _find_project_folder(base_id, project["id"])
        folder_name = _safe_name(project["name"])
        if not project_folder:
            project_folder = global_service.create_folder(
                base_id,
                parent_id=base["root_folder_id"],
                name=folder_name,
                actor=actor,
            )
        elif project_folder["name"] != folder_name:
            with connect() as db:
                global_knowledge_repo.update_folder_name(db, project_folder["id"], folder_name)
                global_knowledge_repo.touch_base(db, base_id)
                project_folder = global_knowledge_repo.find_folder(db, project_folder["id"])
        return base_id, project_folder


def _find_project_folder(base_id: str, project_id: str):
    with connect() as db:
        base = global_knowledge_repo.find_base(db, base_id)
        if not base:
            return None
        folders = global_knowledge_repo.list_child_folders(db, base_id, base["root_folder_id"])
    for folder in folders:
        if folder["name"].startswith(f"{project_id}-"):
            return folder
        with connect() as db:
            files = global_knowledge_repo.list_files_by_folder(db, folder["id"])
        for file_row in files:
            try:
                header, records = parse_document(_read_file_content(file_row))
            except ValueError:
                continue
            if header.get("project_id") == project_id or any(record.project_id == project_id for record in records):
                return folder
    return None


def _requirement_file_state(base_id: str, folder_id: str, requirement_id: str, requirement_name: str):
    row = _find_requirement_file(folder_id, requirement_id)
    if row:
        return row, row["display_name"], _read_file_content(row)
    display_name = f"{_safe_name(requirement_name)}.md"
    with connect() as db:
        conflicting = global_knowledge_repo.find_vault_file_by_folder_and_name(db, folder_id, display_name)
    if conflicting:
        raise ValueError(f"当前项目已存在同名需求知识文件：{display_name}")
    return None, display_name, ""


def _find_requirement_file(folder_id: str, requirement_id: str):
    with connect() as db:
        rows = global_knowledge_repo.list_files_by_folder(db, folder_id)
    for row in rows:
        if row["display_name"].startswith(f"{requirement_id}-"):
            return row
        try:
            header, records = parse_document(_read_file_content(row))
        except ValueError:
            continue
        if header.get("requirement_id") == requirement_id or any(
            record.requirement_id == requirement_id for record in records
        ):
            return row
    return None


def _read_file_content(row) -> str:
    from app.core.storage import resolve_stored_path

    path = resolve_stored_path(row["markdown_path"])
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    return str(row["markdown_content"] or "")


def _classify_reason(reason: str) -> tuple[str, str]:
    if "重复" in reason:
        return "重复用例", "block_duplicate"
    if "已被" in reason and "覆盖" in reason:
        return "已被其他用例覆盖", "block_duplicate"
    if any(keyword in reason for keyword in ("不存在", "不成立", "超出需求", "不支持")):
        return "业务场景不成立", "block_duplicate"
    if any(keyword in reason for keyword in ("缺少", "步骤", "预期", "前置", "不可执行", "不准确", "错误")):
        return "预期结果错误", "generate_with_correction"
    return "其他", "warning_only"


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value.strip()).strip(".-")
    return cleaned[:80] or f"untitled-{secrets.token_hex(4)}"
