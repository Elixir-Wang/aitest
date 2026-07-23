from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.agents.test_point_generation.agent import test_point_generation_agent
import hashlib
import json

from app.agents.test_point_generation.schemas import (
    GeneratedTestPoint,
    GeneratedTestPointDraft,
    RequirementObligation,
    TestPointGenerationInput,
    TestPointGenerationDraftResult,
    TestPointGenerationResult,
)


CAPABILITY_ID = "test_point_generation"


async def generate_test_points(
    input_data: TestPointGenerationInput,
    *,
    obligations: list[RequirementObligation],
    existing_points: list[GeneratedTestPoint] | None = None,
    missing_obligation_keys: list[str] | None = None,
) -> TestPointGenerationResult:
    if not input_data.requirement_content.strip():
        raise ValueError("最终需求内容为空，无法生成测试点。")
    content = "\n".join(
        [
            f"需求名称: {input_data.requirement_name}",
            f"最终需求版本 ID: {input_data.requirement_version_id}",
            "",
            "最终需求文档:",
            input_data.requirement_content,
            "",
            "必须覆盖的最终需求义务:",
            json.dumps(
                [
                    {
                        "obligation_key": item.obligation_key,
                        "module": item.modules[0] if item.modules else "",
                        "statement": item.statement,
                    }
                    for item in obligations
                ],
                ensure_ascii=False,
            ),
            "",
            "已生成测试点:",
            json.dumps(
                [{"module": item.module, "test_point": item.title, "priority": item.priority} for item in existing_points or []],
                ensure_ascii=False,
            ),
            "",
            "本轮仅需补齐的义务 ID:",
            json.dumps(missing_obligation_keys or [], ensure_ascii=False),
            "",
            "请使用 test-point-generation skill 生成结构化测试点。",
        ]
    )
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
    result = await test_point_generation_agent(model).ainvoke({"messages": [{"role": "user", "content": content}]})
    if not isinstance(result, dict) or not result.get("structured_response"):
        raise ValueError("测试点生成智能体未返回结构化结果。")
    structured = result["structured_response"]
    draft_result = (
        structured
        if isinstance(structured, TestPointGenerationDraftResult)
        else TestPointGenerationDraftResult.model_validate(structured)
    )
    generation_result = TestPointGenerationResult(
        points=_enrich_drafts(
            draft_result.points,
            obligations=obligations,
            missing_obligation_keys=missing_obligation_keys,
        )
    )
    _validate_generation_result(generation_result, obligations)
    return generation_result


def _enrich_drafts(
    drafts: list[GeneratedTestPointDraft],
    *,
    obligations: list[RequirementObligation],
    missing_obligation_keys: list[str] | None,
) -> list[GeneratedTestPoint]:
    obligation_by_key = {item.obligation_key: item for item in obligations}
    target_keys = missing_obligation_keys or [item.obligation_key for item in obligations]
    assigned: set[str] = set()
    enriched: list[GeneratedTestPoint] = []
    for draft in drafts:
        module = draft.module.strip()
        matching = [
            key for key in target_keys
            if key not in assigned and module in obligation_by_key[key].modules
        ]
        if not matching:
            matching = [key for key in target_keys if key not in assigned][:1]
        if not matching:
            # Ignore extra model rows once this supplement's obligations are covered.
            continue
        assigned.update(matching)
        test_point = draft.test_point.strip()
        point_key = "tp-" + hashlib.sha1(f"{module}\n{test_point}".encode()).hexdigest()[:16]
        enriched.append(
            GeneratedTestPoint(
                point_key=point_key,
                title=test_point,
                module=module,
                category="功能",
                priority=draft.priority,
                description=test_point,
                preconditions=[],
                verification_points=[test_point],
                source_refs=["最终需求"],
                notes="",
                requirement_obligation_keys=matching,
            )
        )
    return enriched


def _validate_generation_result(
    result: TestPointGenerationResult,
    obligations: list[RequirementObligation],
) -> None:
    point_keys = [point.point_key for point in result.points]
    duplicate_keys = sorted({key for key in point_keys if point_keys.count(key) > 1})
    if duplicate_keys:
        raise ValueError(f"模型返回了重复的测试点 key：{', '.join(duplicate_keys)}")

    obligation_keys = {obligation.obligation_key for obligation in obligations}
    unknown_keys = sorted(
        {
            key
            for point in result.points
            for key in point.requirement_obligation_keys
            if key not in obligation_keys
        }
    )
    if unknown_keys:
        raise ValueError(f"模型返回了不存在的需求义务 ID：{', '.join(unknown_keys)}")


__all__ = ["generate_test_points"]
