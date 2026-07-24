from __future__ import annotations

from pages.base_page import BasePage


class PublishDialogPage(BasePage):
    route = ""

    # <ui-element confirm_btn>
    @property
    def confirm_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-17, uirun-manual-qwen-plus-response-fix-13/trace.zip#visible-confirm-dialog-button
        return self.page.locator(".confirm-dialog.uui-modal-root button.uui-btn-primary:visible")
    # </ui-element>
    # <ui-element confirm_dialog_text>
    @property
    def confirm_dialog_text(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-16
        return self.page.get_by_text("确认要发布吗？", exact=True)
    # </ui-element>
    # <ui-element log_input>
    @property
    def log_input(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-15, agentRelease-live-dom#release-log-placeholder
        return self.page.get_by_placeholder("请填写发布日志", exact=True)
    # </ui-element>
    # <ui-element publish_confirm_btn>
    @property
    def publish_confirm_btn(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-16, agentRelease-live-dom#unique-publish-span
        return self.page.get_by_text("发布", exact=True)
    # </ui-element>
    # <ui-element publishing_status>
    @property
    def publishing_status(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-17, uirun-manual-qwen-plus-response-fix-11/failure-screenshot#published-success
        return self.page.get_by_text("已成功发布", exact=True)
    # </ui-element>
    # <ui-element version_input>
    @property
    def version_input(self):
        # evidence: mtc-1b4a3792fd2cf4e3-step-14, agentRelease-live-dom#version-placeholder
        return self.page.get_by_placeholder("支持自定义版本号；若为 X.Y.Z 格式，最大 99.9.9", exact=True)
    # </ui-element>
