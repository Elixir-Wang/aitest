# 按Spec完全重新实现 - 实施计划

## 当前状态评估

### ❌ 需要废弃/重构的代码
1. 后端 `_execute_exploration()` 模拟实现 - **完全错误**
2. 产物Tab的artifacts概念 - **与spec偏差**
3. 缺少LangChain Agent - **核心缺失**
4. 缺少pages/*.yaml管理 - **核心缺失**

### ✅ 可以保留的代码
1. 探索进度展示（AgentPlan组件）- 符合spec
2. SSE推送基础设施 - 符合spec
3. 数据库表结构（exploration_runs等）- 基本符合
4. Playwright CLI Wrapper - 已存在但需验证

---

## 完整实施计划

按照spec第7节实施计划，分4个阶段：

### 阶段1：探索引擎核心（3天）⭐ 优先级P0

#### 1.1 实现LangChain Exploration Agent
**文件**: `apps/backend/app/agents/page_exploration/exploration_agent.py`

```python
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

class PageExplorationAgent:
    """基于LangChain的页面探索Agent"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.tools = [
            NavigatePageTool(),
            GetPageStructureTool(),
            ClickElementTool(),
            ExtractElementsTool(),
            CheckUrlExploredTool(),
            MarkUrlExploredTool(),
        ]
        self.agent = self._create_agent()
    
    def explore_page(self, url: str, context: dict) -> dict:
        """探索单个页面"""
        pass
    
    def explore_site(self, start_url: str, config: dict) -> None:
        """探索整个站点"""
        pass
```

#### 1.2 集成Playwright CLI
**文件**: `apps/backend/app/agents/page_exploration/playwright/cli_wrapper.py` (已存在，需验证)

- [ ] 验证现有wrapper是否符合spec
- [ ] 实现spec要求的所有操作
- [ ] 添加错误处理和重试

#### 1.3 实现Artifact Service
**文件**: `apps/backend/app/agents/page_exploration/artifact_service.py`

```python
class ArtifactService:
    """产物服务 - 管理pages/*.yaml和explored_urls.yaml"""
    
    def save_page_snapshot(self, project_id: str, page_data: dict) -> str:
        """保存页面快照到pages/page-{slug}.yaml"""
        pass
    
    def load_page_snapshot(self, project_id: str, page_id: str) -> dict:
        """加载页面快照"""
        pass
    
    def update_explored_urls(self, project_id: str, url: str, page_id: str) -> None:
        """更新explored_urls.yaml"""
        pass
    
    def check_url_explored(self, project_id: str, url: str) -> bool:
        """检查URL是否已探索"""
        pass
```

#### 1.4 实现Skills
**文件**: 
- `apps/backend/app/agents/page_exploration/skills/page_explorer.md`
- `apps/backend/app/agents/page_exploration/skills/locator_best_practices.md`

按照spec第4节创建Skills文件。

---

### 阶段2：产物生成和管理（2天）⭐ 优先级P0

#### 2.1 实现YAML产物生成

**数据结构**（按spec第3.5节）:
```yaml
# pages/page-workspace-agents.yaml
page_id: page-workspace-agents
original_url: "https://example.com/workspace/agents"
normalized_url: "/workspace/agents"
title: "工作区 - Agents管理"
description: "Agent列表和配置页面"
explored_at: "2026-06-27T10:30:00Z"
elements:
  - element_id: btn-create-agent
    role: button
    label: "创建Agent"
    locator: "role=button[name='创建Agent']"
    context: "页面顶部工具栏"
```

#### 2.2 实现explored_urls.yaml管理

```yaml
# explored_urls.yaml
urls:
  - url: "/workspace/agents"
    page_id: page-workspace-agents
    explored_at: "2026-06-27T10:30:00Z"
  - url: "/workspace/settings"
    page_id: page-workspace-settings
    explored_at: "2026-06-27T10:35:00Z"
```

#### 2.3 更新数据库schema（如需要）

检查是否需要添加新表或字段。

---

### 阶段3：前端页面管理界面（2天）⭐ 优先级P1

#### 3.1 实现后端API

**新增API端点**:
```python
# apps/backend/app/api/v1/page_exploration.py

@router.get("/pages/tree")
def get_pages_tree(project_id: str) -> dict:
    """获取项目的pages树形结构"""
    pass

@router.get("/pages/{page_id}")
def get_page_detail(page_id: str) -> dict:
    """获取页面快照详情"""
    pass

@router.post("/pages/{page_id}/re-explore")
def re_explore_page(page_id: str) -> dict:
    """重新探索指定页面"""
    pass

@router.delete("/pages/{page_id}")
def delete_page(page_id: str) -> dict:
    """删除页面记录"""
    pass

@router.get("/explored-urls")
def get_explored_urls(project_id: str) -> dict:
    """获取已探索URL列表"""
    pass
```

#### 3.2 实现前端页面管理界面

**文件**: `apps/frontend/src/components/ai-testing/page-management-panel.tsx`

```tsx
/**
 * 页面管理面板 - 按照spec第7.2节设计
 */
export function PageManagementPanel() {
  return (
    <div className="space-y-4">
      {/* 左侧：页面树 */}
      <div className="flex gap-4">
        <div className="w-80">
          <PageTree pages={pages} />
        </div>
        
        {/* 右侧：页面详情 */}
        <div className="flex-1">
          <PageDetailView page={selectedPage} />
        </div>
      </div>
      
      {/* 底部：explored_urls列表 */}
      <ExploredUrlsList urls={exploredUrls} />
    </div>
  );
}
```

#### 3.3 修改exploration-workspace.tsx

- [ ] 将"探索产物"Tab改为"页面管理"Tab
- [ ] 集成PageManagementPanel组件
- [ ] 删除artifacts相关代码

---

### 阶段4：SSE实时推送和上下文管理（1天）⭐ 优先级P1

#### 4.1 实现SSE事件推送

按照spec第3.5节，推送以下事件：
- `exploration_started`
- `module_started`
- `page_started`
- `page_completed`
- `module_completed`
- `exploration_completed`

#### 4.2 实现LangChain上下文管理

```python
from langchain.middleware import SummarizationMiddleware

middleware = SummarizationMiddleware(
    llm=llm,
    summary_threshold=8000,
    target_length=2000
)
```

---

## 实施顺序

### Week 1: 探索引擎核心
- Day 1-2: LangChain Agent + Playwright CLI集成
- Day 3: Artifact Service + Skills

### Week 2: 产物和前端
- Day 4-5: YAML产物生成和管理
- Day 6-7: 前端页面管理界面

### Week 3: 优化和测试
- Day 8: SSE推送和上下文管理
- Day 9-10: 集成测试和bug修复

---

## 需要确认的问题

### 1. 代码清理策略
- ❓ 是否删除当前的产物Tab代码？
- ❓ 是否保留artifacts表和相关代码作为补充？

### 2. LangChain版本
- ❓ 使用LangChain 0.1.x 还是 0.2.x？
- ❓ 使用哪个LLM提供商（OpenAI/Azure/本地）？

### 3. 环境配置
- ❓ Playwright CLI是否已安装？
- ❓ Node.js环境是否配置好？

### 4. 测试数据
- ❓ 使用哪个项目/环境进行测试？
- ❓ 测试URL是什么？

---

## 立即开始

**建议从阶段1开始**，逐步实现探索引擎核心。

请确认：
1. ✅ 是否同意这个实施计划？
2. ✅ 是否从阶段1.1（LangChain Agent）开始？
3. ✅ 是否删除当前的产物Tab代码？
4. ✅ LangChain和LLM配置信息？

确认后我立即开始实施！
