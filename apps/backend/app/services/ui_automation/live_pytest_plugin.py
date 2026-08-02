from __future__ import annotations

import os
import json
import secrets
import signal
import threading
import time
import traceback
from contextlib import contextmanager
from pathlib import Path

import pytest

from .execution_events import safe_parameters, write_event


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


def pytest_collection_finish(session) -> None:
    for index, item in enumerate(session.items):
        iteration_id = f"iteration-{index + 1:04d}"
        item._ui_iteration_id = iteration_id
        params = dict(getattr(getattr(item, "callspec", None), "params", {}) or {})
        allowed_parameters = _business_parameter_names()
        if allowed_parameters is not None:
            params = {key: value for key, value in params.items() if key in allowed_parameters}
        params = safe_parameters(params)
        write_event(
            "iteration_collected",
            iteration_id=iteration_id,
            pytest_node_id=item.nodeid,
            index=index,
            parameters=params,
            attempt=1,
        )


def pytest_runtest_setup(item) -> None:
    item._ui_started_monotonic = time.monotonic()
    item._ui_reports = {}
    item._ui_finished = False
    item._ui_step_started = False
    item._ui_call_error = None
    write_event(
        "iteration_started",
        iteration_id=_iteration_id(item),
        pytest_node_id=item.nodeid,
    )


@pytest.fixture
def ui_case(request, page):
    return UiCaseRecorder(request.node, page)


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


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    reports = getattr(item, "_ui_reports", {})
    reports[report.when] = report
    item._ui_reports = reports
    if report.when == "setup" and report.failed:
        _finish_iteration(item, "infrastructure_error", error=_call_error(call))
        return
    if report.when == "call" and report.failed:
        item._ui_call_error = _call_error(call)
    if report.when != "teardown":
        return
    setup_report = reports.get("setup")
    call_report = reports.get("call")
    teardown_report = reports.get("teardown")
    status = _iteration_status(item, setup_report, call_report, teardown_report)
    error = getattr(item, "_ui_call_error", None)
    if teardown_report and teardown_report.failed and error is None:
        error = _call_error(call)
    _finish_iteration(item, status, error=error)


class UiCaseRecorder:
    def __init__(self, item, page) -> None:
        self.item = item
        self.page = page

    def define_steps(self, steps: list[dict]) -> None:
        write_event(
            "steps_defined",
            iteration_id=_iteration_id(self.item),
            pytest_node_id=self.item.nodeid,
            steps=steps,
        )

    @contextmanager
    def step(
        self,
        step_id: str,
        title: str,
        *,
        operation_ids: list[str] | None = None,
        visible: bool = True,
    ):
        self.item._ui_step_started = True
        started = time.monotonic()
        common = {
            "iteration_id": _iteration_id(self.item),
            "pytest_node_id": self.item.nodeid,
            "step_id": step_id,
            "title": title,
            "operation_ids": list(operation_ids or []),
            "visible": visible,
        }
        write_event("step_started", **common)
        try:
            yield
        except BaseException as exc:
            artifacts = self._capture_failure(step_id)
            write_event(
                "step_finished",
                **common,
                status="failed",
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                },
                artifacts=artifacts,
            )
            raise
        else:
            write_event(
                "step_finished",
                **common,
                status="passed",
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                error=None,
                artifacts=[],
            )

    def _capture_failure(self, step_id: str) -> list[dict]:
        artifact_root = os.getenv("UI_RUN_ARTIFACT_DIR", "").strip()
        run_dir = os.getenv("UI_RUN_DIR", "").strip()
        if not artifact_root or not run_dir:
            return []
        artifact_id = f"artifact-{secrets.token_hex(8)}"
        target = Path(artifact_root) / _iteration_id(self.item) / f"{artifact_id}.png"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(target), full_page=True)
            relative_path = target.resolve().relative_to(Path(run_dir).resolve()).as_posix()
            return [
                {
                    "artifact_id": artifact_id,
                    "kind": "screenshot",
                    "mime_type": "image/png",
                    "relative_path": relative_path,
                    "step_id": step_id,
                }
            ]
        except Exception:
            return []


def _iteration_id(item) -> str:
    return str(getattr(item, "_ui_iteration_id", "iteration-0001"))


def _business_parameter_names() -> set[str] | None:
    value = os.getenv("UI_BUSINESS_PARAMETERS", "").strip()
    if not value:
        return None
    try:
        payload = json.loads(value)
    except ValueError:
        return None
    return {str(item) for item in payload} if isinstance(payload, list) else None


def _finish_iteration(item, status: str, *, error: dict | None = None) -> None:
    if getattr(item, "_ui_finished", False):
        return
    item._ui_finished = True
    started = float(getattr(item, "_ui_started_monotonic", time.monotonic()))
    write_event(
        "iteration_finished",
        iteration_id=_iteration_id(item),
        pytest_node_id=item.nodeid,
        status=status,
        duration_ms=round((time.monotonic() - started) * 1000, 3),
        error=error,
    )


def _call_error(call) -> dict | None:
    excinfo = getattr(call, "excinfo", None)
    if excinfo is None:
        return None
    exc = excinfo.value
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    }


def _iteration_status(item, setup_report, call_report, teardown_report) -> str:
    if setup_report and setup_report.failed:
        return "infrastructure_error"
    if call_report and call_report.failed:
        return "failed" if getattr(item, "_ui_step_started", False) else "infrastructure_error"
    if teardown_report and teardown_report.failed:
        return "infrastructure_error"
    if call_report and call_report.skipped:
        return "skipped"
    return "passed"


__all__ = ["UiCaseRecorder", "pytest_configure", "pytest_fixture_setup"]
