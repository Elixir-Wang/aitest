"""
搜索服务 - 针对单个问题搜索答案

封装搜索 Agent，提供统一的服务接口
"""

from typing import Any, Dict, List

from app.agents.requirement_analysis.v3.agents.search import create_auxiliary_search_agent


async def search_for_answer(
    model,
    question: str,
    auxiliary_documents: List[Dict]
) -> Dict:
    """
    针对单个问题搜索答案

    Args:
        model: LLM 模型
        question: 待澄清的问题（如："验证码有效期是多少？"）
        auxiliary_documents: 辅助文档列表
            格式: [{"filename": "...", "markdown_content": "..."}, ...]

    Returns:
        {
            "found": bool,              # 是否找到答案
            "answer": str,              # 答案内容
            "source": str,              # 来源文档
            "confidence": str,          # high/medium/low
            "search_steps": List[str]   # 搜索路径（关键词列表）
        }
    """
    # 空辅助文档快速返回
    if not auxiliary_documents:
        return {
            "found": False,
            "answer": "",
            "source": "",
            "confidence": "none",
            "search_steps": []
        }

    # 创建搜索 Agent
    search_agent = create_auxiliary_search_agent(model, auxiliary_documents)

    # 执行搜索
    try:
        result = await search_agent.ainvoke({
            "input": f"请搜索以下问题的答案：{question}"
        })
    except Exception as e:
        # 搜索失败
        return {
            "found": False,
            "answer": "",
            "source": "",
            "confidence": "none",
            "search_steps": [],
            "error": str(e)
        }

    # 解析结果
    answer = result.get("output", "")
    found = "未找到" not in answer and len(answer.strip()) > 0

    # 提取来源文档
    source = ""
    if found and "【文档:" in answer:
        try:
            source = answer.split("【文档:")[1].split("】")[0].strip()
        except IndexError:
            source = "未知"

    # 评估置信度
    if found:
        # 有明确来源 → high
        if source:
            confidence = "high"
        # 答案长度 > 20 → medium
        elif len(answer) > 20:
            confidence = "medium"
        else:
            confidence = "low"
    else:
        confidence = "none"

    # 提取搜索步骤（关键词列表）
    search_steps = []
    for step in result.get("intermediate_steps", []):
        query = _extract_search_query(step)
        if query:
            search_steps.append(query)

    return {
        "found": found,
        "answer": answer if found else "",
        "source": source,
        "confidence": confidence,
        "search_steps": search_steps
    }


def _extract_search_query(step: Any) -> str:
    if isinstance(step, dict):
        action_input = step.get("action_input", {})
        if isinstance(action_input, dict):
            return action_input.get("query", "")
        return str(action_input) if action_input else ""

    if isinstance(step, tuple) and step:
        action = step[0]
        tool_input = getattr(action, "tool_input", None)
        if isinstance(tool_input, dict):
            return tool_input.get("query", "")
        return str(tool_input) if tool_input else ""

    return ""


__all__ = ["search_for_answer"]
