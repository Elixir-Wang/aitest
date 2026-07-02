# 探索概览界面实现说明

## 已完成的工作

### 1. 设计文档
创建了 `exploration-overview-design.md`，包含：
- 完整的布局结构设计
- 左右双栏的详细规划
- 响应式设计方案
- 交互特性说明
- 视觉风格指南

### 2. 组件实现
创建了 `exploration-task-info-panel.tsx`，包含：
- `ExplorationTaskInfoPanel` - 主容器组件
- `ExplorationStepCard` - 步骤卡片组件
- `ExplorationEventCard` - 事件卡片组件
- `ReadableExecutionDisplayCard` - 可读性展示卡片
- `StepStatusIcon` - 状态图标组件

## 集成指南

### 第一步：复制组件文件

将 `exploration-task-info-panel.tsx` 复制到你的前端项目中：

```bash
# 目标位置建议
apps/frontend/src/components/ai-testing/exploration-task-info-panel.tsx
```

### 第二步：在探索详情页面中使用

修改 `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`：

```typescript
// 1. 导入新组件
import { ExplorationTaskInfoPanel } from "@/components/ai-testing/exploration-task-info-panel";

// 2. 替换空的 ExplorationModuleProgressPanel 实现
function ExplorationModuleProgressPanel({
  isUnsupportedArtifact,
  loading,
  monitor,
  onRestart,
  restarting,
  run,
  unsupportedArtifactReason,
}: {
  isUnsupportedArtifact: boolean;
  loading: boolean;
  monitor: ExplorationMonitorState;
  onRestart: () => Promise<void> | void;
  restarting: boolean;
  run: ExplorationRun | null;
  unsupportedArtifactReason: string;
}) {
  // 如果是不支持的产物格式，显示提示
  if (isUnsupportedArtifact) {
    return (
      <ShellSection>
        <UnsupportedArtifactNotice
          onRestart={onRestart}
          reason={unsupportedArtifactReason}
          restarting={restarting}
        />
      </ShellSection>
    );
  }

  // 使用新的双栏布局组件
  return (
    <ShellSection>
      <ExplorationTaskInfoPanel monitor={monitor} loading={loading} />
    </ShellSection>
  );
}
```

### 第三步：确保图标导入

确保 `lucide-react` 已安装并导入所需图标：

```typescript
import {
  CheckCircle2,
  Circle,
  ListChecks,
  Loader2,
  XCircle,
  AlertTriangle,
  MinusCircle,
} from "lucide-react";
```

## 功能特性

### 左侧面板 - 探索计划和步骤

1. **计划概览卡片**
   - 显示探索目标、范围、策略
   - 显示预计时长和步骤数
   - 使用 `ListChecks` 图标

2. **步骤列表**
   - 每个步骤显示为独立卡片
   - 状态图标动态变化：
     - `Circle` - 待执行（灰色）
     - `Loader2`（旋转动画）- 执行中（蓝色）
     - `CheckCircle2` - 已完成（绿色）
     - `XCircle` - 失败（红色）
     - `MinusCircle` - 已取消（灰色）
     - `AlertTriangle` - 部分完成/阻塞（黄色/橙色）
   - 显示步骤编号、描述、模块名称
   - 执行中或失败的步骤自动展开显示详情

### 右侧面板 - 实时执行监控

1. **阶段指示器**
   - 显示当前执行阶段（规划中、执行中、已完成等）
   - 执行阶段显示旋转动画

2. **实时事件流**
   - 时间轴样式显示所有事件
   - 每条事件包含：
     - 时间戳（格式化为 HH:MM:SS）
     - 事件类型标签（带颜色标识）
     - 事件摘要
     - 可选的详细展示卡片
   - 不同状态用不同颜色区分：
     - 成功：绿色
     - 执行中：蓝色
     - 失败：红色
     - 警告：黄色
     - 取消/待执行：灰色

3. **可读性展示**
   - 支持展示模型分析、导航、点击等结构化信息
   - 支持字段列表显示（标签-值对）
   - 支持代码块显示（使用等宽字体）
   - 支持标签（chips）显示

## 响应式设计

- **大屏幕（lg 及以上）**：双栏并排，左侧 320px 固定宽度
- **中小屏幕**：上下堆叠，左侧面板在上

布局使用 Tailwind CSS Grid：
```css
grid lg:grid-cols-[320px_minmax(0,1fr)]
```

## 实时数据流

组件设计为接收实时更新的 `monitor` 状态：

1. 主页面通过 SSE 接收后端事件
2. 使用 `applyStreamEvent` 函数更新 `monitor` 状态
3. `ExplorationTaskInfoPanel` 自动响应状态变化重新渲染
4. 新事件添加到事件流顶部（最新在前）

## 样式系统

使用项目现有的设计系统：

- **容器背景**：`bg-muted/20`（左侧）、`bg-background`（右侧）
- **卡片样式**：`rounded-lg border bg-background p-3`
- **状态颜色**：
  - 成功：`text-green-600`
  - 警告：`text-amber-600`
  - 错误：`text-red-600`
  - 执行中：`text-blue-600`
  - 默认：`text-muted-foreground`
- **悬停效果**：`hover:bg-muted/30`
- **过渡动画**：`transition-colors`

## 性能优化建议

1. **虚拟滚动**：如果事件数量超过 100 条，考虑使用虚拟滚动（如 `react-virtual`）
2. **事件限制**：后端可以限制返回的事件数量（如最近 200 条）
3. **自动滚动**：可以添加自动滚动到最新事件的功能：

```typescript
const eventsEndRef = useRef<HTMLDivElement>(null);

useEffect(() => {
  // 有新事件时自动滚动
  eventsEndRef.current?.scrollIntoView({ behavior: "smooth" });
}, [events.length]);

// 在事件流末尾添加
<div ref={eventsEndRef} />
```

## 下一步增强

1. **事件过滤**：添加按钮过滤特定类型的事件（只看错误、只看关键步骤等）
2. **步骤详情弹窗**：点击步骤卡片弹出详细信息对话框
3. **导出功能**：导出执行日志为文本或 JSON 文件
4. **搜索功能**：在事件流中搜索关键词
5. **截图预览**：如果步骤包含截图路径，显示缩略图并支持点击查看大图

## 测试建议

1. 测试不同执行阶段的 UI 显示
2. 测试大量步骤和事件的性能
3. 测试响应式布局在不同屏幕尺寸下的表现
4. 测试实时数据流更新的流畅性
5. 测试错误状态和边界情况（无数据、加载失败等）

## 常见问题

**Q: 如何自定义左侧面板宽度？**
A: 修改 Grid 布局的列定义，例如改为 380px：
```typescript
className="grid lg:grid-cols-[380px_minmax(0,1fr)]"
```

**Q: 如何修改状态颜色？**
A: 在 `statusColor` 对象中修改对应状态的 Tailwind 类名。

**Q: 如何添加新的事件类型显示？**
A: 在 `ReadableExecutionDisplay` 的 `kind` 类型中添加新类型，并在 `ReadableExecutionDisplayCard` 中处理展示逻辑。

**Q: 事件顺序是什么？**
A: 事件数组是最新的在前面（数组开头），组件按照数组顺序渲染，所以最新事件显示在顶部。
