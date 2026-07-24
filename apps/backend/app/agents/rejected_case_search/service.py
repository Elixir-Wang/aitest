import json

from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.agents.rejected_case_search.agent import rejected_case_search_agent
from app.agents.rejected_case_search.schemas import (
    RejectedCaseReference,
    RejectedCaseSearchInput,
    RejectedCaseSearchResult,
)


CAPABILITY_ID = "test_case_generation"


async def search_rejected_cases(input_data: RejectedCaseSearchInput) -> RejectedCaseSearchResult:
    if not input_data.source_documents:
        return RejectedCaseSearchResult()
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
    result = await rejected_case_search_agent(model).ainvoke(_payload(input_data))
    structured = result.get("structured_response") if isinstance(result, dict) else None
    if isinstance(structured, RejectedCaseSearchResult):
        output = structured
    elif isinstance(structured, dict):
        output = RejectedCaseSearchResult.model_validate(structured)
    elif isinstance(structured, str):
        output = RejectedCaseSearchResult.model_validate_json(structured)
    else:
        raise ValueError("不采纳用例检索 Agent 未返回结构化结果。")
    return _validate_references(input_data, output)


def _payload(input_data: RejectedCaseSearchInput) -> dict:
    files = {
        "/README.md": _file_data(
            "# 不采纳用例检索清单\n\n"
            "本次只允许搜索 /rejected-cases/ 下文件。当前最终需求优先于历史不采纳记录。\n"
            + "\n".join(
                f"- `/rejected-cases/{input_data.project_id}/{document.file_name}`: {document.file_id}"
                for document in input_data.source_documents
            )
        )
    }
    for document in input_data.source_documents:
        metadata = json.dumps(
            {"source_file_id": document.file_id, "source_file_name": document.file_name},
            ensure_ascii=False,
        )
        files[f"/rejected-cases/{input_data.project_id}/{document.file_name}"] = _file_data(
            f"<!-- source_metadata: {metadata} -->\n\n{document.markdown_content}"
        )
    test_points = "\n".join(
        f"- [{point.point_key}] {point.title}；模块={point.module}；描述={point.description}；验证点={'；'.join(point.verification_points)}"
        for point in input_data.test_points
    ) or "无结构化测试点。"
    message = "\n".join(
        [
            f"当前项目：{input_data.project_name}（{input_data.project_id}）",
            f"当前需求：{input_data.requirement_name}（{input_data.requirement_id}，v{input_data.requirement_version_no}）",
            f"生成范围：{input_data.generation_scope or '全部'}",
            "",
            "当前测试点：",
            test_points,
            "",
            "当前最终需求：",
            input_data.requirement_content,
            "",
            "请检索虚拟文件并返回直接相关的有效历史不采纳记录。",
        ]
    )
    return {"messages": [{"role": "user", "content": message}], "files": files}


def _file_data(content: str) -> dict[str, str]:
    return {"content": content, "encoding": "utf-8"}


def _validate_references(
    input_data: RejectedCaseSearchInput,
    output: RejectedCaseSearchResult,
) -> RejectedCaseSearchResult:
    points = {point.point_key for point in input_data.test_points}
    records = {
        record.record_id: (document, record)
        for document in input_data.source_documents
        for record in document.records
        if record.status == "active"
    }
    validated: list[RejectedCaseReference] = []
    per_point: dict[str, int] = {}
    seen: set[str] = set()
    for reference in output.matches:
        source = records.get(reference.record_id)
        if not source:
            raise ValueError(f"检索结果引用了不存在或已失效的记录：{reference.record_id}")
        document, record = source
        if reference.source_file_id != document.file_id:
            raise ValueError(f"检索结果文件来源不一致：{reference.record_id}")
        matched_keys = [key for key in reference.matched_test_point_keys if key in points]
        accepted_keys = []
        for key in matched_keys[:5]:
            if per_point.get(key, 0) >= 5:
                continue
            per_point[key] = per_point.get(key, 0) + 1
            accepted_keys.append(key)
        if reference.record_id in seen:
            continue
        seen.add(reference.record_id)
        validated.append(
            reference.model_copy(
                update={
                    "source_file_name": document.file_name,
                    "source_requirement_id": record.requirement_id,
                    "source_requirement_version": str(record.requirement_version_no or "unknown"),
                    "matched_test_point_keys": accepted_keys,
                    "title": record.title,
                    "module": record.module,
                    "reason_type": record.reason_type,
                    "reason": record.reason,
                    "handling": record.handling,
                    "correction": record.correction,
                }
            )
        )
    return RejectedCaseSearchResult(matches=validated[:20])
