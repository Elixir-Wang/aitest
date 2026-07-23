"""智能体数据分析 - POST /openapi/v1/agent/analysis/"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from support.assertions import assert_response_assertions
from utils.observations import record_observation


def _load_cases(data_file: str) -> list[dict]:
    """加载当前目录下的 YAML 用例数据。"""
    path = Path(__file__).parent / data_file
    if not path.is_file():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("cases", data.get("test_cases", [data]))
    return []


def _build_request(case: dict) -> dict:
    """从用例数据构建 request 参数字典。"""
    req = case.get("request", {})
    request_data = {
        "method": req.get("method", "POST"),
        "path": req.get("path", ""),
    }
    query = req.get("query")
    if query and query.get("$text") != "{}":
        request_data["query"] = query
    headers = req.get("headers")
    if headers and headers.get("$text") != "{}":
        # 过滤掉 $text 元字段，保留真实 header 覆盖
        actual_headers = {k: v for k, v in headers.items() if k != "$text"}
        if actual_headers:
            request_data["headers"] = actual_headers
    if "body" in req:
        body = req["body"]
        # 处理 $text 标记的空对象
        if isinstance(body, dict) and body.get("$text") == "{}":
            request_data["body"] = {}
        else:
            request_data["body"] = body
    return request_data


def _should_skip_assertions(case: dict) -> bool:
    """needs_confirmation 且断言仅有推断状态码时跳过断言执行。"""
    oracle_status = case.get("oracle_status", "")
    if oracle_status not in ("inferred", "needs_confirmation"):
        return False
    assertions = case.get("assertions", [])
    if not assertions:
        return True
    # 检查是否所有断言都是 inferred 状态码（无事实依据）
    # 对于 needs_confirmation，notes 中标记了"按常见 REST 契约推断"的断言不执行
    return True


CASES = _load_cases("cases.yaml")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.get("test_point_key", ""))
def test_agent_analysis(api_client, case: dict):
    """智能体数据分析 - 参数化用例"""
    request_data = _build_request(case)
    response = api_client.request(request_data, case.get("test_data") or {})

    oracle_status = case.get("oracle_status", "")

    # inferred / needs_confirmation 记录观察证据
    if oracle_status in ("inferred", "needs_confirmation"):
        record_observation(case, response)

    assertions = case.get("assertions", [])
    if assertions:
        assert_response_assertions(response, assertions)
