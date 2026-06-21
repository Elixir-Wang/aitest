# 探索任务失败问题完整分析报告

## 📋 执行日期
2026-06-20

## 🔴 问题描述
用户报告：执行探索任务总是失败

## 🔍 问题诊断

### 1. 核心错误
```
错误信息: 'sqlite3.Row' object has no attribute 'get'
失败任务ID: explore-01b554b4f26ba242
状态: blocked
```

### 2. 根本原因

#### 问题1: sqlite3.Row 对象使用不一致 ✅ **已修复**

**技术细节：**
- `app/core/db.py` 配置了 `connection.row_factory = sqlite3.Row`
- `sqlite3.Row` 对象支持：
  - ✅ `row["key"]` - 字典式访问
  - ✅ `key in row.keys()` - 键检查
  - ❌ `row.get("key")` - **不支持** `.get()` 方法

**代码问题：**
```python
# app/repositories/exploration_repo.py (修复前)
def find_by_id(db: Connection, run_id: str) -> Row | None:
    return db.execute(f"{BASE_SELECT} WHERE er.id = ?", (run_id,)).fetchone()
    # 返回 sqlite3.Row 对象
```

```python
# app/services/exploration/service.py (问题代码)
# 代码中 185 处使用了 .get() 方法
run.get("scope")  # ❌ 失败：sqlite3.Row 没有 get 方法
```

**执行流程：**
```
start_project_run()
  ↓
_dispatch_exploration_run()
  ↓
site_orchestrator.run_exploration()
  ↓
exploration_repo.find_by_id(db, run_id)  # 返回 sqlite3.Row
  ↓
exploration_service.seed_planned_modules_for_run(db, run)
  ↓
_seed_planned_modules(db, run)
  ↓
run["scope"] or run["environment_name"]  # ✅ 这里可以工作
  但其他地方 run.get()  # ❌ 这里失败
```

**修复方案：**
将 `exploration_repo.py` 中的函数返回值从 `sqlite3.Row` 转换为 `dict`：

```python
# app/repositories/exploration_repo.py (修复后)
def find_by_id(db: Connection, run_id: str) -> Row | None:
    row = db.execute(f"{BASE_SELECT} WHERE er.id = ?", (run_id,)).fetchone()
    return dict(row) if row else None  # ✅ 转换为 dict

def list_by_project(db: Connection, project_id: str) -> list[Row]:
    rows = db.execute(...).fetchall()
    return [dict(row) for row in rows]  # ✅ 转换为 dict 列表

def list_visible(db: Connection, actor: Row) -> list[Row]:
    rows = db.execute(...).fetchall()
    return [dict(row) for row in rows]  # ✅ 转换为 dict 列表
```

## ⚙️ 环境检查

### Python 环境
- ✅ Python 版本: 3.9.6
- ✅ Python 路径: `/Library/Developer/CommandLineTools/usr/bin/python3`
- ⚠️ **注意**: 当前使用系统 Python，不是虚拟环境

### Node.js 环境 (Playwright 依赖)
- ✅ Node.js: v24.15.0
- ✅ NPM/NPX: 11.12.1
- ✅ 命令路径: `/usr/local/bin/node`, `/usr/local/bin/npx`

### 数据库
- ✅ SQLite 数据库存在: `data/ai_testing.db` (3.9 MB)
- ✅ 最近更新: 2026-06-20 23:30

## 🔧 已执行的修复

### 修复1: 转换 sqlite3.Row 为 dict
**文件**: `app/repositories/exploration_repo.py`
**修改函数**:
1. `find_by_id()` - 返回 dict 而不是 Row
2. `list_by_project()` - 返回 dict 列表
3. `list_visible()` - 返回 dict 列表

**影响范围**: 27 处 `find_by_id` 调用

## ⚠️ 潜在问题（待验证）

### 问题2: Playwright Runner 配置
需要检查以下配置是否正确：
1. `PLAYWRIGHT_RUNNER_DIR` 路径是否存在
2. Playwright CLI 是否已安装
3. 浏览器是否已安装 (`npx playwright install`)

### 问题3: 虚拟环境
- 当前使用系统 Python 而不是虚拟环境
- 可能导致依赖包版本不一致或缺失

## 📝 验证步骤

### 1. 验证修复是否生效
```bash
cd apps/backend

# 检查是否还有其他使用 Row 的地方
grep -rn "sqlite3.Row" app/

# 运行测试
python3 -m pytest tests/test_exploration_run_restart.py -v
```

### 2. 检查 Playwright 配置
```bash
# 检查 Playwright runner 目录
ls -la ../playwright-runners/

# 检查 Playwright 是否已安装
npx playwright --version

# 安装 Playwright 浏览器（如果未安装）
npx playwright install
```

### 3. 设置虚拟环境（推荐）
```bash
cd apps/backend

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 4. 重新测试探索任务
```bash
# 启动后端服务
python3 -m uvicorn app.main:app --reload

# 在前端创建新的探索任务并执行
```

## 📊 测试计划

### 测试用例1: 基本探索任务
- [ ] 创建新的探索任务
- [ ] 配置测试环境和目标URL
- [ ] 启动探索任务
- [ ] 验证任务状态变为 "running"
- [ ] 等待任务完成
- [ ] 检查任务状态（应为 "completed" 或 "partial"，不应为 "blocked"）
- [ ] 查看日志输出

### 测试用例2: 错误恢复
- [ ] 查看之前失败的任务 `explore-01b554b4f26ba242`
- [ ] 尝试重新启动该任务
- [ ] 验证不再出现 `'sqlite3.Row' object has no attribute 'get'` 错误

## 🎯 预期结果

修复后，探索任务应该能够：
1. ✅ 正常启动，状态变为 "running"
2. ✅ 成功访问目标网站
3. ✅ 执行 Playwright 探索脚本
4. ✅ 生成探索报告和产物
5. ✅ 任务状态变为 "completed" 或 "partial"（根据探索结果）

## 📌 后续建议

### 1. 代码规范
- 统一数据库返回类型：要么全部使用 `dict`，要么全部使用 `Row` 并提供兼容层
- 添加类型注解的测试以避免类似问题

### 2. 虚拟环境
- 创建并使用虚拟环境来隔离项目依赖
- 更新部署文档说明虚拟环境配置

### 3. 测试覆盖
- 添加集成测试来验证探索任务的完整流程
- 添加数据库 Row/dict 转换的单元测试

### 4. 错误处理
- 改进错误日志记录，使问题更容易诊断
- 添加更详细的错误提示

## 📞 联系信息
如果问题仍然存在，请提供：
1. 完整的错误日志（`logs/app/2026-06-20.log`）
2. 探索任务配置
3. Playwright runner 目录结构
4. `pip list` 输出（依赖包列表）
