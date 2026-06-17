"""Requirement understanding child agent."""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_analysis.understanding.schemas import (
    BusinessObject,
    RequirementModule,
    RequirementUnderstandingOutput,
    Risk,
)
from app.agents.requirement_analysis.understanding.explainer import ExplanationGenerator
from app.agents.requirement_analysis.understanding.models import (
    DeepUnderstandingResult,
    UnifiedUnderstandingOutput,
)
from app.agents.requirement_analysis.utils.timing import record_step_timing, start_step_timer


UNDERSTANDING_SYSTEM_PROMPT = """
你是资深业务架构师、DDD 专家与测试架构师。

# 需求文档
{requirement_doc}

# 任务

请在一次分析中完成以下三部分，并严格输出 UnifiedUnderstandingOutput 结构。

## 1. 业务洞察 (business_insight)

- 识别业务领域、痛点、核心价值、关键流程与决策点
- 重点理解「为什么」，不要简单复述文档
- 聚焦决定成败的关键流程与测试关注点

## 2. 领域模型 (domain_model)

- 识别核心概念与领域实体（理解存在意义，不是罗列字段）
- 提取不变性约束（可验证的业务规则）
- 为有状态对象构建状态机（含异常路径与 Mermaid 状态图代码）

## 3. 风险画像 (risk_profile)

- 识别复杂场景（说明复杂度来源：state_machine / concurrency / async / external_dependency / business_rule）
- 分析风险根因（具体场景、触发条件、后果、概率）
- 识别边界条件与可执行的测试策略（含断言点与优先级）

# 输出要求

一次性输出包含以下三个字段的 JSON：
- business_insight
- domain_model
- risk_profile

## 质量标准

- 有推理过程，不泛泛而谈
- 风险与测试策略具体、可执行
- 状态机与边界条件完整
- 只基于需求文档内容，不臆造
"""


def understanding_agent(model, requirement_doc: str):
    """Create the requirement understanding agent."""
    return create_agent(
        model=model,
        tools=[],
        system_prompt=UNDERSTANDING_SYSTEM_PROMPT.format(requirement_doc=requirement_doc),
        response_format=ToolStrategy(UnifiedUnderstandingOutput),
    )


def _map_deep_result_to_understanding(deep_result: DeepUnderstandingResult) -> RequirementUnderstandingOutput:
    modules = []
    for entity in deep_result.domain_model.entities:
        modules.append(
            RequirementModule(
                module_key=entity.name.lower().replace(" ", "_"),
                module_name=entity.name,
                summary=entity.essence,
                capabilities=entity.key_attributes,
                business_objects=[
                    BusinessObject(
                        name=entity.name,
                        description=entity.why_exists,
                        fields=entity.key_attributes,
                        relationships=entity.relationships,
                    )
                ],
                business_rules=[],
                state_flows=[],
                dependencies=[],
            )
        )

    risks = []
    for root_cause in deep_result.risk_profile.root_causes:
        risks.append(
            Risk(
                risk_id=f"RISK-{len(risks) + 1}",
                category="business" if "业务" in root_cause.risk_description else "technical",
                description=root_cause.risk_description,
                impact="high" if root_cause.likelihood == "high" else "medium",
                likelihood=root_cause.likelihood,
                mitigation=root_cause.root_cause,
            )
        )

    return RequirementUnderstandingOutput(
        modules=modules,
        dependencies=[],
        risks=risks,
        assumptions=[],
        understanding_summary=deep_result.business_insight.summary,
    )


def _build_deep_understanding_metadata(deep_result: DeepUnderstandingResult) -> dict[str, Any]:
    return {
        "business_insight": deep_result.business_insight.model_dump(),
        "domain_model": deep_result.domain_model.model_dump(),
        "risk_profile": deep_result.risk_profile.model_dump(),
        "explanation_markdown": deep_result.explanation_markdown,
    }


async def run_understanding_agent(
    model,
    primary_markdown_content: str,
    *,
    run_id: str = "",
    metadata: dict[str, Any] | None = None,
    output_dir: str = "",  # 新增：Mermaid 输出目录
) -> tuple[RequirementUnderstandingOutput, dict[str, Any]]:
    """Run the requirement understanding agent."""
    from datetime import datetime

    metadata = metadata if metadata is not None else {}
    explainer = ExplanationGenerator()

    llm_started = start_step_timer()
    agent = understanding_agent(model, primary_markdown_content)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "请完成统一需求理解分析。",
                }
            ]
        }
    )
    unified = result.get("structured_response")
    if unified is None:
        raise ValueError("需求理解智能体未返回结构化结果")
    record_step_timing(
        metadata,
        run_id=run_id,
        step="understand_llm",
        started_at=llm_started,
    )

    explain_started = start_step_timer()
    explanation = explainer.generate(
        unified.business_insight,
        unified.domain_model,
        unified.risk_profile,
    )
    record_step_timing(
        metadata,
        run_id=run_id,
        step="understand_explain",
        started_at=explain_started,
    )

    deep_result = DeepUnderstandingResult(
        business_insight=unified.business_insight,
        domain_model=unified.domain_model,
        risk_profile=unified.risk_profile,
        explanation_markdown=explanation,
        generated_at=datetime.now().isoformat(),
    )

    # 新增：保存 Mermaid 图到文件系统（Token 优化）
    mermaid_files = {}
    if output_dir:
        from app.agents.requirement_analysis.understanding.mermaid_manager import MermaidManager

        mermaid_mgr = MermaidManager(output_dir)

        # 保存状态机图（如果领域模型中有状态机）
        if hasattr(unified.domain_model, 'entities'):
            for entity in unified.domain_model.entities:
                # 检查实体是否有状态机相关属性
                if hasattr(entity, 'state_machine_mermaid') and entity.state_machine_mermaid:
                    paths = mermaid_mgr.save_state_machine(
                        entity.name,
                        entity.state_machine_mermaid,
                        render_png=True
                    )
                    mermaid_files[f"state_{entity.name}"] = paths

        # 保存领域模型图（如果有）
        if hasattr(unified.domain_model, 'mermaid_diagram') and unified.domain_model.mermaid_diagram:
            paths = mermaid_mgr.save_domain_model(
                unified.domain_model.mermaid_diagram,
                render_png=True
            )
            mermaid_files["domain_model"] = paths

        # 记录 Mermaid 文件路径到元数据（不传源码）
        if mermaid_files:
            metadata["mermaid_files"] = mermaid_files
            print(f"[Understanding] Mermaid 图已保存到: {output_dir}")
            for name, paths in mermaid_files.items():
                print(f"  - {name}: {paths.get('mmd', 'N/A')}")

    return (
        _map_deep_result_to_understanding(deep_result),
        _build_deep_understanding_metadata(deep_result),
    )


__all__ = [
    "UNDERSTANDING_SYSTEM_PROMPT",
    "understanding_agent",
    "run_understanding_agent",
]
