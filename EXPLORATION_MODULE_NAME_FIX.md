# 探索模块进度显示修复说明

## 问题描述

探索模块进度显示"工作台"这样的固定字符串，而不是按照规划生成的模块名称和进度。

**症状**：
- 前端显示：`工作台 0/1 页面 阻塞`
- 预期：应该显示规划的模块名称（如 `planned-01`）和实际的探索进度

## 问题根源

### 1. 数据流程
```
探索开始 → 生成规划模块 → 执行探索 → 生成页面产物 → 构建模块覆盖 → 显示进度
          (planned-01: 工作台)  (page.module: 工作台)  (需要关联)      (显示)
```

### 2. 问题点

**原始逻辑**：
1. 探索开始时，根据 `scope` 生成规划模块：
   - `planned-01` → "工作台"
   - `planned-02` → "探索广场"
   - ...

2. 页面执行时，通过 URL 路径推断模块名：
   - URL 包含 `/workspace/` → 推断为"工作台"
   - URL 包含 `/agentStore/` → 推断为"探索广场"

3. **关键问题**：在 `_build_module_coverages` 中，直接使用页面的模块名作为 `module_key`：
   ```python
   module_key = str(page.get("module") or "unclassified")  # "工作台"
   ```
   
   这导致：
   - 规划模块：`planned-01` (module_key) → "工作台" (module_name)
   - 实际页面：`工作台` (module_key) → "工作台" (module_name)
   - **两者没有关联**，前端显示时无法匹配到规划模块

## 修复方案

### 修改文件 1: `apps/backend/app/services/exploration/site_orchestrator.py`

在 `_build_module_coverages` 函数中，增加规划模块映射逻辑：

```python
def _build_module_coverages(...) -> list[dict]:
    # 获取规划的模块列表，建立模块名到 module_key 的映射
    from app.core.db import connect
    from app.repositories import exploration_repo

    planned_module_map = {}
    with connect() as db:
        for module in exploration_repo.list_module_coverages(db, run["id"]):
            # 将规划的模块名映射到 module_key (planned-01, planned-02 等)
            planned_module_map[module["module_name"]] = module["module_key"]

    module_groups: dict[str, dict] = {}
    for page_artifact in page_artifacts:
        page = page_artifact["page"]
        page_module_name = str(page.get("module") or "unclassified")

        # 如果页面的模块名在规划中存在，使用规划的 module_key
        if page_module_name in planned_module_map:
            module_key = planned_module_map[page_module_name]
            module_name = page_module_name
        else:
            module_key = page_module_name
            module_name = page_module_name if page_module_name != "unclassified" else _module_name(run)

        # 后续使用 module_key 构建模块覆盖信息...
```

**核心逻辑**：
1. 从数据库读取规划的模块列表
2. 建立 `module_name → module_key` 的映射表
3. 处理页面时，如果页面的模块名在规划中存在，使用规划的 `module_key`
4. 这样实际采集的页面就能正确关联到规划的模块

### 修改文件 2: `apps/backend/app/services/exploration/artifact_service.py`

优化模块名推断逻辑，避免覆盖已设置的值：

```python
# 只有当 module 真正为空时才推断，不要覆盖已经设置的值
if not _text(page_meta.get("module")):
    page_meta["module"] = _page_module_name(page_meta)
```

**原始逻辑问题**：
```python
# 旧代码：即使 module 有值也可能被覆盖
if not _text(page_meta.get("module")) or _text(page_meta.get("module")) == _text(page_meta.get("title")):
    page_meta["module"] = _page_module_name(page_meta)
```

## 修复效果

### 修复前
```
数据库规划模块:
- id: expcov-plan-xxx, module_key: planned-01, module_name: 工作台

实际页面产物:
- page.module: 工作台

构建模块覆盖:
- module_key: 工作台  ← 直接用页面的 module 作为 key
- module_name: 工作台

前端显示:
- 工作台 0/1 页面 阻塞  ← 找不到 planned-01，显示为新模块
```

### 修复后
```
数据库规划模块:
- id: expcov-plan-xxx, module_key: planned-01, module_name: 工作台

实际页面产物:
- page.module: 工作台

构建模块覆盖 (使用映射):
- 查找 planned_module_map["工作台"] → planned-01
- module_key: planned-01  ← 使用规划的 module_key
- module_name: 工作台
- explored_page_count: 1  ← 更新探索进度

前端显示:
- 工作台 1/1 页面 已完成  ← 正确关联并显示进度
```

## 测试验证

```python
# 验证映射逻辑
planned_modules = [
    {'module_key': 'planned-01', 'module_name': '工作台'},
    {'module_key': 'planned-02', 'module_name': '探索广场'},
]

planned_module_map = {m['module_name']: m['module_key'] for m in planned_modules}

page_module_name = '工作台'
if page_module_name in planned_module_map:
    module_key = planned_module_map[page_module_name]
    print(f'✓ 页面关联到规划模块: {module_key}')
    # 输出: ✓ 页面关联到规划模块: planned-01
```

## 后续优化建议

1. **在页面采集时直接设置 module_key**：
   - 当前方案在后处理阶段进行映射
   - 更好的方案是在页面采集时就设置正确的 `module_key`

2. **统一模块标识符**：
   - 考虑使用 `module_key` 作为唯一标识
   - `module_name` 仅用于显示

3. **增强 URL 路径映射**：
   - 当前 `_route_label` 函数的映射是硬编码的
   - 可以考虑从配置或规划中读取

## 相关文件

- `apps/backend/app/services/exploration/site_orchestrator.py` - 核心修复
- `apps/backend/app/services/exploration/artifact_service.py` - 辅助优化
- `apps/backend/app/services/exploration/service.py` - 规划模块生成
- `apps/backend/app/repositories/exploration_repo.py` - 模块数据访问

## 修复时间

2026-06-21
