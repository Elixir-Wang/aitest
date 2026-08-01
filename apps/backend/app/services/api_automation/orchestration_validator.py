from __future__ import annotations

from typing import Any

from app.schemas.api_automation import ApiScenarioAiReviewPlan
from app.services.api_automation.orchestration_asset_analysis import request_slots


def validate_review_plan(
    review: ApiScenarioAiReviewPlan,
    endpoints: list[dict[str, Any]],
    *,
    for_apply: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    endpoint_by_id = {str(endpoint.get("id")): endpoint for endpoint in endpoints}
    order_by_step = {step.step_id: step.order for step in review.steps}
    if len(order_by_step) != len(review.steps):
        errors.append("步骤 ID 不能重复。")
    orders = [step.order for step in review.steps]
    if len(set(orders)) != len(orders):
        errors.append("步骤执行顺序不能重复。")
    for step in review.steps:
        endpoint = endpoint_by_id.get(step.endpoint_id)
        if endpoint is None:
            errors.append(f"步骤 {step.step_id} 引用了不存在的接口 {step.endpoint_id}。")
            continue
        valid_targets = {(slot.location, slot.path) for slot in request_slots(endpoint)}
        for dependency in step.depends_on:
            dependency_order = order_by_step.get(dependency)
            if dependency_order is None:
                errors.append(f"步骤 {step.step_id} 引用了不存在的依赖步骤 {dependency}。")
            elif dependency_order >= step.order:
                errors.append(f"步骤 {step.step_id} 的依赖 {dependency} 必须位于上游。")
        for group in step.field_groups:
            for field in group.fields:
                if (group.location, field.path) not in valid_targets:
                    errors.append(f"步骤 {step.step_id} 的字段 {group.location}:{field.path} 不存在。")
                source = field.resolved
                if source and source.type == "step_output":
                    source_order = order_by_step.get(source.step_id)
                    if source_order is None or source_order >= step.order:
                        errors.append(f"字段 {field.display_name} 的上游步骤 {source.step_id} 必须位于当前步骤之前。")
                if for_apply and field.required and (field.status == "pending" or source is None):
                    errors.append(f"必填字段 {field.display_name} 尚未确认。")
                if not field.required and source is None:
                    warnings.append(f"可选字段 {field.display_name} 未设置。")
    return {
        "valid": not errors,
        "errors": list(dict.fromkeys(errors)),
        "warnings": list(dict.fromkeys(warnings)),
    }


__all__ = ["validate_review_plan"]
