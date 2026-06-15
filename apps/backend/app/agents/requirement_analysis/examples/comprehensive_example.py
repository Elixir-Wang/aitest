"""
综合需求分析使用示例

展示如何使用ComprehensiveQAOrchestrator进行完整的需求分析
"""

import asyncio
from app.agents.requirement_analysis.comprehensive_orchestrator import ComprehensiveQAOrchestrator


async def example_comprehensive_analysis():
    """完整分析示例"""

    # 示例需求文档
    requirement_doc = """
# 邮箱登录功能需求

## 功能描述
用户可以使用邮箱和密码进行登录，支持常见邮箱格式（如Gmail、QQ邮箱等）。

## 功能详情

### 1. 邮箱格式校验
- 支持标准邮箱格式：xxx@xxx.xxx
- 支持国际域名
- 不区分大小写

### 2. 登录验证
- 输入邮箱和密码
- 后端验证账号密码是否正确
- 验证成功后生成Token返回给前端

### 3. 失败处理
- 密码错误超过5次，锁定账号30分钟
- 锁定期间不允许登录
- 显示友好的错误提示

### 4. 安全要求
- 密码使用bcrypt加密存储
- 登录Token有效期24小时
- 支持单设备登录（新登录会踢掉旧设备）

## 非功能需求
- 登录响应时间 < 500ms
- 支持1000并发登录
    """

    # 初始化编排器（需要传入实际的model实例）
    # orchestrator = ComprehensiveQAOrchestrator(model)

    print("=" * 80)
    print("综合需求分析示例")
    print("=" * 80)

    # 执行完整分析
    # result = await orchestrator.analyze(requirement_doc)

    # ========== 使用快速理解结果 ==========
    print("\n" + "=" * 80)
    print("第1部分：快速理解（3-5分钟）")
    print("=" * 80)

    print("\n📊 智能摘要:")
    # print(f"核心功能: {result.quick_understanding.summary.core_function}")
    # print(f"复杂度: {result.quick_understanding.summary.estimated_complexity}")
    # print(f"主要变更: {len(result.quick_understanding.summary.main_changes)}项")
    # for i, change in enumerate(result.quick_understanding.summary.main_changes, 1):
    #     print(f"  {i}. {change}")

    print("\n🗺️ 功能地图:")
    # print(result.quick_understanding.feature_map_diagram)

    print("\n🔄 核心流程图:")
    # print(result.quick_understanding.core_flow_diagram)

    print("\n❓ 快速FAQ（前5个）:")
    # for i, faq in enumerate(result.quick_understanding.faq[:5], 1):
    #     print(f"\n{i}. [{faq.category}] {faq.question}")
    #     print(f"   答: {faq.answer}")

    # ========== 使用测试场景结果 ==========
    print("\n" + "=" * 80)
    print("第2部分：测试场景（10-15分钟）")
    print("=" * 80)

    print("\n🎯 测试场景（前3个）:")
    # for scenario in result.test_scenarios.test_scenarios[:3]:
    #     print(f"\n{scenario.scenario_id}: {scenario.title} [{scenario.priority}]")
    #     print(f"Given: {scenario.given}")
    #     print(f"When: {scenario.when}")
    #     print(f"Then: {scenario.then}")
    #     print(f"断言点: {', '.join(scenario.assertion_points)}")

    print("\n📊 数据流图:")
    # print(result.test_scenarios.data_flow_mermaid)

    print("\n⚠️ 风险热点:")
    # for hotspot in result.test_scenarios.risk_hotspots:
    #     print(f"- [{hotspot.priority}] {hotspot.area}: {hotspot.risk}")

    # ========== 使用可测试性评估结果 ==========
    print("\n" + "=" * 80)
    print("第3部分：可测试性评估")
    print("=" * 80)

    # print(f"\n✅ 可测试性评分: {result.testability.score}/100")
    # print(f"可测试功能: {len(result.testability.testable_features)}个")
    # print(f"不可测试功能: {len(result.testability.untestable_features)}个")
    # print(f"阻塞项: {len(result.testability.blocking_issues)}个")

    # if result.testability.blocking_issues:
    #     print("\n🚫 阻塞项:")
    #     for issue in result.testability.blocking_issues:
    #         print(f"- {issue}")

    # ========== 使用综合视图结果 ==========
    print("\n" + "=" * 80)
    print("第4部分：综合QA视图")
    print("=" * 80)

    # print(f"\n📋 测试清单: {len(result.test_checklist)}项")
    # print("\n优先级分布:")
    # priority_counts = {}
    # for item in result.test_checklist:
    #     priority_counts[item.priority] = priority_counts.get(item.priority, 0) + 1
    # for priority in ["P0", "P1", "P2", "P3"]:
    #     count = priority_counts.get(priority, 0)
    #     print(f"  {priority}: {count}项")

    # print(f"\n📈 测试覆盖度:")
    # print(f"  覆盖率: {result.coverage_analysis.coverage_percentage:.1f}%")
    # print(f"  可测试: {result.coverage_analysis.testable_features}/{result.coverage_analysis.total_features}个功能点")

    # if result.coverage_analysis.gaps:
    #     print(f"\n⚠️ 需求不清的地方:")
    #     for gap in result.coverage_analysis.gaps:
    #         print(f"  - {gap}")

    print("\n📊 所有可视化图表:")
    print("  - 功能地图（mindmap）")
    print("  - 核心流程图（flowchart）")
    print("  - 数据流图（graph）")
    # if result.all_diagrams.state_machines:
    #     print(f"  - 状态机图（{len(result.all_diagrams.state_machines)}个）")

    print("\n" + "=" * 80)
    print("综合总结")
    print("=" * 80)
    # print(result.summary)


async def example_simple_analysis():
    """简化分析示例（适用于长文档）"""

    # 很长的需求文档
    long_requirement_doc = """
# 复杂的电商系统需求
... (假设有10000+字的详细需求)
    """

    # 初始化编排器
    # orchestrator = ComprehensiveQAOrchestrator(model)

    print("=" * 80)
    print("简化分析示例（长文档优化）")
    print("=" * 80)

    # 使用简化模式分析（自动截断文档）
    # result = await orchestrator.analyze_simple(
    #     long_requirement_doc,
    #     max_doc_length=5000  # 最多保留5000字符
    # )

    print("\n✅ 分析完成（使用token优化）")
    # 后续使用方式与完整分析相同


async def example_step_by_step():
    """分步骤使用示例"""

    requirement_doc = "... 需求文档 ..."

    # 如果只需要快速理解，不需要完整分析
    from app.agents.requirement_analysis.requirement_understanding_assistant import (
        RequirementUnderstandingAssistant
    )

    # assistant = RequirementUnderstandingAssistant(model)
    # quick_view = await assistant.generate_quick_view(requirement_doc)

    print("快速理解完成，耗时3-5分钟")
    # print(f"核心功能: {quick_view.summary.core_function}")
    # print(f"FAQ数量: {len(quick_view.faq)}个")


if __name__ == "__main__":
    print("=" * 80)
    print("综合需求分析使用示例")
    print("=" * 80)
    print("\n提示: 取消注释相关代码并传入实际的model实例后即可运行")
    print("\n包含三个示例:")
    print("1. example_comprehensive_analysis() - 完整分析流程")
    print("2. example_simple_analysis() - 简化分析（长文档）")
    print("3. example_step_by_step() - 分步骤使用")

    # asyncio.run(example_comprehensive_analysis())
