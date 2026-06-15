"""
可测试性评估器：评估需求的可测试性

核心职责：
1. 检查输入输出明确性
2. 识别模糊描述
3. 验证断言点
4. 检查前置条件完整性
5. 评估异常场景覆盖
6. 检查状态机完整性
7. 生成可测试性评分
"""

from typing import Optional
from app.agents.requirement_analysis.models import (
    TestScenarioInsight,
    DomainModel,
    TestabilityAssessment,
    TestabilityIssue,
)


TESTABILITY_ASSESSMENT_PROMPT = """
你是资深的测试架构师和质量专家。

# 测试场景分析结果
{test_scenarios_json}

# 领域模型
{domain_model_json}

# 任务目标

评估需求的**可测试性**，识别阻塞测试的问题。

## 评估维度

### 1. 输入输出明确性
检查每个功能点是否有明确的输入和输出：
- ✅ 好：输入=[用户名, 密码]，输出=[JWT token, 用户信息]
- ❌ 差：输入=[用户凭证]，输出=[认证结果]

### 2. 模糊描述检查
识别无法量化的描述：
- ❌ "系统应该快" → 没有具体指标
- ❌ "用户体验应该好" → 无法验证
- ❌ "密码强度应该合理" → "合理"无法定义
- ❌ "系统尽量保证数据一致性" → "尽量"不是约束
- ✅ "页面加载时间 < 2秒" → 可测试
- ✅ "密码长度 >= 8字符且包含大小写字母和数字" → 可测试

**模糊词汇清单**：
- 合理、适当、尽量、酌情、适度
- 快、慢、好、差、高、低
- 稳定、可靠、安全（没有具体指标时）

### 3. 断言点验证
检查每个测试场景是否有明确的断言点：
- ✅ 好：["状态码=200", "响应包含access_token", "token未过期"]
- ❌ 差：["验证成功"]

### 4. 提示语明确性
检查是否明确了所有提示文案：
- ❌ 差："提示用户操作失败"
- ✅ 好："提示'密码错误，请重新输入'"

### 5. 前置条件完整性
检查测试前置条件是否可构造：
- ✅ 好："用户已注册（username=test@example.com）且账号未锁定"
- ❌ 差："在有数据的情况下测试查询"

### 6. 异常场景覆盖
检查是否至少覆盖以下异常类型：
- 校验失败（参数错误）
- 权限不足（403）
- 依赖缺失（404）
- 网络异常（503）
- 超时（504）

### 7. 状态机完整性
检查状态流转是否闭环：
- 每个状态都有来源
- 每个状态都有去向
- 没有孤立状态

## 问题分类

**vague_description**: 模糊描述
- 示例："系统应该快"、"用户体验好"

**missing_assertion**: 缺少断言点
- 示例：测试场景没有具体的验证点

**unclear_precondition**: 前置条件不清
- 示例："在有数据的情况下"

**missing_exception**: 缺少异常场景
- 示例：只有正常流程，没有错误处理

**incomplete_state_machine**: 状态机不完整
- 示例：有"处理中"状态但无法进入或退出

## 评分规则

**基础分**: 100分

**扣分项**:
- 每个模糊描述：-5分
- 每个缺少断言点的场景：-10分
- 每个前置条件不清的场景：-8分
- 缺少异常场景覆盖：-15分
- 状态机不完整：-10分

**最低分**: 0分

**评级**:
- 90-100分：优秀，可直接进入知识库生成
- 80-89分：良好，建议补充后再生成
- 60-79分：一般，必须补充澄清
- <60分：差，阻塞知识库生成

## 阻塞标准

以下问题会**阻塞知识库生成**：
1. 可测试性评分 < 80分
2. 存在核心功能（P0）的模糊描述
3. 核心功能缺少断言点
4. 完全没有异常场景覆盖
5. 状态机存在孤立状态

## 输出要求

严格按照 **TestabilityAssessment** 数据模型输出，包含：
- **score**: 可测试性评分（0-100）
- **testable_features**: 可测试功能列表（功能名称）
- **untestable_features**: 不可测试功能列表（TestabilityIssue列表）
- **blocking_issues**: 阻塞项列表（简短描述）
- **allow_knowledge_generation**: 是否允许进入知识库生成（boolean）
- **summary**: 评估总结（说明评分原因和主要问题）

## 示例

### 示例1: 可测试的需求（评分95）
```
功能：用户登录
输入：[用户名, 密码]
输出：[JWT token, 用户信息]
异常场景：密码错误→401, 账号锁定→403
断言点：[状态码=200, 包含access_token, token未过期]

评估：
- ✅ 输入输出明确
- ✅ 有异常场景
- ✅ 断言点具体
- ✅ 前置条件清晰

评分：95分（扣5分因为缺少提示语具体文案）
```

### 示例2: 不可测试的需求（评分60）
```
功能：系统应该稳定运行
描述：确保系统性能良好，用户体验流畅

评估：
- ❌ "稳定"无法量化
- ❌ "性能良好"无指标
- ❌ "用户体验流畅"无法验证
- ❌ 缺少异常场景
- ❌ 没有断言点

评分：60分
阻塞：是
问题：
1. [vague_description] "稳定运行"无法量化
2. [vague_description] "性能良好"缺少具体指标
3. [missing_assertion] 缺少可验证的断言点
4. [missing_exception] 缺少异常场景

建议：
- 将"稳定"量化为"99.9%可用率"
- 将"性能良好"具体化为"响应时间<500ms"
- 补充异常场景和断言点
```

## 质量标准

✅ 好的评估：
- 评分有依据
- 问题具体
- 建议可执行
- 阻塞判断准确

❌ 避免：
- 评分过于宽松或严格
- 泛泛而谈的问题
- 没有改进建议
"""


class TestabilityAssessor:
    """可测试性评估器"""

    def __init__(self, model):
        """
        初始化可测试性评估器

        Args:
            model: LLM模型实例
        """
        self.model = model

    async def assess(
        self,
        test_scenarios: TestScenarioInsight,
        domain_model: Optional[DomainModel] = None
    ) -> TestabilityAssessment:
        """
        评估可测试性

        Args:
            test_scenarios: 测试场景洞察
            domain_model: 领域模型（可选，用于状态机检查）

        Returns:
            TestabilityAssessment: 可测试性评估结果
        """
        from langchain.agents import create_agent
        from langchain.agents.structured_output import ToolStrategy

        # 准备输入
        domain_model_json = "无领域模型"
        if domain_model:
            domain_model_json = domain_model.model_dump_json(indent=2)

        # 创建结构化输出agent
        agent = create_agent(
            model=self.model,
            tools=[],
            system_prompt=TESTABILITY_ASSESSMENT_PROMPT.format(
                test_scenarios_json=test_scenarios.model_dump_json(indent=2),
                domain_model_json=domain_model_json
            ),
            response_format=ToolStrategy(TestabilityAssessment),
        )

        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "请开始可测试性评估。",
                    }
                ]
            }
        )

        output = result.get("structured_response")
        if output is None:
            raise ValueError("可测试性评估器未返回结构化结果")

        return output


__all__ = ["TestabilityAssessor"]
