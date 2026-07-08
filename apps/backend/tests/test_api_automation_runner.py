import json
from pathlib import Path
from types import SimpleNamespace

from app.services.api_automation import reporting, runner


def test_parse_pytest_json_report_reads_summary(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "summary": {"total": 2, "passed": 1, "failed": 1},
                "duration": 1.25,
                "exitcode": 1,
                "tests": [{"nodeid": "tests/test_api.py::test_one", "outcome": "failed"}],
            }
        ),
        encoding="utf-8",
    )

    parsed = reporting.parse_pytest_json_report(report_path)

    assert parsed["total"] == 2
    assert parsed["passed"] == 1
    assert parsed["failed"] == 1
    assert parsed["exitcode"] == 1


def test_runner_cleans_stale_outputs_writes_env_and_parses_report(monkeypatch, tmp_path: Path) -> None:
    suite_path = tmp_path / "suite"
    run_dir = tmp_path / "run"
    suite_path.mkdir()
    run_dir.mkdir()
    (run_dir / "report.json").write_text("stale", encoding="utf-8")
    (run_dir / "stdout.txt").write_text("old stdout", encoding="utf-8")
    (run_dir / "stderr.txt").write_text("old stderr", encoding="utf-8")
    calls = []

    def fake_run(command, cwd, text, capture_output, timeout, env):
        calls.append((command, cwd, env))
        if command[:2] == ["uv", "run"]:
            report_file = next(part.split("=", 1)[1] for part in command if part.startswith("--json-report-file="))
            Path(report_file).write_text(
                json.dumps({"summary": {"total": 1, "passed": 1, "failed": 0}, "duration": 0.2, "exitcode": 0, "tests": []}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="Authorization: Bearer secret-token", stderr="")
        return SimpleNamespace(returncode=0, stdout="sync ok", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_script_suite(
        run_id="apirun-1",
        project_id="project-1",
        suite_path=suite_path,
        run_dir=run_dir,
        environment={
            "api_base_url": "https://api.example.test",
            "timeout_seconds": 5,
            "auth": {"bearer": "secret-token"},
            "headers": {"X-Test": "yes"},
            "variables": {"tenant_id": "t1"},
        },
        timeout=30,
    )

    assert calls[0][0] == ["uv", "sync"]
    assert calls[1][0][:3] == ["uv", "run", "pytest"]
    assert calls[1][2]["API_BASE_URL"] == "https://api.example.test"
    assert calls[1][2]["API_AUTH_BEARER"] == "secret-token"
    assert json.loads((run_dir / "runtime" / "env.json").read_text(encoding="utf-8"))["auth"] == {"bearer_saved": True}
    assert "secret-token" not in (run_dir / "stdout.txt").read_text(encoding="utf-8")
    assert result["summary"]["passed"] == 1
