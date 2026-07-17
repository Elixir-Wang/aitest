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
            Path(env["API_SCENARIO_RESULT_PATH"]).write_text('{"status":"passed","steps":[]}', encoding="utf-8")
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
    assert calls[1][2]["API_SCENARIO_RESULT_PATH"] == str(run_dir / "scenario-result.json")
    assert json.loads((run_dir / "runtime" / "env.json").read_text(encoding="utf-8"))["auth"] == {"bearer_saved": True}
    assert "secret-token" not in (run_dir / "stdout.txt").read_text(encoding="utf-8")
    assert result["summary"]["passed"] == 1
    assert result["scenario_result_path"] == str(run_dir / "scenario-result.json")


def test_runner_returns_observed_when_observation_evidence_exists(monkeypatch, tmp_path: Path) -> None:
    suite_path = tmp_path / "suite"
    run_dir = tmp_path / "run"
    suite_path.mkdir()

    def fake_run(command, cwd, text, capture_output, timeout, env):
        if command[:2] == ["uv", "run"]:
            report_file = next(part.split("=", 1)[1] for part in command if part.startswith("--json-report-file="))
            Path(report_file).write_text(
                json.dumps({"summary": {"total": 1, "passed": 1, "failed": 0}, "duration": 0.1, "tests": []}),
                encoding="utf-8",
            )
            Path(env["API_OBSERVATION_RESULT_PATH"]).write_text(
                json.dumps(
                    {
                        "observations": [
                            {
                                "case_id": "apitc-1",
                                "status_code": 400,
                                "response_body": {"code": "INVALID_ARGUMENT"},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_script_suite(
        run_id="apirun-1",
        project_id="project-1",
        suite_path=suite_path,
        run_dir=run_dir,
        environment={"api_base_url": "https://api.example.test"},
        timeout=30,
    )

    assert result["status"] == "observed"
    assert result["summary"]["observed"] == 1
    assert result["observation_result_path"] == str(run_dir / "observations.json")


def test_collect_script_suite_uses_uv_and_returns_redacted_failure(monkeypatch, tmp_path: Path) -> None:
    suite_path = tmp_path / "suite"
    suite_path.mkdir()
    calls = []

    def fake_run(command, cwd, text, capture_output, timeout, env):
        calls.append((command, cwd, timeout, env))
        if command == ["uv", "sync"]:
            return SimpleNamespace(returncode=0, stdout="sync ok", stderr="")
        return SimpleNamespace(
            returncode=4,
            stdout="",
            stderr="Authorization: Bearer secret-token\nModuleNotFoundError: support",
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.collect_script_suite(suite_path=suite_path, timeout=30)

    assert calls[0][0] == ["uv", "sync"]
    assert calls[1][0] == ["uv", "run", "pytest", "--collect-only", "testcases"]
    assert all(call[1] == suite_path.resolve() for call in calls)
    assert result == {
        "ok": False,
        "exitcode": 4,
        "stdout": "",
        "stderr": "Authorization: Bearer ***\nModuleNotFoundError: support",
    }


def test_collect_script_suite_uses_provided_test_paths(monkeypatch, tmp_path: Path) -> None:
    suite_path = tmp_path / "suite"
    suite_path.mkdir()
    calls = []

    def fake_run(command, cwd, text, capture_output, timeout, env):
        calls.append((command, cwd))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.collect_script_suite(
        suite_path=suite_path,
        timeout=30,
        test_paths=["testcases/v1/agent/test_agent.py"],
    )

    assert calls[1][0] == [
        "uv",
        "run",
        "pytest",
        "--collect-only",
        "testcases/v1/agent/test_agent.py",
    ]
    assert all(call[1] == suite_path.resolve() for call in calls)
    assert result["ok"] is True
    assert result["exitcode"] == 0


def test_suite_processes_do_not_inherit_backend_virtual_env(monkeypatch, tmp_path: Path) -> None:
    suite_path = tmp_path / "suite"
    suite_path.mkdir()
    captured_envs = []

    monkeypatch.setenv("VIRTUAL_ENV", "D:/project/test_project/apps/backend/.venv")

    def fake_run(command, cwd, text, capture_output, timeout, env):
        captured_envs.append(env)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.collect_script_suite(suite_path=suite_path, timeout=30)

    assert result["ok"] is True
    assert captured_envs
    assert all("VIRTUAL_ENV" not in env for env in captured_envs)
