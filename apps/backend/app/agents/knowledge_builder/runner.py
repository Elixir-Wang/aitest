from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.knowledge_builder.prompts import build_knowledge_builder_input
from app.agents.runtime import run_agent
from app.schemas.knowledge import KnowledgeBuildInput, KnowledgeBuildOutput


AGENT_ID = "knowledge_builder"


async def run_knowledge_builder(input_data: KnowledgeBuildInput) -> KnowledgeBuildOutput:
    result = await run_agent(AGENT_ID, build_knowledge_builder_input(input_data))
    return parse_knowledge_builder_output(result.output)


def parse_knowledge_builder_output(output: Any) -> KnowledgeBuildOutput:
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
