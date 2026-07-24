from pathlib import Path

import pytest
from playwright.sync_api import expect

from utils.data_loader import load_case_data
from pages.generated.project_75fec50973f2adf6.bot_settings_page import BotSettingsPage
from pages.generated.project_75fec50973f2adf6.publish_dialog_page import PublishDialogPage
from pages.generated.project_75fec50973f2adf6.workspace_page import WorkspacePage


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
    workspace_page_page.agent_name_link.click()
    bot_settings_page_page.model_selector.click()
    bot_settings_page_page.visible_text(str(target_model)).click()
    bot_settings_page_page.history_sessions_btn.click()
    bot_settings_page_page.new_session_btn.click()
    bot_settings_page_page.chat_input.fill(str("hi"))
    bot_settings_page_page.send_btn.click()
    bot_settings_page_page.last_response.wait_for(state="visible")
    bot_settings_page_page.chat_input.fill(str("flow1"))
    bot_settings_page_page.send_btn.click()
    bot_settings_page_page.last_response.wait_for(state="visible")
    bot_settings_page_page.chat_input.fill(str("北京今日天气"))
    bot_settings_page_page.send_btn.click()
    bot_settings_page_page.last_response.wait_for(state="visible")
    bot_settings_page_page.publish_btn.click()
    publish_dialog_page.version_input.fill(str("1.0.0"))
    publish_dialog_page.log_input.fill(str("自动化测试发布"))
    publish_dialog_page.publish_confirm_btn.click()
    publish_dialog_page.confirm_btn.click()
    publish_dialog_page.publishing_status.wait_for(state="visible")
    workspace_page_page.open()
    workspace_page_page.use_button.click()
    bot_settings_page_page.new_session_btn.click()
    bot_settings_page_page.chat_input.fill(str("hi"))
    bot_settings_page_page.send_btn.click()
    bot_settings_page_page.last_response.wait_for(state="visible")
    bot_settings_page_page.chat_input.fill(str("flow1"))
    bot_settings_page_page.send_btn.click()
    bot_settings_page_page.last_response.wait_for(state="visible")
    bot_settings_page_page.chat_input.fill(str("北京今日天气"))
    bot_settings_page_page.send_btn.click()
    bot_settings_page_page.last_response.wait_for(state="visible")
    expect(page).to_have_url(str("/workspace"))
    expect(workspace_page_page.agent_card).to_be_visible()
    expect(bot_settings_page_page.last_response).to_have_text(str("flow_exit"))
    expect(bot_settings_page_page.last_response).to_have_text(str("flow_exit"))
    expect(bot_settings_page_page.last_response).to_have_text(str("调用完成"))
    expect(publish_dialog_page.confirm_dialog_text).to_be_visible()
    expect(workspace_page_page.status_published).to_be_visible()
    expect(bot_settings_page_page.last_response).to_have_text(str("flow_exit"))
    expect(bot_settings_page_page.last_response).to_have_text(str("调用完成"))
