"""测试用例 - v1/agent"""
import pytest

from api.module_v1 import V1API
from utils.data_loader import load_cases
from utils.assert_utils import assert_response


TEST_CASES = load_cases(__file__, "test_agent.yaml")


@pytest.mark.parametrize("case", TEST_CASES)
def test_agent(case):
    """智能体数据分析"""
    api = V1API()
    method_name = "post_agent"
    api_method = getattr(api, method_name)

    response = api_method(**case.get("request", {}))
    assert_response(response, case.get("assertions", {}))
