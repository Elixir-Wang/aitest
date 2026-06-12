# 需求分析 v2.0 快速上手指南

## 概述

需求分析 v2.0 采用**三块核心架构**，简化了需求分析流程，同时增强了质量评估能力。

## 核心改进

### ✅ 相比 v1.0 的优势

1. **架构更清晰**
   - v1.0：单一 159 行 requirement-review skill
   - v2.0：三块独立模块，职责明确

2. **NFR 评估完善**
   - v1.0：缺失非功能需求评估
   - v2.0：评估 6 大类 NFR（性能、安全、可用性、可扩展性、兼容性、合规）

3. **自动修正建议**
   - v1.0：只识别模糊词
   - v2.0：提供具体的 `suggested_fix`，可直接替换

4. **辅助文档集成**
   - v1.0：独立的 `auxiliary_enhancement_agent`
   - v2.0：集成到"待澄清内容"阶段，自动查找答案

5. **优先级排序**
   - v1.0：简单按严重程度分类
   - v2.0：7 级优先级（blocker+无答案优先级最高）

6. **决策明确**
   - v1.0：`quality_gate.result: passed/warning/blocked`
   - v2.0：`decision.result: approved/conditional/rejected` + 理由 + 下一步建议

---

## 快速开始

### 1. 基本使用

```python
from app.agents.requirement_analysis.agent_v2 import run_requirement_analysis_v2
from app.agents.requirement_analysis.schemas_v2 import AuxiliaryDocument

# 准备输入
primary_content = """
# 订单管理模块

用户可以创建订单。订单创建后状态为"待支付"。
用户支付成功后，订单状态变为"已支付"。
订单金额大于1000元时，需要经理审批。
系统应当快速响应用户操作。
"""

auxiliary_docs = [
    AuxiliaryDocument(
        mapping_id="doc-001",
        filename="运营规范.docx",
        document_type="policy",
        markdown_content="所有审批流程超时时间统一为48小时。"
    )
]

# 运行分析
result = await run_requirement_analysis_v2(
    model=your_llm_model,
    primary_markdown_content=primary_content,
    auxiliary_documents=auxiliary_docs,
)

# 查看结果
print(f"状态: {result.status}")
print(f"质量评分: {result.quality_assessment.scores.overall}/100")
print(f"决策: {result.quality_assessment.decision.result}")
print(f"待澄清问题: {result.clarification.summary.needs_manual} 个")
```

### 2. 分阶段使用

如果只需要特定阶段的分析：

```python
from app.agents.requirement_analysis.agent_v2 import (
    run_understanding_agent,
    run_quality_assessment_agent,
    run_clarification_agent,
)

# 只做需求理解
understanding = await run_understanding_agent(
    model=model,
    primary_markdown_content=content,
)

# 基于理解结果做质量评估
quality = await run_quality_assessment_agent(
    model=model,
    primary_markdown_content=content,
    understanding_result=understanding,
)

# 生成待澄清内容
clarification = await run_clarification_agent(
    model=model,
    understanding_result=understanding,
    quality_assessment_result=quality,
    auxiliary_documents=auxiliary_docs,
)
```

---

## 输出结构详解

### 1️⃣ 需求理解输出

```python
result.understanding
├── modules: list[RequirementModule]
│   ├── module_key: str              # "order_management"
│   ├── module_name: str             # "订单管理"
│   ├── capabilities: list[str]      # ["创建订单", "支付订单"]
│   ├── business_objects: list[...]  # 业务对象列表
│   ├── business_rules: list[...]    # 业务规则列表
│   └── state_flows: list[...]       # 状态流转
├── dependencies: list[Dependency]   # 模块依赖
├── risks: list[Risk]                # 风险列表
├── assumptions: list[Assumption]    # 假设列表
└── understanding_summary: str       # 总结
```

**使用示例**：
```python
# 获取所有模块
for module in result.understanding.modules:
    print(f"模块: {module.module_name}")
    print(f"功能点: {', '.join(module.capabilities)}")

# 获取高风险项
high_risks = [r for r in result.understanding.risks if r.impact == "high"]
```

### 2️⃣ 质量评估输出

```python
result.quality_assessment
├── scores: QualityScores
│   ├── completeness: int (0-100)
│   ├── clarity: int (0-100)
│   ├── testability: int (0-100)
│   ├── consistency: int (0-100)
│   └── overall: int (0-100)
├── decision: QualityDecision
│   ├── result: "approved" | "conditional" | "rejected"
│   ├── rationale: str
│   ├── blocking_issues: list[str]
│   └── recommended_actions: list[str]
├── completeness: CompletenessAssessment
│   ├── functional_gaps: list[str]
│   ├── nfr_gaps: list[NFRGap]      # 非功能需求缺口 ⭐ 新增
│   └── missing_details: list[str]
├── clarity: ClarityAssessment
│   ├── fuzzy_terms: list[FuzzyTerm] # 模糊词 + suggested_fix ⭐ 增强
│   └── ambiguous_statements: list[...]
├── testability: TestabilityAssessment
│   ├── acceptance_criteria_gaps: list[...]
│   └── test_coverage_gaps: list[...]
└── consistency: ConsistencyAssessment
    ├── conflicts: list[Conflict]
    └── terminology_issues: list[...]
```

**使用示例**：
```python
# 检查是否通过
if result.quality_assessment.decision.result == "approved":
    print("✅ 需求质量达标，可以进入设计阶段")
elif result.quality_assessment.decision.result == "conditional":
    print("⚠️ 需解决以下问题：")
    for issue in result.quality_assessment.decision.blocking_issues:
        print(f"  - {issue}")
else:
    print("❌ 需求质量不达标，需要大幅返工")

# 获取 NFR 缺口
nfr_gaps = result.quality_assessment.completeness.nfr_gaps
for gap in nfr_gaps:
    print(f"[{gap.category}] {gap.description}")
    print(f"建议: {gap.suggested_requirement}")

# 获取模糊词修正建议
for term in result.quality_assessment.clarity.fuzzy_terms:
    print(f"原文: {term.current_text}")
    print(f"修正为: {term.suggested_fix}")
```

### 3️⃣ 待澄清内容输出

```python
result.clarification
├── items: list[ClarificationItem]   # 按优先级排序
│   ├── item_id: str
│   ├── source: "understanding" | "completeness" | ...
│   ├── question: str                # 面向人工的问题
│   ├── impact: str                  # 不确认的影响
│   ├── severity: "blocker" | "major" | "minor"
│   ├── current_text: str            # 原文
│   ├── suggested_fix: str           # 建议修正 ⭐ 新增
│   ├── recommended_options: list[ClarificationOption]
│   ├── evidence: list[EvidenceReference]  # 辅助文档证据
│   └── resolution_status: "auto_resolved" | "has_suggestions" | "needs_manual"
└── summary: ClarificationSummary
    ├── total: int
    ├── auto_resolved: int           # 自动解决的数量
    ├── has_suggestions: int         # 有建议的数量
    ├── needs_manual: int            # 需要人工的数量
    ├── by_severity: dict            # 按严重程度统计
    └── by_source: dict              # 按来源统计
```

**使用示例**：
```python
# 获取需要人工确认的问题（按优先级）
manual_items = [
    item for item in result.clarification.items
    if item.resolution_status == "needs_manual"
]

for item in manual_items[:5]:  # 显示前5个
    print(f"[{item.severity}] {item.question}")
    print(f"影响: {item.impact}")
    
    # 如果有建议选项
    for option in item.recommended_options:
        print(f"  选项: {option.label} (可信度: {option.confidence})")
        print(f"  答案: {option.answer_markdown}")
    
    # 如果有修正建议
    if item.suggested_fix:
        print(f"建议修正:")
        print(f"  原文: {item.current_text}")
        print(f"  改为: {item.suggested_fix}")

# 统计信息
summary = result.clarification.summary
print(f"总问题数: {summary.total}")
print(f"自动解决: {summary.auto_resolved}")
print(f"有建议: {summary.has_suggestions}")
print(f"需人工: {summary.needs_manual}")
print(f"Blocker: {summary.by_severity['blocker']}")
```

---

## 配置选项

### 质量阈值配置

```python
config = {
    "quality_thresholds": {
        "approved": 90,      # 通过阈值
        "conditional": 75,   # 有条件通过阈值
    },
    "dimension_weights": {
        "completeness": 0.30,
        "clarity": 0.25,
        "testability": 0.25,
        "consistency": 0.20,
    },
    "nfr_categories": [
        "performance",
        "security",
        "availability",
        "scalability",
        "compatibility",
        "compliance",
    ],
    "auto_enhancement": {
        "enabled": True,              # 是否启用辅助文档自动增强
        "min_confidence": "medium",   # 最低可信度
    },
}

result = await run_requirement_analysis_v2(
    model=model,
    primary_markdown_content=content,
    auxiliary_documents=auxiliary_docs,
    config=config,
)
```

---

## 常见使用场景

### 场景 1：快速质量检查

只关心需求是否达标，不需要详细分析：

```python
result = await run_requirement_analysis_v2(model, content)

if result.status == "completed":
    print("✅ 需求质量优秀，可以进入开发")
elif result.status == "needs_clarification":
    print(f"⚠️ 有 {result.clarification.summary.needs_manual} 个问题需要澄清")
else:
    print("❌ 需求质量不达标，建议返工")
```

### 场景 2：生成待办事项

将待澄清内容转为团队的待办任务：

```python
todos = []
for item in result.clarification.items:
    if item.severity == "blocker" or item.severity == "major":
        todos.append({
            "title": item.question,
            "description": item.impact,
            "priority": "high" if item.severity == "blocker" else "medium",
            "suggested_solution": item.suggested_fix or "",
        })

# 导出为 JSON/CSV 或创建 Jira tickets
```

### 场景 3：自动修正需求文档

应用修正建议，生成改进版需求：

```python
# 获取所有模糊词的修正
fixes = []
for term in result.quality_assessment.clarity.fuzzy_terms:
    fixes.append({
        "original": term.current_text,
        "fixed": term.suggested_fix,
    })

# 应用修正
improved_content = primary_content
for fix in fixes:
    improved_content = improved_content.replace(fix["original"], fix["fixed"])

# 补充 NFR
for gap in result.quality_assessment.completeness.nfr_gaps:
    improved_content += f"\n\n## {gap.category.title()} 要求\n\n{gap.suggested_requirement}"
```

### 场景 4：生成评审报告

```python
# 使用内置报告生成
report_markdown = result.analysis_report_markdown

# 或自定义报告格式
report = f"""
# 需求评审报告

## 基本信息
- 文档: {document_name}
- 评审时间: {datetime.now()}
- 质量评分: {result.quality_assessment.scores.overall}/100

## 评审结果
{result.quality_assessment.decision.result.upper()}

{result.quality_assessment.decision.rationale}

## 待澄清问题 (Top 10)
{generate_clarification_table(result.clarification.items[:10])}

## 建议行动
{format_actions(result.quality_assessment.decision.recommended_actions)}
"""
```

---

## 与 v1.0 对比

### 迁移指南

| v1.0 | v2.0 | 说明 |
|------|------|------|
| `RequirementAnalysisOutput` | `RequirementAnalysisResultV2` | 新结构更清晰 |
| `modules` | `understanding.modules` | 移到 understanding |
| `clarification_questions` | `clarification.items` | 增强了字段 |
| `quality_gate` | `quality_assessment.decision` | 更明确的决策 |
| `coverage_audit` | `quality_assessment.testability.test_coverage_gaps` | 重组 |
| ❌ 无 | `quality_assessment.completeness.nfr_gaps` | NFR 评估 |
| ❌ 无 | `clarification.items[].suggested_fix` | 行内修正 |
| ❌ 无 | `clarification.items[].evidence` | 辅助文档证据 |

### 代码迁移示例

**v1.0**：
```python
from app.agents.requirement_analysis.primary_analysis.agent import (
    run_primary_analysis_agent
)

result = await run_primary_analysis_agent(model, user_content)
modules = result.modules
questions = result.clarification_questions
quality = result.quality_gate
```

**v2.0**：
```python
from app.agents.requirement_analysis.agent_v2 import (
    run_requirement_analysis_v2
)

result = await run_requirement_analysis_v2(model, primary_content)
modules = result.understanding.modules
questions = result.clarification.items
decision = result.quality_assessment.decision
```

---

## 最佳实践

### 1. 提供高质量的辅助文档

辅助文档可以显著提高自动增强的效果：

```python
auxiliary_docs = [
    AuxiliaryDocument(
        mapping_id="std-001",
        filename="技术标准.md",
        document_type="standard",
        markdown_content=tech_standard_content,
    ),
    AuxiliaryDocument(
        mapping_id="policy-001",
        filename="运营规范.docx",
        document_type="policy",
        markdown_content=policy_content,
    ),
]
```

### 2. 关注 Blocker 问题

优先解决 blocker 级别的问题：

```python
blockers = [
    item for item in result.clarification.items
    if item.severity == "blocker"
]

if blockers:
    print(f"⚠️ 发现 {len(blockers)} 个阻塞问题，必须解决：")
    for item in blockers:
        print(f"  - {item.question}")
```

### 3. 利用建议选项

对于有建议选项的问题，可以快速确认：

```python
for item in result.clarification.items:
    if item.recommended_options and item.resolution_status == "has_suggestions":
        print(f"问题: {item.question}")
        print("建议选项:")
        for i, opt in enumerate(item.recommended_options, 1):
            print(f"  {i}. {opt.label} (可信度: {opt.confidence})")
            if opt.source:
                print(f"     来源: {opt.source}")
```

### 4. 定期检查 NFR

非功能需求常被忽略，应重点关注：

```python
nfr_gaps = result.quality_assessment.completeness.nfr_gaps
if nfr_gaps:
    print("⚠️ 缺少以下非功能需求:")
    for gap in nfr_gaps:
        print(f"  [{gap.category}] {gap.description}")
```

---

## 故障排查

### 问题 1：质量评分过低

**原因**：需求文档确实质量不佳，或模型理解偏差

**解决**：
1. 检查 `quality_assessment.decision.rationale` 了解评分理由
2. 查看具体缺口：`completeness.functional_gaps`、`clarity.fuzzy_terms`
3. 根据建议修正需求文档后重新分析

### 问题 2：待澄清问题过多

**原因**：需求不够具体，或缺少辅助文档

**解决**：
1. 提供相关的辅助文档（标准、规范、示例）
2. 查看 `resolution_status == "auto_resolved"` 的问题，这些已有答案
3. 优先处理 blocker 和 major 问题

### 问题 3：NFR 缺口误报

**原因**：某些项目不需要所有类型的 NFR

**解决**：
通过 config 配置需要检查的 NFR 类别：
```python
config = {
    "nfr_categories": ["performance", "security"],  # 只检查这两类
}
```

---

## 技术支持

- 架构文档：`docs/requirement-analysis-architecture.md`
- Schema 定义：`app/agents/requirement_analysis/schemas_v2.py`
- Agent 实现：`app/agents/requirement_analysis/agent_v2.py`
- Skill 文档：`app/agents/requirement_analysis/skills/requirement-analysis-v2/SKILL.md`
