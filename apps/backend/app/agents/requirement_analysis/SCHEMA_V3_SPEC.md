# 测试驱动澄清架构 v3.0 规格说明

## 📋 概述

这是一个全新设计的测试驱动澄清架构，去除了旧版本的冗余字段，专注于从测试视角提出高质量的澄清问题。

### 核心设计原则

1. **测试优先**：每个澄清项都从"测试如何验证"的角度出发
2. **可执行性**：提供可直接转化为测试用例的输出
3. **决策导向**：明确需要人工裁决的业务点，而非开放式大问题
4. **证据驱动**：所有推荐选项必须有来源依据
5. **风险分级**：按测试风险和交付影响分优先级

---

## 🏗️ 架构对比

### v2.0（旧版，兼容模式）

```python
{
    "question": "...",           # 通用问题
    "impact": "...",             # 通用影响
    "test_impact": "...",        # 测试影响（常为空）
    "human_question": "...",     # 人工问题
    "recommended_options": [...], # 推荐选项
    "decision_options": [...],   # 决策选项
}
```

**问题**：字段冗余、语义重叠、测试信息不够详细

### v3.0（新版，纯测试驱动）

```python
{
    "decision_point": "...",           # 需要裁决什么
    "why_clarify": "...",              # 为什么需要澄清
    "test_impact": "...",              # 测试影响
    "risk_scenario": "...",            # Given-When-Then 风险场景
    "affected_surfaces": [...],        # 影响的测试表面
    "test_cases": [...],               # 测试用例草案（详细）
    "options": [...],                  # 澄清选项（含优劣分析）
}
```

**优势**：字段清晰、测试信息完整、可直接转化为测试用例

---

## 📊 核心数据结构

### 1. ClarificationItem（待澄清项）

#### 基础标识

```python
item_id: str                    # 唯一标识，如 CL-001
title: str                      # 简短标题
issue_category: Literal[...]    # 问题分类（10种）
priority: Literal["P0", "P1", "P2", "P3"]  # 优先级
```

#### 问题分类（issue_category）

| 分类 | 说明 | 示例 |
|-----|------|------|
| `contract_unclear` | 契约不明确 | 接口输入输出格式不明确 |
| `rule_missing` | 规则缺失 | 缺少计算规则、业务规则 |
| `boundary_undefined` | 边界未定义 | 最大值、最小值、空值处理 |
| `exception_unhandled` | 异常未处理 | 错误码、失败场景 |
| `state_ambiguous` | 状态模糊 | 状态流转规则不清楚 |
| `concurrency_unclear` | 并发不明确 | 幂等性、锁策略 |
| `permission_undefined` | 权限未定义 | 谁能做、什么不能做 |
| `dependency_unclear` | 依赖不清楚 | 外部依赖、数据依赖 |
| `acceptance_missing` | 验收标准缺失 | 不知道怎么算"完成" |
| `conflict` | 需求冲突 | 多处需求互相矛盾 |

#### 优先级（priority）

| 级别 | 说明 | 处理要求 |
|-----|------|---------|
| `P0` | 阻塞交付 | 必须立即澄清，否则无法开始开发/测试 |
| `P1` | 高风险 | 应优先澄清，风险较大 |
| `P2` | 中风险 | 建议澄清，有一定风险 |
| `P3` | 低风险 | 可后续澄清，风险较小 |

#### 测试驱动核心字段

```python
# 1. 决策点
decision_point: str
# 示例："重复提交订单时系统的处理策略"

# 2. 澄清原因
why_clarify: str
# 示例："当前需求未说明重复提交的处理规则，存在幂等性风险"

# 3. 测试影响
test_impact: str
# 示例："不澄清会导致：(1) 并发测试无法设计；(2) 无法验证是否产生重复数据；(3) 压测无法判定系统行为正确性"

# 4. 风险场景（Given-When-Then）
risk_scenario: str
# 示例：
# Given 订单处于'待支付'状态
# When 用户连续点击两次'提交订单'按钮
# Then 系统应按确认后的规则处理（幂等返回/拒绝重复/生成新订单）

# 5. 影响的测试表面
affected_surfaces: list[TestSurface]
# 示例：[
#   {
#     "surface_type": "api",
#     "rationale": "影响接口幂等性测试"
#   },
#   {
#     "surface_type": "data_consistency",
#     "rationale": "影响数据一致性测试"
#   }
# ]

# 6. 测试用例草案
test_cases: list[TestCase]
# 示例：见下文 TestCase 结构
```

---

### 2. TestCase（测试用例草案）

```python
{
    "test_id": "TC-001",
    "scenario": "Given 订单已创建且待支付\nWhen 用户连续点击两次支付按钮\nThen 第二次点击应返回'订单已支付'且不重复扣款",
    "test_type": "concurrency",
    "expected_result": "第二次请求返回 200，响应包含 'already_paid' 状态，用户余额仅扣减一次",
    "assertion_points": [
        "响应状态码为 200",
        "响应体包含 order_status='already_paid'",
        "数据库中只有一条支付记录",
        "用户余额仅扣减订单金额一次"
    ],
    "priority": "P0"
}
```

#### 测试类型（test_type）

| 类型 | 说明 |
|-----|------|
| `positive` | 正向测试（正常路径） |
| `negative` | 负向测试（异常路径） |
| `boundary` | 边界值测试 |
| `concurrency` | 并发测试 |
| `security` | 安全测试 |
| `performance` | 性能测试 |

#### 测试优先级（priority）

| 级别 | 说明 |
|-----|------|
| `P0` | 冒烟测试（必须通过） |
| `P1` | 核心功能测试 |
| `P2` | 重要功能测试 |
| `P3` | 边缘场景测试 |

---

### 3. ClarificationOption（澄清选项）

```python
{
    "option_id": "OPT-001",
    "label": "按幂等处理",
    "description": "重复提交时返回已有结果，不产生重复业务数据。第二次请求返回第一次的订单ID和状态。",
    
    # 优劣分析（测试视角）
    "pros": [
        "用户体验好，不会因网络抖动产生重复订单",
        "测试简单，验证返回的订单ID一致即可"
    ],
    "cons": [
        "需要实现请求去重逻辑（如：基于请求ID或业务唯一键）",
        "需要考虑去重窗口期（如：5分钟内认为是重复请求）"
    ],
    
    # 如果选择该选项，需要补充的测试
    "additional_tests": [
        "验证5分钟内重复请求返回相同订单ID",
        "验证5分钟后重复请求可创建新订单",
        "验证不同用户的相同参数不被误判为重复"
    ],
    
    "confidence": "high",
    "source": "电商系统最佳实践",
    "evidence_excerpt": ""
}
```

---

### 4. TestSurface（测试表面）

```python
{
    "surface_type": "api",
    "rationale": "该澄清项影响接口契约测试，需要明确接口的幂等性行为"
}
```

#### 测试表面类型

| 类型 | 说明 | 关注点 |
|-----|------|--------|
| `api` | API 契约层 | 输入输出、错误码、幂等性 |
| `state_flow` | 状态流转层 | 状态定义、流转规则、非法操作 |
| `data_consistency` | 数据一致性层 | 唯一性、关联规则、并发控制 |
| `permission` | 权限控制层 | 认证授权、数据隔离 |
| `security` | 安全层 | 敏感操作、审计日志 |
| `audit_log` | 审计日志层 | 操作留痕、可追溯性 |
| `async_task` | 异步任务层 | 任务状态、重试、超时 |
| `external_dependency` | 外部依赖层 | 第三方服务、降级策略 |
| `ui_feedback` | 用户反馈层 | 错误提示、成功反馈 |
| `migration` | 数据迁移层 | 历史数据、兼容性 |
| `non_functional` | 非功能需求层 | 性能、可用性、兼容性 |

---

### 5. ClarificationOutput（输出）

```python
{
    "items": [...],              # 待澄清项列表（按优先级排序）
    "summary": {...},            # 汇总统计
    "overall_assessment": "...", # 整体评估
    "test_strategy_recommendations": [...],  # 测试策略建议
    "generated_at": "2024-01-15T10:30:00Z",
    "model_version": "v3.0-test-driven"
}
```

#### ClarificationSummary（汇总）

```python
{
    # 总体统计
    "total": 15,
    "by_priority": {"P0": 3, "P1": 7, "P2": 4, "P3": 1},
    "by_category": {
        "contract_unclear": 5,
        "rule_missing": 3,
        "boundary_undefined": 4,
        "state_ambiguous": 2,
        "concurrency_unclear": 1
    },
    "by_resolution": {
        "auto_resolved": 2,
        "has_options": 10,
        "needs_input": 3
    },
    
    # 测试覆盖分析
    "test_surfaces_coverage": {
        "api": 8,
        "state_flow": 5,
        "data_consistency": 6,
        "permission": 3
    },
    "total_test_cases": 45,
    
    # 风险评估
    "blocking_count": 3,
    "high_risk_count": 7,
    
    # 推荐行动
    "recommended_actions": [
        "优先澄清 3 个 P0 阻塞项（CL-001, CL-005, CL-008）",
        "重点关注 API 契约层和数据一致性层的澄清",
        "建议补充并发测试和边界值测试"
    ]
}
```

---

## 🔄 完整示例

### 输入

```json
{
  "project_id": "proj-001",
  "document_id": "doc-001",
  "document_name": "电商订单系统需求",
  "primary_markdown_content": "...",
  "auxiliary_documents": [
    {
      "mapping_id": "aux-001",
      "filename": "订单API设计文档.md",
      "markdown_content": "...",
      "document_type": "api_spec"
    }
  ],
  "config": {
    "max_options_per_item": 3,
    "max_test_cases_per_item": 5,
    "auto_resolve_confidence_threshold": "high",
    "generate_detailed_test_cases": true
  }
}
```

### 输出

```json
{
  "items": [
    {
      "item_id": "CL-001",
      "title": "订单重复提交处理策略待确认",
      "issue_category": "concurrency_unclear",
      "priority": "P0",
      "module_key": "order_management",
      "module_name": "订单管理",
      "source_stage": "testability",
      
      "decision_point": "用户重复提交订单时系统的处理策略",
      "why_clarify": "当前需求未说明重复提交的处理规则，存在幂等性风险和数据一致性风险",
      "test_impact": "不澄清会导致：(1) 并发测试无法设计；(2) 无法验证是否产生重复订单；(3) 压测无法判定系统行为正确性；(4) 生产环境可能出现重复扣款",
      
      "risk_scenario": "Given 用户在订单确认页面\nWhen 网络不稳定导致用户连续点击两次'提交订单'按钮\nThen 系统应按确认后的规则处理（避免重复下单或明确告知用户）",
      
      "affected_surfaces": [
        {
          "surface_type": "api",
          "rationale": "影响订单创建接口的幂等性设计"
        },
        {
          "surface_type": "data_consistency",
          "rationale": "影响订单数据的唯一性约束和并发控制"
        },
        {
          "surface_type": "ui_feedback",
          "rationale": "影响前端防重复提交的实现"
        }
      ],
      
      "test_cases": [
        {
          "test_id": "TC-001",
          "scenario": "Given 用户已添加商品到购物车\nWhen 用户在5秒内连续点击两次'提交订单'按钮\nThen 系统只创建一个订单，第二次点击返回已有订单ID",
          "test_type": "concurrency",
          "expected_result": "第一次返回 201 + 新订单ID；第二次返回 200 + 相同订单ID + 提示'订单已创建'",
          "assertion_points": [
            "数据库中只有一条订单记录",
            "两次请求返回的 order_id 相同",
            "第二次响应包含 is_duplicate=true 标识",
            "用户余额仅扣减一次"
          ],
          "priority": "P0"
        },
        {
          "test_id": "TC-002",
          "scenario": "Given 用户已成功创建订单A\nWhen 用户10分钟后使用相同商品再次提交订单\nThen 系统创建新订单B",
          "test_type": "positive",
          "expected_result": "返回 201 + 新订单ID（与订单A不同）",
          "assertion_points": [
            "数据库中有两条订单记录",
            "订单A和订单B的 order_id 不同",
            "两个订单的 created_at 相差10分钟"
          ],
          "priority": "P1"
        },
        {
          "test_id": "TC-003",
          "scenario": "Given 用户A和用户B购买相同商品\nWhen 两个用户几乎同时提交订单\nThen 系统分别为两个用户创建不同订单",
          "test_type": "concurrency",
          "expected_result": "两个用户各自获得独立的订单ID",
          "assertion_points": [
            "数据库中有两条订单记录",
            "两个订单的 user_id 不同",
            "两个订单的 order_id 不同"
          ],
          "priority": "P1"
        }
      ],
      
      "options": [
        {
          "option_id": "OPT-001",
          "label": "按幂等处理（推荐）",
          "description": "基于请求唯一标识（如 idempotency_key）或业务唯一键（如 user_id + cart_id + timestamp窗口）进行去重。5分钟内的重复请求返回已有订单，不创建新数据。",
          "pros": [
            "用户体验好，避免因网络问题产生重复订单",
            "测试简单，验证幂等性即可",
            "符合电商行业最佳实践"
          ],
          "cons": [
            "需要实现去重逻辑（Redis 或数据库唯一索引）",
            "需要定义去重窗口期（建议5分钟）",
            "需要前端传递 idempotency_key"
          ],
          "additional_tests": [
            "验证5分钟内重复请求返回相同订单ID",
            "验证5分钟后重复请求创建新订单",
            "验证 idempotency_key 缺失时的降级处理"
          ],
          "confidence": "high",
          "source": "电商系统最佳实践 + Stripe API 设计",
          "evidence_excerpt": "API 文档中提到：'所有创建类接口应支持幂等性，建议使用 Idempotency-Key 请求头'"
        },
        {
          "option_id": "OPT-002",
          "label": "拒绝重复提交",
          "description": "检测到重复提交时直接返回 409 Conflict 错误，提示用户'订单正在处理中，请勿重复提交'。",
          "pros": [
            "实现简单，后端逻辑清晰",
            "明确告知用户系统状态"
          ],
          "cons": [
            "用户体验较差，需要用户重新操作",
            "在网络不稳定时可能频繁报错",
            "增加前端防重复提交的复杂度"
          ],
          "additional_tests": [
            "验证重复提交返回 409 状态码",
            "验证错误信息包含明确的提示",
            "验证第一次请求成功后才拒绝后续重复"
          ],
          "confidence": "medium",
          "source": "保守策略",
          "evidence_excerpt": ""
        },
        {
          "option_id": "OPT-003",
          "label": "前端防重（不推荐）",
          "description": "仅依赖前端按钮禁用和防抖，后端不做重复检测。",
          "pros": [
            "后端实现最简单"
          ],
          "cons": [
            "不可靠，前端可被绕过（直接调用API）",
            "无法防御并发请求",
            "测试无法验证后端的防护能力"
          ],
          "additional_tests": [
            "验证绕过前端直接调用API时是否产生重复订单"
          ],
          "confidence": "low",
          "source": "不推荐的方案",
          "evidence_excerpt": ""
        }
      ],
      
      "recommended_option_id": "OPT-001",
      "recommendation_rationale": "基于以下理由推荐选项1（按幂等处理）：(1) 符合电商行业最佳实践；(2) 用户体验最好；(3) 测试覆盖全面；(4) 辅助文档明确提到应支持幂等性",
      
      "source_excerpt": "用户在订单确认页面点击'提交订单'后，系统创建订单并跳转到支付页面。",
      "related_requirements": ["订单创建流程", "支付流程"],
      
      "resolution_status": "has_options",
      "auto_resolution": "",
      "auto_resolution_source": "",
      
      "tags": ["高并发", "支付核心", "用户体验"],
      "related_items": ["CL-005"]
    }
  ],
  
  "summary": {
    "total": 1,
    "by_priority": {"P0": 1, "P1": 0, "P2": 0, "P3": 0},
    "by_category": {"concurrency_unclear": 1},
    "by_resolution": {"has_options": 1},
    "test_surfaces_coverage": {"api": 1, "data_consistency": 1, "ui_feedback": 1},
    "total_test_cases": 3,
    "blocking_count": 1,
    "high_risk_count": 0,
    "recommended_actions": [
      "立即澄清 CL-001（订单重复提交处理策略），这是 P0 阻塞项",
      "推荐选择选项1（按幂等处理），符合行业最佳实践",
      "澄清后需补充并发测试和幂等性测试"
    ]
  },
  
  "overall_assessment": "当前需求在并发处理方面存在 1 个 P0 阻塞项，需要立即澄清订单重复提交的处理策略。建议采用幂等处理方案，并补充相应的并发测试。",
  
  "test_strategy_recommendations": [
    "重点设计并发测试场景，验证订单创建的幂等性",
    "补充边界值测试，验证去重窗口期的边界行为",
    "增加压力测试，模拟高并发下的重复提交场景"
  ],
  
  "generated_at": "2024-01-15T10:30:00Z",
  "model_version": "v3.0-test-driven"
}
```

---

## 🚀 实施指南

### 1. 迁移步骤

#### Step 1：更新 Schema
```python
# 新建文件或替换现有文件
from schemas_v3_test_driven import (
    ClarificationItem,
    ClarificationOption,
    ClarificationOutput,
    TestCase,
    TestSurface,
)
```

#### Step 2：更新 Prompt
```python
# 在 clarification.py 中
CLARIFICATION_SYSTEM_PROMPT_V3 = """
你是测试驱动澄清智能体 v3.0

输出 Schema 严格遵循 ClarificationItem 结构：
- decision_point: 需要裁决的具体业务点
- why_clarify: 为什么需要澄清
- test_impact: 测试影响（3个以上具体影响）
- risk_scenario: Given-When-Then 格式
- test_cases: 3-5个代表性测试用例
- options: 2-4个互斥选项（每个选项包含 pros/cons/additional_tests）
"""
```

#### Step 3：更新 Agent 创建
```python
def clarification_agent_v3(model):
    return create_agent(
        model=model,
        tools=[],
        system_prompt=CLARIFICATION_SYSTEM_PROMPT_V3,
        response_format=ToolStrategy(ClarificationOutput),  # v3 Schema
    )
```

### 2. 前端适配

#### 显示澄清项卡片
```tsx
<ClarificationCard item={item}>
  <Priority level={item.priority} />
  <Title>{item.title}</Title>
  <Category>{item.issue_category}</Category>
  
  <Section title="决策点">
    {item.decision_point}
  </Section>
  
  <Section title="测试影响">
    {item.test_impact}
  </Section>
  
  <Section title="风险场景">
    <pre>{item.risk_scenario}</pre>
  </Section>
  
  <Section title="测试用例">
    {item.test_cases.map(tc => (
      <TestCase key={tc.test_id} data={tc} />
    ))}
  </Section>
  
  <Section title="澄清选项">
    {item.options.map(opt => (
      <Option key={opt.option_id} data={opt} />
    ))}
  </Section>
</ClarificationCard>
```

#### 测试用例展示
```tsx
<TestCaseCard test={testCase}>
  <Badge type={testCase.test_type} priority={testCase.priority} />
  <Scenario>{testCase.scenario}</Scenario>
  <ExpectedResult>{testCase.expected_result}</ExpectedResult>
  <AssertionPoints>
    {testCase.assertion_points.map(point => (
      <li key={point}>{point}</li>
    ))}
  </AssertionPoints>
</TestCaseCard>
```

### 3. API 路由

```python
@router.post("/api/v3/requirements/analyze")
async def analyze_requirement_v3(
    input: RequirementAnalysisInputV3
) -> ClarificationOutput:
    """需求分析 v3.0（纯测试驱动）"""
    return await run_requirement_analysis_v3(input)
```

---

## 📈 预期效果

### 输出质量提升

| 维度 | v2.0 | v3.0 | 提升 |
|-----|------|------|------|
| 澄清项数量 | 5-10个 | 8-15个 | +50% |
| 测试用例数量 | 0-5个 | 30-50个 | +900% |
| 选项质量 | 简单描述 | 含优劣分析 | 质变 |
| 可执行性 | 低 | 高 | ⭐⭐⭐⭐⭐ |

### 团队收益

- **需求分析师**：获得清晰的决策点和推荐方案
- **测试工程师**：获得可直接执行的测试用例草案
- **开发工程师**：理解边界和异常场景
- **项目经理**：清晰的风险评估和优先级

---

## ✅ 验收标准

部署 v3.0 后，每个需求分析应满足：

- [ ] 至少 80% 的澄清项有 3 个以上测试用例
- [ ] 至少 70% 的澄清项有 2 个以上选项
- [ ] 100% 的 P0 项有明确的推荐选项
- [ ] 100% 的测试用例有清晰的断言点
- [ ] 测试表面覆盖至少 5 个不同类型

---

## 🎉 总结

v3.0 架构通过以下改进，实现了真正的测试驱动澄清：

1. **去除冗余**：合并 `question`/`human_question`，`impact`/`test_impact` 等重复字段
2. **增强测试信息**：详细的测试用例、断言点、测试类型
3. **优劣分析**：每个选项都有 pros/cons，帮助决策
4. **可执行性**：输出可直接转化为自动化测试脚本

**核心价值**：让澄清过程成为测试设计的起点，而不是事后补救。
