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
    return "\n".join(
        [
            "你是 AI 测试系统的需求分析智能体。",
            "只能读取当前工作目录 input/ 和 skills/ 下的文件，不要扫描其他目录。",
            "这是一次非交互式批处理任务；必须立即读取输入、完成分析并写入输出文件。",
            "不要只回复确认、承诺或后续会处理；最终回答可以简短，但落盘文件必须先生成。",
            "",
            "请按以下固定流程执行，不要跳步：",
            "使用 requirement-review skill 对 input/primary.md 做需求分析，生成待确认问题。",
            "必须包含测试覆盖缺口视角：从测试目标、角色、前置条件、操作步骤、预期结果、边界值、异常路径和错误场景缺口反推模块、规则、边界和待确认问题。",
            "本阶段只分析主需求，不读取、不引用、不推测任何辅助文档。",
            "辅助文档增强由后续 RequirementAuxiliaryEnhancementAgent 处理，本阶段不得代替它回答待确认问题。",
            "",
            "输出要求：",
            "- 必须生成 output/analysis.json，内容必须符合 RequirementAnalysisOutput。",
            "- 必须生成 output/analysis.md，作为待确认需求 tab 后面的分析报告 tab 展示内容。",
            "- analysis.json.analysis_report_markdown 必须等于 output/analysis.md 的正文。",
            "- 分析报告只写分析摘要、成熟度、关键缺口分类、测试覆盖缺口、质量门禁和下一步建议。",
            "- 分析报告不要出现“待确认问题”“待人工确认”“澄清问题”等面向人工答复的章节、标题、统计或问题清单。",
            "- 分析报告中的关键缺口只做归类和影响说明，不要写成可答复的问题清单。",
            "- 分析报告中的测试覆盖缺口只说明测试覆盖影响，不要展开具体待人工答复事项。",
            "- 分析报告不要重复、统计或摘要 clarification_questions/conflicts；这些内容只进入结构化字段。",
            "- 需要人工回答或裁决的内容必须进入 clarification_questions/conflicts，由待确认问题 tab 展示。",
            "- preliminary_requirement_markdown 可为空字符串；如果为空，系统会使用主需求原文作为初步需求。",
            "- applied_supplements 必须为空数组。",
            "- clarification_questions/conflicts 保留主需求自身无法确认或存在冲突的条目。",
            "- question 必须直接写要人工确认的问题，不要拆成“当前缺口”“缺失说明”等解释段。",
            "- recommended_options.answer_markdown 必须是可直接写入初步需求的答案。",
            "- status 只能是 completed、needs_clarification、blocked；不要输出 CONDITIONAL_PASS、PASSED、FAILED 等评审结论。",
            "- 评审结论写入 quality_gate.result，只能是 passed、warning、blocked。",
            "- coverage_audit 必须是数组，不要输出 covered/partial/missing 字典。",
            "- clarification_questions/conflicts 必须使用 module_key、module_name、question、impact、severity 等结构化字段。",
            "",
            "输入文件：",
            "- 主需求：input/primary.md",
            "- skill：skills/requirement-review/SKILL.md",
            "",
            "RequirementAnalysisOutput 字段提醒：",
            "status, analysis_summary, preliminary_requirement_markdown, analysis_report_markdown, applied_supplements,",
            "maturity_assessment, key_gaps, assumptions, modules, clarification_questions, conflicts, coverage_audit, quality_gate, next_actions",
            "",
            "最小 JSON 结构示例：",
            json.dumps(
                {
                    "status": "needs_clarification",
                    "analysis_summary": "需求分析摘要。",
                    "preliminary_requirement_markdown": "# 初步需求",
                    "analysis_report_markdown": "# 分析报告",
                    "applied_supplements": [],
                    "maturity_assessment": {
                        "level": "RA2",
                        "label": "部分可测试",
                        "reason": "核心流程明确但仍有待确认项。",
                        "evidence": ["已有主流程描述。"],
                    },
                    "key_gaps": [
                        {
                            "category": "scope",
                            "description": "缺口描述。",
                            "impact": "影响说明。",
                            "severity": "major",
                        }
                    ],
                    "assumptions": [
                        {
                            "description": "分析假设。",
                            "validation_needed": "需要确认的内容。",
                            "risk": "假设错误的风险。",
                        }
                    ],
                    "modules": [
                        {
                            "module_key": "login",
                            "module_name": "登录",
                            "summary": "模块摘要。",
                            "rules": ["业务规则。"],
                            "risks": ["风险。"],
                        }
                    ],
                    "clarification_questions": [
                        {
                            "id": "CQ-001",
                            "module_key": "login",
                            "module_name": "登录",
                            "question": "需要确认什么？",
                            "impact": "不确认的影响。",
                            "dimension": "scope",
                            "severity": "major",
                            "recommended_options": [
                                {
                                    "id": "OPT-001",
                                    "label": "选项",
                                    "answer_markdown": "可写入需求的答案。",
                                    "confidence": "medium",
                                }
                            ],
                        }
                    ],
                    "conflicts": [],
                    "coverage_audit": [
                        {
                            "module_key": "login",
                            "module_name": "登录",
                            "source_excerpt": "来源摘录。",
                            "analysis_status": "pending_clarification",
                            "reason": "仍需确认。",
                        }
                    ],
                    "quality_gate": {
                        "result": "warning",
                        "testability_score": 70,
                        "blocking_issues": [],
                        "warning_issues": ["存在待确认项。"],
                        "passed_checks": ["主流程已识别。"],
                    },
                    "next_actions": ["下一步动作。"],
                },
                ensure_ascii=False,
            ),
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
    (root / "input").mkdir(parents=True, exist_ok=True)
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
    (workdir / "prompt.md").write_text(prompt, encoding="utf-8")
    _copy_skill("requirement-review", workdir / "skills" / "requirement-review")


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
    raw_output = json.loads(output_path.read_text(encoding="utf-8"))
    normalized_output = _normalize_analysis_output(raw_output)
    output = RequirementAnalysisOutput.model_validate(normalized_output)
    report_path = workdir / "output" / "analysis.md"
    if report_path.exists():
        report = report_path.read_text(encoding="utf-8").strip()
        if report:
            output.analysis_report_markdown = report
    return output


def _normalize_analysis_output(value: dict) -> dict:
    output = dict(value)
    raw_status = output.get("status")
    output["status"] = _normalize_analysis_status(output.get("status"), output.get("quality_gate"), output.get("clarification_questions"))
    output["quality_gate"] = _normalize_quality_gate(output.get("quality_gate"), raw_status)
    output["applied_supplements"] = []
    output["maturity_assessment"] = _normalize_maturity_assessment(output.get("maturity_assessment"))
    output["key_gaps"] = _normalize_key_gaps(output.get("key_gaps"))
    output["assumptions"] = _normalize_assumptions(output.get("assumptions"))
    output["modules"] = _normalize_modules(output.get("modules"))
    output["clarification_questions"] = _normalize_findings(output.get("clarification_questions"), default_issue_type="clarification")
    output["conflicts"] = _normalize_findings(output.get("conflicts"), default_issue_type="conflict")
    output["coverage_audit"] = _normalize_coverage_audit(output.get("coverage_audit"))
    output["next_actions"] = _normalize_string_list(output.get("next_actions"))
    return output


def _normalize_analysis_status(value, quality_gate, clarification_questions) -> str:
    if value in {"completed", "needs_clarification", "blocked"}:
        return value
    gate_result = quality_gate.get("result") if isinstance(quality_gate, dict) else None
    if gate_result == "blocked" or value in {"BLOCKED", "FAILED", "FAIL"}:
        return "blocked"
    if clarification_questions:
        return "needs_clarification"
    if value in {"CONDITIONAL_PASS", "WARNING", "WARN"}:
        return "needs_clarification"
    return "completed"


def _normalize_quality_gate(value, raw_status) -> dict:
    gate = dict(value) if isinstance(value, dict) else {}
    result = gate.get("result")
    if result not in {"passed", "warning", "blocked"}:
        decision = str(gate.get("decision") or raw_status or "").lower()
        blocking_items = gate.get("blocking_items") or gate.get("blocking_issues") or []
        if "blocked" in decision or "阻塞" in decision:
            result = "blocked"
        elif "conditional" in decision or "有条件" in decision or blocking_items or gate.get("pass") is False:
            result = "warning"
        else:
            result = "passed"
    return {
        "result": result,
        "testability_score": _bounded_int(gate.get("testability_score") or gate.get("score") or 0, 0, 100),
        "blocking_issues": _normalize_string_list(gate.get("blocking_issues") or gate.get("blocking_items")),
        "warning_issues": _normalize_string_list(gate.get("warning_issues") or gate.get("non_blocking_items")),
        "passed_checks": _normalize_string_list(gate.get("passed_checks")),
    }


def _normalize_maturity_assessment(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        return {"level": "RA2", "label": str(value), "reason": str(value), "evidence": []}
    level = value.get("level")
    if level not in {"RA0", "RA1", "RA2", "RA3", "RA4", "RA5"}:
        level = "RA2"
    label = value.get("label") or value.get("overall_level") or level
    evidence = value.get("evidence")
    if not evidence and isinstance(value.get("dimensions"), list):
        evidence = [f"{item.get('name', '维度')}：{item.get('notes', '')}" for item in value["dimensions"] if isinstance(item, dict)]
    return {"level": level, "label": str(label), "reason": str(value.get("reason") or label), "evidence": _normalize_string_list(evidence)}


def _normalize_key_gaps(value) -> list[dict]:
    items = value if isinstance(value, list) else ([value] if value else [])
    normalized = []
    for item in items:
        if isinstance(item, dict):
            category = item.get("category")
            normalized.append(
                {
                    "category": category if category in _GAP_CATEGORIES else "other",
                    "description": str(item.get("description") or item.get("gap") or item),
                    "impact": str(item.get("impact") or "影响后续设计、开发或测试确认。"),
                    "severity": item.get("severity") if item.get("severity") in {"blocker", "major", "minor"} else "major",
                }
            )
        else:
            normalized.append({"category": "other", "description": str(item), "impact": "影响后续设计、开发或测试确认。", "severity": "major"})
    return normalized


def _normalize_assumptions(value) -> list[dict]:
    items = value if isinstance(value, list) else ([value] if value else [])
    normalized = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(
                {
                    "description": str(item.get("description") or item.get("assumption") or item),
                    "validation_needed": str(item.get("validation_needed") or "需要业务负责人确认。"),
                    "risk": str(item.get("risk") or "假设不成立会影响需求分析结论。"),
                }
            )
        else:
            normalized.append({"description": str(item), "validation_needed": "需要业务负责人确认。", "risk": "假设不成立会影响需求分析结论。"})
    return normalized


def _normalize_modules(value) -> list[dict]:
    items = value if isinstance(value, list) else ([value] if value else [])
    normalized = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            item = {"module_name": str(item), "summary": str(item)}
        module_name = str(item.get("module_name") or item.get("name") or f"模块 {index}")
        normalized.append(
            {
                "module_key": str(item.get("module_key") or _slug(module_name) or f"module-{index:03d}"),
                "module_name": module_name,
                "summary": str(item.get("summary") or item.get("scope") or module_name),
                "business_objects": _normalize_string_list(item.get("business_objects")),
                "capabilities": _normalize_string_list(item.get("capabilities")),
                "rules": _normalize_string_list(item.get("rules")),
                "fields": _normalize_string_list(item.get("fields")),
                "state_flows": _normalize_string_list(item.get("state_flows")),
                "dependencies": _normalize_string_list(item.get("dependencies")),
                "risks": _normalize_string_list(item.get("risks") or item.get("open_points")),
            }
        )
    return normalized


def _normalize_findings(value, *, default_issue_type: str) -> list[dict]:
    items = value if isinstance(value, list) else ([value] if value else [])
    normalized = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            item = {"question": str(item)}
        question = str(item.get("question") or item.get("resolution_needed") or item.get("description") or item.get("topic") or "需要人工确认。")
        module_name = str(item.get("module_name") or item.get("topic") or "通用")
        is_conflict = default_issue_type == "conflict"
        issue_type = item.get("issue_type") or default_issue_type
        normalized_item = {
            "id": str(item.get("id") or f"{'CF' if is_conflict else 'CQ'}-{index:03d}"),
            "module_key": str(item.get("module_key") or _slug(module_name) or "general"),
            "module_name": module_name,
            "question": question,
            "impact": str(item.get("impact") or "不确认会影响后续设计、开发、测试或验收判断。"),
            "severity": _normalize_severity(item.get("severity") or item.get("priority")),
            "evidence": _normalize_evidence_list(item),
            "recommended_options": _normalize_options(item.get("recommended_options")),
        }
        excerpt = str(item.get("primary_excerpt") or item.get("source_excerpt") or item.get("description") or "")
        if is_conflict:
            normalized_item["issue_type"] = issue_type if issue_type in _ISSUE_TYPES else default_issue_type
            normalized_item["primary_excerpt"] = excerpt
        else:
            normalized_item["dimension"] = item["dimension"] if item.get("dimension") in _DIMENSIONS else "other"
            normalized_item["source_excerpt"] = excerpt
        normalized.append(normalized_item)
    return normalized


def _normalize_coverage_audit(value) -> list[dict]:
    if isinstance(value, dict):
        items = []
        for status_key, entries in value.items():
            analysis_status = {"covered": "analyzed", "partial": "missing_detail", "missing": "pending_clarification"}.get(status_key, "missing_detail")
            for entry in _normalize_string_list(entries):
                items.append(
                    {
                        "module_key": _slug(entry) or "general",
                        "module_name": entry,
                        "source_excerpt": entry,
                        "analysis_status": analysis_status,
                        "reason": entry,
                    }
                )
        return items
    items = value if isinstance(value, list) else []
    normalized = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            item = {"module_name": str(item), "reason": str(item)}
        status = item.get("analysis_status")
        normalized.append(
            {
                "module_key": str(item.get("module_key") or _slug(item.get("module_name") or item.get("reason") or "") or f"coverage-{index:03d}"),
                "module_name": str(item.get("module_name") or item.get("reason") or f"覆盖项 {index}"),
                "source_excerpt": str(item.get("source_excerpt") or item.get("reason") or ""),
                "analysis_status": status if status in _COVERAGE_STATUSES else "missing_detail",
                "reason": str(item.get("reason") or item.get("source_excerpt") or ""),
            }
        )
    return normalized


def _normalize_options(value) -> list[dict]:
    items = value if isinstance(value, list) else []
    normalized = []
    for index, item in enumerate(items[:2], start=1):
        if not isinstance(item, dict):
            item = {"label": str(item), "answer_markdown": str(item)}
        normalized.append(
            {
                "id": str(item.get("id") or f"OPT-{index:03d}"),
                "label": str(item.get("label") or f"选项 {index}"),
                "answer_markdown": str(item.get("answer_markdown") or item.get("answer") or ""),
                "rationale": str(item.get("rationale") or ""),
                "confidence": item.get("confidence") if item.get("confidence") in {"high", "medium", "low"} else "medium",
            }
        )
    return normalized


def _normalize_evidence_list(item: dict) -> list[dict]:
    evidence = item.get("evidence")
    if isinstance(evidence, list):
        return [_normalize_evidence(entry, item) for entry in evidence]
    if evidence or item.get("sources"):
        return [_normalize_evidence(evidence, item)]
    return []


def _normalize_evidence(value, fallback: dict) -> dict:
    if isinstance(value, dict):
        source_file = value.get("filename") or value.get("source_file") or fallback.get("source_file") or ""
        return {
            "mapping_id": str(value.get("mapping_id") or fallback.get("mapping_id") or _mapping_id_from_source(source_file)),
            "filename": str(source_file or "unknown"),
            "excerpt": str(value.get("excerpt") or value.get("evidence") or fallback.get("evidence") or ""),
            "section_hint": str(value.get("section_hint") or value.get("section") or ""),
        }
    source = fallback.get("source_file")
    sources = fallback.get("sources")
    if not source and isinstance(sources, list) and sources:
        source = sources[-1]
    return {
        "mapping_id": str(fallback.get("mapping_id") or _mapping_id_from_source(str(source or ""))),
        "filename": str(source or "unknown"),
        "excerpt": str(value or fallback.get("evidence") or fallback.get("description") or ""),
        "section_hint": "",
    }


def _mapping_id_from_source(value: str) -> str:
    filename = Path(value).name
    if filename.startswith(("001-", "002-", "003-")):
        parts = filename.split("-", 2)
        if len(parts) >= 2:
            return parts[1]
    return Path(filename).stem or "unknown"


def _normalize_string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def _normalize_severity(value) -> str:
    normalized = str(value or "").lower()
    if normalized in {"blocker", "major", "minor"}:
        return normalized
    if normalized in {"high", "critical", "p0", "p1"}:
        return "blocker"
    if normalized in {"low", "p3"}:
        return "minor"
    return "major"


def _bounded_int(value, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _slug(value) -> str:
    return str(value or "").strip().lower().replace(" ", "_")[:60]


_GAP_CATEGORIES = {
    "problem_statement",
    "stakeholder",
    "scope",
    "business_rule",
    "acceptance_criteria",
    "data",
    "permission",
    "integration",
    "non_functional",
    "constraint",
    "other",
}
_ISSUE_TYPES = {"conflict", "out_of_scope", "weak_evidence", "source_unclear", "other"}
_DIMENSIONS = {
    "boundary_value",
    "exception_path",
    "state_flow",
    "permission",
    "data_dependency",
    "message",
    "validation_rule",
    "concurrency",
    "time_related",
    "data_consistency",
    "scope",
    "other",
}
_COVERAGE_STATUSES = {"analyzed", "pending_clarification", "not_testable", "missing_detail"}
