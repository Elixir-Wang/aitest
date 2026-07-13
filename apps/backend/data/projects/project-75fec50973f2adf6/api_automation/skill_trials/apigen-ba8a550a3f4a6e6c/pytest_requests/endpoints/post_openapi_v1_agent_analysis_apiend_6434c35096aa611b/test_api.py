import json
from pathlib import Path

import pytest

from support.assertions import assert_response_assertions


CASES = json.loads(
    Path(__file__).with_name("cases.json").read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case_data", CASES, ids=lambda case: case.get("title", "api-case"))
def test_api_case_execution(api_client, case_data):
    response = api_client.request(case_data["request"], case_data.get("test_data", {}))
    assert_response_assertions(response, case_data["assertions"])
