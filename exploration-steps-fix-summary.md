# 探索任务步骤显示问题修复总结

## 问题描述

用户在执行探索任务时，探索模块进度只显示"工作台"三个字，不显示每次的步骤（进入哪个页面、点击哪些操作等详细信息）。

## 问题分析

### 根本原因

经过代码分析，发现问题出在前端显示逻辑：

1. **后端数据正常**：
   - `apps/backend/app/services/exploration/service.py` 第1989行和第2079-2100行的 `_normalize_steps` 函数正确返回了探索步骤数据
   - 每个页面的 `steps` 数组包含了详细的探索步骤信息

2. **前端组件支持显示步骤**：
   - `apps/frontend/src/components/ui/agent-plan.tsx` 第374-391行有渲染步骤的代码
   - 组件完全支持显示子任务的步骤列表

3. **问题所在**：
   - AgentPlan 组件中的 **子任务（页面）默认是折叠状态**
   - `expandedSubtasks` 初始化为空对象 `{}`（第139行）
   - **只有用户手动点击页面（子任务）后才会展开显示详细步骤**

### 数据流程

```
后端返回数据:
└─ modules (模块)
   └─ pages (页面/子任务)
      └─ steps (探索步骤) ← 这里有数据但默认不显示

前端显示逻辑:
├─ 模块默认展开 ✓ (能看到"工作台")
└─ 页面默认折叠 ✗ (看不到步骤详情) ← 问题所在
```

## 解决方案

### 修改文件
`apps/frontend/src/components/ui/agent-plan.tsx`

### 修改内容

在第150-186行添加了一个新的 `useEffect`，实现了自动展开子任务的逻辑：

```typescript
// 自动展开正在运行或最新的子任务，让用户能看到探索步骤
useEffect(() => {
  const newExpanded: Record<string, boolean> = {};

  for (const task of tasks) {
    if (!task.subtasks?.length) continue;

    // 优先展开正在运行中的子任务
    const runningSubtask = task.subtasks.find(
      (subtask) => subtask.status === "running" || subtask.status === "in-progress" || subtask.status === "queued"
    );

    if (runningSubtask) {
      newExpanded[`${task.id}-${runningSubtask.id}`] = true;
    } else {
      // 如果没有运行中的，展开最后一个有步骤的子任务
      const subtaskWithSteps = [...task.subtasks].reverse().find((subtask) => subtask.steps && subtask.steps.length > 0);
      if (subtaskWithSteps) {
        newExpanded[`${task.id}-${subtaskWithSteps.id}`] = true;
      }
    }
  }

  // 只在有新的需要展开的子任务时更新状态
  if (Object.keys(newExpanded).length > 0) {
    setExpandedSubtasks((current) => {
      // 保留用户手动操作的状态，只添加新的自动展开
      const merged = { ...current };
      for (const [key, value] of Object.entries(newExpanded)) {
        if (!(key in merged)) {
          merged[key] = value;
        }
      }
      return merged;
    });
  }
}, [tasks]);
```

### 解决方案特点

1. **智能展开**：
   - 优先展开正在运行中的子任务（`running`/`in-progress`/`queued`）
   - 如果没有运行中的，展开最后一个包含步骤的子任务
   
2. **保留用户操作**：
   - 只自动展开之前没有被用户操作过的子任务
   - 用户手动折叠的子任务不会被自动重新展开

3. **实时更新**：
   - 当探索任务状态变化时，会自动调整展开状态
   - 始终确保用户能看到最新的探索进度

## 预期效果

修复后，用户在查看探索任务时将能够：

1. ✅ 直接看到"工作台"页面的详细探索步骤
2. ✅ 看到每次进入哪个页面的信息
3. ✅ 看到每次点击、填写等操作的详细记录
4. ✅ 实时跟踪正在执行的探索步骤

## 测试建议

1. 启动一个新的探索任务，观察是否能实时看到探索步骤
2. 查看已完成的探索任务，验证是否能看到历史步骤
3. 手动折叠某个页面后，刷新页面，验证是否保持折叠状态
4. 查看有多个页面的探索任务，验证最新页面是否自动展开

## 相关文件

- 修改文件：`apps/frontend/src/components/ui/agent-plan.tsx`
- 相关文件：
  - `apps/backend/app/services/exploration/service.py` (后端数据处理)
  - `apps/backend/app/schemas/exploration.py` (数据结构定义)
  - `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx` (探索详情页面)
