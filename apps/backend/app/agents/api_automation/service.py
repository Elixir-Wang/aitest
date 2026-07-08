from app.agents.api_automation.schemas import ApiAutomationGenerationInput, ApiAutomationGenerationResult


def generate_api_test_cases(input_data: ApiAutomationGenerationInput) -> ApiAutomationGenerationResult:
    """Generate structured API automation cases.

    This deterministic baseline keeps the product usable when no model provider
    is configured. A later LLM-backed implementation can replace this function
    without changing the service layer contract.
    """
    cases = []
    for endpoint in input_data.endpoints:
        method = endpoint.get("method", "GET")
        path = endpoint.get("path", "")
        status_code = _first_success_status(endpoint.get("responses", {}))
        required_inputs = _required_inputs(endpoint)
        status = "needs_input" if required_inputs else "ready"
        notes = f"需补充参数：{', '.join(required_inputs)}" if required_inputs else ""
        cases.append(
            {
                "title": f"{endpoint.get('summary') or method + ' ' + path} - 正常响应",
                "priority": "P1",
                "endpoint_id": endpoint["id"],
                "request": {
                    "method": method,
                    "path": path,
                    "query": {},
                    "headers": {},
                },
                "expected": {"status_code": status_code},
                "assertions": [{"type": "status_code", "expected": status_code}],
                "variables": {},
                "data_origin": {
                    "request": "openapi",
                    "expected.status_code": "openapi",
                    "assertions": "openapi",
                },
                "status": status,
                "notes": notes,
            }
        )
    return ApiAutomationGenerationResult(summary=f"生成 {len(cases)} 条接口自动化用例。", cases=cases)


def _first_success_status(responses: object) -> int:
    if isinstance(responses, dict):
        for key in responses:
            if str(key).startswith("2") and str(key).isdigit():
                return int(key)
    return 200


def _required_inputs(endpoint: dict) -> list[str]:
    missing = []
    for parameter in endpoint.get("parameters", []):
        if isinstance(parameter, dict) and parameter.get("required"):
            missing.append(str(parameter.get("name") or "parameter"))
    request_body = endpoint.get("request_body")
    if isinstance(request_body, dict) and request_body:
        missing.append("request_body")
    return missing
