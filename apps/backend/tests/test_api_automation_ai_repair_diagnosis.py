import pytest
from pydantic import ValidationError

from app.agents.api_automation.self_healing.diagnosis_agent import SYSTEM_PROMPT, create_diagnosis_agent
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


def test_diagnosis_prompt_only_generates_code_change_proposals() -> None:
    assert "只有 classification 为 test_code_issue 时才生成 proposal" in SYSTEM_PROMPT
    assert "必须生成 proposal" not in SYSTEM_PROMPT
    assert "不生成 proposal、风险清单或问题清单" in SYSTEM_PROMPT
