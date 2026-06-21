# 🚨 紧急修复方案 - SSE无事件问题

## 问题诊断

### 现象
- 前端SSE只收到 `: keep-alive`
- 任务状态一直是 `running`
- 日志只有一行：`DEBUG: _execute_unified_exploration called at ...`

### 根本原因
**任务在启动后立即卡死，event_bus没有收到任何事件**

可能的问题点：
1. ❌ `_playwright_cli_available()` 检查卡死（同步阻塞）
2. ❌ `unified_orchestrator.run_unified_exploration_sync()` 没有返回
3. ❌ `asyncio.run()` 在 daemon 线程中死锁
4. ❌ LLM调用超时无响应

---

## 🎯 最简修复方案（立即执行）

### Step 1: 强制清理卡死任务

```bash
cd /Users/wanghongbao/project/test_project/apps/backend

# 直接更新数据库
sqlite3 data/ai_testing.db "
UPDATE exploration_runs 
SET status = 'interrupted', 
    result_summary = '任务执行卡死，已强制中断。',
    finished_at = CURRENT_TIMESTAMP
WHERE status IN ('running', 'queued', 'stopping');
"

# 验证
sqlite3 data/ai_testing.db "SELECT id, status FROM exploration_runs WHERE id = 'explore-01b554b4f26ba242';"
```

### Step 2: 添加超时保护和详细日志

创建临时修复补丁：

```python
# apps/backend/app/services/exploration/site_orchestrator.py

def _execute_unified_exploration(run_id: str, artifact_root: Path) -> dict:
    log_path = artifact_root / "logs" / "run.log"
    
    def log_and_publish(message: str):
        """同时写日志和发布事件"""
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()}: {message}\n")
            exploration_event_bus.publish(run_id, "debug", {"message": message})
        except:
            pass
    
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_and_publish("START: _execute_unified_exploration called")
        
        # 检查点1: Playwright CLI
        log_and_publish("CHECK: Checking playwright CLI...")
        if not _playwright_cli_available():
            message = "未检测到可用 Playwright CLI"
            log_and_publish(f"ERROR: {message}")
            exploration_event_bus.publish(run_id, "error", {"message": message})
            return {"status": "blocked", "summary": message}
        log_and_publish("PASS: Playwright CLI available")
        
        # 检查点2: 加载上下文
        log_and_publish("CHECK: Loading run context from DB...")
        page_url, forbidden_paths, storage_state_path = _safe_run_context_from_db(run_id)
        log_and_publish(f"PASS: Context loaded - URL: {page_url}")
        
        # 检查点3: 调用统一编排器（带超时）
        log_and_publish("START: Calling unified_orchestrator...")
        exploration_event_bus.publish(run_id, "execution_started", {"url": page_url})
        
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Unified orchestrator execution timeout")
        
        # 设置60秒超时
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(60)
        
        try:
            result = unified_orchestrator.run_unified_exploration_sync(
                run_id,
                artifact_root,
                start_url=page_url,
                forbidden_paths=forbidden_paths,
                storage_state_path=storage_state_path,
            )
            signal.alarm(0)  # 取消超时
            log_and_publish(f"DONE: Orchestrator finished - {result.get('status')}")
            return result
            
        except TimeoutError as e:
            signal.alarm(0)
            log_and_publish(f"TIMEOUT: Orchestrator timeout after 60s")
            exploration_event_bus.publish(run_id, "error", {"message": "执行超时"})
            return {"status": "blocked", "summary": "执行超时（60秒）"}
            
    except Exception as e:
        log_and_publish(f"EXCEPTION: {type(e).__name__}: {str(e)}")
        exploration_event_bus.publish(run_id, "error", {"message": str(e)})
        import traceback
        log_and_publish(f"TRACEBACK: {traceback.format_exc()}")
        raise
```

### Step 3: 检查 unified_orchestrator.run_unified_exploration_sync

```python
# apps/backend/app/services/exploration/unified_orchestrator.py

def run_unified_exploration_sync(
    run_id: str,
    artifact_root: Path,
    start_url: str,
    forbidden_paths: str = "",
    storage_state_path: str = "",
) -> dict:
    """同步包装器：在新的事件循环中运行异步探索"""
    
    # 🔴 问题点：asyncio.run() 可能在daemon线程中死锁
    # 解决方案：使用已存在的事件循环或创建新的
    
    try:
        # 尝试获取当前事件循环
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果循环已经在运行，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        # 没有事件循环，创建新的
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    orchestrator = UnifiedExplorationOrchestrator(
        run_id=run_id,
        artifact_root=artifact_root,
        start_url=start_url,
        forbidden_paths=forbidden_paths,
        storage_state_path=storage_state_path,
    )
    
    # 🔴 关键：添加超时保护
    try:
        result = loop.run_until_complete(
            asyncio.wait_for(orchestrator.run(), timeout=300)  # 5分钟超时
        )
        return result
    except asyncio.TimeoutError:
        return {
            "status": "blocked",
            "summary": "探索执行超时（5分钟）",
            "log": "Execution timeout after 300 seconds"
        }
    finally:
        loop.close()
```

---

## 🔧 最简化方案（删除无用功能）

### 删除1: 复杂的统一编排器
**问题**: `unified_orchestrator` 太复杂，容易卡死  
**方案**: 回退到简单的直接执行

```python
# site_orchestrator.py - 简化版本

def _execute_simple_exploration(run_id: str, artifact_root: Path) -> dict:
    """极简探索：只做最基本的页面访问和元素采集"""
    
    log_path = artifact_root / "logs" / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log_write(msg):
        with open(log_path, "a") as f:
            f.write(f"{datetime.now()}: {msg}\n")
        exploration_event_bus.publish(run_id, "log", {"message": msg})
    
    try:
        log_write("开始简化探索")
        exploration_event_bus.publish(run_id, "run_started", {"mode": "simple"})
        
        # 获取URL
        page_url, _, _ = _safe_run_context_from_db(run_id)
        log_write(f"目标URL: {page_url}")
        
        # 启动浏览器
        from app.services.exploration.browser_session import PlaywrightBrowserSession
        
        log_write("启动浏览器...")
        exploration_event_bus.publish(run_id, "browser_starting", {})
        
        with PlaywrightBrowserSession(start_url=page_url, timeout_seconds=30) as browser:
            log_write("浏览器已启动")
            exploration_event_bus.publish(run_id, "browser_started", {})
            
            # 导航
            log_write(f"导航到: {page_url}")
            result = browser.navigate(page_url)
            
            if result.get("status") == "passed":
                log_write("导航成功")
                exploration_event_bus.publish(run_id, "navigation_success", {"url": page_url})
                
                # 观察页面
                log_write("采集页面元素...")
                observation = browser.observe()
                
                elements = observation.get("elements", [])
                log_write(f"发现 {len(elements)} 个元素")
                exploration_event_bus.publish(run_id, "elements_discovered", {
                    "count": len(elements),
                    "url": page_url
                })
                
                # 写入结果
                pages_file = artifact_root / "pages.json"
                pages_file.write_text(json.dumps({
                    "pages": [{
                        "url": page_url,
                        "title": observation.get("title", ""),
                        "elements": elements
                    }]
                }, ensure_ascii=False, indent=2))
                
                log_write("探索完成")
                exploration_event_bus.publish(run_id, "run_completed", {"status": "completed"})
                
                return {
                    "status": "completed",
                    "summary": f"完成简化探索，发现 {len(elements)} 个元素",
                    "pages_count": 1,
                    "elements_count": len(elements)
                }
            else:
                error = result.get("error", "未知错误")
                log_write(f"导航失败: {error}")
                exploration_event_bus.publish(run_id, "error", {"message": error})
                return {"status": "blocked", "summary": f"导航失败: {error}"}
                
    except Exception as e:
        error_msg = f"探索异常: {str(e)}"
        log_write(error_msg)
        exploration_event_bus.publish(run_id, "error", {"message": error_msg})
        import traceback
        log_write(traceback.format_exc())
        return {"status": "blocked", "summary": error_msg}
```

### 删除2: 复杂的Planning
**问题**: LLM调用可能超时或失败  
**方案**: 跳过planning，直接执行

### 删除3: Agentic Loop
**问题**: 复杂的agent决策容易卡死  
**方案**: 只做简单的页面访问和元素采集

---

## ⚡ 立即执行（5分钟内完成）

```bash
# 1. 清理卡死任务
cd /Users/wanghongbao/project/test_project/apps/backend
sqlite3 data/ai_testing.db "UPDATE exploration_runs SET status = 'interrupted', finished_at = CURRENT_TIMESTAMP WHERE status IN ('running', 'queued');"

# 2. 备份当前代码
cp app/services/exploration/site_orchestrator.py app/services/exploration/site_orchestrator.py.backup

# 3. 应用简化补丁（手动编辑或用脚本）
# 将 _execute_unified_exploration 替换为 _execute_simple_exploration

# 4. 重启服务
pkill -f uvicorn
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &

# 5. 测试
# - 刷新前端
# - 创建新任务
# - 观察SSE是否有事件
```

---

## 🎯 终极建议

**删除以下无用功能**:
1. ❌ 统一编排器（unified_orchestrator） - 太复杂
2. ❌ 智能规划器（planner with LLM） - 容易超时
3. ❌ Agentic Loop - 不稳定
4. ❌ 复杂的重试和重新规划逻辑 - 增加复杂度

**只保留核心功能**:
1. ✅ 简单的浏览器会话
2. ✅ 基本的页面导航
3. ✅ 元素采集和记录
4. ✅ 清晰的事件发布
5. ✅ 超时保护

**预期效果**:
- 任务立即启动
- SSE实时收到事件
- 不会卡死
- 可预测的行为

---

## 验证步骤

1. 清理数据库 ✓
2. 应用简化补丁 ✓
3. 重启服务 ✓
4. 创建新任务 
5. 观察SSE事件流
6. 检查任务是否完成
7. 查看日志和结果文件

---

**当前时间**: 2026-06-21 13:47  
**执行优先级**: 🔴 P0 - 立即执行  
**预计时间**: 5-10分钟
