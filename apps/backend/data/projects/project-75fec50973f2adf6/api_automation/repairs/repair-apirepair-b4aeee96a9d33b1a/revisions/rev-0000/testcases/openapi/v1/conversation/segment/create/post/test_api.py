"""创建智能体会话 - 接口测试"""
from __future__ import annotations

import pytest

from utils.assert_utils import assert_response
from utils.data_loader import load_cases

DATA_FILE = "cases.yaml"


def _build_request(case: dict) -> dict:
    """从用例数据构建请求参数字典。"""
    request_data = {
        "method": case["request"]["method"],
        "path": case["request"]["path"],
    }
    query = case["request"].get("query")
    if query:
        request_data["query"] = query
    headers = case["request"].get("headers")
    if headers:
        request_data["headers"] = headers
    if "body" in case["request"]:
        body = case["request"]["body"]
        if body == "" or body is None:
            request_data["body"] = {}
        else:
            request_data["body"] = body
    return request_data


class TestConversationSegmentCreate:
    """创建智能体会话"""

    cases = load_cases(__file__, DATA_FILE)

    @pytest.mark.parametrize(
        "case",
        cases,
        ids=[c.get("title", c.get("test_point_key", "")) for c in cases],
    )
    def test_conversation_segment_create(self, api_client, case):
        request_data = _build_request(case)
        response = api_client.request(request_data, case.get("test_data"))
        assert_response(response, case.get("assertions"))
