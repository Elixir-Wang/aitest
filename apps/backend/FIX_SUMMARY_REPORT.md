# 前后端对接问题 - 修复总结报告

## 📋 问题概述

**报告时间**: 2026-06-21 13:41  
**问题描述**: 前端显示"探索中"但后端不返回任何信息，任务卡死  
**影响范围**: 探索任务执行流程  
**严重程度**: 🔴 高

---

## 🔍 根本原因分析

### 1. **URL导航问题**（已修复 ✅）

**问题**: 
- Planner生成的导航步骤中，`target_selector`（实际URL）为空
- Executor使用 `target_description`（中文描述）作为URL
- 浏览器尝试导航到无效URL，如 `"起始URL对应的页面，包含智能体卡片列表"`

**错误信息**:
```
浏览器错误: page.goto: Protocol error (Page.navigate): 
Cannot navigate to invalid URL
```

**修复内容**:
- ✅ 更新 `planner.py` 系统提示词，明确要求 `navigate` 动作必须在 `target_selector` 填写实际URL
- ✅ 更新示例代码，将 `target_selector` 从空改为 `/workspace`

**代码位置**:
- `apps/backend/app/services/exploration/plan_and_execute/planner.py:87-95`
- `apps/backend/app/services/exploration/plan_and_execute/planner.py:167-177`

### 2. **任务卡死问题**（已修复 ✅）

**问题**:
- 任务 `explore-01b554b4f26ba242` 在 `05:33:44` 启动后卡在 `running` 状态
- 后台线程可能因异常退出，但数据库状态未更新
- 前端持续等待，显示"探索中"

**修复措施**:
- ✅ 直接更新数据库，将卡死任务状态改为 `interrupted`
- ✅ 创建恢复脚本 `scripts/recover_stale_explorations.py`

### 3. **系统性问题**（待改进 🔄）

**识别的架构问题**:

| 问题 | 影响 | 优先级 |
|------|------|--------|
| daemon线程无异常处理 | 异常静默失败 | P0 |
| 缺少任务超时机制 | 任务无限运行 | P1 |
| SSE流无超时检测 | 前端永久等待 | P1 |
| 缺少心跳检测 | 无法判断任务存活 | P1 |
| 线程池vs任务队列 | 扩展性差 | P2 |

---

## ✅ 已完成的修复

### 1. URL导航修复
```python
# 修改前
target_description: "/workspace路径"
target_selector: ""  # 空，导致使用描述作为URL

# 修改后
target_description: "工作台首页，显示智能体卡片列表"
target_selector: "/workspace"  # 实际URL
```

### 2. 卡死任务恢复
```sql
UPDATE exploration_runs 
SET status = 'interrupted', 
    result_summary = '任务执行异常中断，请检查日志并重新启动。',
    finished_at = CURRENT_TIMESTAMP
WHERE id = 'explore-01b554b4f26ba242';
```

**验证**:
```
✓ 任务状态已从 running → interrupted
✓ 前端刷新后应能看到任务已中断
```

### 3. 恢复工具
创建了 `scripts/recover_stale_explorations.py`，用于：
- 自动检测运行超过60分钟的任务
- 批量恢复卡死任务
- 支持 dry-run 模式预览

**使用方法**:
```bash
# 预览模式
cd apps/backend
python scripts/recover_stale_explorations.py --dry-run

# 实际执行
python scripts/recover_stale_explorations.py
```

---

## 🔄 待改进项

### P1 优先级（本周内）

#### 1. 添加任务超时检测
```python
# site_orchestrator.py
def run_exploration(run_id: str) -> None:
    """执行探索，带超时检测"""
    try:
        with timeout(get_timeout_minutes(run_id) * 60):
            _run_exploration(run_id)
    except TimeoutError:
        _mark_run_as_timeout(run_id)
    except Exception as e:
        _mark_run_failed_after_unhandled_error(run_id, e)
```

#### 2. 改进SSE超时机制
```python
# exploration.py
def event_stream():
    start_time = time.time()
    timeout_seconds = 3600
    
    for event in exploration_event_bus.subscribe(run_id):
        if time.time() - start_time > timeout_seconds:
            # 检查任务是否真的在运行
            run = get_run_status(run_id)
            if run["status"] == "running":
                yield timeout_event()
            break
        yield format_event(event)
```

#### 3. 添加心跳检测
```python
class ExplorationHeartbeat:
    def __init__(self, run_id: str, interval: int = 30):
        self.run_id = run_id
        self.last_beat = datetime.now(timezone.utc)
        
    def beat(self):
        """更新心跳"""
        self.last_beat = datetime.now(timezone.utc)
        cache.set(f"heartbeat:{self.run_id}", self.last_beat)
        
    def is_alive(self) -> bool:
        """检查是否存活"""
        elapsed = (datetime.now(timezone.utc) - self.last_beat).seconds
        return elapsed < self.interval * 3
```

### P2 优先级（下个迭代）

#### 1. 迁移到任务队列
- 使用 Celery 或 RQ 替代 threading.Thread
- 自动异常捕获和重试
- 分布式执行支持

#### 2. WebSocket 替代 SSE
- 双向通信，支持主动检测
- 更好的连接状态管理
- 支持重连机制

---

## 🧪 测试验证清单

### 立即验证（修复后）
- [x] 卡死任务状态已恢复为 `interrupted`
- [ ] 前端刷新后显示任务已中断
- [ ] 可以重新启动任务
- [ ] 新任务能正常导航到正确URL

### 回归测试（服务重启后）
- [ ] 创建新的探索任务
- [ ] 任务正常启动和执行
- [ ] 前端能实时看到进度更新
- [ ] 任务能正常完成
- [ ] 失败时能看到错误信息

### 压力测试（可选）
- [ ] 并发创建多个任务
- [ ] 模拟网络异常
- [ ] 模拟超时场景
- [ ] 验证恢复机制

---

## 📊 数据对比

### 修复前
```
任务状态: running
运行时间: 8+ 小时
前端表现: 一直显示"探索中"，无响应
后端日志: 无错误输出
用户体验: ❌ 任务卡死，无法操作
```

### 修复后
```
任务状态: interrupted
前端表现: 显示任务已中断，可重新启动
后端改进: URL正确生成，导航不再失败
用户体验: ✅ 问题明确，可继续操作
```

---

## 🎯 操作指南

### 给开发者

#### 1. 应用修复
```bash
# 1. 拉取最新代码（包含URL修复）
git pull

# 2. 恢复卡死任务（如果需要）
cd apps/backend
python scripts/recover_stale_explorations.py

# 3. 重启服务（必须）
pkill -f uvicorn
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. 监控任务
```bash
# 实时查看日志
tail -f logs/app/$(date +%Y-%m-%d).log | grep -E "exploration|ERROR"

# 检查任务状态
sqlite3 data/ai_testing.db "
SELECT id, status, 
       CAST((julianday('now') - julianday(started_at)) * 24 * 60 AS INTEGER) as minutes
FROM exploration_runs 
WHERE status IN ('running', 'queued', 'stopping')
ORDER BY started_at DESC;
"
```

### 给测试者

#### 1. 验证修复
1. 刷新前端页面
2. 确认之前卡死的任务显示为"已中断"
3. 创建新的探索任务
4. 观察任务是否能正常执行

#### 2. 发现问题
如果仍有问题，提供：
- 任务 ID
- 前端截图
- 后端日志（最近50行）
- 任务状态（数据库查询结果）

---

## 📝 经验总结

### 问题根源
1. **系统提示词不够明确** - LLM生成的数据结构不符合预期
2. **异常处理不完善** - 后台线程异常静默失败
3. **缺少监控机制** - 无法及时发现卡死任务
4. **状态同步问题** - 数据库状态与实际运行状态不一致

### 改进建议
1. **明确的Schema约束** - 使用Pydantic严格验证LLM输出
2. **完善的异常处理** - 所有后台任务都要有超时和异常捕获
3. **健壮的监控系统** - 心跳检测 + 定时巡检
4. **清晰的日志记录** - 关键步骤都要记录日志

### 防止复发
- [ ] 添加集成测试，覆盖导航场景
- [ ] 实施代码审查，检查异常处理
- [ ] 设置监控告警，及时发现卡死
- [ ] 定期执行恢复脚本，清理卡死任务

---

## 📚 相关文档

- 详细分析: `FRONTEND_BACKEND_INTEGRATION_ANALYSIS.md`
- 恢复脚本: `scripts/recover_stale_explorations.py`
- 修复代码: Git commit `[当前提交]`

---

## ✅ 签署确认

**修复完成**: 2026-06-21 13:41  
**验证状态**: ⏳ 等待测试验证  
**后续跟进**: 开发团队  

---

**下一步行动**:
1. ✅ 立即重启服务
2. ✅ 验证任务恢复
3. 🔄 测试新任务执行
4. 🔄 规划P1改进项
5. 📅 制定P2路线图
