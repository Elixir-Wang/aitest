"""
领域建模器：构建系统的心智模型

核心职责：
1. 识别核心概念（对象的本质）
2. 分析对象关系（依赖、约束）
3. 提取不变性约束（永远不能违反的规则）
4. 构建状态机（对象如何变化）
"""

from typing import Optional
from app.agents.requirement_analysis.models import (
    BusinessInsight,
    DomainModel,
    CoreConcept,
    DomainEntity,
    Invariant,
    StateMachine,
)


DOMAIN_MODELING_PROMPT = """
你是DDD（领域驱动设计）专家和系统架构师。

# 需求文档
{requirement_doc}

# 业务分析结果
{business_insight_json}

# 建模任务

请构建领域模型（重点是理解本质，不是罗列信息）：

## 1. 核心概念识别

不是找"名词"，而是找"核心抽象"：
- 这个系统的核心概念是什么？
- 为什么这些概念是核心的？
- 它们解决了什么业务问题？

示例：
```
对于智能体平台：
✅ 核心概念：智能体（Agent）
   本质：用户定义的AI能力封装，包含模型+知识+工具
   为什么核心：整个平台围绕"创建和使用智能体"展开

✅ 核心概念：会话（Conversation）
   本质：用户与智能体的交互过程
   为什么核心：体现智能体的价值（通过对话完成任务）

❌ 非核心概念：配置项、日志记录
   这些是技术细节，不是业务核心
```

## 2. 对象本质分析

对每个核心对象，理解其存在意义：
- 它为什么需要存在？
- 它的生命周期是什么样的？（诞生→成长→死亡）
- 它的关键属性是什么？（不要列全部字段，只列核心的）
- 它与其他对象的关系是什么？

示例：
```
对象：智能体
存在意义：封装用户定义的AI能力，让非技术用户也能创建AI应用
生命周期：创建（草稿）→ 配置（添加知识、工具）→ 测试 → 发布 → 运行 → 下线/删除
关键属性：
  - name: 智能体名称
  - model_config: 模型配置
  - status: 状态（草稿/已发布）
关系：
  - 属于一个用户（创建者）
  - 包含多个知识库
  - 产生多个会话
```

## 3. 不变性约束提取

找出"永远不能被违反"的规则：
- 哪些规则是不变的？
- 为什么这个约束重要？
- 违反会导致什么后果？
- 如何测试验证？

示例：
```
约束：会话必须属于某个智能体
重要性：孤儿会话没有意义，无法处理用户消息
违反后果：系统无法找到对应的模型和配置，会话无法工作
测试验证：尝试创建没有agent_id的会话，应该被拒绝
```

## 4. 状态机构建

对有状态的对象，构建完整的状态机：
- 对象有哪些状态？
- 为什么需要这些状态？
- 状态转换的条件是什么？
- 哪些转换最容易出问题？
- 异常路径是什么？

要求：
- 状态要完整（包括异常状态）
- 转换要明确（条件、触发事件）
- 标注风险点（容易出问题的转换）
- 生成Mermaid状态图代码

示例：
```
对象：智能体
状态：草稿、已发布、已下线、已删除

转换：
1. 草稿 → 已发布
   条件：配置完整（有模型、有提示词）
   触发：用户点击"发布"

2. 已发布 → 草稿
   条件：无限制
   触发：用户点击"下线"

3. 已发布 → 已删除
   条件：无进行中的会话
   触发：用户点击"删除"
   风险点：如果有进行中的会话，删除会导致会话失败

状态图（Mermaid）：
stateDiagram-v2
    [*] --> 草稿: 用户创建
    草稿 --> 已发布: 发布
    已发布 --> 草稿: 下线
    草稿 --> 已删除: 删除
    已发布 --> 已删除: 删除
    已删除 --> [*]: 30天后
```

# 输出要求

严格按照 DomainModel 数据模型输出，包含：
- core_concepts: 核心概念列表
- entities: 领域实体列表
- invariants: 不变性约束列表
- state_machines: 状态机列表
- summary: 领域模型总结

## 质量标准

✅ 好的建模：
- 理解对象的"为什么存在"
- 不变性约束明确、可验证
- 状态机完整（包括异常路径）
- 有推理过程

❌ 避免的建模：
- 罗列所有字段（数据库表设计）
- 缺少关系分析
- 状态机不完整
- 没有解释"为什么"
"""


class DomainModeler:
    """领域建模器"""

    def __init__(self, model):
        """
        初始化领域建模器

        Args:
            model: LLM模型实例
        """
        self.model = model

    async def build_model(
        self,
        requirement_doc: str,
        business_insight: BusinessInsight
    ) -> DomainModel:
        """
        构建领域模型

        Args:
            requirement_doc: 需求文档内容
            business_insight: 业务洞察结果

        Returns:
            DomainModel: 领域模型结果
        """
        from langchain.agents import create_agent
        from langchain.agents.structured_output import ToolStrategy

        # 创建结构化输出agent
        agent = create_agent(
            model=self.model,
            tools=[],
            system_prompt=DOMAIN_MODELING_PROMPT.format(
                requirement_doc=requirement_doc,
                business_insight_json=business_insight.model_dump_json(indent=2)
            ),
            response_format=ToolStrategy(DomainModel),
        )

        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "请开始领域建模。",
                    }
                ]
            }
        )

        output = result.get("structured_response")
        if output is None:
            raise ValueError("领域建模器未返回结构化结果")

        return output


__all__ = ["DomainModeler"]
