from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.runtime import run_agent
from app.schemas.knowledge import KnowledgeBuildInput, KnowledgeBuildOutput

KNOWLEDGE_BUILDER_AGENT_ID = "knowledge_builder"


async def run_knowledge_builder(input_data: KnowledgeBuildInput) -> KnowledgeBuildOutput:
    result = await run_agent(KNOWLEDGE_BUILDER_AGENT_ID, _build_agent_prompt(input_data))
    return _parse_agent_output(result.output)


def _build_agent_prompt(input_data: KnowledgeBuildInput) -> str:
    payload = input_data.model_dump()
    return (
        "请基于以下已准入来源，生成项目知识库 llm-wiki。\n"
        "必须使用 Karpathy llm-wiki 思路：先编译成可导航 Markdown wiki，而不是切 chunk 或生成向量检索材料。\n"
        "只能沉淀已确认需求事实、页面事实、融合事实和测试关注点。\n"
        "待确认问题、阻塞项、未确认冲突和失败诊断不得作为正式知识条目。\n"
        "必须生成 AGENTS.md、index.md、模块页、来源引用矩阵、质量检查、测试关注点和构建摘要。\n"
        "只返回一个 JSON 对象，不要 Markdown 代码块，不要解释文字。\n"
        "JSON 必须符合字段：status, summary, change_summary, affected_modules, blockers, pages, knowledge_items, lint_issues。\n\n"
        f"输入：\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _parse_agent_output(output: Any) -> KnowledgeBuildOutput:
    if isinstance(output, KnowledgeBuildOutput):
        return output
    if isinstance(output, dict):
        return KnowledgeBuildOutput.model_validate(output)
    if not isinstance(output, str):
        raise ValueError("知识库智能体输出类型不支持。")

    text = output.strip()
    if text.startswith("```"):
        text = _strip_code_fence(text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("知识库智能体未返回合法 JSON。") from exc
    try:
        return KnowledgeBuildOutput.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("知识库智能体输出不符合知识库契约。") from exc


def _strip_code_fence(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
