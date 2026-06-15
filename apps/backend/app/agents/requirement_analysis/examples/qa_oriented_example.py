"""
QA导向需求分析架构 - 示例测试

展示如何使用新架构进行需求分析
"""

import asyncio
from app.agents.requirement_analysis.qa_orchestrator import QAOrientedRequirementOrchestrator


# 示例需求文档
EXAMPLE_REQUIREMENT = """
# 用户登录功能需求

## 功能描述
系统需要提供用户登录功能，支持用户名密码登录。

## 功能规格

### 输入
- 用户名：邮箱格式
- 密码：8-20位，必须包含大小写字母和数字

### 输出
- 成功：返回JWT token和用户基本信息
- 失败：返回错误提示

### 业务规则
1. 用户名必须在系统中已注册
2. 密码错误连续3次后锁定账号30分钟
3. Token有效期为24小时
4. 已锁定账号不允许登录

### 错误处理
- 用户名不存在：返回404 "用户不存在"
- 密码错误：返回401 "密码错误，剩余X次尝试机会"
- 账号已锁定：返回403 "账号已锁定，请X分钟后再试"
- 参数格式错误：返回400 "参数格式错误"
- 数据库连接失败：返回503 "服务暂时不可用"

### 性能要求
- 登录接口响应时间 < 500ms
- 支持并发100用户同时登录

### 安全要求
- 密码需要加密存储
- Token需要签名验证
- 登录失败需要记录日志
"""


async def test_qa_oriented_analysis():
    """测试QA导向的需求分析"""
    print("=" * 80)
    print("QA导向需求分析架构 - 示例测试")
    print("=" * 80)
    print()

    # 注意：这里需要实际的模型实例
    # 在实际环境中，需要从配置中获取模型
    print("⚠️  注意：此示例需要实际的LLM模型实例")
    print("⚠️  请在实际环境中运行，并提供模型配置")
    print()

    # 示例代码结构（需要实际模型才能运行）
    """
    from langchain_openai import ChatOpenAI

    # 初始化模型
    model = ChatOpenAI(model="gpt-4", temperature=0)

    # 创建编排器
    orchestrator = QAOrientedRequirementOrchestrator(model)

    # 执行分析
    qa_view = await orchestrator.analyze(EXAMPLE_REQUIREMENT)

    # 查看结果
    print("\n" + "=" * 80)
    print("分析结果")
    print("=" * 80)
    print()

    print(f"📊 测试清单: {len(qa_view.test_checklist)} 项")
    print(f"⚠️  风险热点: {len(qa_view.risk_hotspots)} 个")
    print(f"📈 测试覆盖率: {qa_view.coverage_analysis.coverage_percentage}%")
    print(f"✅ 可测试性评分: {qa_view.testability_assessment.score}/100")
    print()

    # 打印测试清单（P0优先级）
    print("\n" + "-" * 80)
    print("P0 测试清单")
    print("-" * 80)
    for item in qa_view.test_checklist:
        if item.priority == "P0":
            print(f"\n## {item.id}: {item.feature}")
            print(item.given_when_then)
            print(f"断言点:")
            for point in item.assertion_points:
                print(f"  - {point}")

    # 打印数据流图
    print("\n" + "-" * 80)
    print("数据流图")
    print("-" * 80)
    print("```mermaid")
    print(qa_view.data_flow_diagram)
    print("```")

    # 打印功能地图
    if qa_view.feature_map_diagram:
        print("\n" + "-" * 80)
        print("功能地图")
        print("-" * 80)
        print("```mermaid")
        print(qa_view.feature_map_diagram)
        print("```")

    # 打印总结
    print("\n" + "-" * 80)
    print("QA视图总结")
    print("-" * 80)
    print(qa_view.summary)
    """

    print("\n✨ 示例代码展示完成")
    print("\n预期输出内容：")
    print("  1. 测试场景提取（Given-When-Then格式）")
    print("  2. 功能点清单（输入、输出、前置条件、异常路径）")
    print("  3. 数据流图（Mermaid）")
    print("  4. 风险热点识别")
    print("  5. 可测试性评估（评分 + 阻塞项）")
    print("  6. 统一的QA视图")


def print_architecture_comparison():
    """打印架构对比"""
    print("\n" + "=" * 80)
    print("架构对比：现有 vs 改进")
    print("=" * 80)
    print()

    comparison = """
| 维度           | 现有架构                     | 改进架构                          |
|----------------|------------------------------|-----------------------------------|
| **核心视角**   | 开发理解（痛点、价值、实体） | 测试场景（Given-When-Then）       |
| **输出格式**   | 业务洞察 + 领域模型 + 风险画像| 测试清单 + 风险热点 + 覆盖度      |
| **可视化**     | 只有状态机                   | 数据流图 + 功能地图 + 状态机 + 覆盖度图 |
| **Token使用**  | 全量传递（可能80KB+）        | 摘要传递（约10KB）                |
| **可测试性**   | 事后评估                     | 前置评估 + 阻塞项识别             |
| **QA友好度**   | 需要跨多个输出查找信息       | 统一QA视图，一站式                |
| **完整性保障** | 依赖人工检查                 | 覆盖度分析 + 可测试性评分         |

## 核心改进点

### 1. 测试场景优先
- ✅ Given-When-Then格式
- ✅ 具体的断言点
- ✅ 测试数据示例
- ✅ 优先级排序

### 2. Token优化
- ✅ 只传递摘要，不传完整JSON
- ✅ 截断长文档，保留核心部分
- ✅ Token使用量减少50%+

### 3. 可视化增强
- ✅ 数据流图（Mermaid flowchart）
- ✅ 功能地图（Mermaid mindmap）
- ✅ 状态机图（继承自领域建模）
- ✅ 覆盖度分析

### 4. 可测试性评估
- ✅ 7大检查项
- ✅ 模糊描述识别
- ✅ 断言点验证
- ✅ 异常场景覆盖检查
- ✅ 阻塞项识别

### 5. 统一QA视图
- ✅ 测试清单（按优先级）
- ✅ 风险热点汇总
- ✅ 覆盖度分析
- ✅ 所有图表集成
- ✅ 一站式测试信息
"""

    print(comparison)


def print_usage_guide():
    """打印使用指南"""
    print("\n" + "=" * 80)
    print("使用指南")
    print("=" * 80)
    print()

    guide = """
## 基本用法

```python
from langchain_openai import ChatOpenAI
from app.agents.requirement_analysis.qa_orchestrator import QAOrientedRequirementOrchestrator

# 1. 初始化模型
model = ChatOpenAI(model="gpt-4", temperature=0)

# 2. 创建编排器
orchestrator = QAOrientedRequirementOrchestrator(model)

# 3. 执行完整分析（包含领域建模）
qa_view = await orchestrator.analyze(requirement_doc)

# 4. 或者执行简化分析（只提取测试场景）
test_scenarios = await orchestrator.analyze_simple(requirement_doc)
```

## 获取分析结果

```python
# 测试清单
for item in qa_view.test_checklist:
    print(f"{item.id}: {item.feature} [{item.priority}]")
    print(item.given_when_then)
    print(f"断言点: {item.assertion_points}")

# 风险热点
for risk in qa_view.risk_hotspots:
    print(f"{risk.area}: {risk.risk} [{risk.priority}]")

# 覆盖度分析
coverage = qa_view.coverage_analysis
print(f"覆盖率: {coverage.coverage_percentage}%")
print(f"不可测试功能: {coverage.gaps}")

# 可测试性评估
testability = qa_view.testability_assessment
print(f"评分: {testability.score}/100")
print(f"是否允许知识库生成: {testability.allow_knowledge_generation}")
```

## 可视化图表

```python
# 数据流图
print(qa_view.data_flow_diagram)  # Mermaid代码

# 功能地图
print(qa_view.feature_map_diagram)  # Mermaid代码

# 状态机
for sm in qa_view.state_machines:
    print(sm)  # Mermaid代码
```

## 与现有架构对比

```python
# 现有架构
from app.agents.requirement_analysis.orchestrator import DeepUnderstandingOrchestrator
old_orchestrator = DeepUnderstandingOrchestrator(model)
old_result = await old_orchestrator.analyze(requirement_doc)
# 输出：DeepUnderstandingResult (业务洞察 + 领域模型 + 风险画像)

# 新架构
new_orchestrator = QAOrientedRequirementOrchestrator(model)
new_result = await new_orchestrator.analyze(requirement_doc)
# 输出：QARequirementView (测试清单 + 风险热点 + 覆盖度 + QA视图)
```

## 配置选项

```python
# 不包含领域建模（更快，Token更少）
qa_view = await orchestrator.analyze(
    requirement_doc,
    include_domain_model=False
)

# 简化模式（最快，只提取测试场景）
test_scenarios = await orchestrator.analyze_simple(requirement_doc)
```
"""

    print(guide)


def main():
    """主函数"""
    # 打印架构对比
    print_architecture_comparison()

    # 打印使用指南
    print_usage_guide()

    # 运行示例测试
    asyncio.run(test_qa_oriented_analysis())


if __name__ == "__main__":
    main()
