from pathlib import Path

from playwright.sync_api import sync_playwright
from playwright.sync_api import Error as PlaywrightError


PROJECT_ID = "project-75fec50973f2adf6"
DOCUMENT_ID = "doc-2afde57dff93959d"
BASE_URL = "http://127.0.0.1:3000"


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    console_errors = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)

    for attempt in range(20):
        try:
            page.goto(f"{BASE_URL}/auth/v1/login")
            break
        except PlaywrightError:
            if attempt == 19:
                raise
            page.wait_for_timeout(500)
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="登录", exact=True).click()
    page.wait_for_url("**/dashboard")

    page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/requirements/{DOCUMENT_ID}?tab=test-points")
    page.wait_for_load_state("networkidle")
    page.get_by_text("当前测试要点未生成完整").wait_for()

    summary = page.locator("details").filter(has_text="展开全部")
    assert summary.count() == 1
    assert page.get_by_text("展开全部", exact=False).is_visible()
    visible_items = page.locator("ul.space-y-1 > li:visible").count()
    assert visible_items == 5, visible_items

    screenshot_path = Path("/tmp/test-point-coverage-collapsed.png")
    page.screenshot(path=str(screenshot_path), full_page=True)
    summary.locator("summary").click()
    assert page.get_by_text("收起", exact=True).is_visible()
    expanded_items = page.locator("ul.space-y-1 > li:visible").count()
    assert expanded_items > 5, expanded_items

    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    assert not overflow
    assert not console_errors, console_errors
    print(
        {
            "visible_items": visible_items,
            "expanded_items": expanded_items,
            "overflow": overflow,
            "screenshot": str(screenshot_path),
        }
    )
    browser.close()
