import time

import re

from pathlib import Path

import pytest
from playwright.sync_api import expect

from utils.data_loader import load_case_data
from pages.generated.project_75fec50973f2adf6.bot_settings_page import BotSettingsPage
from pages.generated.project_75fec50973f2adf6.publish_dialog_page import PublishDialogPage
from pages.generated.project_75fec50973f2adf6.workspace_page import WorkspacePage


UI_AUTOMATION_INSTRUMENTATION_VERSION = 2


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
def test_uiauto_uigen_eda941ca57507528(page, ui_case, target_model):
    case_data = CASE_DATA
    workspace_page_page = WorkspacePage(page)
    bot_settings_page_page = BotSettingsPage(page)
    publish_dialog_page = PublishDialogPage(page)
    ui_case.define_steps([{'step_id': 'step-1', 'title': 'step-1', 'visible': True, 'operation_ids': ['step-1']}, {'step_id': 'step-2', 'title': 'step-2', 'visible': True, 'operation_ids': ['step-2']}, {'step_id': 'step-3', 'title': 'step-3', 'visible': True, 'operation_ids': ['step-3']}, {'step_id': 'step-4', 'title': 'step-4', 'visible': True, 'operation_ids': ['step-4']}, {'step_id': 'step-5', 'title': 'step-5', 'visible': True, 'operation_ids': ['step-5']}, {'step_id': 'step-6', 'title': 'step-6', 'visible': True, 'operation_ids': ['step-6']}, {'step_id': 'step-6-close-history', 'title': 'step-6-close-history', 'visible': True, 'operation_ids': ['step-6-close-history']}, {'step_id': 'step-7', 'title': 'step-7', 'visible': True, 'operation_ids': ['step-7']}, {'step_id': 'step-7-send', 'title': 'step-7-send', 'visible': True, 'operation_ids': ['step-7-send']}, {'step_id': 'step-8', 'title': 'step-8', 'visible': True, 'operation_ids': ['step-8']}, {'step_id': 'step-9', 'title': 'step-9', 'visible': True, 'operation_ids': ['step-9']}, {'step_id': 'step-9-send', 'title': 'step-9-send', 'visible': True, 'operation_ids': ['step-9-send']}, {'step_id': 'step-10', 'title': 'step-10', 'visible': True, 'operation_ids': ['step-10']}, {'step_id': 'step-13', 'title': 'step-13', 'visible': True, 'operation_ids': ['step-13']}, {'step_id': 'step-14', 'title': 'step-14', 'visible': True, 'operation_ids': ['step-14']}, {'step_id': 'step-15', 'title': 'step-15', 'visible': True, 'operation_ids': ['step-15']}, {'step_id': 'step-16', 'title': 'step-16', 'visible': True, 'operation_ids': ['step-16']}, {'step_id': 'step-17', 'title': 'step-17', 'visible': True, 'operation_ids': ['step-17']}, {'step_id': 'step-18', 'title': 'step-18', 'visible': True, 'operation_ids': ['step-18']}, {'step_id': 'step-19', 'title': 'step-19', 'visible': True, 'operation_ids': ['step-19']}, {'step_id': 'step-19-use', 'title': 'step-19-use', 'visible': True, 'operation_ids': ['step-19-use']}, {'step_id': 'step-20-history', 'title': 'step-20-history', 'visible': True, 'operation_ids': ['step-20-history']}, {'step_id': 'step-20', 'title': 'step-20', 'visible': True, 'operation_ids': ['step-20']}, {'step_id': 'step-20-close-history', 'title': 'step-20-close-history', 'visible': True, 'operation_ids': ['step-20-close-history']}, {'step_id': 'step-21', 'title': 'step-21', 'visible': True, 'operation_ids': ['step-21']}, {'step_id': 'step-21-send', 'title': 'step-21-send', 'visible': True, 'operation_ids': ['step-21-send']}, {'step_id': 'step-22', 'title': 'step-22', 'visible': True, 'operation_ids': ['step-22']}, {'step_id': 'step-23', 'title': 'step-23', 'visible': True, 'operation_ids': ['step-23']}, {'step_id': 'step-23-send', 'title': 'step-23-send', 'visible': True, 'operation_ids': ['step-23-send']}, {'step_id': 'step-24', 'title': 'step-24', 'visible': True, 'operation_ids': ['step-24']}])
    with ui_case.step("step-1", "step-1", operation_ids=["step-1"], visible=True):
        workspace_page_page.open()
        expect(page).to_have_url(re.compile(re.escape(str("/workspace"))))
        expect(workspace_page_page.agent_card).to_be_visible()
    with ui_case.step("step-2", "step-2", operation_ids=["step-2"], visible=True):
        workspace_page_page.agent_name_link.click()
    with ui_case.step("step-3", "step-3", operation_ids=["step-3"], visible=True):
        bot_settings_page_page.model_selector.click()
    with ui_case.step("step-4", "step-4", operation_ids=["step-4"], visible=True):
        bot_settings_page_page.visible_text(str(target_model)).click()
    with ui_case.step("step-5", "step-5", operation_ids=["step-5"], visible=True):
        bot_settings_page_page.history_sessions_btn.click()
    with ui_case.step("step-6", "step-6", operation_ids=["step-6"], visible=True):
        bot_settings_page_page.new_session_btn.click()
    with ui_case.step("step-6-close-history", "step-6-close-history", operation_ids=["step-6-close-history"], visible=True):
        bot_settings_page_page.history_sessions_btn.click()
    with ui_case.step("step-7", "step-7", operation_ids=["step-7"], visible=True):
        bot_settings_page_page.chat_input.fill(str("hi"))
    with ui_case.step("step-7-send", "step-7-send", operation_ids=["step-7-send"], visible=True):
        _response_before_9 = _last_locator_text(bot_settings_page_page.last_response)
        bot_settings_page_page.send_btn.click()
    with ui_case.step("step-8", "step-8", operation_ids=["step-8"], visible=True):
        _wait_for_response(bot_settings_page_page.last_response, _response_before_9)
        expect(bot_settings_page_page.last_response).to_be_visible()
    with ui_case.step("step-9", "step-9", operation_ids=["step-9"], visible=True):
        bot_settings_page_page.chat_input.fill(str("flow1"))
    with ui_case.step("step-9-send", "step-9-send", operation_ids=["step-9-send"], visible=True):
        _response_before_12 = _last_locator_text(bot_settings_page_page.last_response)
        bot_settings_page_page.send_btn.click()
    with ui_case.step("step-10", "step-10", operation_ids=["step-10"], visible=True):
        _wait_for_response(bot_settings_page_page.last_response, _response_before_12)
        expect(bot_settings_page_page.flow_exit_status).to_contain_text(str("flow_exit"))
    with ui_case.step("step-13", "step-13", operation_ids=["step-13"], visible=True):
        bot_settings_page_page.publish_btn.click()
    with ui_case.step("step-14", "step-14", operation_ids=["step-14"], visible=True):
        _commit_current_value(publish_dialog_page.version_input)
    with ui_case.step("step-15", "step-15", operation_ids=["step-15"], visible=True):
        publish_dialog_page.log_input.fill(str("自动化测试发布"))
    with ui_case.step("step-16", "step-16", operation_ids=["step-16"], visible=True):
        publish_dialog_page.publish_confirm_btn.click()
        expect(publish_dialog_page.confirm_dialog_text).to_be_visible()
    with ui_case.step("step-17", "step-17", operation_ids=["step-17"], visible=True):
        publish_dialog_page.confirm_btn.click()
    with ui_case.step("step-18", "step-18", operation_ids=["step-18"], visible=True):
        publish_dialog_page.publishing_status.wait_for(state="visible")
    with ui_case.step("step-19", "step-19", operation_ids=["step-19"], visible=True):
        workspace_page_page.open()
        expect(workspace_page_page.status_published).to_be_visible()
    with ui_case.step("step-19-use", "step-19-use", operation_ids=["step-19-use"], visible=True):
        workspace_page_page.use_button.click()
    with ui_case.step("step-20-history", "step-20-history", operation_ids=["step-20-history"], visible=True):
        bot_settings_page_page.published_history_sessions_btn.click()
    with ui_case.step("step-20", "step-20", operation_ids=["step-20"], visible=True):
        bot_settings_page_page.new_session_btn.click()
    with ui_case.step("step-20-close-history", "step-20-close-history", operation_ids=["step-20-close-history"], visible=True):
        bot_settings_page_page.published_history_sessions_btn.click()
    with ui_case.step("step-21", "step-21", operation_ids=["step-21"], visible=True):
        bot_settings_page_page.chat_input.fill(str("hi"))
    with ui_case.step("step-21-send", "step-21-send", operation_ids=["step-21-send"], visible=True):
        _response_before_26 = _last_locator_text(bot_settings_page_page.last_response)
        bot_settings_page_page.send_btn.click()
    with ui_case.step("step-22", "step-22", operation_ids=["step-22"], visible=True):
        _wait_for_response(bot_settings_page_page.last_response, _response_before_26)
    with ui_case.step("step-23", "step-23", operation_ids=["step-23"], visible=True):
        bot_settings_page_page.chat_input.fill(str("flow1"))
    with ui_case.step("step-23-send", "step-23-send", operation_ids=["step-23-send"], visible=True):
        _response_before_29 = _last_locator_text(bot_settings_page_page.last_response)
        bot_settings_page_page.send_btn.click()
    with ui_case.step("step-24", "step-24", operation_ids=["step-24"], visible=True):
        _wait_for_response(bot_settings_page_page.last_response, _response_before_29)
        expect(bot_settings_page_page.flow_exit_status).to_contain_text(str("flow_exit"))
