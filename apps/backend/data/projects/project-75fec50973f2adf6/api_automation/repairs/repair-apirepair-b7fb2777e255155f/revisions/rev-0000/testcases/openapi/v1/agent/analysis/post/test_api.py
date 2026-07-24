"""智能体数据分析 - POST /openapi/v1/agent/analysis/"""
from __future__ import annotations

import pytest

from support.assertions import assert_response_assertions
from utils.data_loader import load_cases
from utils.observations import record_observation

DATA_FILE = "cases.yaml"


def _build_request(case: dict) -> dict:
    """根据用例数据构造请求参数字典。"""
    request_data = {
        "method": case["request"]["method"],
        "path": case["request"]["path"],
    }
    headers = dict(case["request"].get("headers") or {})
    if headers:
        request_data["headers"] = headers
    if "body" in case["request"]:
        request_data["body"] = case["request"]["body"]
    return request_data


class TestAgentAnalysis:
    """智能体数据分析"""

    @pytest.mark.parametrize(
        "case",
        load_cases(__file__, DATA_FILE),
        ids=lambda c: c.get("test_point_key", c.get("id", "")),
    )
    def test_agent_analysis(self, api_client, case: dict):
        request_data = _build_request(case)
        response = api_client.request(request_data, case.get("test_data"))

        # needs_confirmation / inferred 用例：先记录脱敏观察证据
        oracle_status = case.get("oracle_status", "")
        if oracle_status in ("needs_confirmation", "inferred"):
            record_observation(case, response)

        # 执行断言
        assert_response_assertions(response, case.get("assertions", []))
