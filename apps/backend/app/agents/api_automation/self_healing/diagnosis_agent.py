from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.api_automation.self_healing.schemas import FailureDiagnosis
from app.agents.api_automation.self_healing.schemas import FailureIssue, RepairProposal
from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware
from app.agents.shared.skill_middleware import SkillMiddleware


SYSTEM_PROMPT = """
你是接口自动化失败诊断智能体。只分析，不修改文件。
必须把失败分类为 test_code_issue、test_data_issue、environment_issue、interface_bug、contract_ambiguity 或 unknown。
优先使用用户确认规则、已审批用例、正式接口契约、实际请求响应、历史稳定结果，最后才使用常见约定推断。
接口缺陷只输出证据和定位建议，不修改业务代码。不得为了让测试通过而删除用例、跳过用例或弱化断言。
当 generated_cases 中 oracle_status 为 needs_confirmation 或 inferred，且 generation_notes/notes 的推断与本次实际响应证据冲突或已被响应明确时，可将其分类为 contract_ambiguity 或 test_data_issue，并生成用于同步测试脚本和对应用例数据的 proposal；此时 proposal.target 必须为 test_script、script_repair_allowed 必须为 true。只有证据足够明确才允许这样做，否则只输出诊断结论。
test_code_issue，以及上述证据明确支持修正测试预期的 contract_ambiguity/test_data_issue 才生成 proposal。proposal.proposed_changes 只填写明确的文件路径、函数/代码位置和修改内容，保持简短。
interface_bug、environment_issue 或 unknown 只输出简短诊断结论，不生成 proposal、风险清单或问题清单，也不引导修改测试脚本。
不要为了完整而重复输出状态码、证据、影响用例等信息；只有它们直接决定测试代码修改时才保留。
""".strip()


def create_diagnosis_agent(*, model):
    middleware = [
        SkillMiddleware(
            skill_path=Path(__file__).parent / "skills" / "api-failure-diagnosis",
            load_references=True,
        ),
        InvalidToolCallRecoveryMiddleware(),
    ]
    return create_agent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        response_format=ToolStrategy(FailureDiagnosis),
    )


async def diagnose_failure(*, model, context: dict[str, Any]) -> FailureDiagnosis:
    result = await create_diagnosis_agent(model=model).ainvoke(
        {"messages": [{"role": "user", "content": json.dumps(context, ensure_ascii=False)}]}
    )
    if not isinstance(result, dict) or not result.get("structured_response"):
        raise ValueError("接口自动化失败诊断智能体未返回结构化结果。")
    structured = result["structured_response"]
    if isinstance(structured, FailureDiagnosis):
        return structured
    return FailureDiagnosis.model_validate(structured)


def enforce_uncertain_oracle_policy(diagnosis: FailureDiagnosis, context: dict[str, Any]) -> FailureDiagnosis:
    """Turn an inferred-oracle mismatch into an approval proposal deterministically."""
    cases = {
        str(item.get("case_id")): item
        for item in context.get("generated_cases", [])
        if isinstance(item, dict) and item.get("case_id")
    }
    observations = {
        str(item.get("case_id")): item
        for item in context.get("observations", [])
        if isinstance(item, dict) and item.get("case_id")
    }
    corrections: list[tuple[str, int, int, str]] = []
    for case_id, case in cases.items():
        if case.get("oracle_status") not in {"inferred", "needs_confirmation"}:
            continue
        observation = observations.get(case_id) or {}
        actual = observation.get("status_code")
        if not isinstance(actual, int) or actual >= 500:
            continue
        expected = next(
            (
                assertion.get("expected")
                for assertion in case.get("assertions", [])
                if assertion.get("type") == "status_code" and isinstance(assertion.get("expected"), int)
            ),
            None,
        )
        if isinstance(expected, int) and expected != actual:
            corrections.append((case_id, expected, actual, str(case.get("title") or case_id)))
    if not corrections:
        return diagnosis

    changes = [
        f"cases.yaml: case_id={case_id} ({title}) 的 status_code {expected} -> {actual}；审批后同步测试用例并确认测试预期"
        for case_id, expected, actual, title in corrections
    ]
    issue = FailureIssue(
        failure_ids=[case_id for case_id, _, _, _ in corrections],
        classification="test_data_issue",
        confidence=0.98,
        root_cause="用例状态码来自未确认的生成推断，实际响应已明确返回不同状态码。",
        recommendation="建议按实际响应校准测试用例预期，审批通过后同步脚本数据和数据库用例。",
        repairable=True,
    )
    proposal = RepairProposal(
        target="test_script",
        action="modify_assertion",
        title=f"将 {len(corrections)} 条不确定用例的预期状态码按实际响应校准",
        summary="这些用例的状态码没有正式契约依据，实际响应已提供可复现证据；仅生成候选修改，等待人工审批。",
        confidence=0.98,
        proposed_changes=changes,
        case_updates=[
            {
                "case_id": case_id,
                "expected_status_code": expected,
                "actual_status_code": actual,
            }
            for case_id, expected, actual, _ in corrections
        ],
        script_repair_allowed=True,
    )
    return diagnosis.model_copy(update={"issues": [issue, *diagnosis.issues], "proposal": proposal})
