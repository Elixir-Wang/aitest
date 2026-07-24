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
    if missing_obligation_keys == []:
        raise ValueError("当前没有需要补生成的需求义务。")
    obligation_by_key = {item.obligation_key: item for item in obligations}
    target_keys = (
        [item.obligation_key for item in obligations]
        if missing_obligation_keys is None
        else list(dict.fromkeys(missing_obligation_keys))
    )
    unknown_target_keys = sorted(set(target_keys) - set(obligation_by_key))
    if unknown_target_keys:
        raise ValueError(f"补生成包含不存在的需求义务 ID：{', '.join(unknown_target_keys)}")
    target_obligations = [obligation_by_key[key] for key in target_keys]
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
                    for item in target_obligations
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
            "测试点名称规则:",
            "test_point 只写简短、可区分的测试目标，不得拼接完整 module 或模块层级路径；相同行为涉及不同对象时，用最短业务对象自然区分；名称在全部已生成和本轮测试点中必须唯一。",
            "",
            "本轮仅需补齐的义务 ID:",
            json.dumps(missing_obligation_keys if missing_obligation_keys is not None else [], ensure_ascii=False),
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
    _validate_generation_result(
        generation_result,
        obligations,
        existing_points=existing_points,
    )
    return generation_result


def _enrich_drafts(
    drafts: list[GeneratedTestPointDraft],
    *,
    obligations: list[RequirementObligation],
    missing_obligation_keys: list[str] | None,
) -> list[GeneratedTestPoint]:
    obligation_by_key = {item.obligation_key: item for item in obligations}
    target_keys = (
        [item.obligation_key for item in obligations]
        if missing_obligation_keys is None
        else missing_obligation_keys
    )
    target_key_set = set(target_keys)
    enriched_by_key: dict[str, GeneratedTestPoint] = {}
    for draft in drafts:
        matching = list(dict.fromkeys(draft.requirement_obligation_keys))
        invalid_keys = sorted(set(matching) - target_key_set)
        if invalid_keys:
            raise ValueError(f"模型关联了本轮范围外的需求义务 ID：{', '.join(invalid_keys)}")
        linked_modules = {
            module.strip()
            for key in matching
            for module in obligation_by_key[key].modules
            if module.strip()
        }
        if len(linked_modules) > 1:
            raise ValueError("同一测试点不能关联多个不同模块的需求义务。")
        module = next(iter(linked_modules), draft.module.strip())
        test_point = draft.test_point.strip()
        point_key = "tp-" + hashlib.sha1(f"{module}\n{test_point}".encode()).hexdigest()[:16]
        existing = enriched_by_key.get(point_key)
        if existing is not None:
            enriched_by_key[point_key] = existing.model_copy(
                update={
                    "requirement_obligation_keys": list(
                        dict.fromkeys(existing.requirement_obligation_keys + matching)
                    )
                }
            )
            continue
        enriched_by_key[point_key] = GeneratedTestPoint(
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
    return list(enriched_by_key.values())


def _validate_generation_result(
    result: TestPointGenerationResult,
    obligations: list[RequirementObligation],
    *,
    existing_points: list[GeneratedTestPoint] | None = None,
) -> None:
    point_keys = [point.point_key for point in result.points]
    duplicate_keys = sorted({key for key in point_keys if point_keys.count(key) > 1})
    if duplicate_keys:
        raise ValueError(f"模型返回了重复的测试点 key：{', '.join(duplicate_keys)}")

    all_points = [*(existing_points or []), *result.points]
    title_identities = [_title_identity(point.title) for point in all_points]
    duplicate_titles = sorted(
        {
            point.title
            for point, identity in zip(all_points, title_identities, strict=True)
            if title_identities.count(identity) > 1
        }
    )
    if duplicate_titles:
        raise ValueError(f"模型返回了重复的测试点标题：{', '.join(duplicate_titles)}")

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


def _title_identity(title: str) -> str:
    return " ".join(title.split()).casefold()


__all__ = ["generate_test_points"]
