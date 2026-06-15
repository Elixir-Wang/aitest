"""
风险识别器：找出容易出bug的地方

核心职责：
1. 识别复杂场景（逻辑复杂、容易出错）
2. 分析风险根因（为什么会出问题）
3. 识别边界条件（系统的边界在哪里）
4. 制定测试策略（如何测试验证）
"""

from typing import Optional
from app.agents.requirement_analysis.models import (
    BusinessInsight,
    DomainModel,
    RiskProfile,
    ComplexScenario,
    RiskRootCause,
    BoundaryCondition,
    TestStrategy,
)


RISK_IDENTIFICATION_PROMPT = """
你是资深的测试架构师和质量专家。

# 需求文档
{requirement_doc}

# 业务分析结果
{business_insight_json}

# 领域模型
{domain_model_json}

# 风险识别任务

请识别测试风险（重点是理解"为什么"有风险，而不是泛泛而谈）：

## 1. 复杂场景识别

不要说"XX功能复杂"，要具体分析：
- 哪些场景逻辑复杂、容易出错？
- 为什么这里复杂？
- 复杂度来源是什么？

复杂度来源分类：
- state_machine: 状态多、转换多
- concurrency: 并发操作、竞态条件
- async: 异步处理、时序问题
- external_dependency: 依赖外部服务（不可控）
- business_rule: 业务规则复杂、条件多

示例：
```
❌ 错误："订单处理很复杂"
✅ 正确：
   场景：订单支付后的库存扣减
   为什么复杂：涉及多个系统（订单、库存、支付）的数据一致性
   复杂度来源：async + external_dependency
   影响：高（资损风险）
```

## 2. 风险根因分析

不要说"并发风险""性能风险"这种泛泛的话，要分析：
- 具体什么操作在什么条件下会出问题？
- 为什么会出问题？（根本原因）
- 什么场景下会触发？
- 后果是什么？
- 发生概率如何？

示例：
```
风险：智能体配置冲突
根因：用户A和用户B同时修改同一智能体的配置，后提交者会覆盖前者的修改
触发条件：两个用户在5秒内对同一智能体进行修改操作
后果：配置丢失，用户投诉
概率：中等（团队协作场景下会发生）
```

## 3. 边界条件识别

找出系统的"临界点"：
- 系统的边界在哪里？
- 边界处的行为是否明确？
- 超过边界会怎样？
- 如何测试边界？

示例：
```
边界：知识库存储空间上限（免费用户100MB）
边界行为：
  - 已用99MB，上传1.5MB文件 → 返回"空间不足"
  - 已用99MB，上传0.5MB文件 → 成功
超出边界：拒绝上传，提示升级套餐
测试用例：
  - 正好到达上限（100MB）
  - 超过1KB
  - 批量上传导致超限
```

## 4. 测试策略设计

针对每个风险，设计测试策略：
- 如何构造测试场景？
- 如何验证是否有问题？
- 验证的断言点是什么？
- 优先级如何？

示例：
```
风险：LLM响应超时
测试策略：模拟LLM慢响应场景
测试场景：
  1. LLM响应时间25秒（在超时阈值内）
  2. LLM响应时间35秒（超过30秒超时）
  3. LLM完全无响应
断言点：
  - 超时后返回明确的错误信息
  - 不阻塞其他用户请求
  - 超时计数器正确记录
优先级：P0（影响用户体验）
```

# 输出要求

严格按照 RiskProfile 数据模型输出，包含：
- complex_scenarios: 复杂场景列表
- root_causes: 风险根因列表
- boundary_conditions: 边界条件列表
- test_strategies: 测试策略列表
- summary: 风险总结

## 质量标准

✅ 好的风险识别：
- 风险具体，有场景，有根因
- 不泛泛而谈
- 测试策略可执行
- 有优先级判断

❌ 避免的风险识别：
- "性能风险""安全风险"（太宽泛）
- 没有根因分析
- 测试策略不可执行
- 所有风险都是P0
"""


class RiskIdentifier:
    """风险识别器"""

    def __init__(self, model):
        """
        初始化风险识别器

        Args:
            model: LLM模型实例
        """
        self.model = model

    async def identify(
        self,
        requirement_doc: str,
        business_insight: BusinessInsight,
        domain_model: DomainModel
    ) -> RiskProfile:
        """
        识别测试风险

        Args:
            requirement_doc: 需求文档内容
            business_insight: 业务洞察结果
            domain_model: 领域模型结果

        Returns:
            RiskProfile: 风险画像结果
        """
        from langchain.agents import create_agent
        from langchain.agents.structured_output import ToolStrategy

        # 创建结构化输出agent
        agent = create_agent(
            model=self.model,
            tools=[],
            system_prompt=RISK_IDENTIFICATION_PROMPT.format(
                requirement_doc=requirement_doc,
                business_insight_json=business_insight.model_dump_json(indent=2),
                domain_model_json=domain_model.model_dump_json(indent=2)
            ),
            response_format=ToolStrategy(RiskProfile),
        )

        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "请开始风险识别。",
                    }
                ]
            }
        )

        output = result.get("structured_response")
        if output is None:
            raise ValueError("风险识别器未返回结构化结果")

        return output


__all__ = ["RiskIdentifier"]
