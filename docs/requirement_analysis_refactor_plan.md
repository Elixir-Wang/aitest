# 需求分析模块重构方案

## 当前目录结构问题

```
requirement_analysis/
├── agents/              # ✅ 活跃 - LLM智能体
├── analyzers/           # ⚠️ 部分使用 - 深度理解用
├── examples/            # ❌ 示例代码 - 可删除
├── generators/          # ❌ 空目录
├── knowledge/           # ❌ 空目录
├── nodes/               # ✅ 活跃 - LangGraph节点
├── services/            # ✅ 使用 - 辅助文档搜索
├── tools/               # ✅ 使用 - LangChain工具
├── utils/               # ✅ 活跃 - 工具函数
├── comprehensive_orchestrator.py  # ❌ 旧版本
├── explainer.py                   # ✅ 使用中
├── orchestrator.py                # ✅ 使用中 - 深度理解编排
├── qa_orchestrator.py             # ⚠️ QA视角编排
├── qa_view_generator.py           # ⚠️ QA报告生成
├── requirement_understanding_assistant.py  # ❌ 旧版本
├── schemas.py                     # ✅ 核心schema
├── schemas_v2_backup.py           # ❌ 备份文件
├── search.py                      # ⚠️ 搜索功能
├── state.py                       # ✅ LangGraph状态
├── workflow.py                    # ✅ 核心工作流
└── models.py                      # ✅ 数据模型
```

## 文件使用状态分析

### ✅ 核心文件（必须保留）

**Workflow层**
- `workflow.py` - LangGraph工作流编排
- `state.py` - 工作流状态定义
- `schemas.py` - 所有Pydantic模型

**Nodes层（LangGraph节点）**
- `nodes/understand_node.py` - 需求理解节点
- `nodes/quality_node.py` - 质量评估节点
- `nodes/clarify_node.py` - 澄清节点
- `nodes/enhance_node.py` - 增强节点

**Agents层（LLM智能体）**
- `agents/quality_assessment.py` - 质量评估agent + 转换函数
- `agents/clarification.py` - 澄清agent
- `agents/understanding.py` - 理解agent（如果使用）

**深度理解层**
- `orchestrator.py` - DeepUnderstandingOrchestrator
- `models.py` - BusinessInsight, DomainModel, RiskProfile
- `explainer.py` - 生成理解报告
- `analyzers/business.py` - 业务分析器
- `analyzers/domain.py` - 领域建模器
- `analyzers/risk.py` - 风险识别器
- `analyzers/testability.py` - 可测试性分析器
- `analyzers/test_scenario.py` - 测试场景提取器

**工具层**
- `utils/report_generator.py` - 报告生成
- `utils/requirement_enhancer.py` - 需求增强
- `utils/priority_sorter.py` - 优先级排序
- `utils/clarification_adapter.py` - 澄清适配器
- `services/auxiliary_search_service.py` - 辅助文档搜索
- `tools/search_auxiliary.py` - LangChain搜索工具

### ⚠️ 可选文件（根据需求决定）

- `qa_orchestrator.py` - QA视角编排（如果需要QA视图）
- `qa_view_generator.py` - QA报告生成（如果需要QA视图）
- `search.py` - 搜索功能（看是否被使用）

### ❌ 可删除文件

**示例代码**
- `examples/architecture_comparison.py`
- `examples/comprehensive_example.py`
- `examples/qa_oriented_example.py`

**旧版本/废弃文件**
- `comprehensive_orchestrator.py` - 旧版orchestrator
- `requirement_understanding_assistant.py` - 旧版理解助手
- `schemas_v2_backup.py` - 备份文件

**空目录**
- `generators/` - 空目录
- `knowledge/patterns/` - 空目录
- `knowledge/risks/` - 空目录

---

## 推荐的重构方案

### 方案A：最小化结构（推荐）

适合当前v3.0架构，保留核心功能。

```
requirement_analysis/
├── core/                        # 核心层
│   ├── schemas.py              # 所有数据模型
│   ├── state.py                # LangGraph状态
│   └── models.py               # 领域模型
│
├── workflow/                    # 工作流层
│   ├── workflow.py             # LangGraph编排
│   ├── nodes.py                # 所有节点（合并4个node文件）
│   └── orchestrator.py         # 深度理解编排
│
├── agents/                      # LLM智能体层
│   ├── quality.py              # 质量评估（合并assessment + 转换函数）
│   ├── clarification.py        # 澄清
│   └── understanding.py        # 理解（如果使用）
│
├── analyzers/                   # 深度分析器（保留5个）
│   ├── business.py
│   ├── domain.py
│   ├── risk.py
│   ├── testability.py
│   └── test_scenario.py
│
├── utils/                       # 工具函数
│   ├── report.py               # 报告生成
│   ├── enhancer.py             # 需求增强
│   ├── adapter.py              # 适配器
│   └── sorter.py               # 排序
│
├── services/                    # 服务层
│   └── search.py               # 辅助文档搜索
│
└── __init__.py                  # 懒加载入口
```

**优点**：
- 层次清晰：core → workflow → agents → analyzers → utils
- 文件数量减少：43个 → 约20个
- 便于维护和理解

**改动**：
1. 合并4个node文件 → `workflow/nodes.py`
2. 删除examples、空目录、旧版本文件
3. 重命名和整合utils文件

---

### 方案B：功能分组结构

按业务功能分组，适合多团队协作。

```
requirement_analysis/
├── schemas.py                   # 核心schema（保持根目录）
├── workflow.py                  # 入口（保持根目录）
│
├── understanding/               # 需求理解模块
│   ├── orchestrator.py         # 深度理解编排
│   ├── explainer.py            # 报告生成
│   └── analyzers/              # 5个分析器
│       ├── business.py
│       ├── domain.py
│       ├── risk.py
│       ├── testability.py
│       └── test_scenario.py
│
├── quality/                     # 质量评估模块
│   ├── agent.py                # 质量评估agent
│   ├── node.py                 # 质量评估node
│   └── converter.py            # 简化输出转换器
│
├── clarification/               # 澄清模块
│   ├── agent.py                # 澄清agent
│   ├── node.py                 # 澄清node
│   ├── search.py               # 搜索服务
│   └── adapter.py              # 适配器
│
├── enhancement/                 # 增强模块
│   ├── node.py                 # 增强node
│   ├── enhancer.py             # 需求增强
│   └── report.py               # 报告生成
│
└── utils/                       # 共享工具
    └── sorter.py
```

**优点**：
- 功能内聚：每个模块独立完整
- 便于并行开发
- 清晰的模块边界

**缺点**：
- 层级更深
- 跨模块依赖需要清晰定义

---

### 方案C：按层级分离（适合大型项目）

```
requirement_analysis/
├── domain/                      # 领域层（纯数据）
│   ├── schemas.py
│   ├── models.py
│   └── state.py
│
├── application/                 # 应用层（编排）
│   ├── workflow.py
│   ├── orchestrator.py
│   └── nodes/
│       ├── understand.py
│       ├── quality.py
│       ├── clarify.py
│       └── enhance.py
│
├── infrastructure/              # 基础设施层
│   ├── agents/                 # LLM调用
│   ├── analyzers/              # 分析器
│   ├── services/               # 外部服务
│   └── utils/                  # 工具函数
│
└── __init__.py
```

**优点**：
- DDD分层清晰
- 依赖方向明确（domain ← application ← infrastructure）
- 适合大型项目

**缺点**：
- 对当前规模可能过度设计
- 学习成本较高

---

## 具体执行步骤（方案A）

### Step 1: 删除废弃文件

```bash
# 删除示例代码
rm -rf examples/

# 删除空目录
rm -rf generators/ knowledge/

# 删除旧版本文件
rm comprehensive_orchestrator.py
rm requirement_understanding_assistant.py
rm schemas_v2_backup.py
```

### Step 2: 创建新结构

```bash
mkdir -p core workflow
```

### Step 3: 移动核心文件

```bash
# 移动到core/
mv schemas.py core/
mv state.py core/
mv models.py core/

# 移动到workflow/
mv workflow.py workflow/
mv orchestrator.py workflow/
mv explainer.py workflow/
```

### Step 4: 合并节点文件

创建 `workflow/nodes.py`，包含：
- understand_node
- quality_node
- clarify_node
- enhance_node

### Step 5: 重命名utils文件

```bash
mv utils/report_generator.py utils/report.py
mv utils/requirement_enhancer.py utils/enhancer.py
mv utils/clarification_adapter.py utils/adapter.py
mv utils/priority_sorter.py utils/sorter.py
```

### Step 6: 合并agents

```bash
# 重命名
mv agents/quality_assessment.py agents/quality.py
```

### Step 7: 更新导入路径

更新所有文件中的import语句：
```python
# 旧
from app.agents.requirement_analysis.schemas import X
# 新
from app.agents.requirement_analysis.core.schemas import X

# 旧
from app.agents.requirement_analysis.nodes.quality_node import quality_node
# 新
from app.agents.requirement_analysis.workflow.nodes import quality_node
```

### Step 8: 更新__init__.py

```python
"""Requirement analysis package."""

def run_requirement_analysis(*args, **kwargs):
    """Lazily load workflow."""
    from app.agents.requirement_analysis.workflow.workflow import run_requirement_analysis as _run
    return _run(*args, **kwargs)

__all__ = ["run_requirement_analysis"]
```

---

## 可选：决策QA相关文件

检查这些文件是否被使用：
- `qa_orchestrator.py`
- `qa_view_generator.py`
- `search.py`

```bash
# 检查使用情况
grep -r "qa_orchestrator\|qa_view_generator\|from.*search import" app/ tests/ --include="*.py"
```

如果未使用或仅在示例中使用，可以删除。

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 导入路径错误 | 高 | 运行完整测试套件 |
| 遗漏关键文件 | 中 | 先备份，再删除 |
| 依赖关系破坏 | 中 | 使用IDE重构功能 |
| 外部调用失败 | 低 | 保持__init__.py入口不变 |

---

## 建议

1. **优先选择方案A（最小化结构）**
   - 适合当前v3.0架构
   - 改动最小，风险最低
   - 结构清晰，易于维护

2. **分步执行**
   - 先删除废弃文件（低风险）
   - 再重组目录结构（中风险）
   - 最后更新导入路径（高风险）

3. **每步都运行测试**
   ```bash
   pytest tests/test_workflow_v3.py -v
   pytest tests/agents/requirement_analysis/ -v
   ```

4. **使用Git保护**
   ```bash
   git checkout -b refactor/requirement-analysis-structure
   # 每完成一个大步骤就commit
   ```

要我立即实施方案A吗？
