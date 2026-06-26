# Web探索功能架构设计（基于实际项目架构）

## 1. 项目架构理解

### 1.1 技术栈
- **后端**: FastAPI + SQLAlchemy + PostgreSQL
- **智能体框架**: LangGraph + DeepAgents
- **浏览器自动化**: Playwright MCP Server
- **技能系统**: Skills (存储在`.claude/skills`目录)
- **后端系统**: 
  - `FilesystemBackend`: 文件系统访问
  - `LocalShellBackend`: 本地Shell命令执行
  - `CompositeBackend`: 组合多个后端
- **中间件**: SkillsMiddleware (按需加载技能)

### 1.2 现有Agent架构
```
backend/app/agents/
├── web_mcp/
│   └── agent.py          # Web智能体（使用Playwright MCP）
├── api/
│   └── agent.py          # API测试智能体
├── android/
│   └── agent.py          # Android测试智能体
└── security/
    └── agent.py          # 安全测试智能体
```

### 1.3 现有Skills结构
```
.claude/skills/
├── web_mcp/
│   ├── explorer/         # 页面探索
│   ├── planner/          # 测试计划生成
│   ├── generator/        # 测试代码生成
│   ├── executor/         # 测试执行
│   ├── healer/           # 测试修复
│   ├── reporter/         # 报告生成
│   ├── prerequisite/     # 前置条件分析
│   └── case-designer/    # 测试用例设计
└── web_cli/
    └── playwright-cli/   # Playwright CLI工具
```

### 1.4 现有数据库模型
- `WebFunction`: Web功能表
- `WebSubFunction`: Web子功能表
- `WebTest`: Web测试脚本表
- `WebTestRun`: Web测试运行表
- `WebTestResult`: Web测试结果表

## 2. 探索功能架构设计

### 2.1 设计目标
1. **集成到现有架构**: 复用现有的Agent、Skills、Backend系统
2. **使用Playwright MCP**: 通过MCP Server与Playwright交互
3. **存储探索快照**: 将探索结果存储为YAML快照
4. **去重机制**: 避免重复探索相同页面
5. **语义化定位器**: 优先使用`getByRole`, `getByLabel`, `getByText`, `getByTestId`

### 2.2 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Web探索功能（新增）                            │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Explorer Skill │   │  数据库扩展      │   │  Playwright MCP │
│  (新增)         │   │  (新增表)        │   │  (现有)         │
└─────────────────┘   └─────────────────┘   └─────────────────┘
        │                       │                       │
        │                       │                       │
        └───────────────────────┴───────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │   Web Agent (现有)     │
                    │   + 探索功能扩展        │
                    └───────────────────────┘
```

### 2.3 核心组件

#### 2.3.1 新增Skill: `web-page-explorer`

**位置**: `.claude/skills/web_mcp/web-page-explorer/SKILL.md`

**职责**:
- 接收探索配置（范围、目标、禁止路径）
- 使用Playwright MCP探索页面
- 生成语义化定位器
- 检查页面去重
- 保存YAML快照

**核心工具调用**:
```python
# 1. 初始化
planner_setup_page(project="chromium")

# 2. 导航
browser_navigate(url="https://example.com/login")
browser_snapshot()  # 获取页面结构

# 3. 生成定位器
locator = browser_generate_locator(description="登录按钮")

# 4. 保存快照
save_page_exploration_snapshot(
    project_identifier="proj-001",
    page_url="https://example.com/login",
    snapshot_yaml=yaml_content,
    fingerprint=page_fingerprint
)
```

#### 2.3.2 新增数据库表

**表1: `web_page_explorations` (页面探索会话表)**
```sql
CREATE TABLE web_page_explorations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    session_name VARCHAR(255),
    start_url TEXT NOT NULL,
    url_patterns JSONB,  -- 允许的URL模式
    forbidden_paths JSONB,  -- 禁止路径
    max_depth INTEGER DEFAULT 3,
    max_pages INTEGER DEFAULT 100,
    status VARCHAR(50) NOT NULL,  -- running, completed, failed
    total_pages_explored INTEGER DEFAULT 0,
    total_elements_found INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**表2: `web_explored_pages` (已探索页面表)**
```sql
CREATE TABLE web_explored_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exploration_id UUID REFERENCES web_page_explorations(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    page_url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,  -- URL规范化
    page_fingerprint VARCHAR(255) NOT NULL UNIQUE,  -- 页面指纹
    page_title VARCHAR(500),
    snapshot_yaml TEXT NOT NULL,  -- YAML格式快照
    snapshot_path VARCHAR(2048),  -- MinIO存储路径
    element_count INTEGER DEFAULT 0,
    link_count INTEGER DEFAULT 0,
    explored_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    INDEX idx_project_fingerprint (project_id, page_fingerprint),
    INDEX idx_normalized_url (normalized_url)
);
```

**表3: `web_page_elements` (页面元素表)**
```sql
CREATE TABLE web_page_elements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    explored_page_id UUID NOT NULL REFERENCES web_explored_pages(id) ON DELETE CASCADE,
    element_ref VARCHAR(50) NOT NULL,  -- e1, e2, e3等
    element_type VARCHAR(50) NOT NULL,  -- button, textbox, link等
    role VARCHAR(50),
    label VARCHAR(500),
    primary_locator TEXT NOT NULL,  -- 主定位器
    alternative_locators JSONB,  -- 备选定位器
    attributes JSONB,  -- 元素属性
    position JSONB,  -- {x, y, width, height}
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    INDEX idx_explored_page (explored_page_id),
    INDEX idx_element_type (element_type)
);
```

#### 2.3.3 新增工具函数

**位置**: `backend/app/agents/tools/web_exploration.py`

```python
"""Web探索工具函数"""

from typing import Dict, List, Optional
from langchain_core.tools import tool

@tool
async def create_page_exploration_session(
    project_identifier: str,
    session_name: str,
    start_url: str,
    url_patterns: List[str],
    forbidden_paths: List[str],
    max_depth: int = 3,
    max_pages: int = 100
) -> Dict:
    """
    创建页面探索会话
    
    Args:
        project_identifier: 项目标识符
        session_name: 会话名称
        start_url: 起始URL
        url_patterns: 允许的URL模式（正则表达式）
        forbidden_paths: 禁止路径列表
        max_depth: 最大探索深度
        max_pages: 最大探索页面数
    
    Returns:
        Dict: {session_id, status, message}
    """
    # 实现：创建数据库记录
    pass

@tool
async def save_page_exploration_snapshot(
    project_identifier: str,
    exploration_session_id: str,
    page_url: str,
    page_title: str,
    snapshot_yaml: str,
    page_fingerprint: str,
    elements: List[Dict],
    links: List[Dict]
) -> Dict:
    """
    保存页面探索快照
    
    Args:
        project_identifier: 项目标识符
        exploration_session_id: 探索会话ID
        page_url: 页面URL
        page_title: 页面标题
        snapshot_yaml: YAML格式快照
        page_fingerprint: 页面指纹
        elements: 元素列表
        links: 链接列表
    
    Returns:
        Dict: {success, explored_page_id, message}
    """
    # 实现：保存到数据库和MinIO
    pass

@tool
async def check_page_explored(
    project_identifier: str,
    page_url: str,
    page_fingerprint: str
) -> Dict:
    """
    检查页面是否已探索
    
    Args:
        project_identifier: 项目标识符
        page_url: 页面URL
        page_fingerprint: 页面指纹
    
    Returns:
        Dict: {is_explored, explored_page_id, explored_at}
    """
    # 实现：查询数据库
    pass

@tool
async def get_page_snapshot_by_url(
    project_identifier: str,
    page_url: str
) -> Dict:
    """
    根据URL获取页面快照
    
    Args:
        project_identifier: 项目标识符
        page_url: 页面URL
    
    Returns:
        Dict: {snapshot_yaml, elements, links, explored_at}
    """
    # 实现：从数据库或MinIO获取
    pass

@tool
async def list_explored_pages(
    project_identifier: str,
    exploration_session_id: Optional[str] = None
) -> Dict:
    """
    列出已探索的页面
    
    Args:
        project_identifier: 项目标识符
        exploration_session_id: 探索会话ID（可选）
    
    Returns:
        Dict: {pages: [{page_url, page_title, element_count, explored_at}]}
    """
    # 实现：查询数据库
    pass
```

#### 2.3.4 YAML快照格式

```yaml
# 页面快照格式
metadata:
  url: "https://example.com/login"
  title: "登录页面"
  timestamp: "2026-06-25T10:30:00Z"
  fingerprint: "login-page-abc123"
  project_id: "proj-001"
  exploration_session_id: "session-xyz"

page_structure:
  viewport:
    width: 1920
    height: 1080
  
  elements:
    - id: "e1"
      type: "textbox"
      role: "textbox"
      label: "用户名"
      locators:
        primary: "getByRole('textbox', { name: '用户名' })"
        alternatives:
          - "getByLabel('用户名')"
          - "getByPlaceholder('请输入用户名')"
      attributes:
        name: "username"
        placeholder: "请输入用户名"
        required: true
      position:
        x: 100
        y: 200
        
    - id: "e2"
      type: "textbox"
      role: "textbox"
      label: "密码"
      locators:
        primary: "getByRole('textbox', { name: '密码' })"
        alternatives:
          - "getByLabel('密码')"
      attributes:
        name: "password"
        type: "password"
        
    - id: "e3"
      type: "button"
      role: "button"
      label: "登录"
      locators:
        primary: "getByRole('button', { name: '登录' })"
        alternatives:
          - "getByText('登录', { exact: true })"

  links:
    - text: "忘记密码"
      href: "/forgot-password"
      locator: "getByRole('link', { name: '忘记密码' })"
    - text: "注册新账号"
      href: "/register"
      locator: "getByRole('link', { name: '注册新账号' })"
```

## 3. 实现流程

### 3.1 探索工作流

```python
# Skill: web-page-explorer

# 用户输入
user_input = {
    "project_identifier": "proj-001",
    "start_url": "https://example.com/login",
    "url_patterns": [r"https://example\.com/.*"],
    "forbidden_paths": ["/api/", "/logout"],
    "max_depth": 2,
    "max_pages": 50
}

# 步骤1: 创建探索会话
session = create_page_exploration_session(
    project_identifier=user_input["project_identifier"],
    session_name="登录模块探索",
    start_url=user_input["start_url"],
    url_patterns=user_input["url_patterns"],
    forbidden_paths=user_input["forbidden_paths"],
    max_depth=user_input["max_depth"],
    max_pages=user_input["max_pages"]
)

# 步骤2: 初始化Playwright
planner_setup_page(project="chromium")

# 步骤3: 探索页面（BFS或DFS）
explore_queue = [(user_input["start_url"], 0)]  # (url, depth)
visited = set()

while explore_queue and len(visited) < user_input["max_pages"]:
    url, depth = explore_queue.pop(0)
    
    if depth > user_input["max_depth"]:
        continue
    
    # 导航到页面
    browser_navigate(url=url)
    browser_snapshot()  # 等待加载
    
    # 获取页面快照
    snapshot_result = browser_snapshot()
    
    # 计算页面指纹
    fingerprint = calculate_page_fingerprint(url, snapshot_result)
    
    # 检查是否已探索
    check_result = check_page_explored(
        project_identifier=user_input["project_identifier"],
        page_url=url,
        page_fingerprint=fingerprint
    )
    
    if check_result["is_explored"]:
        print(f"页面已探索，跳过: {url}")
        continue
    
    # 解析页面元素
    elements = parse_page_elements(snapshot_result)
    
    # 为每个元素生成定位器
    for element in elements:
        if element["is_interactive"]:
            locator = browser_generate_locator(
                description=element["description"]
            )
            element["locators"]["primary"] = locator
    
    # 提取链接
    links = extract_links(snapshot_result)
    
    # 生成YAML快照
    yaml_snapshot = generate_yaml_snapshot(
        url=url,
        title=snapshot_result["title"],
        elements=elements,
        links=links
    )
    
    # 保存快照
    save_page_exploration_snapshot(
        project_identifier=user_input["project_identifier"],
        exploration_session_id=session["session_id"],
        page_url=url,
        page_title=snapshot_result["title"],
        snapshot_yaml=yaml_snapshot,
        page_fingerprint=fingerprint,
        elements=elements,
        links=links
    )
    
    visited.add(url)
    
    # 发现新链接并加入队列
    for link in links:
        link_url = link["href"]
        if link_url not in visited:
            if matches_pattern(link_url, user_input["url_patterns"]):
                if not is_forbidden(link_url, user_input["forbidden_paths"]):
                    explore_queue.append((link_url, depth + 1))
```

### 3.2 去重机制

```python
def calculate_page_fingerprint(url: str, snapshot: Dict) -> str:
    """
    计算页面指纹
    
    指纹 = 规范化URL + DOM结构哈希
    """
    # 1. URL规范化
    normalized_url = normalize_url(url)
    
    # 2. DOM结构哈希
    dom_structure = extract_dom_structure(snapshot)
    dom_hash = hashlib.sha256(dom_structure.encode()).hexdigest()[:16]
    
    # 3. 组合指纹
    return f"{normalized_url}:{dom_hash}"

def normalize_url(url: str) -> str:
    """URL规范化"""
    parsed = urlparse(url)
    
    # 移除动态参数
    query_params = parse_qs(parsed.query)
    filtered_params = {
        k: v for k, v in query_params.items()
        if k not in ["timestamp", "session_id", "token"]
    }
    
    # 重新构建URL
    normalized_query = urlencode(sorted(filtered_params.items()))
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path,
        '',
        normalized_query,
        ''
    ))
```

### 3.3 与现有流程集成

```python
# 在web_agent中添加探索功能

# 用户: "探索登录模块"
# Agent识别为探索任务，调用web-page-explorer skill

# 用户: "为子功能生成测试"
# Agent流程:
# 1. 调用 get_sub_function_details(sub_function_id)
# 2. 检查页面是否已探索: get_page_snapshot_by_url(page_url)
# 3. 如果已探索，直接使用快照中的定位器
# 4. 如果未探索，先调用web-page-explorer探索页面
# 5. 使用planner skill生成测试计划（使用快照中的定位器）
# 6. 使用generator skill生成测试代码
```

## 4. API接口设计

### 4.1 探索相关API

```python
# backend/app/api/v1/endpoints/web_exploration.py

@router.post("/explorations", response_model=ExplorationSessionResponse)
async def create_exploration_session(
    session_create: ExplorationSessionCreate,
    db: Session = Depends(get_db)
):
    """创建探索会话"""
    pass

@router.get("/explorations/{session_id}", response_model=ExplorationSessionResponse)
async def get_exploration_session(
    session_id: UUID,
    db: Session = Depends(get_db)
):
    """获取探索会话详情"""
    pass

@router.get("/explorations/{session_id}/pages", response_model=List[ExploredPageResponse])
async def list_explored_pages(
    session_id: UUID,
    db: Session = Depends(get_db)
):
    """列出已探索的页面"""
    pass

@router.get("/pages/snapshot", response_model=PageSnapshotResponse)
async def get_page_snapshot(
    project_id: UUID,
    page_url: str,
    db: Session = Depends(get_db)
):
    """根据URL获取页面快照"""
    pass
```

## 5. 使用示例

### 5.1 通过Agent探索

```python
# 用户输入
"探索 https://example.com/login 页面，深度2层，最多50个页面，禁止访问/api/和/logout"

# Agent执行
1. 解析用户输入
2. 创建探索会话
3. 调用web-page-explorer skill
4. 输出探索结果

# 输出
✅ 探索完成！
📊 探索统计:
  - 探索页面数: 25
  - 发现元素数: 156
  - 发现链接数: 45
  
📄 探索的页面:
  1. https://example.com/login (登录页面) - 8个元素
  2. https://example.com/register (注册页面) - 12个元素
  3. https://example.com/forgot-password (忘记密码) - 5个元素
  ...
```

### 5.2 使用已探索的页面生成测试

```python
# 用户输入
"为登录子功能生成测试"

# Agent执行
1. 获取子功能详情: get_sub_function_details(sub_function_id)
2. 检查页面是否已探索: get_page_snapshot_by_url(page_url)
3. ✅ 页面已探索，使用快照中的定位器
4. 调用planner skill（直接使用快照中的定位器，无需重新探索）
5. 调用generator skill生成测试代码
6. 保存测试脚本

# 优势
- 无需重复探索页面
- 定位器一致性高
- 生成速度快
```

## 6. 关键特性

### 6.1 语义化定位器优先级

1. `getByTestId('...')` - 如果有data-testid
2. `getByRole('button', { name: '...' })` - 最推荐
3. `getByLabel('...')` - 表单元素
4. `getByText('...', { exact: true })` - 唯一文本
5. `getByPlaceholder('...')` - 输入框

### 6.2 去重策略

- **URL规范化**: 移除动态参数、排序查询参数
- **DOM结构哈希**: 简化DOM结构后计算哈希
- **组合指纹**: URL + DOM哈希

### 6.3 存储策略

- **数据库**: 元数据、指纹、统计信息
- **MinIO**: YAML快照文件（大文件）
- **缓存**: 最近探索的页面（Redis可选）

## 7. 总结

本设计基于项目的实际架构：
- ✅ 使用现有的Agent + Skills + Backend架构
- ✅ 通过Playwright MCP与浏览器交互
- ✅ 复用现有的web_agent和工具函数
- ✅ 扩展数据库模型存储探索结果
- ✅ 生成标准YAML快照格式
- ✅ 实现页面去重机制
- ✅ 优先使用语义化定位器
- ✅ 与现有测试生成流程无缝集成

**下一步**:
1. 创建数据库迁移脚本
2. 实现工具函数
3. 编写web-page-explorer skill
4. 添加API接口
5. 前端UI集成
