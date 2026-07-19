"""智能体数据分析接口测试。"""
import pytest

from support.assertions import assert_response_assertions
from utils.data_loader import load_cases
from utils.observations import record_observation


TEST_CASES = load_cases(__file__, "cases.yaml")


def _case_id(case: dict) -> str:
    return case.get("case_id", "unknown-case")


@pytest.mark.parametrize("case", TEST_CASES, ids=_case_id)
def test_agent_analysis(api_client, case):
    """按用例数据发送请求，仅对已确认 Oracle 执行强断言。"""
    response = api_client.request(case["request"], case.get("test_data"))
    oracle_status = case.get("oracle_status")
    if oracle_status in {"inferred", "needs_confirmation"}:
        record_observation(case, response)
    if oracle_status in {"confirmed", "inferred"}:
        assert_response_assertions(response, case.get("assertions", []))
