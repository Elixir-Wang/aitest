from typing import Any

from app.agents.api_automation.case_generation.schemas import ApiGeneratedCase


def validate_generated_cases(
    endpoint: dict[str, Any],
    planned_test_points: list[dict[str, Any]],
    cases: list[ApiGeneratedCase],
) -> None:
    planned_keys = [str(point.get("key") or "") for point in planned_test_points]
    if len(planned_keys) != len(set(planned_keys)):
        raise ValueError("测试点计划包含重复 test_point_key。")

    case_keys = [case.test_point_key for case in cases]
    if any(not key for key in case_keys):
        raise ValueError("生成用例缺少 test_point_key。")
    if len(case_keys) != len(set(case_keys)):
        raise ValueError("生成用例包含重复 test_point_key。")

    planned_key_set = set(planned_keys)
    case_key_set = set(case_keys)
    missing_keys = [key for key in planned_keys if key not in case_key_set]
    unexpected_keys = [key for key in case_keys if key not in planned_key_set]
    if missing_keys:
        raise ValueError(f"生成用例遗漏测试点：{', '.join(missing_keys)}")
    if unexpected_keys:
        raise ValueError(f"生成用例包含计划外测试点：{', '.join(unexpected_keys)}")

    endpoint_id = str(endpoint.get("id") or "")
    endpoint_method = str(endpoint.get("method") or "").upper()
    endpoint_path = str(endpoint.get("path") or "")
    planned_by_key = {str(point.get("key") or ""): point for point in planned_test_points}
    for case in cases:
        request = case.request.model_dump(exclude_unset=True)
        if case.endpoint_id != endpoint_id:
            raise ValueError(f"测试点 {case.test_point_key} 的 endpoint_id 不一致。")
        if str(request.get("method") or "").upper() != endpoint_method:
            raise ValueError(f"测试点 {case.test_point_key} 的请求方法不一致。")
        if str(request.get("path") or "") != endpoint_path:
            raise ValueError(f"测试点 {case.test_point_key} 的请求路径不一致。")
        if case.test_point_key == "request_body.missing" and "body" in request:
            raise ValueError("request_body.missing 必须省略 body，不能使用空对象代替。")
        planned_point = planned_by_key[case.test_point_key]
        planned_oracle_status = planned_point.get("oracle_status")
        if planned_oracle_status and case.oracle_status != planned_oracle_status:
            raise ValueError(f"测试点 {case.test_point_key} 的 oracle_status 与测试点计划不一致。")
        required_assertions = planned_point.get("required_assertions") or []
        generated_assertions = [
            assertion.model_dump() if hasattr(assertion, "model_dump") else dict(assertion)
            for assertion in case.assertions
        ]
        generated_assertion_keys = {
            _assertion_key(assertion)
            for assertion in generated_assertions
        }
        for required_assertion in required_assertions:
            if _assertion_key(required_assertion) not in generated_assertion_keys:
                raise ValueError(
                    "测试点 "
                    f"{case.test_point_key} 缺少响应契约断言："
                    f"{required_assertion.get('type', '')} {required_assertion.get('path', '')}。"
                )
        if planned_point.get("oracle_fact"):
            approved_assertions = planned_point.get("assertions") or []
            if generated_assertions != approved_assertions:
                raise ValueError(f"测试点 {case.test_point_key} 的生成断言与审批断言不一致。")

    success_requests = [
        case.request.model_dump(exclude_unset=True)
        for case in cases
        if case.coverage == "positive" and case.test_point_key.startswith("success.")
    ]
    if len({repr(request) for request in success_requests}) != len(success_requests):
        raise ValueError("成功基线存在重复请求。")


def _assertion_key(assertion: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(assertion.get("type") or ""),
        str(assertion.get("path") or "").strip(),
        repr(assertion.get("expected")),
    )
