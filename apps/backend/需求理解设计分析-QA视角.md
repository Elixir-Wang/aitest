# 需求理解设计分析 - 从测试/QA 视角

## 📊 当前架构概览

### 需求分析系统 v2.0 的三层架构

```
1️⃣ 需求理解 (Requirement Understanding)
   → 识别模块、业务对象、规则、状态流转
   → 识别依赖、风险、假设

2️⃣ 质量评估 (Quality Assessment)  
   → 完整性、清晰度、可测试性、一致性
   → NFR 评估（性能、安全、可用性等）

3️⃣ 待澄清内容 (Clarification)
   → 汇总问题，自动查找答案
   → 提供决策选项和测试用例
```

### 深度理解架构（需求理解第一步）

```
业务分析 (BusinessAnalyzer)
  → 识别业务痛点、核心价值、关键流程、决策点
  
领域建模 (DomainModeler)  
  → 核心概念、领域实体、不变性约束、状态机
  
风险识别 (RiskIdentifier)
  → 复杂场景、风险根因、边界条件、测试策略
```

---

## ⚠️ 从 QA 视角发现的问题

### 问题 1: **需求理解视角偏向"开发理解"，不够"测试友好"**

**当前设计：**
- **业务分析**：关注"为什么"（业务痛点、核心价值）
- **领域建模**：关注"是什么"（领域实体、关系、生命周期）
- **风险识别**：关注"怎么测"（复杂场景、边界、测试策略）

**问题所在：**

1. **业务分析过于抽象**
   - 输出的"业务痛点"、"核心价值"对 QA 来说太宏观
   - QA 需要的是：**用户会怎么用、哪些操作路径、什么场景下会失败**
   - 例如：业务分析说"用户无法利用企业私有数据训练AI"，但 QA 需要知道"用户上传文档的具体步骤、每步可能的失败点"

2. **领域建模偏重设计，不够面向测试**
   - 输出的"领域实体"、"不变性约束"是开发视角
   - QA 需要的是：**什么数据会变、什么关系会断、什么约束容易被破坏**
   - 例如：领域模型说"订单 belongs_to 用户"，但 QA 需要知道"删除用户时订单会怎样、能否转移订单"

3. **风险识别虽然面向测试，但缺少"可执行测试场景"**
   - 输出的"复杂场景"、"风险根因"仍然偏向描述性
   - QA 需要的是：**Given-When-Then 测试场景、具体的断言点、测试数据准备**

**对比 v3.0 的澄清架构：**
```python
# v3.0 澄清架构非常测试友好
{
    "decision_point": "重复提交订单时的处理策略",
    "risk_scenario": """
        Given 订单处于'待支付'状态
        When 用户连续点击两次'提交订单'
        Then 系统应按确认后的规则处理
    """,
    "test_cases": [
        {
            "scenario": "...",
            "assertion_points": ["响应码", "数据一致性", "幂等性"],
            "priority": "P0"
        }
    ]
}
```

---

### 问题 2: **输出结构不一致，导致信息割裂**

**当前情况：**

- **深度理解** 输出：`DeepUnderstandingResult`（业务洞察 + 领域模型 + 风险画像）
- **需求理解** 输出：`RequirementUnderstandingOutput`（模块 + 依赖 + 风险 + 假设）
- **质量评估** 输出：`QualityAssessmentOutput`（完整性 + 清晰度 + 可测试性）
- **澄清内容** 输出：`ClarificationOutput`（待澄清项 + 测试用例）

**问题：**
1. QA 需要跨越多个输出结构才能获取完整的测试信息
2. 同样的概念在不同输出中用不同的字段名（如 `Risk` vs `RiskRootCause` vs `TestStrategy`）
3. 没有统一的"测试友好输出视图"

---

### 问题 3: **Token 超限问题会影响长需求文档**

**分析：**
- 业务分析：`requirement_doc`
- 领域建模：`requirement_doc` + `BusinessInsight JSON`
- 风险识别：`requirement_doc` + `BusinessInsight JSON` + `DomainModel JSON`

对于 50KB 的需求文档，到风险识别阶段可能累积 **~80KB (32,000+ tokens)**。

**影响：**
- 超过某些模型的 context 限制
- 成本高昂
- 响应时间长

---

### 问题 4: **缺少"测试人员的需求消化视图"**

**QA 人员需要什么？**

1. **功能点清单**（What to test）
   - 每个功能的输入、输出、前置条件、后置条件
   - 正常路径、异常路径、边界条件

2. **测试场景清单**（How to test）
   - Given-When-Then 场景
   - 测试数据准备
   - 断言点

3. **风险优先级**（What to test first）
   - 按风险等级排序的测试点
   - P0/P1/P2/P3 优先级

4. **数据流和依赖**（What affects what）
   - 数据如何流动
   - 模块之间的依赖关系
   - 外部系统依赖

**当前架构缺少这样的"测试友好汇总视图"。**

---

## 💡 改进建议

### 建议 1: **重构需求理解，面向"测试场景提取"**

**新的第一步：测试场景提取 (Test Scenario Extraction)**

```python
class TestScenarioExtractor:
    """从需求中提取可测试场景"""
    
    async def extract(self, requirement_doc: str) -> TestScenarioInsight:
        return TestScenarioInsight(
            # 1. 功能点清单
            features=[
                {
                    "feature_name": "用户登录",
                    "preconditions": ["用户已注册", "账号未被锁定"],
                    "inputs": ["用户名", "密码"],
                    "outputs": ["JWT token", "用户信息"],
                    "normal_path": "输入正确凭证 → 返回 token",
                    "exception_paths": [
                        "用户名不存在 → 返回 404",
                        "密码错误 → 返回 401",
                        "账号锁定 → 返回 403"
                    ],
                    "boundary_conditions": [
                        "密码长度 < 8 → 拒绝",
                        "连续失败 3 次 → 锁定账号"
                    ]
                }
            ],
            
            # 2. 测试场景清单（Given-When-Then）
            test_scenarios=[
                {
                    "scenario_id": "TS-001",
                    "title": "正常登录",
                    "given": "用户已注册且账号未锁定",
                    "when": "输入正确的用户名和密码",
                    "then": "返回 200 和有效的 JWT token",
                    "test_type": "functional",
                    "priority": "P0",
                    "assertion_points": [
                        "状态码 = 200",
                        "响应包含 access_token",
                        "token 可解析且未过期"
                    ]
                },
                {
                    "scenario_id": "TS-002",
                    "title": "密码错误",
                    "given": "用户已注册",
                    "when": "输入错误的密码",
                    "then": "返回 401 且不生成 token",
                    "test_type": "negative",
                    "priority": "P1"
                }
            ],
            
            # 3. 数据依赖图
            data_flow=[
                {
                    "from": "用户输入",
                    "to": "认证服务",
                    "data": "用户名 + 密码",
                    "validation": "非空、格式校验"
                },
                {
                    "from": "认证服务",
                    "to": "用户数据库",
                    "data": "用户名查询",
                    "risk": "数据库不可用 → 503"
                }
            ],
            
            # 4. 风险热点
            risk_hotspots=[
                {
                    "area": "账号锁定逻辑",
                    "risk": "并发登录导致计数不准",
                    "complexity": "concurrency",
                    "priority": "P0",
                    "test_strategy": "压测 + 并发测试"
                }
            ]
        )
```

**优势：**
- ✅ 直接面向测试人员的需求
- ✅ 输出可直接转化为测试用例
- ✅ 覆盖正常/异常/边界场景
- ✅ Given-When-Then 格式，易于理解

---

### 建议 2: **简化深度分析链，减少 Token 累积**

**方案 A：只传递摘要，不传递完整 JSON**

```python
# 风险识别时，不传递完整的 requirement_doc
risk_profile = await self.risk_identifier.identify(
    business_summary=business_insight.summary,  # 只传摘要
    domain_summary=domain_model.summary,        # 只传摘要
    key_entities=[e.name for e in domain_model.entities],  # 只传关键信息
)
```

**方案 B：分块处理长文档**

```python
# 将长需求文档分块
chunks = split_requirement_doc(requirement_doc, max_chunk_size=10000)

# 并行处理各块
results = await asyncio.gather(
    *[self.business_analyzer.analyze(chunk) for chunk in chunks]
)

# 合并结果
business_insight = merge_business_insights(results)
```

**方案 C：使用更大 context 的模型**

- 对于需求分析，使用 `Claude Sonnet 4` 或 `GPT-4 Turbo`（128K context）

---

### 建议 3: **创建"QA 视图"，统一测试信息**

```python
class QARequirementView(BaseModel):
    """面向 QA 的需求视图"""
    
    # 1. 测试清单（按优先级排序）
    test_checklist: list[TestItem] = [
        {
            "id": "T-001",
            "feature": "用户登录",
            "scenario": "正常登录流程",
            "priority": "P0",
            "test_type": "functional",
            "given_when_then": "...",
            "assertion_points": [...],
            "test_data": {"username": "test@example.com", "password": "Test123!"},
            "risk_level": "low"
        }
    ]
    
    # 2. 风险热点（需要重点测试的地方）
    risk_hotspots: list[RiskHotspot] = [
        {
            "area": "支付流程",
            "risk": "并发支付导致重复扣款",
            "impact": "high",
            "test_strategy": "并发测试 + 幂等性验证",
            "related_test_ids": ["T-015", "T-016"]
        }
    ]
    
    # 3. 数据流图（便于理解依赖）
    data_flow_diagram: str  # Mermaid diagram
    
    # 4. 待澄清项（阻塞测试的问题）
    blocking_questions: list[ClarificationItem]
    
    # 5. 测试覆盖度检查
    coverage_analysis: {
        "total_features": 10,
        "testable_features": 8,
        "untestable_features": 2,  # 需求不够清晰，无法测试
        "coverage_percentage": 80,
        "gaps": ["用户权限边界未定义", "异常恢复机制未说明"]
    }
```

---

### 建议 4: **优化 Prompt，强调"可测试性"**

**当前 BUSINESS_ANALYSIS_PROMPT 的问题：**
- 过于关注"为什么"（业务痛点、核心价值）
- 缺少"怎么测"的视角

**改进后的 PROMPT：**

```python
TEST_ORIENTED_REQUIREMENT_ANALYSIS_PROMPT = """
你是资深的测试架构师和 QA 专家。

从**测试视角**分析需求，帮助 QA 人员理解"如何测试"。

## 分析任务

### 1. 功能点提取（What to test）
从需求中提取所有可测试的功能点，对每个功能点：
- 输入是什么？
- 输出是什么？
- 前置条件是什么？
- 正常路径是什么？
- 异常路径有哪些？
- 边界条件在哪里？

### 2. 测试场景生成（How to test）
为每个功能点生成 Given-When-Then 测试场景：
- Given: 前置条件和初始状态
- When: 执行的操作
- Then: 预期的结果和断言点

覆盖：
- 正常场景（Happy Path）
- 异常场景（Error Handling）
- 边界场景（Boundary Conditions）
- 并发场景（Concurrency）

### 3. 风险识别（What to test first）
识别测试风险热点：
- 哪些地方逻辑复杂、容易出错？
- 哪些地方涉及并发、状态转换？
- 哪些地方依赖外部系统？
- 哪些地方有数据一致性风险？

### 4. 数据依赖分析（Test data preparation）
识别测试数据依赖：
- 需要准备哪些测试数据？
- 数据之间有什么依赖关系？
- 哪些数据会影响测试结果？

### 5. 可测试性评估（Testability check）
评估需求的可测试性：
- 哪些功能可以测试？
- 哪些功能无法测试（需求不清晰）？
- 哪些地方需要澄清才能测试？

## 输出格式
严格按照 TestOrientedRequirementAnalysis schema 输出。

## 质量标准
✅ 好的分析：
- 测试场景具体、可执行
- 断言点明确
- 覆盖正常/异常/边界
- 风险评估准确
- 可测试性评估客观

❌ 避免：
- 泛泛而谈（"系统应该稳定"）
- 缺少具体场景
- 没有断言点
- 忽略边界和异常
"""
```

---

## 🎯 总结：如何让 AI 更好地为 QA 梳理需求

### 核心原则

1. **面向测试场景，而非业务分析**
   - 不要问"为什么要这个功能"
   - 要问"如何测试这个功能"

2. **输出可执行的测试信息**
   - Given-When-Then 场景
   - 具体的断言点
   - 测试数据准备

3. **覆盖正常/异常/边界/并发**
   - 不只是 Happy Path
   - 重点关注容易出错的地方

4. **提供优先级和风险评估**
   - P0/P1/P2/P3 优先级
   - 风险热点标注

5. **统一的测试友好视图**
   - 不要让 QA 跨越多个输出结构
   - 提供一个"QA Dashboard"

### 推荐架构

```
需求文档
    ↓
【测试场景提取】
    ├─ 功能点清单（What to test）
    ├─ 测试场景清单（How to test, Given-When-Then）
    ├─ 数据依赖图（Test data）
    └─ 风险热点（What to test first）
    ↓
【可测试性评估】
    ├─ 可测试功能
    ├─ 不可测试功能（需求不清）
    └─ 测试覆盖度分析
    ↓
【澄清问题生成】（复用 v3.0 架构）
    ├─ 决策点
    ├─ 风险场景
    ├─ 测试用例草案
    └─ 优先级排序
    ↓
【QA 需求视图】
    - 测试清单
    - 风险热点
    - 数据流图
    - 待澄清项
    - 覆盖度分析
```

---

## 📋 行动建议

### 短期（优先修复）

1. ✅ **修复 `ChatOpenAI` 命名冲突**（已完成）
2. **优化 Token 使用**：在风险识别时只传递摘要，不传完整文档
3. **补充"测试场景提取"视角**：在业务分析中增加测试场景提取

### 中期（架构优化）

4. **创建 QA 视图**：统一测试信息输出
5. **重构 PROMPT**：强调可测试性和测试场景
6. **补充测试数据准备指导**

### 长期（全面重构）

7. **重新设计需求理解架构**：从"开发视角"转向"测试视角"
8. **与 v3.0 澄清架构对齐**：统一风格和输出格式
9. **提供测试用例生成能力**：从需求直接生成测试代码框架
