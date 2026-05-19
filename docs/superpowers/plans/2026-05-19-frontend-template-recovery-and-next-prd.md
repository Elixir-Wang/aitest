# 前端继续补充与下一步 PRD 计划

> **给执行型 agent：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐项执行本计划。步骤使用 `- [ ]` 复选框跟踪。

**目标：** 在当前已改造的一版 `apps/frontend` 上继续补齐功能和体验，保留 `next-shadcn-admin-dashboard-main` 的模板能力，不再使用 OpenSpec，不再重走从零回正流程。

**架构：** `apps/frontend` 是 AI 测试系统前端实现目录；`next-shadcn-admin-dashboard-main` 只作为模板参考和回归对照。产品范围以 `docs/05-前端方案` 和 `docs/00-产品文档` 为准。

**技术栈：** Next.js 16、React 19、shadcn/ui、Tailwind CSS v4、Lucide Icons、React Hook Form、Zod、TanStack Table、Zustand、Biome。

---

## 当前判断

- 当前前端已经完成一版模板化改造，不再需要“重新恢复模板基线”的大计划。
- 下一步重点是补齐遗漏项：登录保护、项目上下文、导航动态化、页面统一组件、列表选择框与本地删除、无用模板示例入口清理、浏览器验收。
- 业务 PRD 暂不直接开工，等前端壳层稳定后再进入 `00-03-AI测试系统-需求文档分析与版本管理PRD.md`。

## 待办总览

- [ ] 阶段 1：确认当前前端缺口。
- [ ] 阶段 2：补齐登录与路由保护。
- [ ] 阶段 3：补齐项目上下文与导航动态化。
- [ ] 阶段 4：统一页面组件和状态文案。
- [ ] 阶段 5：补齐所有列表的选择框和本地删除。
- [ ] 阶段 6：清理无用模板入口。
- [ ] 阶段 7：运行检查和浏览器验收。
- [ ] 阶段 8：生成下一份业务 PRD 实施计划。

---

## 关键文件

- `apps/frontend/package.json`
- `apps/frontend/src/app/page.tsx`
- `apps/frontend/src/app/(main)/auth`
- `apps/frontend/src/app/(main)/dashboard/layout.tsx`
- `apps/frontend/src/app/(main)/dashboard/_components/sidebar`
- `apps/frontend/src/app/(main)/projects`
- `apps/frontend/src/app/(main)/tasks`
- `apps/frontend/src/app/(main)/reports`
- `apps/frontend/src/app/(main)/settings`
- `apps/frontend/src/components/ai-testing`
- `apps/frontend/src/navigation/sidebar/sidebar-items.ts`
- `apps/frontend/src/lib`
- `apps/frontend/src/stores`
- `apps/frontend/README.md`
- `docs/05-前端方案/05-01-AI测试系统-前端总体方案PRD.md`
- `docs/05-前端方案/05-02-AI测试系统-导航与页面映射清单.md`

---

## 阶段 1：确认当前前端缺口

### 任务 1：列出当前页面和导航状态

**文件：**
- 阅读：`apps/frontend/src/navigation/sidebar/sidebar-items.ts`
- 阅读：`apps/frontend/src/app/(main)`
- 阅读：`apps/frontend/src/components/ai-testing`

- [ ] **步骤 1：列出当前业务页面**

运行：

```powershell
Get-ChildItem -Recurse -File apps\frontend\src\app\(main) | Select-Object -ExpandProperty FullName
```

预期：能看到登录、控制台、项目、任务、报告、设置和各项目内页面。

- [ ] **步骤 2：核对侧边栏导航**

确认 `apps/frontend/src/navigation/sidebar/sidebar-items.ts` 中只包含：

```text
工作台: 控制台, 任务中心
项目工作区: 项目, 需求, 探索, 知识库
测试资产: 测试用例, UI 自动化, 接口自动化, 报告中心
系统管理: 模型配置, 用户与权限, 系统设置
```

- [ ] **步骤 3：记录实际缺口**

在本计划的“当前缺口记录”中补充实际结果。

### 当前缺口记录

- [ ] 项目作用域导航目前是否仍硬编码 `/projects/zhiliao/...`。
- [ ] 未登录访问 `/dashboard`、`/projects`、`/tasks`、`/reports`、`/settings/*` 是否会跳到登录页。
- [ ] `ProjectSwitcher` 是否真正驱动当前项目上下文，而不仅是静态展示。
- [ ] 控制台、项目、任务、报告、设置页面是否使用统一 `PageShell`。
- [ ] 接口自动化是否只有 Soon/禁用状态，没有创建、生成、执行入口。
- [ ] CRM、Finance、E-commerce、Academy、Productivity、Analytics 是否仍出现在产品导航或默认入口中。

---

## 阶段 2：补齐登录与路由保护

### 任务 2：统一登录入口和未登录跳转

**文件：**
- 修改：`apps/frontend/src/app/page.tsx`
- 修改：`apps/frontend/src/app/(main)/auth/_components/login-form.tsx`
- 修改：`apps/frontend/src/app/(main)/dashboard/layout.tsx`
- 需要时新增或修改：`apps/frontend/src/lib/auth`
- 需要时新增或修改：`apps/frontend/src/stores`

- [ ] **步骤 1：确认正式登录入口**

正式登录入口固定为：

```text
/auth/v1/login
```

根路径 `/` 应按登录态跳转：未登录到 `/auth/v1/login`，已登录到 `/dashboard`。

- [ ] **步骤 2：保护业务路由**

这些路由未登录时必须跳转到 `/auth/v1/login`：

```text
/dashboard
/projects
/projects/:projectId/*
/tasks
/reports
/settings/*
```

- [ ] **步骤 3：登录态失效清理**

API 返回未授权或 token 失效时：

```text
清理 token
清理当前用户
清理项目上下文中依赖登录态的临时状态
跳转 /auth/v1/login
展示中文错误提示
```

- [ ] **步骤 4：禁用注册入口**

注册页只展示“请联系管理员创建账号”，不能出现可提交注册表单。

- [ ] **步骤 5：验证**

运行：

```powershell
cd apps\frontend
npm run check
npm run dev
```

浏览器验证：

```text
/dashboard
/projects
/tasks
/reports
/settings/users
```

预期：未登录访问都会进入 `/auth/v1/login`。

---

## 阶段 3：补齐项目上下文与导航动态化

### 任务 3：移除项目作用域导航硬编码

**文件：**
- 修改：`apps/frontend/src/navigation/sidebar/sidebar-items.ts`
- 修改：`apps/frontend/src/app/(main)/dashboard/_components/sidebar/nav-main.tsx`
- 修改：`apps/frontend/src/components/ai-testing/project-switcher.tsx`
- 需要时新增或修改：`apps/frontend/src/stores/project-context-store.ts`

- [ ] **步骤 1：保留导航元数据，不硬编码具体项目**

`sidebar-items.ts` 中项目作用域页面可以保留抽象路由或标记：

```text
/projects/:projectId/requirements
/projects/:projectId/exploration
/projects/:projectId/knowledge
/projects/:projectId/test-cases
/projects/:projectId/automation/ui
/projects/:projectId/automation/api
```

不要把产品导航永久写成 `/projects/zhiliao/...`。

- [ ] **步骤 2：点击项目作用域导航时读取当前项目**

如果有当前项目：

```text
跳转 /projects/{currentProjectId}/...
```

如果没有当前项目：

```text
跳转 /projects
或禁用入口并提示“请先选择项目”
```

- [ ] **步骤 3：区分全部项目和指定项目**

控制台、任务中心、报告中心允许“全部项目”。

需求、探索、知识库、测试用例、UI 自动化、接口自动化必须使用指定项目。

- [ ] **步骤 4：验证**

浏览器验证：

```text
选择全部项目后，项目强绑定入口不可直接执行写操作。
选择指定项目后，项目强绑定入口进入对应项目页面。
```

---

## 阶段 4：统一页面组件和状态文案

### 任务 4：补齐共享组件

**文件：**
- 修改：`apps/frontend/src/components/ai-testing/page-shell.tsx`
- 修改：`apps/frontend/src/components/ai-testing/project-switcher.tsx`
- 需要时新增：`apps/frontend/src/components/ai-testing/status-badge.tsx`
- 需要时新增：`apps/frontend/src/components/ai-testing/empty-state.tsx`
- 需要时新增：`apps/frontend/src/components/ai-testing/confirm-risk-dialog.tsx`

- [ ] **步骤 1：统一页面头部**

项目、任务、报告、设置、项目内模块页面统一使用 `PageShell` 或同等页面壳层，包含：

```text
标题
说明
面包屑或上级入口
主操作按钮
项目切换器
```

- [ ] **步骤 2：统一状态展示**

如果多个页面展示任务状态、项目状态、风险状态，抽成 `StatusBadge`，中文标签集中维护。

- [ ] **步骤 3：统一空状态**

列表为空、功能未启用、暂无结果使用统一 `EmptyState`。

- [ ] **步骤 4：统一高风险确认**

归档、恢复、删除、执行、生成等高风险操作使用统一确认弹窗，至少展示：

```text
当前项目
对象名称
影响范围
不可逆或风险说明
确认按钮
取消按钮
```

- [ ] **步骤 5：验证**

运行：

```powershell
cd apps\frontend
npm run check
```

预期：检查通过。

---

## 阶段 5：清理无用模板入口

### 任务 5：隐藏或移除产品入口中的模板示例业务

**文件：**
- 修改：`apps/frontend/src/navigation/sidebar/sidebar-items.ts`
- 修改：`apps/frontend/src/app/(main)/dashboard/page.tsx`
- 需要时修改：`apps/frontend/src/app/(main)/dashboard/default/page.tsx`
- 需要时修改：`apps/frontend/src/app/(main)/dashboard/coming-soon/page.tsx`

- [ ] **步骤 1：确认产品导航无示例业务**

产品导航中不能出现：

```text
CRM
Finance
E-commerce
Academy
Productivity
Analytics
legacy demo
```

- [ ] **步骤 2：确认默认入口是 AI 测试系统控制台**

`/dashboard` 必须进入 AI 测试系统控制台，不进入模板示例页。

- [ ] **步骤 3：保留模板文件但不作为产品入口**

如果示例文件仍作为模板参考存在，可以保留；但不能在 sidebar、搜索入口、默认跳转中出现。

---

## 阶段 6：运行检查和浏览器验收

### 任务 6：执行本地检查

**文件：**
- 修改：`apps/frontend/README.md`

- [ ] **步骤 1：安装依赖**

运行：

```powershell
cd apps\frontend
npm install
```

预期：安装成功。

- [ ] **步骤 2：运行静态检查**

运行：

```powershell
npm run check
```

预期：无 Biome 错误。

- [ ] **步骤 3：启动前端**

运行：

```powershell
npm run dev
```

预期：前端服务启动成功。

- [ ] **步骤 4：浏览器验收核心路由**

验收：

```text
/auth/v1/login
/dashboard
/projects
/projects/zhiliao
/projects/zhiliao/requirements
/projects/zhiliao/exploration
/projects/zhiliao/knowledge
/projects/zhiliao/test-cases
/projects/zhiliao/automation/ui
/projects/zhiliao/automation/api
/tasks
/reports
/settings/users
/settings/models
/settings/system
```

预期：

- 登录页是模板认证风格。
- 控制台是 AI 测试系统控制台。
- 侧边栏只显示 AI 测试系统导航。
- 项目切换器可用。
- 接口自动化只有 Soon/禁用状态。
- 页面在 `1440x900` 和 `390x844` 下无明显遮挡或溢出。

- [ ] **步骤 5：更新 README**

`apps/frontend/README.md` 至少记录：

```text
启动命令
登录路由
默认后端 API 地址
当前不使用 OpenSpec
前端以 next-shadcn-admin-dashboard-main 为模板参考
```

---

## 阶段 7：生成下一份业务 PRD 实施计划

### 任务 7：规划 `00-03` 需求文档分析

**文件：**
- 阅读：`docs/00-产品文档/00-03-AI测试系统-需求文档分析与版本管理PRD.md`
- 阅读：`docs/03-后端架构与数据/03-01-AI测试系统-后端架构PRD.md`
- 阅读：`docs/03-后端架构与数据/03-02-AI测试系统-数据模型PRD.md`
- 创建：`docs/superpowers/plans/2026-05-19-requirement-document-analysis.md`

- [ ] **步骤 1：提取 MVP 范围**

只规划第一版最小闭环：

```text
需求文档上传
需求文档版本管理
Markdown 工作稿
需求分析任务
澄清问题
模块评审
来源引用
```

- [ ] **步骤 2：生成独立计划**

生成新的中文实施计划文件：

```text
docs/superpowers/plans/2026-05-19-requirement-document-analysis.md
```

- [ ] **步骤 3：先不实现**

前端补齐和验收完成前，不开始 `00-03` 的代码实现。

---

## 完成条件

- [ ] 未登录业务路由会跳到 `/auth/v1/login`。
- [ ] 项目作用域导航不再硬编码单个项目。
- [ ] `ProjectSwitcher` 能表达“全部项目/指定项目”。
- [ ] 产品导航与 `docs/05-前端方案/05-02-AI测试系统-导航与页面映射清单.md` 一致。
- [ ] `/dashboard` 是 AI 测试系统控制台。
- [ ] 接口自动化保持 Soon/禁用状态。
- [ ] 模板示例业务不再作为产品入口出现。
- [ ] `npm run check` 通过。
- [ ] 核心路由通过桌面和移动端浏览器验收。
- [ ] 已生成 `00-03` 的独立实施计划。
