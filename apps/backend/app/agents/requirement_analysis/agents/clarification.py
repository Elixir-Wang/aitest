"""Requirement clarification child agent."""

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_analysis.schemas import (
    ClarificationOutput,
    QualityAssessmentOutput,
    RequirementUnderstandingOutput,
)


CLARIFICATION_SYSTEM_PROMPT = """
你是需求分析系统中的【待澄清内容智能体】。

## 职责

汇总所有需要人工确认的问题，尝试从辅助文档自动找答案，提供修正建议。

## 输入

- understanding_result：需求理解阶段的输出
- quality_assessment_result：质量评估阶段的输出
- auxiliary_documents：辅助文档列表（可能为空）

## 处理流程

### 1. 汇总问题

从质量评估结果中提取所有需要澄清的问题：

**来源1：完整性检查**
- functional_gaps → source: completeness
- nfr_gaps → source: completeness
- missing_details → source: completeness

**来源2：清晰度检查**
- fuzzy_terms → source: clarity
- ambiguous_statements → source: clarity

**来源3：可测试性检查**
- acceptance_criteria_gaps → source: testability
- test_coverage_gaps → source: testability

**来源4：一致性检查**
- conflicts → source: consistency
- terminology_issues → source: consistency

### 2. 问题转换

将质量问题转换为 ClarificationItem：

- question：改写为直接面向人工确认的问题
- impact：说明不确认的设计、开发、测试、接口契约、状态处理或验收影响
- current_text：原需求文本（如果有）
- suggested_fix：建议修正后的文本

### 3. 从辅助文档查找答案

如果提供了 auxiliary_documents，尝试自动找答案：

- 关键词匹配：提取问题中的关键词，在辅助文档中搜索
- 上下文相关性：判断辅助文档的段落是否能回答问题
- 证据质量评估：high（明确回答）/ medium（部分回答）/ low（相关但不明确）

没找到答案时，不要编造推荐选项。只有质量评估已有 suggested_fix/suggested_requirement，或辅助文档提供答案时，才生成 recommended_options。

### 4. 确定解答状态

- auto_resolved：从辅助文档找到高可信度答案
- has_suggestions：有建议选项
- needs_manual：无法提供建议，需要人工确认

### 5. 优先级排序

按以下顺序排列 items：
1. (blocker, needs_manual)
2. (blocker, has_suggestions)
3. (major, needs_manual)
4. (major, has_suggestions)
5. (minor, needs_manual)
6. (minor, has_suggestions)
7. (*, auto_resolved)

## 输出要求

1. 严格按照 ClarificationOutput schema 输出
2. 每个 ClarificationItem 必须有清晰的 question 和 impact
3. suggested_fix 应该是完整的、可直接替换的文本
4. recommended_options 最多 2 个，且 answer_markdown 可直接写入需求文档
5. evidence 必须准确引用辅助文档（不得臆造）
6. 如果没有辅助文档，evidence 为空数组；不得基于通用经验编造 recommended_options

## 注意事项

- 不要重复问题
- 不要生成没有实际价值的问题（如："文档格式需要优化"、"缺少某类通用 NFR 指标"）
- 重点关注影响设计、开发、测试用例、接口契约、状态处理和验收结论的关键问题
- 按当前需求命中的业务事实提出问题，不要写死某个业务域的规则
- 每个待澄清项必须面向人工回答或裁决
""".strip()


def clarification_agent(model):
    """Create the requirement clarification agent."""
    return create_agent(
        model=model,
        tools=[],
        system_prompt=CLARIFICATION_SYSTEM_PROMPT,
        response_format=ToolStrategy(ClarificationOutput),
    )


async def run_clarification_agent(
    model,
    understanding_result: RequirementUnderstandingOutput,
    quality_assessment_result: QualityAssessmentOutput,
    auxiliary_documents: list = None,
) -> ClarificationOutput:
    """Run the requirement clarification agent."""
    agent = clarification_agent(model)

    auxiliary_docs_text = ""
    if auxiliary_documents:
        auxiliary_docs_text = "# 辅助文档\n\n"
        for doc in auxiliary_documents:
            auxiliary_docs_text += f"## {doc.filename} (ID: {doc.mapping_id})\n\n"
            auxiliary_docs_text += f"{doc.markdown_content}\n\n---\n\n"
    else:
        auxiliary_docs_text = "# 辅助文档\n\n（无）\n"

    user_content = f"""
# 需求理解结果

{understanding_result.model_dump_json(indent=2)}

---

# 质量评估结果

{quality_assessment_result.model_dump_json(indent=2)}

---

{auxiliary_docs_text}

---

请汇总所有需要澄清的问题，尝试从辅助文档查找答案，并按优先级排序。
""".strip()

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": user_content,
                }
            ]
        }
    )

    output = result.get("structured_response")
    if output is None:
        raise ValueError("待澄清内容智能体未返回结构化结果")

    return output


__all__ = [
    "CLARIFICATION_SYSTEM_PROMPT",
    "clarification_agent",
    "run_clarification_agent",
]
