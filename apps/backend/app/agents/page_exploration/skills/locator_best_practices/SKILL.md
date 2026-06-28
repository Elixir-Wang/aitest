---
name: locator-best-practices
description: Expert guidance on selecting stable, maintainable Playwright locators with priority on semantic locators (getByRole, getByLabel) and avoiding fragile selectors like ref, CSS classes, and XPath.
---

# Locator Best Practices

你是一个专业的 Playwright 定位器选择专家。你的任务是为网页元素选择最稳定、最可维护的定位器。

---

## 核心原则

1. **优先使用语义定位器** - 基于角色、标签、文本等语义信息
2. **避免脆弱定位器** - 不使用 CSS 选择器、XPath、临时引用
3. **确保唯一性** - 每个定位器必须唯一标识一个元素
4. **确保可维护性** - 代码易读，页面改版时容易更新

---

## 定位器优先级（从高到低）

### 1. getByRole (最高优先级) ⭐⭐⭐⭐⭐

**为什么优先**:
- 基于 ARIA 角色，最符合无障碍标准
- 最稳定，页面样式改变不影响
- 语义化强，代码可读性好

**适用场景**:
- 按钮: `getByRole('button', { name: '创建智能体' })`
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
page.get_by_role("button", name="提交订单")
page.get_by_role("link", name="查看详情")
page.get_by_role("textbox", name="搜索")

# ❌ 避免
page.locator("button.submit-btn")  # CSS 选择器
page.locator("//button[text()='提交']")  # XPath
```

---

### 2. getByLabel (表单字段首选) ⭐⭐⭐⭐

**为什么优先**:
- 明确关联表单字段和标签
- 符合无障碍标准
- 用户看到什么，你就定位什么

**适用场景**:
- 所有带 `<label>` 的表单字段
- aria-label 或 aria-labelledby 的元素

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

### 3. getByTestId (开发专门添加) ⭐⭐⭐⭐

**为什么推荐**:
- 开发专门为测试添加的标识
- 不会因为业务逻辑改变而变化
- 明确表示这是测试专用

**适用场景**:
- 元素没有合适的 role 或 label
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

### 4. getByText (文本内容定位) ⭐⭐⭐

**为什么使用**:
- 用户看到什么，你就定位什么
- 适合文本固定的场景
- 简单直观

**适用场景**:
- 静态文本（标题、标签、提示）
- 按钮文本（如果没有合适的 role）

**注意事项**:
- ⚠️ 文本变化会导致定位器失效
- ⚠️ 多语言项目需要考虑国际化

**示例**:
```python
# ✅ 适合的场景
page.get_by_text("欢迎回来")  # 固定标题
page.get_by_text("暂无数据")  # 固定提示

# ⚠️ 需要谨慎的场景
page.get_by_text("张三")  # 用户数据，可能变化
page.get_by_text("2024-01-01")  # 动态日期
```

**精确匹配 vs 模糊匹配**:
```python
# 精确匹配
page.get_by_text("提交", exact=True)

# 模糊匹配（包含即可）
page.get_by_text("提交")  # 会匹配 "提交订单"
```

---

### 5. getByPlaceholder (输入框占位符) ⭐⭐⭐

**适用场景**:
- 输入框有 placeholder 属性
- 没有对应的 label

**示例**:
```python
# ✅ 适合的场景
page.get_by_placeholder("请输入手机号")
page.get_by_placeholder("搜索商品")

# 对应的 HTML:
# <input placeholder="请输入手机号" />
```

**注意**:
- placeholder 可能变化，不如 label 稳定
- 优先使用 getByLabel，placeholder 作为备选

---

### 6. CSS 选择器（最后选择）⭐

**什么时候使用**:
- 前面所有方法都不适用
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
page.get_by_role("button", name="删除智能体")
```

3. **组合多个定位器**
```python
# ✅ 先定位容器，再定位元素
dialog = page.get_by_role("dialog", name="确认删除")
dialog.get_by_role("button", name="确定")
```

---

## 定位器决策树

```
开始
 │
 ├─ 是按钮/链接/输入框等标准元素？
 │   └─ 是 → 使用 getByRole ✅
 │
 ├─ 是表单字段？
 │   └─ 是 → 使用 getByLabel ✅
 │
 ├─ 有 data-testid？
 │   └─ 是 → 使用 getByTestId ✅
 │
 ├─ 有唯一且稳定的文本？
 │   └─ 是 → 使用 getByText ✅
 │
 ├─ 是输入框且有 placeholder？
 │   └─ 是 → 使用 getByPlaceholder ✅
 │
 └─ 以上都不适用？
     └─ 使用 CSS 选择器（尽量用 data 属性或 id）⚠️
```

---

## 常见场景示例

### 场景 1: 导航菜单

```python
# ✅ 好的做法
page.get_by_role("navigation").get_by_role("link", name="智能体工作台")
page.get_by_role("navigation").get_by_role("link", name="知识库")

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
page.get_by_role("textbox", name="搜索").fill("智能体")
page.get_by_role("button", name="搜索").click()

# 或者使用 placeholder
page.get_by_placeholder("请输入关键词").fill("智能体")
page.get_by_role("button", name="搜索").click()

# ❌ 避免
page.locator(".search-input").fill("智能体")
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

1. ✅ **优先使用语义定位器**: getByRole > getByLabel > getByTestId
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

- [ ] 定位器类型是否是最高优先级的可行方案？
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
