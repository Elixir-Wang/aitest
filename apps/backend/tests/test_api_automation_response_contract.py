import pytest

from app.agents.api_automation.case_generation.response_contract import (
    ResponseContractError,
    compile_response_contract,
    merge_response_assertions,
)


def _assertion_dicts(assertions):
    return [assertion.model_dump() for assertion in assertions]


def test_compile_json_response_contract_includes_nested_fields_and_fixed_success_code() -> None:
    endpoint = {
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "code": {
                                    "type": "string",
                                    "description": '返回码，"000000" 表示成功',
                                    "example": "000000",
                                },
                                "message": {"type": "string", "example": "ok"},
                                "data": {
                                    "type": "object",
                                    "properties": {
                                        "user_cnt": {"type": "number", "example": 123},
                                        "normal_answer_rate": {
                                            "type": "number",
                                            "format": "float",
                                            "example": 98.5,
                                        },
                                    },
                                },
                            },
                        }
                    }
                }
            }
        }
    }

    assertions = _assertion_dicts(compile_response_contract(endpoint, expected_status_code=200))

    assert assertions == [
        {"type": "status_code", "path": "", "expected": 200},
        {"type": "content_type", "path": "", "expected": "application/json"},
        {"type": "jsonpath_equals", "path": "$.code", "expected": "000000"},
        {"type": "jsonpath_exists", "path": "$.message", "expected": True},
        {"type": "jsonpath_exists", "path": "$.data", "expected": True},
        {"type": "jsonpath_exists", "path": "$.data.user_cnt", "expected": True},
        {"type": "jsonpath_exists", "path": "$.data.normal_answer_rate", "expected": True},
    ]


def test_compile_array_contract_does_not_assume_first_item_or_non_empty() -> None:
    endpoint = {
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "items": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {"id": {"type": "string"}},
                                    },
                                }
                            },
                        }
                    }
                }
            }
        }
    }

    assertions = _assertion_dicts(compile_response_contract(endpoint, expected_status_code=200))

    assert {"type": "jsonpath_exists", "path": "$.items", "expected": True} in assertions
    assert not any("[0]" in assertion["path"] for assertion in assertions)
    assert not any(assertion["type"] == "body_not_empty" for assertion in assertions)


def test_compile_binary_response_contract_avoids_jsonpath() -> None:
    endpoint = {
        "responses": {
            "200": {
                "content": {
                    "application/octet-stream": {
                        "schema": {"type": "string", "format": "binary"}
                    }
                }
            }
        }
    }

    assertions = _assertion_dicts(compile_response_contract(endpoint, expected_status_code=200))

    assert assertions == [
        {"type": "status_code", "path": "", "expected": 200},
        {"type": "content_type", "path": "", "expected": "application/octet-stream"},
        {"type": "body_not_empty", "path": "", "expected": True},
    ]


def test_compile_response_contract_rejects_unresolved_reference() -> None:
    endpoint = {
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/AnalysisResponse"}
                    }
                }
            }
        }
    }

    with pytest.raises(ResponseContractError, match="无法解析响应 Schema 引用"):
        compile_response_contract(endpoint, expected_status_code=200)


def test_merge_response_assertions_completes_missing_contract_and_deduplicates() -> None:
    required = [
        {"type": "status_code", "path": "", "expected": 200},
        {"type": "jsonpath_equals", "path": "$.code", "expected": "000000"},
        {"type": "jsonpath_exists", "path": "$.data.user_cnt", "expected": True},
    ]
    generated = [
        {"type": "status_code", "path": "", "expected": 200},
        {"type": "jsonpath_exists", "path": "$.message", "expected": True},
    ]

    assertions = _assertion_dicts(merge_response_assertions(required, generated))

    assert assertions == [
        {"type": "status_code", "path": "", "expected": 200},
        {"type": "jsonpath_equals", "path": "$.code", "expected": "000000"},
        {"type": "jsonpath_exists", "path": "$.data.user_cnt", "expected": True},
        {"type": "jsonpath_exists", "path": "$.message", "expected": True},
    ]


def test_merge_response_assertions_prefers_contract_over_generated_fixed_value() -> None:
    assertions = _assertion_dicts(
        merge_response_assertions(
            [{"type": "jsonpath_equals", "path": "$.code", "expected": "000000"}],
            [{"type": "jsonpath_equals", "path": "$.code", "expected": "0"}],
        )
    )

    assert assertions == [
        {"type": "jsonpath_equals", "path": "$.code", "expected": "000000"},
    ]


def test_merge_response_assertions_prefers_contract_over_generated_status_code() -> None:
    assertions = _assertion_dicts(
        merge_response_assertions(
            [{"type": "status_code", "path": "", "expected": 200}],
            [{"type": "status_code", "path": "", "expected": 201}],
        )
    )

    assert assertions == [
        {"type": "status_code", "path": "", "expected": 200},
    ]
