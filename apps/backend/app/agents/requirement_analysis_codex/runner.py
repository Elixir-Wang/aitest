import asyncio
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

from app.agents.model_selection import resolve_model_selection
from app.core.settings import REQUIREMENT_ANALYSIS_CODEX_COMMAND, REQUIREMENT_ANALYSIS_CODEX_TIMEOUT_SECONDS
from app.core.storage import project_requirement_dir
from app.schemas.requirement_analysis import RequirementAnalysisInput, RequirementAnalysisOutput


CAPABILITY_ID = "requirement_analysis"
CODEX_MODEL_PROVIDER = "backend_requirement_analysis"


async def run_requirement_analysis_with_codex(input_data: RequirementAnalysisInput) -> RequirementAnalysisOutput:
    output = await asyncio.to_thread(_run_codex_requirement_analysis, input_data)
    if not output.preliminary_requirement_markdown.strip():
        output.preliminary_requirement_markdown = input_data.primary_markdown_content.strip()
    return output


def _run_codex_requirement_analysis(input_data: RequirementAnalysisInput) -> RequirementAnalysisOutput:
    workdir = _prepare_workdir(input_data)
    prompt = _build_codex_prompt(input_data)
    _write_inputs(workdir, input_data, prompt)
    selection = resolve_model_selection(CAPABILITY_ID)
    command = _codex_command(workdir, selection, prompt)
    env = _codex_env(selection)
    _run_codex_process(command, workdir, env)
    return _read_analysis_output(workdir)


def _build_codex_prompt(input_data: RequirementAnalysisInput) -> str:
    auxiliary_count = len(input_data.auxiliary_documents)
    return "\n".join(
        [
            "你是 AI 测试系统的需求分析智能体。",
            "只能读取当前工作目录 input/ 和 skills/ 下的文件，不要扫描其他目录。",
            "这是一次非交互式批处理任务；必须立即读取输入、完成分析并写入输出文件。",
            "不要只回复确认、承诺或后续会处理；最终回答可以简短，但落盘文件必须先生成。",
            "",
            "请按以下固定流程执行，不要跳步：",
            "第一阶段：使用 requirement-review skill 对 input/primary.md 做第一次需求分析，生成待确认问题。",
            "第二阶段：使用 test-scenarios skill 对 input/primary.md 做第二次需求分析，从测试场景角度补充模块、规则、边界、异常路径和待确认问题。",
            "第三阶段：使用辅助文件 input/auxiliary/ 解答前两阶段生成的待确认问题。",
            "如果辅助文件能回答待确认问题，必须删除对应待确认条目，把答案写入 preliminary_requirement_markdown，并在 applied_supplements 记录来源。",
            "如果辅助文件证据不足、互相冲突或没有答案，保留待确认条目或冲突项，不要臆造。",
            "",
            "输出要求：",
            "- 必须生成 output/analysis.json，内容必须符合 RequirementAnalysisOutput。",
            "- 必须生成 output/analysis.md，作为待确认需求 tab 后面的分析报告 tab 展示内容。",
            "- analysis.json.analysis_report_markdown 必须等于 output/analysis.md 的正文。",
            "- preliminary_requirement_markdown 必须包含主需求原文，并合并已由辅助文件明确解答的补充内容。",
            "- clarification_questions/conflicts 只保留辅助文件无法回答或存在冲突的条目。",
            "- question 必须直接写要人工确认的问题，不要拆成“当前缺口”“缺失说明”等解释段。",
            "- recommended_options.answer_markdown 必须是可直接写入初步需求的答案。",
            "",
            "输入文件：",
            "- 主需求：input/primary.md",
            f"- 辅助文件数量：{auxiliary_count}",
            "- skill：skills/requirement-review/SKILL.md 与 skills/test-scenarios/SKILL.md",
            "",
            "RequirementAnalysisOutput 字段提醒：",
            "status, analysis_summary, preliminary_requirement_markdown, analysis_report_markdown, applied_supplements,",
            "maturity_assessment, key_gaps, assumptions, modules, clarification_questions, conflicts, coverage_audit, quality_gate, next_actions",
            "",
            f"项目：{input_data.project_id}",
            f"需求：{input_data.document_name} ({input_data.document_id})",
            f"主文件：{input_data.primary_filename}",
        ]
    )


def _prepare_workdir(input_data: RequirementAnalysisInput) -> Path:
    run_dir = input_data.run_id.strip() or "codex-latest"
    root = project_requirement_dir(input_data.project_id, input_data.document_id) / "analysis_runs" / run_dir / "codex-work"
    if root.exists():
        shutil.rmtree(root)
    (root / "input" / "auxiliary").mkdir(parents=True, exist_ok=True)
    (root / "output").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "skills").mkdir(parents=True, exist_ok=True)
    return root


def _write_inputs(workdir: Path, input_data: RequirementAnalysisInput, prompt: str) -> None:
    (workdir / "input" / "primary.md").write_text(input_data.primary_markdown_content, encoding="utf-8")
    (workdir / "input" / "metadata.json").write_text(
        json.dumps(input_data.model_dump(exclude={"primary_markdown_content", "auxiliary_documents"}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for index, document in enumerate(input_data.auxiliary_documents, start=1):
        safe_name = _safe_filename(document.filename or f"auxiliary-{index}.md")
        path = workdir / "input" / "auxiliary" / f"{index:03d}-{document.mapping_id}-{safe_name}"
        path.write_text(document.markdown_content, encoding="utf-8")
    (workdir / "prompt.md").write_text(prompt, encoding="utf-8")
    _copy_skill("requirement-review", workdir / "skills" / "requirement-review")
    _copy_skill("test-scenarios", workdir / "skills" / "test-scenarios")


def _copy_skill(skill_name: str, target: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "requirement_analysis" / "primary_analysis" / "skills" / skill_name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _codex_command(workdir: Path, selection, prompt: str) -> list[str]:
    codex_command = _codex_command_path()
    command = [
        codex_command,
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
    return command


def _codex_command_path() -> str:
    configured = REQUIREMENT_ANALYSIS_CODEX_COMMAND.strip()
    if not configured:
        raise RuntimeError("需求分析智能体执行命令未配置，请设置 AI_TESTING_REQUIREMENT_ANALYSIS_CODEX_COMMAND。")
    configured_path = Path(configured).expanduser()
    if configured_path.is_absolute() or configured_path.parent != Path("."):
        if configured_path.exists():
            return str(configured_path)
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


def _codex_env(selection) -> dict[str, str]:
    env = os.environ.copy()
    env["CODEX_API_KEY"] = selection.api_key
    env["OPENAI_API_KEY"] = selection.api_key
    if selection.base_url:
        env["OPENAI_BASE_URL"] = selection.base_url
    return env


def _run_codex_process(command: list[str], workdir: Path, env: dict[str, str]) -> None:
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
    reader = threading.Thread(target=_enqueue_output_lines, args=(process.stdout, stdout_queue), daemon=True)
    reader.start()
    started_at = time.monotonic()
    while process.poll() is None:
        _drain_codex_stdout(workdir, stdout_queue, stdout_lines)
        if time.monotonic() - started_at > REQUIREMENT_ANALYSIS_CODEX_TIMEOUT_SECONDS:
            process.kill()
            process.wait()
            reader.join(timeout=1)
            stderr = process.stderr.read() if process.stderr else ""
            _write_process_logs(workdir, stdout_lines, stderr)
            raise subprocess.TimeoutExpired(command, REQUIREMENT_ANALYSIS_CODEX_TIMEOUT_SECONDS, output="\n".join(stdout_lines), stderr=stderr)
        time.sleep(0.2)
    process.wait()
    reader.join(timeout=1)
    stderr = process.stderr.read() if process.stderr else ""
    _drain_codex_stdout(workdir, stdout_queue, stdout_lines)
    _write_process_logs(workdir, stdout_lines, stderr)
    if process.returncode != 0:
        raise RuntimeError(f"需求分析智能体执行失败，退出码：{process.returncode}。{stderr.strip()}")


def _enqueue_output_lines(pipe, output_queue: queue.Queue[str | None]) -> None:
    try:
        if pipe is None:
            return
        for line in pipe:
            output_queue.put(line)
    finally:
        output_queue.put(None)


def _drain_codex_stdout(workdir: Path, stdout_queue: queue.Queue[str | None], stdout_lines: list[str]) -> None:
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


def _write_process_logs(workdir: Path, stdout_lines: list[str], stderr: str) -> None:
    logs_dir = workdir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.log").write_text("\n".join(stdout_lines), encoding="utf-8")
    (logs_dir / "stderr.log").write_text(stderr, encoding="utf-8")


def _read_analysis_output(workdir: Path) -> RequirementAnalysisOutput:
    output_path = workdir / "output" / "analysis.json"
    if not output_path.exists():
        raise ValueError("需求分析智能体未生成 output/analysis.json。")
    output = RequirementAnalysisOutput.model_validate_json(output_path.read_text(encoding="utf-8"))
    report_path = workdir / "output" / "analysis.md"
    if report_path.exists():
        report = report_path.read_text(encoding="utf-8").strip()
        if report:
            output.analysis_report_markdown = report
    return output


def _safe_filename(value: str) -> str:
    return "".join(char if char not in '<>:"/\\|?*' else "_" for char in value).strip() or "auxiliary.md"
