# 页面探索功能规范澄清说明

**日期**: 2026-06-27  
**版本**: v1.2 澄清  

---

## 📝 核心澄清

### 1. 探索和缓存的关系

**原分析误解**: 认为"缓存命中后跳过该页"会导致无法发现链接，探索无法继续

**实际逻辑澄清**:
```
核心原则：有探索就不用缓存，有缓存就不探索

正确理解：
- 缓存命中 = 这个页面已经探索过 = 完全跳过
- 缓存未命中 = 需要探索 = 重新分析，不使用缓存数据

链接发现的解决方案：
- 缓存中必须包含 links_discovered 字段
- 缓存命中时，直接从缓存读取链接加入队列
- 不需要重新访问页面，不需要重新获取快照
```

**正确流程**:
```
首次探索 /workspace:
  1. 检查缓存 → 未命中
  2. 访问页面，获取快照
  3. 分析元素，生成定位器
  4. 提取链接: [/agents, /settings, /knowledge]
  5. 保存到缓存（包含 links_discovered）
  6. 将链接加入队列
  7. 继续探索队列中的页面

第二次探索 /workspace（相同起始页）:
  1. 检查缓存 → 命中！
  2. 从缓存读取 links_discovered: [/agents, /settings, /knowledge]
  3. 将链接加入队列（每个链接会再次检查自己的缓存）
  4. 不访问 /workspace，不重新获取快照
  5. 继续探索队列中未缓存的页面
```

**必要的Schema更新**:
```yaml
# pages/page-workspace.yaml
page:
  id: "page-workspace"
  title: "工作台"
  normalized_path: "/workspace"
  explored_at: "2026-06-26T11:00:00Z"
  
  # ✅ 必须包含：发现的链接
  links_discovered:
    - url: "/workspace/agents"
      text: "智能体"
      locator: "getByRole('link', { name: '智能体' })"
      priority: 1  # 主导航
    
    - url: "/workspace/settings"
      text: "设置"
      locator: "getByRole('link', { name: '设置' })"
      priority: 1
    
    - url: "/workspace/knowledge"
      text: "知识库"
      locator: "getByRole('link', { name: '知识库' })"
      priority: 1
  
  # 元素定位器
  elements:
    - id: "nav_agents"
      name: "智能体导航"
      role: "link"
      locators: [...]
```

**结论**: 
- ✅ 探索和缓存不冲突
- ✅ 缓存必须包含 links_discovered
- ✅ 这个设计是合理的

---

### 2. 导航场景下的错误驱动验证

**原分析误解**: 认为"点击后页面跳转了无法优化定位器"

**实际逻辑澄清**:
```
错误驱动验证的正确理解：
- "执行动作，无效的时候触发排查更换定位器"
- "无效" = 执行失败（没有成功点击）
- 不是"点击后出问题才优化"

正确流程：
1. 尝试点击定位器
2. 如果失败（ElementNotFoundError, NotUniqueError等）
   → 优化定位器
   → 重试
3. 如果成功
   → 记录定位器（已隐式验证）
   → 继续探索
```

**具体场景**:
```python
# 场景A: 定位器不唯一（点击失败）
try:
    playwright_cli.locator("getByRole('button', { name: '提交' })").click()
except NotUniqueError:
    # ✅ 点击失败，页面没有跳转
    # ✅ 可以在当前页面优化定位器
    optimized = "getByRole('form').getByRole('button', { name: '提交' })"
    playwright_cli.locator(optimized).click()

# 场景B: 定位器唯一（点击成功）
try:
    playwright_cli.locator("getByRole('link', { name: '智能体' })").click()
    # ✅ 点击成功，页面跳转
    # ✅ 记录定位器，不需要优化
    record_locator("getByRole('link', { name: '智能体' })", validated=True)
except:
    # 不会走到这里（点击成功了）
    pass
```

**关键点**:
- 只有在执行失败时才优化定位器
- 执行失败 = 页面没有变化 = 可以安全优化
- 执行成功 = 定位器有效 = 不需要优化

**结论**:
- ✅ 错误驱动验证是可行的
- ✅ 原分析理解错了

---

### 3. URL归一化规则

**原分析**: 需要明确具体规则

**实际逻辑澄清**:
```
"同项目域名后面的部分是一样的"
= 提取路径部分作为归一化标识
```

**明确的归一化规则**:
```python
from urllib.parse import urlparse, unquote

def normalize_url(url: str) -> str:
    """
    URL归一化规则：
    1. 提取path（域名后面的部分）
    2. 去除query参数（?后面的）
    3. 去除fragment（#后面的）
    4. URL解码（%20 → 空格）
    5. 统一去除尾部斜杠（除了根路径"/"）
    6. 转小写（路径通常不区分大小写）
    """
    parsed = urlparse(url)
    path = unquote(parsed.path)
    
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    
    return path.lower()

# 示例
normalize_url("https://test.com/workspace/agents")       # → "/workspace/agents"
normalize_url("https://test.com/workspace/agents/")      # → "/workspace/agents"
normalize_url("https://test.com/workspace/agents?tab=1") # → "/workspace/agents"
normalize_url("https://test.com/workspace/agents#top")   # → "/workspace/agents"
normalize_url("https://prod.com/workspace/agents")       # → "/workspace/agents" (跨环境)
```

**结论**:
- ✅ URL归一化规则明确
- ✅ 支持跨环境缓存复用

---

## 🔄 修正后的问题清单

### ❌ 删除的"问题"（误解）

1. ~~探索和缓存的矛盾~~ → 不是问题，需要缓存链接信息
2. ~~导航场景验证不可行~~ → 不是问题，错误驱动验证是可行的

### ✅ 真正需要补充的内容

#### P0 - 必须补充（阻塞实施）

**1. pages/*.yaml Schema必须包含 links_discovered**

当前Schema缺少这个字段：
```yaml
page:
  id: "page-001"
  title: "工作台"
  normalized_path: "/workspace"
  explored_at: "2026-06-26T11:00:00Z"
  
  # ✅ 必须新增
  links_discovered:
    - url: "/workspace/agents"
      text: "智能体"
      locator: "getByRole('link', { name: '智能体' })"
      priority: 1  # 1=主导航, 2=侧边栏, 3=页面内链接
  
  elements:
    - id: "nav_agents"
      ...
```

**2. 缓存检查逻辑必须返回links_discovered**

当前代码：
```python
def check_cache(normalized_path: str, project_id: str) -> Optional[dict]:
    # ...
    return {
        'cache_hit': True,
        'page_file': page_file,
        'page_id': page['page_id'],
        'last_explored_at': page['last_explored_at']
        # ❌ 缺少 links_discovered
    }
```

修正后：
```python
def check_cache(normalized_path: str, project_id: str) -> Optional[dict]:
    # ...
    page_data = load_yaml(page_file)
    
    return {
        'cache_hit': True,
        'page_file': page_file,
        'page_id': page['page_id'],
        'last_explored_at': page['last_explored_at'],
        'links_discovered': page_data['page']['links_discovered']  # ✅ 新增
    }
```

**3. 探索流程必须处理缓存的链接**

当前流程缺少这一步：
```python
# 5.1 探索流程 第 c 步修正
def explore_page(url):
    normalized = normalize_url(url)
    cache_result = check_cache(normalized, project_id)
    
    if cache_result['cache_hit']:
        # ✅ 从缓存读取链接
        for link in cache_result['links_discovered']:
            exploration_queue.add(link['url'], parent_depth=current_depth)
        
        # ✅ 跳过该页面的元素探索
        return {
            'status': 'cached',
            'links_added': len(cache_result['links_discovered'])
        }
    
    # 缓存未命中，正常探索
    snapshot = playwright_cli.snapshot(url)
    elements = analyze_elements(snapshot)
    links = extract_links(snapshot)
    
    # ✅ 保存时包含链接
    save_page_artifact({
        'page': {...},
        'links_discovered': links,
        'elements': elements
    })
    
    # ✅ 将链接加入队列
    for link in links:
        exploration_queue.add(link['url'], parent_depth=current_depth)
```

#### P1 - 应该明确（建议补充）

4. URL归一化的具体实现代码（已在上面提供）
5. 探索深度的计算逻辑
6. states设计说明或简化
7. 探索范围判断逻辑
8. 定位器优化的具体策略

#### P2 - 细节完善

9. 时间估算调整（13天 → 20天）
10. 缓存命中率指标调整（30% → 80%）
11. 自动失效检测的边界条件处理
12. 清除缓存的范围说明
13. 环境区分机制
14. 登录态管理设计

---

## 📋 需要更新的文档章节

### 3.4 产物Schema - 必须更新

**当前**:
```yaml
pages/page-*.yaml:
  page:
    id: "page-001"
    elements: [...]
```

**更新为**:
```yaml
pages/page-*.yaml:
  page:
    id: "page-001"
    
    # ✅ 新增字段
    links_discovered:
      - url: "/target"
        text: "显示文本"
        locator: "定位器代码"
        priority: 1  # 1=主导航, 2=次要, 3=页面内
    
    elements: [...]
```

### 5.1 探索流程 - 必须更新

**第 c 步更新为**:
```
c. 如已探索 → 从缓存读取 links_discovered，加入队列，跳过元素探索
```

**新增步骤**（在第 h 和 i 之间）:
```
h. 关键点获取快照
h2. ✅ 新增：提取页面链接
     - 识别所有导航链接（主导航、侧边栏、页面内链接）
     - 记录链接的URL、文本、定位器、优先级
i. 写入/更新项目级pages产物（包含 links_discovered）
```

### 3.3 缓存检查逻辑 - 必须更新

```python
def check_cache(normalized_path: str, project_id: str) -> Optional[dict]:
    """
    检查页面是否已探索（项目级缓存）
    
    ✅ 返回值必须包含 links_discovered
    """
    cache_index_path = f"data/projects/{project_id}/page_exploration/cache_index.yaml"
    cache_index = load_yaml(cache_index_path)
    
    for page in cache_index.get('pages', []):
        if page['normalized_path'] == normalized_path:
            page_file = f"data/projects/{project_id}/page_exploration/{page['page_file']}"
            
            if Path(page_file).exists():
                page_data = load_yaml(page_file)  # ✅ 读取完整数据
                
                return {
                    'cache_hit': True,
                    'page_file': page_file,
                    'page_id': page['page_id'],
                    'last_explored_at': page['last_explored_at'],
                    'links_discovered': page_data['page'].get('links_discovered', [])  # ✅ 新增
                }
    
    return {'cache_hit': False}
```

---

## 🎯 下一步行动

### 立即执行
1. ✅ 更新 3.4 产物Schema（增加 links_discovered 字段）
2. ✅ 更新 5.1 探索流程（第 c 步 + 新增 h2 步）
3. ✅ 更新 3.3 缓存检查逻辑（返回 links_discovered）

### 建议补充
4. 补充 3.1 URL归一化具体实现
5. 补充探索深度计算逻辑
6. 简化或说明 states 设计

---

## ✅ 修正后的质量评分

| 维度 | v1.2 原评分 | 修正后评分 | 说明 |
|------|-----------|-----------|------|
| 完整性 | 8.5/10 | 8.0/10 | 缺少 links_discovered 字段 |
| 正确性 | 6.0/10 | **9.0/10** | 核心逻辑是对的，只是表述不够明确 |
| 清晰性 | 7.5/10 | 7.5/10 | 需要补充 links_discovered 的说明 |
| 可实施性 | 7.0/10 | **8.5/10** | 补充 links_discovered 后即可实施 |

**综合得分**: **8.0/10** → **8.3/10**（补充 links_discovered 后）

---

**结论**: 
- 原规范的核心设计是正确的
- 只需要补充 links_discovered 字段和相关逻辑
- 不需要大规模重构，只需要增量补充

**澄清完成时间**: 2026-06-27  
**下一步**: 更新 v1.2 规范，补充 links_discovered 相关内容
