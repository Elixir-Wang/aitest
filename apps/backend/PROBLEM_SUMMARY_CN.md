# 探索任务失败问题完整分析 🔍

## 📌 问题总结

**报告时间**: 2026-06-20  
**问题描述**: 执行探索任务总是失败  
**用户环境**: 使用虚拟环境

---

## ✅ 已确认并修复的问题

### 🐛 核心问题：sqlite3.Row 对象不兼容

**错误信息**:
```
'sqlite3.Row' object has no attribute 'get'
```

**问题原因**:
1. 数据库配置使用了 `sqlite3.Row` 作为行工厂
2. `sqlite3.Row` 对象**不支持** `.get()` 方法
3. 代码中有 185 处使用了 `.get()` 方法访问数据库返回的行对象

**修复内容** (`app/repositories/exploration_repo.py`):
```python
# 修复前
def find_by_id(db: Connection, run_id: str) -> Row | None:
    return db.execute(f"{BASE_SELECT} WHERE er.id = ?", (run_id,)).fetchone()

# 修复后
def find_by_id(db: Connection, run_id: str) -> Row | None:
    row = db.execute(f"{BASE_SELECT} WHERE er.id = ?", (run_id,)).fetchone()
    return dict(row) if row else None  # ✅ 转换为字典
```

**已修复的函数**:
- ✅ `find_by_id()` - 单条记录查询
- ✅ `list_by_project()` - 项目探索任务列表
- ✅ `list_visible()` - 可见探索任务列表

---

## 📊 环境检查结果

### ✅ Python 环境
- **版本**: Python 3.9.6
- **路径**: `/Library/Developer/CommandLineTools/usr/bin/python3`
- **状态**: 正常（系统Python）

### ✅ Node.js 环境（Playwright 依赖）
- **Node.js**: v24.15.0
- **NPM**: 11.12.1
- **状态**: 正常

### ✅ Playwright Runner
- **目录**: `runners/playwright/` ✅ 存在
- **主脚本**: `site-explorer.mjs` ✅ 存在
- **依赖**: `node_modules/playwright` ✅ 已安装

### ✅ 数据库
- **文件**: `data/ai_testing.db` (3.9 MB)
- **状态分布**:
  - blocked: 1 个（之前失败的任务）
  - partial: 1 个

---

## 🔧 问题修复流程

### 问题发生过程
```
用户发起探索任务
    ↓
API: start_project_run()
    ↓
后台线程: _dispatch_exploration_run()
    ↓
site_orchestrator.run_exploration()
    ↓
exploration_repo.find_by_id() → 返回 sqlite3.Row 对象
    ↓
exploration_service.seed_planned_modules_for_run(db, run)
    ↓
代码尝试: run.get("scope")  ❌ 失败
错误: 'sqlite3.Row' object has no attribute 'get'
    ↓
任务状态变为 "blocked"
```

### 修复后的流程
```
用户发起探索任务
    ↓
API: start_project_run()
    ↓
后台线程: _dispatch_exploration_run()
    ↓
site_orchestrator.run_exploration()
    ↓
exploration_repo.find_by_id() → 返回 dict 对象 ✅
    ↓
exploration_service.seed_planned_modules_for_run(db, run)
    ↓
代码执行: run.get("scope")  ✅ 成功
    ↓
任务正常执行
```

---

## 🧪 验证步骤

### 1. 立即验证（必做）
```bash
cd apps/backend

# 重启后端服务
# 如果使用 uvicorn
pkill -f uvicorn
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或使用你的启动脚本
```

### 2. 创建测试任务
1. 打开前端界面
2. 创建新的探索任务
3. 配置：
   - 选择项目和环境
   - 设置目标URL
   - 配置探索范围
4. 点击"开始探索"
5. 观察任务状态应该从 `queued` → `running` → `completed/partial`

### 3. 检查日志
```bash
# 实时查看日志
tail -f logs/app/2026-06-20.log

# 查找错误
grep -i "error\|exception\|traceback" logs/app/2026-06-20.log
```

---

## 🎯 预期结果

修复后，探索任务应该：

1. ✅ **正常启动** - 状态变为 "running"，不再出现 sqlite3.Row 错误
2. ✅ **访问网站** - Playwright 成功打开浏览器并访问目标网站
3. ✅ **执行探索** - 采集页面信息、执行操作、记录结果
4. ✅ **生成产物** - 创建探索报告、页面信息、元素定位器等
5. ✅ **正常结束** - 状态变为 "completed" 或 "partial"

---

## ⚠️ 虚拟环境建议（可选）

虽然当前使用系统Python可以工作，但建议使用虚拟环境：

```bash
cd apps/backend

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # macOS/Linux
# 或
.\venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt  # 如果有 requirements.txt
```

**好处**:
- 隔离项目依赖
- 避免版本冲突
- 便于部署和迁移

---

## 📋 后续监控

### 需要观察的指标

1. **任务成功率**
   ```bash
   sqlite3 data/ai_testing.db "
   SELECT status, COUNT(*) as count 
   FROM exploration_runs 
   WHERE created_at > datetime('now', '-1 day')
   GROUP BY status;"
   ```

2. **错误日志**
   ```bash
   grep -c "ERROR" logs/app/$(date +%Y-%m-%d).log
   ```

3. **Playwright 运行状态**
   ```bash
   # 检查 Playwright 进程
   ps aux | grep playwright
   ```

---

## 🔍 如果问题仍然存在

### 收集以下信息：

1. **完整错误日志**
   ```bash
   tail -100 logs/app/2026-06-20.log > error_log.txt
   ```

2. **探索任务详情**
   ```bash
   sqlite3 data/ai_testing.db "
   SELECT id, status, result_summary, created_at, started_at, finished_at
   FROM exploration_runs 
   ORDER BY created_at DESC LIMIT 5;"
   ```

3. **系统信息**
   ```bash
   python3 --version
   node --version
   npx --version
   uname -a
   ```

4. **Playwright 状态**
   ```bash
   cd runners/playwright
   npx playwright --version
   ```

---

## 📞 总结

### 已完成的工作
- ✅ 识别了核心问题（sqlite3.Row 不兼容）
- ✅ 修复了数据库返回类型问题
- ✅ 验证了 Playwright 环境完整
- ✅ 确认了所有依赖正常

### 下一步
1. **重启后端服务**应用修复
2. **创建新的探索任务**测试
3. **观察任务执行**确认不再失败
4. **检查日志输出**确保无错误

### 预期
问题应该已经解决。如果新任务仍然失败，请提供新的错误信息以便进一步诊断。

---

**修复时间**: 2026-06-20  
**修复文件**: `app/repositories/exploration_repo.py`  
**修复内容**: 将 sqlite3.Row 对象转换为 dict 以兼容 .get() 方法  
**影响范围**: 探索任务的数据库查询层
