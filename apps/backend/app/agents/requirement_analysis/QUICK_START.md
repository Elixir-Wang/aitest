# 快速开始指南

## 一分钟了解

### 这是什么？
一个帮助QA快速理解需求的AI工具，支持：
- ✅ 3-5分钟快速理解需求
- ✅ 自动生成可视化图表（功能地图、流程图）
- ✅ 自动生成FAQ
- ✅ 提取测试场景
- ✅ 评估可测试性

### 核心价值
**从30分钟读需求 → 3-5分钟快速理解**

---

## 快速开始

### 方式1：完整分析（推荐）

```python
from app.agents.requirement_analysis.comprehensive_orchestrator import (
    ComprehensiveQAOrchestrator
)

# 初始化（需要传入LLM模型实例）
orchestrator = ComprehensiveQAOrchestrator(model)

# 执行分析
result = await orchestrator.analyze(requirement_doc)

# 查看结果
print("📊 核心功能:", result.quick_understanding.summary.core_function)
print("🗺️ 功能地图:\n", result.quick_understanding.feature_map_diagram)
print("❓ FAQ数量:", len(result.quick_understanding.faq))
print("🎯 测试场景数:", len(result.test_scenarios.test_scenarios))
print("✅ 可测试性评分:", result.testability.score)
```

### 方式2：只要快速理解（3-5分钟）

```python
from app.agents.requirement_analysis.requirement_understanding_assistant import (
    RequirementUnderstandingAssistant
)

# 初始化
assistant = RequirementUnderstandingAssistant(model)

# 生成快速理解视图
quick_view = await assistant.generate_quick_view(requirement_doc)

# 查看结果
print("核心功能:", quick_view.summary.core_function)
print("复杂度:", quick_view.summary.estimated_complexity)
print("功能地图:\n", quick_view.feature_map_diagram)
print("核心流程图:\n", quick_view.core_flow_diagram)

# 查看FAQ
for faq in quick_view.faq:
    print(f"Q: {faq.question}")
    print(f"A: {faq.answer}\n")
```

### 方式3：长文档优化

```python
# 对于超长需求文档，使用简化模式
result = await orchestrator.analyze_simple(
    requirement_doc,
    max_doc_length=5000  # 自动截断到5000字符
)
```

---

## 输出结构

### 快速理解部分
```python
result.quick_understanding
├── summary                    # 智能摘要
│   ├── core_function         # 核心功能（一句话）
│   ├── main_changes          # 主要变更（3-5条）
│   ├── affected_modules      # 影响模块
│   ├── key_risks            # 关键风险
│   └── estimated_complexity  # 复杂度估计
├── feature_map_diagram        # 功能地图（Mermaid mindmap）
├── core_flow_diagram          # 核心流程图（Mermaid flowchart）
└── faq                        # 快速FAQ（10个问题）
```

### 测试场景部分
```python
result.test_scenarios
├── features                   # 功能点清单
├── test_scenarios            # Given-When-Then测试场景
├── data_flow                 # 数据流转
├── data_flow_mermaid         # 数据流图（Mermaid）
├── risk_hotspots             # 风险热点
└── summary                   # 总结
```

### 可测试性部分
```python
result.testability
├── score                     # 评分（0-100）
├── testable_features         # 可测试功能列表
├── untestable_features       # 不可测试功能列表
├── blocking_issues           # 阻塞项
└── summary                   # 总结
```

### 综合视图部分
```python
result
├── test_checklist            # 测试清单（按优先级排序）
├── coverage_analysis         # 覆盖度分析
├── all_diagrams              # 所有可视化图表
│   ├── feature_map          # 功能地图
│   ├── core_flow            # 核心流程图
│   ├── data_flow            # 数据流图
│   └── state_machines       # 状态机图列表
└── summary                   # 综合总结
```

---

## 使用场景

### 场景1：QA刚拿到新需求
```python
# 1. 先快速理解（3-5分钟）
quick_view = await assistant.generate_quick_view(requirement_doc)

# 2. 看智能摘要
print(quick_view.summary.core_function)
print(quick_view.summary.key_risks)

# 3. 看功能地图，了解结构
print(quick_view.feature_map_diagram)

# 4. 看FAQ，找答案
for faq in quick_view.faq:
    if "并发" in faq.question:
        print(faq.answer)
```

### 场景2：需求评审会议准备
```python
# 会前3分钟
result = await orchestrator.analyze(requirement_doc)

# 打印关键信息
print("核心功能:", result.quick_understanding.summary.core_function)
print("关键风险:", result.quick_understanding.summary.key_risks)
print("风险热点数:", len(result.test_scenarios.risk_hotspots))

# 投屏展示图表
print(result.quick_understanding.feature_map_diagram)
print(result.quick_understanding.core_flow_diagram)
```

### 场景3：编写测试用例
```python
# 完整分析
result = await orchestrator.analyze(requirement_doc)

# 查看测试清单
for item in result.test_checklist:
    if item.priority in ["P0", "P1"]:
        print(f"{item.id}: {item.feature}")
        print(f"  Given: {item.given_when_then}")
        print(f"  断言点: {item.assertion_points}")
```

---

## 进阶用法

### 自定义prompt
如果需要调整生成内容，可以修改：
- `requirement_understanding_assistant.py` 中的prompt
- 调整FAQ数量、问题类型
- 调整图表复杂度

### 批量分析
```python
# 分析多个需求文档
docs = [doc1, doc2, doc3]

results = []
for doc in docs:
    result = await orchestrator.analyze_simple(doc)
    results.append(result)

# 汇总统计
total_scenarios = sum(len(r.test_scenarios.test_scenarios) for r in results)
avg_score = sum(r.testability.score for r in results) / len(results)
```

### 导出为Markdown
```python
# 导出完整报告
def export_to_markdown(result):
    md = []
    md.append(f"# {result.quick_understanding.summary.core_function}\n")
    md.append(f"## 智能摘要\n")
    md.append(f"- 复杂度: {result.quick_understanding.summary.estimated_complexity}\n")
    md.append(f"\n## 功能地图\n```mermaid\n{result.quick_understanding.feature_map_diagram}\n```\n")
    md.append(f"\n## FAQ\n")
    for faq in result.quick_understanding.faq:
        md.append(f"### {faq.question}\n{faq.answer}\n")
    return "\n".join(md)

markdown_report = export_to_markdown(result)
with open("requirement_report.md", "w") as f:
    f.write(markdown_report)
```

---

## 常见问题

### Q: 需要什么依赖？
A: 需要一个支持结构化输出的LLM模型实例（如Claude、GPT-4）

### Q: 分析需要多长时间？
A: 
- 快速理解：3-5分钟
- 完整分析：15-20分钟（包含测试场景提取和可测试性评估）

### Q: 支持哪些需求格式？
A: 任何纯文本格式的需求文档（Markdown、纯文本、Word转文本等）

### Q: 生成的图表如何展示？
A: Mermaid格式的图表可以在支持Mermaid的平台展示（GitHub、GitLab、Notion、Typora等）

### Q: 如果需求文档很长怎么办？
A: 使用 `analyze_simple()` 方法，会自动截断文档避免token超限

### Q: 可以只生成某一部分吗？
A: 可以，直接调用对应组件：
- `RequirementUnderstandingAssistant` - 只要快速理解
- `TestScenarioExtractor` - 只要测试场景
- `TestabilityAssessor` - 只要可测试性评估

---

## 下一步

1. 查看完整示例：[examples/comprehensive_example.py](examples/comprehensive_example.py)
2. 了解架构对比：[ARCHITECTURE_COMPARISON.md](ARCHITECTURE_COMPARISON.md)
3. 查看实施总结：[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

---

**开始使用吧！** 🚀
