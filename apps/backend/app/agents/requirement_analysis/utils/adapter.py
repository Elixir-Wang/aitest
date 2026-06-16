"""ClarificationItem 下游适配工具。"""

from __future__ import annotations

from typing import Literal

from app.agents.requirement_analysis.core.schemas import ClarificationItem, ClarificationOption, TestSurface

PRIORITY_LABELS = {
    "P0": "P0 阻塞项",
    "P1": "P1 高风险",
    "P2": "P2 中风险",
    "P3": "P3 低风险",
}

ISSUE_CATEGORY_LABELS = {
    "contract_unclear": "契约不明确",
    "rule_missing": "规则缺失",
    "boundary_undefined": "边界未定义",
    "exception_unhandled": "异常未处理",
    "state_ambiguous": "状态模糊",
    "concurrency_unclear": "并发不明确",
    "permission_undefined": "权限未定义",
    "dependency_unclear": "依赖不清楚",
    "acceptance_missing": "验收标准缺失",
    "conflict": "需求冲突",
}

SOURCE_STAGE_LABELS = {
    "understanding": "需求理解",
    "completeness": "完整性",
    "clarity": "清晰度",
    "testability": "可测试性",
    "consistency": "一致性",
}

RESOLUTION_STATUS_LABELS = {
    "auto_resolved": "自动解决",
    "has_options": "有可选方案",
    "needs_input": "需人工输入",
    "needs_research": "需进一步调研",
}

SURFACE_TYPE_LABELS = {
    "api": "接口契约",
    "state_flow": "状态流转",
    "data_consistency": "数据一致性",
    "permission": "权限",
    "security": "安全",
    "audit_log": "审计日志",
    "async_task": "异步任务",
    "external_dependency": "外部依赖",
    "ui_feedback": "用户反馈",
    "migration": "数据迁移",
    "non_functional": "非功能",
}


def priority_to_severity(priority: str) -> Literal["blocker", "major", "minor"]:
    if priority == "P0":
        return "blocker"
    if priority == "P1":
        return "major"
    return "minor"


def priority_to_bucket(priority: str) -> Literal["blocker", "risk", "acceptance"]:
    if priority == "P0":
        return "blocker"
    if priority in {"P1", "P2"}:
        return "risk"
    return "acceptance"


def issue_category_to_issue_type(category: str) -> Literal["missing", "confirmation", "conflict", "ambiguous"]:
    if category == "conflict":
        return "conflict"
    if category in {"rule_missing", "acceptance_missing", "boundary_undefined"}:
        return "missing"
    if category in {"contract_unclear", "state_ambiguous", "concurrency_unclear", "dependency_unclear"}:
        return "ambiguous"
    return "confirmation"


def surface_label(surface: TestSurface | str) -> str:
    if isinstance(surface, TestSurface):
        return SURFACE_TYPE_LABELS.get(surface.surface_type, surface.surface_type)
    return SURFACE_TYPE_LABELS.get(surface, surface)


def clarification_option_to_api(option: ClarificationOption) -> dict:
    return {
        "id": option.option_id,
        "label": option.label,
        "answer_markdown": option.description,
        "rationale": option.source,
        "confidence": option.confidence,
        "description": option.description,
        "source": option.source,
        "evidence_excerpt": option.evidence_excerpt,
    }


def clarification_item_to_api(item: ClarificationItem) -> dict:
    """将 ClarificationItem 转为 API / 前端可用的 dict。"""
    options = [clarification_option_to_api(option) for option in item.options]
    severity = priority_to_severity(item.priority)
    question = item.decision_point.strip() or item.title
    impact = item.test_impact.strip() or item.why_clarify.strip()
    affected_surfaces = [surface_label(surface) for surface in item.affected_surfaces]
    test_case_drafts = [
        f"{test_case.test_id}: {test_case.scenario} → {test_case.expected_result}"
        for test_case in item.test_cases
    ]

    return {
        "id": item.item_id,
        "title": item.title,
        "issue_category": item.issue_category,
        "issue_type": issue_category_to_issue_type(item.issue_category),
        "module_key": item.module_key,
        "module_name": item.module_name or item.title,
        "question": question,
        "impact": impact,
        "dimension": item.source_stage,
        "source_stage": item.source_stage,
        "severity": severity,
        "priority": item.priority,
        "source_excerpt": item.source_excerpt,
        "clarification_bucket": priority_to_bucket(item.priority),
        "decision_point": item.decision_point,
        "why_clarify": item.why_clarify,
        "current_gap": item.why_clarify,
        "test_impact": item.test_impact,
        "risk_scenario": item.risk_scenario,
        "affected_surfaces": affected_surfaces,
        "options": options,
        "decision_options": options,
        "recommended_options": options[:2],
        "recommended_decision": item.recommendation_rationale,
        "recommended_option_id": item.recommended_option_id,
        "human_question": item.decision_point,
        "draft_acceptance_tests": test_case_drafts,
        "test_cases": [test_case.model_dump() for test_case in item.test_cases],
        "resolution_status": item.resolution_status,
        "auto_resolution": item.auto_resolution,
        "auto_resolution_source": item.auto_resolution_source,
        "tags": item.tags,
        "related_items": item.related_items,
        "related_requirements": item.related_requirements,
    }


def is_pending_resolution_status(status: str) -> bool:
    return status in {"needs_input", "needs_research", "has_options"}


__all__ = [
    "ISSUE_CATEGORY_LABELS",
    "PRIORITY_LABELS",
    "RESOLUTION_STATUS_LABELS",
    "SOURCE_STAGE_LABELS",
    "SURFACE_TYPE_LABELS",
    "clarification_item_to_api",
    "clarification_option_to_api",
    "is_pending_resolution_status",
    "issue_category_to_issue_type",
    "priority_to_bucket",
    "priority_to_severity",
    "surface_label",
]
