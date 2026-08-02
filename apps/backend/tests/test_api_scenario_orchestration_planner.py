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
async def test_planner_accepts_sse_extractor_without_unverified_event() -> None:
    proposal_json = json.dumps(
        {
            "scenario_name": "SSE 对话",
            "steps": [
                {
                    "client_step_id": "step-sse",
                    "endpoint_id": "apiend-sse",
                    "order": 1,
                    "extractors": [
                        {
                            "name": "answer",
                            "source": "sse_event_json",
                            "path": "/data/answer",
                            "value_type": "string",
                        }
                    ],
                }
            ],
        },
        ensure_ascii=False,
    )
    model = FakeModel([proposal_json])
    planner = ApiScenarioPlanner(model)

    proposal = await planner.plan(
        {"goal": "发起 SSE 对话", "endpoint_catalog": [{"endpoint_id": "apiend-sse"}]}
    )

    assert proposal.steps[0].extractors[0].event == ""
    assert planner.model_call_count == 1


@pytest.mark.anyio
async def test_planner_repairs_invalid_json_once() -> None:
    model = FakeModel(["not-json", _proposal_json()])
    planner = ApiScenarioPlanner(model)

    proposal = await planner.plan(
        {"goal": "查询资料", "endpoint_catalog": [{"endpoint_id": "apiend-selected"}]}
    )

    assert proposal.scenario_name == "查询资料"
    assert planner.model_call_count == 2
    assert "JSON Schema" in model.calls[1][-1]["content"]
    assert '"fields"' in model.calls[1][-1]["content"]
    assert any(
        message.get("role") == "assistant" and message.get("content") == "not-json"
        for message in model.calls[1]
    )


@pytest.mark.anyio
async def test_planner_uses_plain_json_without_binding_provider_tools() -> None:
    class PlainJsonOnlyModel(FakeModel):
        def bind_tools(self, _tools):
            raise AssertionError("Planner must not bind provider tools")

    model = PlainJsonOnlyModel([_proposal_json()])
    planner = ApiScenarioPlanner(model)

    proposal = await planner.plan(
        {"goal": "查询资料", "endpoint_catalog": [{"endpoint_id": "apiend-selected"}]}
    )

    assert proposal.scenario_name == "查询资料"
    assert planner.model_call_count == 1


@pytest.mark.anyio
async def test_planner_repairs_long_json_with_missing_comma_using_previous_output() -> None:
    proposal_data = json.loads(_proposal_json())
    proposal_data["description"] = "x" * 1800
    proposal_data["steps"][0]["fields"].extend(
        {
            "target": {"location": "query", "path": f"/field_{index}"},
            "display_name": f"field_{index}_" + "y" * 80,
            "required": False,
            "value_type": "string",
            "proposal": {"type": "environment", "key": f"field_{index}"},
        }
        for index in range(8)
    )
    proposal_data["steps"][0]["enabled"] = True
    valid_json = json.dumps(proposal_data, ensure_ascii=False, separators=(",", ":"))
    malformed_json = valid_json.replace(',"enabled":true', '"enabled":true', 1)
    assert len(malformed_json) > 3384

    class RepairAwareModel:
        def __init__(self):
            self.calls = []

        def bind_tools(self, _tools):
            raise AssertionError("Planner must not bind provider tools")

        async def ainvoke(self, messages):
            self.calls.append(messages)
            if len(self.calls) == 1:
                return {"content": malformed_json}
            has_previous_output = any(
                message.get("role") == "assistant" and message.get("content") == malformed_json
                for message in messages
            )
            has_syntax_error = "json_invalid" in messages[-1]["content"]
            return {"content": valid_json if has_previous_output and has_syntax_error else "still-bad"}

    model = RepairAwareModel()
    planner = ApiScenarioPlanner(model)

    proposal = await planner.plan(
        {"goal": "查询资料", "endpoint_catalog": [{"endpoint_id": "apiend-selected"}]}
    )

    assert proposal.description == "x" * 1800
    assert planner.model_call_count == 2
    assert planner.attempt_metrics[0]["error_type"] == "invalid_json"
    assert "error_type" not in planner.attempt_metrics[1]


@pytest.mark.anyio
async def test_planner_repairs_legacy_request_shape_with_current_schema() -> None:
    legacy = json.dumps(
        {
            "scenario_name": "生成并使用 SegmentCode",
            "steps": [
                {
                    "client_step_id": "step-generate",
                    "endpoint_id": "apiend-generate",
                    "order": 1,
                    "request": {"json": {"message_source": "openai-ws"}},
                    "extractors": [
                        {"name": "segment_code", "source": "response", "target": "scenario.segment_code"}
                    ],
                }
            ],
        },
        ensure_ascii=False,
    )
    model = FakeModel([legacy, _proposal_json()])
    planner = ApiScenarioPlanner(model)

    proposal = await planner.plan(
        {"goal": "编排两个接口", "endpoint_catalog": [{"endpoint_id": "apiend-generate"}]}
    )

    assert proposal.steps[0].endpoint_id == "apiend-selected"
    correction = model.calls[1][-1]["content"]
    assert "steps.0.request" in correction
    assert '"fields"' in correction
    assert '"json_body"' in correction


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
    planner = ApiScenarioPlanner(model, total_deadline_seconds=0.02)

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

    prompt = "\n".join(message["content"] for message in model.calls[0])
    assert "apiend-selected" in prompt
    assert "apiend-unselected" not in prompt
    assert "不得猜测 event" in prompt
