# 需求分析 v2.0 完整流程

## 流程概览

```
┌─────────────────────────────────────────────────────────────┐
│                      输入准备                                 │
│  • 主需求文档 (primary_markdown_content)                      │
│  • 辅助文档列表 (auxiliary_documents) - 可选                  │
│  • 配置参数 (config) - 可选                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              阶段 1️⃣：需求理解 (Understanding)                │
│                                                               │
│  输入：主需求文档                                              │
│  处理：                                                        │
│    1. 识别功能模块（module_key, module_name, capabilities）   │
│    2. 提取业务对象（name, fields, relationships）             │
│    3. 提取业务规则（验证、计算、工作流、权限）                 │
│    4. 分析状态流转（states, transitions）                     │
│    5. 识别依赖关系（模块间、第三方）                           │
│    6. 识别风险（technical, business, resource）               │
│    7. 识别假设（validation_needed, risk_if_invalid）          │
│  输出：RequirementUnderstandingOutput                         │
│    • modules[]                                                │
│    • dependencies[]                                           │
│    • risks[]                                                  │
│    • assumptions[]                                            │
│    • understanding_summary                                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              阶段 2️⃣：质量评估 (Quality Assessment)           │
│                                                               │
│  输入：主需求文档 + 需求理解结果                                │
│  处理：四个维度并行评估                                        │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 2.1 完整性检查 (30% 权重)                            │    │
│  │   • 功能完整性：规则、字段、边界、异常场景            │    │
│  │   • NFR 完整性：性能、安全、可用性、可扩展性、       │    │
│  │                  兼容性、合规                         │    │
│  │   输出：functional_gaps[], nfr_gaps[]                │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 2.2 清晰度检查 (25% 权重)                            │    │
│  │   • 识别模糊词："快速"、"用户友好"、"安全"          │    │
│  │   • 识别歧义表述：多种理解、逻辑不清                 │    │
│  │   • 为每个问题提供 suggested_fix                     │    │
│  │   输出：fuzzy_terms[], ambiguous_statements[]        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 2.3 可测试性检查 (25% 权重)                          │    │
│  │   • 验收标准完整性：Given-When-Then 格式             │    │
│  │   • 测试覆盖缺口：边界值、异常路径、错误提示、       │    │
│  │                    权限、并发                         │    │
│  │   输出：acceptance_criteria_gaps[],                  │    │
│  │         test_coverage_gaps[]                         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 2.4 一致性检查 (20% 权重)                            │    │
│  │   • 规则冲突："手机号必填" vs "手机号可选"          │    │
│  │   • 术语不一致："用户" vs "客户" vs "会员"         │    │
│  │   输出：conflicts[], terminology_issues[]            │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  计算质量分数：                                                │
│    overall_score = completeness×0.30 + clarity×0.25          │
│                  + testability×0.25 + consistency×0.20       │
│                                                               │
│  生成决策：                                                    │
│    • approved: 总分≥90 且无 blocker                          │
│    • conditional: 总分75-89 或有1-2个 blocker                │
│    • rejected: 总分<75 或有≥3个 blocker                      │
│                                                               │
│  输出：QualityAssessmentOutput                                │
│    • scores (completeness/clarity/testability/consistency)   │
│    • decision (result/rationale/blocking_issues)             │
│    • completeness/clarity/testability/consistency 详细结果    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│         阶段 3️⃣：待澄清内容 (Clarification + 自动增强)        │
│                                                               │
│  输入：需求理解结果 + 质量评估结果 + 辅助文档                  │
│                                                               │
│  处理流程：                                                    │
│                                                               │
│  Step 1: 汇总问题                                             │
│    来源1：需求理解阶段的模糊点                                 │
│    来源2：完整性检查的缺口 (functional_gaps, nfr_gaps)        │
│    来源3：清晰度检查的问题 (fuzzy_terms, ambiguous)           │
│    来源4：可测试性检查的缺口 (criteria_gaps, coverage_gaps)   │
│    来源5：一致性检查的冲突 (conflicts, terminology)            │
│                                                               │
│  Step 2: 问题转换                                             │
│    将质量问题转换为 ClarificationItem：                        │
│      • question: 面向人工确认的问题                           │
│      • impact: 不确认的下游影响                               │
│      • current_text: 原需求文本                               │
│      • suggested_fix: 建议修正文本                            │
│                                                               │
│  Step 3: 自动从辅助文档查找答案                                │
│    如果提供了 auxiliary_documents：                            │
│      • 关键词匹配                                              │
│      • 上下文相关性判断                                        │
│      • 证据质量评估 (high/medium/low)                         │
│      • 生成 EvidenceReference                                 │
│      • 生成 recommended_options (带来源标注)                  │
│                                                               │
│  Step 4: 确定解答状态                                          │
│    • auto_resolved: 高可信度答案 (confidence: high)          │
│    • has_suggestions: 有建议选项                              │
│    • needs_manual: 无法提供建议                               │
│                                                               │
│  Step 5: 优先级排序                                            │
│    1. (blocker, needs_manual)      ← 最高优先级              │
│    2. (blocker, has_suggestions)                              │
│    3. (major, needs_manual)                                   │
│    4. (major, has_suggestions)                                │
│    5. (minor, needs_manual)                                   │
│    6. (minor, has_suggestions)                                │
│    7. (*, auto_resolved)            ← 最低优先级              │
│                                                               │
│  输出：ClarificationOutput                                     │
│    • items[] (按优先级排序)                                    │
│    • summary (total/auto_resolved/has_suggestions/            │
│                needs_manual/by_severity/by_source)            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    最终输出汇总                                │
│                                                               │
│  确定分析状态：                                                │
│    • blocked: decision = rejected                             │
│    • needs_clarification: needs_manual > 0                    │
│    • completed: 其他情况                                       │
│                                                               │
│  生成分析报告 (analysis_report_markdown)：                     │
│    1. 执行摘要                                                 │
│       - 质量评分、决策结果、待澄清问题数                       │
│    2. 需求理解                                                 │
│       - 识别的模块、业务对象、规则、风险                       │
│    3. 质量评估                                                 │
│       - 各维度分数、关键问题、阻塞问题                         │
│    4. 待澄清内容                                               │
│       - 按优先级排列的问题 (Top 10)                            │
│    5. 下一步建议                                               │
│                                                               │
│  输出：RequirementAnalysisResultV2                            │
│    • status                                                   │
│    • understanding                                            │
│    • quality_assessment                                       │
│    • clarification                                            │
│    • analysis_report_markdown                                 │
│    • preliminary_requirement_markdown (可选)                  │
│    • metadata                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 详细流程说明

### 阶段 1️⃣：需求理解

**目标**：从原始需求文档中提取结构化信息

**执行逻辑**：
```python
async def run_understanding_agent(model, primary_markdown_content):
    # 创建 Understanding Agent（使用 UNDERSTANDING_SYSTEM_PROMPT）
    agent = understanding_agent(model)
    
    # 输入：主需求文档
    user_content = f"# 主需求文档\n\n{primary_markdown_content}"
    
    # 调用 LLM 进行结构化提取
    result = await agent.ainvoke({"messages": [...]})
    
    # 返回 RequirementUnderstandingOutput
    return result.structured_response
```

**输出示例**：
```json
{
  "modules": [
    {
      "module_key": "order_management",
      "module_name": "订单管理",
      "capabilities": ["创建订单", "支付订单", "取消订单"],
      "business_objects": [
        {
          "name": "订单",
          "fields": ["订单ID", "金额", "状态", "创建时间"],
          "relationships": ["关联用户", "包含商品"]
        }
      ],
      "business_rules": [
        {
          "rule_id": "BR-001",
          "rule_type": "workflow",
          "description": "订单金额大于1000元需要经理审批"
        }
      ],
      "state_flows": [
        {
          "object_name": "订单",
          "states": ["待支付", "已支付", "待审批", "已完成"],
          "transitions": [
            {
              "from_state": "待支付",
              "to_state": "已支付",
              "trigger": "支付成功"
            }
          ]
        }
      ]
    }
  ],
  "risks": [
    {
      "risk_id": "RISK-001",
      "category": "technical",
      "description": "支付网关可能超时",
      "impact": "high",
      "likelihood": "medium"
    }
  ]
}
```

---

### 阶段 2️⃣：质量评估

**目标**：评估需求质量，识别缺口和问题

**执行逻辑**：
```python
async def run_quality_assessment_agent(model, primary_markdown_content, understanding_result):
    # 创建 Quality Assessment Agent（使用 QUALITY_ASSESSMENT_SYSTEM_PROMPT）
    agent = quality_assessment_agent(model)
    
    # 输入：主需求文档 + 需求理解结果
    user_content = f"""
    # 主需求文档
    {primary_markdown_content}
    
    # 需求理解结果
    {understanding_result.model_dump_json()}
    """
    
    # 调用 LLM 进行质量评估
    result = await agent.ainvoke({"messages": [...]})
    
    # 返回 QualityAssessmentOutput
    return result.structured_response
```

**质量评分计算**：
```python
# 各维度评分（0-100）
completeness_score = 70  # 缺失3个NFR，5个功能细节
clarity_score = 75       # 发现2个模糊词
testability_score = 60   # 60%功能缺少验收标准
consistency_score = 95   # 1个minor冲突

# 加权计算总分
overall_score = (
    completeness_score * 0.30 +  # 70 * 0.30 = 21
    clarity_score * 0.25 +        # 75 * 0.25 = 18.75
    testability_score * 0.25 +    # 60 * 0.25 = 15
    consistency_score * 0.20      # 95 * 0.20 = 19
)  # = 73.75

# 决策判断
if overall_score >= 90 and blocker_count == 0:
    decision = "approved"
elif overall_score >= 75 or blocker_count <= 2:
    decision = "conditional"
else:
    decision = "rejected"
```

**输出示例**：
```json
{
  "scores": {
    "completeness": 70,
    "clarity": 75,
    "testability": 60,
    "consistency": 95,
    "overall": 73
  },
  "decision": {
    "result": "conditional",
    "rationale": "总分73，低于75分阈值，但接近可交付标准。主要问题：缺少NFR定义、部分功能缺少验收标准。",
    "blocking_issues": [
      "缺少性能要求定义",
      "缺少安全认证方案"
    ],
    "recommended_actions": [
      "补充性能指标：响应时间、并发用户数",
      "定义安全要求：认证方式、权限模型",
      "为核心功能补充验收标准"
    ]
  },
  "completeness": {
    "score": 70,
    "nfr_gaps": [
      {
        "category": "performance",
        "description": "未定义系统性能要求",
        "severity": "blocker",
        "suggested_requirement": "## 性能要求\n\n- 响应时间：95% 请求 < 2秒\n- 并发用户：支持1000并发\n- 吞吐量：1000 TPS"
      }
    ]
  },
  "clarity": {
    "score": 75,
    "fuzzy_terms": [
      {
        "term": "快速",
        "location": "订单管理模块",
        "current_text": "系统应当快速响应用户操作",
        "issue": "无法度量",
        "suggested_fix": "系统响应时间要求：95% 请求 < 2秒"
      }
    ]
  }
}
```

---

### 阶段 3️⃣：待澄清内容（含自动增强）

**目标**：汇总问题，自动查找答案，提供修正建议

**执行逻辑**：
```python
async def run_clarification_agent(
    model, 
    understanding_result, 
    quality_assessment_result, 
    auxiliary_documents
):
    # 创建 Clarification Agent（使用 CLARIFICATION_SYSTEM_PROMPT）
    agent = clarification_agent(model)
    
    # 输入：需求理解 + 质量评估 + 辅助文档
    user_content = f"""
    # 需求理解结果
    {understanding_result.model_dump_json()}
    
    # 质量评估结果
    {quality_assessment_result.model_dump_json()}
    
    # 辅助文档
    {format_auxiliary_documents(auxiliary_documents)}
    """
    
    # 调用 LLM 汇总问题并查找答案
    result = await agent.ainvoke({"messages": [...]})
    
    # 返回 ClarificationOutput
    return result.structured_response
```

**问题汇总逻辑**：
```python
# 从质量评估提取问题
clarification_items = []

# 来源1：完整性缺口
for gap in quality_assessment.completeness.nfr_gaps:
    item = ClarificationItem(
        source="completeness",
        question=f"请确认：{gap.description}的具体要求是什么？",
        impact="无法评估系统能力，可能导致上线后不满足预期",
        severity=gap.severity,
        suggested_fix=gap.suggested_requirement,
    )

# 来源2：清晰度问题
for term in quality_assessment.clarity.fuzzy_terms:
    item = ClarificationItem(
        source="clarity",
        question=f"'{term.term}'的具体标准是什么？",
        current_text=term.current_text,
        suggested_fix=term.suggested_fix,
    )

# 来源3：可测试性缺口
# 来源4：一致性冲突
# ...
```

**自动增强逻辑**：
```python
# 如果有辅助文档，尝试查找答案
if auxiliary_documents:
    for item in clarification_items:
        # 提取问题关键词
        keywords = extract_keywords(item.question)
        
        # 在辅助文档中搜索
        for doc in auxiliary_documents:
            matches = search_in_document(doc.markdown_content, keywords)
            
            if matches:
                # 评估证据质量
                confidence = evaluate_confidence(matches, item.question)
                
                # 生成证据引用
                item.evidence.append(EvidenceReference(
                    mapping_id=doc.mapping_id,
                    filename=doc.filename,
                    excerpt=matches[0],
                    confidence=confidence,
                ))
                
                # 生成建议选项
                if confidence == "high":
                    item.recommended_options.append(
                        ClarificationOption(
                            label=f"来自 {doc.filename}",
                            answer_markdown=format_answer(matches[0]),
                            confidence=confidence,
                            source=doc.filename,
                        )
                    )
                    item.resolution_status = "auto_resolved"
                elif confidence == "medium":
                    item.resolution_status = "has_suggestions"

# 优先级排序
clarification_items.sort(key=lambda x: (
    {"blocker": 0, "major": 1, "minor": 2}[x.severity],
    {"needs_manual": 0, "has_suggestions": 1, "auto_resolved": 2}[x.resolution_status],
))
```

**输出示例**：
```json
{
  "items": [
    {
      "item_id": "CLR-001",
      "source": "completeness",
      "module_key": "order_management",
      "question": "请确认：系统响应时间要求是多少？并发用户数目标是多少？",
      "impact": "无法评估系统性能需求，可能导致上线后性能不足",
      "severity": "blocker",
      "current_text": "系统应当快速响应用户操作",
      "suggested_fix": "系统性能要求：\n- 响应时间：95% 请求 < 2秒\n- 并发用户：支持1000并发用户",
      "recommended_options": [
        {
          "option_id": "opt1",
          "label": "2秒响应、1000并发（来自技术标准）",
          "answer_markdown": "## 性能要求\n\n- 响应时间：95% 请求 < 2秒\n- 并发用户：支持1000并发用户\n- 吞吐量：1000 TPS",
          "confidence": "high",
          "source": "技术标准.md"
        }
      ],
      "evidence": [
        {
          "mapping_id": "doc-tech-std",
          "filename": "技术标准.md",
          "excerpt": "Web应用响应时间要求：95%请求<2秒，支持1000并发用户",
          "confidence": "high"
        }
      ],
      "resolution_status": "auto_resolved"
    },
    {
      "item_id": "CLR-002",
      "source": "completeness",
      "question": "请确认：订单审批超时时间是多少？超时后如何处理？",
      "severity": "major",
      "recommended_options": [
        {
          "label": "48小时（来自运营规范）",
          "answer_markdown": "审批超时时间：48小时。超时后自动转至上级审批。",
          "confidence": "high",
          "source": "运营规范.docx"
        }
      ],
      "resolution_status": "has_suggestions"
    },
    {
      "item_id": "CLR-003",
      "source": "clarity",
      "question": "请澄清：'用户'、'客户'、'会员'是否指同一概念？",
      "severity": "minor",
      "resolution_status": "needs_manual"
    }
  ],
  "summary": {
    "total": 3,
    "auto_resolved": 1,
    "has_suggestions": 1,
    "needs_manual": 1,
    "by_severity": {
      "blocker": 1,
      "major": 1,
      "minor": 1
    }
  }
}
```

---

## 完整流程代码示例

```python
async def run_requirement_analysis_v2(
    model,
    primary_markdown_content: str,
    auxiliary_documents: list = None,
    config: dict = None,
) -> RequirementAnalysisResultV2:
    """完整的三阶段流程"""
    
    # ==================== 阶段 1️⃣ ====================
    print("开始需求理解...")
    understanding_result = await run_understanding_agent(
        model=model,
        primary_markdown_content=primary_markdown_content,
    )
    print(f"✓ 识别了 {len(understanding_result.modules)} 个模块")
    
    # ==================== 阶段 2️⃣ ====================
    print("开始质量评估...")
    quality_assessment_result = await run_quality_assessment_agent(
        model=model,
        primary_markdown_content=primary_markdown_content,
        understanding_result=understanding_result,
    )
    print(f"✓ 质量评分: {quality_assessment_result.scores.overall}/100")
    print(f"✓ 决策: {quality_assessment_result.decision.result}")
    
    # ==================== 阶段 3️⃣ ====================
    print("开始待澄清内容分析...")
    clarification_result = await run_clarification_agent(
        model=model,
        understanding_result=understanding_result,
        quality_assessment_result=quality_assessment_result,
        auxiliary_documents=auxiliary_documents,
    )
    print(f"✓ 待澄清问题: {clarification_result.summary.total} 个")
    print(f"  - 自动解决: {clarification_result.summary.auto_resolved}")
    print(f"  - 有建议: {clarification_result.summary.has_suggestions}")
    print(f"  - 需人工: {clarification_result.summary.needs_manual}")
    
    # ==================== 确定状态 ====================
    decision = quality_assessment_result.decision.result
    needs_manual = clarification_result.summary.needs_manual
    
    if decision == "rejected":
        status = "blocked"
    elif needs_manual > 0:
        status = "needs_clarification"
    else:
        status = "completed"
    
    # ==================== 生成报告 ====================
    analysis_report = _generate_analysis_report(
        understanding_result,
        quality_assessment_result,
        clarification_result,
    )
    
    # ==================== 返回结果 ====================
    return RequirementAnalysisResultV2(
        status=status,
        understanding=understanding_result,
        quality_assessment=quality_assessment_result,
        clarification=clarification_result,
        analysis_report_markdown=analysis_report,
        metadata={"version": "2.0", "config": config or {}},
    )
```

---

## 与 v1.0 流程对比

| 维度 | v1.0 | v2.0 |
|------|------|------|
| **阶段数** | 2 阶段 | 3 阶段 |
| **流程** | 1. Primary Analysis<br>2. Auxiliary Enhancement | 1. 需求理解<br>2. 质量评估<br>3. 待澄清（含增强） |
| **并行性** | 串行 | 质量评估内部可并行 |
| **NFR评估** | ❌ 缺失 | ✅ 独立评估 |
| **修正建议** | ❌ 无 | ✅ suggested_fix |
| **优先级** | 简单分类 | 7级排序 |
| **辅助文档** | 独立阶段 | 集成到澄清 |

---

## 时间估算

假设主需求文档 5000 tokens，辅助文档 2000 tokens：

| 阶段 | LLM调用 | 输入tokens | 输出tokens | 耗时 |
|------|---------|------------|------------|------|
| 需求理解 | 1次 | ~6K | ~2K | 10-15s |
| 质量评估 | 1次 | ~8K | ~3K | 15-20s |
| 待澄清内容 | 1次 | ~10K | ~2K | 10-15s |
| **总计** | **3次** | **~24K** | **~7K** | **35-50s** |

---

## 关键改进点总结

1. **✅ 职责清晰**：三个独立阶段，每个阶段只做一件事
2. **✅ NFR完善**：专门评估6大类非功能需求
3. **✅ 自动修正**：提供具体的 suggested_fix，可直接应用
4. **✅ 智能增强**：自动从辅助文档查找答案
5. **✅ 优先级明确**：7级排序，blocker+无答案优先
6. **✅ 决策清晰**：approved/conditional/rejected + 理由
