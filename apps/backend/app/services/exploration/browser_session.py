import json
import queue
import subprocess
import threading
from pathlib import Path

from app.core.settings import PLAYWRIGHT_BROWSER_CHANNEL, PLAYWRIGHT_RUNNER_DIR


class BrowserSessionError(RuntimeError):
    pass


class PlaywrightBrowserSession:
    def __init__(
        self,
        *,
        start_url: str,
        storage_state_path: str = "",
        browser_channel: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.start_url = start_url
        self.storage_state_path = storage_state_path
        self.browser_channel = browser_channel if browser_channel is not None else PLAYWRIGHT_BROWSER_CHANNEL
        self.timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[str] | None = None
        self._queue: queue.Queue[dict | None] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._sequence = 0

    def __enter__(self) -> "PlaywrightBrowserSession":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if self._process is not None:
            return
        script_path = PLAYWRIGHT_RUNNER_DIR / "browser-session.mjs"
        command = [
            "node",
            str(script_path),
            self.start_url or "about:blank",
            self.browser_channel or "",
            self.storage_state_path or "",
        ]
        self._process = subprocess.Popen(
            command,
            cwd=PLAYWRIGHT_RUNNER_DIR,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        started = self._read_message()
        if not started or started.get("kind") != "session_started":
            raise BrowserSessionError("Playwright browser session did not start.")

    def observe(self) -> dict:
        return self.command({"type": "observe"})

    def click(self, element_id: str) -> dict:
        return self.command({"type": "click", "element_id": element_id})

    def fill(self, element_id: str, value: str) -> dict:
        return self.command({"type": "fill", "element_id": element_id, "value": value})

    def go_back(self) -> dict:
        return self.command({"type": "go_back"})

    def close_modal(self) -> dict:
        return self.command({"type": "close_modal"})

    def wait(self, ms: int = 500) -> dict:
        return self.command({"type": "wait", "ms": ms})

    def navigate(self, url: str) -> dict:
        return self.command({"type": "navigate", "url": url})

    def command(self, payload: dict) -> dict:
        process = self._ensure_process()
        if process.stdin is None:
            raise BrowserSessionError("Playwright browser session stdin is unavailable.")
        self._sequence += 1
        command_id = f"cmd-{self._sequence:04d}"
        process.stdin.write(json.dumps({"id": command_id, **payload}, ensure_ascii=False) + "\n")
        process.stdin.flush()
        while True:
            message = self._read_message()
            if message is None:
                raise BrowserSessionError("Playwright browser session closed unexpectedly.")
            if message.get("id") != command_id:
                continue
            if message.get("status") != "ok":
                raise BrowserSessionError(str(message.get("error") or "Playwright browser session command failed."))
            result = message.get("result")
            return result if isinstance(result, dict) else {}

    def close(self) -> None:
        process = self._process
        if process is None:
            return
        try:
            if process.poll() is None and process.stdin is not None:
                self._sequence += 1
                process.stdin.write(json.dumps({"id": f"cmd-{self._sequence:04d}", "type": "finish"}) + "\n")
                process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if self._reader is not None:
            self._reader.join(timeout=1)
        self._process = None

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._process is None or self._process.poll() is not None:
            stderr = self._process.stderr.read() if self._process and self._process.stderr else ""
            raise BrowserSessionError(f"Playwright browser session is not running. {stderr}".strip())
        return self._process

    def _read_stdout(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            self._queue.put(None)
            return
        try:
            for line in process.stdout:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                self._queue.put(payload if isinstance(payload, dict) else {})
        finally:
            self._queue.put(None)

    def _read_message(self) -> dict | None:
        try:
            return self._queue.get(timeout=self.timeout_seconds)
        except queue.Empty as error:
            raise BrowserSessionError("Timed out waiting for Playwright browser session.") from error
