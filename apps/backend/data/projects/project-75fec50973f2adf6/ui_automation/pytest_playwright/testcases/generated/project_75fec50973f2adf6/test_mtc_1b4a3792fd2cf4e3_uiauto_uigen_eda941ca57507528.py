import time

import re

from pathlib import Path

import pytest
from playwright.sync_api import expect

from utils.data_loader import load_case_data
from pages.generated.project_75fec50973f2adf6.bot_settings_page import BotSettingsPage
from pages.generated.project_75fec50973f2adf6.publish_dialog_page import PublishDialogPage
from pages.generated.project_75fec50973f2adf6.workspace_page import WorkspacePage


UI_AUTOMATION_INSTRUMENTATION_VERSION = 3
UI_CASE_STEP_DEFINITIONS = [{'step_id': 'step-1', 'title': '点击"工作台"入口，进入工作台页面。', 'visible': True, 'operation_ids': ['step-1']}, {'step_id': 'step-2', 'title': '在工作台列表中找到"标准智能体测试"，点击该智能体的名称。', 'visible': True, 'operation_ids': ['step-2']}, {'step_id': 'step-3', 'title': '点击"对话模型"下拉框，弹出模型选项列表。', 'visible': True, 'operation_ids': ['step-3']}, {'step_id': 'step-4', 'title': '在下拉框中选择目标对话模型 ${target_model}（参数化）。', 'visible': True, 'operation_ids': ['step-4']}, {'step_id': 'step-5', 'title': '点击页面中的"历史会话"按钮。', 'visible': True, 'operation_ids': ['step-5']}, {'step_id': 'step-6', 'title': '在历史会话区域点击"新建会话"。', 'visible': True, 'operation_ids': ['step-6', 'step-6-close-history']}, {'step_id': 'step-7', 'title': '在问题输入框中输入"hi"，点击发送按钮。', 'visible': True, 'operation_ids': ['step-7', 'step-7-send']}, {'step_id': 'step-8', 'title': '等待"hi"的回复完全结束（回复流不再更新，无加载中状态）。', 'visible': True, 'operation_ids': ['step-8']}, {'step_id': 'step-9', 'title': '在输入框输入"flow1"，点击发送按钮。', 'visible': True, 'operation_ids': ['step-9', 'step-9-send']}, {'step_id': 'step-10', 'title': '等待"flow1"的回复完全结束。', 'visible': True, 'operation_ids': ['step-10']}, {'step_id': 'step-13', 'title': '点击智能体配置页面顶部的"发布"按钮。', 'visible': True, 'operation_ids': ['step-13']}, {'step_id': 'step-14', 'title': '在发布版本号输入框中输入"1.0.0"。', 'visible': True, 'operation_ids': ['step-14']}, {'step_id': 'step-15', 'title': '在发布日志输入框中输入"自动化测试发布"。', 'visible': True, 'operation_ids': ['step-15']}, {'step_id': 'step-16', 'title': '点击发布窗口中的"发布"按钮。', 'visible': True, 'operation_ids': ['step-16']}, {'step_id': 'step-17', 'title': '在发布确认窗口中点击"确认"按钮。', 'visible': True, 'operation_ids': ['step-17']}, {'step_id': 'step-18', 'title': '等待发布流程完成，页面自动返回工作台。', 'visible': True, 'operation_ids': ['step-18']}, {'step_id': 'step-19', 'title': '在工作台列表中找到"标准智能体测试"，点击其"使用"按钮。', 'visible': True, 'operation_ids': ['step-19', 'step-19-use']}, {'step_id': 'step-20', 'title': '点击"历史会话"按钮，再点击"新建会话"。', 'visible': True, 'operation_ids': ['step-20-history', 'step-20', 'step-20-close-history']}, {'step_id': 'step-21', 'title': '在输入框输入"hi"，点击发送按钮。', 'visible': True, 'operation_ids': ['step-21', 'step-21-send']}, {'step_id': 'step-22', 'title': '等待"hi"的回复完全结束。', 'visible': True, 'operation_ids': ['step-22']}, {'step_id': 'step-23', 'title': '在输入框输入"flow1"，点击发送按钮。', 'visible': True, 'operation_ids': ['step-23', 'step-23-send']}, {'step_id': 'step-24', 'title': '等待"flow1"的回复完全结束。', 'visible': True, 'operation_ids': ['step-24']}]


def _last_locator_text(locator):
    try:
        if locator.count() == 0:
            return ""
        return (locator.last.text_content(timeout=250) or "").strip()
    except Exception:
        return ""


def _wait_for_response(locator, previous_text, timeout_ms=30_000, stable_ms=2_000):
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
    with ui_case.step("step-1", "点击\"工作台\"入口，进入工作台页面。", operation_ids=["step-1"], visible=True):
        workspace_page_page.open()
        expect(page).to_have_url(re.compile(re.escape(str("/workspace"))))
        expect(workspace_page_page.agent_card).to_be_visible()
    with ui_case.step("step-2", "在工作台列表中找到\"标准智能体测试\"，点击该智能体的名称。", operation_ids=["step-2"], visible=True):
        workspace_page_page.agent_name_link.click()
    with ui_case.step("step-3", "点击\"对话模型\"下拉框，弹出模型选项列表。", operation_ids=["step-3"], visible=True):
        bot_settings_page_page.model_selector.click()
    with ui_case.step("step-4", "在下拉框中选择目标对话模型 ${target_model}（参数化）。", operation_ids=["step-4"], visible=True):
        bot_settings_page_page.visible_text(str(target_model)).click()
    with ui_case.step("step-5", "点击页面中的\"历史会话\"按钮。", operation_ids=["step-5"], visible=True):
        bot_settings_page_page.history_sessions_btn.click()
    with ui_case.step("step-6", "在历史会话区域点击\"新建会话\"。", operation_ids=["step-6", "step-6-close-history"], visible=True):
        bot_settings_page_page.new_session_btn.click()
        bot_settings_page_page.history_sessions_btn.click()
    with ui_case.step("step-7", "在问题输入框中输入\"hi\"，点击发送按钮。", operation_ids=["step-7", "step-7-send"], visible=True):
        bot_settings_page_page.chat_input.fill(str("hi"))
        _response_before_9 = _last_locator_text(bot_settings_page_page.last_response)
        bot_settings_page_page.send_btn.click()
    with ui_case.step("step-8", "等待\"hi\"的回复完全结束（回复流不再更新，无加载中状态）。", operation_ids=["step-8"], visible=True):
        _wait_for_response(bot_settings_page_page.last_response, _response_before_9)
        expect(bot_settings_page_page.last_response).to_be_visible()
    with ui_case.step("step-9", "在输入框输入\"flow1\"，点击发送按钮。", operation_ids=["step-9", "step-9-send"], visible=True):
        bot_settings_page_page.chat_input.fill(str("flow1"))
        _response_before_12 = _last_locator_text(bot_settings_page_page.last_response)
        bot_settings_page_page.send_btn.click()
    with ui_case.step("step-10", "等待\"flow1\"的回复完全结束。", operation_ids=["step-10"], visible=True):
        _wait_for_response(bot_settings_page_page.last_response, _response_before_12)
        expect(bot_settings_page_page.flow_exit_status).to_contain_text(str("flow_exit"))
    with ui_case.step("step-13", "点击智能体配置页面顶部的\"发布\"按钮。", operation_ids=["step-13"], visible=True):
        bot_settings_page_page.publish_btn.click()
    with ui_case.step("step-14", "在发布版本号输入框中输入\"1.0.0\"。", operation_ids=["step-14"], visible=True):
        _commit_current_value(publish_dialog_page.version_input)
    with ui_case.step("step-15", "在发布日志输入框中输入\"自动化测试发布\"。", operation_ids=["step-15"], visible=True):
        publish_dialog_page.log_input.fill(str("自动化测试发布"))
    with ui_case.step("step-16", "点击发布窗口中的\"发布\"按钮。", operation_ids=["step-16"], visible=True):
        publish_dialog_page.publish_confirm_btn.click()
        expect(publish_dialog_page.confirm_dialog_text).to_be_visible()
    with ui_case.step("step-17", "在发布确认窗口中点击\"确认\"按钮。", operation_ids=["step-17"], visible=True):
        publish_dialog_page.confirm_btn.click()
    with ui_case.step("step-18", "等待发布流程完成，页面自动返回工作台。", operation_ids=["step-18"], visible=True):
        publish_dialog_page.publishing_status.wait_for(state="visible")
    with ui_case.step("step-19", "在工作台列表中找到\"标准智能体测试\"，点击其\"使用\"按钮。", operation_ids=["step-19", "step-19-use"], visible=True):
        workspace_page_page.open()
        expect(workspace_page_page.status_published).to_be_visible()
        workspace_page_page.use_button.click()
    with ui_case.step("step-20", "点击\"历史会话\"按钮，再点击\"新建会话\"。", operation_ids=["step-20-history", "step-20", "step-20-close-history"], visible=True):
        bot_settings_page_page.published_history_sessions_btn.click()
        bot_settings_page_page.new_session_btn.click()
        bot_settings_page_page.published_history_sessions_btn.click()
    with ui_case.step("step-21", "在输入框输入\"hi\"，点击发送按钮。", operation_ids=["step-21", "step-21-send"], visible=True):
        bot_settings_page_page.chat_input.fill(str("hi"))
        _response_before_26 = _last_locator_text(bot_settings_page_page.last_response)
        bot_settings_page_page.send_btn.click()
    with ui_case.step("step-22", "等待\"hi\"的回复完全结束。", operation_ids=["step-22"], visible=True):
        _wait_for_response(bot_settings_page_page.last_response, _response_before_26)
    with ui_case.step("step-23", "在输入框输入\"flow1\"，点击发送按钮。", operation_ids=["step-23", "step-23-send"], visible=True):
        bot_settings_page_page.chat_input.fill(str("flow1"))
        _response_before_29 = _last_locator_text(bot_settings_page_page.last_response)
        bot_settings_page_page.send_btn.click()
    with ui_case.step("step-24", "等待\"flow1\"的回复完全结束。", operation_ids=["step-24"], visible=True):
        _wait_for_response(bot_settings_page_page.last_response, _response_before_29)
        expect(bot_settings_page_page.flow_exit_status).to_contain_text(str("flow_exit"))
