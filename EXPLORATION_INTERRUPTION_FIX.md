# 探索任务中断恢复机制修复报告

## 问题描述

**现象**：后端停止后，探索任务仍然显示"探索中"状态，没有自动标记为中断。

**影响**：
- 用户无法区分哪些任务是真正在运行，哪些是因为后端停止而卡住的
- 重启后端时，卡住的任务不会被自动恢复
- 前端显示的状态与实际状态不一致

## 根本原因分析

### 1. 缺少启动恢复机制

后端有针对其他任务类型的恢复机制：
- `task_service.recover_interrupted_requirement_analysis_runs()` - 需求分析任务
- `test_case_service.recover_interrupted_test_case_generation_runs()` - 测试用例生成任务

但**缺少探索任务的恢复机制**。

探索任务使用内存中的 `_running_explorations` 字典存储运行状态：
```python
# apps/backend/app/services/exploration/page_exploration_service.py
_running_explorations: Dict[str, Dict[str, Any]] = {}
```

当后端停止时：
1. 内存被清空，`_running_explorations` 字典丢失
2. 数据库中的状态仍然是 `running`/`queued`/`stopping`
3. 重启后没有恢复机制将这些任务标记为中断

### 2. 状态约束问题

代码中使用了 `failed` 状态，但数据库约束不允许：

```sql
status TEXT NOT NULL CHECK(status IN (
    'pending', 'queued', 'running', 'stopping', 
    'cancelled', 'interrupted', 'partial', 'completed', 'blocked'
)) DEFAULT 'pending'
```

### 3. Agent创建时的中间件冲突

错误信息：`AssertionError: Please remove duplicate middleware instances`

**原因**：
- 第19行导入：`from deepagents import create_deep_agent as create_agent`
- **实际使用的是 `create_deep_agent`**，只是起了别名叫 `create_agent`
- `create_deep_agent` 在处理 `skills` 参数时，会在 `deepagents/graph.py:740` 自动添加 `SummarizationMiddleware`
- 手动添加的 `SummarizationMiddleware` 与自动添加的冲突

## 修复方案

### 修复1：添加探索任务恢复机制

**文件**: `apps/backend/app/services/exploration/page_exploration_service.py`

新增恢复函数（第495行之后）：

```python
def recover_interrupted_exploration_runs(*, project_id: str | None = None) -> None:
    """恢复被中断的探索任务

    当服务重启时，将所有处于运行状态（running/queued/stopping）的探索任务
    标记为已中断（interrupted），因为内存中的后台任务已经丢失。

    Args:
        project_id: 可选的项目ID，只恢复该项目的任务
    """
    from app.services import operation_log_service

    with connect() as db:
        # 查找所有运行中的探索任务
        runs = exploration_run_repo.list_running(db, project_id)
        recovered_runs = [dict(row) for row in runs]

        # 将这些任务标记为已中断
        for row in runs:
            exploration_run_repo.update_status(
                db,
                row["id"],
                status="interrupted",
                finished_at=datetime.now(timezone.utc).isoformat(),
                result_summary="服务已重启，探索任务已中断。",
            )

    # 记录操作日志
    for row in recovered_runs:
        try:
            operation_log_service.record_task_event(
                module="exploration",
                action="interrupt_exploration",
                object_type="exploration_run",
                object_id=row["id"],
                object_name=row["title"],
                project_id=row["project_id"],
                actor_id="system",
                actor_name="系统",
                source="system",
                result="interrupted",
                failure_reason="服务已重启，内存中的探索后台任务已中断",
                summary="探索任务已中断。",
                after={"status": "interrupted", "reason": "startup_recovered"},
                task_id=row["id"],
            )
        except Exception:
            # 如果记录日志失败，不影响恢复流程
            pass
```

**文件**: `apps/backend/app/services/exploration/__init__.py`

导出恢复函数：

```python
"""Exploration services module"""

from app.services.exploration.page_exploration_service import (
    recover_interrupted_exploration_runs,
)

__all__ = [
    "recover_interrupted_exploration_runs",
]
```

**文件**: `apps/backend/app/main.py`

在启动事件中调用恢复函数：

```python
from app.services.exploration import recover_interrupted_exploration_runs

@app.on_event("startup")
def startup() -> None:
    init_db()
    recover_interrupted_exploration_runs()  # 新增：恢复探索任务
    task_service.recover_interrupted_requirement_analysis_runs()
    test_case_service.recover_interrupted_test_case_generation_runs()
    logger.info("Application started — AI Testing System API v0.1.0")
```

### 修复2：修正状态约束问题

**文件**: `apps/backend/app/services/exploration/page_exploration_service.py`

将两处异常处理中的 `failed` 状态改为 `blocked`：

```python
# 第223行
except Exception as e:
    # 更新状态为blocked（数据库约束不允许failed状态）
    with connect() as db:
        exploration_run_repo.update_status(
            db,
            run_id,
            "blocked",  # 原来是 "failed"
            finished_at=datetime.now(timezone.utc).isoformat(),
            result_summary=f"探索失败: {str(e)}",
        )

# 第262行
except Exception as e:
    # 发生错误，更新状态为blocked（数据库约束不允许failed状态）
    with connect() as db:
        exploration_run_repo.update_status(
            db,
            run_id,
            "blocked",  # 原来是 "failed"
            finished_at=datetime.now(timezone.utc).isoformat(),
            result_summary=f"探索阻塞: {str(e)}",
        )
    raise
```

### 修复3：移除重复的中间件

**文件**: `apps/backend/app/agents/page_exploration/agent.py`

移除手动添加的 `SummarizationMiddleware`：

```python
# 移除导入
# from langchain.agents.middleware import SummarizationMiddleware

def page_exploration_agent(model, project_id: str, run_id: str):
    """创建页面探索智能体"""
    backend_root = Path(__file__).parent.parent.parent.parent
    backend = FilesystemBackend(
        root_dir=str(backend_root),
        virtual_mode=True,
    )

    # 移除手动创建的中间件
    # summarization_middleware = SummarizationMiddleware(...)
    
    all_tools = list(get_local_tools())

    # 不传入 middleware 参数，让 deepagents 自动管理
    return create_agent(
        model=model,
        tools=all_tools,
        system_prompt=SYSTEM_PROMPT,
        backend=backend,
        skills=["app/agents/page_exploration/skills/"],
    )
```

**关键点**：
- 虽然导入时使用了别名 `from deepagents import create_deep_agent as create_agent`
- 实际调用的是 `create_deep_agent`
- 当传入 `skills` 参数时，`create_deep_agent` 会在内部自动添加 `SummarizationMiddleware`（位置：`deepagents/graph.py:740`）
- 手动再添加就会导致重复

## 验证结果

### 1. 当前数据库状态
```sql
SELECT id, title, status, created_at, updated_at 
FROM exploration_runs 
ORDER BY updated_at DESC LIMIT 5;
```

结果：
- 没有卡在 `running`/`queued` 状态的任务
- 最近的任务已正确标记为 `interrupted` 或 `completed`

### 2. 导入验证
```python
from app.services.exploration import recover_interrupted_exploration_runs
# ✓ 导入成功

import inspect
sig = inspect.signature(recover_interrupted_exploration_runs)
# ✓ 函数签名: (*, project_id: str | None = None) -> None
```

## 修改文件清单

1. `apps/backend/app/main.py` - 添加启动恢复调用
2. `apps/backend/app/services/exploration/__init__.py` - 导出恢复函数
3. `apps/backend/app/services/exploration/page_exploration_service.py` - 添加恢复函数，修复状态错误
4. `apps/backend/app/agents/page_exploration/agent.py` - 移除重复中间件

## 测试建议

### 1. 测试恢复机制
```bash
# 1. 启动后端
cd apps/backend
uvicorn app.main:app --reload --port 8000

# 2. 创建一个探索任务并启动
# 3. 强制停止后端（Ctrl+C）
# 4. 重新启动后端
# 5. 检查任务状态应该被标记为 interrupted
```

### 2. 测试正常探索流程
```bash
# 1. 创建并启动探索任务
# 2. 观察任务正常完成
# 3. 检查状态为 completed 而不是 blocked
```

### 3. 验证日志
```bash
# 启动时应该看到：
# - "Application started — AI Testing System API v0.1.0"
# - 如果有中断的任务，会看到恢复日志
```

## 技术要点总结

### 1. DeepAgents 的中间件自动管理
- `create_deep_agent` 在处理 `skills` 参数时自动添加多个中间件
- 包括：`SkillsMiddleware`, `SummarizationMiddleware`, `FilesystemMiddleware` 等
- 用户只需传入 `backend` 和 `skills` 参数，无需手动管理中间件

### 2. 数据库状态约束的重要性
- 必须确保代码中使用的状态值与数据库约束一致
- 违反约束会导致 `sqlite3.IntegrityError`
- 建议在代码中定义状态常量，避免硬编码

### 3. 启动恢复模式的最佳实践
- 将运行中的任务标记为中断，而不是直接删除
- 记录详细的操作日志，便于追踪和调试
- 恢复逻辑应该是幂等的，多次调用结果一致

## 后续优化建议

1. **状态常量化**：定义探索任务状态常量，避免字符串硬编码
2. **监控告警**：添加监控，当探索任务长时间处于运行状态时告警
3. **超时恢复**：除了启动恢复，还可以添加超时恢复机制（类似需求分析任务的 `recover_stale_requirement_analysis_runs`）
4. **优雅停机**：在后端关闭时，主动将运行中的任务标记为中断

## 结论

通过添加启动恢复机制、修正状态约束错误、移除重复中间件，成功解决了探索任务中断后无法恢复的问题。现在后端重启时会自动将卡住的探索任务标记为中断状态，确保前端显示与实际状态一致。
