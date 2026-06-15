"""
业务分析器：深度理解业务需求

核心职责：
1. 识别业务痛点（要解决什么问题）
2. 提炼核心价值（用户为什么用）
3. 识别关键流程（用户怎么用）
4. 找出决策点（哪里需要做决策）
"""

from typing import Optional
from app.agents.requirement_analysis.models import (
    BusinessInsight,
    PainPoint,
    CoreValue,
    CriticalFlow,
    DecisionPoint,
)


BUSINESS_ANALYSIS_PROMPT = """
你是资深的业务架构师和产品专家。

# 需求文档
{requirement_doc}

# 分析任务

请深度分析需求（重点是理解"为什么"，而不是提取"是什么"）：

## 1. 业务领域识别
- 这个需求属于什么业务领域？（如：智能体平台、工作流引擎、知识库系统、API网关等）
- 识别依据是什么？

## 2. 业务痛点分析
不要简单复述需求，要深入推理：
- 文档背后要解决什么问题？
- 为什么现有方案不够好？
- 用户的真实诉求是什么？

示例：
```
❌ 错误："用户可以上传文档"
✅ 正确：
   痛点：用户无法利用企业私有数据训练AI
   原因：公有大模型只有通用知识，不了解企业内部情况
   诉求：让AI能理解和回答企业内部文档的问题
```

## 3. 核心价值提炼
- 这个功能的独特价值是什么？
- 用户为什么要用它而不是竞品？
- 哪个价值点是最核心的？

## 4. 关键流程识别
不要列出所有流程，只找出"决定成败"的关键流程：
- 用户使用的完整路径是什么？
- 哪些环节决定了成败？
- 哪些环节最容易出问题？

对每个关键流程：
- 描述完整的步骤
- 标注决策点（流程中的分叉口）
- 说明为什么这个流程关键

## 5. 决策点识别
决策点是流程中的"分叉口"，需要做出选择：
- 决策点是什么？
- 有哪些可能的选项？
- 决策依据是什么？
- 测试需要关注什么？

示例：
```
决策点：文档解析失败后的处理
选项：
  1. 立即返回错误给用户
  2. 静默失败，跳过该文档
  3. 重试3次后再失败
决策依据：用户体验 vs 系统可靠性
测试关注：验证每种情况下的行为
```

# 输出要求

严格按照 BusinessInsight 数据模型输出，包含：
- domain: 业务领域
- pain_points: 业务痛点列表（每个包含 description, reason, impact）
- core_values: 核心价值列表（每个包含 value, differentiation, priority）
- critical_flows: 关键流程列表（每个包含 name, description, steps, decision_points, why_critical）
- decision_points: 决策点列表（每个包含 point, options, criteria, test_concern）
- summary: 业务理解总结（3-5句话）

## 质量标准

✅ 好的分析：
- 有推理过程，不是简单复述
- 痛点具体，有场景
- 价值明确，有差异化
- 流程完整，有决策点

❌ 避免的分析：
- 简单复述需求文档
- 泛泛而谈（"提升用户体验"）
- 列出所有流程（要聚焦关键）
- 没有推理过程
"""


class BusinessAnalyzer:
    """业务分析器"""

    def __init__(self, model):
        """
        初始化业务分析器

        Args:
            model: LLM模型实例
        """
        self.model = model

    async def analyze(self, requirement_doc: str) -> BusinessInsight:
        """
        深度业务分析

        Args:
            requirement_doc: 需求文档内容

        Returns:
            BusinessInsight: 业务洞察结果
        """
        from langchain.agents import create_agent
        from langchain.agents.structured_output import ToolStrategy

        # 创建结构化输出agent
        agent = create_agent(
            model=self.model,
            tools=[],
            system_prompt=BUSINESS_ANALYSIS_PROMPT.format(
                requirement_doc=requirement_doc
            ),
            response_format=ToolStrategy(BusinessInsight),
        )

        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "请开始业务分析。",
                    }
                ]
            }
        )

        output = result.get("structured_response")
        if output is None:
            raise ValueError("业务分析器未返回结构化结果")

        return output


__all__ = ["BusinessAnalyzer"]
