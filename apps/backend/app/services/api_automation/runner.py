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
    scenario_file: str | None = None,
) -> dict[str, Any]:
    suite_path = suite_path.resolve()
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    _clear_previous_outputs(run_dir)
    _write_runtime_env(run_dir, environment)
    process_env = _build_process_env(environment)
    process_env.pop("API_SCENARIO_FILE", None)
    if scenario_file:
        process_env["API_SCENARIO_FILE"] = scenario_file
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
        status = "passed"

    # 构建详细的失败消息
    error_message = ""
    if pytest.returncode != 0:
        failed_count = summary.get("failed", 0)
        passed_count = summary.get("passed", 0)
        total_count = summary.get("total", 0)

        # 从 stdout.txt 中解析详细的失败信息（包含完整的错误消息）
        stdout_path = run_dir / "stdout.txt"
        stdout_content = stdout_path.read_text(encoding="utf-8") if stdout_path.exists() else ""

        # 从 report.json 中提取失败的测试用例信息
        failed_tests = []
        for test in summary.get("tests", []):
            if test.get("outcome") == "failed":
                nodeid = test.get("nodeid", "")
                # 提取用例名称（去掉路径）
                test_name = nodeid.split("::")[-1] if "::" in nodeid else nodeid

                # 从 stdout 中提取该用例的详细失败信息
                error_detail = "断言失败"
                lines = stdout_content.split("\n")
                test_block_start = -1
                test_block_end = -1

                # 找到该用例的失败信息块
                for i, line in enumerate(lines):
                    if test_name in line and "test_agent_analysis" in line:
                        test_block_start = i
                        # 找到下一个测试用例或 FAILURES 结束标记
                        for j in range(i + 1, len(lines)):
                            if lines[j].startswith("===") or lines[j].startswith("FAILED"):
                                test_block_end = j
                                break
                        break

                if test_block_start >= 0:
                    test_block_end = test_block_end if test_block_end > 0 else min(test_block_start + 60, len(lines))
                    test_block = "\n".join(lines[test_block_start:test_block_end])

                    # 从测试块中提取详细信息
                    # 1. 提取 case_id
                    case_id_match = re.search(r"case_id['\"]:\s*['\"]([^'\"]+)['\"]", test_block)
                    if case_id_match:
                        case_id = case_id_match.group(1)

                    # 2. 提取断言失败详情（查找 "断言X" 或 "期望值"/"实际值"）
                    assertion_detail = ""
                    for line in lines[test_block_start:test_block_end]:
                        if "断言" in line and "失败" in line:
                            # 找到失败信息，提取关键部分
                            assertion_detail = line.strip()
                            break

                    # 3. 如果没有找到，从 E 行提取错误
                    if not assertion_detail:
                        for line in lines[test_block_start:test_block_end]:
                            if line.strip().startswith("E "):
                                assertion_detail = line.strip()[2:].strip()
                                break

                    # 4. 尝试从断言代码中提取期望值和实际值
                    expected_match = re.search(r"expected['\"]?:\s*(\d+|true|false|'[^']*'|\"[^\"]*\")", test_block)
                    actual_line = ""
                    for line in lines[test_block_start:test_block_end]:
                        if "实际值" in line or "actual" in line.lower():
                            actual_line = line
                            break

                    if assertion_detail:
                        error_detail = assertion_detail
                    elif expected_match:
                        error_detail = f"期望 {expected_match.group(1)}"
                        if actual_line:
                            actual_match = re.search(r"[实际actual][:：]\s*(.+?)(?:\n|$)", actual_line, re.IGNORECASE)
                            if actual_match:
                                error_detail += f"，实际 {actual_match.group(1).strip()}"
                        else:
                            error_detail += "（查看详情请查看控制台输出）"
                    else:
                        error_detail = f"用例 {case_id}" if case_id else "断言失败"

                # 清理错误详情，限制长度
                if len(error_detail) > 80:
                    error_detail = error_detail[:80] + "..."

                failed_tests.append(f"{test_name}: {error_detail}")

        if failed_tests:
            # 构建详细错误消息
            error_message = f"pytest 执行失败：{failed_count}/{total_count} 个测试用例失败\n\n"
            for i, failed in enumerate(failed_tests[:5], 1):
                error_message += f"  {i}. {failed}\n"
            if len(failed_tests) > 5:
                error_message += f"  ... 还有 {len(failed_tests) - 5} 个失败用例\n"
        else:
            error_message = f"pytest 执行失败（exitcode={pytest.returncode}）"

    return {
        "status": status,
        "summary": summary,
        "error_message": error_message,
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
