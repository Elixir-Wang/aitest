import asyncio
import json

import pytest

from app.services.api_automation.orchestration_planner import (
    ApiScenarioPlanner,
    PlannerProtocolError,
    PlannerTimeoutError,
)


def _proposal_json() -> str:
    return json.dumps(
        {
            "scenario_name": "查询资料",
            "steps": [
                {
                    "client_step_id": "step-1",
                    "endpoint_id": "apiend-selected",
                    "order": 1,
                    "name": "查询资料",
                    "fields": [
                        {
                            "target": {"location": "query", "path": "/username"},
                            "display_name": "username",
                            "required": True,
                            "value_type": "string",
                            "proposal": {"type": "environment", "key": "username"},
                        }
                    ],
                }
            ],
        },
        ensure_ascii=False,
    )


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            return await response()
        return {"content": response}


@pytest.mark.anyio
async def test_planner_parses_json_content_in_one_call() -> None:
    model = FakeModel([_proposal_json()])
    planner = ApiScenarioPlanner(model)

    proposal = await planner.plan(
        {
            "goal": "查询资料",
            "endpoint_catalog": [{"endpoint_id": "apiend-selected", "path": "/profile"}],
            "environment_schema": {"variables": [{"key": "username", "value_type": "string"}]},
        }
    )

    assert proposal.steps[0].endpoint_id == "apiend-selected"
    assert planner.model_call_count == 1
    assert len(model.calls) == 1


@pytest.mark.anyio
async def test_planner_repairs_invalid_json_once() -> None:
    model = FakeModel(["not-json", _proposal_json()])
    planner = ApiScenarioPlanner(model)

    proposal = await planner.plan(
        {"goal": "查询资料", "endpoint_catalog": [{"endpoint_id": "apiend-selected"}]}
    )

    assert proposal.scenario_name == "查询资料"
    assert planner.model_call_count == 2
    assert "修复" in model.calls[1][-1]["content"]


@pytest.mark.anyio
async def test_planner_never_calls_model_a_third_time() -> None:
    model = FakeModel(["bad", "still bad", _proposal_json()])
    planner = ApiScenarioPlanner(model)

    with pytest.raises(PlannerProtocolError):
        await planner.plan({"goal": "查询资料", "endpoint_catalog": [{"endpoint_id": "apiend-selected"}]})

    assert planner.model_call_count == 2
    assert len(model.calls) == 2


@pytest.mark.anyio
async def test_planner_times_out_single_model_call() -> None:
    async def slow_response():
        await asyncio.sleep(0.05)
        return {"content": _proposal_json()}

    model = FakeModel([slow_response])
    planner = ApiScenarioPlanner(model, request_timeout_seconds=0.01, total_deadline_seconds=0.02)

    with pytest.raises(PlannerTimeoutError):
        await planner.plan({"goal": "查询资料", "endpoint_catalog": [{"endpoint_id": "apiend-selected"}]})

    assert planner.model_call_count == 1


@pytest.mark.anyio
async def test_planner_prompt_contains_only_supplied_endpoint_catalog() -> None:
    model = FakeModel([_proposal_json()])
    planner = ApiScenarioPlanner(model)

    await planner.plan(
        {
            "goal": "查询资料",
            "endpoint_catalog": [{"endpoint_id": "apiend-selected", "path": "/profile"}],
        }
    )

    prompt = model.calls[0][-1]["content"]
    assert "apiend-selected" in prompt
    assert "apiend-unselected" not in prompt
