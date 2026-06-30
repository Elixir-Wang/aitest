"""Long-lived Playwright browser session for page exploration."""

import json
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from app.core.settings import (
    PLAYWRIGHT_BROWSER_CHANNEL,
    PLAYWRIGHT_RUNNER_DIR,
)


class BrowserSessionError(RuntimeError):
    """Raised when the browser session process fails or returns an error."""


class PlaywrightBrowserSession:
    """Manage one Playwright page through a persistent Node child process."""

    def __init__(
        self,
        *,
        start_url: str,
        browser_channel: str | None = None,
        storage_state_path: Path | str | None = None,
    ) -> None:
        self.start_url = start_url
        self._closed = False
        self._command_index = 0
        self._process = subprocess.Popen(
            [
                "node",
                str(PLAYWRIGHT_RUNNER_DIR / "browser-session.mjs"),
                start_url,
                browser_channel or PLAYWRIGHT_BROWSER_CHANNEL,
                str(storage_state_path or ""),
            ],
            cwd=PLAYWRIGHT_RUNNER_DIR,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        started = self._read_message()
        if started.get("kind") == "session_failed":
            self.close()
            error_summary = started.get("error_summary") or started.get("error") or started
            raise BrowserSessionError(f"Browser session failed to start: {error_summary}")
        if started.get("kind") != "session_started" or started.get("status") not in {"started", "ok"}:
            self.close()
            raise BrowserSessionError(f"Browser session failed to start: {started}")

    def navigate(self, url: str) -> dict[str, Any]:
        """Navigate the active page, resolving relative URLs against the session start URL."""
        return self.command(
            {
                "type": "navigate",
                "url": resolve_navigation_url(url, self.start_url),
            }
        )

    def observe(self) -> dict[str, Any]:
        """Observe the current page without changing navigation state."""
        return self.command({"type": "observe"})

    def click(self, element_id: str) -> dict[str, Any]:
        """Click an element from the latest observation."""
        return self.command({"type": "click", "element_id": element_id})

    def fill(self, element_id: str, value: str) -> dict[str, Any]:
        """Fill an element from the latest observation."""
        return self.command({"type": "fill", "element_id": element_id, "value": value})

    def go_back(self) -> dict[str, Any]:
        """Navigate back in the active page."""
        return self.command({"type": "go_back"})

    def wait(self, ms: int = 500) -> dict[str, Any]:
        """Wait briefly in the active page."""
        return self.command({"type": "wait", "ms": ms})

    def command(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a raw browser-session command and return its result."""
        if self._closed:
            raise BrowserSessionError("Browser session is already closed.")
        command_id = self._next_command_id()
        message = {"id": command_id, **payload}
        assert self._process.stdin is not None
        self._process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self._process.stdin.flush()
        response = self._read_message(expected_id=command_id)
        if response.get("status") != "ok":
            raise BrowserSessionError(str(response.get("error") or response))
        return response.get("result") or {}

    def close(self) -> None:
        """Close the browser session and child process."""
        if self._closed:
            return
        self._closed = True
        if self._process.poll() is None and self._process.stdin is not None:
            try:
                command_id = self._next_command_id()
                self._process.stdin.write(json.dumps({"id": command_id, "type": "finish"}) + "\n")
                self._process.stdin.flush()
                self._read_message(expected_id=command_id)
            except Exception:
                pass
        if self._process.stdin is not None:
            try:
                self._process.stdin.close()
            except Exception:
                pass
        try:
            self._process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            try:
                self._process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def __enter__(self) -> "PlaywrightBrowserSession":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _next_command_id(self) -> str:
        self._command_index += 1
        return f"cmd-{self._command_index:04d}"

    def _read_message(self, expected_id: str | None = None) -> dict[str, Any]:
        assert self._process.stdout is not None
        while True:
            line = self._process.stdout.readline()
            if not line:
                stderr = ""
                if self._process.stderr is not None:
                    stderr = self._process.stderr.read() or ""
                raise BrowserSessionError(stderr.strip() or "Browser session exited before response.")
            message = json.loads(line)
            if expected_id is None or message.get("id") == expected_id:
                return message


def resolve_navigation_url(url: str, base_url: str) -> str:
    """Resolve browser navigation targets at the process boundary."""
    parsed_base = urlparse(base_url)
    if not parsed_base.scheme or parsed_base.scheme == "about":
        return url
    return urljoin(base_url, url)
