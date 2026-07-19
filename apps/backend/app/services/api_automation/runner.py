import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.services.api_automation.reporting import parse_pytest_json_report


SENSITIVE_RE = re.compile(
    r"(?i)(authorization:\s*bearer\s+|token=|password=|cookie:\s*|cybertron-robot-(?:key|token)[=:]\s*)([^\s]+)"
)


def _run_backend_pytest(
    args: list[str],
    *,
    cwd: Path,
    text: bool,
    capture_output: bool,
    timeout: int,
    env: dict[str, str],
):
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=cwd,
        text=text,
        capture_output=capture_output,
        timeout=timeout,
        env=env,
    )


def collect_script_suite(*, suite_path: Path, timeout: int, test_paths: list[str] | None = None) -> dict[str, Any]:
    suite_path = suite_path.resolve()
    process_env = dict(os.environ)
    process_env.pop("VIRTUAL_ENV", None)
    collected = _run_backend_pytest(
        ["--collect-only", *(test_paths or ["testcases"])],
        cwd=suite_path,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=process_env,
    )
    return {
        "ok": collected.returncode == 0,
        "exitcode": collected.returncode,
        "stdout": _redact(collected.stdout),
        "stderr": _redact(collected.stderr),
    }


def run_script_suite(
    *,
    run_id: str,
    project_id: str,
    suite_path: Path,
    run_dir: Path,
    environment: dict[str, Any],
    timeout: int,
    test_paths: list[str] | None = None,
) -> dict[str, Any]:
    suite_path = suite_path.resolve()
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    _clear_previous_outputs(run_dir)
    _write_runtime_env(run_dir, environment)
    process_env = _build_process_env(environment)
    scenario_result_path = run_dir / "scenario-result.json"
    observation_result_path = run_dir / "observations.json"
    process_env["API_SCENARIO_RESULT_PATH"] = str(scenario_result_path)
    process_env["API_OBSERVATION_RESULT_PATH"] = str(observation_result_path)

    report_path = run_dir / "report.json"
    pytest_targets = test_paths or ["tests"]
    pytest = _run_backend_pytest(
        [*pytest_targets, "--json-report", f"--json-report-file={report_path}"],
        cwd=suite_path,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=process_env,
    )
    (run_dir / "stdout.txt").write_text(_redact(pytest.stdout), encoding="utf-8")
    (run_dir / "stderr.txt").write_text(_redact(pytest.stderr), encoding="utf-8")

    if not report_path.exists():
        return {
            "status": "failed",
            "summary": {},
            "error_message": "pytest-json-report 未生成 report.json。",
            "stdout_path": str(run_dir / "stdout.txt"),
            "stderr_path": str(run_dir / "stderr.txt"),
            "json_report_path": "",
            "scenario_result_path": str(scenario_result_path) if scenario_result_path.exists() else "",
            "observation_result_path": str(observation_result_path) if observation_result_path.exists() else "",
            "exitcode": pytest.returncode,
        }

    summary = parse_pytest_json_report(report_path)
    observations = _read_observations(observation_result_path)
    if observations:
        summary["observed"] = len(observations)
    status = "failed"
    if pytest.returncode == 0 and summary.get("failed", 0) == 0:
        status = "observed" if observations else "passed"
    return {
        "status": status,
        "summary": summary,
        "error_message": "" if pytest.returncode == 0 else "pytest 执行失败。",
        "stdout_path": str(run_dir / "stdout.txt"),
        "stderr_path": str(run_dir / "stderr.txt"),
        "json_report_path": str(report_path),
        "scenario_result_path": str(scenario_result_path) if scenario_result_path.exists() else "",
        "observation_result_path": str(observation_result_path) if observation_result_path.exists() else "",
        "exitcode": pytest.returncode,
    }


def _clear_previous_outputs(run_dir: Path) -> None:
    for filename in ("report.json", "scenario-result.json", "observations.json", "stdout.txt", "stderr.txt"):
        path = run_dir / filename
        if path.exists():
            path.unlink()
    runtime_dir = run_dir / "runtime"
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)


def _read_observations(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    observations = payload.get("observations", []) if isinstance(payload, dict) else []
    return [item for item in observations if isinstance(item, dict)]


def _write_runtime_env(run_dir: Path, environment: dict[str, Any]) -> None:
    runtime_dir = run_dir / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "api_base_url": environment.get("api_base_url", ""),
        "timeout_seconds": environment.get("timeout_seconds", 30),
        "headers": _mask_headers(environment.get("headers", {})),
        "variables": environment.get("variables", {}),
        "auth": _mask_auth(environment.get("auth", {})),
    }
    (runtime_dir / "env.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_process_env(environment: dict[str, Any]) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    env["API_BASE_URL"] = str(environment.get("api_base_url", ""))
    env["API_TIMEOUT_SECONDS"] = str(environment.get("timeout_seconds", 30))
    auth = environment.get("auth", {})
    if isinstance(auth, dict) and auth.get("bearer"):
        env["API_AUTH_BEARER"] = str(auth["bearer"])
    headers = environment.get("headers", {})
    if isinstance(headers, dict):
        for key, value in headers.items():
            env[f"API_HEADER_{str(key).upper().replace('-', '_')}"] = str(value)
    variables = environment.get("variables", {})
    if isinstance(variables, dict):
        for key, value in variables.items():
            env[f"API_VAR_{str(key).upper()}"] = str(value)
    return env


def _mask_auth(auth: Any) -> dict[str, Any]:
    if not isinstance(auth, dict):
        return {}
    masked = {}
    if auth.get("bearer"):
        masked["bearer_saved"] = True
    if auth.get("cookie"):
        masked["cookie_saved"] = True
    return masked


def _mask_headers(headers: Any) -> dict[str, Any]:
    if not isinstance(headers, dict):
        return {}
    sensitive_names = {"authorization", "cookie", "set-cookie", "x-api-key", "api-key", "cybertron-robot-key", "cybertron-robot-token"}
    return {
        str(key): "***" if str(key).lower() in sensitive_names else value
        for key, value in headers.items()
    }


def _redact(value: str) -> str:
    return SENSITIVE_RE.sub(lambda match: f"{match.group(1)}***", value)
