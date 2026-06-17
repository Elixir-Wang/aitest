# 需求分析架构重构方案

**参考**: document_editor 智能体设计  
**目标**: 简化目录结构，提升代码可维护性  
**时间**: 2026-06-17

---

## 📊 当前结构 vs 目标结构对比

### document_editor（参考标准）

```
document_editor/
├── __init__.py           # 空文件
├── agent.py              # Agent 定义 + System Prompt
├── schemas.py            # Input/Output Schemas
└── service.py            # 服务层（调用入口）
```

**特点**:
- ✅ **扁平化**: 4 个文件，职责清晰
- ✅ **单一职责**: 每个文件功能明确
- ✅ **易维护**: 一个 agent，一个 service
- ✅ **易测试**: 结构简单，依赖清晰

---

### requirement_analysis（当前结构）

```
requirement_analysis/
├── __init__.py
├── orchestrator.py                    # 主编排器（核心）
│
├── agents/                            # 4 个子 Agent
│   ├── __init__.py
│   ├── understanding.py               # 理解 Agent
│   ├── questioning.py                 # 质疑 Agent
│   ├── quality.py                     # 质量 Agent
│   └── clarification.py               # 澄清 Agent
│
├── core/                              # 核心定义
│   ├── __init__.py
│   ├── schemas.py                     # 所有 Schemas（巨大）
│   └── models.py                      # 内部模型
│
├── utils/                             # 工具类（7 个文件）
│   ├── __init__.py
│   ├── context.py                     # Brief 构建
│   ├── report.py                      # 报告生成（巨大）
│   ├── enhancer.py                    # 需求增强
│   ├── explainer.py                   # 解释生成
│   ├── mermaid_manager.py             # Mermaid 管理
│   ├── adapter.py                     # 适配器
│   ├── timing.py                      # 计时工具
│   └── sorter.py                      # 排序工具
│
├── tools/                             # LangChain Tools
│   ├── __init__.py
│   └── search_auxiliary.py
│
├── services/                          # 服务层（空）
│   └── __init__.py
│
└── workflow/                          # 向后兼容层
    ├── __init__.py
    └── workflow.py
```

**问题**:
- ❌ **层级过深**: 5 层目录结构
- ❌ **职责分散**: utils 包含 7 个文件
- ❌ **巨型文件**: schemas.py 和 report.py 过大
- ❌ **空目录**: services/ 目录为空

---

## 🎯 重构目标结构（参考 document_editor）

### 方案A：扁平化结构（推荐）

```
requirement_analysis/
├── __init__.py                        # 导出 run_requirement_analysis
├── orchestrator.py                    # 主编排器（保持不变）
│
├── agents/                            # Agent 层（保持）
│   ├── __init__.py
│   ├── understanding.py               # 理解 Agent + Prompt
│   ├── questioning.py                 # 质疑 Agent + Prompt
│   ├── quality.py                     # 质量 Agent + Prompt
│   └── clarification.py               # 澄清 Agent + Prompt
│
├── schemas/                           # Schemas 拆分（按 Agent）
│   ├── __init__.py                    # 导出所有 Schema
│   ├── common.py                      # 公共 Schema（Input/Output/Brief）
│   ├── understanding.py               # 理解相关 Schema
│   ├── questioning.py                 # 质疑相关 Schema
│   ├── quality.py                     # 质量相关 Schema
│   └── clarification.py               # 澄清相关 Schema
│
├── services/                          # 服务层（聚合工具）
│   ├── __init__.py
│   ├── report.py                      # 报告生成服务
│   ├── context.py                     # Brief 构建服务
│   ├── enhancer.py                    # 需求增强服务
│   └── mermaid.py                     # Mermaid 管理服务
│
└── tools/                             # LangChain Tools（保持）
    ├── __init__.py
    └── search_auxiliary.py
```

**优化点**:
- ✅ 删除 `workflow/`（已完成）
- ✅ 删除 `core/`（拆分到 schemas/）
- ✅ 重组 `utils/` → `services/`（语义更清晰）
- ✅ 拆分巨型 `schemas.py`（按 Agent 分组）

---

### 方案B：单文件结构（极简，适用于未来拆分为独立服务）

```
requirement_analysis/
├── __init__.py
├── orchestrator.py                    # 编排器
├── schemas.py                         # 所有 Schemas（保持）
├── agents.py                          # 4 个 Agent + Prompts
├── services.py                        # 所有服务函数
└── tools.py                           # Tools
```

**适用场景**: 如果未来每个 Agent 独立为微服务，当前先保持简单

---

## 📋 详细重构步骤（方案A）

### 阶段1：拆分 schemas（高优先级）

#### 1.1 创建 `schemas/` 目录

```bash
mkdir apps/backend/app/agents/requirement_analysis/schemas
```

#### 1.2 拆分 `core/schemas.py`

**目标**:
```
core/schemas.py (2000+ 行)
    ↓ 拆分为
schemas/
├── __init__.py           # 导出所有
├── common.py             # RequirementAnalysisInputV2, RequirementAnalysisResultV2, Brief 类
├── understanding.py      # RequirementUnderstandingOutput, RequirementModule, BusinessObject 等
├── questioning.py        # QuestioningOutput, NineGridMatrix, AdversarialScenario 等
├── quality.py            # QualityAssessmentOutput, QualityDecision, Completeness 等
└── clarification.py      # ClarificationOutput, ClarificationItem 等
```

**迁移规则**:
- `common.py`: 顶层 Input/Output + Brief 基类
- `understanding.py`: 所有 `RequirementUnderstanding*` 开头的类
- `questioning.py`: 所有 `Questioning*` / `NineGrid*` / `Adversarial*` / `RiskBreaker`
- `quality.py`: 所有 `Quality*` / `Completeness` / `Clarity` / `Testability` / `Consistency`
- `clarification.py`: 所有 `Clarification*` / `ClarificationItem`

#### 1.3 更新导入

**schemas/__init__.py**:
```python
"""Requirement analysis schemas."""

# Common schemas
from app.agents.requirement_analysis.schemas.common import (
    RequirementAnalysisInputV2,
    RequirementAnalysisResultV2,
    RequirementUnderstandingBrief,
    QuestioningBrief,
    QualityAssessmentBrief,
    EvidenceSnippet,
    AuxiliaryDocument,
)

# Understanding schemas
from app.agents.requirement_analysis.schemas.understanding import (
    RequirementUnderstandingOutput,
    RequirementModule,
    BusinessObject,
    # ... 其他
)

# Questioning schemas
from app.agents.requirement_analysis.schemas.questioning import (
    QuestioningOutput,
    NineGridMatrix,
    AdversarialScenario,
    RiskBreaker,
    # ... 其他
)

# Quality schemas
from app.agents.requirement_analysis.schemas.quality import (
    QualityAssessmentOutput,
    QualityDecision,
    Completeness,
    # ... 其他
)

# Clarification schemas
from app.agents.requirement_analysis.schemas.clarification import (
    ClarificationOutput,
    ClarificationItem,
    # ... 其他
)

__all__ = [
    # ... 所有导出
]
```

**向后兼容**:
```python
# core/schemas.py（保留空壳，重新导出）
"""Backward compatibility: redirect to schemas/ module."""
from app.agents.requirement_analysis.schemas import *  # noqa
```

---

### 阶段2：重组 utils/ → services/

#### 2.1 迁移文件

```bash
# 删除空 services/ 目录
rm -rf apps/backend/app/agents/requirement_analysis/services

# 创建新 services/
mkdir apps/backend/app/agents/requirement_analysis/services

# 迁移文件（重命名，职责更清晰）
mv utils/report.py services/report.py
mv utils/context.py services/context.py
mv utils/enhancer.py services/enhancer.py
mv utils/mermaid_manager.py services/mermaid.py
mv utils/explainer.py services/explainer.py

# 保留 utils/ 中的小工具
# utils/adapter.py     -> 保留
# utils/timing.py      -> 保留
# utils/sorter.py      -> 保留
```

#### 2.2 更新导入路径

**全局替换**:
```bash
# report.py
from app.agents.requirement_analysis.utils.report import ...
    ↓
from app.agents.requirement_analysis.services.report import ...

# context.py
from app.agents.requirement_analysis.utils.context import ...
    ↓
from app.agents.requirement_analysis.services.context import ...

# enhancer.py
from app.agents.requirement_analysis.utils.enhancer import ...
    ↓
from app.agents.requirement_analysis.services.enhancer import ...

# mermaid_manager.py
from app.agents.requirement_analysis.utils.mermaid_manager import ...
    ↓
from app.agents.requirement_analysis.services.mermaid import ...
```

---

### 阶段3：删除 core/ 目录

```bash
# 1. 拆分完成后，删除原始文件
rm apps/backend/app/agents/requirement_analysis/core/schemas.py

# 2. 保留 models.py（如果需要）或迁移到 schemas/models.py
mv apps/backend/app/agents/requirement_analysis/core/models.py \
   apps/backend/app/agents/requirement_analysis/schemas/models.py

# 3. 删除 core/ 目录
rm -rf apps/backend/app/agents/requirement_analysis/core
```

---

### 阶段4：简化 __init__.py 导出

**requirement_analysis/__init__.py**（参考 document_editor 风格）:
```python
"""Requirement analysis agent."""

from app.agents.requirement_analysis.orchestrator import run_requirement_analysis

__all__ = ["run_requirement_analysis"]
```

**agents/__init__.py**:
```python
"""Requirement analysis agents."""

from app.agents.requirement_analysis.agents.understanding import run_understanding_agent
from app.agents.requirement_analysis.agents.questioning import run_questioning_agent
from app.agents.requirement_analysis.agents.quality import run_quality_assessment_agent
from app.agents.requirement_analysis.agents.clarification import run_clarification_agent

__all__ = [
    "run_understanding_agent",
    "run_questioning_agent",
    "run_quality_assessment_agent",
    "run_clarification_agent",
]
```

---

## 📊 重构前后对比

### 目录层级

| 指标 | 重构前 | 重构后 | 改进 |
|------|-------|--------|------|
| **顶层目录** | 7 个 | 5 个 | -29% |
| **Python 文件** | 22 个 | 22 个 | 0%（重组，不增删） |
| **最大文件行数** | ~2000 行（schemas.py） | ~400 行/文件 | -80% |
| **空目录** | 1 个（services/） | 0 个 | ✅ |

### 目录结构清晰度

| 方面 | 重构前 | 重构后 |
|------|-------|--------|
| **schemas 组织** | 单文件 2000+ 行 | 按 Agent 拆分 5 个文件 |
| **services 职责** | 空目录 | 包含业务服务 |
| **utils 定位** | 混杂（7 个文件） | 纯工具函数（3 个文件） |
| **向后兼容** | workflow/ 重定向 | core/ 重定向 |

---

## 🎯 重构收益

### 1. 可维护性提升

**重构前**:
- 修改 understanding schemas → 打开 2000 行文件 → 查找定位 → 修改
- 风险：误改其他 Agent 的 Schema

**重构后**:
- 修改 understanding schemas → 打开 `schemas/understanding.py`（~300 行）→ 直接修改
- 隔离：每个文件独立，互不影响

### 2. 代码导航

**重构前**:
```python
from app.agents.requirement_analysis.core.schemas import (
    RequirementUnderstandingOutput,  # 在哪？2000 行中搜索
    QuestioningOutput,                # 在哪？2000 行中搜索
    QualityAssessmentOutput,          # 在哪？2000 行中搜索
)
```

**重构后**:
```python
from app.agents.requirement_analysis.schemas.understanding import RequirementUnderstandingOutput
from app.agents.requirement_analysis.schemas.questioning import QuestioningOutput
from app.agents.requirement_analysis.schemas.quality import QualityAssessmentOutput
```

**优势**: IDE 跳转更精确，文件语义清晰

### 3. 测试隔离

**重构前**: 测试 understanding schemas 需要导入整个 `core.schemas`

**重构后**: 只导入 `schemas.understanding`，依赖更少

### 4. 团队协作

**重构前**: 多人同时修改 `core/schemas.py` → 高冲突率

**重构后**: 不同 Agent 的 schemas 分散在不同文件 → 低冲突率

---

## ⚠️ 重构风险与缓解

### 风险1：循环导入

**场景**: `schemas/common.py` 引用 `schemas/understanding.py`，反之亦然

**缓解**:
- 使用 `TYPE_CHECKING` 条件导入
- 将真正的"通用类型"放在 `common.py`（如 Brief 基类）
- 将具体实现放在各 Agent 的 schema 文件

### 风险2：向后兼容性

**场景**: 外部代码导入 `from app.agents.requirement_analysis.core.schemas import X`

**缓解**:
- 保留 `core/schemas.py` 作为空壳，重新导出所有类型
- 添加 deprecation warning（可选）

```python
# core/schemas.py
"""Deprecated: use app.agents.requirement_analysis.schemas instead."""
import warnings
from app.agents.requirement_analysis.schemas import *  # noqa

warnings.warn(
    "core.schemas is deprecated, use schemas module instead",
    DeprecationWarning,
    stacklevel=2,
)
```

### 风险3：大规模导入路径修改

**场景**: 22 个文件需要更新导入路径

**缓解**:
- 使用 IDE 的全局重构功能
- 或使用脚本批量替换：
```bash
find apps/backend/app/agents/requirement_analysis -type f -name "*.py" \
  -exec sed -i 's/from app.agents.requirement_analysis.utils.report/from app.agents.requirement_analysis.services.report/g' {} \;
```

---

## 📝 实施计划

### Phase 1: 拆分 schemas（高优先级）
- [ ] 创建 `schemas/` 目录
- [ ] 拆分 `core/schemas.py` 为 5 个文件
- [ ] 更新 `schemas/__init__.py` 导出
- [ ] 保留 `core/schemas.py` 空壳（向后兼容）
- [ ] 更新所有 import 路径
- [ ] 测试验证

**预估工作量**: 4-6 小时

### Phase 2: 重组 utils/ → services/（中优先级）
- [ ] 创建 `services/` 目录
- [ ] 迁移 5 个文件到 services/
- [ ] 更新所有 import 路径
- [ ] 删除空 `services/` 旧目录
- [ ] 测试验证

**预估工作量**: 2-3 小时

### Phase 3: 删除 core/（低优先级）
- [ ] 确认 `core/schemas.py` 无直接引用
- [ ] 迁移 `core/models.py` 到 `schemas/models.py`
- [ ] 删除 `core/` 目录
- [ ] 测试验证

**预估工作量**: 1 小时

### Phase 4: 文档更新
- [ ] 更新架构文档
- [ ] 更新开发指南
- [ ] 更新 API 文档

**预估工作量**: 1 小时

**总计**: 8-11 小时

---

## 🎉 最终效果

### 重构后目录结构

```
requirement_analysis/
├── __init__.py                        # 导出 run_requirement_analysis
├── orchestrator.py                    # 主编排器（168 行）
│
├── agents/                            # 4 个 Agent（清晰）
│   ├── __init__.py
│   ├── understanding.py               # ~230 行
│   ├── questioning.py                 # ~450 行
│   ├── quality.py                     # ~180 行
│   └── clarification.py               # ~200 行
│
├── schemas/                           # Schemas（拆分）
│   ├── __init__.py                    # 导出所有
│   ├── common.py                      # ~150 行
│   ├── understanding.py               # ~300 行
│   ├── questioning.py                 # ~400 行
│   ├── quality.py                     # ~350 行
│   ├── clarification.py               # ~250 行
│   └── models.py                      # ~100 行（原 core/models.py）
│
├── services/                          # 业务服务（语义清晰）
│   ├── __init__.py
│   ├── report.py                      # ~600 行
│   ├── context.py                     # ~280 行
│   ├── enhancer.py                    # ~150 行
│   ├── mermaid.py                     # ~200 行
│   └── explainer.py                   # ~180 行
│
├── utils/                             # 纯工具函数（精简）
│   ├── __init__.py
│   ├── adapter.py                     # ~100 行
│   ├── timing.py                      # ~35 行
│   └── sorter.py                      # ~50 行
│
├── tools/                             # LangChain Tools
│   ├── __init__.py
│   └── search_auxiliary.py
│
└── workflow/                          # 向后兼容（保留）
    ├── __init__.py
    └── workflow.py
```

**特点**:
- ✅ **职责清晰**: 每个目录功能明确
- ✅ **文件适中**: 最大文件 ~600 行（report.py），其他 ~400 行以下
- ✅ **易导航**: 按 Agent 分组，结构清晰
- ✅ **易维护**: 修改某个 Agent 的 Schema 只需打开对应文件

---

## 🤔 是否立即实施？

### 建议：**分阶段实施**

1. **立即实施 Phase 1**（拆分 schemas）:
   - ✅ 收益最大（解决 2000 行巨型文件）
   - ✅ 风险可控（向后兼容）
   - ✅ 后续优化的基础

2. **Phase 2-3 可选**:
   - 如果当前 utils/ 结构工作良好，可暂缓
   - 如果团队协作频繁冲突，建议尽快实施

3. **Phase 4 随时更新**

---

需要我帮你：
1. **立即开始 Phase 1（拆分 schemas）**？
2. **先生成迁移脚本，手动执行**？
3. **暂缓，继续优化其他功能**？
