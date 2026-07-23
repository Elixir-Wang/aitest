# 接口自动化 AI 修复 Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or **superpowers:executing-plans** to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将接口自动化失败运行详情中的内嵌 AI 修复 Panel 替换为与性能测试视觉一致、但代码和业务完全独立的右侧 Drawer。

**Architecture:** 保留现有接口自动化修复 API、Session、Attempt 和轮询流程。新增接口自动化专属 Drawer、进度组件和 Diff Dialog；运行详情只负责入口、开关状态和运行刷新。性能测试目录不做任何修改，也不被接口自动化组件导入。

**Tech Stack:** React 19、Next.js、TypeScript、现有 Drawer/Dialog/Button/Badge、Lucide、Sonner、Node `node:test`、Biome。

## Global Constraints

- 不修改性能测试 AI 分析代码。
- 不抽取或导入跨业务共享组件。
- 不修改接口自动化后端 API 和状态机。
- 按钮权限以后端 `available_actions` 为准。
- 关闭 Drawer 不终止后台任务。
- 保留工作区现有无关改动。

---

## Task 1: 锁定 Drawer 前端契约

**Files:**
- Modify: `apps/frontend/tests/api-automation-ai-repair-contract.test.mjs`
- Modify: `apps/frontend/src/lib/api-client.ts`

**Interfaces:**
- Consumes: 现有 API 修复客户端函数和后端 `available_actions` 字段。
- Produces: Drawer 入口、阶段、审批动作、独立性和客户端类型契约。

- [ ] 更新契约测试，要求运行详情挂载 `ApiRepairDrawer`。
- [ ] 更新契约测试，要求存在右侧 Drawer、进度、Diff 和审批文案。
- [ ] 更新契约测试，要求接口自动化不导入性能测试组件。
- [ ] 运行定向契约测试并确认先失败。

## Task 2: 实现接口自动化独立进度组件

**Files:**
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-repair-progress.tsx`

**Interfaces:**
- Consumes: 接口自动化 Attempt 状态字符串。
- Produces: 接口自动化独立的阶段时间线和人类可读状态。

- [ ] 定义接口自动化状态到阶段的本地映射。
- [ ] 实现未开始、执行中、完成和失败视觉状态。
- [ ] 覆盖收集、诊断、生成、回归、审批、应用和重跑阶段。

## Task 3: 实现接口自动化独立 Diff Dialog

**Files:**
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-repair-diff-dialog.tsx`

**Interfaces:**
- Consumes: Diff 文本、打开状态和关闭回调。
- Produces: 加载、错误、空 Diff 和正常 Diff 展示。

- [ ] 复制现有 Dialog 视觉基准并保持接口自动化目录独立。
- [ ] 支持长 Diff 滚动和关闭后保留 Drawer 状态。

## Task 4: 实现接口自动化独立 Drawer

**Files:**
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-repair-drawer.tsx`
- Delete: `apps/frontend/src/components/ai-testing/api-automation/api-repair-panel.tsx`

**Interfaces:**
- Consumes: `projectId`、失败运行、`open`、`onOpenChange`、`onRunChanged`。
- Produces: 创建/恢复会话、轮询、诊断、验证统计、审批操作和继续修复。

- [ ] 复制性能 Drawer 的布局和视觉样式到接口自动化专属组件。
- [ ] 迁移现有 Panel 的创建、轮询、审批、拒绝和继续修复逻辑。
- [ ] 使用后端 `available_actions` 控制按钮。
- [ ] 展示接口自动化专属进度、验证统计、风险提示和补充信息。
- [ ] 接入独立 Diff Dialog。

## Task 5: 接入运行详情

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-run-detail.tsx`

**Interfaces:**
- Consumes: 运行状态和现有 `loadDetail`。
- Produces: 失败脚本运行的 Drawer 入口和刷新回调。

- [ ] 增加 Drawer 开关状态。
- [ ] 将内嵌 Panel 替换为入口按钮和 Drawer 挂载。
- [ ] 保持原运行详情、JSON 报告和重跑行为不变。

## Task 6: 验证与回归

**Files:**
- Verify: `apps/frontend/tests/api-automation-ai-repair-contract.test.mjs`
- Verify: `apps/frontend/src/components/ai-testing/api-automation/`

- [ ] 运行接口自动化 AI 修复契约测试。
- [ ] 运行相关运行详情契约测试。
- [ ] 运行 Biome 对修改文件的检查。
- [ ] 运行前端构建。
- [ ] 检查 Diff，确认没有修改性能测试文件和后端文件。

