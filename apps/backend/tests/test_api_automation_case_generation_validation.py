import pytest

from app.agents.api_automation.case_generation.schemas import ApiGeneratedCase
from app.agents.api_automation.case_generation.validation import validate_generated_cases


ENDPOINT = {"id": "apiend-1", "method": "POST", "path": "/analysis"}
PLANNED = [
    {"key": "success.minimum_valid"},
    {"key": "request_body.missing"},
]


def _case(key: str, *, request: dict | None = None, coverage: str = "negative") -> ApiGeneratedCase:
    return ApiGeneratedCase(
        title=key,
        endpoint_id="apiend-1",
        test_point_key=key,
        oracle_status="needs_confirmation" if coverage != "positive" else "confirmed",
        coverage=coverage,
        request=request or {"method": "POST", "path": "/analysis"},
        assertions=[{"type": "status_code", "expected": 200}],
    )


def test_validation_rejects_missing_planned_test_point() -> None:
    with pytest.raises(ValueError, match="遗漏测试点.*request_body.missing"):
        validate_generated_cases(
            ENDPOINT,
            PLANNED,
            [_case("success.minimum_valid", coverage="positive")],
        )


def test_validation_rejects_duplicate_test_point_key() -> None:
    duplicate = _case("success.minimum_valid", coverage="positive")

    with pytest.raises(ValueError, match="重复 test_point_key"):
        validate_generated_cases(ENDPOINT, PLANNED, [duplicate, duplicate])


def test_validation_rejects_legacy_case_without_test_point_key() -> None:
    legacy_case = _case("success.minimum_valid", coverage="positive")
    legacy_case.test_point_key = ""

    with pytest.raises(ValueError, match="缺少 test_point_key"):
        validate_generated_cases(ENDPOINT, PLANNED, [legacy_case])


def test_validation_rejects_empty_object_as_missing_request_body() -> None:
    cases = [
        _case("success.minimum_valid", coverage="positive"),
        _case(
            "request_body.missing",
            request={"method": "POST", "path": "/analysis", "body": {}},
        ),
    ]

    with pytest.raises(ValueError, match="必须省略 body"):
        validate_generated_cases(ENDPOINT, PLANNED, cases)


def test_validation_accepts_complete_point_set_with_real_missing_body() -> None:
    validate_generated_cases(
        ENDPOINT,
        PLANNED,
        [
            _case(
                "success.minimum_valid",
                coverage="positive",
                request={"method": "POST", "path": "/analysis", "body": {"start_date": "2026-02-01"}},
            ),
            _case("request_body.missing"),
        ],
    )


def test_validation_rejects_model_changes_to_approved_oracle_fact() -> None:
    planned = [
        {
            "key": "success.minimum_valid",
            "oracle_status": "confirmed",
            "assertions": [{"type": "status_code", "path": "", "expected": 201}],
            "oracle_fact": {"approved_by": "u-admin", "evidence_run_ids": ["apirun-1"]},
        }
    ]

    with pytest.raises(ValueError, match="审批断言不一致"):
        validate_generated_cases(
            ENDPOINT,
            planned,
            [_case("success.minimum_valid", coverage="positive")],
        )


def test_validation_accepts_exact_approved_oracle_fact() -> None:
    planned = [
        {
            "key": "success.minimum_valid",
            "oracle_status": "confirmed",
            "assertions": [{"type": "status_code", "path": "", "expected": 201}],
            "oracle_fact": {"approved_by": "u-admin", "evidence_run_ids": ["apirun-1"]},
        }
    ]
    case = _case("success.minimum_valid", coverage="positive")
    case.assertions = [{"type": "status_code", "path": "", "expected": 201}]

    validate_generated_cases(ENDPOINT, planned, [case])


def test_validation_rejects_missing_required_response_contract_assertion() -> None:
    planned = [
        {
            "key": "success.minimum_valid",
            "oracle_status": "confirmed",
            "required_assertions": [
                {"type": "status_code", "path": "", "expected": 200},
                {"type": "jsonpath_exists", "path": "$.data.user_cnt", "expected": True},
            ],
        }
    ]

    with pytest.raises(ValueError, match=r"缺少响应契约断言.*jsonpath_exists \$\.data\.user_cnt"):
        validate_generated_cases(ENDPOINT, planned, [_case("success.minimum_valid", coverage="positive")])


def test_validation_allows_needs_confirmation_case_with_required_contract_assertions() -> None:
    planned = [
        {
            "key": "request_body.missing",
            "oracle_status": "needs_confirmation",
            "required_assertions": [
                {"type": "jsonpath_exists", "path": "$.code", "expected": True},
            ],
        }
    ]
    case = _case("request_body.missing")
    case.assertions = [{"type": "jsonpath_exists", "path": "$.code", "expected": True}]

    validate_generated_cases(ENDPOINT, planned, [case])
