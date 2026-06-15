"""
测试场景提取器：从QA视角理解需求

核心职责：
1. 提取功能点清单（What to test）
2. 生成测试场景（How to test，Given-When-Then）
3. 识别数据流转（Test data preparation）
4. 识别风险热点（What to test first）
5. 生成可视化图表（Mermaid）
"""

from typing import Optional
from app.agents.requirement_analysis.models import (
    TestScenarioInsight,
    FeatureSpec,
    TestScenario,
    DataFlowEdge,
    RiskHotspot,
)


TEST_SCENARIO_EXTRACTION_PROMPT = """
你是资深的测试架构师和QA专家。

# 需求文档
{requirement_doc}

# 任务目标

从**测试视角**分析需求，帮助QA人员理解"如何测试"，而不是"为什么需要"。

## 1. 功能点提取（What to test）

从需求中提取所有可测试的功能点，对每个功能点：
- **输入是什么？** 用户或系统提供的数据
- **输出是什么？** 预期的响应、界面变化、数据变化
- **前置条件是什么？** 执行前必须满足的状态
- **正常路径是什么？** Happy Path的完整描述
- **异常路径有哪些？** 校验失败、权限不足、依赖缺失、网络失败等
- **边界条件在哪里？** 字段长度上下限、空值、特殊字符、重复值

示例：
```
功能点：用户登录
前置条件：["用户已注册", "账号未被锁定"]
输入：["用户名", "密码"]
输出：["JWT token", "用户信息"]
正常路径：输入正确凭证 → 验证通过 → 返回token
异常路径：
  - 用户名不存在 → 返回404 "用户不存在"
  - 密码错误 → 返回401 "密码错误"
  - 账号锁定 → 返回403 "账号已锁定"
  - 数据库连接失败 → 返回503 "服务暂时不可用"
边界条件：
  - 密码长度 < 8 → 拒绝
  - 连续失败 3 次 → 锁定账号
  - 用户名包含特殊字符 → 如何处理？
```

## 2. 测试场景生成（How to test）

为每个功能点生成 **Given-When-Then** 测试场景：

**格式要求：**
- **Given**: 前置条件和初始状态（具体、可构造）
- **When**: 执行的操作（明确的动作）
- **Then**: 预期的结果（可验证的断言点）

**覆盖类型：**
- **functional**: 正常功能测试（Happy Path）
- **negative**: 异常测试（错误处理）
- **boundary**: 边界值测试（临界点）
- **concurrency**: 并发测试（竞态条件）

**优先级判断：**
- **P0**: 核心功能、资损风险、数据一致性
- **P1**: 重要功能、用户体验
- **P2**: 边界场景、异常处理
- **P3**: 补充测试、优化验证

示例：
```
场景ID: TC-001
标题: 正常登录
Given: 用户已注册（username=test@example.com）且账号未锁定
When: 输入正确的用户名和密码
Then: 返回200和有效的JWT token
测试类型: functional
优先级: P0
断言点:
  - 状态码 = 200
  - 响应包含 access_token 字段
  - token 可解析且未过期
  - token 包含正确的用户信息
测试数据: {{"username": "test@example.com", "password": "Test123!"}}

场景ID: TC-002
标题: 密码错误
Given: 用户已注册
When: 输入错误的密码
Then: 返回401且不生成token
测试类型: negative
优先级: P1
断言点:
  - 状态码 = 401
  - 响应包含错误提示 "密码错误"
  - 未生成 token
  - 失败计数器 +1

场景ID: TC-003
标题: 密码长度边界测试
Given: 用户尝试登录
When: 输入7字符密码（低于最小长度8）
Then: 返回400参数错误
测试类型: boundary
优先级: P2
断言点:
  - 状态码 = 400
  - 错误提示 "密码长度必须至少8个字符"

场景ID: TC-004
标题: 并发登录
Given: 同一用户
When: 两个客户端同时发起登录请求
Then: 两次登录都成功，生成不同的token
测试类型: concurrency
优先级: P1
断言点:
  - 两次都返回200
  - 生成的token不同
  - 两个token都有效
```

## 3. 风险热点识别（What to test first）

识别测试风险热点，重点关注：
- **逻辑复杂**：状态多、转换多、条件多
- **并发场景**：多用户同时操作、竞态条件
- **异步处理**：时序问题、超时处理
- **外部依赖**：第三方服务、数据库、缓存
- **数据一致性**：跨模块数据同步、事务边界

示例：
```
风险区域: 账号锁定逻辑
风险: 并发登录导致失败计数不准确
复杂度来源: concurrency
优先级: P0
测试策略: 使用并发测试工具模拟10个线程同时登录失败，验证计数器准确性和锁定触发
```

## 4. 数据依赖分析（Test data preparation）

识别测试数据依赖关系，帮助QA准备测试数据：
- 数据从哪里来？到哪里去？
- 数据流转中有哪些校验？
- 哪些地方可能出错？

生成 **Mermaid 数据流图**：
```mermaid
graph TD
    User[用户输入] -->|用户名+密码| Auth[认证服务]
    Auth -->|查询用户| DB[(用户数据库)]
    DB -->|用户信息| Auth
    Auth -->|验证失败| Error[返回401错误]
    Auth -->|验证成功| Token[生成JWT Token]
    Token -->|Token| User

    style Auth fill:#e1f5ff
    style DB fill:#fff4e6
    style Error fill:#ffebee
    style Token fill:#e8f5e9
```

**图表要求：**
- 使用 `graph TD` 或 `graph LR` 格式
- 节点名称简洁清晰
- 箭头标注数据内容
- 用颜色区分不同类型节点（可选）
- 标注风险点（可选）

## 输出要求

严格按照 **TestScenarioInsight** 数据模型输出，包含：
- **features**: 功能点清单（FeatureSpec列表）
- **test_scenarios**: 测试场景清单（TestScenario列表，按优先级排序）
- **data_flow**: 数据流转列表（DataFlowEdge列表）
- **data_flow_mermaid**: Mermaid数据流图（完整的mermaid代码）
- **risk_hotspots**: 风险热点列表（RiskHotspot列表）
- **summary**: 测试场景总结（3-5句话，说明测试重点）

## 质量标准

✅ 好的测试场景提取：
- 测试场景具体、可执行
- Given-When-Then 明确
- 断言点具体、可验证
- 覆盖正常/异常/边界/并发
- 风险评估准确
- 数据流图清晰完整
- Mermaid语法正确

❌ 避免：
- 泛泛而谈（"系统应该稳定"）
- 缺少具体场景
- 没有断言点
- 忽略边界和异常
- 所有场景都是P0
- Mermaid图缺失或格式错误

## 注意事项

1. **优先级分配要合理**：不是所有测试都是P0，核心功能、资损风险才是P0
2. **测试数据要具体**：提供可直接使用的测试数据示例
3. **断言点要明确**：不要说"验证成功"，要说"状态码=200且响应包含access_token"
4. **覆盖要全面**：每个功能至少包含正常场景和一个异常场景
5. **Mermaid图要完整**：包含所有关键数据流转路径
"""


class TestScenarioExtractor:
    """测试场景提取器"""

    def __init__(self, model):
        """
        初始化测试场景提取器

        Args:
            model: LLM模型实例
        """
        self.model = model

    async def extract(self, requirement_doc: str) -> TestScenarioInsight:
        """
        提取测试场景

        Args:
            requirement_doc: 需求文档内容

        Returns:
            TestScenarioInsight: 测试场景洞察结果
        """
        from langchain.agents import create_agent
        from langchain.agents.structured_output import ToolStrategy

        # 创建结构化输出agent
        agent = create_agent(
            model=self.model,
            tools=[],
            system_prompt=TEST_SCENARIO_EXTRACTION_PROMPT.format(
                requirement_doc=requirement_doc
            ),
            response_format=ToolStrategy(TestScenarioInsight),
        )

        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "请开始测试场景提取。",
                    }
                ]
            }
        )

        output = result.get("structured_response")
        if output is None:
            raise ValueError("测试场景提取器未返回结构化结果")

        return output


__all__ = ["TestScenarioExtractor"]
