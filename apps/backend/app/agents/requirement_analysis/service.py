"""需求分析服务层"""

import json
import secrets
from pathlib import Path

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.requirement_analysis.agent import requirement_analysis_agent
from app.agents.requirement_analysis.schemas import (
    AuxiliaryRequirementDocument,
    ClarificationItem,
    RequirementAnalysisAgentInput,
    RequirementAnalysisAgentOutput,
    RequirementAnalysisResult,
    RequirementAnalysisRunInput,
    RequirementAnalysisRunOutput,
    RequirementClarificationItem,
    RequirementInput,
)
from app.core.db import connect
from app.core.storage import project_requirement_dir, resolve_stored_path, store_path
from app.repositories import document_repo, requirement_analysis_run_repo


CAPABILITY_ID = "requirement_analysis"


# ==================== 新的核心函数 ====================

async def analyze_requirement(input_data: RequirementInput) -> RequirementAnalysisResult:
    """
    需求分析核心函数（新架构）

    Args:
        input_data: 需求输入

    Returns:
        需求分析结果（包含理解和澄清）

    Raises:
        ValueError: 主需求内容为空或 Agent 未返回结构化结果
    """
    # 验证输入
    if not input_data.requirement_content.strip():
        raise ValueError("主需求内容为空，无法分析。")

    # 构建输入内容
    content_parts = [
        f"需求名称: {input_data.requirement_name}",
        "",
        "主需求内容:",
        input_data.requirement_content,
    ]

    # 添加辅助文档
    if input_data.auxiliary_docs:
        content_parts.append("\n辅助文档:")
        for i, doc in enumerate(input_data.auxiliary_docs, 1):
            content_parts.append(f"\n--- 辅助文档 {i} ---")
            content_parts.append(doc)

    content_parts.append("\n请使用 requirements-analysis skill 分析该需求。")
    content = "\n".join(content_parts)

    # 调用 Agent
    model = build_agent_model(resolve_model_selection(CAPABILITY_ID))
    agent = requirement_analysis_agent(model)

    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": content}]
    })

    # 提取结构化输出
    if not isinstance(result, dict):
        raise ValueError("需求分析智能体输出格式不正确。")

    analysis_result = result.get("structured_response")

    if not analysis_result:
        raise ValueError("需求分析智能体未返回结构化结果。")

    # 处理多种返回类型
    if isinstance(analysis_result, RequirementAnalysisResult):
        return analysis_result
    elif isinstance(analysis_result, dict):
        return RequirementAnalysisResult.model_validate(analysis_result)
    elif isinstance(analysis_result, str):
        return RequirementAnalysisResult.model_validate_json(analysis_result)
    else:
        raise ValueError(f"需求分析智能体输出类型不支持: {type(analysis_result).__name__}")


# ==================== 格式转换函数 ====================

def convert_old_input_to_new(old_input: RequirementAnalysisAgentInput) -> RequirementInput:
    """将旧的输入格式转换为新格式"""
    return RequirementInput(
        requirement_name=old_input.requirement_name,
        requirement_content=old_input.primary_markdown_content,
        auxiliary_docs=[doc.markdown_content for doc in old_input.auxiliary_documents],
    )


def convert_new_output_to_old(new_result: RequirementAnalysisResult) -> RequirementAnalysisAgentOutput:
    """将新的输出格式转换为旧格式"""
    return RequirementAnalysisAgentOutput(
        status=new_result.status,
        understanding_markdown=new_result.to_understanding_markdown(),
        clarification_markdown=new_result.to_clarification_markdown(),
        clarification_items=[
            RequirementClarificationItem(
                id=item.id,
                priority=item.priority,
                module=item.module,
                question=item.question,
                option_a=item.option_a,
                option_b=item.option_b,
                source_excerpt=item.source_excerpt,
                impact=item.impact,
            )
            for item in new_result.clarifications
        ],
    )


# ==================== 旧接口兼容函数 ====================

async def analyze_requirement_legacy(input_data: RequirementAnalysisAgentInput) -> RequirementAnalysisAgentOutput:
    """
    需求分析（旧接口兼容）

    内部使用新架构，对外保持旧接口
    """
    if not input_data.primary_markdown_content.strip():
        raise ValueError("主需求 Markdown 为空，无法分析。")

    # 转换为新格式
    new_input = convert_old_input_to_new(input_data)

    # 使用新架构分析
    new_result = await analyze_requirement(new_input)

    # 转换回旧格式
    return convert_new_output_to_old(new_result)


async def run_requirement_analysis(input_data: RequirementAnalysisRunInput) -> RequirementAnalysisRunOutput:
    """运行需求分析（旧接口兼容）"""
    agent_input, run_context = _load_run_input(input_data.run_id)
    output = await analyze_requirement_legacy(agent_input)
    artifact_paths = _write_artifacts(run_context, output)
    return RequirementAnalysisRunOutput(
        status=output.status,
        understanding_markdown=output.understanding_markdown,
        clarification_markdown=output.clarification_markdown,
        clarification_items=output.clarification_items,
        artifact_paths=artifact_paths,
    )


# ==================== 辅助函数（保持不变）====================

def _load_run_input(run_id: str) -> tuple[RequirementAnalysisAgentInput, dict]:
    """加载运行输入数据"""
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
    """读取 Markdown 文件"""
    markdown_path = resolve_stored_path(path_value) or Path(path_value)
    if not markdown_path.exists():
        raise ValueError(missing_message)
    return markdown_path.read_text(encoding="utf-8")


def _write_artifacts(run_context: dict, output: RequirementAnalysisAgentOutput) -> dict[str, str]:
    """写入产物文件"""
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


def build_requirement_analysis_output_json(output: RequirementAnalysisRunOutput) -> dict:
    """构建需求分析输出 JSON"""
    return {
        "status": output.status,
        "summary": "需求分析完成" if output.status == "completed" else f"发现 {len(output.clarification_items)} 个待澄清问题",
        "analysis_summary": "需求分析完成" if output.status == "completed" else f"发现 {len(output.clarification_items)} 个待澄清问题",
        "understanding_markdown": output.understanding_markdown,
        "clarification_markdown": output.clarification_markdown,
        "clarification_items": [item.model_dump() for item in output.clarification_items],
        "artifacts": output.artifact_paths,
    }


def next_analysis_id() -> str:
    """生成下一个分析 ID"""
    return f"reqana-{secrets.token_hex(8)}"


__all__ = [
    # 新接口
    "analyze_requirement",
    # 旧接口（兼容）
    "analyze_requirement_legacy",
    "run_requirement_analysis",
    "build_requirement_analysis_output_json",
    "next_analysis_id",
]
