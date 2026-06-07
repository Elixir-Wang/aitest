import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.schemas.requirement_analysis import (
    RequirementAnalysisInput,
    RequirementAnalysisOutput,
    RequirementAuxiliaryEnhancementInput,
    RequirementAuxiliaryEnhancementOutput,
)


CAPABILITY_ID = "requirement_analysis"

PRIMARY_ANALYSIS_SYSTEM_PROMPT = """
你是 AI 测试系统中的主需求分析智能体。

只分析输入中的 primary_markdown_content，不读取、不引用、不推测任何辅助文档。

分析目标：
- 识别主需求的遗漏、歧义、冲突、不可测、规则缺失和验收标准缺失。
- 从测试视角反推角色、前置条件、操作步骤、预期结果、边界值和异常路径缺口。
- 生成基于主需求的 preliminary_requirement_markdown。
- 无法从主需求确认的问题进入 clarification_questions 或 conflicts。

输出要求：
- 返回 RequirementAnalysisOutput JSON。
- applied_supplements 必须为空数组。
- 不得引用辅助文件来源。
- preliminary_requirement_markdown 不能为空。
""".strip()

ENHANCEMENT_SYSTEM_PROMPT = """
你是 AI 测试系统中的辅助文档增强智能体。

输入包含阶段一发现的问题列表，以及多个辅助文章 Markdown。你的任务是在这些辅助文章中寻找能回答问题的内容。

边界：
- 只处理输入 questions 中的问题。
- 只能引用输入 auxiliary_articles 中的内容。
- 不得引用输入之外的文件、常识或推测。
- 不重新分析完整主需求。
- 不输出完整 RequirementAnalysisOutput，只输出 RequirementAuxiliaryEnhancementOutput JSON。

输出要求：
- 如果辅助文章能直接回答问题，给出 recommended_options，answer_markdown 必须可直接写入初步需求。
- 如果辅助文章内容可补入初步需求，放入 applied_supplements，并附 evidence。
- 如果辅助文章与主需求或文章之间冲突，放入 new_conflicts。
- 如果找不到答案、证据弱或来源不清，记录 unchanged_question_ids 或 resolution=weak_evidence/not_found。
""".strip()


async def analyze_requirement(input_data: RequirementAnalysisInput) -> RequirementAnalysisOutput:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    output = await _ainvoke_structured(
        model,
        RequirementAnalysisOutput,
        system_prompt=PRIMARY_ANALYSIS_SYSTEM_PROMPT,
        user_content=_build_primary_analysis_input(input_data),
    )
    if output.applied_supplements:
        output.applied_supplements = []
    if not output.preliminary_requirement_markdown.strip():
        raise ValueError("需求分析智能体未返回初步需求内容。")
    return output


async def enhance_requirement_with_auxiliary_articles(
    input_data: RequirementAuxiliaryEnhancementInput,
) -> RequirementAuxiliaryEnhancementOutput:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    return await _ainvoke_structured(
        model,
        RequirementAuxiliaryEnhancementOutput,
        system_prompt=ENHANCEMENT_SYSTEM_PROMPT,
        user_content=_build_auxiliary_enhancement_input(input_data),
    )


async def _ainvoke_structured(model, schema, *, system_prompt: str, user_content: str):
    structured_model = model.with_structured_output(schema)
    result = await structured_model.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
    )
    if isinstance(result, schema):
        return result
    if isinstance(result, dict):
        return schema.model_validate(result)
    raise ValueError("智能体未返回结构化结果。")


def _build_primary_analysis_input(input_data: RequirementAnalysisInput) -> str:
    return "\n".join(
        [
            "请只基于主需求执行需求分析，返回 RequirementAnalysisOutput。",
            "",
            "input_json:",
            json.dumps(_primary_visible_input(input_data), ensure_ascii=False, indent=2),
        ]
    )


def _primary_visible_input(input_data: RequirementAnalysisInput) -> dict[str, Any]:
    return {
        "project_id": input_data.project_id,
        "document_id": input_data.document_id,
        "document_name": input_data.document_name,
        "primary_mapping_id": input_data.primary_mapping_id,
        "primary_filename": input_data.primary_filename,
        "primary_markdown_content": input_data.primary_markdown_content,
    }


def _build_auxiliary_enhancement_input(input_data: RequirementAuxiliaryEnhancementInput) -> str:
    return "\n".join(
        [
            "请基于 questions 和 auxiliary_articles 查找答案，返回 RequirementAuxiliaryEnhancementOutput。",
            "",
            "input_json:",
            json.dumps(input_data.model_dump(), ensure_ascii=False, indent=2),
        ]
    )


def _build_requirement_analysis_input(input_data: RequirementAnalysisInput) -> str:
    return _build_primary_analysis_input(input_data)
