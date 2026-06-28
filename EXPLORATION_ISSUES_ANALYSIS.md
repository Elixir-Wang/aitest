# 探索任务问题分析与解决方案

## 问题1：探索任务快速闪退

### 问题描述
执行探索任务时，顶部任务通知很快就闪退了，任务中心显示探索完成，但实际没有真正执行探索。

### 问题原因

**根本原因**：`_execute_exploration` 函数是一个简化的模拟实现

**代码位置**：`apps/backend/app/services/exploration/page_exploration_service.py:237-292`

**问题代码**：
```python
def _execute_exploration(run_id: str, run_config: dict) -> None:
    """执行探索逻辑（简化版 - 不使用Agent）"""
    import time

    project_id = run_config["project_id"]
    start_url = run_config["scope"]
    max_pages = run_config["max_pages"]

    # 模拟探索过程
    explored_count = 0
    pages_to_explore = [start_url]

    while pages_to_explore and explored_count < max_pages:
        # ... 检查停止标志 ...
        
        # 模拟页面探索（实际应调用Playwright CLI）
        time.sleep(0.5)  # 模拟探索耗时 ← 问题在这里
        
        # 简化版：只更新计数
        pass  # ← 没有实际调用探索逻辑
        
        explored_count += 1

    # 探索完成（实际上什么都没做）
```

### 解决方案

需要将模拟实现替换为真实的探索逻辑：

1. **调用 Playwright CLI** 进行实际的页面探索
2. **记录探索页面**到数据库（`exploration_page_repo.create()`）
3. **生成探索产物**（截图、accessibility tree等）
4. **推送 SSE 事件**通知前端进度更新
5. **生成探索报告**

### 建议实现步骤

1. 集成 Playwright CLI wrapper（已有 `apps/backend/app/agents/page_exploration/playwright/cli_wrapper.py`）
2. 实现真实的探索循环
3. 添加页面发现和抓取逻辑
4. 添加 SSE 事件推送
5. 生成结构化的探索产物

---

## 问题2：添加探索产物Tab

### 需求描述
在探索首页的"探索环境"tab右侧添加一个"探索产物"tab，可以切换查看：
- 指定探索任务的产物信息
- 全部探索产物树
- 样式参考公司知识库

### 设计方案

#### 1. 数据结构

**探索产物类型**：
- 页面截图 (screenshots)
- Accessibility Tree (accessibility)
- 页面结构 (structure)
- 探索日志 (logs)
- 探索报告 (report)

**产物树结构**：
```typescript
type ArtifactNode = {
  id: string;
  name: string;
  type: 'folder' | 'file';
  fileType?: 'screenshot' | 'accessibility' | 'structure' | 'log' | 'report';
  path: string;
  size?: number;
  createdAt: string;
  runId?: string;
  runTitle?: string;
  children?: ArtifactNode[];
};
```

#### 2. 前端实现

**文件位置**：`apps/frontend/src/components/ai-testing/exploration-workspace.tsx`

**Tab结构**：
```tsx
const explorationTabs = ["探索列表", "探索环境", "探索产物"];
```

**产物面板组件**：
```tsx
function ArtifactPanel() {
  return (
    <div className="space-y-4">
      {/* 顶部工具栏：搜索、筛选、排序 */}
      <ArtifactToolbar />
      
      {/* 产物树或列表视图 */}
      <ArtifactTree />
      
      {/* 产物预览面板 */}
      <ArtifactPreview />
    </div>
  );
}
```

**参考知识库样式**：
- 左侧：文件树结构（可折叠）
- 右侧：文件预览区域
- 顶部：面包屑导航
- 支持搜索和筛选

#### 3. 后端实现

**API端点**：
```python
# 列出所有产物（树形结构）
GET /api/v1/page-exploration/artifacts

# 列出指定探索任务的产物
GET /api/v1/page-exploration/runs/{run_id}/artifacts

# 获取产物内容
GET /api/v1/page-exploration/artifacts/{artifact_id}/content

# 下载产物
GET /api/v1/page-exploration/artifacts/{artifact_id}/download
```

**产物组织结构**：
```
artifacts/
├── {run_id}/
│   ├── screenshots/
│   │   ├── page-001.png
│   │   └── page-002.png
│   ├── accessibility/
│   │   ├── page-001.json
│   │   └── page-002.json
│   ├── structure/
│   │   └── pages.yaml
│   ├── logs/
│   │   └── exploration.log
│   └── report.md
```

### 实现优先级

**P0 - 必须**：
- [ ] 添加"探索产物"tab
- [ ] 实现产物列表API
- [ ] 显示产物树结构
- [ ] 支持按探索任务筛选

**P1 - 重要**：
- [ ] 产物预览功能
- [ ] 支持搜索和排序
- [ ] 产物下载功能
- [ ] 显示产物统计信息

**P2 - 可选**：
- [ ] 产物对比功能
- [ ] 产物版本管理
- [ ] 批量操作（删除、下载）

---

## 时间估算

- **问题1修复**：2-3天
  - 集成 Playwright CLI：1天
  - 实现探索逻辑：1天
  - 测试和优化：0.5-1天

- **问题2实现**：3-4天
  - 后端API开发：1天
  - 前端UI组件：1.5天
  - 产物预览功能：1天
  - 测试和优化：0.5-1天

**总计**：5-7天
