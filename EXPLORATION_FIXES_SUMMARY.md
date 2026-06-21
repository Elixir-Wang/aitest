# 探索模块修复总结

## 修复的问题

### 问题 1：探索完成变成"未分组模块"且无法展开

**症状**：
- 探索完成后，前端显示"未分组模块 0/1 页面 已完成"
- 模块无法展开查看详情
- 规划的模块（如 `planned-01`）没有更新进度

**根本原因**：
1. 探索开始时创建规划模块：`planned-01` (module_name: "工作台", status: pending)
2. 探索完成时，代码调用 `create_module_coverage()` **创建新的**模块记录
3. 由于 `module_key` 已存在，导致：
   - 主键冲突（创建失败）
   - 或创建了重复记录
   - 规划模块没有被更新

**修复方案**：
1. 在 `exploration_repo.py` 中添加 `update_module_coverage()` 函数
2. 在 `site_orchestrator.py` 中，探索完成时：
   - 检查模块是否已存在
   - 如果存在，**更新**已有的规划模块
   - 如果不存在，创建新模块

### 问题 2：元素定位选择器优先级不符合 Playwright 最佳实践

**症状**：
- 选择器优先级顺序不符合 Playwright 推荐
- 缺少 `getByPlaceholder` 方法
- `placeholder` 被错误地合并到 `label` 中

**根本原因**：
原始优先级：`["role", "label", "testid", "text", "css"]`
- 缺少 `placeholder`
- `testid` 优先级高于 `text`（不符合最佳实践）

**修复方案**：
更新 `selector-generator.mjs`，使用 Playwright 推荐的优先级：
1. **getByRole** - 首选，匹配无障碍树
2. **getByLabel** - 用于表单输入关联的标签
3. **getByPlaceholder** - 当没有标签时
4. **getByText** - 用于非交互元素的可见文本
5. **getByTestId** - 当语义选择器不可行时
6. **CSS selector** - 最后的手段

## 修改的文件

### 1. `apps/backend/app/repositories/exploration_repo.py`

**新增函数**：`update_module_coverage()`

```python
def update_module_coverage(
    db: Connection,
    *,
    exploration_run_id: str,
    module_key: str,
    module_name: str,
    entry_path: str,
    planned_page_count: int,
    explored_page_count: int,
    blocked_page_count: int,
    action_count: int,
    field_count: int,
    state_transition_count: int,
    completion_status: str,
    completion_summary: str,
) -> None:
    """更新已存在的模块覆盖记录"""
    db.execute(
        """
        UPDATE exploration_module_coverages
        SET module_name = ?,
            entry_path = ?,
            planned_page_count = ?,
            explored_page_count = ?,
            blocked_page_count = ?,
            action_count = ?,
            field_count = ?,
            state_transition_count = ?,
            completion_status = ?,
            completion_summary = ?
        WHERE exploration_run_id = ? AND module_key = ?
        """,
        (...)
    )
```

### 2. `apps/backend/app/services/exploration/site_orchestrator.py`

**修改**：`_persist_completed_result()` 中的模块持久化逻辑

```python
# 修改前：直接创建新模块
for module in module_coverages:
    exploration_repo.create_module_coverage(...)

# 修改后：检查并更新或创建
for module in module_coverages:
    existing_modules = {m["module_key"]: m for m in exploration_repo.list_module_coverages(db, run["id"])}
    
    if module["module_key"] in existing_modules:
        # 更新已存在的规划模块
        exploration_repo.update_module_coverage(...)
    else:
        # 创建新模块（对于未在规划中的模块）
        exploration_repo.create_module_coverage(...)
```

### 3. `apps/backend/runners/playwright/selector-generator.mjs`

**修改**：选择器优先级和 placeholder 支持

```javascript
// 修改前
const SELECTOR_PRIORITY = ["role", "label", "testid", "text", "css"];
const label = clean(element.label || element.ariaLabel || element.placeholder);

// 修改后
const SELECTOR_PRIORITY = ["role", "label", "placeholder", "text", "testid", "css"];
const label = clean(element.label || element.ariaLabel);
const placeholder = clean(element.placeholder);

// 新增 getByPlaceholder 候选项
if (placeholder) {
  candidates.push({
    kind: "placeholder",
    placeholder,
    code: `page.getByPlaceholder('${escapeSingle(placeholder)}')`,
  });
}
```

## 修复效果

### 问题 1 修复效果

**修复前**：
```
数据库：
- planned-01 (工作台, 0/1, pending)  ← 规划模块
- 工作台 (工作台, 1/1, completed)    ← 错误创建的新模块

前端显示：
- 未分组模块 0/1 页面 已完成  ← 找不到匹配的模块
```

**修复后**：
```
数据库：
- planned-01 (工作台, 1/1, completed)  ← 规划模块被正确更新

前端显示：
- 工作台 1/1 页面 已完成  ← 正确显示进度
```

### 问题 2 修复效果

**修复前**：
```
选择器候选项（错误的优先级）：
1. getByRole(...)
2. getByLabel(...)  ← placeholder 被合并到这里
3. getByTestId(...)  ← 优先级过高
4. getByText(...)
5. page.locator(...)
```

**修复后**：
```
选择器候选项（符合 Playwright 最佳实践）：
1. getByRole(...)        ← 首选
2. getByLabel(...)       ← 表单标签
3. getByPlaceholder(...) ← 新增，placeholder 独立
4. getByText(...)        ← 非交互元素
5. getByTestId(...)      ← 降低优先级
6. page.locator(...)     ← 最后的手段
```

## 测试验证

### 验证问题 1 修复

1. 启动探索任务
2. 等待探索完成
3. 检查数据库：
   ```sql
   SELECT module_key, module_name, explored_page_count, completion_status
   FROM exploration_module_coverages
   WHERE exploration_run_id = 'xxx';
   ```
4. 预期结果：规划模块被更新，没有重复记录

### 验证问题 2 修复

1. 运行选择器生成测试：
   ```bash
   cd apps/backend/runners/playwright
   node selector-generator.test.mjs
   ```
2. 测试 placeholder 元素：
   ```javascript
   const element = { placeholder: "请输入邮箱" };
   const selectors = buildElementSelectors(element);
   // 预期：primary_selector.code === "page.getByPlaceholder('请输入邮箱')"
   ```

## 相关文档

- Playwright Locators: https://playwright.dev/docs/locators
- Playwright Best Practices: https://playwright.dev/docs/best-practices

## 修复时间

2026-06-21
