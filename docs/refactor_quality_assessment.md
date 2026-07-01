# 质量评估架构重构方案

## 当前问题

1. **Schema过于复杂**：4个维度对象 × 多个列表字段 × 嵌套对象 = 几十个字段
2. **Prompt过长**：362行系统提示，LLM难以准确遵循
3. **一次性要求太多**：同时要求识别、分类、评估、决策

## 重构方案

### 方案A：扁平化问题模型（推荐）

#### 核心思想
- 用统一的 `QualityIssue` 替代4个维度的独立结构
- 减少嵌套层级（从3-4层减少到1-2层）
- 简化LLM输出任务

#### 新的Schema设计

```python
class QualityIssue(BaseModel):
    """统一的质量问题模型"""
    issue_id: str = Field(description="问题ID，如 COMP-001, CLAR-001")
    
    # 分类维度
    dimension: Literal["completeness", "clarity", "testability", "consistency"]
    category: str = Field(description="具体类别：fuzzy_term, nfr_gap, conflict, missing_detail等")
    severity: Literal["blocker", "major", "minor"]
    
    # 问题描述
    title: str = Field(description="问题标题")
    description: str = Field(description="问题详细描述")
    location: str = Field(description="出现位置（模块、章节）")
    current_text: str = Field(default="", description="当前原文（如有）")
    
    # 建议
    issue_reason: str = Field(description="为什么是问题")
    suggested_fix: str = Field(description="建议修改方案")
    impact: str = Field(description="对测试/开发的影响")


class QualityAssessmentOutputV2(BaseModel):
    """简化后的质量评估输出"""
    
    # 核心：扁平的问题列表
    issues: list[QualityIssue] = Field(description="所有识别的问题")
    
    # 统计信息（自动计算）
    summary: QualityIssueSummary
    
    # 决策（基于统计信息）
    decision: QualityDecision
    
    # 简单的文本总结
    assessment_summary: str
```

#### 优势
1. **LLM容易生成**：每个问题都是独立的、结构简单的对象
2. **易于扩展**：新增问题类型只需添加category，不需要改schema
3. **统一处理**：下游处理逻辑统一（不需要针对4个维度分别处理）
4. **易于调试**：问题列表一目了然

#### 实现步骤

**Step 1: 修改 schemas.py**
```python
# 新增统一问题模型
class QualityIssue(BaseModel):
    issue_id: str
    dimension: Literal["completeness", "clarity", "testability", "consistency"]
    category: str  # "nfr_gap", "fuzzy_term", "conflict", "missing_detail"等
    severity: Literal["blocker", "major", "minor"]
    title: str
    description: str
    location: str
    current_text: str = ""
    issue_reason: str
    suggested_fix: str
    impact: str
    
    # 可选：维度特定的额外信息（用dict而非固定字段）
    extra_info: dict[str, Any] = Field(default_factory=dict)

# 保留原有的Summary和Decision（已经很简单了）
class QualityIssueSummary(BaseModel): ...
class QualityDecision(BaseModel): ...

# 新的输出结构
class QualityAssessmentOutputV2(BaseModel):
    issues: list[QualityIssue]
    summary: QualityIssueSummary
    decision: QualityDecision
    assessment_summary: str
```

**Step 2: 简化 system prompt**

从362行减少到约100行：

```python
QUALITY_ASSESSMENT_SYSTEM_PROMPT_V2 = """
你是需求质量评估专家。

## 任务
识别需求文档中的所有质量问题，每个问题输出为一个 QualityIssue 对象。

## 检查维度

### 1. 完整性 (completeness)
- **nfr_gap**: 缺少非功能需求（必须有原文evidence_text）
- **missing_detail**: 缺少关键细节（字段定义、错误提示等）
- **functional_gap**: 功能定义不完整

### 2. 清晰度 (clarity)
- **fuzzy_term**: 模糊词（"快速"、"用户友好"等）
- **ambiguous**: 歧义表述（一句话多种理解）

### 3. 可测试性 (testability)
- **missing_acceptance**: 缺少验收标准
- **boundary_undefined**: 边界值未定义
- **exception_missing**: 异常路径未覆盖

### 4. 一致性 (consistency)
- **conflict**: 规则冲突、状态矛盾
- **terminology**: 术语不一致

## 严重程度
- **blocker**: 必须立即修复（严重冲突、核心流程无验收标准）
- **major**: 显著影响测试覆盖（边界值缺失、模糊词多）
- **minor**: 不影响核心测试（术语不统一、可选字段说明缺失）

## 输出格式
​```json
{
  "issues": [
    {
      "issue_id": "COMP-001",
      "dimension": "completeness",
      "category": "nfr_gap",
      "severity": "major",
      "title": "智能体列表查询缺少响应时间要求",
      "description": "原文提到'用户可以查询智能体列表'，但未定义性能指标",
      "location": "智能体管理模块",
      "current_text": "用户可以在列表页查询智能体",
      "issue_reason": "查询接口需要性能指标才能设计性能测试",
      "suggested_fix": "列表查询需在2秒内返回结果（95%请求）",
      "impact": "无法设计性能测试、无法判定是否达标"
    }
  ],
  "summary": {
    "completeness_issues": 5,
    "clarity_issues": 8,
    ...
  },
  "decision": {
    "result": "conditional",
    ...
  }
}
```

## 关键规则
1. **深度检查，不要漏**
2. **每个问题必须有证据**（current_text来自原文）
3. **NFR不要过度**（必须有明确原文场景）
4. **severity要准确**（blocker要慎重）
""".strip()
```

**Step 3: 更新 quality_assessment.py**
​```python
async def run_quality_assessment_agent_v2(
    model,
    primary_markdown_content: str,
    understanding_result: RequirementUnderstandingOutput,
) -> QualityAssessmentOutputV2:
    """V2版本：使用简化schema"""
    agent = quality_assessment_agent_v2(model)
    result = await agent.ainvoke({"messages": [...]})
    output = result.get("structured_response")
    
    # 后处理：自动计算summary
    issues = output.issues
    summary = _calculate_summary(issues)
    decision = _make_decision(summary)
    
    return QualityAssessmentOutputV2(
        issues=issues,
        summary=summary,
        decision=decision,
        assessment_summary=output.assessment_summary
    )

def _calculate_summary(issues: list[QualityIssue]) -> QualityIssueSummary:
    """根据问题列表自动计算统计信息"""
    completeness = sum(1 for i in issues if i.dimension == "completeness")
    clarity = sum(1 for i in issues if i.dimension == "clarity")
    testability = sum(1 for i in issues if i.dimension == "testability")
    consistency = sum(1 for i in issues if i.dimension == "consistency")
    
    by_severity = {
        "blocker": sum(1 for i in issues if i.severity == "blocker"),
        "major": sum(1 for i in issues if i.severity == "major"),
        "minor": sum(1 for i in issues if i.severity == "minor"),
    }
    
    return QualityIssueSummary(
        completeness_issues=completeness,
        clarity_issues=clarity,
        testability_issues=testability,
        consistency_issues=consistency,
        total_issues=len(issues),
        by_severity=by_severity,
        has_blocker=by_severity["blocker"] > 0,
        can_proceed=by_severity["blocker"] == 0
    )
```

**Step 4: 适配下游处理**

澄清阶段需要从扁平列表中提取信息：

```python
# 在 clarify_node.py 或 clarification agent 中
def extract_nfr_gaps(issues: list[QualityIssue]) -> list[NFRGap]:
    """从统一问题列表中提取NFR缺口"""
    nfr_issues = [i for i in issues if i.category == "nfr_gap"]
    return [
        NFRGap(
            category=issue.extra_info.get("nfr_category", "performance"),
            description=issue.description,
            impact=issue.impact,
            severity=issue.severity,
            suggested_requirement=issue.suggested_fix,
            evidence_text=issue.current_text,
            evidence_reason=issue.issue_reason
        )
        for issue in nfr_issues
    ]

def extract_fuzzy_terms(issues: list[QualityIssue]) -> list[FuzzyTerm]:
    """提取模糊词"""
    fuzzy_issues = [i for i in issues if i.category == "fuzzy_term"]
    return [
        FuzzyTerm(
            term=issue.extra_info.get("term", ""),
            location=issue.location,
            current_text=issue.current_text,
            issue=issue.issue_reason,
            suggested_fix=issue.suggested_fix
        )
        for issue in fuzzy_issues
    ]
```

---

### 方案B：两阶段执行（可选增强）

如果方案A仍然出错，可以进一步拆分：

#### 阶段1：问题识别（只输出问题列表）
```python
class QualityIssueRaw(BaseModel):
    """第一阶段：只识别问题，不做分类"""
    description: str
    location: str
    current_text: str = ""
```

#### 阶段2：分类和评估（Python代码处理）
用规则或轻量级LLM调用对问题分类、打severity标签

---

## 迁移策略

### 选项1：并行运行（推荐）
1. 保留旧代码（v1）
2. 实现新版本（v2）
3. 通过配置切换
4. 验证v2稳定后移除v1

### 选项2：直接替换
1. 修改schemas.py
2. 修改quality_assessment.py
3. 修改clarify_node.py适配新格式
4. 更新所有测试

---

## 预期效果

1. **LLM成功率提升**：从复杂嵌套JSON降低到简单列表
2. **Prompt可读性**：从362行减少到~100行
3. **维护成本降低**：统一的问题模型，易于扩展
4. **调试体验改善**：问题列表一目了然

---

## 风险评估

### 低风险
- Schema变更（不影响外部API）
- Prompt简化（功能不减少）

### 中等风险
- 下游代码适配（clarify_node需要改）
- 测试用例更新（mock数据格式变化）

### 建议
1. 先实现方案A（扁平化）
2. 如果仍有问题，再加方案B（两阶段）
3. 保持向后兼容（v1/v2并存一段时间）
