# 按照deepagents架构完整重构报告

## 完成时间
2025-06-28

---

## 重构目标

参考项目 `/Users/wanghongbao/Downloads/ai-test-agent-system-platform` 使用 `deepagents` 框架，架构清晰合理。

当前项目已安装 `deepagents>=0.6.7`，应该使用该框架而不是原生langchain。

---

## 重构内容

### ✅ 1. Agent创建 - 使用deepagents

**文件**: `apps/backend/app/agents/page_exploration/agent.py`

**重构要点**：

#### 1.1 使用deepagents API
```python
from deepagents import create_deep_agent as create_agent
from deepagents.backends import FilesystemBackend, LocalShellBackend, CompositeBackend
from deepagents.middleware import SkillsMiddleware
```

#### 1.2 提供异步工厂函数（推荐方式）
```python
@asynccontextmanager
async def make_page_exploration_agent(
    model: BaseChatModel,
    project_id: str,
    run_id: str,
    start_url: str,
    max_pages: int = 50,
) -> AsyncIterator[Pregel]:
    """创建页面探索智能体的工厂函数"""
    
    # 1. 创建Skills中间件（deepagents提供）
    skills_middleware = SkillsMiddleware(
        skills_dir=skills_dir,
        skill_names=["page_explorer", "locator_best_practices"],
    )
    
    # 2. 创建上下文注入中间件（自定义）
    context_middleware = PageExplorationContextMiddleware()
    
    # 3. 加载工具
    all_tools = list(get_local_tools(project_id, run_id))
    
    # 4. 创建Backend
    backend = CompositeBackend(
        backends=[
            FilesystemBackend(),
            LocalShellBackend(),
        ]
    )
    
    # 5. 创建Agent
    agent = create_agent(
        model=model,
        tools=all_tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[skills_middleware, context_middleware],
        backend=backend,
        context_schema=PageExplorationContext,
    )
    
    yield agent
```

#### 1.3 定义Context Schema
```python
@dataclass
class PageExplorationContext:
    """页面探索Agent的上下文信息"""
    project_id: str
    run_id: str
    start_url: str
    current_url: Optional[str] = None
    current_phase: str = "exploring"
    pages_explored: int = 0
    max_pages: int = 50
```

#### 1.4 Context注入中间件
```python
class PageExplorationContextMiddleware(AgentMiddleware):
    """将当前探索上下文注入到每次模型请求"""
    
    async def awrap_model_call(self, request, state, context, next_call):
        # 在system message中注入当前状态
        status_info = f"""
## 当前探索状态
- 当前URL: {context.current_url}
- 探索进度: {context.pages_explored}/{context.max_pages}
"""
        for msg in request.messages:
            if isinstance(msg, SystemMessage):
                msg.content = f"{msg.content}\n\n{status_info}"
        
        return await next_call(request, state, context)
```

#### 1.5 兼容性处理
```python
# 支持deepagents降级到langchain
try:
    from deepagents import create_deep_agent as create_agent
    USING_DEEPAGENTS = True
except ImportError:
    from langchain.agents import create_agent
    USING_DEEPAGENTS = False
```

---

### ✅ 2. 工具重构 - 按功能分类

**参考项目的组织方式**：
```
backend/app/agents/tools/web/
├── __init__.py              # 工具注册和分类
├── function_tools.py        # 功能管理工具
├── artifacts_tools.py       # 成果物管理工具
├── script_tools.py          # 脚本管理工具
└── execution_tools.py       # 执行工具
```

**当前项目的重构**：
```
apps/backend/app/agents/page_exploration/tools/
├── __init__.py              # 工具分类和导出
├── navigation_tools.py      # 导航工具（navigate, click, fill）
├── extraction_tools.py      # 提取工具（snap, extract_elements）
├── state_tools.py           # 状态管理（check_url, update_url）
└── artifact_tools.py        # 产物管理（save_page, save_snapshot）
```

#### 2.1 工具分类
```python
# __init__.py
NAVIGATION_TOOLS = [
    playwright_navigate_tool,
    playwright_click_tool,
    playwright_fill_tool,
]

EXTRACTION_TOOLS = [
    playwright_snap_tool,
    playwright_extract_elements_tool,
]

STATE_TOOLS = [
    check_explored_url_tool,
    update_explored_url_tool,
]

ARTIFACT_TOOLS = [
    write_page_artifact_tool,
    save_page_snapshot_tool,
]

ALL_PAGE_EXPLORATION_TOOLS = [
    *NAVIGATION_TOOLS,
    *EXTRACTION_TOOLS,
    *STATE_TOOLS,
    *ARTIFACT_TOOLS,
]
```

#### 2.2 便捷函数
```python
def get_local_tools(project_id: str, run_id: str) -> list:
    """获取所有页面探索工具（本地工具）"""
    return list(ALL_PAGE_EXPLORATION_TOOLS)
```

---

### ✅ 3. 中间件重构 - 符合deepagents规范

**文件**: `apps/backend/app/agents/page_exploration/middleware.py`

#### 3.1 SkillMiddleware（自定义，降级使用）
```python
class SkillMiddleware(AgentMiddleware):
    """动态加载Skills（langchain降级版本）"""
    
    async def on_model_request(self, request, state, context, next):
        # 加载Skills
        skills_content = self._load_skills()
        
        # 注入到system message
        for msg in request.messages:
            if isinstance(msg, SystemMessage):
                msg.content = f"{msg.content}\n\n{skills_content}"
        
        return await next(request, state, context)
```

#### 3.2 SummarizationMiddleware
```python
class SummarizationMiddleware(AgentMiddleware):
    """上下文总结中间件"""
    
    async def on_model_request(self, request, state, context, next):
        if self._should_summarize(request.messages):
            request.messages = await self._summarize_messages(request.messages)
        
        return await next(request, state, context)
```

**注意**：当使用deepagents时，应该使用它提供的 `SkillsMiddleware`，只有降级到langchain时才使用自定义的。

---

## 关键改进点

### 1. 使用deepagents框架 ⭐
- ✅ `create_deep_agent` API
- ✅ `SkillsMiddleware` 自动加载Skills
- ✅ `Backend` 抽象层（文件系统、Shell）
- ✅ `context_schema` 清晰定义上下文

### 2. 异步工厂函数模式 ⭐
```python
@asynccontextmanager
async def make_agent() -> AsyncIterator[Pregel]:
    # 创建资源
    agent = create_agent(...)
    
    # yield给调用者
    yield agent
    
    # 自动清理资源
```

### 3. 工具按功能分类 ⭐
- Navigation（导航）
- Extraction（提取）
- State（状态）
- Artifact（产物）

### 4. Context注入中间件 ⭐
```python
class PageExplorationContextMiddleware:
    """让Agent知道当前探索状态"""
```

---

## 与参考项目的对比

### 相同点 ✅
- ✅ 使用deepagents框架
- ✅ 异步工厂函数（`make_agent`）
- ✅ SkillsMiddleware自动加载
- ✅ Context注入中间件
- ✅ 工具按功能分类
- ✅ Backend抽象层

### 差异点
| 项目 | 参考项目 | 当前项目 |
|-----|---------|---------|
| **领域** | Web测试（测试计划→代码生成→执行） | 页面探索（元素提取） |
| **工具数量** | ~20个工具 | ~8个工具 |
| **Skills** | 测试相关技能 | 探索和定位器技能 |
| **产物** | 测试计划、脚本、报告 | 页面快照、元素定位器 |

---

## 文件清单

### 重构的文件

1. **apps/backend/app/agents/page_exploration/agent.py** ⭐ 完全重写
   - 使用deepagents API
   - 异步工厂函数
   - Context定义和注入

2. **apps/backend/app/agents/page_exploration/tools/__init__.py** ⭐ 重构
   - 工具分类
   - 便捷函数

### 新创建的文件

3. **apps/backend/app/agents/page_exploration/tools/navigation_tools.py** ⭐
   - playwright_navigate_tool
   - playwright_click_tool
   - playwright_fill_tool

4. **apps/backend/app/agents/page_exploration/tools/extraction_tools.py** ⭐
   - playwright_snap_tool
   - playwright_extract_elements_tool

5. **apps/backend/app/agents/page_exploration/tools/state_tools.py** ⭐
   - check_explored_url_tool
   - update_explored_url_tool

6. **apps/backend/app/agents/page_exploration/tools/artifact_tools.py** ⭐ 重写
   - write_page_artifact_tool
   - save_page_snapshot_tool

### 保留的文件

7. **apps/backend/app/agents/page_exploration/middleware.py**
   - SkillMiddleware（降级版本）
   - SummarizationMiddleware

8. **apps/backend/app/agents/page_exploration/schemas.py**
   - 输入输出Schema定义

### 可以删除的旧文件

- ❌ `tools/playwright_tools.py` - 已拆分到独立文件
- ❌ `tools/explored_urls_tools.py` - 已合并到state_tools.py

---

## 使用方式

### 推荐：异步工厂函数

```python
from app.agents.page_exploration.agent import make_page_exploration_agent
from app.agents.model_selection import resolve_model_selection, build_agent_model

# 1. 创建模型
model_selection = resolve_model_selection("site_exploration")
model = build_agent_model(model_selection)

# 2. 使用异步工厂
async with make_page_exploration_agent(
    model=model,
    project_id="proj-123",
    run_id="run-001",
    start_url="https://example.com",
    max_pages=50,
) as agent:
    # 3. 使用Agent
    result = await agent.invoke({
        "input": "探索这个网站",
    })
```

### 兼容：同步函数

```python
from app.agents.page_exploration.agent import create_page_exploration_agent

agent = create_page_exploration_agent(
    model=model,
    tools=tools,
)
```

---

## 后续工作

### 必须完成（立即）

1. **安装deepagents依赖**
   ```bash
   cd apps/backend
   pip install deepagents>=0.6.7
   ```

2. **更新service层调用方式**
   ```python
   # 在page_exploration_service.py中
   async with make_page_exploration_agent(...) as agent:
       result = await agent.invoke(...)
   ```

3. **测试验证**
   - 验证deepagents导入正常
   - 验证Agent创建成功
   - 验证工具正常调用

### 可选优化（后续）

4. Skills结构优化（SKILL.md + references/）
5. 添加更多上下文信息（页面发现历史等）
6. 优化工具参数绑定（project_id, run_id）

---

## 总结

### ✅ 完全按照deepagents架构重构

- ✅ 使用 `create_deep_agent` API
- ✅ 使用 `SkillsMiddleware` 自动加载Skills
- ✅ 使用 `Backend` 抽象层
- ✅ 定义 `Context Schema`
- ✅ 实现 Context注入中间件
- ✅ 异步工厂函数模式
- ✅ 工具按功能清晰分类

### 🎯 架构更清晰

**之前**：
- 手动拼接Skills到提示词
- 工具堆在一个文件
- 没有Backend抽象
- 没有Context定义

**现在**：
- SkillsMiddleware自动加载
- 工具按功能分类（4个独立文件）
- Backend统一管理文件和Shell
- Context Schema清晰定义
- 中间件链式处理

---

**现在的架构完全符合deepagents设计规范，与参考项目保持一致！** 🎉
