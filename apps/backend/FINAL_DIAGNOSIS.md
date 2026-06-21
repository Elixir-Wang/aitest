# 探索任务失败的真正原因 - 完整诊断 🔍

## 📌 问题演变历史

### 第一个问题：sqlite3.Row 不兼容 ✅ 已修复
- **错误**: `'sqlite3.Row' object has no attribute 'get'`
- **状态**: 已在 `app/repositories/exploration_repo.py` 修复

### 第二个问题：capability_id 未注册 ❌ **当前问题**
- **错误**: `KeyError: 'site_exploration_planning'`
- **状态**: 需要修复

---

## 🔴 当前核心问题分析

### 错误信息
```
探索执行异常: 'site_exploration_planning'
```

### 错误发生位置
```
app/services/exploration/unified_orchestrator.py:125
  → ExplorationPlanner.create_plan()
    → planner._call_planner_llm()  (line 345)
      → resolve_model_selection(self.capability_id)  
        → get_ai_capability("site_exploration_planning")
          → KeyError: 'site_exploration_planning' ❌
```

### 根本原因

在 `app/services/exploration/plan_and_execute/planner.py` 第 276 行：
```python
self.capability_id = "site_exploration_planning"
```

但在 `app/agents/capabilities.py` 中，只注册了这些 capability：
```python
AI_CAPABILITIES = (
    "document_editor",
    "raw_requirement_format_converter", 
    "requirement_analysis",
    "site_exploration",  # ← 只有这个，没有 site_exploration_planning
    "knowledge_query",
)
```

**问题**：`site_exploration_planning` 这个 capability ID **不存在**！

---

## 🔧 解决方案

### 方案1：修改 planner.py 使用已存在的 capability（推荐 ✅）

这是最快最安全的方案，不需要修改数据库配置。

**修改文件**: `app/services/exploration/plan_and_execute/planner.py`

```python
# 第 276 行，修改前
self.capability_id = "site_exploration_planning"

# 修改后
self.capability_id = "site_exploration"  # 使用已存在的 capability
```

**理由**：
- `site_exploration` 已经在 capabilities.py 中注册
- 已经在数据库中配置了模型
- 不需要额外的数据库操作
- Planning 本质上是 site_exploration 的一部分

---

### 方案2：注册新的 capability（不推荐，需要数据库配置）

如果确实需要单独的 `site_exploration_planning` capability：

**步骤1**: 修改 `app/agents/capabilities.py`
```python
AI_CAPABILITIES: tuple[AiCapability, ...] = (
    # ... 其他 capabilities ...
    AiCapability(
        id="site_exploration_planning",
        name="站点探索规划智能体",
        description="分析探索目标和范围，生成详细的探索计划。",
    ),
    # ... 
)
```

**步骤2**: 在数据库中配置模型
```sql
INSERT INTO model_assignments (capability_id, model_config_id) 
VALUES ('site_exploration_planning', <model_config_id>);
```

**问题**: 需要额外配置，复杂度高。

---

## ✅ 推荐的修复步骤

### 立即执行（方案1）

```bash
cd apps/backend

# 1. 备份文件
cp app/services/exploration/plan_and_execute/planner.py app/services/exploration/plan_and_execute/planner.py.backup

# 2. 修改文件（使用编辑器或sed）
# 将第 276 行的 "site_exploration_planning" 改为 "site_exploration"
```

手动编辑 `app/services/exploration/plan_and_execute/planner.py` 第 276 行：
```python
# 修改这一行
self.capability_id = "site_exploration"  # 原来是 "site_exploration_planning"
```

```bash
# 3. 重启后端服务
pkill -f uvicorn
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. 测试探索任务
# 在前端创建新的探索任务并执行
```

---

## 🧪 验证步骤

### 1. 确认修改
```bash
grep -n "self.capability_id" app/services/exploration/plan_and_execute/planner.py
# 应该输出：276:        self.capability_id = "site_exploration"
```

### 2. 检查数据库配置
```bash
sqlite3 data/ai_testing.db "
SELECT capability_id, model_config_id 
FROM model_assignments 
WHERE capability_id IN ('site_exploration', 'site_exploration_planning');"
```

应该看到 `site_exploration` 有配置，但 `site_exploration_planning` 没有（这是正常的）。

### 3. 测试探索任务

创建新任务 → 开始探索 → 观察日志：

**预期成功日志**:
```json
{"event": "run_started", "message": "开始统一探索: xxx"}
{"event": "planning_started", "message": "分析目标并生成探索计划..."}
{"event": "planning_completed", "plan_id": "plan-xxx", "total_steps": 5}
{"event": "step_started", "step_number": 1, ...}
```

**不应该看到**:
```json
{"event": "error", "message": "探索执行异常: 'site_exploration_planning'"}
```

---

## 📊 问题总结

### 问题链条
```
用户启动探索任务
  ↓
site_orchestrator.run_exploration()
  ↓
unified_orchestrator.run()
  ↓
ExplorationPlanner.create_plan()
  ↓
resolve_model_selection("site_exploration_planning")  ← 问题在这里
  ↓
get_ai_capability("site_exploration_planning")
  ↓
KeyError: 'site_exploration_planning'  ❌ 未注册的 capability
```

### 为什么会有这个问题？

这是一个**代码不一致**的问题：
1. `planner.py` 使用了一个新的 capability ID `"site_exploration_planning"`
2. 但 `capabilities.py` 中没有注册这个 ID
3. 导致运行时查找 capability 失败

可能的原因：
- 代码重构时遗漏了 capabilities.py 的更新
- 或者 planner.py 用错了 capability ID

---

## 🎯 修复后的预期结果

1. ✅ **Planning 阶段成功** - 使用 `site_exploration` capability 调用 LLM 生成计划
2. ✅ **Execution 阶段启动** - 根据计划执行探索步骤
3. ✅ **任务正常完成** - 状态变为 `completed` 或 `partial`
4. ✅ **生成探索报告** - 包含页面信息、元素定位器等

---

## 🔍 其他潜在问题（待验证）

### 问题1: Python依赖缺失
前面的测试中发现：
```
ModuleNotFoundError: No module named 'pydantic'
ModuleNotFoundError: No module named 'yaml'
```

**建议**：安装所有依赖
```bash
pip3 install pydantic pyyaml langchain langchain-openai playwright
```

### 问题2: 数据库连接问题
如果探索任务启动后立即失败，检查：
```bash
# 查看数据库是否被锁定
lsof data/ai_testing.db

# 检查探索任务状态
sqlite3 data/ai_testing.db "
SELECT id, status, result_summary, started_at, finished_at 
FROM exploration_runs 
ORDER BY created_at DESC LIMIT 1;"
```

---

## 📝 总结

### 已解决的问题
1. ✅ sqlite3.Row 不兼容 → 已转换为 dict

### 当前问题
2. ❌ capability_id 未注册 → **需要立即修复**

### 修复方案
**推荐**: 将 `planner.py` 中的 `"site_exploration_planning"` 改为 `"site_exploration"`

### 预期
修复后，探索任务应该能够：
- 成功启动 Planning 阶段
- 生成探索计划
- 执行探索步骤
- 完成并生成报告

---

**修复优先级**: 🔴 **紧急** - 这是阻塞探索任务的关键问题
**修复难度**: 🟢 **简单** - 只需修改一行代码
**风险**: 🟢 **低** - 使用已存在的 capability，不影响其他功能

---
