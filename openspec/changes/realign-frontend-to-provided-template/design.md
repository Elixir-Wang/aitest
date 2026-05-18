## Context

当前仓库存在两个前端相关目录：

- `next-shadcn-admin-dashboard-main`：用户提供的真实前端基础项目，包含 Next.js 16、React 19、Tailwind CSS v4、shadcn/ui、Biome、Zustand、内置认证页面、后台 dashboard layout、sidebar、theme/preferences 和共置式目录结构。
- `apps/frontend`：上一轮错误实现出的简化版 Next.js 壳层，仅具备少量页面、手写样式和基础 API client，没有继承模板的技术栈、内置登录和组件体系。

本变更不是新增业务能力，而是纠正前端工程基线。后续 AI 测试系统前端必须落在模板体系内，而不是在简化版壳层上继续开发。

## Goals / Non-Goals

**Goals:**

- 以 `next-shadcn-admin-dashboard-main` 作为 `apps/frontend` 的唯一前端基线。
- 保留模板技术栈、脚本、依赖、Tailwind v4、Biome、shadcn/ui 配置、theme/preferences、sidebar 和 dashboard layout。
- 复用模板内置登录模块，改造其 login form 对接 `/api/v1/auth/login`，登录成功后保存 token 并进入业务 dashboard。
- 将 AI 测试系统第一阶段页面迁移到模板共置式目录结构中。
- 将当前简化版 `apps/frontend` 的可用业务逻辑选择性迁移，而不是把简化版作为主结构。
- 提供可验证启动链路：`npm install`、`npm run dev`、登录、导航、项目切换器和基础页面可用。

**Non-Goals:**

- 不改变后端 API 业务契约。
- 不新增需求分析、站点探索、知识库、测试用例生成、UI 自动化执行、失败诊断、自愈或接口自动化真实能力。
- 不在本变更中做大规模视觉重设计；优先使用模板已有组件和布局语言。
- 不保留模板示例业务页面作为 AI 测试系统正式导航入口；未迁移页面可作为代码参考或移入 legacy/reference 范围。

## Decisions

### 1. 用模板覆盖式重建 `apps/frontend`

实施时先备份或删除当前简化版 `apps/frontend`，再将 `next-shadcn-admin-dashboard-main` 的工程结构复制为新的 `apps/frontend` 基线。之后再迁移 AI 测试系统页面和 API 接入。

选择原因：当前 `apps/frontend` 与模板技术栈差异过大。增量修补会持续留下错误基线，例如 Next 14/React 18、手写 CSS、非模板登录、非模板 sidebar。

替代方案：在当前简化版上逐步复制模板组件。该方案容易产生半模板半自建结构，放弃。

### 2. 复用模板内置登录，不新增 `/login`

模板内置登录位于 `src/app/(main)/auth/v1/login/page.tsx`、`src/app/(main)/auth/v2/login/page.tsx` 和 `src/app/(main)/auth/_components/login-form.tsx`。本系统应选择一个版本作为正式登录页，推荐优先使用 v1 或模板默认入口，并将登录表单改造为：

- 输入用户名或邮箱、密码。
- 调用后端 `POST /api/v1/auth/login`。
- 处理 `{ data, trace_id }` 和错误响应。
- 成功后保存 token、当前用户基础信息，并跳转到 AI 测试系统 dashboard。
- 不开放注册入口；模板 register 页面必须隐藏、禁用或移出正式导航。

选择原因：用户已明确模板内置登录模块，重复创建 `/login` 是偏离模板。

### 3. 保留模板 sidebar/layout，但重写导航配置

保留模板 dashboard layout、sidebar 组件、折叠行为、theme 和 preferences。只替换导航数据为 AI 测试系统一级导航：

- 工作台
- 项目工作区
- 测试资产
- 任务与报告
- 系统管理

左侧不常驻二级菜单；项目详情、任务详情、系统设置等页面内使用 Tabs、面包屑或局部入口承载二级结构。接口自动化仍显示 Soon 且禁用创建、生成、执行。

### 4. API client 迁移到模板 `src/lib` 和状态体系

保留统一 API 适配思路，但按模板结构迁移：

- `src/lib/api` 或 `src/server/api` 负责 API envelope、list envelope、统一错误、登录失效识别。
- token 和当前用户状态使用模板已有 store/hook 方式承载，若模板无认证 store，则新增最小 `auth-store`。
- 项目切换器状态优先使用 Zustand，与模板 preferences/store 风格一致。

### 5. 页面采用模板共置式结构

AI 测试系统页面放入模板 App Router 和共置式结构中，页面本地组件留在对应 route 的 `_components` 下，共用领域组件放在 `src/components` 或 `src/components/ai-testing`：

- dashboard：AI 测试系统控制台
- projects：项目列表
- projects/[projectId]：项目详情
- tasks：任务中心
- tasks/[taskId]：任务详情
- settings/users：用户与权限
- settings/system：系统设置
- settings/models：模型配置入口
- projects/[projectId]/automation/api：接口自动化 Soon

### 6. 当前简化版只作为迁移素材

当前简化版 `apps/frontend` 可迁移的内容只有：

- 后端 API envelope/list/error/auth-expired 的处理思路。
- 项目切换器、available_actions、状态中文展示的领域逻辑。
- 第一阶段页面信息架构和占位内容。

不迁移其工程配置、手写全局样式、独立 `/login` 页面和简化 layout。

## Risks / Trade-offs

- [Risk] 直接以模板重建会产生大量文件变更。→ Mitigation: 在 tasks 中先做差异盘点，再执行模板基线替换，并用 git diff 明确哪些来自模板、哪些是业务改造。
- [Risk] 模板依赖较新，Next 16/React 19 可能对本地 Node 版本有要求。→ Mitigation: 实施前记录 Node/npm 版本，若版本不满足，先报告并暂停，不降级模板。
- [Risk] 模板内置注册页与“管理员创建账号、禁止公开注册”冲突。→ Mitigation: 正式导航和入口移除注册；直接访问 register 页时展示禁用说明或重定向登录。
- [Risk] 模板示例 dashboard 页面很多，可能污染 AI 测试系统导航。→ Mitigation: 导航配置只保留 AI 测试系统入口，示例页面不进入正式导航。
- [Risk] API client 迁移时可能再次出现 CORS 或登录态失效问题。→ Mitigation: 验证任务必须覆盖浏览器登录链路，而不仅是接口直调。

## Migration Plan

1. 记录当前 `apps/frontend` 文件清单，标记保留、废弃、迁移项。
2. 复制 `next-shadcn-admin-dashboard-main` 到 `apps/frontend` 作为基线，保留模板 lockfile、Biome、Tailwind、shadcn、components.json、tsconfig。
3. 改造模板登录页，对接后端登录 API，禁用公开注册入口。
4. 替换 sidebar/navigation 配置为 AI 测试系统一级导航。
5. 迁移 API client、auth store、project context store、ProjectSwitcher、AvailableActions、状态组件。
6. 按模板共置式结构创建项目、任务、设置等页面。
7. 运行 `npm install`、`npm run check` 或可用 lint/check、`npm run dev`。
8. 启动后端，使用浏览器验证登录、跳转、导航、项目切换器和基础页面。

回滚策略：若迁移失败，保留 `next-shadcn-admin-dashboard-main` 原始目录不动，可删除新的 `apps/frontend` 并重新复制模板；后端不受影响。

## Open Questions

- 模板登录正式采用 v1 还是 v2 页面，需要实施时根据当前模板默认路由和视觉适配选择。
- 是否保留模板示例 dashboard 作为开发参考页面，还是从 `apps/frontend` 中删除以减少干扰，需要实施时基于改动量决定。
- 当前 Node.js 版本是否满足 Next.js 16 的运行要求，需要编码前用本机命令确认。
