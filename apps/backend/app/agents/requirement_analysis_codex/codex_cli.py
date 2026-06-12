import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path, PurePath

from app.core.settings import REQUIREMENT_ANALYSIS_CODEX_COMMAND, REQUIREMENT_ANALYSIS_CODEX_TIMEOUT_SECONDS


CODEX_MODEL_PROVIDER = "backend_requirement_analysis"


def codex_command(workdir: Path, selection, prompt: str) -> list[str]:
    codex_command_path = resolve_codex_command_path()
    return [
        codex_command_path,
        "exec",
        "--json",
        "--ignore-user-config",
        "--ignore-rules",
        "-c",
        f"model_provider={json.dumps(CODEX_MODEL_PROVIDER)}",
        "-c",
        f"model_providers.{CODEX_MODEL_PROVIDER}.name={json.dumps(CODEX_MODEL_PROVIDER)}",
        "-c",
        f"model_providers.{CODEX_MODEL_PROVIDER}.base_url={json.dumps(selection.base_url or 'https://api.openai.com/v1')}",
        "-c",
        f"model_providers.{CODEX_MODEL_PROVIDER}.wire_api={json.dumps('responses')}",
        "-c",
        f"model_providers.{CODEX_MODEL_PROVIDER}.requires_openai_auth=true",
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "-C",
        str(workdir),
        "--model",
        selection.model,
        "--output-last-message",
        str(workdir / "output" / "codex-final.md"),
        prompt,
    ]


def resolve_codex_command_path() -> str:
    configured = REQUIREMENT_ANALYSIS_CODEX_COMMAND.strip()
    if not configured:
        raise RuntimeError("需求分析智能体执行命令未配置，请设置 AI_TESTING_REQUIREMENT_ANALYSIS_CODEX_COMMAND。")
    expanded = os.path.expanduser(configured)
    configured_path = PurePath(expanded)
    if configured_path.is_absolute() or configured_path.parent != PurePath("."):
        if os.path.exists(expanded):
            return expanded
        raise RuntimeError(f"需求分析智能体执行命令不存在：{configured}")
    resolved = shutil.which(configured)
    if resolved:
        return resolved
    if os.name == "nt" and not configured.lower().endswith((".cmd", ".bat", ".exe")):
        for suffix in (".cmd", ".bat", ".exe"):
            resolved = shutil.which(f"{configured}{suffix}")
            if resolved:
                return resolved
    raise RuntimeError(
        "未检测到可用需求分析智能体执行命令，无法执行需求分析。"
        "请在后端运行环境安装执行命令，或设置 AI_TESTING_REQUIREMENT_ANALYSIS_CODEX_COMMAND 为可执行文件路径。"
    )


def codex_env(selection) -> dict[str, str]:
    env = os.environ.copy()
    env["CODEX_API_KEY"] = selection.api_key
    env["OPENAI_API_KEY"] = selection.api_key
    if selection.base_url:
        env["OPENAI_BASE_URL"] = selection.base_url
    return env


def run_codex_process(command: list[str], workdir: Path, env: dict[str, str]) -> None:
    try:
        process = subprocess.Popen(
            command,
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
        )
    except OSError as error:
        raise RuntimeError(f"需求分析智能体启动失败：{error}") from error
    stdout_queue: queue.Queue[str | None] = queue.Queue()
    stdout_lines: list[str] = []
    reader = threading.Thread(target=enqueue_output_lines, args=(process.stdout, stdout_queue), daemon=True)
    reader.start()
    started_at = time.monotonic()
    while process.poll() is None:
        drain_codex_stdout(workdir, stdout_queue, stdout_lines)
        if time.monotonic() - started_at > REQUIREMENT_ANALYSIS_CODEX_TIMEOUT_SECONDS:
            process.kill()
            process.wait()
            reader.join(timeout=1)
            stderr = process.stderr.read() if process.stderr else ""
            write_process_logs(workdir, stdout_lines, stderr)
            raise subprocess.TimeoutExpired(command, REQUIREMENT_ANALYSIS_CODEX_TIMEOUT_SECONDS, output="\n".join(stdout_lines), stderr=stderr)
        time.sleep(0.2)
    process.wait()
    reader.join(timeout=1)
    stderr = process.stderr.read() if process.stderr else ""
    drain_codex_stdout(workdir, stdout_queue, stdout_lines)
    write_process_logs(workdir, stdout_lines, stderr)
    if process.returncode != 0:
        # 尝试从 stdout 中提取错误信息
        error_detail = ""
        for line in stdout_lines:
            if '"type":"error"' in line or '"type":"turn.failed"' in line:
                try:
                    import json
                    event = json.loads(line)
                    if event.get("type") == "error":
                        error_detail = event.get("message", "")
                        break
                    elif event.get("type") == "turn.failed":
                        error_detail = event.get("error", {}).get("message", "")
                        break
                except:
                    pass

        error_msg = f"需求分析智能体执行失败，退出码：{process.returncode}。"
        if error_detail:
            error_msg += f"\n错误详情：{error_detail}"
        elif stderr.strip():
            error_msg += f"{stderr.strip()}"

        raise RuntimeError(error_msg)


def enqueue_output_lines(pipe, output_queue: queue.Queue[str | None]) -> None:
    try:
        if pipe is None:
            return
        for line in pipe:
            output_queue.put(line)
    finally:
        output_queue.put(None)


def drain_codex_stdout(workdir: Path, stdout_queue: queue.Queue[str | None], stdout_lines: list[str]) -> None:
    events_path = workdir / "logs" / "codex-events.jsonl"
    while True:
        try:
            line = stdout_queue.get_nowait()
        except queue.Empty:
            break
        if line is None:
            continue
        stdout_lines.append(line.rstrip("\n"))
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(line if line.endswith("\n") else f"{line}\n")


def write_process_logs(workdir: Path, stdout_lines: list[str], stderr: str) -> None:
    logs_dir = workdir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.log").write_text("\n".join(stdout_lines), encoding="utf-8")
    (logs_dir / "stderr.log").write_text(stderr, encoding="utf-8")
