import json
from pathlib import Path

import pytest

from app.services import login_form_analyzer_service


def test_analyze_login_form_maps_element_ids_to_selectors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "login-page.png"
    image_path.write_bytes(b"fake-png")
    elements = [
        {
            "element_id": "login-el-user",
            "tag": "input",
            "placeholder": "请输入账号",
            "selector": '[data-ai-testing-login-el="login-el-user"]',
            "stable_selector": 'input[placeholder="请输入账号"]',
            "locator": {"type": "placeholder", "value": "请输入账号"},
        },
        {
            "element_id": "login-el-password",
            "tag": "input",
            "type": "password",
            "placeholder": "请输入密码",
            "selector": '[data-ai-testing-login-el="login-el-password"]',
            "stable_selector": 'input[placeholder="请输入密码"]',
            "locator": {"type": "placeholder", "value": "请输入密码"},
        },
        {
            "element_id": "login-el-1",
            "tag": "input",
            "placeholder": "请输入图形验证码",
            "selector": '[data-ai-testing-login-el="login-el-1"]',
            "stable_selector": 'input[placeholder="请输入图形验证码"]',
            "locator": {"type": "placeholder", "value": "请输入图形验证码"},
        },
        {
            "element_id": "login-el-2",
            "tag": "img",
            "class_name": "verify-code",
            "selector": '[data-ai-testing-login-el="login-el-2"]',
            "stable_selector": "img.verify-code",
            "locator": {"type": "css", "value": "img.verify-code"},
        },
        {
            "element_id": "login-el-3",
            "tag": "input",
            "type": "checkbox",
            "text": "我已阅读并同意《用户协议》",
            "selector": '[data-ai-testing-login-el="login-el-3"]',
            "stable_selector": 'input[type="checkbox"]',
            "locator": {"type": "label", "value": "我已阅读并同意"},
        },
        {
            "element_id": "login-el-4",
            "tag": "button",
            "text": "登录",
            "selector": '[data-ai-testing-login-el="login-el-4"]',
            "stable_selector": "button",
            "locator": {"type": "role", "role": "button", "name": "登录"},
        },
    ]

    class FakeResponse:
        content = json.dumps(
            {
                "username_element_id": "login-el-user",
                "password_element_id": "login-el-password",
                "captcha_image_element_id": "login-el-2",
                "captcha_input_element_id": "login-el-1",
                "agreement_element_id": "login-el-3",
                "login_button_element_id": "login-el-4",
            }
        )

    class FakeModel:
        async def ainvoke(self, _messages):
            return FakeResponse()

    monkeypatch.setattr(login_form_analyzer_service, "_build_login_form_analyzer_model", lambda: FakeModel())

    plan = login_form_analyzer_service.analyze_login_form(image_path, elements)

    assert plan["strategy"] == "planned"
    assert plan["username_locator"] == {"type": "placeholder", "value": "请输入账号"}
    assert plan["captcha_input_locator"] == {"type": "placeholder", "value": "请输入图形验证码"}
    assert plan["agreement_locator"] == {"type": "label", "value": "我已阅读并同意"}
    assert plan["login_button_locator"] == {"type": "role", "role": "button", "name": "登录"}


def test_analyze_login_form_falls_back_to_heuristic_when_plan_incomplete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "login-page.png"
    image_path.write_bytes(b"fake-png")
    elements = [{"element_id": "login-el-1", "selector": '[data-ai-testing-login-el="login-el-1"]'}]

    class FakeResponse:
        content = json.dumps(
            {
                "username_element_id": "login-el-1",
                "password_element_id": "",
                "captcha_image_element_id": "login-el-1",
                "captcha_input_element_id": "",
                "agreement_element_id": None,
                "login_button_element_id": "",
            }
        )

    class FakeModel:
        async def ainvoke(self, _messages):
            return FakeResponse()

    monkeypatch.setattr(login_form_analyzer_service, "_build_login_form_analyzer_model", lambda: FakeModel())

    plan = login_form_analyzer_service.analyze_login_form(image_path, elements)

    assert plan == {"strategy": "heuristic"}


def test_analyze_login_form_uses_heuristic_agreement_when_llm_omits_checkbox(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "login-page.png"
    image_path.write_bytes(b"fake-png")
    elements = [
        {
            "element_id": "login-el-user",
            "tag": "input",
            "placeholder": "请输入账号",
            "selector": '[data-ai-testing-login-el="login-el-user"]',
            "stable_selector": 'input[placeholder="请输入账号"]',
        },
        {
            "element_id": "login-el-password",
            "tag": "input",
            "type": "password",
            "placeholder": "请输入密码",
            "selector": '[data-ai-testing-login-el="login-el-password"]',
            "stable_selector": 'input[placeholder="请输入密码"]',
        },
        {
            "element_id": "login-el-1",
            "tag": "input",
            "placeholder": "请输入图形验证码",
            "selector": '[data-ai-testing-login-el="login-el-1"]',
            "stable_selector": 'input[placeholder="请输入图形验证码"]',
        },
        {
            "element_id": "login-el-2",
            "tag": "img",
            "class_name": "verify-code",
            "selector": '[data-ai-testing-login-el="login-el-2"]',
            "stable_selector": "img.verify-code",
        },
        {
            "element_id": "login-el-3",
            "tag": "div",
            "kind": "agreement",
            "class_name": "uui-checkbox-wrap",
            "text": "我已阅读并同意《用户协议》和《隐私政策》",
            "selector": '[data-ai-testing-login-el="login-el-3"]',
            "stable_selector": ".uui-checkbox-wrap",
            "locator": {"type": "text", "value": "我已阅读并同意"},
        },
        {
            "element_id": "login-el-4",
            "tag": "button",
            "text": "登录",
            "selector": '[data-ai-testing-login-el="login-el-4"]',
            "stable_selector": "button",
        },
    ]

    class FakeResponse:
        content = json.dumps(
            {
                "username_element_id": "login-el-user",
                "password_element_id": "login-el-password",
                "captcha_image_element_id": "login-el-2",
                "captcha_input_element_id": "login-el-1",
                "agreement_element_id": None,
                "login_button_element_id": "login-el-4",
            }
        )

    class FakeModel:
        async def ainvoke(self, _messages):
            return FakeResponse()

    monkeypatch.setattr(login_form_analyzer_service, "_build_login_form_analyzer_model", lambda: FakeModel())

    plan = login_form_analyzer_service.analyze_login_form(image_path, elements)

    assert plan["strategy"] == "planned"
    assert plan["agreement_locator"] == {"type": "text", "value": "我已阅读并同意"}
    assert plan["has_agreement_checkbox"] is True


def test_analyze_login_form_preserves_text_first_agreement_selector(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "login-page.png"
    image_path.write_bytes(b"fake-png")
    elements = [
        {
            "element_id": "login-el-user",
            "tag": "input",
            "stable_selector": 'input[placeholder="请输入邮箱/手机号"]',
            "locator": {"type": "placeholder", "value": "请输入邮箱/手机号"},
        },
        {
            "element_id": "login-el-password",
            "tag": "input",
            "type": "password",
            "stable_selector": 'input[placeholder="请输入密码"]',
            "locator": {"type": "placeholder", "value": "请输入密码"},
        },
        {
            "element_id": "login-el-captcha-input",
            "tag": "input",
            "stable_selector": 'input[placeholder="请输入图形验证码"]',
            "locator": {"type": "placeholder", "value": "请输入图形验证码"},
        },
        {
            "element_id": "login-el-captcha-image",
            "tag": "img",
            "stable_selector": "img.verify-code",
            "locator": {"type": "css", "value": "img.verify-code"},
        },
        {
            "element_id": "login-el-agreement",
            "tag": "div",
            "kind": "agreement",
            "class_name": "policy",
            "text": "我已阅读并同意 《用户协议》 和 《隐私政策》",
            "stable_selector": '.policy:has-text("我已阅读并同意")',
            "locator": {"type": "text", "value": "我已阅读并同意"},
        },
        {
            "element_id": "login-el-button",
            "tag": "button",
            "stable_selector": "button",
            "locator": {"type": "role", "role": "button", "name": "登录"},
        },
    ]

    class FakeResponse:
        content = json.dumps(
            {
                "username_element_id": "login-el-user",
                "password_element_id": "login-el-password",
                "captcha_image_element_id": "login-el-captcha-image",
                "captcha_input_element_id": "login-el-captcha-input",
                "agreement_element_id": "login-el-agreement",
                "login_button_element_id": "login-el-button",
            }
        )

    class FakeModel:
        async def ainvoke(self, _messages):
            return FakeResponse()

    monkeypatch.setattr(login_form_analyzer_service, "_build_login_form_analyzer_model", lambda: FakeModel())

    plan = login_form_analyzer_service.analyze_login_form(image_path, elements)

    assert plan["strategy"] == "planned"
    assert plan["agreement_locator"] == {"type": "text", "value": "我已阅读并同意"}
