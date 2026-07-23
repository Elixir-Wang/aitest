from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    args = dict(browser_context_args)
    args["ignore_https_errors"] = True
    args["locale"] = os.getenv("UI_LOCALE", "zh-CN")
    storage_state = os.getenv("UI_STORAGE_STATE", "").strip()
    if storage_state:
        args["storage_state"] = storage_state
    return args


@pytest.fixture(autouse=True)
def configure_page(page):
    timeout = int(os.getenv("UI_TIMEOUT_MS", "30000"))
    page.set_default_timeout(timeout)
    page.set_default_navigation_timeout(timeout)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed or "page" not in item.funcargs:
        return
    target_root = os.getenv("UI_ARTIFACT_DIR", "").strip()
    if not target_root:
        return
    try:
        target = Path(target_root) / "failure-screenshots" / f"{item.nodeid.replace('/', '_').replace(':', '_')}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        item.funcargs["page"].screenshot(path=str(target), full_page=True)
    except Exception:
        pass
