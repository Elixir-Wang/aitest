import time

import re

from pathlib import Path

import pytest
from playwright.sync_api import expect

from utils.data_loader import load_case_data
from pages.generated.project_75fec50973f2adf6.bot_settings_page import BotSettingsPage
from pages.generated.project_75fec50973f2adf6.publish_dialog_page import PublishDialogPage
from pages.generated.project_75fec50973f2adf6.workspace_page import WorkspacePage


def _last_locator_text(locator):
    try:
        if locator.count() == 0:
            return ""
        return (locator.last.text_content(timeout=250) or "").strip()
    except Exception:
        return ""


def _wait_for_response(locator, previous_text, timeout_ms=120_000, stable_ms=2_000):
    deadline = time.monotonic() + timeout_ms / 1_000
    stable_since = None
    candidate = ""
    while time.monotonic() < deadline:
        current = _last_locator_text(locator)
        if current and current != previous_text:
            if current != candidate:
                candidate = current
                stable_since = time.monotonic()
            elif stable_since is not None and (time.monotonic() - stable_since) * 1_000 >= stable_ms:
                return current
        else:
            candidate = ""
            stable_since = None
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for a new stable assistant response")


def _commit_current_value(locator):
    current = locator.input_value().strip()
    if not current:
        current = time.strftime("release-%Y%m%d%H%M%S") + f"-{time.time_ns() % 10_000:04d}"
    locator.fill("")
    locator.fill(current)


CASE_DATA = load_case_data(Path(__file__).resolve().parents[3] / "data/projects/project_75fec50973f2adf6/cases/mtc_1b4a3792fd2cf4e3_uiauto_uigen_eda941ca57507528.yaml")


@pytest.mark.parametrize(
    "target_model",
    CASE_DATA["parameters"]["target_model"]["values"],
    ids=lambda value: str(value),
)
def test_uiauto_uigen_eda941ca57507528(page, target_model):
    case_data = CASE_DATA
    workspace_page_page = WorkspacePage(page)
    bot_settings_page_page = BotSettingsPage(page)
    publish_dialog_page = PublishDialogPage(page)
    workspace_page_page.open()
    expect(page).to_have_url(re.compile(re.escape(str("/workspace"))))
    expect(workspace_page_page.agent_card).to_be_visible()
    workspace_page_page.agent_name_link.click()
    bot_settings_page_page.model_selector.click()
    bot_settings_page_page.visible_text(str(target_model)).click()
    bot_settings_page_page.history_sessions_btn.click()
    bot_settings_page_page.new_session_btn.click()
    bot_settings_page_page.history_sessions_btn.click()
    bot_settings_page_page.chat_input.fill(str("hi"))
    _response_before_9 = _last_locator_text(bot_settings_page_page.last_response)
    bot_settings_page_page.send_btn.click()
    _wait_for_response(bot_settings_page_page.last_response, _response_before_9)
    expect(bot_settings_page_page.last_response).to_be_visible()
    bot_settings_page_page.chat_input.fill(str("flow1"))
    _response_before_12 = _last_locator_text(bot_settings_page_page.last_response)
    bot_settings_page_page.send_btn.click()
    _wait_for_response(bot_settings_page_page.last_response, _response_before_12)
    expect(bot_settings_page_page.flow_exit_status).to_contain_text(str("flow_exit"))
    bot_settings_page_page.publish_btn.click()
    _commit_current_value(publish_dialog_page.version_input)
    publish_dialog_page.log_input.fill(str("自动化测试发布"))
    publish_dialog_page.publish_confirm_btn.click()
    expect(publish_dialog_page.confirm_dialog_text).to_be_visible()
    publish_dialog_page.confirm_btn.click()
    publish_dialog_page.publishing_status.wait_for(state="visible")
    workspace_page_page.open()
    expect(workspace_page_page.status_published).to_be_visible()
    workspace_page_page.use_button.click()
    bot_settings_page_page.published_history_sessions_btn.click()
    bot_settings_page_page.new_session_btn.click()
    bot_settings_page_page.published_history_sessions_btn.click()
    bot_settings_page_page.chat_input.fill(str("hi"))
    _response_before_26 = _last_locator_text(bot_settings_page_page.last_response)
    bot_settings_page_page.send_btn.click()
    _wait_for_response(bot_settings_page_page.last_response, _response_before_26)
    bot_settings_page_page.chat_input.fill(str("flow1"))
    _response_before_29 = _last_locator_text(bot_settings_page_page.last_response)
    bot_settings_page_page.send_btn.click()
    _wait_for_response(bot_settings_page_page.last_response, _response_before_29)
    expect(bot_settings_page_page.flow_exit_status).to_contain_text(str("flow_exit"))
