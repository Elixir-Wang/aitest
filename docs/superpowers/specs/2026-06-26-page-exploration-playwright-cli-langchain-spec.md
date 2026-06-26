# 页面探索 Playwright CLI + LangChain 架构设计

## 1. 背景与目标

### 背景
当前项目需要实现基于 Playwright CLI 和 LangChain 的页面元素探索功能，用于：
- 探索项目页面结构和交互元素
- 生成可复用的页面元素定位器快照
- 为后续自动化测试用例生成提供准确的元素定位信息

### 核心需求
1. 根据探索范围、探索目标、禁止路径进行智能探索
2. 使用语义化定位器（getByRole/getByText/getByLabel/getByTestId），避免不可复用的ref或CSS选择器
3. 探索过程中验证定位器的唯一性和可用性
4. 生成 playwright 探索快照（YAML格式）
5. 支持探索缓存，避免重复探索同一页面
6. 跨环境URL归一化（测试环境和生产环境URL不同但路径相同）

### 非目标
- 不在本阶段实现测试用例生成
- 不在本阶段实现自动化测试执行
- 不使用 ref 定位器（因为不能复用）

## 2. 整体架构

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

## 3. 目录结构

```
apps/backend/
├── app/
│   ├── agents/
│   │   └── page_exploration/              # 新模块（独立）
│   │       ├── __init__.py
│   │       ├── agent.py                   # LangChain Agent 定义
│   │       ├── service.py                 # 探索服务
│   │       ├── schemas.py                 # 数据模型
│   │       ├── skills/                    # Agent Skills
│   │       │   ├── page_explorer/        # 探索策略
│   │       │   └── locator_best_practices/  # 定位器最佳实践
│   │       ├── tools/                     # Agent Tools
│   │       │   ├── __init__.py
│   │       │   ├── playwright_tools.py    # Playwright CLI 工具
│   │       │   ├── cache_tools.py         # 缓存工具
│   │       │   └── artifact_tools.py      # 产物工具
│   │       ├── prompts/                   # Agent Prompts
│   │       │   ├── __init__.py
│   │       │   ├── system_prompt.py
│   │       │   └── exploration_prompt.py
│   │       └── utils/                     # 工具函数
│   │           ├── __init__.py
│   │           ├── url_normalizer.py      # URL归一化
│   │           ├── locator_validator.py   # 定位器验证
│   │           └── playwright_wrapper.py  # Playwright CLI 包装
│   │
│   ├── services/
│   │   └── page_exploration/
│   │       ├── __init__.py
│   │       ├── orchestrator.py            # 探索编排器
│   │       ├── artifact_service.py        # 产物服务
│   │       ├── cache_manager.py           # 缓存管理器（纯编程逻辑）
│   │       └── project_pages_service.py   # 项目级pages服务
│   │
│   └── api/
│       └── routes/
│           └── page_exploration.py         # API路由
│
├── data/
│   └── projects/
│       └── {project_id}/
│           ├── requirements/              # 需求文档（定义测试场景）
│           │   └── req-001-agent-management.md
│           │
│           └── page_exploration/
│               ├── pages/                 # ✅ 项目级pages（全局复用）
│               │   ├── page-workspace-agents.yaml
│               │   ├── page-workspace-settings.yaml
│               │   └── pages-index.yaml
│               │
│               ├── cache_index.yaml       # 项目级缓存索引
│               │
│               └── runs/                  # 探索运行历史
│                   └── {run_id}/
│                       ├── run.yaml       # 运行配置 + 统计摘要（合并）
│                       ├── discovered_pages.yaml  # 本次发现的页面（引用全局pages）
│                       ├── graph.yaml     # 页面关系图
│                       ├── screenshots/   # 截图
│                       ├── logs/
│                       │   └── run.log
│                       └── reports/
│                           └── exploration-report.md
│
└── tests/
    └── agents/
        └── page_exploration/
            ├── test_agent.py
            ├── test_tools.py
            └── test_artifact_service.py
```

## 4. 核心组件设计

### 4.1 URL归一化策略

不同环境的URL需要归一化到统一的路径标识，支持跨环境缓存复用。

**核心价值：**
- 一次探索，所有环境（测试/生产/本地）都能复用同一份pages产物
- pages产物存储在项目级目录，不随探索run变化

**关键设计点：**
- 提取路径部分作为归一化标识
- 保留环境映射关系（在pages产物的env_urls字段）
- 支持路径到完整URL的还原

### 4.2 定位器优先级

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

### 4.3 探索流程（优化后）

```
1. 启动探索任务
   ↓
2. 加载项目级缓存索引 (cache_index.yaml)
   ↓
3. Agent 探索循环：
   a. 获取当前页面快照 (playwright-cli snapshot)
   b. 归一化URL并检查缓存
   c. 如已探索 → 复用项目级pages产物，跳过该页
   d. 如未探索 → 继续探索
   e. 识别操作场景（导航/表单/搜索）
   f. 为元素生成语义定位器
   g. 根据场景执行操作：
      【导航场景】
      - 直接点击（无预验证）
      - 失败则根据错误优化定位器
      
      【表单场景】
      - 批量填写所有字段
      - 点击提交
      - 一次性完成，减少中间步骤
      
      【搜索场景】
      - 输入搜索词 + 点击搜索
      - 批量执行
   
   h. 关键点获取快照（而非每步快照）
   i. 写入/更新项目级pages产物
   j. 更新项目级缓存索引
   k. 记录到discovered_pages.yaml
   l. 判断是否继续（目标完成、超出范围、禁止路径）
   ↓
4. 生成本次run的探索报告
   ↓
5. 更新任务状态
```

**核心优化：**
- ✅ 删除预验证步骤（不再eval count/visible）
- ✅ 场景化批量操作（表单一次性填写）
- ✅ 关键点快照（不是每步都快照）
- ✅ 错误驱动优化（失败再调整定位器）
- ✅ Token节省 60-70%

### 4.4 缓存检查逻辑

```python
def check_cache(normalized_path: str, project_id: str) -> Optional[dict]:
    """
    检查页面是否已探索（项目级缓存）
    
    Args:
        normalized_path: /workspace/agents
        project_id: 项目ID
    
    Returns:
        如果已探索，返回项目级pages产物路径；否则返回None
    """
    # 加载项目级缓存索引
    cache_index_path = f"data/projects/{project_id}/page_exploration/cache_index.yaml"
    cache_index = load_yaml(cache_index_path)
    
    for page in cache_index.get('pages', []):
        if page['normalized_path'] == normalized_path:
            # 页面文件路径（项目级）
            page_file = f"data/projects/{project_id}/page_exploration/{page['page_file']}"
            
            if Path(page_file).exists():
                return {
                    'cache_hit': True,
                    'page_file': page_file,  # 项目级pages路径
                    'page_id': page['page_id'],
                    'last_explored_at': page['last_explored_at']
                }
    
    return {'cache_hit': False}
```

### 4.5 产物Schema详解

#### cache_index.yaml（项目级缓存索引）

```yaml
version: "1.0"
project_id: "proj-123"
created_at: "2026-06-26T10:00:00Z"
updated_at: "2026-06-26T12:00:00Z"

pages:
  - normalized_path: "/workspace/agents"
    page_id: "page-workspace-agents"
    path_hash: "sha256-abc123"
    
    # 页面文件路径（项目级）
    page_file: "pages/page-workspace-agents.yaml"
    
    # 最后探索信息
    last_explored_at: "2026-06-26T11:00:00Z"
    last_run_id: "run-001"
    
    # 页面签名（用于检测变化）
    signature:
      title: "智能体工作台"
      element_count: 15
      interactive_element_count: 8
    
    # 环境URL映射
    env_urls:
      prod: "https://prod.example.com/workspace/agents"
      test: "https://test.example.com/workspace/agents"
      local: "http://localhost:3000/workspace/agents"
```

#### discovered_pages.yaml（本次探索发现的页面清单）

```yaml
# data/projects/{project_id}/page_exploration/runs/{run_id}/discovered_pages.yaml

run_id: "run-001"
discovered_at: "2026-06-26T11:00:00Z"

pages:
  - page_id: "page-workspace-agents"
    page_file: "../../pages/page-workspace-agents.yaml"  # 引用项目级pages
    normalized_path: "/workspace/agents"
    cache_status: "miss"  # miss=本次新探索, hit=复用缓存
    elements_count: 15
    interactive_elements_count: 8
    exploration_status: "completed"
  
  - page_id: "page-workspace-settings"
    page_file: "../../pages/page-workspace-settings.yaml"
    normalized_path: "/workspace/settings"
    cache_status: "hit"  # 复用了之前的探索结果
    elements_count: 8
    interactive_elements_count: 5
    exploration_status: "cached"
```

#### pages/page-workspace-agents.yaml（项目级页面产物）

```yaml
page:
  id: "page-001"
  title: "智能体工作台"
  url: "https://test.example.com/workspace/agents"
  normalized_path: "/workspace/agents"
  path_hash: "sha256-abc123"
  explored_at: "2026-06-26T11:00:00Z"
  screenshot: "screenshots/page-001.png"

states:
  - id: "default"
    type: "page"
    title: "智能体工作台 - 默认状态"
    
    elements:
      - id: "create_agent_btn"
        name: "创建智能体"
        role: "button"
        element_type: "button"
        action_type: "click"
        
        locators:
          - kind: "role"
            code: "getByRole('button', { name: '创建智能体' })"
            priority: 1
            validation:
              is_unique: true
              is_visible: true
              match_count: 1
              validated_at: "2026-06-26T11:00:05Z"
          
          - kind: "testid"
            code: "getByTestId('create-agent-btn')"
            priority: 2
            validation:
              is_unique: true
              is_visible: true
              match_count: 1
              validated_at: "2026-06-26T11:00:06Z"
        
        attributes:
          aria-label: "创建智能体按钮"
          data-testid: "create-agent-btn"
          class: "ant-btn ant-btn-primary"
      
      - id: "search_input"
        name: "搜索智能体"
        role: "textbox"
        element_type: "input"
        action_type: "fill"
        
        locators:
          - kind: "label"
            code: "getByLabel('搜索智能体')"
            priority: 1
            validation:
              is_unique: true
              is_visible: true
              match_count: 1

quality:
  locator_coverage: 0.95
  unique_locator_ratio: 1.0
  needs_manual_review: false
  issues: []

metadata:
  explored_by: "langchain_agent"
  exploration_duration_seconds: 45
  interaction_count: 3
  state_count: 2
```

#### graph.yaml（页面关系图）

```yaml
nodes:
  - id: "page-001"
    title: "智能体工作台"
    normalized_path: "/workspace/agents"
    type: "page"
  
  - id: "page-002"
    title: "创建智能体"
    normalized_path: "/workspace/agents/create"
    type: "page"
  
  - id: "page-001:create_dialog"
    title: "创建智能体弹窗"
    type: "state"
    parent_page: "page-001"

edges:
  - id: "edge-001"
    from: "page-001"
    to: "page-002"
    type: "navigation"
    trigger:
      element_id: "create_agent_btn"
      action: "click"
      locator: "getByRole('button', { name: '创建智能体' })"
```

#### run.yaml（运行配置 + 统计摘要）

```yaml
# run.yaml - 探索运行的唯一真实来源（Single Source of Truth）

# 运行配置（探索开始时写入）
run:
  id: "run-001"
  project_id: "proj-123"
  environment: "test"
  created_at: "2026-06-26T10:00:00Z"
  created_by: "user-123"

# 探索范围
scope:
  start_url: "https://test.example.com/workspace"
  target: "探索工作台所有功能页面"
  include_paths:
    - "/workspace/*"
  exclude_paths:
    - "/workspace/settings/*"
    - "/workspace/billing/*"
  max_pages: 50
  max_depth: 3
  timeout_minutes: 30

# 执行状态（探索过程中更新）
execution:
  status: "completed"  # pending/running/completed/partial/failed/cancelled
  start_time: "2026-06-26T10:00:00Z"
  end_time: "2026-06-26T10:30:00Z"
  duration_seconds: 1800
  error: null

# 探索摘要（探索完成后写入）
summary:
  pages_discovered: 8
  pages_cached: 2
  cache_hit_rate: 0.25
  
  total_elements: 120
  elements_with_stable_locators: 114
  locator_coverage: 0.95
  
  states_discovered: 5
  interactions_performed: 25
  
  quality_score: 0.95
  has_issues: false
  needs_review: 0

# 产物引用
artifacts:
  discovered_pages: "discovered_pages.yaml"
  graph: "graph.yaml"
  report: "reports/exploration-report.md"
  screenshots_dir: "screenshots/"
  logs_dir: "logs/"
```

## 5. LangChain Agent 设计

### 5.1 Agent Prompt

```python
SYSTEM_PROMPT = """
你是一个专业的Web页面探索智能体，负责自动探索网站页面并生成元素定位器快照。

## 核心职责
1. 理解探索目标和范围
2. 智能决策探索路径
3. 为每个页面生成稳定的元素定位器
4. 检查缓存避免重复探索
5. 生成结构化的探索产物

## 定位器规则
- **必须使用语义定位器**：优先使用 getByRole、getByLabel、getByTestId、getByText、getByPlaceholder，尽量不要使用css定位
- **禁止使用ref定位器**：ref是临时引用，不能在测试用例中复用
- **探索时直接验证**：每次使用定位器前验证唯一性和可见性
- **优先级策略**：优先选择最稳定的定位器（role > label > testid）

## 探索策略
1. 获取页面快照
2. 归一化URL并检查缓存
3. 如果页面已探索过（缓存命中），复用缓存产物，跳过该页面
4. 如果未探索，提取可交互元素并生成定位器
5. 验证每个定位器的唯一性和可见性
6. 决策下一步：点击链接、填写表单、或记录产物
7. 更新缓存索引

## 缓存策略
- 按照归一化路径（normalized_path）判断是否已探索
- 测试环境和生产环境的相同路径视为同一页面
- 缓存命中时直接复用产物，节省时间

## 约束
- 遵守探索范围（include_paths）
- 避开禁止路径（exclude_paths）
- 不执行危险操作（删除、支付等）
- 定位器验证失败时标记需要人工review
"""

USER_PROMPT_TEMPLATE = """
## 探索任务
**目标**: {target}
**范围**: 允许 {include_paths}，禁止 {exclude_paths}

## 当前状态
**页面**: {current_url}
**进度**: 已探索 {pages_explored} 页

## 缓存状态
{cache_status_message}

请决策下一步操作。
"""

# cache_status_message 格式：
# - 缓存命中: "✓ 此页面已探索（{last_explored_at}），直接复用产物"
# - 缓存未命中: "✗ 此页面未探索，需要执行探索"

# 优化说明：
# 删除了对模型无用的字段（project_id, run_id, environment, normalized_path）
# 简化了缓存检查结果为人类可读消息
# Token 节省约 30-40%
```

### 5.2 Agent Tools 列表

```python
tools = [
    PlaywrightOpenTool(cli_wrapper),           # 打开浏览器
    PlaywrightGotoTool(cli_wrapper),           # 导航到URL
    PlaywrightSnapshotTool(cli_wrapper),       # 获取页面快照
    PlaywrightClickTool(cli_wrapper, validator), # 点击元素
    PlaywrightFillTool(cli_wrapper),           # 填写表单
    CacheLookupTool(cache_service),            # 缓存查询
    ArtifactWriteTool(artifact_service),       # 写入产物
    UpdateCacheIndexTool(cache_service),       # 更新缓存索引
]
```

## 6. 实施步骤

### 阶段1：基础设施（1-2天）
- [ ] 创建目录结构（包括项目级pages目录）
- [ ] 安装playwright-cli依赖
- [ ] 实现PlaywrightCLIWrapper
- [ ] 实现URLNormalizer
- [ ] 实现LocatorValidator
- [ ] 编写单元测试

### 阶段2：产物服务（2-3天）
- [ ] 实现项目级pages产物管理
- [ ] 实现项目级缓存索引管理
- [ ] 实现页面产物生成（写入项目级目录）
- [ ] 实现discovered_pages清单生成
- [ ] 实现探索图谱生成
- [ ] 实现探索摘要生成
- [ ] 实现探索报告生成
- [ ] 产物Schema验证

### 阶段3：Agent核心（2-3天）
- [ ] 定义Pydantic schemas
- [ ] 实现LangChain Tools（支持项目级pages操作）
- [ ] 实现Agent prompt（集成3个skills）
- [ ] 实现探索循环逻辑（项目级缓存检查）
- [ ] 编写Agent测试

### 阶段4：缓存系统（1-2天）
- [ ] 实现项目级缓存索引查询
- [ ] 实现项目级缓存更新
- [ ] 实现跨环境URL映射
- [ ] 测试缓存命中逻辑
- [ ] 测试跨环境复用

### 阶段5：API与SSE（1-2天）
- [ ] 实现探索任务CRUD API
- [ ] 实现SSE事件流（实时进度）
- [ ] 实现探索事件历史API（页面刷新恢复）
- [ ] 集成编排服务
- [ ] API测试

### 阶段6：前端集成（2-3天）
- [ ] 创建探索任务表单
- [ ] 实时进度展示（SSE连接）
- [ ] 探索结果展示（读取项目级pages）
- [ ] 缓存状态展示
- [ ] 跨环境复用提示

### 阶段7：测试用例生成集成（2-3天）
- [ ] 需求文档解析器
- [ ] 页面元素查找服务（从项目级pages查找）
- [ ] 测试代码生成器
- [ ] 测试数据生成（利用attributes验证规则）
- [ ] 端到端测试

### 阶段8：测试与优化（2-3天）
- [ ] 端到端测试
- [ ] 性能优化（项目级pages读写性能）
- [ ] 错误处理完善
- [ ] 文档补充

## 7. 关键技术决策

### 7.1 为什么不使用ref？
- ref是playwright-cli快照时生成的临时引用（e15, e20等）
- ref在下次快照时会变化，不能在测试用例中复用
- 语义定位器（getByRole等）稳定且可读性强，适合测试用例

### 7.2 如何在探索时验证定位器？
```bash
# 探索时直接使用语义定位器并点击
playwright-cli click "getByRole('button', { name: '创建智能体' })"

# 如果定位器不唯一或不可见，playwright-cli会报错
# 此时标记该元素需要人工review

# 也可以先验证再点击
playwright-cli eval "await page.locator(\"getByRole('button', { name: '创建'})\").count()"
```

### 7.3 缓存何时失效？
- 手动清除缓存
- 页面结构发生重大变化（通过element_count检测）
- 指定缓存过期时间（可选）

### 7.4 跨环境URL归一化示例
```python
# 测试环境
url = "https://test.example.com/workspace/agents"
normalized = "/workspace/agents"

# 生产环境
url = "https://prod.example.com/workspace/agents"
normalized = "/workspace/agents"  # 相同

# 本地环境
url = "http://localhost:3000/workspace/agents"
normalized = "/workspace/agents"  # 相同

# 缓存检查时使用normalized_path，因此三个环境共享缓存
```

## 8. 验收标准

- [ ] 能创建探索任务并指定范围、目标、禁止路径
- [ ] 探索过程中使用语义定位器（无ref）
- [ ] 每个定位器都经过唯一性和可见性验证
- [ ] 生成符合Schema的页面产物YAML
- [ ] 缓存系统正常工作，相同路径不重复探索
- [ ] 跨环境URL归一化正确
- [ ] 生成探索图谱和摘要
- [ ] SSE实时推送探索进度
- [ ] 前端能查看探索结果和产物

## 9. 未来扩展

- 支持登录流程自动化
- 支持验证码识别
- 支持动态内容等待策略
- 支持多浏览器并行探索
- 支持A/B测试页面探索
- 支持移动端页面探索
- 与测试用例生成模块集成
