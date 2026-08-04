import pytest
from pydantic import ValidationError

from app.agents.ui_automation.pytest_playwright.schemas import (
    AutomationPlan,
    LocatorPlan,
)


def test_locator_requires_evidence_refs():
    with pytest.raises(ValidationError):
        LocatorPlan(strategy="role", role="button", name="提交", evidence_refs=[])


def test_automation_plan_rejects_unknown_fields():
    payload = {
        "schema_version": "v2",
        "project_id": "project-1",
        "automation_case_id": "uiauto-1",
        "source_test_case_id": "case-1",
        "source_test_case_version": 1,
        "environment_id": "env-1",
        "exploration_run_id": "explore-1",
        "page_objects": [],
        "steps": [],
        "assertions": [],
        "artifacts": {
            "test_file": "testcases/generated/project_1/test_login.py",
            "data_file": "data/projects/project_1/cases/login.yaml",
            "plan_file": "data/projects/project_1/cases/login.plan.json",
        },
        "unknown": True,
    }

    with pytest.raises(ValidationError):
        AutomationPlan.model_validate(payload)


def test_automation_plan_accepts_supported_actions_and_assertions():
    plan = AutomationPlan.model_validate(
        {
            "schema_version": "v2",
            "project_id": "project-1",
            "automation_case_id": "uiauto-1",
            "source_test_case_id": "case-1",
            "source_test_case_version": 1,
            "environment_id": "env-1",
            "exploration_run_id": "explore-1",
            "page_objects": [
                {
                    "page_key": "login",
                    "class_name": "LoginPage",
                    "file_path": "pages/generated/project_1/login_page.py",
                    "route": "/login",
                    "elements": [
                        {
                            "key": "submit_button",
                            "locator": {
                                "strategy": "role",
                                "role": "button",
                                "name": "登录",
                                "evidence_refs": ["pages/page-login.yaml#submit"],
                            },
                        }
                    ],
                }
            ],
            "steps": [
                {
                    "source_step_id": "step-1",
                    "business_step_id": "step-1",
                    "title": "点击登录",
                    "kind": "click",
                    "page_key": "login",
                    "element_key": "submit_button",
                }
            ],
            "assertions": [
                {
                    "source_expected_result_id": "expected-1",
                    "kind": "visible",
                    "page_key": "login",
                    "element_key": "submit_button",
                }
            ],
            "artifacts": {
                "test_file": "testcases/generated/project_1/test_login.py",
                "data_file": "data/projects/project_1/cases/login.yaml",
                "plan_file": "data/projects/project_1/cases/login.plan.json",
            },
        }
    )

    assert plan.steps[0].kind == "click"
    assert plan.assertions[0].kind == "visible"


def test_v2_automation_plan_requires_business_step_mapping_and_title():
    payload = {
        "schema_version": "v2",
        "project_id": "project-1",
        "automation_case_id": "uiauto-1",
        "source_test_case_id": "case-1",
        "source_test_case_version": 1,
        "environment_id": "env-1",
        "steps": [
            {
                "source_step_id": "operation-1",
                "kind": "navigate",
                "page_key": "login",
            }
        ],
        "artifacts": {
            "test_file": "testcases/generated/project_1/test_login.py",
            "data_file": "data/projects/project_1/cases/login.yaml",
            "plan_file": "data/projects/project_1/cases/login.plan.json",
        },
    }

    with pytest.raises(ValidationError, match="business_step_id 和 title"):
        AutomationPlan.model_validate(payload)


def test_automation_plan_rejects_legacy_v1_schema():
    payload = {
        "schema_version": "v1",
        "project_id": "project-1",
        "automation_case_id": "uiauto-1",
        "source_test_case_id": "case-1",
        "source_test_case_version": 1,
        "environment_id": "env-1",
        "artifacts": {
            "test_file": "testcases/generated/project_1/test_login.py",
            "data_file": "data/projects/project_1/cases/login.yaml",
            "plan_file": "data/projects/project_1/cases/login.plan.json",
        },
    }

    with pytest.raises(ValidationError, match="schema_version"):
        AutomationPlan.model_validate(payload)


def test_generation_contract_rejects_unknown_business_step():
    payload = {
        "schema_version": "v2",
        "project_id": "project-1",
        "automation_case_id": "uiauto-1",
        "source_test_case_id": "case-1",
        "source_test_case_version": 1,
        "environment_id": "env-1",
        "steps": [
            {
                "source_step_id": "operation-1",
                "business_step_id": "invented-step",
                "title": "编造步骤",
                "kind": "navigate",
                "page_key": "login",
            }
        ],
        "artifacts": {
            "test_file": "testcases/generated/project_1/test_login.py",
            "data_file": "data/projects/project_1/cases/login.yaml",
            "plan_file": "data/projects/project_1/cases/login.plan.json",
        },
    }

    plan = AutomationPlan.model_validate(payload)

    with pytest.raises(ValueError, match="business_step_id 不存在于原始用例"):
        plan.require_generation_contract({"step-1": "进入登录页"})


def test_automation_plan_rejects_another_project_namespace():
    payload = {
        "schema_version": "v2",
        "project_id": "project-1",
        "automation_case_id": "uiauto-1",
        "source_test_case_id": "case-1",
        "source_test_case_version": 1,
        "environment_id": "env-1",
        "page_objects": [],
        "steps": [],
        "assertions": [],
        "artifacts": {
            "test_file": "testcases/generated/project_2/test_login.py",
            "data_file": "data/projects/project_2/cases/login.yaml",
            "plan_file": "data/projects/project_2/cases/login.plan.json",
        },
    }

    with pytest.raises(ValidationError, match="当前业务项目命名空间"):
        AutomationPlan.model_validate(payload)


def test_wait_for_response_must_follow_send_action_on_same_page():
    payload = {
        "schema_version": "v2",
        "project_id": "project-1",
        "automation_case_id": "uiauto-1",
        "source_test_case_id": "case-1",
        "source_test_case_version": 1,
        "environment_id": "env-1",
        "page_objects": [],
        "steps": [
            {
                "source_step_id": "step-1",
                "business_step_id": "step-1",
                "title": "输入消息",
                "kind": "fill",
                "page_key": "chat",
                "element_key": "input",
                "value": "hi",
            },
            {
                "source_step_id": "step-2",
                "business_step_id": "step-2",
                "title": "等待回复",
                "kind": "wait_for_response",
                "page_key": "chat",
                "element_key": "last_response",
            },
        ],
        "assertions": [],
        "artifacts": {
            "test_file": "testcases/generated/project_1/test_chat.py",
            "data_file": "data/projects/project_1/cases/chat.yaml",
            "plan_file": "data/projects/project_1/cases/chat.plan.json",
        },
    }

    with pytest.raises(ValidationError, match="必须紧跟发送消息"):
        AutomationPlan.model_validate(payload)


def test_assertion_checkpoint_must_reference_existing_step():
    payload = {
        "schema_version": "v2",
        "project_id": "project-1",
        "automation_case_id": "uiauto-1",
        "source_test_case_id": "case-1",
        "source_test_case_version": 1,
        "environment_id": "env-1",
        "page_objects": [],
        "steps": [],
        "assertions": [
            {
                "source_expected_result_id": "expected-1",
                "after_step_id": "missing-step",
                "kind": "url",
                "expected": "/workspace",
            }
        ],
        "artifacts": {
            "test_file": "testcases/generated/project_1/test_login.py",
            "data_file": "data/projects/project_1/cases/login.yaml",
            "plan_file": "data/projects/project_1/cases/login.plan.json",
        },
    }

    with pytest.raises(ValidationError, match="断言检查点不存在"):
        AutomationPlan.model_validate(payload)
