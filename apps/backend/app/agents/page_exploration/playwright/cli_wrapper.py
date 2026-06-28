"""Python wrapper for the playwright-cli browser automation tool."""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from app.core.settings import PLAYWRIGHT_RUNNER_DIR

from .schemas import (
    SnapshotResult,
    NavigateResult,
    ClickResult,
    FillResult,
    ElementInfo,
)


DEFAULT_PLAYWRIGHT_CLI_COMMAND = str(
    PLAYWRIGHT_RUNNER_DIR
    / "node_modules"
    / ".bin"
    / ("playwright-cli.cmd" if os.name == "nt" else "playwright-cli")
)
SNAPSHOT_ELEMENT_RE = re.compile(
    r'^\s*-\s+(?P<role>[\w-]+)(?:\s+"(?P<name>[^"]*)")?.*?\[ref=(?P<ref>e\d+)\]'
)
PAGE_URL_RE = re.compile(r"^- Page URL:\s*(?P<url>.+)$")
PAGE_TITLE_RE = re.compile(r"^- Page Title:\s*(?P<title>.*)$")


class PlaywrightCLI:
    """Wrapper for playwright-cli commands."""

    def __init__(
        self,
        timeout: int = 30,
        session_id: Optional[str] = None,
        command: Optional[str] = None,
    ):
        self.timeout = timeout
        self.session_id = session_id
        self.command = command or os.getenv(
            "AI_TESTING_PLAYWRIGHT_CLI_COMMAND",
            DEFAULT_PLAYWRIGHT_CLI_COMMAND,
        )

    def _build_command(self, *args: str) -> list[str]:
        """Build command with optional session_id."""
        cmd = [self.command]
        if self.session_id:
            cmd.append(f"-s={self.session_id}")
        cmd.extend(args)
        return cmd

    def snap(self, url: str) -> SnapshotResult:
        """Capture page snapshot with element info."""
        try:
            nav_result = self._run("open", url)
            if nav_result.returncode != 0 and "already" in f"{nav_result.stdout}\n{nav_result.stderr}".lower():
                nav_result = self._run("goto", url)
            if nav_result.returncode != 0:
                return SnapshotResult(
                    url=url,
                    title="",
                    elements=[],
                    raw_output=nav_result.stdout,
                    error=nav_result.stderr,
                )

            snapshot_result = self._run("snapshot")

            if snapshot_result.returncode != 0:
                return SnapshotResult(
                    url=url,
                    title="",
                    elements=[],
                    raw_output=snapshot_result.stdout,
                    error=snapshot_result.stderr,
                )

            return self._parse_snapshot_output(url, snapshot_result.stdout)
        except subprocess.TimeoutExpired:
            raise
        except Exception as e:
            return SnapshotResult(
                url=url,
                title="",
                elements=[],
                raw_output="",
                error=str(e),
            )

    def navigate(self, url: str) -> NavigateResult:
        """Navigate to URL."""
        result = self._run("goto", url)

        if result.returncode == 0:
            return NavigateResult(url=url, success=True)
        else:
            return NavigateResult(url=url, success=False, error=result.stderr)

    def click(self, locator: str) -> ClickResult:
        """Click element by locator."""
        result = self._run("click", locator)

        if result.returncode == 0:
            return ClickResult(success=True)
        else:
            return ClickResult(success=False, error=result.stderr)

    def fill(self, locator: str, value: str) -> FillResult:
        """Fill input element with value."""
        result = self._run("fill", locator, value)

        if result.returncode == 0:
            return FillResult(success=True)
        else:
            return FillResult(success=False, error=result.stderr)

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run playwright-cli with a deterministic cwd for its session files."""
        return subprocess.run(
            self._build_command(*args),
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=Path(PLAYWRIGHT_RUNNER_DIR),
        )

    def _parse_snapshot_output(self, fallback_url: str, output: str) -> SnapshotResult:
        """Convert playwright-cli snapshot text into the legacy structured result."""
        url = fallback_url
        title = ""
        elements: list[ElementInfo] = []

        for line in output.splitlines():
            url_match = PAGE_URL_RE.match(line)
            if url_match:
                url = url_match.group("url").strip()
                continue

            title_match = PAGE_TITLE_RE.match(line)
            if title_match:
                title = title_match.group("title").strip()
                continue

            element_match = SNAPSHOT_ELEMENT_RE.match(line)
            if not element_match:
                continue

            name = element_match.group("name") or ""
            elements.append(
                ElementInfo(
                    ref=element_match.group("ref"),
                    role=element_match.group("role"),
                    name=name,
                    text=_snapshot_text_for(line, name),
                    visible=True,
                )
            )

        return SnapshotResult(
            url=url,
            title=title,
            elements=elements,
            raw_output=output,
        )


def _snapshot_text_for(line: str, name: str) -> Optional[str]:
    """Extract inline text from snapshot nodes that do not expose a quoted name."""
    if name:
        return None
    if ":" not in line:
        return None
    text = line.split(":", 1)[1].strip()
    return text
