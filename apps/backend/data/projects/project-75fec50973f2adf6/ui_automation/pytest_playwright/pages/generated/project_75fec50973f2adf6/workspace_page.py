from __future__ import annotations

from pages.base_page import BasePage


class WorkspacePage(BasePage):
    route = "/workspace"

    # <ui-element agent_card>
    @property
    def agent_card(self):
        # evidence: page-workspace__root__001
        return self.page.get_by_text("标准智能体测试")
    # </ui-element>
    # <ui-element agent_name_link>
    @property
    def agent_name_link(self):
        # evidence: page-workspace__root__001
        return self.page.get_by_text("标准智能体测试")
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
        # evidence: page-workspace__root__001
        return self.page.get_by_text("已发布")
    # </ui-element>
    # <ui-element use_button>
    @property
    def use_button(self):
        # evidence: page-workspace__root__001
        return self.page.get_by_role("button", name="使用")
    # </ui-element>
