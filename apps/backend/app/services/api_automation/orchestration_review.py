from __future__ import annotations

import re
from typing import Any

from app.agents.api_automation.orchestration.schemas import (
    PlannerExtractorProposal,
    PlannerProposal,
    ScenarioExtractor,
    ValueSource,
)
from app.schemas.api_automation import (
    ApiScenarioAiReviewField,
    ApiScenarioAiReviewFieldGroup,
    ApiScenarioAiReviewPlan,
    ApiScenarioAiReviewStep,
)
from app.services.api_automation.orchestration_asset_analysis import AssetSlot, normalize_request_target, request_slots


_GROUP_LABELS = {
    "path": "Path",
    "query": "Query",
    "header": "Headers",
    "cookie": "Cookies",
    "json_body": "Body",
    "form": "Form",
    "multipart": "Form Data",
    "raw_body": "Raw Body",
}


def build_review_plan(
    proposal: PlannerProposal,
    endpoints: list[dict[str, Any]],
    environment_schema: dict[str, Any],
    *,
    plan_id: str,
    scenario_id: str | None,
    expected_revision: int | None,
    asset_fingerprint: str,
    expires_at: str,
) -> ApiScenarioAiReviewPlan:
    endpoint_by_id = {str(endpoint.get("id")): endpoint for endpoint in endpoints}
    step_order = {step.client_step_id: step.order for step in proposal.steps}
    environment_variables = {
        str(item.get("key")): item
        for item in environment_schema.get("variables", [])
        if isinstance(item, dict) and item.get("key")
    }
    environment_secrets = {
        str(item.get("key"))
        for item in environment_schema.get("secrets", [])
        if isinstance(item, dict) and item.get("key") and item.get("configured", True)
    }
    review_steps: list[ApiScenarioAiReviewStep] = []
    review_warnings: list[str] = []
    for step in sorted(proposal.steps, key=lambda item: item.order):
        endpoint = endpoint_by_id.get(step.endpoint_id, {})
        slot_by_target = {(slot.location, slot.path): slot for slot in request_slots(endpoint)}
        grouped: dict[str, list[ApiScenarioAiReviewField]] = {}
        for field in step.fields:
            location, path = normalize_request_target(endpoint, field.target.location, field.target.path)
            slot = slot_by_target.get((location, path))
            source = field.proposal
            status = _initial_status(
                source,
                slot,
                step_id=step.client_step_id,
                step_order=step.order,
                step_order_by_id=step_order,
                environment_variables=environment_variables,
                environment_secrets=environment_secrets,
            )
            grouped.setdefault(location, []).append(
                ApiScenarioAiReviewField(
                    field_id=_field_id(step.client_step_id, location, path),
                    path=path,
                    display_name=field.display_name,
                    required=slot.required if slot else field.required,
                    value_type=slot.value_type if slot else field.value_type,
                    sensitive=slot.sensitive if slot else field.sensitive,
                    proposal=source,
                    resolved=source,
                    status=status,
                )
            )
        field_groups = [
            ApiScenarioAiReviewFieldGroup(
                location=location,
                label=_GROUP_LABELS[location],
                fields=fields,
            )
            for location, fields in grouped.items()
        ]
        review_steps.append(
            ApiScenarioAiReviewStep(
                step_id=step.client_step_id,
                endpoint_id=step.endpoint_id,
                order=step.order,
                phase=step.phase,
                name=step.name or str(endpoint.get("summary") or endpoint.get("path") or step.endpoint_id),
                method=str(endpoint.get("method") or "GET").upper(),
                path=str(endpoint.get("path") or ""),
                depends_on=list(step.depends_on),
                field_groups=field_groups,
                extractors=_executable_extractors(step.extractors, step.client_step_id, review_warnings),
                assertions=step.assertions,
                on_failure=step.on_failure,
                enabled=step.enabled,
            )
        )
    plan = ApiScenarioAiReviewPlan(
        plan_id=plan_id,
        scenario_id=scenario_id,
        scenario_name=proposal.scenario_name,
        description=proposal.description,
        steps=review_steps,
        expected_revision=expected_revision,
        asset_fingerprint=asset_fingerprint,
        expires_at=expires_at,
    )
    from app.services.api_automation.orchestration_validator import validate_review_plan

    validation = validate_review_plan(plan, endpoints)
    validation["warnings"] = list(dict.fromkeys([*validation["warnings"], *review_warnings]))
    data = plan.model_dump()
    data["validation"] = validation
    return ApiScenarioAiReviewPlan.model_validate(data)


def _executable_extractors(
    extractors: list[PlannerExtractorProposal],
    step_id: str,
    warnings: list[str],
) -> list[ScenarioExtractor]:
    executable: list[ScenarioExtractor] = []
    for extractor in extractors:
        if extractor.source == "sse_event_json" and not extractor.event:
            warnings.append(
                f"步骤 {step_id} 的 SSE 提取器 {extractor.name} 缺少资产明确提供的 event，已忽略该提取器建议。"
            )
            continue
        executable.append(ScenarioExtractor.model_validate(extractor.model_dump(exclude_none=True)))
    return executable


def _initial_status(
    source: ValueSource,
    slot: AssetSlot | None,
    *,
    step_id: str,
    step_order: int,
    step_order_by_id: dict[str, int],
    environment_variables: dict[str, dict[str, Any]],
    environment_secrets: set[str],
) -> str:
    if source.type == "environment" and slot:
        variable = environment_variables.get(source.key)
        if (
            variable
            and variable.get("configured")
            and _normalized_name(source.key) == _normalized_name(slot.name)
            and _types_compatible(str(variable.get("value_type") or "any"), slot.value_type)
        ):
            return "resolved"
    if source.type == "secret" and source.key in environment_secrets:
        return "resolved"
    if source.type == "step_output":
        source_order = step_order_by_id.get(source.step_id)
        if source.step_id != step_id and source_order is not None and source_order < step_order:
            return "resolved"
    if source.type == "literal" and slot:
        if slot.has_default and source.value == slot.default_value:
            return "resolved"
        if len(slot.enum) == 1 and source.value == slot.enum[0]:
            return "resolved"
    return "pending"


def _field_id(step_id: str, location: str, path: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", path.strip("/")) or "root"
    return f"field-{step_id}-{location}-{slug}"[:200]


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _types_compatible(source_type: str, target_type: str) -> bool:
    return source_type == target_type or "any" in {source_type, target_type}


__all__ = ["build_review_plan"]
