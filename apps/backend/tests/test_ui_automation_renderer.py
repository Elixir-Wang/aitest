import ast
import json

from app.agents.ui_automation.pytest_playwright.renderer import (
    initialize_suite,
    render_automation_plan,
)
from app.agents.ui_automation.pytest_playwright.schemas import AutomationPlan


def _plan() -> AutomationPlan:
    return AutomationPlan.model_validate(
        {
            "schema_version": "v1",
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
                            "key": "username_input",
                            "locator": {
                                "strategy": "role",
                                "role": "textbox",
                                "name": "用户名",
                                "evidence_refs": ["pages/page-login.yaml#username"],
                            },
                        },
                        {
                            "key": "submit_button",
                            "locator": {
                                "strategy": "role",
                                "role": "button",
                                "name": "登录",
                                "evidence_refs": ["pages/page-login.yaml#submit"],
                            },
                        },
                    ],
                }
            ],
            "steps": [
                {
                    "source_step_id": "step-1",
                    "kind": "navigate",
                    "page_key": "login",
                },
                {
                    "source_step_id": "step-2",
                    "kind": "fill",
                    "page_key": "login",
                    "element_key": "username_input",
                    "value_ref": "username",
                },
                {
                    "source_step_id": "step-3",
                    "kind": "click",
                    "page_key": "login",
                    "element_key": "submit_button",
                },
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


def test_initialize_suite_creates_project_framework(tmp_path):
    changed = initialize_suite(tmp_path)

    assert tmp_path / "pytest.ini" in changed
    assert (tmp_path / "conftest.py").exists()
    assert (tmp_path / "pages/base_page.py").exists()
    assert (tmp_path / "utils/data_loader.py").exists()
    assert (tmp_path / "scripts/save_auth_state.py").exists()
    assert (tmp_path / ".deepagents/skills/pytest-playwright-ui-generation/SKILL.md").exists()

    base_page = (tmp_path / "pages/base_page.py").read_text(encoding="utf-8")
    waiters = (tmp_path / "utils/waiters.py").read_text(encoding="utf-8")
    conftest = (tmp_path / "conftest.py").read_text(encoding="utf-8")
    assert "click_first_visible" in base_page
    assert "wait_for_page_ready" in waiters
    assert "failure-screenshots" in conftest
    assert '"width": int(os.getenv("UI_VIEWPORT_WIDTH", "1440"))' in conftest
    assert '"height": int(os.getenv("UI_VIEWPORT_HEIGHT", "900"))' in conftest


def test_initialize_suite_preserves_existing_files(tmp_path):
    target = tmp_path / "pages/base_page.py"
    target.parent.mkdir(parents=True)
    target.write_text("# custom\n", encoding="utf-8")

    initialize_suite(tmp_path)

    assert target.read_text(encoding="utf-8") == "# custom\n"


def test_render_plan_writes_pom_test_and_plan_without_inline_test_data(tmp_path):
    initialize_suite(tmp_path)
    data_file = tmp_path / "data/projects/project_1/cases/login.yaml"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text("username: secret-user\n", encoding="utf-8")

    paths = render_automation_plan(tmp_path, _plan())

    page_source = paths["page_files"][0].read_text(encoding="utf-8")
    test_source = paths["test_file"].read_text(encoding="utf-8")
    plan_payload = json.loads(paths["plan_file"].read_text(encoding="utf-8"))

    assert "get_by_role(\"textbox\", name=\"用户名\")" in page_source
    assert "load_case_data" in test_source
    assert "secret-user" not in test_source
    assert "case_data[\"username\"]" in test_source
    assert plan_payload["source_test_case_id"] == "case-1"


def test_render_plan_reuses_existing_page_file_and_adds_elements(tmp_path):
    initialize_suite(tmp_path)
    plan = _plan()
    render_automation_plan(tmp_path, plan)
    first_source = (tmp_path / "pages/generated/project_1/login_page.py").read_text(encoding="utf-8")

    render_automation_plan(tmp_path, plan)
    second_source = (tmp_path / "pages/generated/project_1/login_page.py").read_text(encoding="utf-8")

    assert first_source == second_source
    assert second_source.count("def submit_button") == 1


def test_render_plan_parameterizes_dynamic_text_selection(tmp_path):
    initialize_suite(tmp_path)
    payload = _plan().model_dump(mode="json")
    payload["parameters"] = ["target_model"]
    payload["steps"][2] = {
        "source_step_id": "step-3",
        "kind": "click_parameter_text",
        "page_key": "login",
        "value_ref": "target_model",
    }
    plan = AutomationPlan.model_validate(payload)
    data_file = tmp_path / plan.artifacts.data_file
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text("parameters:\n  target_model:\n    values: [qwen-plus]\n", encoding="utf-8")

    paths = render_automation_plan(tmp_path, plan)
    source = paths["test_file"].read_text(encoding="utf-8")

    assert '@pytest.mark.parametrize(' in source
    assert 'CASE_DATA["parameters"]["target_model"]["values"]' in source
    assert "def test_uiauto_1(page, ui_case, target_model):" in source
    assert "login_page.visible_text(str(target_model)).click()" in source


def test_render_plan_groups_explicit_business_steps(tmp_path):
    initialize_suite(tmp_path)
    payload = _plan().model_dump(mode="json")
    payload["steps"][1].update(
        business_step_id="business-login",
        title="填写并提交登录",
    )
    payload["steps"][2].update(
        business_step_id="business-login",
        title="填写并提交登录",
    )

    source = render_automation_plan(tmp_path, AutomationPlan.model_validate(payload))[
        "test_file"
    ].read_text(encoding="utf-8")

    assert source.count('with ui_case.step("business-login"') == 1
    assert "UI_CASE_STEP_DEFINITIONS = [" in source
    assert 'operation_ids=["step-2", "step-3"]' in source
    assert source.index("username_input.fill") < source.index("submit_button.click")


def test_rendered_step_definitions_are_valid_python_literals(tmp_path):
    initialize_suite(tmp_path)
    source = render_automation_plan(tmp_path, _plan())["test_file"].read_text(encoding="utf-8")
    module = ast.parse(source)
    definitions_assignment = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "UI_CASE_STEP_DEFINITIONS" for target in node.targets)
    )

    definitions = ast.literal_eval(definitions_assignment.value)

    assert definitions[0]["visible"] is True
    assert '"visible": true' not in source
    assert "UI_AUTOMATION_INSTRUMENTATION_VERSION = 3" in source


def test_render_plan_does_not_guess_business_step_for_v1_plan(tmp_path):
    initialize_suite(tmp_path)

    source = render_automation_plan(tmp_path, _plan())["test_file"].read_text(encoding="utf-8")

    assert 'with ui_case.step("step-1", "step-1"' in source
    assert 'with ui_case.step("step-2", "step-2"' in source
    assert 'with ui_case.step("step-3", "step-3"' in source


def test_render_plan_waits_for_new_stable_response_without_welcome_message(tmp_path):
    initialize_suite(tmp_path)
    payload = _plan().model_dump(mode="json")
    payload["page_objects"][0]["elements"].append(
        {
            "key": "last_response",
            "locator": {
                "strategy": "css",
                "value": ".assistant-message:last-child",
                "evidence_refs": ["trace.zip#assistant-message"],
            },
        }
    )
    payload["steps"].append(
        {
            "source_step_id": "step-4",
            "kind": "wait_for_response",
            "page_key": "login",
            "element_key": "last_response",
        }
    )
    plan = AutomationPlan.model_validate(payload)

    source = render_automation_plan(tmp_path, plan)["test_file"].read_text(encoding="utf-8")

    snapshot = "_response_before_3 = _last_locator_text(login_page.last_response)"
    assert source.index(snapshot) < source.index("login_page.submit_button.click()")
    assert "_wait_for_response(login_page.last_response, _response_before_3)" in source
    assert "if current and current != previous_text:" in source
    assert "stable_ms=2_000" in source


def test_render_plan_places_assertion_after_its_checkpoint_step(tmp_path):
    initialize_suite(tmp_path)
    payload = _plan().model_dump(mode="json")
    payload["assertions"][0]["after_step_id"] = "step-1"
    payload["assertions"].append(
        {
            "source_expected_result_id": "expected-url",
            "after_step_id": "step-3",
            "kind": "url",
            "expected": "/workspace",
        }
    )

    source = render_automation_plan(tmp_path, AutomationPlan.model_validate(payload))[
        "test_file"
    ].read_text(encoding="utf-8")

    assert source.index("expect(login_page.submit_button).to_be_visible()") < source.index(
        "login_page.username_input.fill"
    )
    assert source.index("login_page.submit_button.click()") < source.index(
        "expect(page).to_have_url(re.compile(re.escape(str(\"/workspace\"))))"
    )


def test_render_plan_commits_auto_populated_input_without_hardcoded_value(tmp_path):
    initialize_suite(tmp_path)
    payload = _plan().model_dump(mode="json")
    payload["steps"][1] = {
        "source_step_id": "step-2",
        "kind": "commit_value",
        "page_key": "login",
        "element_key": "username_input",
    }

    source = render_automation_plan(tmp_path, AutomationPlan.model_validate(payload))[
        "test_file"
    ].read_text(encoding="utf-8")

    assert "def _commit_current_value(locator):" in source
    assert "current = locator.input_value().strip()" in source
    assert 'time.strftime("release-%Y%m%d%H%M%S")' in source
    assert "_commit_current_value(login_page.username_input)" in source
