# AI 编排审核侧边栏文本拖选复制实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 让 AI 编排审核侧边栏正文支持鼠标拖选文本并通过 Ctrl/Cmd+C 复制，同时保持左侧抽屉关闭拖动不变。

**Architecture:** 复用生成侧边栏已有的 select-text! Tailwind 类，只作用于审核抽屉的正文滚动容器。保留 Drawer direction="right" handleOnly 和独立 DrawerHandle，不改全局抽屉行为，也不触碰字段编辑逻辑。

**Tech Stack:** Next.js、React、TypeScript、Tailwind CSS、Biome、Node.js 内置测试。

## Global Constraints

- 只修改审核侧边栏相关文件和对应契约测试。
- 复用现有 select-text! 模式，不新增依赖、不新增组件。
- 不改变输入框、文本域、下拉框、按钮和抽屉关闭拖动行为。
- 不修改后端接口或 AI 编排数据模型。

---

### Task 1: 为文本拖选行为补充契约测试

**Files:**
- Modify: pps/frontend/tests/api-scenario-ai-generation-drawer-contract.test.mjs，在“AI orchestration drawer separates dragging from text selection”测试附近增加审核侧边栏正文断言。
- Read: pps/frontend/src/components/ai-testing/api-automation/api-scenario-ai-review-drawer.tsx，使用其源码字符串作为测试输入。

**Interfaces:**
- Consumes: eviewDrawerSource，测试文件现有的审核侧边栏源码变量。
- Produces: 对审核侧边栏正文容器必须包含 select-text! 的静态契约。

- [ ] **Step 1: 写失败断言**

在现有测试文件中增加：

`js
 test("AI review drawer allows text selection without changing drawer dragging", () => {
   assert.match(reviewDrawerSource, /<div className="select-text! min-h-0 space-y-4 overflow-y-auto/);
   assert.match(reviewDrawerSource, /<Drawer direction="right" handleOnly/);
   assert.match(reviewDrawerSource, /<DrawerHandle[\\s\\S]*?cursor-ew-resize/);
 });
`

保留测试文件当前的缩进和断言风格；若当前文件使用无前导空格的 	est，按现有格式调整。

- [ ] **Step 2: 运行定向测试确认失败**

Run: cd apps/frontend; node --test tests/api-scenario-ai-generation-drawer-contract.test.mjs

Expected: 新增测试失败，因为审核侧边栏正文当前 className 不含 select-text!；其他既有测试结果保持不变。

### Task 2: 启用审核正文文本拖选

**Files:**
- Modify: pps/frontend/src/components/ai-testing/api-automation/api-scenario-ai-review-drawer.tsx:106，修改正文滚动容器的 className。

**Interfaces:**
- Consumes: Task 1 的源码契约。
- Produces: 审核侧边栏正文根滚动容器具有 select-text!，其余组件结构与回调签名不变。

- [ ] **Step 1: 做最小实现**

将现有正文容器：

`	sx
<div className="min-h-0 space-y-4 overflow-y-auto bg-muted/10 px-4 py-4 sm:px-6">
`

改为：

`	sx
<div className="select-text! min-h-0 space-y-4 overflow-y-auto bg-muted/10 px-4 py-4 sm:px-6">
`

不要修改 DrawerHandle、字段组件、移动步骤回调或 API 数据。

- [ ] **Step 2: 运行定向契约测试**

Run: cd apps/frontend; node --test tests/api-scenario-ai-generation-drawer-contract.test.mjs

Expected: 全部测试 PASS。

- [ ] **Step 3: 运行 Biome 检查**

Run: cd apps/frontend; pnpm exec biome check src/components/ai-testing/api-automation/api-scenario-ai-review-drawer.tsx tests/api-scenario-ai-generation-drawer-contract.test.mjs

Expected: 命令成功退出且无格式或 lint 错误。

### Task 3: 完成手工交互验证

**Files:**
- Verify: pps/frontend/src/components/ai-testing/api-automation/api-scenario-ai-review-drawer.tsx
- Verify: pps/frontend/src/components/ai-testing/api-automation/api-scenario-ai-review-step-card.tsx
- Verify: pps/frontend/src/components/ai-testing/api-automation/api-scenario-ai-review-field.tsx

**Interfaces:**
- Consumes: Task 2 的审核侧边栏 UI。
- Produces: 可复现的浏览器验证结果，不新增代码。

- [ ] **Step 1: 打开审核 AI 编排方案侧边栏**

使用现有前端启动方式打开对应页面，并生成或载入一份包含多个步骤、路径和字段的 AI 编排方案。

- [ ] **Step 2: 验证普通文本复制**

在步骤路径、字段名、字段路径、错误提示和“已自动确定”内容上拖动选中文本，使用 Windows/Linux 的 Ctrl+C 或 macOS 的 Cmd+C，确认可以粘贴出选中文本。

- [ ] **Step 3: 验证控件和关闭拖动未回归**

确认 Input/Textarea 仍可编辑，下拉框仍可打开选择，确认按钮仍可点击；拖动左侧窄条仍可关闭侧边栏，拖动正文不会触发抽屉关闭。

## Self-review

- 设计目标覆盖：正文文本可拖选复制由 Task 2 实现，快捷键复制由浏览器原生选择模型提供。
- 交互边界覆盖：左侧 DrawerHandle 和 handleOnly 由 Task 1 契约测试锁定，控件行为由 Task 3 手工验证。
- 未引入新接口、依赖或全局行为修改。
- 计划中无 TODO、TBD 或占位实现。
