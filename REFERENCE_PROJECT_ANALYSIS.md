# 参考项目与当前项目对比分析

## 关键发现

### 参考项目（ai-test-agent-system-platform）
**使用框架**: `deepagents` (基于LangGraph的高级封装)
```python
from deepagents import create_deep_agent as create_agent
from deepagents.backends import FilesystemBackend, LocalShellBackend
from deepagents.middleware import SkillsMiddleware
```

### 当前项目
**使用框架**: `langchain` (原生LangChain)
```python
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
```

---

## 框架差异

### 1. Agent创建方式

**参考项目 (deepagents)**:
```python
web_agent = create_agent(
    model=model,
    tools=all_tools,
    system_prompt=SYSTEM_PROMPT,
    middleware=[skills_middleware, context_middleware],
    backend=composite_backend,  # 特有：文件系统和Shell后端
    context_schema=WebAgentContext,  # 特有：上下文Schema
)
```

**当前项目 (langchain)**:
```python
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=system_prompt,
    middleware=[skill_middleware, summarization_middleware],
    # 没有backend和context_schema参数
)
```

### 2. 中间件实现

**参考项目使用deepagents.middleware.SkillsMiddleware**:
- 这是deepagents提供的现成中间件
- 自动处理Skills加载和注入

**当前项目需要自己实现AgentMiddleware**:
- 继承`langchain.agents.middleware.AgentMiddleware`
- 实现`on_model_request`方法

---

## 可以学习的要点

### ✅ 1. 工具组织方式

**参考项目的tools组织**非常清晰：
```
backend/app/agents/tools/web/
├── __init__.py              # 工具注册和分类
├── function_tools.py        # 功能管理工具
├── artifacts_tools.py       # 成果物管理工具
├── script_tools.py          # 脚本管理工具
└── execution_tools.py       # 执行工具
```

**工具分类**：
```python
# function_tools.py
FUNCTION_TOOLS = [
    list_web_functions,
    get_function_details,
    create_web_function,
]

# artifacts_tools.py
ARTIFACT_TOOLS = [
    save_web_test_plan,
    save_web_test_cases,
    get_artifact_content,
]

# 在__init__.py中组合
ALL_WEB_TOOLS = [
    *FUNCTION_TOOLS,
    *ARTIFACT_TOOLS,
    *SCRIPT_TOOLS,
    *EXECUTION_TOOLS,
]
```

**当前项目可以学习**：
- ✅ 按功能分类组织工具（而不是全部堆在一个文件）
- ✅ 使用常量分组工具，便于按需加载
- ✅ 清晰的导出和文档

### ✅ 2. Skills组织方式

**参考项目的Skills结构**：
```
backend/app/agents/skills/web_testing/
├── SKILL.md                 # 主技能文档
├── references/              # 参考文档目录
│   ├── best_practices.md
│   └── examples.md
```

**SkillsMiddleware加载逻辑**：
```python
# deepagents会自动：
# 1. 读取SKILL.md
# 2. 读取references/下的文档
# 3. 组合并注入到system prompt
```

**当前项目可以学习**：
- ✅ 主Skill + References的两层结构
- ✅ 自动加载references目录下的文档
- ✅ 支持按需加载（节约token）

### ✅ 3. 上下文管理

**参考项目的WebAgentContext**：
```python
@dataclass
class WebAgentContext:
    """Web Agent的上下文信息"""
    function_id: str
    sub_function_id: str
    current_phase: str  # plan/generate/execute/fix/report
```

**WebContextInjectionMiddleware**：
```python
class WebContextInjectionMiddleware(AgentMiddleware):
    """将当前上下文注入到每次请求"""
    async def awrap_model_call(self, request, state, context, next):
        # 注入当前功能ID、阶段等信息
        return await next(request, state, context)
```

**当前项目可以学习**：
- ✅ 定义清晰的Context Schema
- ✅ 使用中间件自动注入上下文
- ✅ 让Agent知道当前处于哪个阶段

### ❌ 4. Backend（不适用）

参考项目使用的 `deepagents.backends`:
```python
composite_backend = CompositeBackend(
    backends=[
        FilesystemBackend(),  # 文件系统操作
        LocalShellBackend(),  # Shell命令执行
    ]
)
```

**这是deepagents特有功能**，原生LangChain没有。

当前项目不需要学习这部分，因为：
- 我们直接使用工具(tools)实现文件和Shell操作
- 不需要额外的backend抽象层

---

## 当前项目应该做的改进

### 改进1：工具组织方式

**当前**：
```
app/agents/page_exploration/tools/
├── __init__.py
├── playwright_tools.py      # 所有playwright工具
├── explored_urls_tools.py
└── artifact_tools.py
```

**改进建议**：
```
app/agents/page_exploration/tools/
├── __init__.py              # 分类导出
├── navigation_tools.py      # 导航相关: navigate, click, fill
├── extraction_tools.py      # 提取相关: snap, extract_elements
├── state_tools.py          # 状态管理: check_url, mark_url
└── artifact_tools.py       # 产物管理: save_page, save_report
```

### 改进2：Skills结构

**当前**：
```
app/agents/page_exploration/skills/
├── __init__.py
├── locator_best_practices.md
└── page_explorer.md
```

**改进建议**：
```
app/agents/page_exploration/skills/
├── SKILL.md                 # 主技能（页面探索策略）
└── references/
    ├── locator_best_practices.md
    ├── accessibility_guide.md
    └── common_patterns.md
```

### 改进3：Context Schema

**当前**：没有明确的Context定义

**改进建议**：
```python
# schemas.py
@dataclass
class ExplorationContext:
    """探索Agent的上下文信息"""
    project_id: str
    run_id: str
    start_url: str
    current_url: Optional[str] = None
    current_phase: str = "exploring"  # exploring/analyzing/completed
    pages_explored: int = 0
    max_pages: int = 50
```

### 改进4：中间件改进

**当前的中间件是正确的**，但可以添加：

```python
class ExplorationContextMiddleware(AgentMiddleware):
    """注入探索上下文到每次请求"""
    
    def __init__(self, context: ExplorationContext):
        self.context = context
    
    async def on_model_request(self, request, state, context_obj, next):
        # 在system message中注入当前探索状态
        status_info = f"""
当前探索状态：
- 项目: {self.context.project_id}
- 当前URL: {self.context.current_url}
- 已探索: {self.context.pages_explored}/{self.context.max_pages}
- 阶段: {self.context.current_phase}
"""
        # 注入到system message
        for msg in request.messages:
            if isinstance(msg, SystemMessage):
                msg.content = f"{msg.content}\n\n{status_info}"
                break
        
        return await next(request, state, context_obj)
```

---

## 总结

### ✅ 可以学习的（框架无关的设计模式）

1. **工具组织方式** - 按功能分类，清晰导出
2. **Skills两层结构** - 主Skill + References
3. **Context Schema定义** - 清晰的上下文结构
4. **Context注入中间件** - 让Agent知道当前状态

### ❌ 不能直接照搬的（框架特定功能）

1. **deepagents.backends** - 当前项目用不了
2. **create_deep_agent的特定参数** - API不同

### 🎯 当前项目的中间件实现是正确的

我们实现的中间件**已经符合LangChain规范**：
- ✅ 继承`AgentMiddleware`
- ✅ 实现`on_model_request`
- ✅ 使用`await next()`链式调用

**参考项目用的是deepagents封装，我们用的是原生LangChain，实现方式不同但都是正确的。**

---

## 具体行动计划

### 立即可做的改进（1小时）

1. **重组工具文件**
   ```bash
   # 将playwright_tools.py拆分为：
   - navigation_tools.py  # navigate, click, fill
   - extraction_tools.py  # snap, extract
   ```

2. **优化Skills结构**
   ```bash
   # 创建references目录
   mkdir -p skills/references/
   # 移动文件
   mv locator_best_practices.md skills/references/
   ```

3. **添加Context Schema和中间件**
   ```python
   # schemas.py添加ExplorationContext
   # middleware.py添加ExplorationContextMiddleware
   ```

### 可选改进（后续）

4. 参考项目的测试组织方式
5. 参考项目的错误处理模式
6. 参考项目的日志记录方式

---

**结论**：我们的中间件实现是正确的，但可以学习参考项目的组织方式和设计模式。
