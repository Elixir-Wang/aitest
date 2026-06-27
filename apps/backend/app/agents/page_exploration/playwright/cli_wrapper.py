"""Python wrapper for playwright-cli Node.js tool."""

import subprocess
from typing import Optional
import yaml

from .schemas import (
    SnapshotResult,
    NavigateResult,
    ClickResult,
    FillResult,
    ElementInfo,
)


class PlaywrightCLI:
    """Wrapper for playwright-cli commands."""

    def __init__(self, timeout: int = 30, session_id: Optional[str] = None):
        self.timeout = timeout
        self.session_id = session_id

    def _build_command(self, *args: str) -> list[str]:
        """Build command with optional session_id."""
        cmd = ["playwright-cli", *args]
        if self.session_id:
            cmd.extend(["--session", self.session_id])
        return cmd

    def snap(self, url: str) -> SnapshotResult:
        """Capture page snapshot with element info."""
        cmd = self._build_command("snap", url)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )

        if result.returncode != 0:
            raise RuntimeError(f"snap failed: {result.stderr}")

        # ponytail: yaml.safe_load for YAML parsing
        data = yaml.safe_load(result.stdout)
        elements = [ElementInfo(**elem) for elem in data.get("elements", [])]

        return SnapshotResult(
            url=data["url"],
            title=data["title"],
            elements=elements,
            raw_output=result.stdout,
        )

    def navigate(self, url: str) -> NavigateResult:
        """Navigate to URL."""
        cmd = self._build_command("navigate", url)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )

        if result.returncode == 0:
            return NavigateResult(url=url, success=True)
        else:
            return NavigateResult(url=url, success=False, error=result.stderr)

    def click(self, locator: str) -> ClickResult:
        """Click element by locator."""
        cmd = self._build_command("click", locator)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )

        if result.returncode == 0:
            return ClickResult(success=True)
        else:
            return ClickResult(success=False, error=result.stderr)

    def fill(self, locator: str, value: str) -> FillResult:
        """Fill input element with value."""
        cmd = self._build_command("fill", locator, value)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )

        if result.returncode == 0:
            return FillResult(success=True)
        else:
            return FillResult(success=False, error=result.stderr)
