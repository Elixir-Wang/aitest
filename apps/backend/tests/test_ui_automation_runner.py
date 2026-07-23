from pathlib import Path

from app.services.ui_automation import runner


def test_run_case_executes_exact_node_and_writes_generic_result(monkeypatch, tmp_path: Path):
    captured = {}

    class Completed:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Completed()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_case(
        run_id="uirun-1",
        suite_path=tmp_path / "suite",
        run_dir=tmp_path / "run",
        pytest_node_id="testcases/generated/test_login.py::test_uiauto_1",
        environment={"site_url": "https://example.test", "storage_state_path": ""},
        timeout=30,
    )

    assert captured["command"][-1] == "testcases/generated/test_login.py::test_uiauto_1"
    assert captured["kwargs"]["env"]["UI_BASE_URL"] == "https://example.test"
    assert result["status"] == "passed"
    assert Path(result["result_path"]).exists()
    assert Path(result["stdout_path"]).read_text(encoding="utf-8") == "1 passed"


def test_runner_redacts_sensitive_output(monkeypatch, tmp_path: Path):
    class Completed:
        returncode = 1
        stdout = "password=secret token=abc"
        stderr = "authorization: bearer xyz"

    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: Completed())

    result = runner.run_case(
        run_id="uirun-1",
        suite_path=tmp_path / "suite",
        run_dir=tmp_path / "run",
        pytest_node_id="testcases/generated/test_login.py::test_uiauto_1",
        environment={"site_url": "https://example.test", "storage_state_path": ""},
        timeout=30,
    )

    assert "secret" not in Path(result["stdout_path"]).read_text(encoding="utf-8")
    assert "xyz" not in Path(result["stderr_path"]).read_text(encoding="utf-8")
    assert result["status"] == "failed"

