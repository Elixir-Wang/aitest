import asyncio
import json
import os
import shutil
from pathlib import Path

from app.agents.model_selection import resolve_model_selection
from app.agents.requirement_analysis_codex import codex_cli
from app.agents.requirement_analysis_codex.codex_cli import (
    CODEX_MODEL_PROVIDER,
    codex_env,
    drain_codex_stdout,
    enqueue_output_lines,
    run_codex_process,
    write_process_logs,
)
from app.agents.requirement_analysis_codex.output_parser import (
    bounded_int,
    mapping_id_from_source,
    normalize_analysis_output,
    normalize_analysis_status,
    normalize_assumptions,
    normalize_coverage_audit,
    normalize_evidence,
    normalize_evidence_list,
    normalize_findings,
    normalize_key_gaps,
    normalize_maturity_assessment,
    normalize_modules,
    normalize_options,
    normalize_quality_gate,
    normalize_severity,
    normalize_string_list,
    read_analysis_output,
    slug,
)
from app.agents.requirement_analysis_codex.prompt import build_codex_prompt
from app.agents.requirement_analysis_codex.schemas import RequirementAnalysisInput, RequirementAnalysisOutput
from app.agents.requirement_analysis_codex.workspace import copy_skill, prepare_workdir, write_inputs
from app.core.settings import REQUIREMENT_ANALYSIS_CODEX_COMMAND


CAPABILITY_ID = "requirement_analysis"


async def run_requirement_analysis_with_codex(input_data: RequirementAnalysisInput) -> RequirementAnalysisOutput:
    output = await asyncio.to_thread(_run_codex_requirement_analysis, input_data)
    if not output.preliminary_requirement_markdown.strip():
        output.preliminary_requirement_markdown = input_data.primary_markdown_content.strip()
    return output


def _run_codex_requirement_analysis(input_data: RequirementAnalysisInput) -> RequirementAnalysisOutput:
    from app.agents.requirement_analysis_codex.errors import RequirementAnalysisCancelledError
    from app.agents.requirement_analysis_codex.process_registry import cancel_requested

    run_id = input_data.run_id.strip()
    if run_id and cancel_requested(run_id):
        raise RequirementAnalysisCancelledError("用户已停止需求分析。")

    workdir = _prepare_workdir(input_data)
    if run_id and cancel_requested(run_id):
        raise RequirementAnalysisCancelledError("用户已停止需求分析。")
    prompt = _build_codex_prompt(input_data)
    _write_inputs(workdir, input_data, prompt)
    selection = resolve_model_selection(CAPABILITY_ID)
    command = _codex_command(workdir, selection, prompt)
    env = _codex_env(selection, workdir)
    _run_codex_process(command, workdir, env, run_id=input_data.run_id.strip())
    return _read_analysis_output(workdir)


_build_codex_prompt = build_codex_prompt
_prepare_workdir = prepare_workdir
_write_inputs = write_inputs
_copy_skill = copy_skill
def _codex_command(workdir: Path, selection, prompt: str) -> list[str]:
    codex_command_path = _codex_command_path()
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


def _codex_command_path() -> str:
    codex_cli.REQUIREMENT_ANALYSIS_CODEX_COMMAND = REQUIREMENT_ANALYSIS_CODEX_COMMAND
    return codex_cli.resolve_codex_command_path()


_codex_env = codex_env
_run_codex_process = run_codex_process
_enqueue_output_lines = enqueue_output_lines
_drain_codex_stdout = drain_codex_stdout
_write_process_logs = write_process_logs
_read_analysis_output = read_analysis_output
_normalize_analysis_output = normalize_analysis_output
_normalize_analysis_status = normalize_analysis_status
_normalize_quality_gate = normalize_quality_gate
_normalize_maturity_assessment = normalize_maturity_assessment
_normalize_key_gaps = normalize_key_gaps
_normalize_assumptions = normalize_assumptions
_normalize_modules = normalize_modules
_normalize_findings = normalize_findings
_normalize_coverage_audit = normalize_coverage_audit
_normalize_options = normalize_options
_normalize_evidence_list = normalize_evidence_list
_normalize_evidence = normalize_evidence
_mapping_id_from_source = mapping_id_from_source
_normalize_string_list = normalize_string_list
_normalize_severity = normalize_severity
_bounded_int = bounded_int
_slug = slug
