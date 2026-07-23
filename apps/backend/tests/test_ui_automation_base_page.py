from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_generated_base_page_resolves_routes_from_environment_path(monkeypatch):
    monkeypatch.setenv("UI_BASE_URL", "https://www.cybotstar.cn/agentStore")
    suite_root = Path(__file__).parents[1] / "data/ui_automation/pytest_playwright"
    sys.path.insert(0, str(suite_root))

    settings = importlib.import_module("config.settings")
    importlib.reload(settings)
    base_page_module = importlib.import_module("pages.base_page")
    base_page_module = importlib.reload(base_page_module)

    class Page:
        def __init__(self):
            self.url = None

        def goto(self, url):
            self.url = url

    page = Page()
    base_page = base_page_module.BasePage(page)
    base_page.route = "/workspace"
    base_page.open()

    assert page.url == "https://www.cybotstar.cn/workspace"
