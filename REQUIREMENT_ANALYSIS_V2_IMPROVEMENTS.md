# 需求分析架构 v2.1 改进总结

基于 baigong-platform-requirement-analyzer skill 的改进实施文档

---

## 📋 实施概览

| 改进项 | 状态 | 位置 | 说明 |
|-------|------|------|------|
| ✅ 质疑驱动节点 | 已完成 | `agents/questioning.py` | 9宫格矩阵 + 反向破坏场景 |
| ✅ 视觉化分级标记 | 已完成 | `core/schemas.py` | 🔴🟡🟢标记 + risk_level |
| ✅ 工作流集成 | 已完成 | `orchestrator.py` | 理解 → **质疑** → 质量评估 → 澄清 |
| ⏳ 历史需求检索 | 待实施 | - | Phase 2 |
| ⏳ 架构图自动生成 | 待实施 | - | Phase 2 |

---

## 🎯 核心改进点

### 1. 质疑驱动节点（questioning agent）

**插入位置**：理解节点 → **质疑节点** → 质量评估节点

**核心能力**：

#### 1.1 九宫格质疑矩阵
对每个 P0/P1 功能点进行全方位质疑：

```python
九宫格维度：
- WHAT: 功能边界/字段定义/规则是否明确？
- WHY: 业务必要性是否充分？
- WHO: 角色权限是否完整？
- WHEN: 触发时机/超时阈值是否明确？
- WHERE: 入口/场景覆盖是否完整？
- HOW: 技术方案是否明确？
- HOW_MUCH: 性能/容量/成本边界是否定义？
- WHAT_IF: 异常/降级场景是否覆盖？
- WHY_NOT: 不做行不行？是否过度设计？
```

**输出示例**：
```json
{
  "feature_id": "F-001",
  "feature_name": "用户注册",
  "priority": "P0",
  "grid_items": [
    {
      "dimension": "WHAT",
      "status": "Q-001",
      "question": "注册成功后的响应格式是什么？",
      "issue": "需求未定义成功和失败的响应结构"
    },
    {
      "dimension": "WHY",
      "status": "✅"
    }
  ]
}
```

#### 1.2 反向破坏场景（每个核心功能≥3条）
从攻击者视角思考如何破坏需求：

| 攻击向量 | 示例 |
|---------|------|
| malicious_input | 超长字符/SQL注入/XSS/Prompt注入 |
| concurrency | 多人同时操作同一资源 |
| resource_exhaustion | Token/磁盘/内存用完 |
| dependency_failure | 上游API/模型/DB挂了 |
| rollback_chaos | 反复创建-删除-恢复 |
| permission_drift | 用户离职后数据归属 |
| data_pollution | 脏数据/不兼容数据导入 |

**输出示例**：
```json
{
  "scenario_id": "ADV-001",
  "feature_id": "F-001",
  "attack_vector": "concurrency",
  "description": "用户连续点击两次注册按钮",
  "expected_defense": "基于幂等键去重，第二次返回相同用户ID",
  "actual_consequence": "如果没防御，会创建两个相同用户名的账户",
  "risk_level": "🔴"
}
```

#### 1.3 可执行性/可实现性检测
- 可执行性：从测试角度判断能否测试
- 可实现性：从技术角度判断能否实现

#### 1.4 需求漏洞检测
10大漏洞类型：
- logical_flaw（逻辑漏洞）
- missing_feature（功能遗漏）
- rule_conflict（规则矛盾）
- state_conflict（状态冲突）
- permission_breach（权限越界）
- boundary_missing（边界缺失）
- exception_unhandled（异常漏处理）
- concurrency_undefined（并发未定义）
- degradation_undefined（降级未定义）
- consistency_issue（一致性问题）

#### 1.5 风险熔断机制
自动判断是否暂停项目：

```python
熔断规则：
- 🔴 数量 ≥ 5 条 → "⛔ 高风险需求：建议暂缓启动开发，重新评审"
- 🔴 + 🟡 数量 ≥ 15 条 → "⚠️ 需求成熟度低：建议组织 PRD 二次评审会"
- 否则 → "✅ 风险可控，可以继续推进"
```

---

### 2. 视觉化分级标记

**位置**：`ClarificationItem` 模型

**新增字段**：
```python
visual_marker: str = Field(
    description="🔴(P0高风险阻塞) / 🟡(P1/P2中风险) / 🟢(P3低风险)"
)

risk_level: Literal["high", "medium", "low"] = Field(
    description="high(阻塞上线) / medium(影响范围/体验) / low(可观察可优化)"
)
```

**映射规则**：
| Priority | Visual Marker | Risk Level | 说明 |
|----------|---------------|------------|------|
| P0 | 🔴 | high | 阻塞交付，影响主流程、测试设计 |
| P1 | 🟡 | medium | 高风险，影响边界、异常、性能 |
| P2 | 🟡 | medium | 中风险，需关注但不阻碍推进 |
| P3 | 🟢 | low | 低风险，信息补充、文档说明 |

**Clarification Agent 自动生成**：
在 prompt 中明确要求根据 priority 自动设置 visual_marker 和 risk_level。

---

## 🏗️ 新架构工作流

```
┌─────────────────────────────────────────────────────────┐
│             需求分析工作流 v2.1                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1️⃣ 理解节点 (Understanding)                             │
│     └─ 业务洞察 + 领域模型 + 风险画像                       │
│                                                         │
│  2️⃣ 质疑节点 (Questioning) ⭐ 新增                        │
│     ├─ 9宫格质疑矩阵                                      │
│     ├─ 反向破坏场景（5大攻击向量）                          │
│     ├─ 可执行性/可实现性检测                               │
│     ├─ 需求漏洞检测                                       │
│     └─ 风险熔断判断                                       │
│                                                         │
│  3️⃣ 质量评估节点 (Quality Assessment)                     │
│     └─ 完整性/清晰度/可测性/一致性                          │
│                                                         │
│  4️⃣ 澄清节点 (Clarification) ✨ 增强                      │
│     ├─ 整合质疑节点的疑点                                  │
│     ├─ 视觉化分级（🔴🟡🟢）                                │
│     └─ 测试驱动澄清（7大维度）                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 📂 文件变更清单

### 新增文件
1. **`apps/backend/app/agents/requirement_analysis/agents/questioning.py`**
   - 质疑驱动智能体
   - 包含 9 宫格、反向场景、可执行性/可实现性检测、需求漏洞、风险熔断

### 修改文件

#### 1. `core/schemas.py`
```python
# 新增字段到 ClarificationItem
visual_marker: str  # 🔴🟡🟢
risk_level: Literal["high", "medium", "low"]

# 新增字段到 RequirementAnalysisResultV2
questioning: QuestioningOutput | None
```

#### 2. `orchestrator.py`
```python
# 新增质疑节点调用
questioning, questioning_metadata = await run_questioning_agent(
    model=model,
    primary_markdown_content=input_data.primary_markdown_content,
    understanding_result=understanding,
    understanding_brief=understanding_brief,
    run_id=input_data.run_id or "",
    metadata=metadata,
)

# 在结果中返回
return RequirementAnalysisResultV2(
    questioning=questioning,
    ...
)
```

#### 3. `agents/clarification.py`
```python
# 更新 prompt，要求自动生成 visual_marker 和 risk_level
# 根据 priority 自动映射：
# P0 → 🔴 high
# P1/P2 → 🟡 medium  
# P3 → 🟢 low
```

---

## 🚀 使用示例

### 调用方式（保持不变）
```python
from app.agents.requirement_analysis import run_requirement_analysis

result = await run_requirement_analysis(
    RequirementAnalysisInputV2(
        primary_markdown_content="需求文档内容",
        project_id="proj-001",
        document_id="doc-001",
    )
)

# 访问质疑分析结果
questioning = result.questioning
print(f"9宫格矩阵数量: {len(questioning.nine_grid_matrices)}")
print(f"反向场景数量: {len(questioning.adversarial_scenarios)}")
print(f"风险熔断状态: {questioning.risk_breaker.breaker_status}")

# 访问视觉化分级
for item in result.clarification.items:
    print(f"{item.visual_marker} [{item.priority}] {item.title}")
    # 输出示例：
    # 🔴 [P0] 订单状态流转规则待确认
    # 🟡 [P1] 并发提交处理策略待确认
    # 🟢 [P3] 术语统一建议
```

---

## 📊 改进效果对比

| 维度 | 改进前 | 改进后 |
|------|-------|-------|
| **风险识别** | 被动发现 | **主动质疑** + 反向破坏 |
| **问题可视化** | 文本描述 | **🔴🟡🟢** 直观标记 |
| **风险管控** | 无自动判断 | **熔断机制**（🔴≥5 / 总≥15） |
| **测试介入点** | 澄清阶段 | **理解阶段**（更早） |
| **分析深度** | 3个维度 | **9个维度**（全方位质疑） |

---

## 🔄 Phase 2 待实施功能

### 1. 历史需求检索系统
```python
# apps/backend/app/agents/requirement_analysis/services/history.py

async def search_similar_requirements(
    current_requirement_name: str,
    release_version_dir: str
) -> list[HistoricalRequirement]:
    """
    两阶段检索：
    1. 标题相关性评分（需求名标准化 + 同义词归一）
    2. 读取 Top 3 高/中相关文档，做内容对比
    
    输出：复用点/变更点/冲突点/废弃点/风险点
    """
    pass
```

**标准化规则**：
- 删除无效前后缀（需求功能点分析、PRD、评审稿）
- 删除版本日期（V1.0、2026-05-24）
- 同义词归一（技能=Skill、智能体=Agent）
- 保留核心名词（模块名、功能名、流程名）

### 2. 架构图自动生成
```python
# apps/backend/app/agents/requirement_analysis/utils/diagram.py

async def auto_generate_architecture_diagram(
    understanding: RequirementUnderstandingOutput
) -> str:
    """
    从理解结果自动生成 Mermaid 架构图
    → 调用 Kroki API 转 PNG
    → 返回图片路径
    """
    pass
```

---

## 🧪 测试建议

### 单元测试
```python
# tests/agents/requirement_analysis/test_questioning.py

async def test_questioning_agent_nine_grid():
    """测试 9 宫格矩阵生成"""
    result = await run_questioning_agent(...)
    assert len(result.nine_grid_matrices) > 0
    for matrix in result.nine_grid_matrices:
        assert len(matrix.grid_items) == 9  # 必须有 9 个维度

async def test_questioning_agent_adversarial():
    """测试反向破坏场景生成"""
    result = await run_questioning_agent(...)
    assert len(result.adversarial_scenarios) >= 3  # 每个核心功能至少 3 条

async def test_risk_breaker():
    """测试风险熔断判断"""
    result = await run_questioning_agent(...)
    breaker = result.risk_breaker
    if breaker.high_risk_count >= 5:
        assert breaker.breaker_status == "halt"
```

### 集成测试
```python
# tests/agents/requirement_analysis/test_orchestrator_v2.py

async def test_orchestrator_with_questioning():
    """测试完整工作流（含质疑节点）"""
    result = await run_requirement_analysis(...)
    
    # 验证质疑节点执行
    assert result.questioning is not None
    assert result.questioning.risk_breaker is not None
    
    # 验证视觉化标记
    for item in result.clarification.items:
        assert item.visual_marker in ["🔴", "🟡", "🟢"]
        assert item.risk_level in ["high", "medium", "low"]
```

---

## 📖 参考资料

### baigong-platform-requirement-analyzer 核心特性
1. **质疑驱动 9 宫格**：WHAT/WHY/WHO/WHEN/WHERE/HOW/HOW_MUCH/WHAT_IF/WHY_NOT
2. **反向场景挖掘**：7大攻击向量
3. **风险熔断机制**：🔴≥5 / 总≥15 触发熔断
4. **测试左移介入点**：PRD 评审阶段就介入
5. **强疑点四要素**：定位/问题/影响/建议方向

### 实施文档位置
- **skill 源文件**：`D:/project/br-git/br_baigong_project-clean/skills/baigong-platform-requirement-analyzer/SKILL.md`
- **改进总结**：本文档

---

## 🎉 完成状态

- ✅ **质疑驱动节点**：已完成，包含 9 宫格、反向场景、可执行性/可实现性检测、需求漏洞、风险熔断
- ✅ **视觉化分级标记**：已完成，ClarificationItem 新增 visual_marker 和 risk_level 字段
- ✅ **工作流集成**：已完成，orchestrator 已集成质疑节点
- ⏳ **历史需求检索**：待 Phase 2 实施
- ⏳ **架构图自动生成**：待 Phase 2 实施

---

*文档生成时间：2026-06-16*
*架构版本：v2.1*
