from app.agents.api_automation.orchestration.schemas import PlannerProposal
from app.services.api_automation.orchestration_review import build_review_plan
from app.services.api_automation.orchestration_validator import validate_review_plan


ENDPOINT = {
    "id": "apiend-1",
    "method": "POST",
    "path": "/profile",
    "summary": "查询资料",
    "parameters": [
        {"name": "username", "in": "query", "required": True, "schema": {"type": "string"}},
        {"name": "operator", "in": "query", "required": True, "schema": {"type": "string"}},
        {"name": "question", "in": "query", "required": True, "schema": {"type": "string"}},
    ],
    "request_body": {},
    "responses": {"200": {"description": "ok"}},
}


def _build(proposal: PlannerProposal, endpoints=None):
    return build_review_plan(
        proposal,
        endpoints or [ENDPOINT],
        {
            "configured": True,
            "variables": [
                {"key": "username", "value_type": "string", "configured": True},
                {"key": "username_alias", "value_type": "string", "configured": True},
            ],
            "secrets": [],
        },
        plan_id="aiplan-1",
        scenario_id="apiscn-1",
        expected_revision=0,
        asset_fingerprint="hash",
        expires_at="2026-08-01T12:00:00+00:00",
    )


def test_exact_environment_field_is_resolved_automatically() -> None:
    proposal = PlannerProposal.model_validate(
        {
            "scenario_name": "查询资料",
            "steps": [
                {
                    "client_step_id": "step-1",
                    "endpoint_id": "apiend-1",
                    "order": 1,
                    "fields": [
                        {
                            "target": {"location": "query", "path": "/username"},
                            "display_name": "username",
                            "value_type": "string",
                            "proposal": {"type": "environment", "key": "username"},
                        }
                    ],
                }
            ],
        }
    )

    field = _build(proposal).steps[0].field_groups[0].fields[0]

    assert field.status == "resolved"
    assert field.resolved.model_dump() == {"type": "environment", "key": "username"}


def test_semantic_environment_mapping_remains_pending() -> None:
    proposal = PlannerProposal.model_validate(
        {
            "scenario_name": "查询资料",
            "steps": [
                {
                    "client_step_id": "step-1",
                    "endpoint_id": "apiend-1",
                    "order": 1,
                    "fields": [
                        {
                            "target": {"location": "query", "path": "/operator"},
                            "display_name": "operator",
                            "value_type": "string",
                            "proposal": {"type": "environment", "key": "username_alias"},
                        }
                    ],
                }
            ],
        }
    )

    field = _build(proposal).steps[0].field_groups[0].fields[0]

    assert field.status == "pending"


def test_ai_literal_mock_remains_pending() -> None:
    proposal = PlannerProposal.model_validate(
        {
            "scenario_name": "查询资料",
            "steps": [
                {
                    "client_step_id": "step-1",
                    "endpoint_id": "apiend-1",
                    "order": 1,
                    "fields": [
                        {
                            "target": {"location": "query", "path": "/question"},
                            "display_name": "question",
                            "value_type": "string",
                            "proposal": {"type": "literal", "value": "查询用户资料"},
                        }
                    ],
                }
            ],
        }
    )

    field = _build(proposal).steps[0].field_groups[0].fields[0]

    assert field.status == "pending"
    assert field.resolved.model_dump() == {"type": "literal", "value": "查询用户资料"}


def test_step_output_dependency_must_point_to_upstream_step() -> None:
    proposal = PlannerProposal.model_validate(
        {
            "scenario_name": "依赖场景",
            "steps": [
                {"client_step_id": "step-1", "endpoint_id": "apiend-1", "order": 2},
                {
                    "client_step_id": "step-2",
                    "endpoint_id": "apiend-1",
                    "order": 1,
                    "fields": [
                        {
                            "target": {"location": "query", "path": "/username"},
                            "display_name": "username",
                            "value_type": "string",
                            "proposal": {"type": "step_output", "step_id": "step-1", "variable": "username"},
                        }
                    ],
                },
            ],
        }
    )
    review = _build(proposal)

    validation = validate_review_plan(review, [ENDPOINT])

    assert validation["valid"] is False
    assert any("上游" in error for error in validation["errors"])


def test_repeated_endpoint_calls_remain_separate_steps() -> None:
    proposal = PlannerProposal.model_validate(
        {
            "scenario_name": "重复查询",
            "steps": [
                {"client_step_id": "step-1", "endpoint_id": "apiend-1", "order": 1},
                {"client_step_id": "step-2", "endpoint_id": "apiend-1", "order": 2},
            ],
        }
    )

    review = _build(proposal)

    assert [step.step_id for step in review.steps] == ["step-1", "step-2"]
    assert [step.endpoint_id for step in review.steps] == ["apiend-1", "apiend-1"]
