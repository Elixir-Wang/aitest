"""
需求分析 Agent v2.0 - 三块核心架构实现

流程：
1. UnderstandingAgent：需求理解
2. QualityAssessmentAgent：质量评估
3. ClarificationAgent：待澄清内容（自动增强）
"""

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_analysis.schemas_v2 import (
    RequirementUnderstandingOutput,
    QualityAssessmentOutput,
    ClarificationOutput,
    RequirementAnalysisResultV2,
)
from app.agents.requirement_analysis.utils.report_generator import generate_analysis_report
from app.agents.requirement_analysis.utils.requirement_enhancer import (
    generate_enhanced_requirement,
    get_auto_resolved_items,
)


# ============================================================================
# 1️⃣ 需求理解 Agent
# ============================================================================

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
- 遇到模糊或不清晰的内容，如实提取，不做解释或判断
""".strip()


def understanding_agent(model):
    """需求理解 Agent"""
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
    """运行需求理解 Agent"""
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


# ============================================================================
# 2️⃣ 质量评估 Agent
# ============================================================================

QUALITY_ASSESSMENT_SYSTEM_PROMPT = """
你是需求分析系统中的【质量评估智能体】。

## 职责

评估需求文档质量，识别缺口和问题，给出通过/不通过决策。

## 输入

- primary_markdown_content：主需求文档
- understanding_result：需求理解阶段的输出

## 评估维度

### 1. 完整性检查 (Completeness)

**功能完整性**：
- 所有用户故事/功能点已描述
- 所有字段、规则、边界已定义
- 依赖关系已识别
- 异常场景已覆盖

**非功能需求完整性（NFR）**：
检查是否定义了以下类别的需求：
- performance：响应时间、吞吐量、并发用户数
- security：认证方式、授权机制、加密算法、审计日志
- availability：SLA、容错策略、恢复时间目标（RTO）
- scalability：用户增长目标、数据量目标、扩展策略
- compatibility：浏览器兼容、设备兼容、API版本
- compliance：GDPR、HIPAA、行业标准、法律法规
- usability：易用性指标、无障碍要求
- maintainability：代码质量、可扩展性

对于缺失的 NFR，生成 NFRGap 项，并提供 suggested_requirement。

**评分规则**：
- 缺失项 0-2 个：90-100 分
- 缺失项 3-5 个：75-89 分
- 缺失项 6-10 个：60-74 分
- 缺失项 >10 个：<60 分

### 2. 清晰度检查 (Clarity)

识别并标记模糊表述：

**常见模糊词**：
- "快速"、"很快"、"响应快" → 指定响应时间：< 2s
- "用户友好"、"直观"、"简单" → 定义可用性指标：3步内完成
- "安全" → 列出具体控制：密码复杂度、加密算法
- "可扩展" → 定义容量目标：支持10万并发
- "及时"、"尽快"、"适当" → 指定时限或阈值
- "高性能"、"稳定"、"可靠" → 给出具体指标

对每个模糊词生成 FuzzyTerm 项，包含：
- current_text：原文
- issue：问题说明
- suggested_fix：建议修改为（具体、可度量）

**歧义表述**：
- 一句话有多种理解
- 逻辑关系不清（"和"、"或"）
- 代词指代不明

**评分规则**：
- 模糊词/歧义 占比 < 5%：90-100 分
- 5-10%：75-89 分
- 10-20%：60-74 分
- >20%：<60 分

### 3. 可测试性检查 (Testability)

**验收标准完整性**：
检查每个功能点是否有明确的验收标准，最好使用 Given-When-Then 格式：
```
Given: 前置条件（系统状态、用户角色、测试数据）
When: 操作步骤
Then: 预期结果（可观察、可度量）
```

对于缺失或不完整的验收标准，生成 AcceptanceCriteriaGap 项。

**测试覆盖缺口**：
检查以下测试点是否有明确定义：
- boundary_value：边界值（最大最小值、临界点）
- exception_path：异常路径（错误输入、网络异常、超时）
- error_message：错误提示内容
- permission：权限测试（无权限、跨租户）
- concurrency：并发场景（多用户同时操作）
- data_dependency：数据依赖（关联数据不存在、外键约束）

对于缺失的测试点，生成 TestCoverageGap 项。

**评分规则**：
- 90% 以上功能有完整验收标准：90-100 分
- 75-89%：75-89 分
- 60-74%：60-74 分
- <60%：<60 分

### 4. 一致性检查 (Consistency)

**规则冲突**：
- REQ-A 说"手机号必填"，REQ-B 说"手机号可选"
- 状态流转矛盾（A→B 和 B→A 同时存在且无条件）
- 优先级冲突（P0 依赖 P2）

**术语不一致**：
- 同一概念使用不同名称（"用户" vs "客户" vs "会员"）
- 同一字段不同描述

对于冲突，生成 Conflict 项，包含：
- evidence_1 和 evidence_2：冲突的两处原文
- impact：不解决的影响

对于术语问题，生成 TerminologyIssue 项。

**评分规则**：
- 无冲突，术语统一：90-100 分
- 1-2 个 minor 冲突：75-89 分
- 3-5 个冲突或 1 个 major 冲突：60-74 分
- ≥6 个冲突或 ≥2 个 blocker：<60 分

## 质量决策

根据总体评分给出决策：

**总分计算**：
```
overall_score = (
    completeness * 0.30 +
    clarity * 0.25 +
    testability * 0.25 +
    consistency * 0.20
)
```

**决策标准**：
- **approved**：总分 ≥ 90，且无 blocker 问题
- **conditional**：总分 75-89，或有 1-2 个 blocker（需解决后才能通过）
- **rejected**：总分 < 75，或有 ≥3 个 blocker（需要大幅返工）

在 rationale 中说明决策理由。
在 blocking_issues 中列出必须解决的问题。
在 recommended_actions 中给出下一步建议。

## 输出要求

1. 严格按照 QualityAssessmentOutput schema 输出
2. 每个问题必须有具体的 current_text 和 suggested_fix
3. 问题严重程度（severity）评估要准确：
   - blocker：阻塞进展，必须立即修复
   - major：显著影响质量，应在批准前修复
   - minor：质量改进项，最好修复
4. 分数要客观，有依据
""".strip()


def quality_assessment_agent(model):
    """质量评估 Agent"""
    return create_agent(
        model=model,
        tools=[],
        system_prompt=QUALITY_ASSESSMENT_SYSTEM_PROMPT,
        response_format=ToolStrategy(QualityAssessmentOutput),
    )


async def run_quality_assessment_agent(
    model,
    primary_markdown_content: str,
    understanding_result: RequirementUnderstandingOutput,
) -> QualityAssessmentOutput:
    """运行质量评估 Agent"""
    agent = quality_assessment_agent(model)

    user_content = f"""
# 主需求文档

{primary_markdown_content}

---

# 需求理解结果

{understanding_result.model_dump_json(indent=2)}

---

请对上述需求文档进行质量评估，从完整性、清晰度、可测试性、一致性四个维度进行分析。
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
        raise ValueError("质量评估智能体未返回结构化结果")

    return output


# ============================================================================
# 3️⃣ 待澄清内容 Agent（含自动增强）
# ============================================================================

CLARIFICATION_SYSTEM_PROMPT = """
你是需求分析系统中的【待澄清内容智能体】。

## 职责

汇总所有需要人工确认的问题，尝试从辅助文档自动找答案，提供修正建议。

## 输入

- understanding_result：需求理解阶段的输出
- quality_assessment_result：质量评估阶段的输出
- auxiliary_documents：辅助文档列表（可能为空）

## 处理流程

### 1. 汇总问题

从质量评估结果中提取所有需要澄清的问题：

**来源1：完整性检查**
- functional_gaps → source: completeness
- nfr_gaps → source: completeness
- missing_details → source: completeness

**来源2：清晰度检查**
- fuzzy_terms → source: clarity
- ambiguous_statements → source: clarity

**来源3：可测试性检查**
- acceptance_criteria_gaps → source: testability
- test_coverage_gaps → source: testability

**来源4：一致性检查**
- conflicts → source: consistency
- terminology_issues → source: consistency

### 2. 问题转换

将质量问题转换为 ClarificationItem：

- **question**：改写为直接面向人工确认的问题
  - ❌ 不好："缺少性能指标"
  - ✅ 好："请确认：系统响应时间要求是多少？并发用户数目标是多少？"

- **impact**：说明不确认的影响
  - "无法评估系统容量，可能导致上线后性能不足"

- **current_text**：原需求文本（如果有）

- **suggested_fix**：建议修正后的文本
  - 对于 fuzzy_terms，使用 suggested_fix
  - 对于 nfr_gaps，使用 suggested_requirement
  - 对于 conflicts，提供消除冲突的修改建议

### 3. 从辅助文档查找答案

如果提供了 auxiliary_documents，尝试自动找答案：

**查找策略**：
- 关键词匹配：提取问题中的关键词，在辅助文档中搜索
- 上下文相关性：判断辅助文档的段落是否能回答问题
- 证据质量评估：high（明确回答）/ medium（部分回答）/ low（相关但不明确）

**生成证据引用**：
```python
EvidenceReference(
    mapping_id="...",
    filename="运营规范.docx",
    excerpt="审批超时时间统一为48小时",
    section_hint="第3章 审批流程",
    confidence="high"
)
```

**生成建议选项**：
如果找到答案，生成 recommended_options：
```python
ClarificationOption(
    option_id="opt1",
    label="48小时（来自运营规范）",
    answer_markdown="审批超时时间：48小时。超时后自动转至上级审批。",
    confidence="high",
    source="运营规范.docx"
)
```

即使没找到答案，也应尽量从需求文档本身推理出 1-2 个合理的建议选项（标注 confidence: medium/low）。

### 4. 确定解答状态

- **auto_resolved**：从辅助文档找到高可信度答案（confidence: high）
- **has_suggestions**：有建议选项（来自辅助文档或推理）
- **needs_manual**：无法提供建议，需要人工确认

### 5. 优先级排序

按以下顺序排列 items：
1. (blocker, needs_manual)
2. (blocker, has_suggestions)
3. (major, needs_manual)
4. (major, has_suggestions)
5. (minor, needs_manual)
6. (minor, has_suggestions)
7. (*, auto_resolved)

### 6. 生成汇总统计

计算 ClarificationSummary：
- total：总问题数
- auto_resolved、has_suggestions、needs_manual：各状态计数
- by_severity：按严重程度分组
- by_source：按来源分组

## 输出要求

1. 严格按照 ClarificationOutput schema 输出
2. 每个 ClarificationItem 必须有清晰的 question 和 impact
3. suggested_fix 应该是完整的、可直接替换的文本
4. recommended_options 最多 2 个，且 answer_markdown 可直接写入需求文档
5. evidence 必须准确引用辅助文档（不得臆造）
6. 如果没有辅助文档，evidence 为空数组，但仍应尝试生成 recommended_options

## 注意事项

- 不要重复问题（去重）
- 不要生成没有实际价值的问题（如："文档格式需要优化"）
- 重点关注影响设计、开发、测试的关键问题
""".strip()


def clarification_agent(model):
    """待澄清内容 Agent"""
    return create_agent(
        model=model,
        tools=[],
        system_prompt=CLARIFICATION_SYSTEM_PROMPT,
        response_format=ToolStrategy(ClarificationOutput),
    )


async def run_clarification_agent(
    model,
    understanding_result: RequirementUnderstandingOutput,
    quality_assessment_result: QualityAssessmentOutput,
    auxiliary_documents: list = None,
) -> ClarificationOutput:
    """运行待澄清内容 Agent"""
    agent = clarification_agent(model)

    auxiliary_docs_text = ""
    if auxiliary_documents:
        auxiliary_docs_text = "# 辅助文档\n\n"
        for doc in auxiliary_documents:
            auxiliary_docs_text += f"## {doc.filename} (ID: {doc.mapping_id})\n\n"
            auxiliary_docs_text += f"{doc.markdown_content}\n\n---\n\n"
    else:
        auxiliary_docs_text = "# 辅助文档\n\n（无）\n"

    user_content = f"""
# 需求理解结果

{understanding_result.model_dump_json(indent=2)}

---

# 质量评估结果

{quality_assessment_result.model_dump_json(indent=2)}

---

{auxiliary_docs_text}

---

请汇总所有需要澄清的问题，尝试从辅助文档查找答案，并按优先级排序。
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
        raise ValueError("待澄清内容智能体未返回结构化结果")

    return output


# ============================================================================
# 完整流程编排
# ============================================================================

async def run_requirement_analysis_v2(
    model,
    primary_markdown_content: str,
    auxiliary_documents: list = None,
    config: dict = None,
) -> RequirementAnalysisResultV2:
    """
    运行完整的需求分析流程 v2.0

    Args:
        model: LLM 模型
        primary_markdown_content: 主需求文档
        auxiliary_documents: 辅助文档列表
        config: 配置参数

    Returns:
        RequirementAnalysisResultV2: 完整的分析结果
    """

    # 1️⃣ 需求理解
    understanding_result = await run_understanding_agent(
        model=model,
        primary_markdown_content=primary_markdown_content,
    )

    # 2️⃣ 质量评估
    quality_assessment_result = await run_quality_assessment_agent(
        model=model,
        primary_markdown_content=primary_markdown_content,
        understanding_result=understanding_result,
    )

    # 3️⃣ 待澄清内容（含自动增强）
    clarification_result = await run_clarification_agent(
        model=model,
        understanding_result=understanding_result,
        quality_assessment_result=quality_assessment_result,
        auxiliary_documents=auxiliary_documents,
    )

    # 确定状态
    decision = quality_assessment_result.decision.result
    clarification_needs_manual = clarification_result.summary.needs_manual

    if decision == "rejected":
        status = "blocked"
    elif clarification_needs_manual > 0:
        status = "needs_clarification"
    else:
        status = "completed"

    # 生成分析报告
    analysis_report = generate_analysis_report(
        understanding_result,
        quality_assessment_result,
        clarification_result,
    )

    # 生成增强版需求文档
    auto_resolved_items = get_auto_resolved_items(clarification_result.items)
    enhanced_requirement = generate_enhanced_requirement(
        original_markdown=primary_markdown_content,
        auto_resolved_items=auto_resolved_items,
    )

    return RequirementAnalysisResultV2(
        status=status,
        understanding=understanding_result,
        quality_assessment=quality_assessment_result,
        clarification=clarification_result,
        analysis_report_markdown=analysis_report,
        enhanced_requirement_markdown=enhanced_requirement,
        metadata={
            "version": "2.0",
            "config": config or {},
        }
    )


# 报告生成函数已移至 utils/report_generator.py


__all__ = [
    "run_requirement_analysis_v2",
    "run_understanding_agent",
    "run_quality_assessment_agent",
    "run_clarification_agent",
]
