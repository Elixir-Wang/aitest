from app.agents.api_automation.case_generation.planner import plan_api_test_points


ANALYSIS_ENDPOINT = {
    "id": "apiend-6434c35096aa611b",
    "method": "POST",
    "path": "/openapi/v1/agent/analysis/",
    "summary": "智能体数据分析",
    "parameters": [
        {"name": "cybertron-robot-key", "in": "header", "required": True, "x-source": "security"},
        {"name": "cybertron-robot-token", "in": "header", "required": True, "x-source": "security"},
        {"name": "username", "in": "header", "required": True, "x-source": "security"},
    ],
    "request_body": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["start_date", "end_date"],
                    "properties": {
                        "start_date": {"type": "string", "description": "统计开始日期"},
                        "end_date": {"type": "string", "description": "统计结束日期"},
                    },
                }
            }
        },
    },
    "responses": {"200": {"description": "ok"}, "404": {"description": "Not found"}},
}


def test_analysis_endpoint_has_stable_complete_test_point_set() -> None:
    points = plan_api_test_points(ANALYSIS_ENDPOINT)

    keys = [point.key for point in points]

    assert keys == [
        "success.minimum_valid",
        "body.required.start_date.missing",
        "body.required.end_date.missing",
        "request_body.missing",
        "request_body.empty_object",
        "body.required.start_date.empty",
        "body.required.start_date.null",
        "body.required.start_date.invalid_type",
        "body.start_date.invalid_format",
        "body.required.end_date.empty",
        "body.required.end_date.null",
        "body.required.end_date.invalid_type",
        "body.end_date.invalid_format",
        "body.date_relation.start_equals_end",
        "body.date_relation.start_after_end",
        "header.required.cybertron-robot-key.empty",
        "header.required.cybertron-robot-token.empty",
        "header.required.username.empty",
    ]
    assert len(keys) == 18
    assert len(keys) == len(set(keys))


def test_minimum_and_complete_success_are_not_planned_twice_without_optional_fields() -> None:
    points = plan_api_test_points(ANALYSIS_ENDPOINT)

    success_points = [point for point in points if point.category == "positive"]

    assert [point.key for point in success_points] == ["success.minimum_valid"]


def test_planner_derives_auth_points_only_from_endpoint_contract() -> None:
    points = plan_api_test_points(ANALYSIS_ENDPOINT)

    auth_points = [point for point in points if point.key.startswith("header.required.")]

    assert [point.key for point in auth_points] == [
        "header.required.cybertron-robot-key.empty",
        "header.required.cybertron-robot-token.empty",
        "header.required.username.empty",
    ]
