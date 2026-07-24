from __future__ import annotations

from pages.base_page import BasePage


class WorkspacePage(BasePage):
    route = "/workspace"

    # <ui-element agent_card>
    @property
    def agent_card(self):
        # evidence: page-workspace__root__001
        return self.page.get_by_text("标准智能体测试", exact=True)
    # </ui-element>
    # <ui-element agent_name_link>
    @property
    def agent_name_link(self):
        # evidence: page-workspace__root__001
        return self.page.get_by_text("标准智能体测试", exact=True)
    # </ui-element>
    # <ui-element create_button>
    @property
    def create_button(self):
        # evidence: page-workspace__root__001
        return self.page.get_by_role("button", name="创建")
    # </ui-element>
    # <ui-element status_published>
    @property
    def status_published(self):
        # evidence: page-workspace__root__001, uirun-manual-qwen-plus-no-plugin-19/failure-screenshot#standard-agent-published-status
        return self.page.locator("xpath=//*[contains(concat(' ', normalize-space(@class), ' '), ' agent-item-card ')][.//*[normalize-space()='标准智能体测试']]//span[normalize-space()='已发布']")
    # </ui-element>
    # <ui-element use_button>
    @property
    def use_button(self):
        # evidence: page-workspace__root__001, uirun-manual-qwen-plus-response-fix-12/trace.zip#agent-card-use-span
        return self.page.locator("xpath=//*[contains(concat(' ', normalize-space(@class), ' '), ' agent-item-card ')][.//*[normalize-space()='标准智能体测试']]//*[normalize-space()='使用']")
    # </ui-element>
