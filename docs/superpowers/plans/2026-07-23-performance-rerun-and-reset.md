# Performance Rerun And Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复终止态统计重置按钮，并增加复用原配置的一键重新压测操作。

**Architecture:** 保持后端现有创建、启动、重置接口不变。前端控制台对齐状态规则，并串联创建运行、启动运行和路由跳转。

**Tech Stack:** Next.js、React、TypeScript、Node.js contract tests

## Global Constraints

- 不修改现有后端接口。
- 不覆盖或删除原运行数据。
- 复用当前运行的脚本与负载配置。

---

### Task 1: 运行控制按钮契约

**Files:**
- Modify: `apps/frontend/tests/performance-run-detail-contract.test.mjs`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/locust-console.tsx`

**Interfaces:**
- Consumes: `createPerformanceRun`、`startPerformanceRun`、`resetPerformanceRunStats`
- Produces: 终止态可用的统计重置与重新压测操作

- [ ] **Step 1: Write the failing contract test**
- [ ] **Step 2: Run the contract test and verify failure**
- [ ] **Step 3: Implement reset state alignment**
- [ ] **Step 4: Implement create-start-navigate rerun flow**
- [ ] **Step 5: Run contract test, lint, and type/build validation**
