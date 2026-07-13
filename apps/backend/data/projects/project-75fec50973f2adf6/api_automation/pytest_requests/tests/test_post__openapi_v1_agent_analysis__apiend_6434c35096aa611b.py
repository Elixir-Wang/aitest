import json
from pathlib import Path

import pytest

from support.assertions import assert_response_assertions


CASES = json.loads(
    (Path(__file__).parents[1] / "data" / "test_post__openapi_v1_agent_analysis__apiend_6434c35096aa611b.json").read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case_data", CASES, ids=lambda case: case.get("title", "api-case"))
def test_api_case_execution(api_client, case_data):
    response = api_client.request(case_data["request"], case_data.get("test_data", {}))
    assert_response_assertions(response, case_data["assertions"])
