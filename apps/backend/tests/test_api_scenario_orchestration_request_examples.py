from app.agents.api_automation.orchestration.schemas import PlannerProposal
from app.services.api_automation.orchestration_request_examples import apply_request_examples, extract_request_examples


ENDPOINTS = [
    {
        "id": "apiend-gen",
        "method": "POST",
        "path": "/openapi/v1/gw/multi-agent/segment-code/gen",
        "parameters": [],
        "request_body": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"message_source": {"type": "string"}},
                    }
                }
            }
        },
    },
    {
        "id": "apiend-sse",
        "method": "POST",
        "path": "/openapi/v1/gw/multi-agent/sse",
        "parameters": [
            {"name": "SSE-Backend-Type", "in": "header", "schema": {"type": "string"}},
        ],
        "request_body": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "segment_code": {"type": "string"},
                            "message_source": {"type": "string"},
                            "username": {"type": "string"},
                            "data": {
                                "type": "string",
                                "x-json-schema": {
                                    "type": "object",
                                    "properties": {
                                        "agent_node_id": {"type": "string"},
                                        "question": {"type": "string"},
                                        "stream": {"type": "boolean"},
                                    },
                                },
                            },
                        },
                    }
                }
            }
        },
    },
]


def test_extract_request_examples_preserves_explicit_curl_values() -> None:
    goal = r'''
curl --location 'https://www.cybotstar.cn/openapi/v1/gw/multi-agent/sse' \
--header 'SSE-Backend-Type: sse' \
--form 'segment_code="739356205041844226"' \
--form 'message_source="web_share"' \
--form 'username="hongbao.wang"' \
--form 'data="{\"agent_node_id\": \"\",\"question\": \"你好\",\"stream\": true}"'
'''

    examples = extract_request_examples(goal, ENDPOINTS)

    assert examples == {
        "apiend-sse": {
            ("header", "/SSE-Backend-Type"): {"type": "literal", "value": "sse"},
            ("multipart", "/segment_code"): {"type": "literal", "value": "739356205041844226"},
            ("multipart", "/message_source"): {"type": "literal", "value": "web_share"},
            ("multipart", "/username"): {"type": "literal", "value": "hongbao.wang"},
            ("multipart", "/data"): {
                "type": "object",
                "properties": {
                    "agent_node_id": {"type": "literal", "value": ""},
                    "question": {"type": "literal", "value": "你好"},
                    "stream": {"type": "literal", "value": True},
                },
            },
        }
    }


def test_extract_request_examples_uses_json_body_for_data_payload() -> None:
    goal = r'''
curl --location 'https://www.cybotstar.cn/openapi/v1/gw/multi-agent/segment-code/gen' \
--header 'Content-Type: application/json' \
--data '{"message_source":"web_share"}'
'''

    examples = extract_request_examples(goal, ENDPOINTS)

    assert examples["apiend-gen"][("json_body", "/message_source")] == {
        "type": "literal",
        "value": "web_share",
    }


def test_apply_request_examples_overrides_ai_literals_and_normalizes_locations() -> None:
    proposal = PlannerProposal.model_validate(
        {
            "scenario_name": "SSE 对话",
            "steps": [
                {
                    "client_step_id": "step-sse",
                    "endpoint_id": "apiend-sse",
                    "order": 1,
                    "fields": [
                        {
                            "target": {"location": "form", "path": "/message_source"},
                            "display_name": "message_source",
                            "proposal": {"type": "literal", "value": "ai-guessed"},
                        },
                        {
                            "target": {"location": "form", "path": "/data/question"},
                            "display_name": "question",
                            "proposal": {"type": "literal", "value": "AI 猜测"},
                        },
                    ],
                }
            ],
        }
    )
    explicit = {
        "apiend-sse": {
            ("multipart", "/message_source"): {"type": "literal", "value": "web_share"},
            ("multipart", "/data"): {
                "type": "object",
                "properties": {
                    "agent_node_id": {"type": "literal", "value": ""},
                    "question": {"type": "literal", "value": "你好"},
                    "stream": {"type": "literal", "value": True},
                },
            },
        }
    }

    result = apply_request_examples(proposal, explicit, ENDPOINTS)

    fields = {
        (field.target.location, field.target.path): field.proposal.model_dump(exclude_none=True)
        for field in result.steps[0].fields
    }
    assert fields == explicit["apiend-sse"]
