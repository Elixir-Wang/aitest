from __future__ import annotations

from urllib.parse import urljoin

from playwright.sync_api import Locator, Page, expect

from config.settings import BASE_URL


class BasePage:
    route = ""

    def __init__(self, page: Page):
        self.page = page

    def open(self) -> None:
        if not BASE_URL:
            raise RuntimeError("UI_BASE_URL 未配置。")
        self.page.goto(urljoin(f"{BASE_URL}/", f"/{self.route.lstrip('/')}"))

    def visible_text(self, text: str) -> Locator:
        return self.page.get_by_text(text, exact=True).first

    def click_first_visible(self, *locators: Locator) -> None:
        for locator in locators:
            try:
                locator.first.wait_for(state="visible", timeout=3_000)
                locator.first.click()
                return
            except Exception:
                continue
        raise AssertionError("No candidate locator was visible and clickable")

    def expect_text(self, text: str) -> None:
        expect(self.visible_text(text)).to_be_visible()
