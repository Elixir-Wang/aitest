# 探索功能重构改造方案

## 📋 问题分析

### 1. 当前状态
从 git status 和代码分析可以看出，你进行了一次大的架构重构：

**已删除的模块**：
- ✗ `app/agents/requirement_exploration/` - 需求探索 Agent
- ✗ `app/api/v1/requirement_exploration.py` - 需求探索 API
- ✗ `app/schemas/requirement_exploration.py` - 需求探索 Schema
- ✗ `app/services/requirement_exploration_service.py` - 需求探索服务
- ✗ `app/services/exploration/agentic_orchestrator.py` - Agentic 编排器

**已修改的模块**：
- ✓ `app/agents/requirement_analysis/` - 重构为新架构
- ✓ `app/services/exploration/site_orchestrator.py` - 调用统一编排器
- ✓ `app/services/exploration/unified_orchestrator.py` - 新增统一编排器

**依赖的模块**（已存在）：
- ✓ `app/services/exploration/plan_and_execute/planner.py`
- ✓ `app/services/exploration/plan_and_execute/executor.py`
- ✓ `app/services/exploration/plan_and_execute/monitor.py`
- ✓ `app/agents/site_exploration/execution_decision/`

### 2. 核心问题

**问题1：导入错误**
```
ModuleNotFoundError: No module named 'yaml'
```
缺少 PyYAML 依赖包。

**问题2：架构不完整**
- 删除了旧的 `requirement_exploration` 模块
- 新的统一架构 (`unified_orchestrator`) 已创建但未完全集成
- 旧代码可能仍有对已删除模块的引用

**问题3：功能断层**
- 探索功能现在走 `site_orchestrator` → `unified_orchestrator`
- 但 `unified_orchestrator` 依赖的 `plan_and_execute` 模块可能不完整

---

## 🎯 最优改造方案

### 方案选择：渐进式修复 + 快速恢复

基于你的架构设计（从 UNIFIED_ARCHITECTURE.md 看出），你的目标是建立统一的探索架构。我推荐以下方案：

### 阶段1：立即修复（让系统能跑起来）⚡

#### 步骤1.1：安装缺失依赖
```bash
cd apps/backend
pip install pyyaml
```

#### 步骤1.2：临时回退到旧的探索流程
如果 `plan_and_execute` 模块还不完善，临时禁用 unified_orchestrator：

**修改 `apps/backend/app/services/exploration/site_orchestrator.py`**：
```python
# 第117行附近，注释掉 unified_orchestrator 调用
def _run_exploration(run_id: str) -> None:
    # ... 前面代码保持不变 ...
    
    # 临时方案：直接使用 Playwright 探索
    result = _execute_playwright_probe(run_id, artifact_root)
    
    # 原来调用 unified_orchestrator 的代码注释掉
    # result = _execute_unified_exploration(run_id, artifact_root)
    
    _persist_runner_result(run_id, artifact_root, result)
```

#### 步骤1.3：清理暂存区中的不完整变更
```bash
# 如果某些文件的修改不完整，先撤销
git restore --staged <有问题的文件>
git restore <有问题的文件>
```

---

### 阶段2：完善统一架构（推荐方案）🚀

这是长期正确的方向，基于你已经设计好的统一架构。

#### 步骤2.1：确保 plan_and_execute 模块完整

**检查 `planner.py` 是否实现了规划逻辑**：
```python
# apps/backend/app/services/exploration/plan_and_execute/planner.py

class ExplorationPlanner:
    async def create_plan(self, planner_input: PlannerInput) -> ExplorationPlan:
        """
        根据目标生成探索计划
        
        需要实现：
        1. 分析 goal、scope、forbidden_paths
        2. 生成步骤列表（ExplorationStep）
        3. 为每个步骤分配模块
        4. 评估风险和时长
        """
        # TODO: 实现规划逻辑
        pass
```

**检查 `executor.py` 是否实现了执行逻辑**：
```python
# apps/backend/app/services/exploration/plan_and_execute/executor.py

class PlanExecutor:
    def _execute_step(self, step: ExplorationStep) -> StepExecutionResult:
        """
        执行单个步骤
        
        需要实现：
        1. 根据 action_type 选择执行方式
        2. 处理 navigate、click、fill、wait、observe 等操作
        3. 返回执行结果
        """
        # TODO: 实现执行逻辑
        pass
```

**检查 `monitor.py` 是否实现了监控逻辑**：
```python
# apps/backend/app/services/exploration/plan_and_execute/monitor.py

class ExecutionMonitor:
    def should_re_plan(self, result: StepExecutionResult, step: ExplorationStep) -> bool:
        """判断是否需要重新规划"""
        # TODO: 实现监控逻辑
        pass
    
    async def re_plan(self, step_index: int, error: str) -> ExplorationPlan | None:
        """重新规划"""
        # TODO: 实现重新规划逻辑
        pass
```

#### 步骤2.2：完善 unified_orchestrator

**确保所有导入正确**：
```python
# apps/backend/app/services/exploration/unified_orchestrator.py

# 确保这些导入能正常工作
from app.services.exploration.plan_and_execute.planner import (
    ExplorationPlanner,
    ExplorationPlan,
    ExplorationStep,
    PlannerInput,
)
from app.services.exploration.plan_and_execute.executor import PlanExecutor, StepExecutionResult
from app.services.exploration.plan_and_execute.monitor import ExecutionMonitor
```

**处理 agentic 执行的导入**：
```python
# unified_orchestrator.py 第217行
# 确保这个模块存在且可导入
from app.agents.site_exploration.execution_decision import service as agentic_service
from app.agents.site_exploration.execution_decision.schemas import AgenticExplorationInput
```

#### 步骤2.3：实现缺失的核心方法

如果 `plan_and_execute` 模块是新创建的但没有实现，需要补充核心逻辑。我可以为你生成完整的实现代码。

---

### 阶段3：清理和优化 🧹

#### 步骤3.1：删除对已删除模块的引用

**搜索并清理引用**：
```bash
# 搜索对 requirement_exploration 的引用
grep -r "requirement_exploration" apps/backend/app/ --exclude-dir=__pycache__

# 搜索对 agentic_orchestrator 的引用
grep -r "agentic_orchestrator" apps/backend/app/ --exclude-dir=__pycache__
```

#### 步骤3.2：更新测试

**删除或更新失效的测试**：
- ✗ `tests/agents/requirement_exploration/` - 已删除，对应
- 更新 `tests/test_exploration_*.py` 使用新架构

#### 步骤3.3：更新文档和注释

---

## 🔧 具体实施建议

### 推荐：快速修复 + 逐步完善

**今天立即做（30分钟）**：

1. **安装依赖**：
   ```bash
   pip install pyyaml
   ```

2. **测试导入**：
   ```bash
   python3 -c "from app.services.exploration.unified_orchestrator import run_unified_exploration_sync"
   ```
   
3. **如果还有导入错误**，临时禁用 unified_orchestrator：
   - 修改 `site_orchestrator.py` 第117行
   - 改回使用 `_execute_playwright_probe`

4. **提交能运行的版本**：
   ```bash
   git add .
   git commit -m "refactor: 临时禁用 unified_orchestrator，使用 playwright probe"
   ```

**本周逐步完善（2-3天）**：

1. **Day 1**：实现 `planner.py` 的核心规划逻辑
   - 解析 goal/scope
   - 生成步骤列表
   - 测试规划功能

2. **Day 2**：实现 `executor.py` 的执行逻辑
   - 实现基础操作（navigate, click, fill）
   - 集成浏览器会话
   - 测试执行功能

3. **Day 3**：实现 `monitor.py` 的监控逻辑
   - 失败检测
   - 重新规划
   - 端到端测试

4. **启用统一架构**：
   - 恢复 `site_orchestrator.py` 中的 unified_orchestrator 调用
   - 全面测试

---

## 📊 风险评估

### 低风险方案：临时回退
- ✅ 快速恢复功能
- ✅ 系统立即可用
- ⚠️ 但失去了新架构的优势

### 中风险方案：完善 plan_and_execute
- ✅ 实现了你设计的统一架构
- ✅ 长期更易维护
- ⚠️ 需要2-3天开发和测试

### 高风险方案：重新设计
- ❌ 不推荐，你的架构设计是合理的

---

## 🎬 立即行动清单

**现在就做（5分钟）**：
```bash
# 1. 安装依赖
pip install pyyaml

# 2. 检查能否启动
python3 -m app.main
```

**如果启动失败，临时修复（10分钟）**：
```bash
# 编辑 site_orchestrator.py
# 第117行：注释掉 unified_orchestrator
# 第117行：改用 _execute_playwright_probe
```

**如果启动成功，验证探索功能（5分钟）**：
- 创建一个探索任务
- 点击"开始探索"
- 查看是否能正常运行

---

## 💬 需要我帮你做什么？

我可以帮你：

1. **生成完整的 planner.py 实现** - 基于你的架构设计
2. **生成完整的 executor.py 实现** - 集成浏览器操作
3. **生成完整的 monitor.py 实现** - 实现监控和重新规划
4. **修复 site_orchestrator.py** - 添加更好的错误处理
5. **清理所有对已删除模块的引用** - 自动化搜索和替换

告诉我你想从哪里开始！
