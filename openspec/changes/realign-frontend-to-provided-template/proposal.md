## Why

当前 `apps/frontend` 被实现成了一个简化 Next.js 壳层，没有基于用户提供的 `next-shadcn-admin-dashboard-main` 前端基础项目进行设计和改造，导致技术栈、目录结构、内置登录、布局系统、组件体系和验证方式都偏离了已确认前端方案。需要补一个纠偏变更，把前端实现重新对齐到模板项目，避免后续继续在错误基线上堆功能。

本变更用于修正第一阶段前端落地基线：以后续编码必须以 `next-shadcn-admin-dashboard-main` 为源模板，复用其内置认证页面、后台壳层、导航、shadcn/ui 组件、Tailwind v4、Biome 和共置式目录结构。

## What Changes

- **BREAKING**：废弃当前 `apps/frontend` 的简化版自建壳层，不再以该结构继续扩展。
- 以 `next-shadcn-admin-dashboard-main` 作为 `apps/frontend` 的前端工程基线：
  - Next.js 16、React 19、Tailwind CSS v4、shadcn/ui、Lucide、React Hook Form、Zod、TanStack Table、Zustand、Biome。
  - 保留模板的 `src/app/(main)/auth/...` 内置登录模块，优先改造其 login form 对接后端登录 API，而不是另写 `/login` 页面。
  - 保留模板的后台 dashboard layout、sidebar、theme、preferences、shared ui 和 colocation 目录约定。
- 盘点当前简化版 `apps/frontend` 与模板差异，形成保留、废弃、迁移清单。
- 将 AI 测试系统页面迁移到模板结构中：
  - 控制台、项目列表、项目详情、任务中心、任务详情、用户与权限、系统设置、模型配置、接口自动化 Soon 页面。
  - 左侧一级导航按模板 sidebar 配置实现，不展示二级常驻菜单。
  - 页面内二级 Tabs、项目切换器、available_actions、状态中文展示按现有后端 API 继续接入。
- 保留后端 API client 思路，但迁移到模板的 `src/lib`、store、hook 和组件规范中。
- 增加验证任务，确保：
  - `npm install` 能安装模板依赖。
  - `npm run dev` 能启动。
  - 模板内置登录页能登录后端。
  - 基础页面、导航、项目切换器、任务/项目/设置页面可打开。

暂不实现：

- 新业务能力：需求分析、站点探索、知识库、测试用例生成、UI 自动化执行、失败诊断、自愈。
- 真实模型调用、Agent Runtime 调度。
- 接口自动化真实创建、生成或执行。

## Capabilities

### New Capabilities

- `frontend-template-alignment`: 约束 AI 测试系统前端必须基于 `next-shadcn-admin-dashboard-main` 模板落地，包括模板技术栈、内置登录、后台壳层、导航、组件体系、迁移策略和运行验证。

### Modified Capabilities

- 无。本变更不改变已归档的后端、项目、任务、设置、权限和导航业务需求，只修正前端实现基线与验收要求。

## Impact

- 前端：
  - 影响 `apps/frontend` 的工程结构、依赖、路由、登录页、layout、sidebar、组件、样式、API client 和测试。
  - 以 `next-shadcn-admin-dashboard-main` 为模板源，迁移而不是重写简化壳层。
- 后端：
  - 后端 API 保持第一阶段地基实现不变。
  - 登录、当前用户、项目、任务、设置接口仍作为前端接入目标。
- OpenSpec：
  - 新增 `frontend-template-alignment` 能力规格。
  - 本 change 完成后再归档到主 specs。
- 上游依据：
  - `docs/05-前端方案/05-01-AI测试系统-前端总体方案PRD.md`
  - `docs/05-前端方案/05-02-AI测试系统-导航与页面映射清单.md`
  - `docs/00-产品文档/00-01-AI测试系统-PRD.md`
  - `next-shadcn-admin-dashboard-main/README.md`
  - `next-shadcn-admin-dashboard-main/package.json`
