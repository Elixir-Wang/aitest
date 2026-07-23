from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    base_url = os.getenv("UI_BASE_URL", "").rstrip("/")
    target = os.getenv("UI_AUTH_STATE_PATH", "").strip()
    if not base_url or not target:
        raise SystemExit("UI_BASE_URL 和 UI_AUTH_STATE_PATH 必须配置。")
    output = Path(target)
    output.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True, locale=os.getenv("UI_LOCALE", "zh-CN"))
        page = context.new_page()
        page.goto(base_url)
        page.wait_for_url(lambda url: "/login" not in str(url), timeout=10 * 60 * 1000)
        context.storage_state(path=str(output))
        browser.close()
    print(f"Saved auth state to {output}")


if __name__ == "__main__":
    main()
