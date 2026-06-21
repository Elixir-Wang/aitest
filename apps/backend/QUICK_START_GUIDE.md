# 探索任务修复 - 快速启动指南 🚀

## ✅ 修复完成

已修复两个关键问题：
1. ✅ sqlite3.Row 对象不兼容 → 已转换为 dict
2. ✅ capability_id 未注册 → 已修正为 "site_exploration"

---

## 🚀 立即开始（3步）

### 步骤1️⃣: 重启后端服务（必须）

```bash
cd apps/backend

# 杀掉旧进程
pkill -f uvicorn

# 启动新服务
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或使用你的启动脚本
```

**重要**: 不重启服务，修改不会生效！

---

### 步骤2️⃣: 创建并启动探索任务

1. 打开前端界面
2. 进入项目 → 探索任务
3. 点击"新建探索任务"或使用已有任务
4. 配置：
   - 选择项目和环境
   - 输入目标URL（例如：https://example.com）
   - 设置探索范围
5. 点击"开始探索"

---

### 步骤3️⃣: 观察结果

**成功的标志**：
- ✅ 任务状态：`pending` → `queued` → `running` → `completed`/`partial`
- ✅ 有探索报告生成
- ✅ 有页面和元素数据

**失败的标志**：
- ❌ 任务状态：`pending` → `queued` → `blocked`
- ❌ 错误信息中包含 "site_exploration_planning" 或 "sqlite3.Row"

---

## 📊 实时监控

### 监控日志（推荐）
```bash
# 打开新终端窗口
cd apps/backend
tail -f logs/app/$(date +%Y-%m-%d).log | grep -E "exploration|ERROR|error"
```

### 检查任务状态
```bash
sqlite3 data/ai_testing.db "
SELECT id, status, result_summary, started_at 
FROM exploration_runs 
ORDER BY created_at DESC LIMIT 1;"
```

---

## ✨ 预期日志输出

**成功的日志**：
```json
{"event": "run_started", "message": "开始统一探索"}
{"event": "planning_started", "message": "分析目标并生成探索计划"}
{"event": "planning_completed", "total_steps": 5}
{"event": "step_started", "step_number": 1}
{"event": "step_completed", "step_number": 1, "status": "success"}
...
{"event": "run_completed", "status": "completed"}
```

**不应该看到**：
```json
{"event": "error", "message": "探索执行异常: 'site_exploration_planning'"}
{"event": "error", "message": "'sqlite3.Row' object has no attribute 'get'"}
```

---

## 🔍 快速诊断

### 如果任务立即失败

#### 1. 确认服务已重启
```bash
ps aux | grep uvicorn
# 检查启动时间是否是刚才的
```

#### 2. 查看最新错误
```bash
tail -50 logs/app/$(date +%Y-%m-%d).log | grep -A 5 "ERROR\|error"
```

#### 3. 验证修改生效
```bash
# 检查 Row 转换修复
grep -A 2 "def find_by_id" app/repositories/exploration_repo.py

# 检查 capability_id 修复
grep "capability_id" app/services/exploration/plan_and_execute/planner.py
# 应该看到: self.capability_id = "site_exploration"
```

---

## 📞 需要帮助？

如果任务仍然失败，请提供：

```bash
# 1. 收集诊断信息
cd apps/backend

# 最新日志
tail -100 logs/app/$(date +%Y-%m-%d).log > diagnosis.log

# 任务状态
sqlite3 data/ai_testing.db "
SELECT id, status, result_summary, created_at, started_at, finished_at
FROM exploration_runs 
ORDER BY created_at DESC LIMIT 3;" >> diagnosis.log

# 修改确认
echo "=== Git Changes ===" >> diagnosis.log
git diff >> diagnosis.log

# 2. 发送 diagnosis.log 文件
```

---

## 🎯 成功后的下一步

探索任务成功后，你可以：
1. 📊 查看探索报告
2. 🔍 检查页面和元素数据
3. 📝 导出测试用例
4. 🔄 创建更多探索任务

---

**修复完成时间**: 2026-06-20 23:45  
**状态**: ✅ 已修复，等待验证  
**下一步**: 🚀 重启服务并测试

祝你成功！💪
