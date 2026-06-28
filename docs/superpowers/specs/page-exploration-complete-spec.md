# 页面探索功能完整设计规范

**项目**: 基于 Playwright CLI + LangChain 的页面探索功能  
**创建日期**: 2026-06-26  
**最后更新**: 2026-06-27  
**版本**: 1.4  
**状态**: 设计完成，待实施

---

## 目录

1. [概述和背景](#1-概述和背景)
2. [整体架构设计](#2-整体架构设计)
3. [核心组件设计](#3-核心组件设计)
4. [Skills设计](#4-skills设计)
5. [探索流程和终止逻辑](#5-探索流程和终止逻辑)
6. [错误处理策略](#6-错误处理策略)
7. [实施计划](#7-实施计划)
8. [验收标准](#8-验收标准)

---

## 1. 概述和背景

### 1.1 背景

当前项目需要实现基于 Playwright CLI 和 LangChain 的页面元素探索功能，用于：
- 探索项目页面结构和交互元素
- 生成可复用的页面元素定位器快照
- 为后续自动化测试用例生成提供准确的元素定位信息

### 1.2 核心需求

1. 根据探索范围、探索目标、禁止路径进行智能探索
2. 使用语义化定位器（getByRole/getByText/getByLabel/getByTestId），避免不可复用的ref或CSS选择器
3. 定位器无效时自动更换其他定位器
4. 生成 playwright 探索快照（YAML格式）
5. 记录已探索URL，避免同一次探索的无限循环
6. 跨环境URL归一化（测试环境和生产环境URL不同但路径相同）
7. 重复探索会覆盖更新页面产物

### 1.3 非目标

- 不在本阶段实现测试用例生成
- 不在本阶段实现自动化测试执行
- 不使用 ref 定位器（因为不能复用）

---

## 2. 整体架构设计

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (React)                          │
│  - 创建探索任务（范围、目标、禁止路径）                      │
│  - 实时查看探索进度（SSE）                                   │
│  - 查看探索结果和产物                                        │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/SSE
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Exploration Service (FastAPI)                    │
│  - 任务CRUD                                                 │
│  - 任务调度与生命周期管理                                    │
│  - SSE事件推送                                              │
│  - 缓存索引管理                                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         LangChain Exploration Agent                         │
│  职责：                                                      │
│  - 理解探索目标和范围                                        │
│  - 制定探索计划                                              │
│  - 决策下一步动作（访问哪个链接、点击哪个按钮）              │
│  - 判断是否已探索（缓存检查）                                │
│  - 生成探索报告                                             │
│                                                             │
│  Tools:                                                     │
│  - playwright_cli_snapshot_tool                            │
│  - playwright_cli_navigate_tool                            │
│  - playwright_cli_click_tool                               │
│  - playwright_cli_fill_tool                                │
│  - cache_lookup_tool                                       │
│  - artifact_write_tool                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Playwright CLI Wrapper (Python)                  │
│  - 执行 playwright-cli 命令                                 │
│  - 解析快照输出（YAML）                                     │
│  - 会话管理                                                 │
│  - 登录态保存/恢复                                          │
└────────────────────┬────────────────────────────────────────┘
                     │ subprocess
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              playwright-cli (Node.js)                       │
│  - 浏览器自动化                                             │
│  - 页面快照生成                                             │
│  - 元素定位与交互                                           │
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Artifact Service (Python)                        │
│  - 页面产物生成（pages/*.yaml）                            │
│  - 探索图谱生成（graph.yaml）                              │
│  - 探索报告生成（report.md）                               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
data/projects/{project_id}/
├── requirements/                    # 需求文档（定义测试场景）
│   └── req-001-agent-management.md
│
└── page_exploration/                # 页面探索产物
    ├── pages/                       # ✅ 项目级pages（全局复用）
    │   ├── page-workspace-agents.yaml
    │   └── page-workspace-settings.yaml
    │
    ├── explored_urls.yaml           # ✅ 项目级已探索URL列表（避免循环）
    │
    └── runs/                        # 探索运行历史
        ├── run-001/
        │   ├── run.yaml             # 运行配置 + 统计摘要
        │   ├── discovered_pages.yaml  # 本次发现的页面（引用全局pages）
        │   ├── graph.yaml           # 页面关系图
        │   ├── screenshots/
        │   ├── logs/
        │   └── reports/
        └── run-002/
```

### 2.3 Pages全局共享架构

**核心价值：**
- 一次探索，所有环境（测试/生产/本地）都能复用同一份pages产物
- pages产物存储在项目级目录，不随探索run变化
- 跨环境URL映射，支持不同环境的URL归一化
- 重复探索会覆盖更新产物，保持产物最新

**工作流程：**

#### 阶段1：需求分析（定义测试内容）
需求文档定义测试场景、步骤和预期结果

#### 阶段2：页面探索（生成全局pages产物）
- 探索页面 → 生成或更新项目级pages产物
- 记录到 explored_urls.yaml → 避免同一次探索的循环
- 跨环境探索 → 归一化路径，共享产物

---

## 3. 核心组件设计

### 3.1 URL归一化策略

**目的**: 支持跨环境缓存复用

**核心原则**: 提取域名后面的路径部分作为归一化标识

**具体实现**:
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
    
    # 去除尾部斜杠（保留根路径的"/"）
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    
    return path.lower()
```

**归一化示例**:
```python
# 跨环境归一化
normalize_url("https://test.example.com/workspace/agents")    # → "/workspace/agents"
normalize_url("https://prod.example.com/workspace/agents")    # → "/workspace/agents"

# 去除尾部斜杠
normalize_url("https://test.com/workspace/agents/")           # → "/workspace/agents"

# 去除query和fragment
normalize_url("https://test.com/workspace/agents?tab=all")    # → "/workspace/agents"
normalize_url("https://test.com/workspace/agents#section1")   # → "/workspace/agents"

# URL解码
normalize_url("https://test.com/workspace%20agents")          # → "/workspace agents"

# 因此三个环境共享缓存
```

### 3.2 定位器优先级

**优先级顺序（从高到低）：**
1. `getByRole(role, { name })` - 最稳定，语义化最强
2. `getByLabel(label)` - 表单字段首选
3. `getByTestId(testId)` - 开发专门添加的测试ID
4. `getByText(text)` - 文本内容定位
5. `getByPlaceholder(placeholder)` - 输入框占位符
6. CSS选择器 - 最后选择，不推荐

**验证要求：**
- 每个定位器必须验证唯一性（count === 1）
- 每个定位器必须验证可见性（visible === true）
- 探索时直接使用语义定位器，不使用临时ref

### 3.3 已探索URL检查逻辑

**核心原则**: 记录已探索URL，避免同一次探索的无限循环

```python
def check_explored(normalized_path: str, project_id: str) -> dict:
    """
    检查URL是否已探索过（项目级记录）
    
    返回值：
    - explored: True/False（是否已探索过）
    - page_file: 页面产物路径（如果存在）
    - last_explored_at: 最后探索时间（如果存在）
    """
    explored_urls_path = f"data/projects/{project_id}/page_exploration/explored_urls.yaml"
    
    if not Path(explored_urls_path).exists():
        return {'explored': False}
    
    explored_urls = load_yaml(explored_urls_path)
    
    for url_record in explored_urls.get('urls', []):
        if url_record['normalized_path'] == normalized_path:
            page_file = f"data/projects/{project_id}/page_exploration/{url_record['page_file']}"
            
            return {
                'explored': True,
                'page_file': page_file,
                'page_id': url_record.get('page_id'),
                'last_explored_at': url_record['last_explored_at'],
                'last_run_id': url_record['last_run_id']
            }
    
    return {'explored': False}
```

**循环避免策略**:
```python
class ExplorationQueue:
    def __init__(self, project_id):
        self.project_id = project_id
        self.queue = deque()
        self.explored_in_this_run = set()  # 本次run中已探索的URL
    
    def add_url(self, url):
        normalized = normalize_url(url)
        
        # 本次run中已探索过，跳过（避免循环）
        if normalized in self.explored_in_this_run:
            return False
        
        self.queue.append(url)
        return True
    
    def mark_explored(self, url):
        normalized = normalize_url(url)
        self.explored_in_this_run.add(normalized)
        
        # 同时更新项目级 explored_urls.yaml
        update_explored_urls(self.project_id, normalized)
```

### 3.4 产物Schema

#### explored_urls.yaml（项目级已探索URL列表）

```yaml
version: "1.0"
project_id: "proj-123"

urls:
  - normalized_path: "/workspace/agents"
    page_id: "page-workspace-agents"
    page_file: "pages/page-workspace-agents.yaml"
    last_explored_at: "2026-06-26T11:00:00Z"
    last_run_id: "run-001"
  
  - normalized_path: "/workspace/settings"
    page_id: "page-workspace-settings"
    page_file: "pages/page-workspace-settings.yaml"
    last_explored_at: "2026-06-26T11:05:00Z"
    last_run_id: "run-001"
```

#### discovered_pages.yaml（本次探索发现的页面清单）

```yaml
run_id: "run-001"
discovered_at: "2026-06-26T11:00:00Z"

pages:
  - page_id: "page-workspace-agents"
    page_file: "../../pages/page-workspace-agents.yaml"
    normalized_path: "/workspace/agents"
    status: "new"  # new=首次探索, updated=更新已有产物
    elements_count: 15
    exploration_status: "completed"
```

#### pages/page-*.yaml（项目级页面产物）

```yaml
page:
  id: "page-001"
  title: "智能体工作台"
  normalized_path: "/workspace/agents"
  explored_at: "2026-06-26T11:00:00Z"
  
  # 页面元素定位器
  elements:
    - id: "create_agent_btn"
      name: "创建智能体"
      role: "button"
      
      locators:
        - kind: "role"
          code: "getByRole('button', { name: '创建智能体' })"
          priority: 1
          validation:
            is_unique: true
            is_visible: true
```

### 3.5 上下文管理策略

**问题**: Agent 探索多个页面时会积累大量历史消息，导致 token 消耗增加和响应变慢

**方案**: 使用 LangChain SummarizationMiddleware 自动管理上下文

#### 配置示例

```python
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware

agent = create_agent(
    model="gpt-5.5",
    tools=[
        playwright_snapshot_tool,
        playwright_click_tool,
        playwright_fill_tool,
        cache_lookup_tool,
        artifact_write_tool,
    ],
    middleware=[
        SummarizationMiddleware(
            model="gpt-5.4-mini",  # 使用便宜模型进行总结
            trigger=("tokens", 4000),  # 超过 4000 tokens 触发总结
            keep=("messages", 20),  # 保留最近 20 条消息
        ),
    ],
)
```

#### 工作原理

```
Turn 1-15: 历史 < 4000 tokens
  → 不触发总结，正常运行

Turn 20: 历史达到 4200 tokens
  → 自动触发总结：
    - 保留最近 20 条完整消息
    - 总结更早的历史消息
    - 新历史 = [总结] + [最近 20 条]
    - 压缩后约 2000 tokens

Turn 21+: 继续探索...
```

#### 效果对比（50 个页面）

| 方案 | 平均上下文 | 响应时间 | 成本估算 |
|------|----------|---------|---------|
| 无管理 | ~150k tokens | 10秒 | $3.00 |
| SummarizationMiddleware | < 10k tokens | 3秒 | $0.80 |

#### 配置建议

```yaml
# config/exploration.yaml
context_management:
  middleware:
    enabled: true
    summary_model: "gpt-5.4-mini"  # 总结用的便宜模型
    trigger_tokens: 4000  # 触发阈值
    keep_messages: 20  # 保留消息数
```

---

## 4. Skills设计

### 4.1 推荐方案

采用 **2个核心skills** 的方案：

1. **page_explorer** - 探索策略和页面分析
2. **locator_best_practices** - 定位器选择最佳实践

**不包括**：
- ❌ cache_strategy - 缓存是纯编程逻辑，由CacheManager处理

### 4.2 Skill 1: page_explorer

**路径**: `apps/backend/app/agents/page_exploration/skills/page_explorer/SKILL.md`

**职责**：指导Agent如何智能探索网站

**核心内容**：
- **探索策略**: 广度优先（推荐）vs 深度优先
- **页面类型识别**: Dashboard/List/Detail/Form/Modal，每种类型有专门的探索策略
- **导航元素识别**: 主导航（优先级最高）> 侧边栏 > 页面内链接
- **探索深度控制**: 默认 3 层，防止无限探索
- **循环检测**: 避免双向链接、分页链接、无限滚动
- **危险操作避免**: 永远不点击删除、支付、登出按钮
- **探索决策流程**: 7 步判断是否应该探索某个链接

**核心规则示例**：
```
优先探索顺序:
1. 主导航链接（depth=1）
2. 侧边栏导航（depth=2）
3. "创建"、"新建" 按钮
4. 列表页点击第一条记录
5. 表单页记录字段但不提交

避免探索:
- 删除、支付、登出按钮
- 分页和"加载更多"
- 已探索的页面（缓存检查）
```

### 4.3 Skill 2: locator_best_practices

**路径**: `apps/backend/app/agents/page_exploration/skills/locator_best_practices/SKILL.md`

**职责**：指导如何选择最佳定位器

**核心内容**：
- **定位器优先级**: getByRole > getByLabel > getByTestId > getByText > getByPlaceholder > CSS
- **禁止使用**: ref（临时引用，每次变化）
- **唯一性验证**: count() === 1
- **定位器决策树**: 按优先级逐层判断
- **常见场景示例**: 导航菜单、表单提交、对话框、表格、搜索
- **红旗警告**: 包含数字索引、动态类名、过长、过于宽泛

**核心规则示例**：
```
定位器选择流程:
1. 是按钮/链接/输入框？ → getByRole
2. 是表单字段？ → getByLabel
3. 有 data-testid？ → getByTestId
4. 有唯一且稳定的文本？ → getByText
5. 是输入框且有 placeholder？ → getByPlaceholder
6. 以上都不适用？ → CSS 选择器（最后选择）

永远不用:
- ❌ ref=e15（临时引用）
- ❌ .css-abc123（动态类名）
- ❌ button:nth-child(3)（索引依赖）
```

---

## 5. 探索流程和终止逻辑

### 5.1 探索流程

```
1. 启动探索任务
   ↓
2. 加载项目级已探索URL列表 (explored_urls.yaml)
   ↓
3. Agent 探索循环：
   a. 从队列取出URL
   b. 归一化URL
   c. 检查是否在本次run中已探索（避免循环）
      - 如果是 → 跳过
      - 如果否 → 继续
   
   d. 访问页面，获取快照
   e. 识别操作场景（导航/表单/搜索）
   f. 为元素生成语义定位器
   g. 执行操作并验证定位器（错误驱动验证）：
      
      【策略】直接执行操作，失败时优化定位器，而非预验证
      
      【导航场景】
      - 尝试点击链接/按钮
      - 成功 → 记录定位器（已隐式验证唯一性和可见性）
      - 失败 → 根据错误类型优化定位器：
        * 定位器不唯一 → 添加更多限定条件
        * 元素不可见 → 尝试滚动后重试
        * 元素未找到 → 等待加载后重试
      
      【表单场景】
      - 批量填写所有字段
      - 失败字段单独优化定位器
      - 成功字段记录定位器
      
      【搜索场景】
      - 输入搜索词 + 点击搜索按钮
      - 批量执行，失败时单独优化
   
   h. 关键点获取快照
   i. 提取页面链接，加入队列
   j. 写入/更新项目级pages产物
      - 如果页面已存在 → 覆盖更新
      - 如果页面不存在 → 创建新产物
   k. 更新 explored_urls.yaml（记录本次探索）
   l. 标记为本次run已探索
   m. 记录到discovered_pages.yaml
   n. 判断是否继续
   ↓
4. 生成本次run的探索报告
   ↓
5. 更新任务状态
```

### 5.2 终止条件

满足任一即停止：

#### 1. 目标达成终止
```python
if exploration_queue.is_empty():
    stop_reason = "all_pages_explored"
    terminate()
```

#### 2. 达到限制终止
- 页面数量达到上限
- 探索时间达到上限
- 探索深度达到上限

#### 3. 错误终止
- 连续失败次数过多
- Agent无法继续

#### 4. 手动终止
- 用户主动停止

### 5.3 URL队列管理

```python
class ExplorationQueue:
    def __init__(self, start_url, scope):
        self.queue = deque([start_url])
        self.explored = set()
        self.scope = scope
    
    def add_url(self, url):
        normalized = normalize_url(url)
        
        if normalized in self.explored:
            return False
        
        if not self._in_scope(url):
            return False
        
        if url in self.queue:
            return False
        
        self.queue.append(url)
        return True
    
    def pop(self):
        if self.is_empty():
            return None
        return self.queue.popleft()
    
    def mark_explored(self, url):
        normalized = normalize_url(url)
        self.explored.add(normalized)
```

### 5.4 循环检测

**场景A: 双向链接**
```
Page A → Page B
Page B → Page A
```
**解决**: 使用explored set

**场景B: 同一页面多个URL**
```
/workspace/agents
/workspace/agents?tab=all
/workspace/agents#section1
```
**解决**: URL归一化（去除query和fragment）

**场景C: 分页链接**
```
/agents?page=1
/agents?page=2
...
```
**解决**: 限制同一路径的探索次数

---

## 6. 错误处理策略

### 6.1 核心原则

1. **分类处理** - 不同类型的错误用不同策略
2. **快速失败** - 不可恢复的错误立即停止
3. **智能重试** - 可恢复的错误自动重试
4. **记录详细** - 所有错误都要记录

### 6.2 错误分类和处理

#### 定位器错误

| 错误类型 | 重试次数 | 处理策略 |
|---------|---------|---------|
| 定位器不唯一 | 0 | Agent优化定位器 |
| 元素未找到 | 1 | 等待2秒后重试 |
| 元素不可见 | 1 | 滚动后重试 |

#### 页面加载错误

| 错误类型 | 重试次数 | 处理策略 |
|---------|---------|---------|
| 页面加载超时 | 2 | 等待3秒后重试 |
| 404错误 | 0 | 不重试 |
| 500错误 | 1 | 等待5秒后重试 |

#### Agent错误

| 错误类型 | 重试次数 | 处理策略 |
|---------|---------|---------|
| Agent决策失败 | 3 | LLM可能临时故障 |
| Token超限 | 1 | 简化快照后重试 |

#### 网络错误

| 错误类型 | 重试次数 | 处理策略 |
|---------|---------|---------|
| 连接超时 | 3 | 等待5秒后重试 |
| 连接中断 | 2 | 等待3秒后重试 |

#### Playwright CLI错误

| 错误类型 | 重试次数 | 处理策略 |
|---------|---------|---------|
| Playwright崩溃 | 1 | 重启进程后重试 |

### 6.3 致命错误（立即终止）

以下错误不重试，直接终止：
1. 认证失败 - Session过期
2. 权限不足 - 403 Forbidden
3. Playwright无法启动 - 环境问题
4. 配置错误 - 探索配置无效

### 6.4 错误处理流程

```python
class ErrorHandler:
    def __init__(self):
        self.consecutive_failures = 0
        self.total_failures = 0
        self.max_consecutive = 3
        self.max_total = 10
    
    def handle_error(self, error, context):
        # 1. 记录错误
        self.log_error(error, context)
        
        # 2. 增加计数
        self.total_failures += 1
        self.consecutive_failures += 1
        
        # 3. 检查是否应该终止
        if self.should_terminate():
            raise ExplorationFailedError("错误过多，终止探索")
        
        # 4. 分类处理
        error_type = self.classify_error(error)
        strategy = self.get_strategy(error_type)
        
        # 5. 执行策略
        result = strategy.handle(error, context)
        
        # 6. 如果成功，重置连续失败计数
        if result['status'] == 'success':
            self.consecutive_failures = 0
        
        return result
```

---

## 7. 前端页面管理界面

### 7.1 设计理念

**核心目标**:
- 让用户可视化查看所有已探索的页面
- 支持手动重新探索指定页面（覆盖更新产物）
- 类似公司知识库的文件树展示方式
- 提供详细的元素和定位器查看功能

### 7.2 页面树展示

#### 界面布局

```
┌─────────────────────────────────────────────────────────┐
│  页面探索管理                              🔄 刷新列表  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  📁 智能体工作台 (/workspace)                            │
│    ├─ 📄 智能体列表                    [查看] [重新探索]│
│    │   /workspace/agents                                │
│    │   最后探索: 2026-06-26 11:00                       │
│    │   元素数量: 15 个                                   │
│    │                                                    │
│    ├─ 📄 创建智能体                    [查看] [重新探索]│
│    │   /workspace/agents/create                        │
│    │   最后探索: 2026-06-26 11:05                       │
│    │   元素数量: 8 个                                    │
│    │                                                    │
│    └─ 📄 智能体设置                    [查看] [重新探索]│
│        /workspace/agents/settings                       │
│        最后探索: 2026-06-26 11:10                       │
│        元素数量: 12 个                                   │
│                                                          │
│  📁 知识库 (/knowledge)                                  │
│    ├─ 📄 知识库列表                    [查看] [重新探索]│
│    │   /knowledge/list                                 │
│    │   最后探索: 2026-06-26 11:15                       │
│    │   元素数量: 20 个                                   │
│    │                                                    │
│    └─ 📄 创建知识库                    [查看] [重新探索]│
│        /knowledge/create                                │
│        最后探索: 2026-06-26 11:20                       │
│        元素数量: 6 个                                    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

#### 数据结构

```typescript
interface PageTree {
  id: string;
  name: string;              // "智能体工作台"
  type: 'folder' | 'page';
  path: string;              // "/workspace"
  children?: PageTree[];
  
  // 页面特有字段
  pageId?: string;
  lastExploredAt?: string;
  elementCount?: number;
}
```

#### 功能说明

**展示**:
- 按路径自动分组为文件夹结构
- 显示每个页面的基本信息
- 支持展开/折叠文件夹

**操作**:
- **查看**: 跳转到页面详情页
- **重新探索**: 触发重新探索该页面（覆盖更新产物）

### 7.3 页面详情查看

#### 界面布局

```
┌─────────────────────────────────────────────────────────┐
│  ← 返回列表          智能体列表页面详情          [更新] │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  📊 基本信息                                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 页面标题: 智能体工作台                            │  │
│  │ 路径: /workspace/agents                          │  │
│  │ 最后探索: 2026-06-26 11:00:00                    │  │
│  │ 探索 Run: run-001                                │  │
│  │ 总元素数: 15 个                                   │  │
│  │ 可交互元素: 8 个                                  │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  🔍 页面元素 (15)                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 🔘 创建智能体 (button)                            │  │
│  │ └─ getByRole('button', { name: '创建智能体' })   │  │
│  │    ✅ 唯一性: 通过 | ✅ 可见性: 通过               │  │
│  │                                                    │  │
│  │ 🔍 搜索智能体 (textbox)                           │  │
│  │ └─ getByLabel('搜索智能体')                      │  │
│  │    ✅ 唯一性: 通过 | ✅ 可见性: 通过               │  │
│  │                                                    │  │
│  │ 🔗 智能体详情链接 (link)                          │  │
│  │ └─ getByRole('link', { name: '查看详情' })       │  │
│  │    ✅ 唯一性: 通过 | ✅ 可见性: 通过               │  │
│  │                                                    │  │
│  │ ... (展开查看更多元素)                             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  📸 页面截图                                             │
│  [图片预览]                                              │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

#### 展示内容

**基本信息**:
- 页面标题
- 归一化路径
- 最后探索时间
- 探索 Run ID
- 元素统计信息

**页面元素列表**:
- 元素名称和角色
- 所有定位器（按优先级排序）
- 验证状态（唯一性、可见性）
- 支持展开/折叠

**页面截图**:
- 探索时保存的页面截图
- 帮助用户直观了解页面

### 7.4 页面重新探索功能

#### 单个页面重新探索

**触发**: 点击页面的"重新探索"按钮

**确认对话框**:
```
┌─────────────────────────────────────┐
│  确认重新探索                        │
├─────────────────────────────────────┤
│                                      │
│  页面: 智能体列表                    │
│  路径: /workspace/agents            │
│                                      │
│  上次探索: 2026-06-26 11:00         │
│  (1 天前)                            │
│                                      │
│  重新探索将：                        │
│  • 重新分析页面结构                  │
│  • 更新元素定位器                    │
│  • 覆盖现有产物                      │
│                                      │
│  预计耗时: 30-60 秒                  │
│                                      │
│  [取消]            [确认重新探索]   │
└─────────────────────────────────────┘
```

**探索进度**:
```
┌─────────────────────────────────────┐
│  正在探索...                         │
├─────────────────────────────────────┤
│                                      │
│  智能体列表 (/workspace/agents)     │
│                                      │
│  ✅ 访问页面                        │
│  ✅ 获取页面快照                    │
│  ⏳ 识别元素...                     │
│  ⏸ 生成定位器                       │
│                                      │
│  进度: 45%                           │
│                                      │
└─────────────────────────────────────┘
```

**完成提示**:
```
┌─────────────────────────────────────┐
│  ✅ 探索完成                        │
├─────────────────────────────────────┤
│                                      │
│  智能体列表已更新                    │
│                                      │
│  发现 16 个元素 (新增 1 个)         │
│  更新时间: 2026-06-27 10:30         │
│                                      │
│  [关闭]            [查看详情]       │
└─────────────────────────────────────┘
```

#### 批量重新探索

**触发**: 选择多个页面后点击"批量重新探索"

**进度展示**:
- 显示总进度（如 "2/5 已完成"）
- 显示当前正在探索的页面
- 显示每个页面的完成状态

### 7.5 API 设计

#### API 1: 获取页面树

```http
GET /api/projects/{project_id}/page_exploration/pages/tree

Response:
{
  "tree": [
    {
      "id": "workspace",
      "name": "智能体工作台",
      "type": "folder",
      "path": "/workspace",
      "children": [
        {
          "id": "workspace-agents",
          "name": "智能体列表",
          "type": "page",
          "path": "/workspace/agents",
          "pageId": "page-workspace-agents",
          "lastExploredAt": "2026-06-26T11:00:00Z",
          "elementCount": 15
        }
      ]
    }
  ]
}
```

#### API 2: 获取页面详情

```http
GET /api/projects/{project_id}/page_exploration/pages/{page_id}

Response:
{
  "page": {
    "id": "page-workspace-agents",
    "title": "智能体工作台",
    "path": "/workspace/agents",
    "lastExploredAt": "2026-06-26T11:00:00Z",
    "runId": "run-001",
    "elementCount": 15,
    "interactiveElementCount": 8,
    "screenshotUrl": "/screenshots/page-workspace-agents.png",
    "elements": [
      {
        "id": "create_agent_btn",
        "name": "创建智能体",
        "role": "button",
        "locators": [
          {
            "kind": "role",
            "code": "getByRole('button', { name: '创建智能体' })",
            "priority": 1,
            "validation": {
              "is_unique": true,
              "is_visible": true,
              "match_count": 1
            }
          }
        ]
      }
    ]
  }
}
```

#### API 3: 重新探索指定页面

```http
POST /api/projects/{project_id}/page_exploration/pages/{page_id}/re-explore

Body:
{
  "environment": "test"  // 可选：指定环境
}

Response:
{
  "taskId": "explore-task-001",
  "status": "running",
  "message": "正在重新探索页面..."
}

// SSE 实时推送进度
SSE /api/projects/{project_id}/page_exploration/tasks/{task_id}/events

Event data:
{
  "type": "progress",
  "step": "identifying_elements",
  "progress": 0.45,
  "message": "正在识别元素..."
}
```

#### API 4: 批量重新探索

```http
POST /api/projects/{project_id}/page_exploration/pages/batch-re-explore

Body:
{
  "pageIds": ["page-workspace-agents", "page-knowledge-list"],
  "environment": "test"
}

Response:
{
  "taskId": "explore-task-002",
  "status": "running",
  "pageCount": 2
}
```

#### API 5: 删除页面记录

**说明**: 从 explored_urls.yaml 删除记录，保留页面产物供查看

```http
DELETE /api/projects/{project_id}/page_exploration/pages/{page_id}

Response:
{
  "success": true,
  "message": "页面记录已删除",
  "page_id": "page-workspace-agents",
  "details": {
    "url_record_deleted": true,
    "page_artifact_preserved": true
  }
}
```

**批量删除**:
```http
DELETE /api/projects/{project_id}/page_exploration/pages

Body:
{
  "pageIds": ["page-workspace-agents", "page-knowledge-list"]
}

Response:
{
  "success": true,
  "message": "已删除 2 个页面记录",
  "deletedCount": 2
}
```

### 7.6 前端组件设计

#### 组件 1: PageExplorationManager（页面管理主页）

```tsx
const PageExplorationManager: React.FC = () => {
  const [tree, setTree] = useState<PageTree[]>([]);
  const [loading, setLoading] = useState(false);
  
  const fetchPageTree = async () => {
    setLoading(true);
    const data = await api.getPageTree(projectId);
    setTree(data.tree);
    setLoading(false);
  };
  
  useEffect(() => {
    fetchPageTree();
  }, []);
  
  return (
    <div className="page-exploration-manager">
      <div className="header">
        <h2>页面探索管理</h2>
        <Button icon={<ReloadOutlined />} onClick={fetchPageTree}>
          刷新列表
        </Button>
      </div>
      <PageTree 
        data={tree} 
        onRefresh={fetchPageTree}
      />
    </div>
  );
};
```

#### 组件 2: PageTree（文件树）

```tsx
const PageTree: React.FC<{
  data: PageTree[];
  onRefresh: () => void;
}> = ({ data, onRefresh }) => {
  const navigate = useNavigate();
  
  const handleView = (pageId: string) => {
    navigate(`/page-detail/${pageId}`);
  };
  
  const handleReExplore = async (pageId: string) => {
    const confirmed = await showConfirm({
      title: '确认重新探索',
      content: '重新探索将覆盖现有页面产物'
    });
    if (confirmed) {
      await api.reExplorePage(pageId);
      message.success('页面重新探索已启动');
      onRefresh();
    }
  };
  
  return (
    <Tree
      treeData={data}
      titleRender={(node) => (
        <div className="tree-node">
          <span className="name">{node.name}</span>
          {node.type === 'page' && (
            <div className="meta">
              <span className="path">{node.path}</span>
              <span className="time">{formatTime(node.lastExploredAt)}</span>
              <span className="count">{node.elementCount} 个元素</span>
            </div>
          )}
          {node.type === 'page' && (
            <div className="actions">
              <Button size="small" onClick={() => handleView(node.pageId)}>
                查看
              </Button>
              <Button size="small" onClick={() => handleReExplore(node.pageId)}>
                重新探索
              </Button>
            </div>
          )}
        </div>
      )}
    />
  );
};
```

#### 组件 3: PageDetail（详情页）

```tsx
const PageDetail: React.FC = () => {
  const { pageId } = useParams();
  const [page, setPage] = useState<PageDetail | null>(null);
  
  useEffect(() => {
    api.getPageDetail(pageId).then(setPage);
  }, [pageId]);
  
  if (!page) return <Spin />;
  
  const handleReExplore = async () => {
    const confirmed = await showConfirm({
      title: '确认重新探索',
      content: '重新探索将覆盖现有页面产物'
    });
    if (confirmed) {
      await api.reExplorePage(pageId);
      message.success('页面重新探索已启动');
    }
  };
  
  return (
    <div className="page-detail">
      <PageHeader
        onBack={() => navigate(-1)}
        title="页面详情"
        extra={[
          <Button key="re-explore" onClick={handleReExplore}>
            重新探索此页面
          </Button>
        ]}
      />
      
      <Card title="基本信息">
        <Descriptions column={2}>
          <Descriptions.Item label="页面标题">{page.title}</Descriptions.Item>
          <Descriptions.Item label="路径">{page.path}</Descriptions.Item>
          <Descriptions.Item label="最后探索">{page.lastExploredAt}</Descriptions.Item>
          <Descriptions.Item label="探索 Run">{page.runId}</Descriptions.Item>
          <Descriptions.Item label="总元素数">{page.elementCount}</Descriptions.Item>
          <Descriptions.Item label="可交互元素">{page.interactiveElementCount}</Descriptions.Item>
        </Descriptions>
      </Card>
      
      <Card title="页面元素" style={{ marginTop: 16 }}>
        <Collapse>
          {page.elements.map((element) => (
            <Panel
              key={element.id}
              header={
                <Space>
                  <Tag color="blue">{element.role}</Tag>
                  <span>{element.name}</span>
                </Space>
              }
            >
              <div className="element-detail">
                <h4>定位器</h4>
                {element.locators.map((locator, idx) => (
                  <div key={idx} className="locator">
                    <code>{locator.code}</code>
                    <Space style={{ marginLeft: 16 }}>
                      {locator.validation.is_unique && (
                        <Tag color="success">✅ 唯一</Tag>
                      )}
                      {locator.validation.is_visible && (
                        <Tag color="success">✅ 可见</Tag>
                      )}
                    </Space>
                  </div>
                ))}
              </div>
            </Panel>
          ))}
        </Collapse>
      </Card>
      
      <Card title="页面截图" style={{ marginTop: 16 }}>
        <Image src={page.screenshotUrl} />
      </Card>
    </div>
  );
};
```

### 7.7 实施要点

**后端**:
- 实现页面树构建逻辑（按路径分组）
- 实现单页面和批量重新探索接口
- 实现 SSE 进度推送
- 支持截图保存和访问
- 管理 explored_urls.yaml

**前端**:
- 参考公司知识库的文件树组件
- 实现实时进度展示
- 实现页面详情查看
- 良好的加载和错误状态处理

**交互**:
- 重新探索前需要用户确认
- 探索过程实时反馈进度
- 探索完成后自动更新列表
- 支持批量操作

---

## 8. 实施计划

### 8.1 已完成（30%）

- [x] 架构设计 100%
- [x] Skills设计 100%
- [x] 基础设施 80%（URLNormalizer, LocatorValidator, PlaywrightCLIWrapper, Schemas）
- [x] ProjectPagesService（项目级pages管理）

### 8.2 实施阶段

#### 阶段1: Agent核心实现（优先级 P0）
**预计时间**: 3-4天

- [ ] Agent定义（agent.py）
- [ ] Agent Tools（playwright_tools.py, explored_urls_tools.py, artifact_tools.py）
- [ ] Prompts（system_prompt.py, exploration_prompt.py）

#### 阶段2: 探索服务实现（优先级 P0）
**预计时间**: 3-4天

- [ ] 探索编排器（orchestrator.py）
- [ ] 产物服务（artifact_service.py）

#### 阶段3: SSE进度传输（优先级 P1）
**预计时间**: 2-3天

- [ ] 事件发射器（event_emitter.py）
- [ ] 数据库模型（ExplorationRun, ExplorationEventLog）
- [ ] API路由（page_exploration.py）

#### 阶段4: 前端集成（优先级 P1）
**预计时间**: 3-4天

- [ ] SSE Hook（useExplorationStream.ts）
- [ ] 进度展示组件（ExplorationProgressPanel.tsx）
- [ ] 探索任务表单（CreateExplorationForm.tsx）
- [ ] 页面管理界面（PageExplorationManager.tsx）
- [ ] 页面树组件（PageTree.tsx）
- [ ] 页面详情页（PageDetail.tsx）

#### 阶段5: 测试（优先级 P1）
**预计时间**: 4天

- [ ] 单元测试
- [ ] 集成测试
- [ ] E2E测试

#### 阶段6: 依赖和环境（优先级 P0）
**预计时间**: 0.5天

- [ ] 安装playwright-cli
- [ ] 验证playwright-cli可用
- [ ] 安装Python依赖

### 8.3 时间表

- **第1周（5天）**: Agent核心 + 探索服务
- **第2周（5天）**: SSE进度 + 前端集成 + 单元测试
- **第3周（3天）**: 集成测试 + E2E测试 + 文档完善

**总计**: 约13个工作日

### 8.4 里程碑

- **Milestone 1**: Agent核心完成（第1周结束）
- **Milestone 2**: 完整流程打通（第2周结束）
- **Milestone 3**: 生产就绪（第3周结束）

---

## 9. 验收标准

### 9.1 功能验收

- [ ] 能创建探索任务并指定范围、目标、禁止路径
- [ ] 探索过程中使用语义定位器（无ref）
- [ ] 定位器失败时自动更换其他定位器
- [ ] 生成符合Schema的页面产物YAML
- [ ] explored_urls.yaml 正确记录已探索URL
- [ ] 重复探索会覆盖更新产物
- [ ] 跨环境URL归一化正确
- [ ] 生成探索图谱和报告
- [ ] SSE实时推送探索进度
- [ ] 页面刷新后能恢复历史进度
- [ ] 前端能查看探索结果和产物

### 9.2 性能验收

- [ ] 单页探索时间 < 1分钟
- [ ] SSE事件延迟 < 1秒
- [ ] 循环检测正确（避免无限探索）

### 9.3 质量验收

- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试全部通过
- [ ] E2E测试全部通过
- [ ] 元素定位器覆盖率 > 95%

---

## 10. 关键技术决策

### 10.1 为什么不使用ref？
- ref是playwright-cli快照时生成的临时引用（e15, e20等）
- ref在下次快照时会变化，不能在测试用例中复用
- 语义定位器稳定且可读性强，适合测试用例

### 10.2 为什么采用项目级pages？
- 一次探索，所有run共享
- 跨环境复用（测试/生产/本地）
- 维护成本低，页面更新只需更新一个文件
- 重复探索会覆盖更新，保持产物最新

### 10.3 为什么不使用缓存？

**设计变更**: v1.4 移除了缓存机制

**原因**:
- 缓存会导致页面无法重新探索
- 页面经常变化，需要频繁更新产物
- 简化架构，降低复杂度

**替代方案**:
- 使用 `explored_urls.yaml` 记录已探索URL
- 仅用于避免同一次探索的无限循环
- 不阻止重复探索，每次都覆盖更新产物

**循环避免**:
```python
# 本次run中已探索的URL（内存）
explored_in_this_run = set()

# 项目级已探索URL（持久化）
explored_urls.yaml  # 仅供查看，不阻止重复探索
```
---

## 附录

### A. 参考资料

- DeepAgents文档
- Playwright CLI文档
- LangChain 中间件文档
- SSE规范
- 项目架构设计

### B. Skills 文件

- **page_explorer**: `apps/backend/app/agents/page_exploration/skills/page_explorer/SKILL.md`
- **locator_best_practices**: `apps/backend/app/agents/page_exploration/skills/locator_best_practices/SKILL.md`

### C. 未来扩展

- 支持登录流程自动化
- 支持验证码识别
- 支持动态内容等待策略
- 支持多浏览器并行探索
- 与测试用例生成模块集成

---

## 更新日志

### v1.4 (2026-06-27 深夜) 🔥

**重大设计变更**: 移除缓存机制

**核心变更**:
- ✅ 移除缓存机制（cache_index.yaml）
- ✅ 新增 explored_urls.yaml（仅记录已探索URL，不阻止重复探索）
- ✅ 重复探索会覆盖更新页面产物
- ✅ 简化循环检测（仅在当次run中生效）

**文件变更**:
- ❌ 删除 cache_index.yaml
- ✅ 新增 explored_urls.yaml
- ❌ 删除 links_discovered 字段（不需要了）
- ✅ 简化 discovered_pages.yaml（status: new/updated）

**架构简化**:
- 第 3.3 节：缓存检查逻辑 → 已探索URL检查逻辑
- 第 5.1 节：探索流程大幅简化（移除缓存命中分支）
- 第 7 节：缓存管理界面 → 页面管理界面
- 第 10.3 节：新增"为什么不使用缓存"

**API变更**:
- `GET /page_exploration/cache/tree` → `GET /page_exploration/pages/tree`
- `POST /cache/pages/{id}/refresh` → `POST /pages/{id}/re-explore`
- `DELETE /cache/pages/{id}` → `DELETE /pages/{id}`（删除记录，保留产物）

**核心原则**:
- ✅ 每次探索都重新访问页面
- ✅ 重复探索会覆盖更新产物
- ✅ explored_urls.yaml 仅用于循环检测，不阻止重复探索

### v1.3 (2026-06-27 晚上) ✨

**核心修复**:
- ✅ 补充 `links_discovered` 字段（3.4 产物Schema）
- ✅ 更新探索流程（5.1）
- ✅ 更新缓存检查逻辑（3.3）
- ✅ 明确URL归一化实现（3.1）

**核心原则确认**:
- ✅ 有缓存就不探索，有探索就不用缓存
- ✅ 删除缓存才重新探索，保留页面产物
- ✅ 错误驱动验证是可行的（失败时页面未跳转）

**优化**:
- ✅ 简化产物Schema（删除 states 层级）
- ✅ 明确清除缓存的范围（API 5）

### v1.2 (2026-06-27 下午)

**新增**:
- ✅ 第 7 节：前端缓存管理界面设计

**简化**:
- ✅ 简化缓存失效策略（第 9.3 节）

**优化**:
- ✅ 删除 cache_index.yaml 中的 signature 字段
- ✅ 前端实施阶段增加缓存管理相关组件

### v1.1 (2026-06-27 上午)

**新增**:
- ✅ 补充第 3.5 节：上下文管理策略（使用 LangChain SummarizationMiddleware）
- ✅ 创建 2 个实际的 Skills 文件（page_explorer 和 locator_best_practices）
- ✅ 明确定位器验证策略：错误驱动验证，而非预验证
- ✅ 细化缓存失效策略：具体说明 30% 阈值和失效后行为

**修复**:
- ✅ 删除 env_urls 相关内容（确认无需存储）
- ✅ 更新 cache_index.yaml 示例，移除 env_urls 字段
- ✅ 更新探索流程第 g 步，明确各场景的验证方式

**优化**:
- ✅ Skills 章节补充实际文件路径和核心规则示例
- ✅ 上下文管理配置更新为最新的 LangChain API

### v1.0 (2026-06-26)

- 初始版本，整合 6 个独立 spec 文档

---

**文档版本**: 1.4  
**最后更新**: 2026-06-27  
**状态**: ✅ 设计完成，逻辑简化，可以开始实施
