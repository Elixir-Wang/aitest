from pathlib import Path

from app.agents.api_automation.pytest_requests.generator import generate_pytest_requests_code
from app.agents.api_automation.pytest_requests.schemas import PytestRequestsGenerationInput
from app.agents.api_automation.pytest_requests.skill import PYTEST_REQUESTS_CODE_GENERATION_SKILL


def _input(cases: list[dict] | None = None) -> PytestRequestsGenerationInput:
    return PytestRequestsGenerationInput(
        endpoint={
            "id": "apiend-login",
            "method": "POST",
            "path": "/login",
            "summary": "登录",
        },
        cases=cases or [],
    )


def test_generation_uses_runtime_loaded_skill_definition() -> None:
    skill = PYTEST_REQUESTS_CODE_GENERATION_SKILL

    assert skill.name == "pytest-requests-code-generation"
    assert skill.definition.description.startswith("将单个接口")
    assert {reference.name for reference in skill.definition.references} == {
        "assertion-mapping.md",
        "generation-rules.md",
        "project-structure.md",
        "request-mapping.md",
    }
    assert len(skill.fingerprint) == 64


def test_generation_returns_logical_files_without_project_context() -> None:
    result = generate_pytest_requests_code(
        _input(
            [
                {
                    "id": "apitc-login",
                    "endpoint_id": "apiend-login",
                    "title": "登录成功",
                    "request": {"method": "POST", "path": "/login"},
                    "assertions": [{"type": "status_code", "expected": 200}],
                }
            ]
        )
    )

    assert "project_id" not in PytestRequestsGenerationInput.model_fields
    assert result.endpoint_id == "apiend-login"
    assert result.case_count == 1
    assert {file.kind for file in result.files} >= {"test", "data", "support", "config"}
    assert all(not Path(file.key).is_absolute() for file in result.files)
    assert all("project-" not in file.key for file in result.files)


def test_generation_parametrizes_each_case_in_endpoint_module() -> None:
    result = generate_pytest_requests_code(
        _input(
            [
                {
                    "id": f"apitc-{index}",
                    "endpoint_id": "apiend-login",
                    "title": title,
                    "request": {"method": "POST", "path": "/login"},
                    "assertions": [{"type": "status_code", "expected": 200}],
                }
                for index, title in enumerate(("登录成功", "登录失败"), start=1)
            ]
        )
    )

    test_file = next(file for file in result.files if file.kind == "test")
    data_file = next(file for file in result.files if file.kind == "data")

    assert '@pytest.mark.parametrize("case_data", CASES' in test_file.content
    assert '"登录成功"' in data_file.content
    assert '"登录失败"' in data_file.content


def test_generation_groups_test_and_data_under_endpoint_directory() -> None:
    result = generate_pytest_requests_code(_input())

    endpoint_files = {
        file.key
        for file in result.files
        if file.kind in {"test", "data"}
    }

    assert endpoint_files == {
        "endpoints/post_login_apiend_login/test_api.py",
        "endpoints/post_login_apiend_login/cases.json",
    }


def test_generation_reads_cases_from_the_endpoint_directory() -> None:
    result = generate_pytest_requests_code(_input())

    test_file = next(file for file in result.files if file.kind == "test")

    assert 'Path(__file__).with_name("cases.json")' in test_file.content
    assert 'parents[1] / "data"' not in test_file.content


def test_generation_configures_suite_root_for_support_imports() -> None:
    result = generate_pytest_requests_code(_input())

    pytest_config = next(file for file in result.files if file.key == "pytest.ini")

    assert "pythonpath = ." in pytest_config.content


def test_generation_is_stable_for_identical_input() -> None:
    input_data = _input(
        [
            {
                "id": "apitc-login",
                "endpoint_id": "apiend-login",
                "title": "登录成功",
                "request": {"method": "POST", "path": "/login"},
                "assertions": [{"type": "status_code", "expected": 200}],
            }
        ]
    )

    assert generate_pytest_requests_code(input_data) == generate_pytest_requests_code(input_data)
