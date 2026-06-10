import asyncio
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path, PurePath

from app.agents.model_selection import resolve_model_selection
from app.core.settings import (
    KNOWLEDGE_QUERY_CODEX_COMMAND,
    KNOWLEDGE_QUERY_CODEX_TIMEOUT_SECONDS,
    PROJECT_FILE_STORAGE_ROOT,
)
from app.agents.knowledge_chat.schemas import KnowledgeQueryInput, KnowledgeQueryOutput


CAPABILITY_ID = "knowledge_query"
CODEX_MODEL_PROVIDER = "backend_knowledge_query"


async def run_knowledge_query_with_codex(input_data: KnowledgeQueryInput) -> KnowledgeQueryOutput:
    return await asyncio.to_thread(_run_codex_knowledge_query, input_data)


def _run_codex_knowledge_query(input_data: KnowledgeQueryInput) -> KnowledgeQueryOutput:
    workdir = _prepare_query_workdir(input_data)
    prompt = _build_query_prompt(input_data)
    _write_query_inputs(workdir, input_data, prompt)
    selection = resolve_model_selection(CAPABILITY_ID)
    command = _codex_command(workdir, selection, prompt)
    env = _codex_env(selection)
    _run_codex_process(command, workdir, env)
    return _read_query_output(workdir)


def _prepare_query_workdir(input_data: KnowledgeQueryInput) -> Path:
    root = PROJECT_FILE_STORAGE_ROOT / input_data.project_id / "knowledge" / "agentic-search"
    if root.exists():
        shutil.rmtree(root)
    (root / "input").mkdir(parents=True, exist_ok=True)
    (root / "output").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _write_query_inputs(workdir: Path, input_data: KnowledgeQueryInput, prompt: str) -> None:
    (workdir / "input" / "knowledge-query-input.json").write_text(
        input_data.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (workdir / "input" / "requirements").mkdir(exist_ok=True)
    for index, document in enumerate(input_data.source_documents, start=1):
        filename = f"{index:03d}-{_safe_filename(document.document_name)}-v{document.version_no}.md"
        (workdir / "input" / "requirements" / filename).write_text(document.markdown_content, encoding="utf-8")
    (workdir / "input" / "explorations.json").write_text(
        json.dumps([item.model_dump() for item in input_data.explorations], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (workdir / "prompt.md").write_text(prompt, encoding="utf-8")


def _build_query_prompt(input_data: KnowledgeQueryInput) -> str:
    schema_hint = {
        "answer": "Markdown 答案。",
        "source_refs": [
            {
                "source_type": "requirement",
                "source_id": "version-id",
                "source_title": "需求 v1",
                "location": "章节或模块",
                "excerpt": "短摘录",
            }
        ],
        "used_requirement_versions": ["version-id"],
        "used_exploration_runs": ["run-id"],
    }
    return "\n".join(
        [
            "你是 AI 测试系统的项目知识库问答智能体。",
            "这是一次非交互式查询任务；必须直接读取 input/ 下的最终需求文档和探索记录回答用户问题。",
            "可以使用 Codex CLI 的 agentic search 能力定位、比对和归纳输入文件；项目事实只能来自 input/，不得把外部搜索结果写成项目事实。",
            "不要创建离线知识库产物，不要写 wiki 页面，不要修改 input/，只允许写 output/query.json 与 output/answer.md。",
            "",
            "回答要求：",
            "- 使用中文 Markdown 直接回答用户问题。",
            "- 结论必须基于最终需求文档或已完成/部分完成探索记录。",
            "- 涉及业务事实、页面事实、测试关注点时，必须在 source_refs 中提供来源引用。",
            "- 如果来源不足，明确说明缺口，不要假装已确认。",
            "- 如果需求和探索冲突，单独列出冲突点和各自来源。",
            "",
            "输入文件：",
            "- input/knowledge-query-input.json：完整结构化输入和用户问题。",
            "- input/requirements/*.md：项目最终需求文档版本。",
            "- input/explorations.json：项目探索记录。",
            "",
            "输出要求：",
            "- 必须生成 output/query.json，内容符合 KnowledgeQueryOutput。",
            "- 必须生成 output/answer.md，内容与 answer 字段一致。",
            "",
            "最小 JSON 结构示例：",
            json.dumps(schema_hint, ensure_ascii=False),
            "",
            f"项目：{input_data.project_name} ({input_data.project_id})",
            f"需求版本数量：{len(input_data.source_documents)}",
            f"探索结果数量：{len(input_data.explorations)}",
            "",
            "最近对话上下文：",
            _format_conversation_history(input_data),
            "",
            "用户问题：",
            input_data.question.strip(),
        ]
    )


def _format_conversation_history(input_data: KnowledgeQueryInput) -> str:
    if not input_data.conversation_history:
        return "无。"
    lines: list[str] = []
    for message in input_data.conversation_history:
        role = "用户" if message.role == "user" else "项目知识库 AI"
        content = message.content.strip()
        if len(content) > 1200:
            content = f"{content[:1200]}..."
        lines.append(f"{role}：{content}")
    return "\n".join(lines)


def _codex_command(workdir: Path, selection, prompt: str) -> list[str]:
    return [
        _codex_command_path(),
        "--search",
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


def _codex_command_path() -> str:
    configured = KNOWLEDGE_QUERY_CODEX_COMMAND.strip()
    if not configured:
        raise RuntimeError("知识库查询智能体执行命令未配置，请设置 AI_TESTING_KNOWLEDGE_QUERY_CODEX_COMMAND。")
    expanded = os.path.expanduser(configured)
    configured_path = PurePath(expanded)
    if configured_path.is_absolute() or configured_path.parent != PurePath("."):
        if os.path.exists(expanded):
            return expanded
        raise RuntimeError(f"知识库查询智能体执行命令不存在：{configured}")
    resolved = shutil.which(configured)
    if resolved:
        return resolved
    if os.name == "nt" and not configured.lower().endswith((".cmd", ".bat", ".exe")):
        for suffix in (".cmd", ".bat", ".exe"):
            resolved = shutil.which(f"{configured}{suffix}")
            if resolved:
                return resolved
    raise RuntimeError("未检测到可用知识库查询智能体执行命令。")


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
        raise RuntimeError(f"知识库查询智能体启动失败：{error}") from error
    stdout_queue: queue.Queue[str | None] = queue.Queue()
    stdout_lines: list[str] = []
    reader = threading.Thread(target=_enqueue_output_lines, args=(process.stdout, stdout_queue), daemon=True)
    reader.start()
    started_at = time.monotonic()
    while process.poll() is None:
        _drain_codex_stdout(workdir, stdout_queue, stdout_lines)
        if time.monotonic() - started_at > KNOWLEDGE_QUERY_CODEX_TIMEOUT_SECONDS:
            process.kill()
            process.wait()
            reader.join(timeout=1)
            stderr = process.stderr.read() if process.stderr else ""
            raise TimeoutError(f"知识库查询智能体执行超时：{stderr.strip()}")
        time.sleep(0.1)
    reader.join(timeout=1)
    _drain_codex_stdout(workdir, stdout_queue, stdout_lines)
    stderr = process.stderr.read() if process.stderr else ""
    if process.returncode != 0:
        (workdir / "logs" / "codex-stderr.log").write_text(stderr, encoding="utf-8")
        raise RuntimeError(f"知识库查询智能体执行失败，退出码：{process.returncode}。{stderr.strip()}")


def _enqueue_output_lines(stream, output_queue: queue.Queue[str | None]) -> None:
    if stream is None:
        output_queue.put(None)
        return
    for line in stream:
        output_queue.put(line)
    output_queue.put(None)


def _drain_codex_stdout(workdir: Path, output_queue: queue.Queue[str | None], stdout_lines: list[str]) -> None:
    while True:
        try:
            line = output_queue.get_nowait()
        except queue.Empty:
            break
        if line is None:
            continue
        stdout_lines.append(line)
    if stdout_lines:
        (workdir / "logs" / "codex-stdout.jsonl").write_text("".join(stdout_lines), encoding="utf-8")


def _read_query_output(workdir: Path) -> KnowledgeQueryOutput:
    output_path = workdir / "output" / "query.json"
    if not output_path.exists():
        raise ValueError("知识库查询智能体未生成 output/query.json。")
    try:
        return KnowledgeQueryOutput.model_validate_json(output_path.read_text(encoding="utf-8"))
    except Exception as error:
        raise ValueError(f"知识库查询智能体输出格式不正确：{error}") from error


def _safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_." else "-" for char in value.strip())
    return cleaned[:80] or "document"
