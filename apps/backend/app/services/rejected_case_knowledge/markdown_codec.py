import json
import re
from datetime import UTC, datetime

import yaml

from app.services.rejected_case_knowledge.schemas import RejectedCaseRecord

SCHEMA = "rejected-test-case-library/v1"
_BLOCK_PATTERN = re.compile(
    r"<!-- rejected_case:start (?P<meta>\{.*?\}) -->\n"
    r"(?P<body>.*?)"
    r"<!-- rejected_case:end -->",
    re.DOTALL,
)
_DATA_PATTERN = re.compile(r"<!-- rejected_case:data (?P<data>\{.*\}) -->")


def parse_document(content: str) -> tuple[dict, list[RejectedCaseRecord]]:
    if not content.strip():
        return {}, []
    header, _ = _split_front_matter(content)
    if header.get("schema") != SCHEMA:
        raise ValueError("不采纳用例知识文件 schema 无效。")

    records: list[RejectedCaseRecord] = []
    seen: set[str] = set()
    for match in _BLOCK_PATTERN.finditer(content):
        metadata = json.loads(match.group("meta"))
        data_match = _DATA_PATTERN.search(match.group("body"))
        if not data_match:
            raise ValueError("不采纳用例知识条目缺少结构化数据。")
        record = RejectedCaseRecord.model_validate_json(data_match.group("data"))
        if metadata.get("record_id") != record.record_id:
            raise ValueError("不采纳用例知识条目 ID 不一致。")
        if record.record_id in seen:
            raise ValueError(f"不采纳用例知识条目重复：{record.record_id}")
        seen.add(record.record_id)
        records.append(record)

    if content.count("<!-- rejected_case:start ") != len(records) or content.count("<!-- rejected_case:end -->") != len(records):
        raise ValueError("不采纳用例知识条目边界不完整。")
    return header, records


def render_document(
    *,
    project_id: str,
    project_name: str,
    requirement_id: str,
    requirement_name: str,
    records: list[RejectedCaseRecord],
    updated_at: str | None = None,
) -> str:
    now = updated_at or datetime.now(UTC).isoformat()
    header = yaml.safe_dump(
        {
            "schema": SCHEMA,
            "project_id": project_id,
            "project_name": project_name,
            "requirement_id": requirement_id,
            "requirement_name": requirement_name,
            "updated_at": now,
        },
        allow_unicode=True,
        sort_keys=False,
    ).strip()
    active_count = sum(record.status == "active" for record in records)
    sections = [
        f"---\n{header}\n---",
        f"# {requirement_name}",
        f"{project_name} · **{active_count} 条有效反馈**",
    ]
    sections.extend(_render_record(record, index) for index, record in enumerate(records, 1))
    return "\n\n".join(sections).rstrip() + "\n"


def upsert_record(content: str, record: RejectedCaseRecord) -> str:
    _, records = parse_document(content) if content.strip() else ({}, [])
    by_id = {item.record_id: item for item in records}
    by_id[record.record_id] = record
    ordered = sorted(by_id.values(), key=lambda item: (item.reviewed_at, item.record_id), reverse=True)
    return render_document(
        project_id=record.project_id,
        project_name=record.project_name,
        requirement_id=record.requirement_id,
        requirement_name=record.requirement_name,
        records=ordered,
    )


def deactivate(content: str, record_id: str, *, deactivated_at: str) -> tuple[str, RejectedCaseRecord | None]:
    header, records = parse_document(content)
    changed = None
    updated = []
    for record in records:
        if record.record_id == record_id:
            changed = record.model_copy(update={"status": "inactive", "deactivated_at": deactivated_at})
            updated.append(changed)
        else:
            updated.append(record)
    if changed is None:
        return content, None
    return (
        render_document(
            project_id=str(header["project_id"]),
            project_name=str(header["project_name"]),
            requirement_id=str(header["requirement_id"]),
            requirement_name=str(header["requirement_name"]),
            records=updated,
        ),
        changed,
    )


def _split_front_matter(content: str) -> tuple[dict, str]:
    if not content.startswith("---\n"):
        raise ValueError("不采纳用例知识文件缺少 front matter。")
    end = content.find("\n---\n", 4)
    if end < 0:
        raise ValueError("不采纳用例知识文件 front matter 不完整。")
    header = yaml.safe_load(content[4:end])
    if not isinstance(header, dict):
        raise ValueError("不采纳用例知识文件 front matter 无效。")  # noqa: TRY004
    return header, content[end + 5 :]


def _render_record(record: RejectedCaseRecord, index: int) -> str:
    status = "有效" if record.status == "active" else "已失效"
    metadata = json.dumps({"record_id": record.record_id, "schema": "v1"}, ensure_ascii=False, separators=(",", ":"))
    data = record.model_dump_json(ensure_ascii=False)
    lines = [
        f"<!-- rejected_case:start {metadata} -->",
        f"<!-- rejected_case:data {data} -->",
        f"## {index}. {record.title}",
        "",
        " · ".join(
            [
                status,
                record.module or "未指定模块",
                record.priority or "未指定优先级",
                f"V{record.requirement_version_no}" if record.requirement_version_no else "版本未知",
            ]
        ),
        "",
        *_reason_lines(_display_reason(record.reason)),
        "<!-- rejected_case:end -->",
    ]
    return "\n".join(lines)


def _reason_lines(value: str) -> list[str]:
    lines = value.splitlines() or ["未提供具体原因。"]
    return [f"> **不采纳原因：** {lines[0]}", *[f"> {line}" for line in lines[1:]]]


def _display_reason(value: str) -> str:
    return "未提供具体原因。" if _is_empty_feedback(value) else value


def _is_empty_feedback(value: str) -> bool:
    return value.strip().lower() in {"", "无", "无。", "none", "n/a"}
