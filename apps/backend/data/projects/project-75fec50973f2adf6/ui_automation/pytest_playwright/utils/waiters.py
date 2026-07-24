from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, expect


BUSY_TEXT = re.compile(r"停止|生成中|思考中|响应中|加载中|发布中")


def wait_visible(locator: Locator, timeout: int | None = None) -> None:
    locator.wait_for(state="visible", timeout=timeout)


def wait_until_page_idle(page: Page, timeout: int = 120_000) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeoutError:
        pass


def wait_until_not_busy(page: Page, timeout: int = 30_000) -> None:
    try:
        expect(page.get_by_text(BUSY_TEXT).first).to_be_hidden(timeout=timeout)
    except AssertionError:
        pass


def wait_for_page_ready(page: Page, timeout: int = 120_000) -> None:
    wait_until_page_idle(page, timeout=timeout)
    wait_until_not_busy(page, timeout=min(timeout, 30_000))
