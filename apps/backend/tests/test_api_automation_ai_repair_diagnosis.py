import pytest
from pydantic import ValidationError

from app.agents.api_automation.self_healing.diagnosis_agent import (
    SYSTEM_PROMPT,
    create_diagnosis_agent,
    enforce_uncertain_oracle_policy,
)
from app.agents.api_automation.self_healing.schemas import FailureDiagnosis, FailureIssue, RepairProposal


def test_failure_issue_rejects_unknown_classification() -> None:
    with pytest.raises(ValidationError):
        FailureIssue(
            failure_ids=["failure-1"],
            classification="make_tests_pass",
            confidence=0.8,
            root_cause="unknown",
            recommendation="review",
            repairable=True,
        )


def test_failure_issue_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        FailureIssue(
            failure_ids=["failure-1"],
            classification="test_code_issue",
            confidence=1.1,
            root_cause="import failed",
            recommendation="repair import",
            repairable=True,
        )


def test_failure_diagnosis_accepts_mixed_root_causes() -> None:
    diagnosis = FailureDiagnosis(
        summary="mixed",
        issues=[
            FailureIssue(
                failure_ids=["f1"],
                classification="test_code_issue",
                confidence=0.95,
                root_cause="missing import",
                recommendation="repair code",
                repairable=True,
            ),
            FailureIssue(
                failure_ids=["f2"],
                classification="interface_bug",
                confidence=0.8,
                root_cause="server failure",
                recommendation="report business defect",
                repairable=False,
            ),
        ],
    )
    assert len(diagnosis.issues) == 2


def test_create_diagnosis_agent_uses_structured_output() -> None:
    agent = create_diagnosis_agent(model=object())
    assert agent is not None


def test_repair_proposal_rejects_non_code_target() -> None:
    with pytest.raises(ValidationError):
        RepairProposal(
            target="interface",
            action="inspect_interface",
            title="检查接口参数校验",
            summary="不修改测试脚本。",
            confidence=0.88,
            script_repair_allowed=False,
        )


def test_failure_diagnosis_contains_structured_repair_proposal() -> None:
    diagnosis = FailureDiagnosis(
        summary="测试断言实现错误",
        issues=[
            FailureIssue(
                failure_ids=["f1"],
                classification="test_code_issue",
                confidence=0.95,
                root_cause="断言读取了错误字段",
                recommendation="修改断言实现",
                repairable=True,
            )
        ],
        proposal=RepairProposal(
            target="test_script",
            action="modify_assertion",
            title="修复断言实现",
            summary="修改公共断言代码。",
            confidence=0.95,
            proposed_changes=["修改 utils/assertions.py"],
            script_repair_allowed=True,
        ),
    )

    assert diagnosis.proposal is not None
    assert diagnosis.proposal.target == "test_script"
    assert diagnosis.proposal.script_repair_allowed is True


def test_diagnosis_prompt_allows_evidence_backed_inferred_oracle_repairs() -> None:
    assert "needs_confirmation 或 inferred" in SYSTEM_PROMPT
    assert "实际响应证据" in SYSTEM_PROMPT
    assert "只有证据足够明确才允许这样做" in SYSTEM_PROMPT
    assert "interface_bug、environment_issue 或 unknown" in SYSTEM_PROMPT


def test_uncertain_oracle_policy_overrides_interface_bug_with_approval_proposal() -> None:
    diagnosis = FailureDiagnosis(
        summary="接口未校验非法参数",
        issues=[
            FailureIssue(
                failure_ids=["failure-1"],
                classification="interface_bug",
                confidence=0.95,
                root_cause="接口返回 200",
                recommendation="服务端增加校验",
                repairable=False,
            )
        ],
    )
    context = {
        "generated_cases": [
            {
                "case_id": "case-1",
                "title": "start_date 类型错误",
                "oracle_status": "needs_confirmation",
                "assertions": [{"type": "status_code", "expected": 400}],
                "generation_notes": "文档未声明状态码，按常见约定推断为 400，失败时按实际响应调整。",
            }
        ],
        "observations": [{"case_id": "case-1", "status_code": 200, "response_body": {}}],
    }

    normalized = enforce_uncertain_oracle_policy(diagnosis, context)

    assert normalized.issues[0].classification == "test_data_issue"
    assert normalized.issues[0].repairable is True
    assert normalized.proposal is not None
    assert normalized.proposal.action == "modify_assertion"
    assert normalized.proposal.script_repair_allowed is True
    assert "400 -> 200" in normalized.proposal.proposed_changes[0]
    assert "确认测试预期" in normalized.proposal.proposed_changes[0]
    assert "Oracle" not in normalized.proposal.proposed_changes[0]


def test_uncertain_oracle_policy_requires_structured_observation() -> None:
    diagnosis = FailureDiagnosis(
        summary="接口返回 200",
        issues=[
            FailureIssue(
                failure_ids=["failure-1"],
                classification="contract_ambiguity",
                confidence=0.8,
                root_cause="预期不明确",
                recommendation="收集响应证据",
                repairable=False,
            )
        ],
    )
    context = {
        "generated_cases": [
            {
                "case_id": "case-1",
                "oracle_status": "needs_confirmation",
                "assertions": [{"type": "status_code", "expected": 400}],
            }
        ],
        "observations": [],
    }

    assert enforce_uncertain_oracle_policy(diagnosis, context) == diagnosis
