import json
import secrets
from pathlib import Path

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.requirement_analysis.agent import requirement_analysis_agent
from app.agents.requirement_analysis.schemas import (
    AuxiliaryRequirementDocument,
    RequirementAnalysisAgentInput,
    RequirementAnalysisAgentOutput,
    RequirementAnalysisRunInput,
    RequirementAnalysisRunOutput,
)
from app.core.db import connect
from app.core.storage import project_requirement_dir, resolve_stored_path, store_path
from app.repositories import document_repo, requirement_analysis_run_repo


CAPABILITY_ID = "requirement_analysis"


async def run_requirement_analysis(input_data: RequirementAnalysisRunInput) -> RequirementAnalysisRunOutput:
    agent_input, run_context = _load_run_input(input_data.run_id)
    output = await analyze_requirement(agent_input)
    artifact_paths = _write_artifacts(run_context, output)
    return RequirementAnalysisRunOutput(
        status=output.status,
        understanding_markdown=output.understanding_markdown,
        clarification_markdown=output.clarification_markdown,
        clarification_items=output.clarification_items,
        artifact_paths=artifact_paths,
    )


async def analyze_requirement(input_data: RequirementAnalysisAgentInput) -> RequirementAnalysisAgentOutput:
    if not input_data.primary_markdown_content.strip():
        raise ValueError("主需求 Markdown 为空，无法分析。")

    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    agent = requirement_analysis_agent(model)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": _build_agent_input(input_data),
                }
            ]
        }
    )
    output = result.get("structured_response")
    if output is None:
        raise ValueError("需求分析智能体未返回结构化结果。")
    if not output.understanding_markdown.strip():
        raise ValueError("需求分析智能体返回的需求理解文档为空。")
    if not output.clarification_markdown.strip():
        raise ValueError("需求分析智能体返回的待澄清文档为空。")
    return output


def _load_run_input(run_id: str) -> tuple[RequirementAnalysisAgentInput, dict]:
    with connect() as db:
        run = requirement_analysis_run_repo.find_run(db, run_id)
        if not run:
            raise ValueError("需求分析任务不存在。")
        document = document_repo.find_by_project_and_id(db, run["project_id"], run["document_id"])
        if not document:
            raise ValueError("需求文档不存在。")
        primary_file = document_repo.find_file_mapping(db, run["primary_mapping_id"]) if run["primary_mapping_id"] else None
        if not primary_file:
            primary_file = document_repo.find_primary_file_mapping(db, run["document_id"])
        if not primary_file:
            raise ValueError("请先选择主需求文件后再进行需求分析。")
        if primary_file["conversion_status"] not in {"success", "warning"} or not primary_file["markdown_file_path"]:
            raise ValueError("请先完成主需求标准文件转换后再进行需求分析。")

        primary_markdown = _read_markdown_file(primary_file["markdown_file_path"], "主需求标准文件不存在。")
        auxiliary_documents = []
        for row in document_repo.list_file_mappings(db, run["document_id"]):
            if row["id"] == primary_file["id"]:
                continue
            if row["conversion_status"] not in {"success", "warning"} or not row["markdown_file_path"]:
                continue
            auxiliary_documents.append(
                AuxiliaryRequirementDocument(
                    filename=row["original_filename"],
                    markdown_content=_read_markdown_file(row["markdown_file_path"], "辅助需求标准文件不存在。"),
                )
            )

    return (
        RequirementAnalysisAgentInput(
            requirement_name=document["name"],
            primary_filename=primary_file["original_filename"],
            primary_markdown_content=primary_markdown,
            auxiliary_documents=auxiliary_documents,
        ),
        {
            "run_id": run_id,
            "project_id": run["project_id"],
            "document_id": run["document_id"],
        },
    )


def _read_markdown_file(path_value: str, missing_message: str) -> str:
    markdown_path = resolve_stored_path(path_value) or Path(path_value)
    if not markdown_path.exists():
        raise ValueError(missing_message)
    return markdown_path.read_text(encoding="utf-8")


def _write_artifacts(run_context: dict, output: RequirementAnalysisAgentOutput) -> dict[str, str]:
    run_dir = (
        project_requirement_dir(run_context["project_id"], run_context["document_id"])
        / "analysis_runs"
        / run_context["run_id"]
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    understanding_path = run_dir / "understanding.md"
    clarification_path = run_dir / "clarifications.md"
    result_path = run_dir / "result.json"
    understanding_path.write_text(output.understanding_markdown.rstrip() + "\n", encoding="utf-8")
    clarification_path.write_text(output.clarification_markdown.rstrip() + "\n", encoding="utf-8")
    result_path.write_text(output.model_dump_json(indent=2), encoding="utf-8")
    return {
        "understanding": store_path(understanding_path) or str(understanding_path),
        "clarification": store_path(clarification_path) or str(clarification_path),
        "result": store_path(result_path) or str(result_path),
    }


def _build_agent_input(input_data: RequirementAnalysisAgentInput) -> str:
    auxiliary_payload = [
        {
            "filename": item.filename,
            "markdown_content": item.markdown_content,
        }
        for item in input_data.auxiliary_documents
    ]
    return "\n".join(
        [
            f"需求名称: {input_data.requirement_name}",
            f"主需求文件: {input_data.primary_filename}",
            "",
            "主需求 Markdown:",
            input_data.primary_markdown_content,
            "",
            "辅助需求 Markdown 列表:",
            json.dumps(auxiliary_payload, ensure_ascii=False, indent=2),
            "",
            "请使用 requirements-analysis skill 生成需求理解文档和待澄清文档，并返回结构化 JSON。",
            "clarification item id 请使用 clar-001、clar-002 这样的稳定格式。",
        ]
    )


def build_requirement_analysis_output_json(output: RequirementAnalysisRunOutput) -> dict:
    return {
        "status": output.status,
        "summary": "需求分析完成" if output.status == "completed" else f"发现 {len(output.clarification_items)} 个待澄清问题",
        "understanding_markdown": output.understanding_markdown,
        "clarification_markdown": output.clarification_markdown,
        "clarification_items": [item.model_dump() for item in output.clarification_items],
        "artifacts": output.artifact_paths,
    }


def next_analysis_id() -> str:
    return f"reqana-{secrets.token_hex(8)}"


__all__ = [
    "analyze_requirement",
    "build_requirement_analysis_output_json",
    "next_analysis_id",
    "run_requirement_analysis",
]
