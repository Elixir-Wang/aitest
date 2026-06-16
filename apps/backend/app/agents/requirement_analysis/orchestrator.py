"""Sequential requirement analysis orchestrator."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.requirement_analysis.agents.clarification import run_clarification_agent
from app.agents.requirement_analysis.agents.quality import run_quality_assessment_agent
from app.agents.requirement_analysis.agents.questioning import run_questioning_agent
from app.agents.requirement_analysis.agents.understanding import run_understanding_agent
from app.agents.requirement_analysis.core.schemas import (
    RequirementAnalysisInputV2,
    RequirementAnalysisResultV2,
)
from app.agents.requirement_analysis.utils.context import (
    build_evidence_snippets,
    build_quality_brief,
    build_questioning_brief,
    build_understanding_brief,
)
from app.agents.requirement_analysis.utils.enhancer import (
    generate_enhanced_requirement,
    get_auto_resolved_items,
)
from app.agents.requirement_analysis.utils.report import generate_analysis_report
from app.agents.requirement_analysis.utils.timing import record_step_timing, start_step_timer


async def run_requirement_analysis(input_data: RequirementAnalysisInputV2) -> RequirementAnalysisResultV2:
    start_time = time.time()
    model_selection = resolve_model_selection("requirement_analysis")
    model = build_agent_model(model_selection)

    metadata: dict = {}

    # 准备 Mermaid 输出目录
    version = getattr(input_data, 'version', 'VX.X.X')
    requirement_name = getattr(input_data, 'requirement_name', input_data.document_name or 'requirement')
    mermaid_output_dir = f"release_version/{version}/{requirement_name}/diagrams"

    # 1. 理解节点
    started_at = start_step_timer()
    understanding, deep_understanding = await run_understanding_agent(
        model=model,
        primary_markdown_content=input_data.primary_markdown_content,
        run_id=input_data.run_id or "",
        metadata=metadata,
        output_dir=mermaid_output_dir,  # 传递 Mermaid 输出目录
    )
    record_step_timing(metadata, run_id=input_data.run_id or "", step="understand", started_at=started_at)
    metadata["deep_understanding"] = deep_understanding

    # 生成理解摘要（传递给下游）
    understanding_brief = build_understanding_brief(understanding)

    # 将 Mermaid 文件路径添加到摘要中
    if "mermaid_files" in metadata:
        understanding_brief.mermaid_files = metadata["mermaid_files"]

    # 提取高风险 ID
    understanding_brief.high_risk_ids = [
        risk.risk_id for risk in understanding.risks
        if risk.impact == "high"
    ][:5]  # 只保留前5个高风险ID

    evidence_snippets = build_evidence_snippets(
        input_data.primary_markdown_content,
        input_data.auxiliary_documents,
    )

    # 2. 质疑节点 + 3. 质量评估节点（并行执行 🚀）
    # 两个节点都只依赖 Understanding，可以同时执行以节省时间
    parallel_started_at = start_step_timer()

    # 并行执行 Questioning 和 Quality Assessment
    questioning_task = run_questioning_agent(
        model=model,
        primary_markdown_content=input_data.primary_markdown_content,
        understanding_result=understanding,
        understanding_brief=understanding_brief,  # 传递摘要
        run_id=input_data.run_id or "",
        metadata=metadata,
    )

    quality_task = _run_quality_agent_compat(
        model=model,
        primary_markdown_content=input_data.primary_markdown_content,
        understanding=understanding,
        understanding_brief=understanding_brief,  # 传递摘要
        evidence_snippets=evidence_snippets,
    )

    # 等待两个任务完成
    (questioning, questioning_metadata), quality = await asyncio.gather(
        questioning_task,
        quality_task,
    )

    parallel_elapsed_ms = int((time.time() - parallel_started_at) * 1000)
    metadata.setdefault("step_timings", {})["questioning_quality_parallel"] = parallel_elapsed_ms
    metadata["questioning"] = questioning_metadata

    # 生成质疑摘要（传递给下游）
    questioning_brief = build_questioning_brief(questioning)
    quality_brief = build_quality_brief(quality)

    # 4. 澄清节点（传递摘要）
    started_at = start_step_timer()
    clarification = await _run_clarification_agent_compat(
        model=model,
        understanding=understanding,
        quality=quality,
        understanding_brief=understanding_brief,  # 传递摘要
        quality_brief=quality_brief,              # 传递摘要
        evidence_snippets=evidence_snippets,
        auxiliary_documents=input_data.auxiliary_documents,
    )
    record_step_timing(metadata, run_id=input_data.run_id or "", step="clarify", started_at=started_at)

    started_at = start_step_timer()
    analysis_report = generate_analysis_report(understanding)
    auto_resolved_items = get_auto_resolved_items(clarification.items)
    enhanced_requirement = generate_enhanced_requirement(
        original_markdown=input_data.primary_markdown_content,
        auto_resolved_items=auto_resolved_items,
    )
    needs_manual = (
        clarification.summary.by_resolution.get("needs_input", 0)
        + clarification.summary.by_resolution.get("needs_research", 0)
    )
    if quality.decision.result == "rejected":
        status = "blocked"
    elif needs_manual > 0:
        status = "needs_clarification"
    else:
        status = "completed"
    record_step_timing(metadata, run_id=input_data.run_id or "", step="enhance", started_at=started_at)

    execution_time_ms = int((time.time() - start_time) * 1000)
    return RequirementAnalysisResultV2(
        status=status,
        understanding=understanding,
        questioning=questioning,
        quality_assessment=quality,
        clarification=clarification,
        analysis_report_markdown=analysis_report,
        enhanced_requirement_markdown=enhanced_requirement,
        metadata={
            "version": "2.0",
            "engine": "three_agent_orchestrator",
            "project_id": input_data.project_id,
            "document_id": input_data.document_id,
            "document_name": input_data.document_name,
            "run_id": input_data.run_id,
            "execution_time_ms": execution_time_ms,
            "step_timings": metadata.get("step_timings", {}),
            "execution_timestamp": datetime.now().isoformat(),
            "config": input_data.config,
        },
    )


async def _run_quality_agent_compat(
    *,
    model: Any,
    primary_markdown_content: str,
    understanding: Any,
    understanding_brief: Any,
    evidence_snippets: Any,
):
    try:
        return await run_quality_assessment_agent(
            model=model,
            understanding_brief=understanding_brief,
            requirement_evidence=evidence_snippets,
            primary_markdown_content=primary_markdown_content,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return await run_quality_assessment_agent(
            model=model,
            primary_markdown_content=primary_markdown_content,
            understanding_result=understanding,
        )


async def _run_clarification_agent_compat(
    *,
    model: Any,
    understanding: Any,
    quality: Any,
    understanding_brief: Any,
    quality_brief: Any,
    evidence_snippets: Any,
    auxiliary_documents: Any,
):
    try:
        return await run_clarification_agent(
            model=model,
            understanding_brief=understanding_brief,
            quality_brief=quality_brief,
            evidence_snippets=evidence_snippets,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return await run_clarification_agent(
            model=model,
            understanding_result=understanding,
            quality_assessment_result=quality,
            auxiliary_documents=auxiliary_documents,
        )


__all__ = ["run_requirement_analysis"]
