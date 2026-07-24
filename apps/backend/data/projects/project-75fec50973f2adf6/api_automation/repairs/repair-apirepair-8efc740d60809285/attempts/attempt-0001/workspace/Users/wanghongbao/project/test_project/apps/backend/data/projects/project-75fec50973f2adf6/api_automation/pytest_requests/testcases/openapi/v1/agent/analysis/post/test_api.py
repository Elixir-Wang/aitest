"""
智能体数据分析接口测试
POST /openapi/v1/agent/analysis/

按日期范围查询智能体统计数据（用户数、问题数/回答数、反馈与各项占比）。
"""
import os
import pytest
from utils.data_loader import load_cases
from utils.assertions import execute_assertions
from utils.observations import record_observation

DATA_FILE = os.path.join(
    os.path.dirname(__file__),
    "cases.yaml",
)


def _build_request_kwargs(case: dict) -> dict:
    """根据用例构造 requests.request 参数"""
    kwargs = {}
    req = case.get("request", {})

    # headers
    headers = dict(req.get("headers", {}))
    if headers:
        kwargs["headers"] = headers

    # body
    body = req.get("body")
    if body is not None:
        kwargs["json"] = body

    return kwargs


def _get_cases() -> list:
    """加载当前数据文件中的测试用例"""
    return load_cases(DATA_FILE)


class TestAgentAnalysis:
    """智能体数据分析接口测试"""

    @pytest.mark.parametrize(
        "case",
        _get_cases(),
        ids=lambda c: f"{c.get('id', 'unknown')}_{c.get('test_point_key', 'unknown')}",
    )
    def test_agent_analysis(self, api_client, case):
        """执行智能体数据分析接口测试用例"""
        req = case.get("request", {})
        method = req.get("method", "POST")
        path = req.get("path", "/openapi/v1/agent/analysis/")
        kwargs = _build_request_kwargs(case)

        response = api_client.request(method, path, **kwargs)

        # 记录观察证据（inferred / needs_confirmation）
        oracle_status = case.get("oracle_status", "confirmed")
        if oracle_status in ("inferred", "needs_confirmation"):
            record_observation(case, response)

        # 执行断言
        assertions = case.get("assertions", [])
        execute_assertions(response, assertions)