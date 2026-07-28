import json

from playwright.sync_api import sync_playwright


URL = "http://127.0.0.1:3000/office-preview"
SCREENSHOT = "/Users/wanghongbao/project/test_project/output/silicon-office-unified-browser.png"


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    console_errors = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.goto(URL, wait_until="networkidle", timeout=120_000)
    page.locator('article:has(h2:text-is("需求工程组"))').wait_for(state="visible", timeout=30_000)
    page.screenshot(path=SCREENSHOT, full_page=True)

    rooms = page.locator('article:has([class*="roomScene"])')
    room_results = []
    for index in range(rooms.count()):
        room = rooms.nth(index)
        scene = room.locator('[class*="roomScene"]').first
        image = scene.locator("img").first
        heading = room.locator("h2").first.inner_text()
        room_results.append(
            {
                "name": heading,
                "scene": scene.bounding_box(),
                "image": image.evaluate(
                    "element => ({naturalWidth: element.naturalWidth, naturalHeight: element.naturalHeight})"
                ),
                "labels": [
                    scene.locator('[class*="nameplate"]').nth(label_index).bounding_box()
                    for label_index in range(scene.locator('[class*="nameplate"]').count())
                ],
            }
        )

    print(json.dumps({"rooms": room_results, "consoleErrors": console_errors, "screenshot": SCREENSHOT}, ensure_ascii=False))
    browser.close()
