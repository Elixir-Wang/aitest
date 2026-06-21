# 探索任务步骤不显示问题 - 根本原因分析与修复

## 🔍 问题现象

用户在查看探索任务详情时：
- ✅ 能看到模块（如"工作台"）
- ✅ 点击模块后能看到页面列表
- ❌ **点击页面后，看不到任何探索步骤**

## 🎯 根本原因（Super Powers 深度分析）

### 1. 数据结构不匹配

**实际YAML文件结构：**
```yaml
# data/projects/.../pages/page-001-探索广场.yaml
page:
  id: page-001
  url: https://www.cybotstar.cn/agentStore
  title: 百融百工
  module: 模块一：进入智能体与切换对话模型
  status: explored
actions:  # ← 注意：是 actions 不是 steps
  - id: page-001-action-001
    type: navigate
    target: 起始URL：https://www.cybotstar.cn/agentStore
    status: failed
    result: "浏览器错误: page.goto..."
  - id: page-001-action-002
    type: observe
    target: 页面整体布局，包括智能体卡片、按钮、导航等元素
    status: passed
    result: '观察完成: 发现 41 个元素'
  - id: page-001-action-003
    type: click
    target: 包含文本"测试_自主规划智能体"的卡片
    status: passed
    result: '成功点击元素: 创建智能体'
```

**后端代码期望：**
```python
# apps/backend/app/services/exploration/service.py:2033
"steps": _normalize_steps(content.get("steps", []))
# ↑ 问题：YAML中是 actions，代码读取的是 steps
```

### 2. 数据流分析

```
YAML文件产物
└─ actions: [...]  ← 有数据
└─ steps: (不存在)  ← 没有这个字段

后端读取逻辑
└─ content.get("steps", [])  ← 返回空数组 []
   └─ _normalize_steps([])  ← 输入空数组
      └─ return []  ← 输出空数组

前端接收数据
└─ page.steps = []  ← 空数组
   └─ AgentPlan组件判断
      └─ subtask.steps?.length ? (...) : null  ← 不渲染
```

### 3. 为什么之前的修改没效果

**之前的修改：**
- ✅ 修改了前端 AgentPlan 组件的展开逻辑
- ✅ 修改了自动展开子任务的功能
- ❌ **但数据本身就是空的！**

**就像：**
- 修复了显示器 ✓
- 优化了界面 ✓
- 但数据线没插！✗

## ✅ 完整修复方案

### 修改 1: 后端读取逻辑（关键修复）

**文件：** `apps/backend/app/services/exploration/service.py`

**位置：** 第2018-2036行

**修改前：**
```python
for page_item in bundle["pages"]:
    content = page_item.get("content", {})
    page = content.get("page", {})
    pages.append({
        # ...
        "steps": _normalize_steps(content.get("steps", [])),  # ← 永远返回空数组
    })
```

**修改后：**
```python
for page_item in bundle["pages"]:
    content = page_item.get("content", {})
    page = content.get("page", {})
    # 优先使用 steps 字段，如果不存在则使用 actions 字段
    raw_steps = content.get("steps") or content.get("actions", [])  # ← 兼容 actions
    pages.append({
        # ...
        "steps": _normalize_steps(raw_steps),
    })
```

### 修改 2: 步骤规范化函数（增强兼容性）

**文件：** `apps/backend/app/services/exploration/service.py`

**位置：** 第2125-2146行

**修改后：**
```python
def _normalize_steps(raw_steps) -> list[dict]:
    if not isinstance(raw_steps, list):
        return []
    steps = []
    for index, raw_step in enumerate(raw_steps, start=1):
        if not isinstance(raw_step, dict):
            continue
        step_id = str(raw_step.get("id") or f"step-{index:03d}")

        # 兼容 steps 和 actions 两种数据结构
        # actions 格式: {id, type, target, status, result}
        # steps 格式: {id, type, title, detail, status, occurred_at, artifact_path, source}
        step_type = str(raw_step.get("type") or "event")

        # 优先使用 title，如果没有则使用 target（来自 actions）
        title = raw_step.get("title") or raw_step.get("target") or step_type
        if not isinstance(title, str):
            title = str(title)

        # 优先使用 detail，如果没有则使用 result（来自 actions）
        detail = raw_step.get("detail") or raw_step.get("result") or ""
        if not isinstance(detail, str):
            detail = str(detail)

        steps.append({
            "id": step_id,
            "type": step_type,
            "title": title,
            "detail": detail,
            "status": str(raw_step.get("status") or "completed"),
            "occurred_at": raw_step.get("occurred_at") if raw_step.get("occurred_at") else None,
            "artifact_path": str(raw_step.get("artifact_path") or ""),
            "source": str(raw_step.get("source") or ""),
        })
    return steps
```

### 修改 3: 前端自动展开优化（辅助改进）

**文件：** `apps/frontend/src/components/ui/agent-plan.tsx`

**位置：** 第150-186行

已添加自动展开逻辑（之前的修改保留）。

## 📊 数据映射关系

| YAML字段 (actions) | 后端映射 | 前端显示 |
|-------------------|---------|---------|
| `type` | → `type` | 步骤类型图标 |
| `target` | → `title` | 步骤标题（粗体） |
| `result` | → `detail` | 步骤详情（灰色） |
| `status` | → `status` | 步骤状态（✓/✗） |
| `id` | → `id` | 唯一标识 |

## 🎬 预期效果

修复后，用户将看到：

```
工作台 (模块)
  └─ 探索广场 (页面) ← 自动展开
      ├─ 🔴 navigate: 起始URL：https://www.cybotstar.cn/agentStore
      │   └─ 浏览器错误: page.goto: Protocol error...
      ├─ ✅ observe: 页面整体布局，包括智能体卡片、按钮、导航等元素
      │   └─ 观察完成: 发现 41 个元素
      ├─ ✅ click: 包含文本"测试_自主规划智能体"的卡片
      │   └─ 成功点击元素: 创建智能体
      ├─ ✅ observe: 对话页面的初始布局
      │   └─ 观察完成: 发现 41 个元素
      ├─ 🔴 click: 对话模型选择器（下拉菜单/下拉框）
      │   └─ 未找到匹配元素
      └─ ...更多步骤
```

## 🔄 验证步骤

1. **重启后端服务**（必须！加载新代码）
   ```bash
   cd apps/backend
   # 停止现有服务
   # 重新启动
   ```

2. **刷新前端页面**
   ```bash
   # 浏览器中按 Ctrl+Shift+R 或 Cmd+Shift+R 强制刷新
   ```

3. **查看探索任务**
   - 进入任意探索任务详情页
   - 查看"探索概览"标签
   - 页面应该自动展开，显示所有探索步骤

4. **验证数据**
   - 检查步骤数量是否与YAML中的actions数量一致
   - 检查步骤的类型、状态、内容是否正确显示

## 🐛 调试技巧

如果还是看不到步骤，检查：

1. **后端是否重启**
   ```bash
   # 检查进程
   ps aux | grep python | grep uvicorn
   ```

2. **浏览器控制台查看API返回**
   ```javascript
   // 打开开发者工具 -> Network -> 找到 /detail 请求
   // 查看 Response，检查 modules[0].pages[0].steps 是否有数据
   ```

3. **直接查询数据库验证**
   ```bash
   cd apps/backend
   sqlite3 data/ai_testing.db "SELECT artifact_root FROM exploration_runs LIMIT 1;"
   # 检查对应的 YAML 文件是否存在 actions 字段
   ```

## 📝 技术总结

这个问题体现了一个经典的软件工程问题：

1. **症状**：前端不显示数据
2. **第一印象**：前端渲染逻辑问题
3. **实际原因**：数据源字段名不匹配
4. **教训**：遇到显示问题，要从数据源开始追踪，而不是只看UI层

**调试顺序应该是：**
1. ✅ 数据源（YAML文件）→ 有 `actions`，无 `steps`
2. ✅ 数据处理（后端）→ 读取 `steps`（不存在）
3. ✅ 数据传输（API）→ 返回空数组
4. ✅ 数据展示（前端）→ 没数据可显示

**修复顺序：**
1. 🔧 修复数据处理层（后端读取逻辑）← **最关键**
2. 🔧 增强数据兼容性（字段映射）
3. 🔧 优化用户体验（自动展开）

## 🎉 总结

这次修复的核心是：
- **不是前端的展开/折叠问题**
- **不是UI组件的渲染问题**  
- **是后端读取了不存在的字段**

现在已经修复了：
- ✅ 后端正确读取 `actions` 字段
- ✅ 自动转换为 `steps` 格式
- ✅ 前端自动展开最新页面
- ✅ 完整显示所有探索步骤

重启后端服务后，问题应该完全解决！
