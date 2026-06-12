# 需求分析架构设计

## 概述

基于业界最佳实践（BABOK、IREB、IEEE 830），采用**三块核心流程**完成需求分析：

```
需求分析流程
│
├─ 1️⃣ 需求理解
│  ├─ 解析模块结构
│  ├─ 识别业务对象、规则、字段
│  ├─ 提取状态流转和依赖
│  ├─ 识别风险和假设
│  └─ 输出：结构化的需求模型
│
├─ 2️⃣ 质量评估
│  ├─ 完整性检查（功能 + 非功能需求）
│  ├─ 清晰度检查（模糊词、歧义）
│  ├─ 可测试性检查（验收标准、测试覆盖）
│  ├─ 一致性检查（冲突识别）
│  └─ 输出：质量分数 + 决策建议
│
└─ 3️⃣ 待澄清内容
   ├─ 汇总所有问题
   ├─ 自动从辅助文档查找答案
   ├─ 提供建议选项和行内修正
   └─ 输出：优先级排序的问题列表
```

---

## 1️⃣ 需求理解 (Requirement Understanding)

### 职责

从原始需求文档中提取结构化信息，构建需求模型。

### 处理内容

#### 1.1 模块识别
- 识别功能模块/子系统
- 提取模块间依赖关系
- 识别模块边界

#### 1.2 业务对象建模
- 识别核心业务实体（用户、订单、产品等）
- 提取对象属性和字段
- 识别对象间关系（一对多、多对多）

#### 1.3 业务规则提取
- 验证规则（必填、格式、范围）
- 计算规则（价格、积分、折扣）
- 业务逻辑（审批流程、状态机）
- 权限规则（角色、操作权限）

#### 1.4 状态流转分析
- 识别状态机（订单状态、审批状态）
- 提取状态转换条件
- 识别终态和异常流

#### 1.5 风险和假设识别
- 技术风险（性能瓶颈、第三方依赖）
- 业务风险（范围蔓延、需求变更）
- 隐含假设（用户行为、系统环境）

### 输出结构

```typescript
interface RequirementUnderstandingOutput {
  modules: Module[]                    // 功能模块
  business_objects: BusinessObject[]   // 业务对象
  business_rules: BusinessRule[]       // 业务规则
  state_flows: StateFlow[]            // 状态流转
  dependencies: Dependency[]          // 依赖关系
  risks: Risk[]                       // 风险列表
  assumptions: Assumption[]           // 假设列表
}
```

### 示例

**输入**：
```
用户可以创建订单。订单创建后状态为"待支付"。
用户支付成功后，订单状态变为"已支付"。
订单金额大于1000元时，需要经理审批。
```

**输出**：
```yaml
modules:
  - module_key: order_management
    module_name: 订单管理
    capabilities: [创建订单, 支付订单, 审批订单]

business_objects:
  - name: 订单
    fields: [订单ID, 金额, 状态, 创建时间]

business_rules:
  - rule: "订单金额 > 1000 需要经理审批"
    type: validation
    condition: amount > 1000

state_flows:
  - object: 订单
    states: [待支付, 已支付, 待审批, 已完成]
    transitions:
      - from: 待支付, to: 已支付, trigger: 支付成功
      - from: 已支付, to: 待审批, condition: 金额 > 1000
```

---

## 2️⃣ 质量评估 (Quality Assessment)

### 职责

评估需求文档质量，识别缺口和问题，给出通过/不通过决策。

### 评估维度

#### 2.1 完整性检查 (Completeness)

**功能完整性**：
- ✓ 所有用户故事/功能点已描述
- ✓ 所有字段、规则、边界已定义
- ✓ 依赖关系已识别
- ✓ 异常场景已覆盖

**非功能需求完整性（NFR）**：
- ✓ 性能要求（响应时间、吞吐量、并发）
- ✓ 安全要求（认证、授权、加密、审计）
- ✓ 可用性要求（SLA、容错、恢复时间）
- ✓ 可扩展性要求（用户增长、数据量）
- ✓ 兼容性要求（浏览器、设备、API版本）
- ✓ 合规要求（GDPR、HIPAA、行业标准）

**评分标准**：
- 90-100%：优秀，缺失项 ≤ 2 个
- 75-89%：良好，缺失项 3-5 个
- 60-74%：一般，缺失项 6-10 个
- <60%：较差，需要大幅返工

#### 2.2 清晰度检查 (Clarity)

识别并标记模糊表述：

| 模糊词 | 问题 | 修正建议 |
|--------|------|----------|
| "快速" | 无法度量 | 指定响应时间：< 2s |
| "用户友好" | 主观判断 | 定义可用性指标：3步内完成 |
| "安全" | 范围不明 | 列出具体控制：密码复杂度、加密算法 |
| "可扩展" | 无具体目标 | 定义容量：支持10万并发用户 |
| "及时" | 时间模糊 | 指定时限：24小时内 |
| "适当的" | 标准不清 | 给出具体阈值或范围 |

**评分标准**：
- 模糊词数量 / 总需求数 < 5%：优秀
- 5-10%：良好
- 10-20%：一般
- >20%：较差

#### 2.3 可测试性检查 (Testability)

评估需求是否可验证：

**验收标准完整性**：
- ✓ 使用 Given-When-Then 格式
- ✓ 明确前置条件
- ✓ 明确操作步骤
- ✓ 明确预期结果（可观察）

**测试覆盖缺口**：
- 测试目标是否明确
- 用户角色/权限是否定义
- 测试数据要求是否明确
- 边界值和异常路径是否覆盖
- 错误提示和恢复策略是否定义

**示例**：

❌ 不可测：
```
系统应当快速响应用户操作
```

✅ 可测：
```
Given: 用户已登录
When: 点击"查询"按钮
Then: 页面在2秒内显示结果列表
```

#### 2.4 一致性检查 (Consistency)

识别冲突：

**术语一致性**：
- 同一概念使用不同名称（"用户" vs "客户"）
- 同一字段不同描述（"手机号必填" vs "手机号可选"）

**逻辑一致性**：
- 规则互相矛盾
- 状态流转冲突
- 权限规则冲突

**优先级一致性**：
- P0 功能依赖 P2 功能
- 必需功能标记为"可选"

### 质量决策

根据总体评分给出决策：

```typescript
interface QualityDecision {
  result: 'approved' | 'conditional' | 'rejected'
  overall_score: number  // 0-100
  rationale: string
  blocking_issues: string[]      // 必须解决才能通过
  recommended_actions: string[]  // 下一步建议
}
```

**决策标准**：
- **通过 (approved)**：总分 ≥ 90%，无 blocker 问题
- **有条件通过 (conditional)**：总分 75-89%，或有 1-2 个 blocker
- **拒绝 (rejected)**：总分 < 75%，或有 ≥3 个 blocker

---

## 3️⃣ 待澄清内容 (Clarification Items)

### 职责

汇总所有需要人工确认的问题，尝试自动找答案，提供修正建议。

### 问题来源

```
待澄清内容
├─ 来源1：需求理解阶段
│  ├─ 模块边界不清
│  ├─ 状态流转缺失
│  └─ 依赖关系模糊
│
├─ 来源2：质量评估阶段
│  ├─ 完整性缺口（缺失的规则、字段、NFR）
│  ├─ 清晰度问题（模糊词、歧义）
│  ├─ 可测试性缺口（验收标准缺失）
│  └─ 一致性冲突（术语、逻辑矛盾）
│
└─ 自动增强
   └─ 从辅助文档查找答案
```

### 问题结构

```typescript
interface ClarificationItem {
  id: string
  source: 'understanding' | 'completeness' | 'clarity' | 'testability' | 'consistency'
  module_key: string
  module_name: string
  
  // 问题描述（面向人工确认）
  question: string
  impact: string         // 不确认会造成的影响
  severity: 'blocker' | 'major' | 'minor'
  
  // 当前文本和建议修正
  current_text: string   // 原文（如果有）
  suggested_fix: string  // 建议修改为（可直接替换）
  
  // 建议选项（最多2个）
  recommended_options: Option[]
  
  // 辅助文档证据（如果找到）
  evidence: {
    mapping_id: string
    filename: string
    excerpt: string
    confidence: 'high' | 'medium' | 'low'
  }[]
  
  // 自动解答状态
  resolution_status: 'auto_resolved' | 'has_suggestions' | 'needs_manual'
}

interface Option {
  id: string
  label: string
  answer_markdown: string  // 可直接写入需求的内容
  rationale: string
  confidence: 'high' | 'medium' | 'low'
}
```

### 自动增强流程

```
1. 识别问题 → clarification_questions
   ↓
2. 从辅助文档查找相关内容
   ↓
3. 评估证据质量
   ├─ 高可信度 → auto_resolved（自动填充答案）
   ├─ 中等可信度 → has_suggestions（提供建议选项）
   └─ 低可信度/未找到 → needs_manual（等待人工）
   ↓
4. 按优先级排序输出
```

### 优先级排序

```python
priority_order = [
    ('blocker', 'needs_manual'),      # P0: 阻塞且无答案
    ('blocker', 'has_suggestions'),   # P1: 阻塞但有建议
    ('major', 'needs_manual'),        # P2: 主要问题无答案
    ('major', 'has_suggestions'),     # P3: 主要问题有建议
    ('minor', 'needs_manual'),        # P4: 次要问题无答案
    ('minor', 'has_suggestions'),     # P5: 次要问题有建议
    ('*', 'auto_resolved'),           # P6: 已自动解决（仅供确认）
]
```

### 示例

**问题识别**：
```yaml
question: "订单金额超过1000元时，审批超时时间是多少？"
source: completeness
severity: major
current_text: "订单金额大于1000元时，需要经理审批"
impact: "无法设置审批超时提醒，影响工单处理时效"
```

**自动查找辅助文档**：
```yaml
evidence:
  - filename: "运营规范.docx"
    excerpt: "所有审批流程超时时间统一为48小时"
    confidence: high
```

**生成建议修正**：
```yaml
suggested_fix: |
  订单金额大于1000元时，需要经理审批。
  审批超时时间：48小时。超时后自动转至上级审批。

recommended_options:
  - id: opt1
    label: "48小时（来自运营规范）"
    answer_markdown: "审批超时时间：48小时。超时后自动转至上级审批。"
    confidence: high
  
  - id: opt2
    label: "24小时（加快流程）"
    answer_markdown: "审批超时时间：24小时。超时后自动转至上级审批。"
    confidence: medium

resolution_status: has_suggestions
```

---

## 数据流

```
输入：原始需求文档 + 辅助文档
  ↓
┌─────────────────────────────────────┐
│ 1️⃣ 需求理解                          │
│ - 解析结构                            │
│ - 识别模块、对象、规则                │
│ - 提取状态、依赖、风险                │
└─────────────────────────────────────┘
  ↓
  modules, business_objects, rules, risks, assumptions
  ↓
┌─────────────────────────────────────┐
│ 2️⃣ 质量评估                          │
│ - 完整性检查（功能 + NFR）            │
│ - 清晰度检查（模糊词）                │
│ - 可测试性检查（验收标准）            │
│ - 一致性检查（冲突）                  │
└─────────────────────────────────────┘
  ↓
  quality_scores, gaps, conflicts, decision
  ↓
┌─────────────────────────────────────┐
│ 3️⃣ 待澄清内容                        │
│ - 汇总问题（来源1 + 来源2）           │
│ - 从辅助文档查找答案                  │
│ - 生成建议选项和行内修正              │
│ - 按优先级排序                        │
└─────────────────────────────────────┘
  ↓
  clarification_items (优先级排序)
  ↓
输出：结构化分析结果 + 优先级问题列表
```

---

## 质量标准

### 整体目标

- **生产就绪阈值**：总体质量分 ≥ 90%
- **可交付阈值**：总体质量分 ≥ 75%，且无 blocker 问题
- **需要返工**：总体质量分 < 75%，或有 ≥3 个 blocker

### 各维度权重

```python
weights = {
    'completeness': 0.30,    # 完整性最重要
    'clarity': 0.25,         # 清晰度
    'testability': 0.25,     # 可测试性
    'consistency': 0.20,     # 一致性
}

overall_score = sum(score * weight for score, weight in zip(scores, weights.values()))
```

---

## 与现有系统集成

### Agent 架构

```
RequirementAnalysisCodex
├─ PrimaryAnalysisAgent（阶段1 + 2）
│  ├─ 输入：primary_markdown_content
│  ├─ 技能：requirement-review（质量评估）
│  └─ 输出：RequirementAnalysisOutput（初版）
│
└─ AuxiliaryEnhancementAgent（阶段3）
   ├─ 输入：clarification_questions + auxiliary_documents
   ├─ 处理：从辅助文档查找答案
   └─ 输出：RequirementAuxiliaryEnhancementOutput
```

### Skill 重构

**当前**：
```
requirement-review/SKILL.md（159行整体文档）
```

**重构为**：
```
requirement-review/
├─ SKILL.md（总入口，30行）
├─ understanding/
│  ├─ module-parsing.md
│  ├─ business-object-modeling.md
│  └─ rule-extraction.md
│
├─ quality-assessment/
│  ├─ completeness.md
│  ├─ clarity.md
│  ├─ testability.md
│  └─ consistency.md
│
└─ references/
   ├─ nfr-checklist.md       # 非功能需求检查清单
   ├─ fuzzy-words.md         # 模糊词替换表
   └─ quality-standards.md   # 质量标准
```

---

## 输出示例

### 最终输出结构

```typescript
interface RequirementAnalysisResult {
  // 阶段1：需求理解
  understanding: {
    modules: Module[]
    business_objects: BusinessObject[]
    business_rules: BusinessRule[]
    state_flows: StateFlow[]
    risks: Risk[]
    assumptions: Assumption[]
  }
  
  // 阶段2：质量评估
  quality_assessment: {
    scores: {
      completeness: number
      clarity: number
      testability: number
      consistency: number
      overall: number
    }
    decision: QualityDecision
    gaps: Gap[]           // 缺口列表
    fuzzy_terms: FuzzyTerm[]  // 模糊词列表
    conflicts: Conflict[]     // 冲突列表
  }
  
  // 阶段3：待澄清内容
  clarification: {
    items: ClarificationItem[]  // 按优先级排序
    summary: {
      total: number
      auto_resolved: number
      has_suggestions: number
      needs_manual: number
      by_severity: {
        blocker: number
        major: number
        minor: number
      }
    }
  }
  
  // 综合报告
  analysis_report_markdown: string
  preliminary_requirement_markdown: string  // 可选：改进后的需求文档
}
```

---

## 参考标准

- **BABOK**（Business Analysis Body of Knowledge）- 业务分析知识体系
- **IREB**（International Requirements Engineering Board）- 国际需求工程委员会
- **IEEE 830** - 软件需求规格说明标准
- **ISO/IEC 25010** - 系统与软件质量模型
- **INVEST** - 用户故事质量准则（Independent, Negotiable, Valuable, Estimable, Small, Testable）

---

## 版本历史

- v1.0 (2026-06-12) - 初始版本，三块核心架构
  - 需求理解：模块解析 + 业务建模
  - 质量评估：4维度 + NFR + 决策
  - 待澄清内容：汇总 + 自动增强 + 优先级排序
