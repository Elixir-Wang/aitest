---
name: locator_best_practices
description: Expert guidance on selecting stable, maintainable Playwright locators by element semantics and scenario, while avoiding fragile selectors like ref, CSS classes, and XPath.
---

# Locator Best Practices

你是一个专业的 Playwright 定位器选择专家。你的任务是为网页元素选择最稳定、最可维护的定位器。

---

## 核心原则

1. **按场景使用语义定位器** - 基于元素类型、角色、标签、文本等语义信息
2. **避免脆弱定位器** - 不使用 CSS 选择器、XPath、临时引用
3. **确保唯一性** - 每个定位器必须唯一标识一个元素
4. **确保可维护性** - 代码易读，页面改版时容易更新

---

## 定位器选择规则

依据 Playwright 官方定位器规则：定位器不是简单线性优先级，而是要在合适的位置使用合适的定位方式。先判断元素类型、无障碍语义和页面上下文，再选择最符合该元素语义的 locator。`getByRole` 只有在元素确实具备原生或显式无障碍 role 时才能使用；不能因为元素“可点击”就猜成 `button`。

### getByRole：真实无障碍角色元素

**为什么使用**:
- 基于 ARIA 角色，最符合无障碍标准
- 最稳定，页面样式改变不影响
- 语义化强，代码可读性好

**适用场景**:
- 按钮: `getByRole('button', { name: '创建资源' })`
- 链接: `getByRole('link', { name: '返回列表' })`
- 输入框: `getByRole('textbox', { name: '用户名' })`
- 复选框: `getByRole('checkbox', { name: '记住我' })`
- 单选按钮: `getByRole('radio', { name: '男' })`
- 下拉选择: `getByRole('combobox', { name: '选择城市' })`
- 表格: `getByRole('table')`

**常见角色**:
```python
常用角色列表:
- button, link, textbox, checkbox, radio, combobox
- heading, list, listitem, table, row, cell
- tab, tabpanel, dialog, alert, navigation
- main, banner, contentinfo, complementary
```

**示例**:
```python
# ✅ 好的做法
page.get_by_role("button", name="提交任务")
page.get_by_role("link", name="查看详情")
page.get_by_role("textbox", name="搜索")

# ❌ 避免
page.locator("button.submit-btn")  # CSS 选择器
page.locator("//button[text()='提交']")  # XPath
```

---

### getByLabel：带标签的表单字段

**为什么使用**:
- 明确关联表单字段和标签
- 符合无障碍标准
- 用户看到什么，你就定位什么

**适用场景**:
- 所有带 `<label>` 的表单字段
- 有 aria-label 或 aria-labelledby 的表单控件
- 例如文本框、密码框、复选框、单选框、下拉选择

**示例**:
```python
# ✅ 好的做法
page.get_by_label("用户名")
page.get_by_label("密码")
page.get_by_label("出生日期")

# 对应的 HTML:
# <label for="username">用户名</label>
# <input id="username" />
```

---

### getByText：可见文本或非标准文本入口

**为什么使用**:
- 用户看到什么，你就定位什么
- 适合文本固定的场景
- 对没有真实 role 的可点击文本，比伪造 `getByRole('button')` 更正确

**适用场景**:
- 静态文本（标题、标签、提示）
- 没有真实 button/link role 的菜单项或文字入口

**注意事项**:
- ⚠️ 文本变化会导致定位器失效
- ⚠️ 多语言项目需要考虑国际化

**示例**:
```python
# ✅ 适合的场景
page.get_by_text("欢迎回来")  # 固定标题
page.get_by_text("暂无数据")  # 固定提示
page.get_by_text("工作台")  # 文本入口，不伪造成 button

# ⚠️ 需要谨慎的场景
page.get_by_text("张三")  # 用户数据，可能变化
page.get_by_text("2024-01-01")  # 动态日期
```

**精确匹配 vs 模糊匹配**:
```python
# 精确匹配
page.get_by_text("提交", exact=True)

# 模糊匹配（包含即可）
page.get_by_text("提交")  # 会匹配 "提交任务"
```

---

### getByPlaceholder：没有 label 的输入框

**适用场景**:
- 输入框有 placeholder 属性
- 没有对应的 label

**示例**:
```python
# ✅ 适合的场景
page.get_by_placeholder("请输入手机号")
page.get_by_placeholder("搜索资源")

# 对应的 HTML:
# <input placeholder="请输入手机号" />
```

**注意**:
- placeholder 可能变化，不如 label 稳定
- 优先使用 getByLabel，placeholder 作为备选

---

### getByTestId：显式测试契约

**为什么推荐**:
- 开发专门为测试添加的标识
- 不会因为业务逻辑改变而变化
- 明确表示这是测试专用

**适用场景**:
- 元素没有合适的用户可见语义
- 需要稳定的定位器
- 团队约定使用 data-testid

**示例**:
```python
# ✅ 好的做法
page.get_by_test_id("user-avatar")
page.get_by_test_id("delete-confirm-dialog")

# 对应的 HTML:
# <div data-testid="user-avatar">...</div>
```

**注意**:
- 需要与开发团队协商添加 data-testid
- 命名规范: kebab-case, 描述性强

---

### CSS 选择器：最后兜底

**什么时候使用**:
- 语义定位器和测试契约都不适用
- 作为最后的备选方案

**为什么不推荐**:
- ❌ 依赖页面结构和样式
- ❌ 样式改版时容易失效
- ❌ 可读性差，维护困难

**如果必须使用**:
```python
# 尽量使用稳定的属性
page.locator("[data-id='user-123']")  # data 属性
page.locator("#unique-id")  # 唯一 ID

# ❌ 避免脆弱的选择器
page.locator(".btn.btn-primary.css-abc123")  # 动态类名
page.locator("div > div > button:nth-child(3)")  # 结构依赖
```

---

## 禁止使用的定位器

### ❌ ref（临时引用）

**为什么禁止**:
- ref 是 playwright-cli 快照时生成的临时引用（e15, e20 等）
- 每次快照 ref 都会变化
- 无法在测试用例中复用

**示例**:
```python
# ❌ 永远不要这样
page.locator("ref=e15")  # ref 会变化
page.locator("ref=e20")  # 不可复用
```

---

## 定位器唯一性验证

每个定位器必须唯一标识一个元素。

### 验证方法

```python
# 方法1: 使用 count() 验证
locator = page.get_by_role("button", name="提交")
count = locator.count()

if count == 0:
    # 元素未找到
    handle_not_found()
elif count == 1:
    # ✅ 唯一，可以使用
    locator.click()
elif count > 1:
    # ❌ 不唯一，需要优化定位器
    optimize_locator()
```

### 优化不唯一的定位器

**问题**: 有多个"提交"按钮

**解决方法**:

1. **添加更多上下文**
```python
# ❌ 不唯一
page.get_by_role("button", name="提交")

# ✅ 添加容器限定
page.locator("#order-form").get_by_role("button", name="提交")
```

2. **使用更精确的描述**
```python
# ❌ 不唯一
page.get_by_text("删除")

# ✅ 使用完整文本
page.get_by_role("button", name="删除资源")
```

3. **组合多个定位器**
```python
# ✅ 先定位容器，再定位元素
dialog = page.get_by_role("dialog", name="确认删除")
dialog.get_by_role("button", name="确定")
```

---

## 决策树（v2，链式 filter 优先）

```
开始
 │
 ├─ 元素有真实原生/显式无障碍 role，且 role 与目标动作匹配？
 │   └─ 是 → 使用 getByRole ✅
 │
 ├─ 是带 label / aria-label 的表单字段？
 │   └─ 是 → 使用 getByLabel ✅
 │
 ├─ 目标在列表/卡片/表格/对话框/弹窗中，且会出现多个同名元素？
 │   ├─ 列表/卡片/行/单元格有稳定容器 role（listitem/row/cell/dialog/tabpanel）？
 │   │   └─ 是 → page.getByRole('listitem').filter({ hasText: '...' }).getByRole('button', { name: '...' })
 │   ├─ 容器有 data-testid？
 │   │   └─ 是 → page.getByTestId('xxx').filter({ hasText: '...' }).getByRole('button', { name: '...' })
 │   ├─ 容器是 form / dialog 且有 aria-label？
 │   │   └─ 是 → page.getByLabel('容器名').getByRole('button', { name: '...' })
 │   └─ 以上都不行 → page.locator('...').filter({ hasText: '...' }).getByRole(...)
 │
 ├─ 是无真实 role 的文本入口，且文本唯一稳定？
 │   └─ 是 → 使用 getByText('...', { exact: true }) ✅
 │
 ├─ 是没有 label 的输入框，且有 placeholder？
 │   └─ 是 → 使用 getByPlaceholder('...', { exact: true }) ✅
 │
 ├─ 有明确 data-testid 测试契约？
 │   └─ 是 → 使用 getByTestId('...') ✅
 │
 └─ 以上都不适用？
     └─ 使用 CSS 选择器（尽量用 data 属性或 id）⚠️
```

---

## 常见场景示例

### 场景 1: 导航菜单

```python
# ✅ 好的做法
page.get_by_role("navigation").get_by_role("link", name="资源管理")
page.get_by_role("navigation").get_by_role("link", name="系统设置")

# ❌ 避免
page.locator(".nav-menu a:nth-child(1)")
```

### 场景 2: 表单提交

```python
# ✅ 好的做法
page.get_by_label("用户名").fill("admin")
page.get_by_label("密码").fill("123456")
page.get_by_role("button", name="登录").click()

# ❌ 避免
page.locator("#username").fill("admin")
page.locator("input[type='password']").fill("123456")
page.locator(".btn-primary").click()
```

### 场景 3: 对话框操作

```python
# ✅ 好的做法
dialog = page.get_by_role("dialog", name="删除确认")
dialog.get_by_role("button", name="确定").click()

# ❌ 避免
page.locator(".modal-content .btn-danger").click()
```

### 场景 4: 表格操作

```python
# ✅ 好的做法
table = page.get_by_role("table")
row = table.get_by_role("row").filter(has_text="张三")
row.get_by_role("button", name="编辑").click()

# ❌ 避免
page.locator("table tr:nth-child(2) td:last-child button").click()
```

### 场景 5: 搜索功能

```python
# ✅ 好的做法
page.get_by_role("textbox", name="搜索").fill("资源")
page.get_by_role("button", name="搜索").click()

# 或者使用 placeholder
page.get_by_placeholder("请输入关键词").fill("资源")
page.get_by_role("button", name="搜索").click()

# ❌ 避免
page.locator(".search-input").fill("资源")
page.locator(".search-btn").click()
```

---

## 红旗警告 🚩

遇到以下情况，说明定位器需要优化：

### 🚩 包含数字索引
```python
# ❌ 脆弱
page.locator("button:nth-child(3)")
page.locator("div:nth-of-type(2)")
```

### 🚩 包含动态类名
```python
# ❌ 脆弱（CSS Modules 生成的类名）
page.locator(".css-abc123")
page.locator("[class*='makeStyles']")
```

### 🚩 定位器过长
```python
# ❌ 脆弱（结构依赖严重）
page.locator("div.container > div.content > div.panel > button")
```

### 🚩 定位器过于宽泛
```python
# ❌ 不唯一
page.get_by_text("确定")  # 页面可能有多个"确定"
page.get_by_role("button")  # 页面可能有多个按钮
```

### 🚩 使用了 ref
```python
# ❌ 禁止
page.locator("ref=e15")
```

---

## 最佳实践总结

1. ✅ **按场景选择定位器**: 真实角色用 getByRole，表单标签用 getByLabel，文本入口用 getByText，输入提示用 getByPlaceholder，测试契约用 getByTestId
2. ✅ **确保唯一性**: 每个定位器 count() === 1
3. ✅ **使用明确的名称**: name 参数要具体，避免模糊
4. ✅ **使用容器限定**: 通过父容器缩小查找范围
5. ✅ **避免结构依赖**: 不使用 nth-child, :first-child 等
6. ✅ **避免样式依赖**: 不使用动态类名、样式选择器
7. ✅ **命名要描述性**: 让代码自解释
8. ❌ **永远不用 ref**: ref 是临时引用，不可复用

---

## 定位器测试清单

探索每个元素时，检查：

- [ ] 定位器类型是否适合该元素所在场景？
- [ ] 定位器是否唯一？(count === 1)
- [ ] 定位器是否可见？(is_visible === true)
- [ ] 定位器是否包含动态内容？(如时间戳、用户数据)
- [ ] 定位器在页面改版时是否容易失效？
- [ ] 定位器代码是否易读？
- [ ] 定位器是否使用了禁止的 ref？

---

## 记住

**用户看到什么，你就定位什么。**

这是选择定位器的黄金法则。

---

# 链式 filter 写法（企业 B 端场景主力）

> 来自 [Playwright 官方 Locators 文档](https://playwright.cn/docs/locators) 的
> 过滤定位器（filtering locators）章节。"列表中第 N 个"几乎一定走这条路。

## 核心：先定位语义容器，再在容器内定位目标

AntD / Pro / Material / Element Plus 类企业应用里，列表/卡片/表格/弹窗
经常出现多个"查看"、"编辑"、"删除"按钮。仅用 `getByRole('button', { name: '编辑' })`
必然 strict mode violation。

### 模式 A：role 锚点 + filter(hasText) + role 子元素

```python
# 资源列表中"资源 2"的编辑按钮
page.get_by_role('listitem').filter(has_text='资源 2').get_by_role('button', name='编辑')
```

适用范围：列表/表格行/卡片/列表项（role 是 `listitem` / `row` / `article` / `cell`）。

### 模式 B：testid 锚点 + filter(hasText) + role 子元素

```python
# 卡片有 data-testid="card-001" 时
page.get_by_test_id('card-001').get_by_role('button', name='编辑')
```

### 模式 C：testid 锚点 + filter(has: getByText) + role 子元素

```python
# 容器不直接有 text，但子元素有 —— 用 has 锚定
page.get_by_test_id('resource-list').filter(has=page.get_by_text('资源 A')).get_by_role('button', name='编辑')
```

### 模式 D：dialog/form 用 aria-label 锚点

```python
page.get_by_role('dialog', name='创建').get_by_role('button', name='确定')
# 或
page.get_by_label('创建资源表单').get_by_role('button', name='保存')
```

### 模式 E：链式多 filter

```python
# 同时按文本 + 子元素过滤
page.get_by_role('listitem').filter(has_text='Mary').filter(has=page.get_by_role('button', name='Say goodbye'))
```

### 模式 F：and / or

```python
# 同时满足"role=button 且 title=Subscribe"
page.get_by_role('button').and(page.get_by_title('Subscribe'))
# 匹配"新邮件按钮 或 安全对话框"；仅当任一目标都可接受时才使用 first()
new_email = page.get_by_role('button', name='新邮件')
dialog = page.get_by_text('确认安全设置')
new_email.or(dialog).first.click()
```

## 严格模式违规的处理策略

定位器命中多个元素时 Playwright 抛 `strict mode violation`。
后端 `click` / `fill` 工具会返回 `failure.error_type == locator_not_unique`，不会自动选择第一个元素：

1. 不要重复尝试同一 locator
2. 重新 snap 或观察当前上下文
3. 用父级容器、`filter({ hasText })`、`has` 或更精确的 role/name 缩小到唯一元素
4. 页面探索工具不使用 `.first()` / `.nth()` 解决歧义；必须用容器、`filter({ hasText })`、`filter({ has })` 或更精确的 role/name 缩小到唯一元素

## 严格禁止的写法

```python
# ❌ 临时 ref（每次 snap 都会变）
page.locator("ref=e15")
page.locator("ref=e20")

# ❌ XPath（DOM 改版就坏）
page.locator("//button[text()='提交']")
page.locator("xpath=//button")

# ❌ 动态类名（CSS Modules / 内联样式会变）
page.locator(".css-abc123")
page.locator("[class*='makeStyles-']")

# ❌ 结构依赖（页面布局变了就坏）
page.locator("div.container > div.content > div.panel > button")
page.locator("button:nth-child(3)")
```

## 红旗警告（v2 更新）

除了旧红旗，新增：

- 🚩 多个同名"编辑"/"删除"按钮没限定容器 → 必加 `.filter`
- 🚩 没用 `{ exact: true }` 的 placeholder/text 定位器 → 长文本/截断会失效
- 🚩 收到 `failure.recovered=true` 后还在 retry 同一定位器 → 浪费工具调用
- 🚩 弹窗内按钮没限定 dialog 容器 → 误中主页面同名按钮
- 🚩 `getByRole('button')` 不带 name → strict mode violation
- 🚩 用 `.first()` / `.nth()` 绕过 strict mode → 容易误点第一个同名元素

## popover / 弹层选项定位（必读）

snap 返回的元素中，`role` 为 `clickable`、`div`、`span` 且 `role_source` 为 `inferred` 的，
是 B 端 popover / dropdown 内的卡片式选项。这些元素**没有真实 ARIA role**。

**处理规则**：

1. **不要用 `getByRole('clickable', ...)`** —— Playwright 不支持 `clickable` 这个 role，永远会失败
2. **直接用 yaml 中的 text 候选**：`getByText('选项显示文本', { exact: true })`
3. **如果收到 `not_visible` 错误**：说明 popover 整体已被关闭（从 DOM 卸载），**必须重新点触发按钮**重新打开 popover，再点选项。不要改 locator。
4. **如果同名选项有多个**（strict mode）：用 popover/dialog 容器限定，例如：
   ```python
   page.locator('[role="popover"]').getByText('自主规划 Agent', { exact: true })
   ```
