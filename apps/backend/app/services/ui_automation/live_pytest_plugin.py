from __future__ import annotations

import os
import signal
import threading
import time

import pytest


def pytest_configure(config) -> None:
    parent_pid = _runner_parent_pid()
    if parent_pid is None:
        return
    threading.Thread(
        target=_watch_runner_parent,
        args=(parent_pid,),
        name="ui-runner-parent-watchdog",
        daemon=True,
    ).start()


def _runner_parent_pid() -> int | None:
    value = os.getenv("UI_RUNNER_PARENT_PID", "").strip()
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _watch_runner_parent(parent_pid: int) -> None:
    while _parent_is_alive(parent_pid):
        time.sleep(0.25)
    if os.name != "nt":
        os.killpg(os.getpgrp(), signal.SIGTERM)
    else:
        os._exit(1)


def _parent_is_alive(parent_pid: int) -> bool:
    if os.getppid() != parent_pid:
        return False
    try:
        os.kill(parent_pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_fixture_setup(fixturedef, request):
    outcome = yield
    if fixturedef.argname not in {"browser_context_args", "browser_type_launch_args"}:
        return
    args = outcome.get_result()
    if not isinstance(args, dict):
        return
    if fixturedef.argname == "browser_context_args":
        args["viewport"] = {
            "width": int(os.getenv("UI_VIEWPORT_WIDTH", "1440")),
            "height": int(os.getenv("UI_VIEWPORT_HEIGHT", "900")),
        }
        return
    if fixturedef.argname != "browser_type_launch_args":
        return
    cdp_port = os.getenv("UI_LIVE_CDP_PORT", "").strip()
    if not cdp_port:
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


__all__ = ["pytest_configure", "pytest_fixture_setup"]
