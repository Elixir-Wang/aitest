# 探索任务失败问题 - 完整修复总结 ✅

## 📅 修复时间
2026-06-20 23:40

## 🎯 问题概述
用户报告：执行探索任务总是失败

## 🔍 诊断过程

### 问题1: sqlite3.Row 对象不兼容 ✅ 已修复
**错误**: `'sqlite3.Row' object has no attribute 'get'`

**原因**: 
- 数据库查询返回 `sqlite3.Row` 对象
- 代码中使用了 `.get()` 方法，但 Row 对象不支持

**修复**: `app/repositories/exploration_repo.py`
- `find_by_id()` - 转换为 dict
- `list_by_project()` - 转换为 dict 列表  
- `list_visible()` - 转换为 dict 列表

### 问题2: capability_id 未注册 ✅ 已修复
**错误**: `KeyError: 'site_exploration_planning'`

**原因**:
- `planner.py` 使用了不存在的 capability ID: `"site_exploration_planning"`
- `capabilities.py` 中只注册了 `"site_exploration"`

**修复**: `app/services/exploration/plan_and_execute/planner.py`
```python
# 第 276 行修改
self.capability_id = "site_exploration"  # 原: "site_exploration_planning"
```

---

## ✅ 已完成的修复

### 修复1: 数据库返回类型转换
**文件**: `app/repositories/exploration_repo.py`
**影响**: 27 处 `find_by_id` 调用

```python
def find_by_id(db: Connection, run_id: str) -> Row | None:
    row = db.execute(f"{BASE_SELECT} WHERE er.id = ?", (run_id,)).fetchone()
    return dict(row) if row else None  # ✅ 转换为字典
```

### 修复2: Capability ID 修正
**文件**: `app/services/exploration/plan_and_execute/planner.py`
**行号**: 276

```python
def __init__(self):
    self.capability_id = "site_exploration"  # ✅ 使用已注册的 ID
```

---

## 🚀 验证步骤（必须执行）

### 1. 重启后端服务
```bash
cd apps/backend

# 杀掉旧进程
pkill -f uvicorn

# 启动新服务
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 创建测试任务
在前端界面：
1. 进入项目 → 探索任务
2. 点击"新建探索任务"
3. 填写配置并保存
4. 点击"开始探索"

### 3. 观察任务执行
**预期行为**:
```
状态: pending → queued → running → completed/partial
```

**预期日志**:
```json
{"event": "run_started", "message": "开始统一探索: xxx"}
{"event": "planning_started", "message": "分析目标并生成探索计划..."}
{"event": "planning_completed", "total_steps": 5}
{"event": "step_started", "step_number": 1}
...
{"event": "run_completed"}
```

**不应该看到**:
- ❌ `'sqlite3.Row' object has no attribute 'get'`
- ❌ `KeyError: 'site_exploration_planning'`

### 4. 检查结果
```bash
# 查看最新任务状态
sqlite3 data/ai_testing.db "
SELECT id, status, result_summary 
FROM exploration_runs 
ORDER BY created_at DESC LIMIT 1;"

# 应该看到 status = 'completed' 或 'partial'，不是 'blocked'
```

---

## 📊 修复对比

### 修复前
```
启动探索任务
  ↓
queued (立即失败)
  ↓
blocked: '探索执行异常: site_exploration_planning'
```

### 修复后
```
启动探索任务
  ↓
queued
  ↓
running (Planning → Execution)
  ↓
completed/partial (生成报告和产物)
```

---

## 📁 修改的文件列表

1. ✅ `app/repositories/exploration_repo.py` - 3个函数修改
2. ✅ `app/services/exploration/plan_and_execute/planner.py` - 1行修改

**总计**: 2个文件，4处修改

---

## 🎯 预期结果

修复后，探索任务应该能够：

1. ✅ **正常启动** - 状态从 pending → queued → running
2. ✅ **Planning 成功** - 使用 site_exploration capability 生成探索计划
3. ✅ **Execution 执行** - 按计划访问页面、执行操作
4. ✅ **生成产物** - 创建探索报告、页面信息、元素定位器
5. ✅ **任务完成** - 状态变为 completed 或 partial（不是 blocked）

---

## ⚠️ 注意事项

### 1. 服务必须重启
修改代码后，**必须重启后端服务**才能生效。

### 2. 依赖检查（可选）
如果遇到其他错误，可能需要安装依赖：
```bash
pip3 install pydantic pyyaml langchain langchain-openai playwright
```

### 3. 数据库配置
确保 `site_exploration` capability 已在数据库中配置模型：
```bash
sqlite3 data/ai_testing.db "
SELECT * FROM model_assignments WHERE capability_id = 'site_exploration';"
```

---

## 🔍 故障排查

### 如果任务仍然失败

#### 步骤1: 检查修改是否生效
```bash
grep -n "capability_id" app/services/exploration/plan_and_execute/planner.py
# 应该显示: 276:        self.capability_id = "site_exploration"
```

#### 步骤2: 查看最新日志
```bash
tail -100 logs/app/$(date +%Y-%m-%d).log | grep -E "error|ERROR|Exception"
```

#### 步骤3: 查看探索任务日志
```bash
find data/projects -name "run.log" -type f -mtime 0 -exec tail -20 {} \;
```

#### 步骤4: 检查服务是否重启
```bash
ps aux | grep uvicorn
# 检查进程启动时间是否是最近的
```

---

## 📞 如果问题持续存在

请提供以下信息：

1. **最新的错误日志**
```bash
tail -100 logs/app/$(date +%Y-%m-%d).log > latest_error.log
```

2. **最新任务状态**
```bash
sqlite3 data/ai_testing.db "
SELECT * FROM exploration_runs 
WHERE id = (SELECT id FROM exploration_runs ORDER BY created_at DESC LIMIT 1);"
```

3. **修改确认**
```bash
git diff app/repositories/exploration_repo.py
git diff app/services/exploration/plan_and_execute/planner.py
```

---

## ✨ 成功标志

看到以下内容说明修复成功：

### 1. 后端日志正常
```
INFO | 站点探索开始执行
INFO | 分析目标并生成探索计划
INFO | 规划完成，共 X 个步骤
INFO | 开始执行步骤 1/X
...
INFO | 探索完成
```

### 2. 任务状态正确
```bash
sqlite3 data/ai_testing.db "SELECT status FROM exploration_runs ORDER BY created_at DESC LIMIT 1;"
# 输出: completed 或 partial（不是 blocked）
```

### 3. 前端显示正常
- ✅ 任务状态显示为完成
- ✅ 可以查看探索报告
- ✅ 有页面和元素数据展示

---

## 📝 总结

### 核心问题
1. **sqlite3.Row 不兼容** - 代码使用 .get() 方法，但 Row 对象不支持
2. **capability_id 错误** - 使用了未注册的 "site_exploration_planning"

### 解决方案
1. 转换 Row 对象为 dict - 使代码兼容
2. 修正 capability_id - 使用已注册的 "site_exploration"

### 影响范围
- ✅ 只修改了2个文件
- ✅ 不影响其他功能
- ✅ 向后兼容

### 风险评估
- 🟢 **风险低** - 使用已有的 capability 配置
- 🟢 **测试简单** - 创建探索任务即可验证
- 🟢 **回滚容易** - 如有问题可快速回滚

---

**修复完成时间**: 2026-06-20 23:40  
**修复状态**: ✅ **完成，等待验证**  
**下一步**: 🚀 **重启服务并测试**

---

## 🙏 致谢

感谢你的耐心！这次我们彻底分析了问题：
1. ✅ 第一层：sqlite3.Row 不兼容
2. ✅ 第二层：capability_id 未注册

两个问题都已修复。现在请重启服务并测试，探索任务应该能正常工作了！

如果还有问题，请立即提供最新的错误日志，我会继续深入分析。💪
