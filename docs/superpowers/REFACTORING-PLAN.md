# Page Exploration 功能重构方案

**创建日期**: 2026-06-27  
**状态**: 待审核

---

## 🔴 问题分析

### 当前问题

1. **脱离现有框架**: 生成的代码独立于现有项目架构，没有遵循项目的设计模式
2. **缺少数据库集成**: 没有使用项目的数据库和Repository模式
3. **API路由不统一**: 未遵循现有的API设计规范
4. **Service层缺失**: 没有按照项目的Service层架构组织代码
5. **缺少任务管理集成**: 未使用现有的task_service进行任务管理

### 现有框架分析

通过分析现有代码，发现项目遵循以下架构模式：

```
apps/backend/app/
├── agents/                    # Agent实现（LangChain）
│   ├── document_editor/       # 示例：文档编辑Agent
│   │   ├── agent.py          # LangChain Agent定义
│   │   ├── service.py        # 调用Agent的服务层
│   │   └── schemas.py        # Pydantic模型
│   └── requirement_analysis/  # 示例：需求分析Agent
│       ├── agent.py
│       ├── service.py        # 包含异步调用、存储管理
│       ├── schemas.py
│       └── skills/           # LangChain skills
├── api/v1/                   # FastAPI路由
│   ├── agents.py             # Agent相关API
│   ├── tasks.py              # 任务管理API
│   └── ...
├── services/                 # 业务逻辑服务层
│   ├── task_service.py       # 任务管理服务
│   ├── project_service.py
│   └── exploration/          # 探索相关服务
│       └── plan_and_execute/
├── repositories/             # 数据访问层（Repository模式）
│   ├── project_repo.py
│   ├── session_repo.py
│   └── ...
└── core/
    ├── db.py                 # SQLite数据库连接
    └── storage.py            # 文件存储管理
```

### 关键发现

1. **数据库**: 项目使用SQLite，有`exploration_runs`表（见`project_repo.py:8`）
2. **Agent模式**: Agent在`agents/`目录，每个Agent有独立的service.py调用
3. **任务管理**: 使用`task_service.py`管理后台任务
4. **API设计**: 所有API在`api/v1/`，使用`current_user`依赖注入
5. **存储管理**: 使用`core/storage.py`管理项目文件
6. **Repository模式**: 所有数据库操作通过Repository层

---

## ✅ 重构方案

### 方案概述

将Page Exploration功能**完全融入现有框架**，遵循项目的架构模式和设计规范。

### 架构对比

#### ❌ 之前的架构（独立、不兼容）
```
page_exploration/
├── orchestrator.py           # 独立的编排器
├── event_emitter.py          # 独立的事件系统
├── exploration_queue.py      # 独立的队列
├── artifact_service.py       # 独立的产物服务
├── tools/                    # LangChain工具
└── api/routes/page_exploration.py  # 独立的API路由
```

#### ✅ 重构后的架构（集成、兼容）
```
# 1. Agent层 - 决策和工具调用
agents/page_exploration/
├── agent.py                  # LangChain Agent（决策探索逻辑）
├── service.py                # 服务层（调用Agent、管理任务）
├── schemas.py                # Pydantic模型
├── skills/                   # Skills（如果需要）
└── tools/                    # LangChain Tools
    ├── playwright_tools.py   # Playwright操作工具
    ├── cache_tools.py        # 缓存检查工具
    └── artifact_tools.py     # 产物生成工具

# 2. Service层 - 业务逻辑
services/exploration/
├── page_exploration_service.py  # 页面探索服务（业务逻辑）
└── artifact_service.py          # 产物管理服务

# 3. Repository层 - 数据访问
repositories/
├── exploration_run_repo.py      # exploration_runs表操作
└── explored_url_repo.py         # explored_urls表操作

# 4. API层 - HTTP接口
api/v1/
└── page_exploration.py          # 页面探索API（遵循现有API规范）

# 5. 基础设施
agents/page_exploration/
├── playwright/
│   ├── cli_wrapper.py           # Playwright CLI封装
│   └── schemas.py               # Playwright相关模型
└── utils/
    └── url_normalizer.py        # URL规范化工具
```

---

## 📋 详细重构任务

### Phase 1: 数据库层 (Database Schema)

**目标**: 定义数据库表结构，使用项目的SQLite数据库

#### 1.1 创建exploration_runs表
```sql
CREATE TABLE IF NOT EXISTS exploration_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,  -- pending/running/completed/failed
    start_url TEXT NOT NULL,
    scope TEXT,
    max_depth INTEGER DEFAULT 3,
    max_pages INTEGER DEFAULT 50,
    max_duration INTEGER,  -- seconds
    pages_discovered INTEGER DEFAULT 0,
    pages_completed INTEGER DEFAULT 0,
    pages_failed INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    created_by TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);
```

#### 1.2 创建explored_urls表
```sql
CREATE TABLE IF NOT EXISTS explored_urls (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    original_url TEXT NOT NULL,
    status TEXT NOT NULL,  -- discovered/completed/failed
    depth INTEGER NOT NULL,
    artifact_path TEXT,
    error_message TEXT,
    discovered_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (run_id) REFERENCES exploration_runs(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_explored_urls_run 
    ON explored_urls(run_id);
CREATE INDEX IF NOT EXISTS idx_explored_urls_project_normalized 
    ON explored_urls(project_id, normalized_url);
```

#### 1.3 创建Repository
- `repositories/exploration_run_repo.py`
- `repositories/explored_url_repo.py`

---

### Phase 2: Agent层重构

**目标**: 将探索逻辑重构为标准的LangChain Agent

#### 2.1 保留Playwright基础设施
```
agents/page_exploration/playwright/
├── cli_wrapper.py      # ✅ 保留（已完成）
├── schemas.py          # ✅ 保留（已完成）
└── __init__.py
```

#### 2.2 保留工具层
```
agents/page_exploration/tools/
├── playwright_tools.py  # ✅ 保留并优化
├── cache_tools.py       # ✅ 新增（检查URL是否已探索）
└── artifact_tools.py    # ✅ 重构（写入数据库+文件）
```

**关键变化**:
- `cache_tools.py`: 使用`explored_url_repo`查询数据库而非内存
- `artifact_tools.py`: 同时写入文件系统和数据库

#### 2.3 创建Agent定义
```python
# agents/page_exploration/agent.py
from langchain_core.agents import AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

def page_exploration_agent(model, tools):
    """页面探索Agent
    
    职责：
    1. 理解探索目标和范围
    2. 决策下一步访问哪个页面
    3. 调用tools进行页面快照和缓存检查
    4. 生成页面产物
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", EXPLORATION_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ])
    
    return AgentExecutor(
        agent=create_react_agent(model, tools, prompt),
        tools=tools,
        verbose=True,
    )
```

#### 2.4 创建Service层
```python
# agents/page_exploration/service.py
async def start_exploration_run(
    run_id: str,
    project_id: str,
    config: ExplorationConfig
) -> None:
    """启动探索任务（异步后台任务）"""
    
    # 1. 更新run状态为running
    with connect() as db:
        exploration_run_repo.update_status(db, run_id, "running")
    
    # 2. 创建Agent
    model = build_agent_model(resolve_model_selection("page_exploration"))
    tools = [
        playwright_snap_tool,
        playwright_navigate_tool,
        check_explored_url_tool,
        write_page_artifact_tool,
    ]
    agent = page_exploration_agent(model, tools)
    
    # 3. 执行探索（循环直到完成）
    queue = ExplorationQueue(config.start_url, config.scope, config.max_depth)
    
    while not queue.is_empty():
        url, depth = queue.pop()
        
        # Agent决策并执行
        result = await agent.ainvoke({
            "messages": [{
                "role": "user",
                "content": f"探索页面: {url}, 深度: {depth}"
            }],
            "run_id": run_id,
            "project_id": project_id,
        })
        
        # 发现新链接，加入队列
        for link in result.get("discovered_links", []):
            queue.push(link, depth + 1)
    
    # 4. 完成，更新状态
    with connect() as db:
        exploration_run_repo.update_status(db, run_id, "completed")
```

---

### Phase 3: Service层

**目标**: 创建业务逻辑服务层

#### 3.1 页面探索服务
```python
# services/exploration/page_exploration_service.py

def create_exploration_run(
    actor,
    project_id: str,
    request: CreateExplorationRequest
) -> dict:
    """创建探索任务"""
    run_id = f"exp_{secrets.token_urlsafe(16)}"
    
    with connect() as db:
        exploration_run_repo.create(
            db,
            run_id=run_id,
            project_id=project_id,
            created_by=actor["id"],
            **request.dict()
        )
    
    # 启动后台任务
    task_service.start_background_task(
        task_id=run_id,
        module="page_exploration",
        description=f"探索: {request.start_url}",
        callback=lambda: start_exploration_run(run_id, project_id, request)
    )
    
    return {"run_id": run_id, "status": "pending"}

def get_exploration_run(actor, run_id: str) -> dict:
    """获取探索任务详情"""
    with connect() as db:
        run = exploration_run_repo.find_by_id(db, run_id)
        if not run:
            raise ValueError("探索任务不存在")
        
        urls = explored_url_repo.list_by_run(db, run_id)
        
        return {
            "run": dict(run),
            "urls": [dict(u) for u in urls],
        }

def list_exploration_runs(actor, project_id: str) -> list[dict]:
    """列出探索任务"""
    with connect() as db:
        runs = exploration_run_repo.list_by_project(db, project_id)
        return [dict(r) for r in runs]
```

#### 3.2 产物管理服务
```python
# services/exploration/artifact_service.py

def write_page_artifact(
    project_id: str,
    run_id: str,
    url: str,
    snapshot: SnapshotResult
) -> Path:
    """写入页面产物（YAML文件 + 数据库记录）"""
    
    # 1. 生成YAML文件
    artifact_dir = Path(f"projects/{project_id}/explorations/{run_id}")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    normalized_url = normalize_url(url)
    page_id = f"page-{normalized_url.strip('/').replace('/', '-')}"
    artifact_path = artifact_dir / f"{page_id}.yaml"
    
    yaml_content = {
        "page_id": page_id,
        "url": url,
        "normalized_url": normalized_url,
        "title": snapshot.title,
        "elements": [e.dict() for e in snapshot.elements],
    }
    
    artifact_path.write_text(yaml.dump(yaml_content))
    
    # 2. 更新数据库
    with connect() as db:
        explored_url_repo.update_artifact(
            db,
            run_id=run_id,
            normalized_url=normalized_url,
            artifact_path=str(artifact_path),
            status="completed"
        )
    
    return artifact_path
```

---

### Phase 4: API层

**目标**: 遵循现有API规范，统一路由设计

#### 4.1 API路由
```python
# api/v1/page_exploration.py
from fastapi import APIRouter, Depends, Query
from app.dependencies.auth import current_user
from app.services.exploration import page_exploration_service

router = APIRouter(prefix="/page-exploration", tags=["page-exploration"])

@router.post("/runs")
def create_exploration_run(
    request: CreateExplorationRequest,
    actor=Depends(current_user)
) -> dict:
    """创建页面探索任务"""
    return page_exploration_service.create_exploration_run(
        actor,
        request.project_id,
        request
    )

@router.get("/runs/{run_id}")
def get_exploration_run(
    run_id: str,
    actor=Depends(current_user)
) -> dict:
    """获取探索任务详情"""
    return page_exploration_service.get_exploration_run(actor, run_id)

@router.get("/runs")
def list_exploration_runs(
    project_id: str = Query(...),
    actor=Depends(current_user)
) -> list[dict]:
    """列出探索任务"""
    return page_exploration_service.list_exploration_runs(actor, project_id)

@router.get("/runs/{run_id}/artifacts")
def list_artifacts(
    run_id: str,
    actor=Depends(current_user)
) -> list[dict]:
    """列出探索产物"""
    return page_exploration_service.list_artifacts(actor, run_id)
```

#### 4.2 注册路由
```python
# api/v1/__init__.py
from app.api.v1 import page_exploration

v1_router.include_router(page_exploration.router)
```

---

### Phase 5: 实时进度（SSE）

**目标**: 使用现有的任务系统或添加SSE支持

#### 选项1: 使用现有task_service
```python
# 利用现有的task_service.list_running_tasks()
@router.get("/runs/{run_id}/status")
def get_run_status(run_id: str, actor=Depends(current_user)):
    # 从task_service获取任务状态
    task = task_service.get_task_status(run_id)
    
    # 从数据库获取详细进度
    with connect() as db:
        run = exploration_run_repo.find_by_id(db, run_id)
        urls = explored_url_repo.list_by_run(db, run_id)
    
    return {
        "run": dict(run),
        "task_status": task,
        "progress": {
            "discovered": len(urls),
            "completed": len([u for u in urls if u["status"] == "completed"]),
            "failed": len([u for u in urls if u["status"] == "failed"]),
        }
    }
```

#### 选项2: 添加SSE支持（如果需要实时性）
```python
@router.get("/runs/{run_id}/events")
async def stream_exploration_events(run_id: str):
    async def event_generator():
        # 实现SSE流
        pass
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

---

### Phase 6: 前端集成

**目标**: 将页面探索功能集成到现有前端

#### 6.1 API客户端
```typescript
// src/api/pageExplorationAPI.ts
export class PageExplorationAPI {
  async createRun(request: CreateExplorationRequest): Promise<ExplorationRun> {
    const response = await fetch('/api/v1/page-exploration/runs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(request),
    });
    return response.json();
  }
  
  async getRun(runId: string): Promise<ExplorationRunDetail> {
    const response = await fetch(`/api/v1/page-exploration/runs/${runId}`);
    return response.json();
  }
  
  async listRuns(projectId: string): Promise<ExplorationRun[]> {
    const response = await fetch(
      `/api/v1/page-exploration/runs?project_id=${projectId}`
    );
    return response.json();
  }
}
```

#### 6.2 集成到项目页面
- 在项目详情页添加"页面探索"标签页
- 显示探索任务列表
- 创建探索任务表单
- 查看探索结果和产物

---

## 🔄 迁移计划

### Step 1: 保留可复用部分
```bash
# 保留
agents/page_exploration/playwright/     # ✅ Playwright基础设施
agents/page_exploration/tools/          # ✅ LangChain工具（需优化）
agents/page_exploration/utils/          # ✅ 工具函数
```

### Step 2: 重构核心部分
```bash
# 重构
agents/page_exploration/orchestrator.py     # ❌ 删除，逻辑移到service.py
agents/page_exploration/event_emitter.py    # ❌ 删除，使用task_service
agents/page_exploration/exploration_queue.py # ⚠️  简化，移到service.py
agents/page_exploration/artifact_service.py  # ⚠️  重构，移到services/exploration/
```

### Step 3: 新建缺失部分
```bash
# 新建
repositories/exploration_run_repo.py
repositories/explored_url_repo.py
services/exploration/page_exploration_service.py
api/v1/page_exploration.py
```

### Step 4: 数据库迁移
```bash
# 创建迁移脚本
app/migrations/create_exploration_tables.py
```

---

## 📊 对比总结

| 维度 | 之前的实现 | 重构后 |
|------|-----------|--------|
| **数据持久化** | 文件系统（YAML） | SQLite数据库 + 文件系统 |
| **任务管理** | 自定义EventEmitter | 使用task_service |
| **API设计** | 独立路由 | 遵循v1 API规范 |
| **Repository** | 无 | 标准Repository模式 |
| **Service层** | Agent直接调用 | 清晰的Service层 |
| **认证授权** | 无 | current_user依赖注入 |
| **项目关联** | 文件路径 | 数据库外键 |
| **前端集成** | 独立页面 | 集成到项目页面 |

---

## ⏱️ 实施时间估算

| Phase | 任务 | 预估时间 |
|-------|------|---------|
| Phase 1 | 数据库Schema + Repository | 2小时 |
| Phase 2 | Agent层重构 | 3小时 |
| Phase 3 | Service层 | 2小时 |
| Phase 4 | API层 | 1小时 |
| Phase 5 | 实时进度（可选） | 2小时 |
| Phase 6 | 前端集成 | 3小时 |
| **总计** | | **13小时** |

---

## ✅ 验收标准

1. **数据库集成**: 所有探索任务和URL存储在SQLite
2. **API统一**: 遵循`/api/v1/`规范，使用`current_user`
3. **任务管理**: 使用`task_service`管理后台任务
4. **Repository模式**: 所有数据库操作通过Repository
5. **Service层**: 清晰的业务逻辑分层
6. **测试**: 100%测试覆盖（Repository + Service + API）
7. **前端集成**: 集成到现有项目页面

---

## 🎯 下一步行动

**请确认以下问题**:

1. ✅ 是否认可这个重构方案？
2. ✅ 是否需要保留SSE实时推送功能？（或使用轮询）
3. ✅ 前端是否集成到项目页面？（或独立页面）
4. ✅ 是否需要查看现有数据库Schema再开始？

**确认后，我将开始Phase 1实施。**
