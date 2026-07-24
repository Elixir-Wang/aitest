from __future__ import annotations

from pages.base_page import BasePage


class BotSettingsPage(BasePage):
    route = ""

    # <ui-element chat_input>
    @property
    def chat_input(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-7
        return self.page.locator("textarea")
    # </ui-element>
    # <ui-element history_sessions_btn>
    @property
    def history_sessions_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-5
        return self.page.get_by_role("button", name="历史会话")
    # </ui-element>
    # <ui-element last_response>
    @property
    def last_response(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-8
        return self.page.locator("[class*='message']:last-of-type")
    # </ui-element>
    # <ui-element model_selector>
    @property
    def model_selector(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-3
        return self.page.get_by_text("对话模型")
    # </ui-element>
    # <ui-element new_session_btn>
    @property
    def new_session_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-6
        return self.page.get_by_role("button", name="新建会话")
    # </ui-element>
    # <ui-element publish_btn>
    @property
    def publish_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-13
        return self.page.get_by_text("发布")
    # </ui-element>
    # <ui-element send_btn>
    @property
    def send_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-7
        return self.page.get_by_role("button", name="发送")
    # </ui-element>
