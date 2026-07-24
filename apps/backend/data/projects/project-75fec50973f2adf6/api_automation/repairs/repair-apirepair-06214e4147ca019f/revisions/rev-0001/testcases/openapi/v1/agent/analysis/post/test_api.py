"""智能体数据分析 - POST /openapi/v1/agent/analysis/"""
from __future__ import annotations

import pytest

from utils.assert_utils import assert_response
from utils.data_loader import load_cases
from utils.observations import record_observation

DATA_FILE = "cases.yaml"


def _build_request(case: dict) -> dict:
    """构建请求字典，合并 case 中的 request 和 test_data。"""
    request_data = dict(case.get("request", {}))
    test_data = case.get("test_data") or {}
    if test_data:
        request_data.setdefault("test_data", {}).update(test_data)
    return request_data


@pytest.mark.parametrize(
    "case",
    load_cases(__file__, DATA_FILE),
    ids=lambda c: c.get("test_point_key", c.get("id", "unknown")),
)
def test_agent_analysis(api_client, case: dict):
    """智能体数据分析 - 参数化测试"""
    request_data = _build_request(case)
    response = api_client.request(request_data)

    oracle_status = case.get("oracle_status", "confirmed")
    if oracle_status in ("inferred", "needs_confirmation"):
        record_observation(case, response)

    assertions = case.get("assertions", [])
    if assertions:
        assert_response(response, assertions)
