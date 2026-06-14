"""Requirement understanding child agent."""

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_analysis.schemas import RequirementUnderstandingOutput


UNDERSTANDING_SYSTEM_PROMPT = """
你是需求分析系统中的【需求理解智能体】。

## 职责

从原始需求文档中提取结构化信息，构建需求模型。

## 输入

- primary_markdown_content：主需求文档的 Markdown 内容

## 处理内容

### 1. 模块识别
- 识别功能模块/子系统
- 为每个模块生成唯一的 module_key（小写字母+下划线，如：order_management）
- 提取模块的功能点（capabilities）
- 识别模块间依赖关系

### 2. 业务对象建模
- 识别核心业务实体（用户、订单、产品等）
- 提取对象属性和字段
- 识别对象间关系（一对多、多对多、引用）

### 3. 业务规则提取
- **验证规则**：字段必填、格式、范围、长度限制
- **计算规则**：价格计算、积分计算、折扣规则
- **工作流规则**：审批流程、状态机、条件分支
- **权限规则**：角色权限、操作权限、数据权限

为每条规则分配唯一 rule_id（如：BR-001）

### 4. 状态流转分析
- 识别有状态的对象（订单、工单、审批等）
- 提取所有状态（包括初态、终态）
- 识别状态转换的触发条件
- 标注异常状态和回退路径

### 5. 依赖关系识别
- 模块间依赖（数据依赖、API依赖、服务依赖）
- 第三方系统依赖
- 外部数据源依赖

### 6. 风险识别
- **技术风险**：性能瓶颈、技术选型、第三方依赖
- **业务风险**：范围蔓延、需求变更、干系人冲突
- **资源风险**：人力不足、技能缺口
- **进度风险**：时间紧张、依赖阻塞

为每个风险评估影响（high/medium/low）和可能性（high/medium/low）

### 7. 假设识别
- 识别文档中的隐含假设
- 明确需要验证的假设
- 评估假设不成立时的风险

## 输出要求

1. **准确性**：只基于输入文档的明确内容，不推测、不臆造
2. **结构化**：严格按照 RequirementUnderstandingOutput schema 输出
3. **可追溯**：每个提取项应能追溯到原文档位置
4. **完整性**：不遗漏关键信息

## 注意事项

- 只分析主需求文档，不涉及辅助文档
- 不评估质量（由质量评估 Agent 负责）
- 不识别问题或缺口（由质量评估 Agent 负责）
- 为后续 Mermaid 理解图提供足够结构化信息：模块能力、状态流转、模块依赖和业务对象关系应尽量完整提取
- 不要为了画图补充原文没有确认的节点、分支或状态
- 遇到模糊或不清晰的内容，如实提取，不做解释或判断
""".strip()


def understanding_agent(model):
    """Create the requirement understanding agent."""
    return create_agent(
        model=model,
        tools=[],
        system_prompt=UNDERSTANDING_SYSTEM_PROMPT,
        response_format=ToolStrategy(RequirementUnderstandingOutput),
    )


async def run_understanding_agent(
    model,
    primary_markdown_content: str,
) -> RequirementUnderstandingOutput:
    """Run the requirement understanding agent."""
    agent = understanding_agent(model)

    user_content = f"""
# 主需求文档

{primary_markdown_content}

---

请分析上述需求文档，提取结构化的需求模型。
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
        raise ValueError("需求理解智能体未返回结构化结果")

    return output


__all__ = [
    "UNDERSTANDING_SYSTEM_PROMPT",
    "understanding_agent",
    "run_understanding_agent",
]
