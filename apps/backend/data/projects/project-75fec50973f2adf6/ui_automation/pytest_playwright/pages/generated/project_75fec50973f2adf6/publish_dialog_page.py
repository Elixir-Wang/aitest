from __future__ import annotations

from pages.base_page import BasePage


class PublishDialogPage(BasePage):
    route = ""

    # <ui-element confirm_btn>
    @property
    def confirm_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-17
        return self.page.get_by_role("button", name="确认")
    # </ui-element>
    # <ui-element confirm_dialog_text>
    @property
    def confirm_dialog_text(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-16
        return self.page.get_by_text("确认要发布吗？")
    # </ui-element>
    # <ui-element log_input>
    @property
    def log_input(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-15
        return self.page.locator("textarea")
    # </ui-element>
    # <ui-element publish_confirm_btn>
    @property
    def publish_confirm_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-16
        return self.page.get_by_role("button", name="发布")
    # </ui-element>
    # <ui-element publishing_status>
    @property
    def publishing_status(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-17
        return self.page.get_by_text("正在发布版本")
    # </ui-element>
    # <ui-element version_input>
    @property
    def version_input(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-14
        return self.page.locator("input")
    # </ui-element>
