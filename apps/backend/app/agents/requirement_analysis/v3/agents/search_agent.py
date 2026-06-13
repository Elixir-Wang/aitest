"""
搜索 Agent - 使用 ReAct 模式智能搜索辅助文档

ReAct = Reasoning + Acting
Agent 自主决定搜索策略，多轮迭代优化
"""

from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate
from typing import List, Dict

from app.agents.requirement_analysis.v3.tools.search_auxiliary import search_auxiliary_docs


SEARCH_AGENT_PROMPT = PromptTemplate.from_template("""
你是需求分析系统的搜索助手。

## 任务

根据质量问题，在辅助文档中搜索答案。

## 可用工具

{tools}

## 搜索策略

1. **提取关键词**：从问题中提取核心关键词
2. **执行搜索**：使用 search_auxiliary_docs 搜索
3. **评估结果**：判断是否找到答案
4. **迭代优化**：如果没找到，换关键词再试（最多3次）

## 示例

### 场景1：直接找到
问题：验证码有效期是多少？
- 第1次搜索："验证码有效期" → 找到！
- 答案："验证码有效期为 5 分钟"

### 场景2：迭代搜索
问题：审批超时后如何处理？
- 第1次搜索："审批超时" → 未找到
- 第2次搜索："超时处理" → 找到！
- 答案："超时后自动转至上级审批"

### 场景3：未找到
问题：系统支持哪些支付方式？
- 第1次搜索："支付方式" → 未找到
- 第2次搜索："支付" → 未找到
- 第3次搜索："payment" → 未找到
- 答案："未找到答案"

## 注意

- 如果搜索3次都没找到，返回 "未找到答案"
- 答案必须引用原文，不要改写
- 必须注明来源文档

---

## 当前问题

{input}

---

{agent_scratchpad}
""")


def create_auxiliary_search_agent(model, auxiliary_documents: List[Dict]) -> AgentExecutor:
    """
    创建辅助文档搜索 Agent

    Args:
        model: LLM 模型
        auxiliary_documents: 辅助文档列表
            格式: [{"filename": "...", "markdown_content": "..."}, ...]

    Returns:
        AgentExecutor: 可执行的搜索 Agent
    """
    # 注入辅助文档到工具
    search_auxiliary_docs._auxiliary_documents = auxiliary_documents

    # 创建 ReAct Agent
    agent = create_react_agent(
        llm=model,
        tools=[search_auxiliary_docs],
        prompt=SEARCH_AGENT_PROMPT
    )

    return AgentExecutor(
        agent=agent,
        tools=[search_auxiliary_docs],
        max_iterations=3,  # 最多搜索3次
        verbose=True,
        handle_parsing_errors=True,
        return_intermediate_steps=True  # 返回搜索路径
    )


__all__ = ["create_auxiliary_search_agent"]
