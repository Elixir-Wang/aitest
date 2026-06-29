import json
from pathlib import Path
from unittest.mock import Mock, patch

from app.services.exploration.browser_session import (
    PlaywrightBrowserSession,
    resolve_navigation_url,
)


class FakeStdout:
    def __init__(self, lines: list[dict]):
        self._lines = [json.dumps(line) + "\n" for line in lines]

    def readline(self) -> str:
        if not self._lines:
            return ""
        return self._lines.pop(0)


class FakeStdin:
    def __init__(self):
        self.writes: list[str] = []
        self.closed = False

    def write(self, value: str) -> int:
        self.writes.append(value)
        return len(value)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class FakeProcess:
    def __init__(self, lines: list[dict]):
        self.stdin = FakeStdin()
        self.stdout = FakeStdout(lines)
        self.stderr = Mock()
        self.returncode = None
        self.terminated = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.returncode = -9


def test_browser_session_sends_commands_to_one_child_process():
    process = FakeProcess(
        [
            {"kind": "session_started", "status": "started", "url": "https://example.test"},
            {"id": "cmd-0001", "status": "ok", "result": {"status": "passed", "url": "https://example.test/workspace"}},
            {"id": "cmd-0002", "status": "ok", "result": {"url": "https://example.test/workspace", "elements": []}},
            {"id": "cmd-0003", "status": "ok", "result": {"status": "closed"}},
        ]
    )

    with patch("subprocess.Popen", return_value=process) as popen:
        session = PlaywrightBrowserSession(start_url="https://example.test", browser_channel="chrome")
        navigate_result = session.navigate("/workspace")
        observe_result = session.observe()
        session.close()

    popen.assert_called_once()
    assert navigate_result["url"] == "https://example.test/workspace"
    assert observe_result["elements"] == []
    commands = [json.loads(line) for line in process.stdin.writes]
    assert [command["type"] for command in commands] == ["navigate", "observe", "finish"]
    assert commands[0]["url"] == "https://example.test/workspace"


def test_browser_session_passes_storage_state_to_runner(tmp_path: Path):
    process = FakeProcess(
        [
            {"kind": "session_started", "status": "started", "url": "https://example.test"},
            {"id": "cmd-0001", "status": "ok", "result": {"status": "closed"}},
        ]
    )
    storage_state = tmp_path / "state.json"
    storage_state.write_text("{}", encoding="utf-8")

    with patch("subprocess.Popen", return_value=process) as popen:
        session = PlaywrightBrowserSession(
            start_url="https://example.test",
            browser_channel="chrome",
            storage_state_path=storage_state,
        )
        session.close()

    args = popen.call_args[0][0]
    assert args[-1] == str(storage_state)


def test_resolve_navigation_url_handles_relative_paths():
    assert (
        resolve_navigation_url("/workspace", "https://example.test/login?next=/workspace")
        == "https://example.test/workspace"
    )
    assert resolve_navigation_url("https://other.test/workspace", "https://example.test/login") == "https://other.test/workspace"
    assert resolve_navigation_url("/workspace", "about:blank") == "/workspace"
