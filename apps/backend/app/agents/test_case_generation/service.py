"""测试用例生成服务层"""

import asyncio
import secrets

from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.agents.test_case_generation.agent import test_case_generation_agent
from app.agents.test_case_generation.conflict import check_generated_case_conflicts
from app.agents.test_case_generation.schemas import (
    TestCaseGenerationInput,
    TestCaseGenerationResult,
    TestCaseModule,
)


CAPABILITY_ID = "test_case_generation"
TEST_POINT_BATCH_SIZE = 5
MAX_CONCURRENT_BATCHES = 3


async def generate_test_cases(input_data: TestCaseGenerationInput) -> TestCaseGenerationResult:
    """
    测试用例生成核心函数

    Args:
        input_data: 测试用例生成输入

    Returns:
        测试用例生成结果

    Raises:
        ValueError: 需求内容为空或 Agent 未返回结构化结果
    """
    # 验证输入
    if not input_data.requirement_content.strip():
        raise ValueError("需求内容为空，无法生成测试用例。")

    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
    test_point_batches = _partition_test_points(input_data.test_points)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_BATCHES)

    async def generate_batch(batch_number: int, test_points: list[dict]) -> TestCaseGenerationResult:
        async with semaphore:
            content = _build_generation_content(
                input_data,
                test_points=test_points,
                batch_number=batch_number,
                batch_count=len(test_point_batches),
            )
            agent = test_case_generation_agent(model)
            result = await agent.ainvoke({"messages": [{"role": "user", "content": content}]})
            generated = _coerce_generation_result(result)
            references = _references_for_batch(input_data, test_points)
            if not references:
                return generated
            first_check = await check_generated_case_conflicts(model, generated, references)
            if not first_check.conflicts:
                return generated

            retry_content = "\n".join(
                [
                    content,
                    "",
                    "上一次候选用例仍命中以下历史不采纳问题。请重新生成本批次并逐项消除冲突：",
                    *(
                        f"- 候选 {conflict.generated_case_id} 与 {conflict.record_id} 冲突：{conflict.explanation}"
                        for conflict in first_check.conflicts
                    ),
                ]
            )
            retry_result = await agent.ainvoke({"messages": [{"role": "user", "content": retry_content}]})
            retried = _coerce_generation_result(retry_result)
            second_check = await check_generated_case_conflicts(model, retried, references)
            uncorrected = [item for item in second_check.conflicts if item.conflict_type == "uncorrected"]
            if uncorrected:
                raise ValueError("生成用例在重试后仍未按历史不采纳原因修正。")
            duplicate_ids = {
                item.generated_case_id for item in second_check.conflicts if item.conflict_type == "duplicate"
            }
            return _without_cases(retried, duplicate_ids)

    batch_results = await asyncio.gather(
        *(
            generate_batch(batch_number, test_points)
            for batch_number, test_points in enumerate(test_point_batches, start=1)
        )
    )
    return _merge_batch_results(batch_results, test_point_count=len(input_data.test_points))


def _build_generation_content(
    input_data: TestCaseGenerationInput,
    *,
    test_points: list[dict],
    batch_number: int,
    batch_count: int,
) -> str:
    content_parts = [
        f"需求名称: {input_data.requirement_name}",
        "",
        "最终需求文档:",
        input_data.requirement_content,
    ]

    # 添加生成范围
    if input_data.generation_scope:
        content_parts.append("")
        content_parts.append(f"生成范围: {input_data.generation_scope}")

    if test_points:
        content_parts.append("")
        if batch_count > 1:
            content_parts.append(
                f"当前为第 {batch_number}/{batch_count} 批。仅生成下列本批次测试点对应的用例，"
                "不要扩展到其他测试点或模块。"
            )
        content_parts.append("本批次测试点（必须逐项覆盖；测试点未明确的业务规则不得编造）:")
        for index, point in enumerate(test_points, 1):
            content_parts.append(
                f"{index}. [{point.get('point_key', '')}] {point.get('title', '')} "
                f"模块={point.get('module', '')} 类型={point.get('category', '')} 优先级={point.get('priority', '')}"
            )
            content_parts.append(f"   描述: {point.get('description', '')}")
            for verification in point.get("verification_points", []):
                content_parts.append(f"   验证点: {verification}")

    references = _references_for_batch(input_data, test_points)
    if references:
        content_parts.append("")
        content_parts.append("Agentic Search 命中的历史不采纳记录（当前最终需求优先于历史记录）:")
        for index, reference in enumerate(references, 1):
            instruction = {
                "block_duplicate": "不得生成语义等价场景",
                "generate_with_correction": "场景可生成，但必须按处理建议修正",
                "warning_only": "仅作为提醒，不得删除当前需求明确要求的测试点",
            }[reference.handling]
            content_parts.append(f"{index}. [{reference.record_id}] {reference.title}")
            content_parts.append(f"   模块: {reference.module or '未指定'}")
            content_parts.append(f"   不采纳原因: {reference.reason}")
            content_parts.append(f"   处理规则: {instruction}")
            if reference.correction:
                content_parts.append(f"   处理建议: {reference.correction}")

    content_parts.append("\n请使用 test-case-generation skill 生成测试用例集。")
    return "\n".join(content_parts)


def _references_for_batch(input_data: TestCaseGenerationInput, test_points: list[dict]):
    point_keys = {str(point.get("point_key", "")) for point in test_points}
    modules = {str(point.get("module", "")).strip() for point in test_points}
    selected = []
    for reference in input_data.rejected_case_references:
        if point_keys.intersection(reference.matched_test_point_keys) or (
            not reference.matched_test_point_keys and reference.module.strip() in modules
        ):
            selected.append(reference)
    selected.sort(key=lambda item: (item.relevance != "high", item.record_id))
    return selected[:10]


def _coerce_generation_result(result) -> TestCaseGenerationResult:
    if not isinstance(result, dict):
        raise ValueError("测试用例生成智能体输出格式不正确。")

    generation_result = result.get("structured_response")

    if not generation_result:
        raise ValueError("测试用例生成智能体未返回结构化结果。")

    if isinstance(generation_result, TestCaseGenerationResult):
        return generation_result
    if isinstance(generation_result, dict):
        return TestCaseGenerationResult.model_validate(generation_result)
    if isinstance(generation_result, str):
        return TestCaseGenerationResult.model_validate_json(generation_result)
    raise ValueError(f"测试用例生成智能体输出类型不支持: {type(generation_result).__name__}")


def _partition_test_points(test_points: list[dict]) -> list[list[dict]]:
    if not test_points:
        return [[]]

    points_by_module: dict[str, list[dict]] = {}
    for point in test_points:
        module = str(point.get("module", "")).strip()
        points_by_module.setdefault(module, []).append(point)

    return [
        module_points[index:index + TEST_POINT_BATCH_SIZE]
        for module_points in points_by_module.values()
        for index in range(0, len(module_points), TEST_POINT_BATCH_SIZE)
    ]


def _merge_batch_results(
    batch_results: list[TestCaseGenerationResult],
    *,
    test_point_count: int,
) -> TestCaseGenerationResult:
    if len(batch_results) == 1:
        return batch_results[0]

    cases_by_module: dict[str, list] = {}
    for batch_result in batch_results:
        for module in batch_result.modules:
            cases_by_module.setdefault(module.module_name, []).extend(module.test_cases)

    next_case_number = 1
    modules = []
    for module_name, test_cases in cases_by_module.items():
        renumbered_cases = []
        for test_case in test_cases:
            renumbered_cases.append(
                test_case.model_copy(update={"id": f"tc-{next_case_number:03d}"})
            )
            next_case_number += 1
        modules.append(TestCaseModule(module_name=module_name, test_cases=renumbered_cases))

    total_count = next_case_number - 1
    summary = (
        f"已分 {len(batch_results)} 个批次生成并合并 {total_count} 条测试用例，"
        f"覆盖 {test_point_count} 个测试点。"
    )
    return TestCaseGenerationResult(summary=summary, total_count=total_count, modules=modules)


def _without_cases(result: TestCaseGenerationResult, case_ids: set[str]) -> TestCaseGenerationResult:
    if not case_ids:
        return result
    modules = [
        module.model_copy(update={"test_cases": [case for case in module.test_cases if case.id not in case_ids]})
        for module in result.modules
    ]
    total_count = sum(len(module.test_cases) for module in modules)
    return result.model_copy(update={"modules": modules, "total_count": total_count})


def next_generation_id() -> str:
    """生成下一个测试用例生成 ID"""
    return f"tcgen-{secrets.token_hex(8)}"


__all__ = [
    "generate_test_cases",
    "next_generation_id",
]
