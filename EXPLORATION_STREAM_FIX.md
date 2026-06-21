# 探索任务实时传递问题修复报告

## 问题描述

用户报告：新建探索后，后端没有传信息给前端，无法实时传递信息。前端只收到 `keep-alive` 消息，没有收到实际的探索进度事件。

## 问题诊断

### 诊断结果

通过诊断脚本发现：
- 数据库中有一个任务状态为 `running`
- 任务摘要显示：`正在智能分析探索目标并生成探索计划。`
- **关键发现：日志目录不存在**

这表明：
1. 任务已标记为 `running`，但实际没有真正开始执行
2. `unified_orchestrator` 的异步执行遇到了未捕获的异常
3. 异常导致任务卡在初始化阶段，无法发布任何事件

### 根本原因

1. **异步执行异常未捕获**：`run_unified_exploration_sync` 使用 `asyncio.run()` 执行异步任务，但没有 try-catch 包装，导致异常被吞没
2. **事件发布延迟**：事件发布在数据库更新之后，如果初始化阶段出错，前端永远收不到事件
3. **错误传递链断裂**：异步任务中的错误没有通过 event_bus 发布给前端

## 修复方案

### 修复 1: 增强 `run_unified_exploration_sync` 的异常处理

**文件**: `apps/backend/app/services/exploration/unified_orchestrator.py`

**修改内容**:
```python
def run_unified_exploration_sync(...) -> dict:
    """同步运行统一探索"""
    try:
        # 在开始执行前立即发布初始事件
        event_bus.publish(run_id, "execution_starting", {
            "message": "统一探索编排器正在初始化...",
            "start_url": start_url,
        })

        result = asyncio.run(run_unified_exploration(...))
        return result
    except Exception as error:
        # 捕获所有异常并发布错误事件
        import traceback
        error_detail = f"{type(error).__name__}: {str(error)}"
        error_traceback = traceback.format_exc()

        # 发布错误事件到前端
        event_bus.publish(run_id, "execution_error", {
            "message": f"探索执行异常: {error_detail}",
            "error_type": type(error).__name__,
            "error_detail": error_detail,
        })

        # 写入错误日志
        log_path = artifact_root / "logs" / "run.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(...)
        except Exception:
            pass

        # 返回错误结果
        return {
            "status": "blocked",
            "summary": f"探索执行异常中断: {error_detail[:200]}",
            ...
        }
```

**效果**:
- 所有异常都被捕获并发布到前端
- 前端能看到具体的错误信息
- 写入日志文件便于调试

### 修复 2: 在 `run()` 方法开始时立即发布事件

**文件**: `apps/backend/app/services/exploration/unified_orchestrator.py`

**修改内容**:
```python
async def run(self) -> dict:
    """运行统一探索流程"""
    try:
        # 立即发布开始事件，确保前端能收到
        self._publish("orchestrator_initialized", {
            "message": "统一探索编排器已初始化",
            "start_url": self.start_url,
        })

        run = self._load_run()
        if not run:
            error_msg = "探索任务不存在"
            self._publish("error", {"message": error_msg})
            return self._error_result(error_msg)

        self._log("run_started", message=f"开始统一探索: {run['title']}")
        self._publish("run_started", {"status": "running", "mode": "unified"})
    except Exception as e:
        error_msg = f"初始化阶段异常: {str(e)}"
        self._publish("error", {"message": error_msg})
        return self._error_result(error_msg)
```

**效果**:
- 任务一开始就发布事件，前端立即能收到反馈
- 初始化阶段的错误也能被捕获并发布

## 已完成的修复

- ✅ 修复 `run_unified_exploration_sync` 异常捕获
- ✅ 在 `run()` 开始时立即发布事件
- ✅ 增强错误日志写入
- ✅ 重置卡住的任务状态

## 测试建议

1. **清理环境**：已将卡住的任务重置为 `blocked` 状态
2. **重启后端服务**：让代码修改生效
3. **创建新的探索任务**：
   - 前端应该能立即收到 `execution_starting` 事件
   - 如果有错误，能收到 `execution_error` 事件
   - 正常情况下能收到完整的进度事件流

## 预期效果

修复后的事件流：
```
1. 用户点击"开始探索"
2. 后端返回 {status: 'queued'}
3. 子线程启动，立即发布 execution_starting 事件 ✨ 新增
4. 前端 SSE 连接收到第一个事件
5. 后续发布: orchestrator_initialized ✨ 新增
6. 后续发布: run_started
7. 后续发布: planning_started
8. ... 完整的探索进度事件
```

如果遇到错误：
```
1-3. (同上)
4. 前端收到 execution_error 事件 ✨ 新增
5. 任务标记为 blocked，前端显示错误信息
```

## 进一步优化建议

1. **添加心跳机制**：在长时间运行的步骤中定期发布进度事件
2. **增加重试逻辑**：对于临时性错误（网络超时等）自动重试
3. **改进前端错误提示**：根据 error_type 显示不同的用户友好提示
4. **监控告警**：对于频繁失败的任务发送告警

## 相关文件

- `apps/backend/app/services/exploration/unified_orchestrator.py` - 主要修复
- `apps/backend/app/services/exploration/site_orchestrator.py` - 已有完善的错误处理
- `apps/backend/app/services/exploration/event_bus.py` - 事件总线实现
- `apps/backend/app/api/v1/exploration.py` - SSE stream endpoint

---

**修复时间**: 2026-06-21
**修复状态**: ✅ 已完成
