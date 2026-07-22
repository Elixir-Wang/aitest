# 测试要点脑图叶子节点点击行为优化

## 目标

点击测试要点脑图中的叶子节点后，保持当前脑图视图，仅更新节点选中高亮，不自动切换到列表，也不打开详情。

## 现状

`TestPointsPanel` 的 `handleSelectPoint` 在更新 `selectedPointId` 后调用 `setViewMode("list")`，导致任何可选择节点被点击后立即跳转到列表视图。

## 设计

- 保留 `selectedPointId` 更新，使脑图节点继续显示选中状态。
- 移除节点选择回调中的列表视图切换。
- 不修改通用 `MindMapTree` 的点击协议，避免影响测试用例脑图等其他调用方。
- 不增加详情弹窗或新的交互入口。

## 验证

- 增加前端契约测试，确认 `handleSelectPoint` 只设置选中节点，不调用 `setViewMode("list")`。
- 运行对应前端测试，确认既有测试不受影响。
