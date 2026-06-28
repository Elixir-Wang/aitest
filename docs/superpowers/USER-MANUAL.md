# 页面探索功能 - 使用手册

## 目录

1. [快速开始](#快速开始)
2. [创建探索任务](#创建探索任务)
3. [监控探索进度](#监控探索进度)
4. [查看探索结果](#查看探索结果)
5. [最佳实践](#最佳实践)
6. [常见问题](#常见问题)

---

## 快速开始

### 第一次使用

1. **打开页面探索管理界面**
   
   访问：`http://your-app.com/page-exploration`

2. **点击"New Exploration"按钮**

3. **配置探索参数**
   - Start URL: `https://your-app.com/workspace`
   - Max Depth: `3`
   - Max Pages: `50`

4. **点击"Start Exploration"**

5. **等待探索完成**
   
   实时进度会在页面上显示。

---

## 创建探索任务

### 基本配置

#### Start URL（必填）
探索的起始URL。

**示例：**
- `https://app.example.com/workspace`
- `https://app.example.com/dashboard`

**注意：**
- 必须是完整的URL（包含 `https://`）
- 必须是可访问的页面

#### Scope（可选）
限制探索范围，只探索该URL前缀下的页面。

**示例：**
- Scope: `https://app.example.com/workspace`
- 只会探索 `/workspace/*` 下的页面
- 不会探索 `/settings` 或其他路径

**什么时候使用：**
- 只想探索特定模块（如工作台）
- 避免探索到登录页或错误页

**留空的话：**
- 会探索整个域名下的所有页面

### 限制参数

#### Max Depth
最大探索深度，从起始页面算起。

**取值：** 1-10  
**推荐：** 3

**示例：**
```
Depth 0: /workspace (起始页)
Depth 1: /workspace/agents (从起始页点击一次)
Depth 2: /workspace/agents/create (再点击一次)
Depth 3: /workspace/agents/create/template (再点击一次)
```

**建议：**
- 简单站点：2-3
- 复杂站点：3-4
- 深层级站点：4-5

#### Max Pages
最多探索的页面数量。

**取值：** 1-500  
**推荐：** 50

**用途：**
- 防止无限探索
- 控制探索时间
- 节省资源

**估算：**
- 10页 ≈ 2-3分钟
- 50页 ≈ 10-15分钟
- 100页 ≈ 20-30分钟

#### Max Duration
最大探索时长（秒）。

**取值：** 60-7200  
**推荐：** 3600 (1小时)

**用途：**
- 超时自动停止
- 防止挂死

---

## 监控探索进度

### 实时统计

探索过程中会显示：

1. **Pages Explored**
   已探索的页面数量

2. **Queue Size**
   待探索的页面数量
   
   **含义：**
   - 为0时：即将完成
   - 持续增长：发现大量新页面
   - 持续为1-2：接近完成

3. **Progress**
   进度百分比
   
   **计算方式：**
   ```
   progress = (explored / (explored + queue)) * 100
   ```

### 状态说明

- **🔄 Connecting**: 正在连接服务器
- **⚡ Running**: 探索进行中
- **✅ Completed**: 探索成功完成
- **❌ Failed**: 探索失败

### 实时信息

#### Current URL
当前正在探索的页面。

#### Discovered Pages
发现的页面列表（显示最近5个）。

#### Completed Pages
已完成探索的页面（显示最近5个）。

#### Failed Pages
探索失败的页面及错误原因。

### 事件日志

显示最近10个事件，包括：
- 探索开始
- 页面发现
- 页面完成
- 进度更新
- 错误事件

---

## 查看探索结果

### 探索产物

探索完成后，会生成以下文件：

```
data/projects/{project_id}/page_exploration/
├── pages/                           # 页面产物（全局复用）
│   ├── page-workspace-agents.yaml
│   ├── page-workspace-settings.yaml
│   └── ...
│
├── explored_urls.yaml               # 已探索URL列表
│
└── runs/                            # 探索运行历史
    └── run-001/
        ├── run.yaml                 # 运行配置和统计
        ├── discovered_pages.yaml   # 本次发现的页面
        ├── graph.yaml               # 页面关系图
        ├── report.md                # 探索报告
        ├── logs/                    # 日志
        └── screenshots/             # 截图
```

### 页面产物 (pages/*.yaml)

每个页面一个YAML文件：

```yaml
page:
  id: page-workspace-agents
  title: 智能体工作台
  normalized_path: /workspace/agents
  explored_at: 2026-06-27T11:00:00Z
  
  elements:
    - id: create_agent_btn
      name: 创建智能体
      role: button
      locators:
        - kind: role
          code: getByRole('button', { name: '创建智能体' })
          priority: 1
          validation:
            is_unique: true
            is_visible: true
```

**用途：**
- 测试用例生成
- 元素定位复用
- 页面结构参考

### 探索报告 (report.md)

总结探索结果：
- 探索统计
- 发现的问题
- 优化建议

### 页面关系图 (graph.yaml)

展示页面之间的链接关系：

```yaml
edges:
  - from_page: page-workspace-agents
    to_page: page-agent-detail
    link_text: 查看详情
    locator: getByRole('link', { name: '查看详情' })
```

---

## 最佳实践

### 1. 探索前准备

**登录状态：**
- 确保浏览器已登录
- 或配置自动登录脚本

**网络环境：**
- 使用稳定的网络
- 避免高峰期探索

### 2. 合理设置参数

**小型站点（<20页）：**
```
Max Depth: 2-3
Max Pages: 20-30
```

**中型站点（20-100页）：**
```
Max Depth: 3
Max Pages: 50-100
```

**大型站点（>100页）：**
```
Max Depth: 3-4
Max Pages: 100-200
分批探索不同模块
```

### 3. 使用Scope限制

**按模块探索：**
```
# 第一次：探索工作台
Start URL: https://app.com/workspace
Scope: https://app.com/workspace

# 第二次：探索设置
Start URL: https://app.com/settings
Scope: https://app.com/settings
```

**好处：**
- 探索更聚焦
- 产物更清晰
- 便于管理

### 4. 监控探索过程

**正常情况：**
- Progress稳步增长
- Queue Size逐渐减少
- 少量Failed Pages (<5%)

**异常情况需关注：**
- Progress长时间不变
- 大量Failed Pages
- Queue Size异常增长

### 5. 定期重新探索

**建议频率：**
- 页面有更新时
- 每周一次（活跃项目）
- 每月一次（稳定项目）

---

## 常见问题

### Q1: 探索一直卡在某个页面？

**可能原因：**
- 页面加载太慢
- 页面有弹窗阻塞
- 定位器匹配失败

**解决：**
1. 查看Event Log确认卡在哪里
2. 检查Failed Pages是否有错误
3. 手动访问该页面排查问题
4. 调整Playwright timeout设置

### Q2: 很多页面探索失败？

**可能原因：**
- 登录状态失效
- 页面需要特殊权限
- 网络不稳定
- URL不可访问

**解决：**
1. 检查Failed Pages的错误信息
2. 确认登录状态
3. 检查网络连接
4. 调整Max Pages降低并发

### Q3: 探索发现的页面太少？

**可能原因：**
- Scope设置过窄
- Max Depth太小
- 页面链接是JavaScript跳转

**解决：**
1. 扩大Scope范围
2. 增加Max Depth到4-5
3. 检查是否使用了SPA路由

### Q4: 内存占用过高？

**解决：**
1. 减小Max Pages
2. 分批探索
3. 增加服务器内存
4. 定期清理旧的run数据

### Q5: SSE连接断开？

**可能原因：**
- 网络代理
- 防火墙
- Nginx配置问题

**解决：**
```nginx
# Nginx配置
location /api/exploration/runs {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_read_timeout 3600s;
}
```

### Q6: 探索结果如何使用？

**用途1: 自动化测试**
```python
from pages.page_workspace_agents import WorkspaceAgentsPage

page = WorkspaceAgentsPage()
page.create_agent_btn.click()
```

**用途2: 手动测试参考**
查看页面产物，了解所有可交互元素。

**用途3: 文档生成**
基于探索结果生成功能文档。

---

## 高级技巧

### 自定义探索策略

修改Skills配置，调整：
- 探索优先级
- 元素筛选规则
- 定位器生成策略

### 批量探索

使用API批量创建任务：
```bash
for module in workspace settings profile; do
  curl -X POST /api/exploration/runs \
    -d "{\"start_url\":\"https://app.com/$module\"}"
done
```

### 定时探索

配置cron定时任务：
```cron
# 每天凌晨2点探索
0 2 * * * /path/to/explore.sh
```

---

## 获取帮助

- **文档**: `/docs/superpowers/specs/`
- **API文档**: `http://localhost:8000/docs`
- **部署指南**: `/docs/superpowers/DEPLOYMENT.md`
- **问题反馈**: GitHub Issues
