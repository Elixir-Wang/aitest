"""智能体数据分析 - POST /openapi/v1/agent/analysis/"""
from __future__ import annotations

import pytest

from utils.data_loader import load_cases
from utils.assert_utils import assert_response
from utils.observations import record_observation

DATA_FILE = "cases.yaml"


def _build_request(case: dict) -> dict:
    """从用例数据构建 request_data dict。"""
    req = case.get("request", {})
    request_data = {
        "method": req.get("method", "POST"),
        "path": req.get("path", "/openapi/v1/agent/analysis/"),
    }
    headers = req.get("headers") or {}
    if headers:
        request_data["headers"] = headers
    if "body" in req:
        request_data["body"] = req.get("body")
    return request_data


@pytest.mark.parametrize(
    "case",
    load_cases(__file__, DATA_FILE),
    ids=lambda c: c.get("test_point_key", c.get("id", "")),
)
def test_agent_analysis(api_client, case):
    """智能体数据分析 - 参数化测试"""
    request_data = _build_request(case)
    response = api_client.request(request_data, case.get("test_data"))

    oracle_status = case.get("oracle_status", "needs_confirmation")

    # inferred / needs_confirmation: 先记录观察证据，再执行当前最佳断言
    if oracle_status in ("inferred", "needs_confirmation"):
        record_observation(case, response)

    # 执行断言（所有 oracle_status 都执行）
    assertions = case.get("assertions", [])
    if assertions:
        assert_response(response, assertions)
