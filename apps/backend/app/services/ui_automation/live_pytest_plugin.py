from __future__ import annotations

import os

import pytest


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_fixture_setup(fixturedef, request):
    outcome = yield
    if fixturedef.argname != "browser_type_launch_args":
        return
    args = outcome.get_result()
    cdp_port = os.getenv("UI_LIVE_CDP_PORT", "").strip()
    if not cdp_port or not isinstance(args, dict):
        return
    chromium_args = list(args.get("args", []))
    chromium_args.extend(
        [
            "--remote-debugging-address=127.0.0.1",
            f"--remote-debugging-port={cdp_port}",
            "--remote-allow-origins=*",
        ]
    )
    args["args"] = chromium_args


__all__ = ["pytest_fixture_setup"]
