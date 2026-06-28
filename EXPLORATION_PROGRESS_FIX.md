# 探索进度显示修复报告

## 问题描述

用户反馈：点击探索后，前端没有显示探索进度，顶部任务进度也没有弹出。探索详情页面的"探索概览"标签下显示"暂无探索模块进度信息"。

## 问题原因

在探索详情页面 (`apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`) 的"探索概览"标签中，探索模块进度部分被硬编码为显示空状态文本，没有实际渲染进度数据。

**问题代码位置**：第 1673-1683 行

```tsx
<div className="rounded-lg border bg-muted/20 p-8 text-center text-muted-foreground text-sm">
  暂无探索模块进度信息
</div>
```

## 修复方案

### 1. 修复探索进度显示逻辑

将硬编码的空状态替换为实际的进度展示逻辑：

- **加载状态**：显示"探索进度加载中..."
- **不支持的产物**：显示 `UnsupportedArtifactNotice` 组件，提示用户重新探索
- **有进度数据**：使用 `AgentPlan` 组件渲染实际的探索进度（`agentPlanTasks`）
- **空状态**：根据任务状态显示相应的提示信息

### 2. 添加缺失的辅助函数

添加 `stringValue` 函数，用于安全地将未知类型转换为字符串：

```tsx
function stringValue(value: unknown): string {
  return value ? String(value) : "";
}
```

### 3. 补充 Table 组件导入

添加 `Table` 相关组件和 `StatusBadgeTone` 类型的导入，确保实时监控面板中的表格正常显示。

## 修改文件

- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

## 修改内容

### 1. 导入部分（第 35-38 行）

```tsx
import { StatusBadge, type StatusBadgeTone } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
```

### 2. 辅助函数（第 805-817 行）

```tsx
function stringValue(value: unknown): string {
  return value ? String(value) : "";
}

function arrayOfStrings(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function numberOrNull(value: unknown): number | null {
  const next = Number(value);
  return Number.isFinite(next) ? next : null;
}
```

### 3. 探索进度渲染逻辑（第 1672-1696 行）

```tsx
<ShellSection className="min-w-0">
  <div className="mb-4 flex items-center justify-between gap-3">
    <div>
      <h2 className="font-medium text-sm">探索模块进度</h2>
      <p className="text-muted-foreground text-xs">展示模块、页面状态和页面探索步骤</p>
    </div>
  </div>
  {loading ? (
    <div className="rounded-lg border bg-muted/20 p-8 text-center text-muted-foreground text-sm">
      探索进度加载中...
    </div>
  ) : isUnsupportedArtifact ? (
    <UnsupportedArtifactNotice
      onRestart={startExploration}
      reason={unsupportedArtifactReason}
      restarting={starting}
    />
  ) : agentPlanTasks.length > 0 ? (
    <AgentPlan tasks={agentPlanTasks} />
  ) : (
    <div className="rounded-lg border bg-muted/20 p-8 text-center text-muted-foreground text-sm">
      {run?.status === "pending" ? "任务尚未开始，点击「开始探索」后将显示进度信息。" : "暂无探索模块进度信息"}
    </div>
  )}
</ShellSection>
```

## 功能验证

### 验证步骤

1. 启动前端开发服务器
2. 进入探索详情页面（`/projects/{projectId}/exploration/{runId}`）
3. 切换到"探索概览"标签
4. 验证以下场景：
   - **加载中**：页面加载时显示加载提示
   - **待执行任务**：未开始的任务显示提示"任务尚未开始，点击「开始探索」后将显示进度信息。"
   - **运行中任务**：显示 `AgentPlan` 组件，展示模块、页面和探索步骤的实时进度
   - **已完成任务**：显示完整的探索进度树
   - **不支持的产物**：显示警告提示和"重新探索"按钮

### 构建验证

✅ TypeScript 类型检查通过  
✅ Next.js 生产构建成功

## 预期效果

修复后，用户在探索详情页面的"探索概览"标签中可以看到：

1. **实时进度展示**：通过 `AgentPlan` 组件展示模块、页面和探索步骤的层级结构
2. **进度状态**：每个模块和页面显示对应的状态（待执行、运行中、已完成、失败等）
3. **探索步骤**：展示每个页面的具体探索步骤和动作结果
4. **友好提示**：根据不同状态显示相应的提示信息

## 相关组件

- `AgentPlan`：用于展示层级化的探索进度树
- `UnsupportedArtifactNotice`：用于提示历史产物不支持的情况
- `ExplorationRealtimeMonitor`：在"探索计划"标签中展示实时监控信息

## 日期

2025-06-28
