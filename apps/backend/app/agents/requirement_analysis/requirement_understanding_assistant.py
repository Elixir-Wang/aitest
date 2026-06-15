"""
需求快速理解助手

提供3-5分钟的快速理解能力：
- 智能摘要
- 功能地图
- 核心流程图
- 快速FAQ
"""

from app.agents.requirement_analysis.models import (
    SmartSummary,
    FAQItem,
    QuickUnderstandingView,
)


class RequirementUnderstandingAssistant:
    """需求快速理解助手"""

    def __init__(self, model):
        """
        初始化

        Args:
            model: LLM模型实例
        """
        self.model = model

    async def generate_quick_view(self, requirement_doc: str) -> QuickUnderstandingView:
        """
        生成快速理解视图（3-5分钟）

        Args:
            requirement_doc: 需求文档内容

        Returns:
            QuickUnderstandingView: 快速理解视图
        """
        # 1. 生成智能摘要
        summary = await self._generate_summary(requirement_doc)

        # 2. 生成功能地图
        feature_map = await self._generate_feature_map(requirement_doc)

        # 3. 生成核心流程图
        core_flow = await self._generate_core_flow(requirement_doc)

        # 4. 生成快速FAQ
        faq = await self._generate_faq(requirement_doc)

        return QuickUnderstandingView(
            summary=summary,
            feature_map_diagram=feature_map,
            core_flow_diagram=core_flow,
            faq=faq,
        )

    async def _generate_summary(self, doc: str) -> SmartSummary:
        """生成智能摘要"""
        prompt = f"""你是一位测试专家，需要快速理解需求文档。

## 任务
阅读需求文档，用最简洁的方式提炼核心信息，帮助QA在3分钟内理解需求。

## 需求文档
{doc}

## 提炼要求
1. **核心功能**：一句话说清楚这个需求是干什么的（30字以内）
2. **主要变更**：列出3-5个关键变更点，每条15字以内
3. **影响模块**：列出受影响的模块/系统（如：用户模块、支付模块）
4. **关键风险**：最多3个最需要关注的风险点（如：并发问题、数据一致性）
5. **复杂度估计**：low/medium/high

## 注意事项
- 面向QA，不是开发人员
- 突出"测试需要关注什么"
- 避免技术细节，聚焦功能和风险
"""
        return await self.model.generate_structured(prompt, SmartSummary)

    async def _generate_feature_map(self, doc: str) -> str:
        """生成功能地图（Mermaid mindmap）"""
        prompt = f"""你是一位测试专家，需要将需求可视化为功能地图。

## 任务
阅读需求文档，生成Mermaid mindmap格式的功能地图，帮助QA快速了解功能结构。

## 需求文档
{doc}

## Mermaid mindmap要求
1. **根节点**：需求的核心主题（如：邮箱登录功能）
2. **一级节点**：主要功能模块（如：登录验证、账号管理、安全控制）
3. **二级节点**：具体功能点（如：格式校验、密码验证、失败锁定）
4. 最多3层，避免过于复杂

## 示例格式
```mermaid
mindmap
  root((邮箱登录))
    登录验证
      格式校验
      密码验证
      验证码
    账号管理
      注册
      找回密码
    安全控制
      失败锁定
      并发登录
```

## 注意事项
- 只输出mermaid代码块，不要其他内容
- 节点名称简短（5字以内）
- 突出测试关注的功能点
"""
        response = await self.model.generate_text(prompt)
        # 提取mermaid代码块
        if "```mermaid" in response:
            start = response.find("```mermaid") + 10
            end = response.find("```", start)
            return response[start:end].strip()
        return response.strip()

    async def _generate_core_flow(self, doc: str) -> str:
        """生成核心流程图（Mermaid flowchart）"""
        prompt = f"""你是一位测试专家，需要将需求的核心流程可视化。

## 任务
阅读需求文档，生成Mermaid flowchart格式的核心流程图，帮助QA理解用户如何使用功能。

## 需求文档
{doc}

## Mermaid flowchart要求
1. **起点**：用户从哪里开始
2. **关键步骤**：只包含主流程的关键步骤（5-10个节点）
3. **决策点**：用菱形表示分支（如：验证成功？）
4. **异常流程**：标注主要异常路径
5. 使用简洁的节点名称

## 示例格式
```mermaid
flowchart TD
    Start([用户进入登录页]) --> Input[输入邮箱和密码]
    Input --> Validate{{格式校验}}
    Validate -->|失败| Error1[提示格式错误]
    Validate -->|成功| Auth[验证账号密码]
    Auth -->|失败| Check{{失败次数检查}}
    Check -->|<5次| Error2[提示错误，重试]
    Check -->|≥5次| Lock[锁定账号]
    Auth -->|成功| Success([登录成功])
```

## 注意事项
- 只输出mermaid代码块，不要其他内容
- 节点名称简短清晰
- 突出测试关注的决策点和异常路径
"""
        response = await self.model.generate_text(prompt)
        # 提取mermaid代码块
        if "```mermaid" in response:
            start = response.find("```mermaid") + 10
            end = response.find("```", start)
            return response[start:end].strip()
        return response.strip()

    async def _generate_faq(self, doc: str) -> list[FAQItem]:
        """生成快速FAQ（10个常见问题）"""
        prompt = f"""你是一位测试专家，需要为需求文档生成FAQ。

## 任务
阅读需求文档，生成10个QA最关心的问题及答案。

## 需求文档
{doc}

## FAQ要求
1. **数量**：正好10个问题
2. **问题类型**：覆盖功能、数据、流程、边界、异常、性能、依赖等
3. **问题风格**：QA视角，关注"怎么测"、"什么情况"、"怎么判断"
4. **答案要求**：简短明确，30字左右

## 问题示例
- Q: 邮箱格式校验规则是什么？
- Q: 密码错误多少次会锁定账号？
- Q: 锁定后多久自动解锁？
- Q: 并发登录是否允许？
- Q: 登录失败如何提示用户？
- Q: 是否支持第三方邮箱？
- Q: 密码加密方式是什么？
- Q: 登录超时时间是多久？
- Q: 如何测试账号锁定功能？
- Q: 异常情况下如何保证数据一致性？

## 分类要求
每个问题必须归类到以下之一：
- 功能：功能是否支持
- 数据：数据格式、校验、存储
- 流程：操作步骤、流转逻辑
- 边界：边界值、极限情况
- 异常：错误处理、异常场景
- 性能：响应时间、并发处理
- 依赖：外部依赖、第三方服务
- 其他：其他关注点
"""
        return await self.model.generate_structured(
            prompt,
            list[FAQItem],
            description="生成10个FAQ问题"
        )
