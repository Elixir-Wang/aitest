# 探索功能立即修复方案

## 🔴 核心问题

1. **缺少依赖**：`pyyaml` 和 `pydantic` 未安装
2. **网络问题**：pip 代理配置导致无法安装依赖
3. **架构未完成**：`unified_orchestrator` 依赖的模块虽存在但可能未完整实现

## ⚡ 立即修复步骤

### 方案1：修复依赖安装（推荐）

```bash
# 跳过代理安装依赖
pip3 install --no-proxy pyyaml pydantic

# 或者使用国内镜像
pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple pyyaml pydantic

# 或者手动下载whl文件安装
# 1. 从 https://pypi.org/project/PyYAML/ 下载对应版本
# 2. pip3 install PyYAML-6.0-cp39-cp39-macosx_11_0_arm64.whl
```

### 方案2：临时禁用 unified_orchestrator（快速恢复）

如果依赖无法安装，临时回退到旧的探索方式：

**修改文件：`apps/backend/app/services/exploration/site_orchestrator.py`**

在第117行左右，找到 `_execute_unified_exploration` 调用，改为：

```python
def _run_exploration(run_id: str) -> None:
    # ... 前面代码保持不变 ...
    
    # 临时禁用 unified_orchestrator，使用 Playwright 直接探索
    # result = _execute_unified_exploration(run_id, artifact_root)
    result = _execute_playwright_probe(run_id, artifact_root)
    
    _persist_runner_result(run_id, artifact_root, result)
```

这样探索功能可以立即恢复，使用原有的 Playwright 探索方式。

---

## 🔍 问题诊断详情

### 1. 依赖问题
```
✗ yaml import failed: No module named 'yaml'
✗ pydantic import failed: No module named 'pydantic'
```

这两个包在以下文件中被使用：
- `app/services/exploration/service.py:8` - `import yaml`
- `app/services/exploration/plan_and_execute/planner.py:10` - `from pydantic import BaseModel, Field`
- `app/agents/site_exploration/execution_decision/` - 使用 pydantic

### 2. 网络代理问题
```
ProxyError('Cannot connect to proxy.', OSError('Tunnel connection failed: 403 Forbidden'))
```

pip 尝试通过代理连接但失败。

### 3. 模块完整性
- ✓ `plan_and_execute/planner.py` - 存在，包含完整的规划逻辑
- ✓ `plan_and_execute/executor.py` - 存在
- ✓ `plan_and_execute/monitor.py` - 存在
- ✓ `unified_orchestrator.py` - 存在并实现完整

---

## 📋 完整修复流程

### Step 1: 安装依赖（选择一种方式）

**方式A - 临时禁用代理**：
```bash
export http_proxy=""
export https_proxy=""
pip3 install pyyaml pydantic
```

**方式B - 使用国内镜像**：
```bash
pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple pyyaml pydantic
```

**方式C - 修改pip配置**：
```bash
# 创建或编辑 ~/.pip/pip.conf
mkdir -p ~/.pip
cat > ~/.pip/pip.conf << EOF
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
[install]
trusted-host = pypi.tuna.tsinghua.edu.cn
EOF

pip3 install pyyaml pydantic
```

### Step 2: 验证安装

```bash
python3 -c "import yaml; import pydantic; print('✓ Dependencies installed')"
```

### Step 3: 测试导入

```bash
cd apps/backend
python3 -c "
import sys
sys.path.insert(0, '.')
from app.services.exploration.unified_orchestrator import run_unified_exploration_sync
from app.services.exploration.site_orchestrator import run_exploration
print('✓ All modules import successfully')
"
```

### Step 4: 启动服务测试

```bash
cd apps/backend
python3 -m uvicorn app.main:app --reload
```

访问探索功能，创建并启动一个探索任务，验证是否正常运行。

---

## 🛠️ 如果依赖无法安装

如果由于网络或权限原因无法安装依赖，使用临时回退方案：

### 修改 `site_orchestrator.py`

```python
# 在文件开头添加注释说明
# TODO: 临时禁用 unified_orchestrator，等待依赖安装后恢复

def _run_exploration(run_id: str) -> None:
    # ... 前面代码 ...
    
    # 原代码第117行：
    # result = _execute_unified_exploration(run_id, artifact_root)
    
    # 临时回退到 Playwright 直接探索
    result = _execute_playwright_probe(run_id, artifact_root)
    
    _persist_runner_result(run_id, artifact_root, result)
```

这样修改后，探索功能使用原有的 Playwright 探索器，不依赖 `unified_orchestrator`。

### 提交临时修复

```bash
git add apps/backend/app/services/exploration/site_orchestrator.py
git commit -m "fix: 临时禁用 unified_orchestrator，等待依赖安装"
```

---

## ✅ 验证清单

完成修复后，验证以下功能：

- [ ] 服务能正常启动（无导入错误）
- [ ] 创建探索任务
- [ ] 启动探索任务
- [ ] 查看探索日志
- [ ] 查看探索结果
- [ ] 查看探索报告

---

## 🎯 后续优化（依赖安装成功后）

### 1. 恢复 unified_orchestrator

将 `site_orchestrator.py` 改回：
```python
result = _execute_unified_exploration(run_id, artifact_root)
```

### 2. 完整测试新架构

测试 unified_orchestrator 的核心功能：
- Planning 阶段：目标分析和计划生成
- Execution 阶段：步骤执行（direct 和 agentic）
- Monitoring 阶段：失败重试和重新规划

### 3. 清理暂存的变更

```bash
# 查看当前暂存的变更
git status

# 如果有未完成的功能，暂时撤销暂存
git restore --staged <file>

# 提交已完成的功能
git add <completed-files>
git commit -m "refactor: 完成探索架构重构"
```

---

## 💡 推荐方案

**立即执行：方案2（临时禁用）**
- 修改 `site_orchestrator.py` 一行代码
- 5分钟内恢复探索功能
- 无需等待依赖安装

**后续优化：方案1（安装依赖）**
- 解决网络或代理问题
- 安装 pyyaml 和 pydantic
- 恢复 unified_orchestrator
- 测试新架构

---

## 📞 需要帮助

如果遇到问题，告诉我：
1. 选择哪个方案？
2. 遇到什么错误？
3. 需要我生成具体的代码修改吗？
