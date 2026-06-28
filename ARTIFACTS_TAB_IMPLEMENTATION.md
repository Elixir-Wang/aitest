# 探索产物Tab实现方案

## 实现进度总结

### 已完成

✅ **后端API**：
- 添加 `list_all_artifacts()` 服务方法 - 列出所有产物
- 添加 `build_artifact_tree()` 服务方法 - 构建产物树结构  
- 添加 `/page-exploration/artifacts` API端点 - 列出产物
- 添加 `/page-exploration/artifacts-tree` API端点 - 获取产物树

✅ **前端基础**：
- 修改 `explorationTabs` 数组，添加"探索产物"选项

### 待完成

**前端UI实现**（约3-4小时工作量）：

1. **产物列表/树视图组件** - 2小时
   - 状态管理（loading, artifacts, selectedArtifact）
   - API调用（useEffect加载产物数据）
   - 树形结构渲染（可折叠的项目→任务→产物层级）
   - 列表视图渲染（表格形式，带搜索和筛选）

2. **产物预览组件** - 1小时
   - 根据文件类型渲染不同预览
   - 支持图片、JSON、文本、Markdown预览
   - 添加下载按钮

3. **样式和交互优化** - 1小时
   - 参考知识库样式
   - 添加搜索和筛选功能
   - 优化加载状态和错误处理

## 快速实现方案（MVP）

由于时间关系，建议先实现一个简化的产物列表视图：

### 第一步：添加产物Tab基础界面（15分钟）

```tsx
{activeTab === "探索产物" ? (
  <ShellSection>
    <div className="mb-4">
      <h2 className="font-medium text-sm">探索产物</h2>
      <p className="text-muted-foreground text-xs">查看所有探索任务生成的产物文件</p>
    </div>
    
    {/* 简化版：先显示提示信息 */}
    <div className="rounded-lg border bg-muted/20 p-8 text-center">
      <p className="text-muted-foreground text-sm">
        探索产物功能开发中，即将上线
      </p>
      <p className="mt-2 text-muted-foreground text-xs">
        将支持查看截图、accessibility tree、页面结构等产物
      </p>
    </div>
  </ShellSection>
) : null}
```

### 第二步：实现基础产物列表（1-2小时）

添加状态和API调用：

```tsx
const [artifacts, setArtifacts] = useState<any[]>([]);
const [artifactsLoading, setArtifactsLoading] = useState(false);

useEffect(() => {
  if (activeTab === "探索产物") {
    loadArtifacts();
  }
}, [activeTab, projectId]);

async function loadArtifacts() {
  setArtifactsLoading(true);
  try {
    const params = projectId ? `?project_id=${projectId}` : '';
    const data = await apiRequest<any[]>(`/page-exploration/artifacts${params}`);
    setArtifacts(data);
  } catch (error) {
    // 错误处理
  } finally {
    setArtifactsLoading(false);
  }
}
```

渲染产物列表：

```tsx
<Table>
  <TableHeader>
    <TableRow>
      <TableHead>产物名称</TableHead>
      <TableHead>所属任务</TableHead>
      <TableHead>类型</TableHead>
      <TableHead>大小</TableHead>
      <TableHead>创建时间</TableHead>
      <TableHead>操作</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    {artifacts.map((artifact) => (
      <TableRow key={artifact.id}>
        <TableCell>{artifact.file_name}</TableCell>
        <TableCell>{artifact.run_title}</TableCell>
        <TableCell>{artifact.artifact_type}</TableCell>
        <TableCell>{formatFileSize(artifact.file_size)}</TableCell>
        <TableCell>{formatDateTime(artifact.created_at)}</TableCell>
        <TableCell>
          <Button size="sm" variant="outline">查看</Button>
        </TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>
```

### 第三步：实现产物树视图（可选，2小时）

使用递归组件渲染树形结构，参考知识库的文件树实现。

## 推荐实施策略

鉴于当前情况，建议：

1. **立即完成第一步**（15分钟）- 添加占位界面，让Tab可用
2. **后续迭代第二步**（1-2小时）- 实现基础列表功能
3. **长期优化第三步**（2小时）- 实现完整树视图和预览

这样可以先让功能可见，避免用户点击Tab后看到报错，然后逐步完善功能。

## 测试要点

1. 切换到"探索产物"Tab不会报错
2. 有产物数据时正确显示列表
3. 无产物数据时显示空状态提示
4. 支持按项目筛选产物
5. 产物预览功能正常工作

## 相关文件

- 前端：`apps/frontend/src/components/ai-testing/exploration-workspace.tsx`
- 后端API：`apps/backend/app/api/v1/page_exploration.py`
- 后端服务：`apps/backend/app/services/exploration/page_exploration_service.py`
