"""EARS (Easy Approach to Requirements Syntax) validator."""

import re
from typing import Literal

from pydantic import BaseModel


class EARSIssue(BaseModel):
    """EARS 句式问题"""
    requirement_text: str
    issue_type: Literal["missing_subject", "missing_trigger", "missing_action", "missing_condition"]
    description: str
    suggested_ears: str


def validate_ears_pattern(requirement_text: str) -> list[EARSIssue]:
    """
    检查需求是否符合 EARS 模板。

    EARS 5 种标准句式：
    1. 无条件：The system shall <action>
    2. 事件驱动：When <trigger>, the system shall <action>
    3. 状态驱动：While <state>, the system shall <action>
    4. 可选特性：Where <feature enabled>, the system shall <action>
    5. 复杂条件：If <condition>, when <trigger>, the system shall <action>
    """
    issues: list[EARSIssue] = []
    text = requirement_text.strip()

    # 检查是否有主语（系统、用户、管理员等）
    has_subject = bool(re.search(r'(系统|用户|管理员|服务|接口|应用|平台)', text))

    # 检查是否有动词（应、需、可以、能够、shall、should、must）
    has_action_verb = bool(re.search(r'(应|需|可以|能够|支持|提供|shall|should|must|can)', text))

    # 检查是否有触发条件（当、如果、在...时、while、when、if）
    has_trigger = bool(re.search(r'(当|如果|在.*时|若|while|when|if)', text))

    # 情况 1：缺少主语
    if not has_subject:
        issues.append(EARSIssue(
            requirement_text=text,
            issue_type="missing_subject",
            description="缺少明确主语：不清楚是系统行为还是用户操作",
            suggested_ears=f"【系统/用户】应{text}"
        ))

    # 情况 2：缺少动词（行为不明确）
    if not has_action_verb:
        issues.append(EARSIssue(
            requirement_text=text,
            issue_type="missing_action",
            description="缺少明确行为动词：不清楚要做什么",
            suggested_ears=f"{text}【应执行什么操作？】"
        ))

    # 情况 3：有动词但没有触发条件（可能需要条件）
    # 检查是否是隐含触发的场景（如"显示"、"提示"、"通知"）
    implicit_trigger_verbs = ['显示', '提示', '通知', '跳转', '返回']
    has_implicit_trigger = any(verb in text for verb in implicit_trigger_verbs)

    if has_action_verb and not has_trigger and has_implicit_trigger:
        issues.append(EARSIssue(
            requirement_text=text,
            issue_type="missing_trigger",
            description="缺少触发条件：什么时候执行这个操作？",
            suggested_ears=f"当【触发条件】时，{text}"
        ))

    return issues


def batch_validate_requirements(requirements: list[str]) -> dict[str, list[EARSIssue]]:
    """批量检查需求列表"""
    results = {}
    for i, req in enumerate(requirements):
        issues = validate_ears_pattern(req)
        if issues:
            results[f"REQ-{i+1:03d}"] = issues
    return results


__all__ = ["validate_ears_pattern", "batch_validate_requirements", "EARSIssue"]
