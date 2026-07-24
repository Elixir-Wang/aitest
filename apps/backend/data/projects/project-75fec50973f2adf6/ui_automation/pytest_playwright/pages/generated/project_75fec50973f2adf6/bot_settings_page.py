from __future__ import annotations

from pages.base_page import BasePage


class BotSettingsPage(BasePage):
    route = ""

    # <ui-element chat_input>
    @property
    def chat_input(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-7, uirun-manual-qwen-plus-response-fix-2/failure-screenshot#chat-placeholder
        return self.page.get_by_placeholder("请输入问题，按Shift+Enter换行", exact=True)
    # </ui-element>
    # <ui-element flow_exit_status>
    @property
    def flow_exit_status(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-10, uirun-manual-qwen-plus-response-fix-16/failure-screenshot#flow_exit-status-node
        return self.page.get_by_text("flow_exit", exact=True)
    # </ui-element>
    # <ui-element history_sessions_btn>
    @property
    def history_sessions_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-5, uirun-manual-qwen-plus-response-fix-3/trace.zip#.chat-head-svg-icon-history
        return self.page.locator(".right-pane .chat-head .radius-right")
    # </ui-element>
    # <ui-element last_response>
    @property
    def last_response(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-8, uirun-227ca1e659cbf551/trace.zip#bot-chart-content-item-left, uirun-manual-qwen-plus-response-fix-7/failure-screenshot#flow-exit-after-assistant
        return self.page.locator("xpath=(//*[contains(concat(' ', normalize-space(@class), ' '), ' bot-chart-content-item-left ')]//*[contains(concat(' ', normalize-space(@class), ' '), ' bot-chart-content-content ')])[last()]")
    # </ui-element>
    # <ui-element model_selector>
    @property
    def model_selector(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-3, uirun-manual-qwen-plus-response-fix-2/trace.zip#.model-setting-.select
        return self.page.locator(".model-setting .select")
    # </ui-element>
    # <ui-element new_session_btn>
    @property
    def new_session_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-6, uirun-manual-qwen-plus-response-fix-3/trace.zip#svg-icon-chat-new-line, uirun-manual-qwen-plus-response-fix-5/trace.zip#.new-conversation-btn
        return self.page.locator(".conversation-list .new-conversation-btn")
    # </ui-element>
    # <ui-element publish_btn>
    @property
    def publish_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-13, uirun-manual-qwen-plus-response-fix-8/stdout#unique-publish-button
        return self.page.get_by_role("button", name="发布")
    # </ui-element>
    # <ui-element published_history_sessions_btn>
    @property
    def published_history_sessions_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-20, uirun-manual-qwen-plus-response-fix-15/trace.zip#.teleport-to-agent-header-.avatar-info-wrap-.radius-right
        return self.page.locator(".teleport-to-agent-header .avatar-info-wrap .radius-right")
    # </ui-element>
    # <ui-element send_btn>
    @property
    def send_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-7, uirun-manual-qwen-plus-response-fix-3/trace.zip#.sent-btn
        return self.page.locator(".chat-bottom-tools .sent-btn[role='button']")
    # </ui-element>
