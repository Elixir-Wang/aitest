"""需求分析服务层"""

import json
import secrets
from pathlib import Path

from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.agents.requirement_analysis.agent import requirement_analysis_agent
from app.agents.requirement_analysis.schemas import (
    RequirementAnalysisResult,
    RequirementInput,
)
from app.core.db import connect
from app.core.storage import project_requirement_dir, resolve_stored_path, store_path
from app.repositories import document_repo, requirement_analysis_run_repo


CAPABILITY_ID = "requirement_analysis"
REQUIREMENT_ANALYSIS_MARKDOWN_FIELDS = {
    "clarification_report_markdown",
    "clarification_markdown",
    "understanding_markdown",
}


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
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
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


async def run_requirement_analysis(input_data: RequirementInput) -> RequirementAnalysisResult:
    """运行需求分析。"""
    return await analyze_requirement(input_data)


def load_run_input(run_id: str) -> RequirementInput:
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
        auxiliary_docs = []
        for row in document_repo.list_file_mappings(db, run["document_id"]):
            if row["id"] == primary_file["id"]:
                continue
            if row["conversion_status"] not in {"success", "warning"} or not row["markdown_file_path"]:
                continue
            auxiliary_docs.append(_read_markdown_file(row["markdown_file_path"], "辅助需求标准文件不存在。"))

    return RequirementInput(
        requirement_name=document["name"],
        requirement_content=primary_markdown,
        auxiliary_docs=auxiliary_docs,
    )


def _read_markdown_file(path_value: str, missing_message: str) -> str:
    """读取 Markdown 文件"""
    markdown_path = resolve_stored_path(path_value) or Path(path_value)
    if not markdown_path.exists():
        raise ValueError(missing_message)
    return markdown_path.read_text(encoding="utf-8")


def write_requirement_analysis_artifacts(run_id: str, output: RequirementAnalysisResult) -> dict[str, str]:
    """写入产物文件"""
    with connect() as db:
        run = requirement_analysis_run_repo.find_run(db, run_id)
        if not run:
            raise ValueError("需求分析任务不存在。")

    run_dir = (
        project_requirement_dir(run["project_id"], run["document_id"])
        / "analysis_runs"
        / run_id
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    understanding_path = run_dir / "understanding.md"
    clarification_path = run_dir / "clarifications.md"
    result_path = run_dir / "result.json"
    understanding_path.write_text(output.to_understanding_markdown().rstrip() + "\n", encoding="utf-8")
    clarification_path.write_text(output.to_clarification_markdown().rstrip() + "\n", encoding="utf-8")
    result_path.write_text(
        json.dumps(build_requirement_analysis_output_json(output), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "understanding": store_path(understanding_path) or str(understanding_path),
        "clarification": store_path(clarification_path) or str(clarification_path),
        "result": store_path(result_path) or str(result_path),
    }


def build_requirement_analysis_output_json(output: RequirementAnalysisResult, artifact_paths: dict[str, str] | None = None) -> dict:
    """构建需求分析输出 JSON"""
    return {
        "status": output.status,
        "summary": "需求分析完成" if output.status == "completed" else f"发现 {len(output.clarifications)} 个待澄清问题",
        "analysis_summary": "需求分析完成" if output.status == "completed" else f"发现 {len(output.clarifications)} 个待澄清问题",
        "understanding_markdown": output.to_understanding_markdown(),
        "clarification_markdown": output.to_clarification_markdown(),
        "clarification_items": [item.model_dump() for item in output.clarifications],
        "artifacts": artifact_paths or {},
    }


def normalize_analysis_output_markdown(output: dict) -> dict:
    """Normalize escaped markdown fields stored in analysis JSON rows."""
    normalized = dict(output)
    for field in REQUIREMENT_ANALYSIS_MARKDOWN_FIELDS:
        if field in normalized:
            normalized[field] = _normalize_markdown_text(normalized[field])
    return normalized


def _normalize_markdown_text(value: object) -> str:
    text = str(value or "")
    if "\\" in text:
        text = (
            text.replace("\\r\\n", "\n")
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
        )
    return text.replace("质量保证", "质量保障")


def next_analysis_id() -> str:
    """生成下一个分析 ID"""
    return f"reqana-{secrets.token_hex(8)}"


__all__ = [
    "analyze_requirement",
    "run_requirement_analysis",
    "load_run_input",
    "write_requirement_analysis_artifacts",
    "build_requirement_analysis_output_json",
    "normalize_analysis_output_markdown",
    "next_analysis_id",
]
