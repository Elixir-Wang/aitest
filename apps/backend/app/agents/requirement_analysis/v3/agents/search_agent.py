"""
搜索 Agent - 使用简化的工具调用模式搜索辅助文档

使用 LangChain 的 bind_tools 和结构化输出
"""

from typing import List, Dict, Optional
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool

from app.agents.requirement_analysis.v3.tools.search_auxiliary import search_auxiliary_docs


class AuxiliarySearchAgent:
    """辅助文档搜索 Agent（简化版本）"""

    def __init__(self, model, auxiliary_documents: List[Dict]):
        """
        初始化搜索 Agent

        Args:
            model: LLM 模型（支持工具调用）
            auxiliary_documents: 辅助文档列表
        """
        self.model = model
        self.auxiliary_documents = auxiliary_documents
        # 注入文档到工具
        search_auxiliary_docs._auxiliary_documents = auxiliary_documents

        # 绑定工具到模型
        self.model_with_tools = model.bind_tools([search_auxiliary_docs])

    async def ainvoke(self, input_dict: dict) -> dict:
        """
        异步执行搜索

        Args:
            input_dict: {"input": "搜索问题"}

        Returns:
            {"output": "答案", "intermediate_steps": [...]}
        """
        question = input_dict.get("input", "")
        messages = [
            HumanMessage(content=f"""你是需求分析系统的搜索助手。

任务：在辅助文档中搜索答案来回答下面的问题。

搜索策略：
1. 提取关键词
2. 使用 search_auxiliary_docs 工具搜索
3. 如果没找到，换关键词再试（最多3次）
4. 返回最终答案

问题：{question}

请开始搜索。""")
        ]

        intermediate_steps = []
        max_iterations = 3

        for i in range(max_iterations):
            # LLM 决定是否调用工具
            response = await self.model_with_tools.ainvoke(messages)
            messages.append(response)

            # 检查是否有工具调用
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    # 执行工具
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']

                    if tool_name == 'search_auxiliary_docs':
                        result = search_auxiliary_docs.invoke(tool_args)

                        # 记录中间步骤
                        intermediate_steps.append({
                            'action': tool_name,
                            'action_input': tool_args,
                            'observation': result
                        })

                        # 添加工具结果到消息
                        messages.append(ToolMessage(
                            content=result,
                            tool_call_id=tool_call['id']
                        ))

                        # 如果找到答案，让 LLM 总结
                        if "未找到" not in result:
                            final_response = await self.model.ainvoke(
                                messages + [HumanMessage(content="请基于搜索结果回答原问题。")]
                            )
                            return {
                                "output": final_response.content,
                                "intermediate_steps": intermediate_steps
                            }
            else:
                # 没有工具调用，直接返回 LLM 的回答
                return {
                    "output": response.content,
                    "intermediate_steps": intermediate_steps
                }

        # 达到最大迭代次数
        return {
            "output": "未找到答案",
            "intermediate_steps": intermediate_steps
        }


def create_auxiliary_search_agent(model, auxiliary_documents: List[Dict]) -> AuxiliarySearchAgent:
    """
    创建辅助文档搜索 Agent

    Args:
        model: LLM 模型
        auxiliary_documents: 辅助文档列表
            格式: [{"filename": "...", "markdown_content": "..."}, ...]

    Returns:
        AuxiliarySearchAgent: 可执行的搜索 Agent
    """
    return AuxiliarySearchAgent(model, auxiliary_documents)


__all__ = ["create_auxiliary_search_agent"]
