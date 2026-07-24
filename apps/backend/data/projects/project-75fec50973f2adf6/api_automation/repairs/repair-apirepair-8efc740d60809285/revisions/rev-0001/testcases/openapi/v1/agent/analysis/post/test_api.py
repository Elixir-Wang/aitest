"""智能体数据分析 - POST /openapi/v1/agent/analysis/"""
from __future__ import annotations

import pytest

from utils.assertions import assert_response_assertions
from utils.data_loader import load_cases
from utils.observations import record_observation

CASES = load_cases(__file__, "cases.yaml")


def _get_case_id(case: dict) -> str:
    return case.get("case_id") or case.get("id", "")


def _needs_observation(case: dict) -> bool:
    return case.get("oracle_status") in ("inferred", "needs_confirmation")


@pytest.mark.parametrize("case", CASES, ids=_get_case_id)
def test_agent_analysis(api_client, case: dict):
    request_data = case.get("request", {})
    assertions = case.get("assertions", [])

    response = api_client.request(request_data)

    if _needs_observation(case):
        record_observation(case, response)

    assert_response_assertions(response, assertions)
