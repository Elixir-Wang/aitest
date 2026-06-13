"""
搜索 Agent - 使用 LangChain 1.3+ 工具调用模式

基于 langchain 1.3+ 和 langgraph 1.2+ 的最新 API
"""

from typing import List, Dict, Optional, Literal
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.agents.requirement_analysis.v3.tools.search_auxiliary import search_auxiliary_docs


SEARCH_SYSTEM_PROMPT = """你是需求分析系统的搜索助手。

## 任务
根据用户问题，在辅助文档中搜索答案。

## 可用工具
- search_auxiliary_docs: 在辅助文档中搜索关键词

## 搜索策略
1. 从问题中提取核心关键词
2. 使用 search_auxiliary_docs 工具搜索
3. 如果未找到，尝试不同的关键词（最多3次）
4. 找到答案后，引用原文并注明来源

## 示例
用户: "验证码有效期是多少？"
你: 搜索关键词"验证码有效期"
工具: 【文档: 安全规范.md】验证码有效期为 5 分钟
你: 根据安全规范.md，验证码有效期为 5 分钟。

## 注意
- 必须使用工具搜索，不要凭空编造
- 如果3次都没找到，明确说明"未找到答案"
- 答案必须引用原文，注明来源文档"""


class AuxiliarySearchAgent:
    """辅助文档搜索 Agent（基于 LangChain 1.3+ 工具调用）"""

    def __init__(self, model, auxiliary_documents: List[Dict], max_iterations: int = 3):
        """
        初始化搜索 Agent

        Args:
            model: LLM 模型（必须支持工具调用）
            auxiliary_documents: 辅助文档列表
            max_iterations: 最大搜索迭代次数
        """
        self.model = model
        self.auxiliary_documents = auxiliary_documents
        self.max_iterations = max_iterations

        # 注入文档到工具
        search_auxiliary_docs._auxiliary_documents = auxiliary_documents

        # 绑定工具到模型
        self.model_with_tools = model.bind_tools([search_auxiliary_docs])

    async def ainvoke(self, input_dict: dict, config: Optional[RunnableConfig] = None) -> dict:
        """
        异步执行搜索

        Args:
            input_dict: {"input": "搜索问题"}
            config: 可选的运行配置

        Returns:
            {"output": "答案", "intermediate_steps": [...]}
        """
        question = input_dict.get("input", "")

        # 初始化消息历史
        messages = [
            SystemMessage(content=SEARCH_SYSTEM_PROMPT),
            HumanMessage(content=f"请帮我搜索以下问题的答案：{question}")
        ]

        intermediate_steps = []

        for iteration in range(self.max_iterations):
            # 调用 LLM（带工具）
            response = await self.model_with_tools.ainvoke(messages, config=config)
            messages.append(response)

            # 检查是否有工具调用
            if not response.tool_calls:
                # 没有工具调用，LLM 直接给出答案
                return {
                    "output": response.content,
                    "intermediate_steps": intermediate_steps
                }

            # 执行所有工具调用
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]

                if tool_name == "search_auxiliary_docs":
                    # 执行搜索工具
                    try:
                        result = search_auxiliary_docs.invoke(tool_args)
                    except Exception as e:
                        result = f"搜索失败: {str(e)}"

                    # 记录中间步骤
                    intermediate_steps.append({
                        "action": tool_name,
                        "action_input": tool_args,
                        "observation": result
                    })

                    # 添加工具结果到消息
                    messages.append(ToolMessage(
                        content=result,
                        tool_call_id=tool_id
                    ))

        # 达到最大迭代次数，请求 LLM 总结
        messages.append(HumanMessage(content="请基于搜索结果给出最终答案。如果没找到，请明确说明'未找到答案'。"))
        final_response = await self.model.ainvoke(messages, config=config)

        return {
            "output": final_response.content,
            "intermediate_steps": intermediate_steps
        }


def create_auxiliary_search_agent(model, auxiliary_documents: List[Dict]) -> AuxiliarySearchAgent:
    """
    创建辅助文档搜索 Agent

    Args:
        model: LLM 模型（必须支持工具调用，如 gpt-4、claude-3 等）
        auxiliary_documents: 辅助文档列表
            格式: [{"filename": "...", "markdown_content": "..."}, ...]

    Returns:
        AuxiliarySearchAgent: 搜索 Agent 实例
    """
    return AuxiliarySearchAgent(model, auxiliary_documents)


__all__ = ["create_auxiliary_search_agent", "AuxiliarySearchAgent"]


__all__ = ["create_auxiliary_search_agent"]
