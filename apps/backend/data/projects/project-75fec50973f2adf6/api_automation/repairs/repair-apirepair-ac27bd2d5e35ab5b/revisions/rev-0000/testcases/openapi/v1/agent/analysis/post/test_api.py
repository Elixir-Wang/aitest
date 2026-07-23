"""智能体数据分析 - 接口测试。"""
from __future__ import annotations

import pytest

from utils.assert_utils import assert_response
from utils.data_loader import load_cases

DATA_FILE = "cases.yaml"


def _build_request(case: dict) -> dict:
    """按快照内容构建请求，并保留“请求体缺失”的语义。"""
    source = case["request"]
    request_data = {
        "method": source["method"],
        "path": source["path"],
    }
    query = source.get("query")
    if query:
        request_data["query"] = query
    headers = source.get("headers")
    if headers:
        request_data["headers"] = headers
    if "body" in source:
        request_data["body"] = source["body"]
    return request_data


class TestAgentAnalysis:
    """POST /openapi/v1/agent/analysis/。"""

    cases = load_cases(__file__, DATA_FILE)

    @pytest.mark.parametrize(
        "case",
        cases,
        ids=[case.get("title", case.get("test_point_key", "")) for case in cases],
    )
    def test_agent_analysis(self, api_client, case):
        response = api_client.request(_build_request(case), case.get("test_data"))
        assert_response(response, case.get("assertions"))
