import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.services.api_automation.reporting import parse_pytest_json_report


SENSITIVE_RE = re.compile(
    r"(?i)(authorization:\s*bearer\s+|token=|password=|cookie:\s*|cybertron-robot-(?:key|token)[=:]\s*)([^\s]+)"
)


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

    sync = subprocess.run(
        ["uv", "sync"],
        cwd=suite_path,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=process_env,
    )
    stdout_parts = [sync.stdout]
    stderr_parts = [sync.stderr]

    report_path = run_dir / "report.json"
    pytest_targets = test_paths or ["tests"]
    pytest = subprocess.run(
        ["uv", "run", "pytest", *pytest_targets, "--json-report", f"--json-report-file={report_path}"],
        cwd=suite_path,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=process_env,
    )
    stdout_parts.append(pytest.stdout)
    stderr_parts.append(pytest.stderr)
    (run_dir / "stdout.txt").write_text(_redact("\n".join(stdout_parts)), encoding="utf-8")
    (run_dir / "stderr.txt").write_text(_redact("\n".join(stderr_parts)), encoding="utf-8")

    if not report_path.exists():
        return {
            "status": "failed",
            "summary": {},
            "error_message": "pytest-json-report 未生成 report.json。",
            "stdout_path": str(run_dir / "stdout.txt"),
            "stderr_path": str(run_dir / "stderr.txt"),
            "json_report_path": "",
            "exitcode": pytest.returncode,
        }

    summary = parse_pytest_json_report(report_path)
    return {
        "status": "passed" if pytest.returncode == 0 and summary.get("failed", 0) == 0 else "failed",
        "summary": summary,
        "error_message": "" if pytest.returncode == 0 else "pytest 执行失败。",
        "stdout_path": str(run_dir / "stdout.txt"),
        "stderr_path": str(run_dir / "stderr.txt"),
        "json_report_path": str(report_path),
        "exitcode": pytest.returncode,
    }


def _clear_previous_outputs(run_dir: Path) -> None:
    for filename in ("report.json", "stdout.txt", "stderr.txt"):
        path = run_dir / filename
        if path.exists():
            path.unlink()
    runtime_dir = run_dir / "runtime"
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)


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
