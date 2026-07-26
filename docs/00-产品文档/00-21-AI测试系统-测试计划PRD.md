# 00-21 AI测试系统 - 测试计划 PRD

## 0. 基线与事实源

- **基线日期：2026-07-26**
- **事实源：当前工作区源码（`apps/backend/app/`、`apps/frontend/src/`）**
- **状态标签：【未实现】**

---

## 1. 范围与目标

### 1.1 适用范围

本文档定义 AI 测试系统中"测试计划（Test Plan）"模块的产品需求。该模块用于在项目维度组织测试活动，围绕以下维度组织测试范围：

| 维度 | 说明 |
|------|------|
| 版本 / 迭代 | 关联至特定版本号或迭代周期 |
| 变更 / 变更范围 | 关联需求变更或缺陷修复 |
| 回归范围 | 关联需回归验证的用例集 |
| 上线前验证 | 预发布门禁检查清单 |
| 负责人 | 指定测试计划 Owner |
| 环境 | 关联测试执行环境 |
| 执行批次 | 支持分批执行与进度追踪 |
| 计划结论 | 记录测试通过 / 阻塞 / 上线风险结论 |

### 1.2 本模块目标

- 为项目提供跨模块测试活动的统一编排视图；
- 支持将测试集、接口场景、性能场景等资产打包为可执行的测试计划；
- 追踪测试计划执行进度，汇总报告结论。

### 1.3 本模块边界

- 测试集管理由 00-20（测试集管理）覆盖；
- 接口场景编排由 00-16（接口自动化）覆盖；
- 性能场景编排由 00-17（性能场景）覆盖；
- 报告汇总由 00-13（报告中心）覆盖。

---

## 2. 当前实现状态

### 2.1 状态结论

**测试计划模块当前未实现。**

### 2.2 路由核查

| 核查项 | 核对依据 | 结果 |
|--------|----------|------|
| `test-plans` 前端路由 | `grep -rn "test-plans" apps/frontend/src/` | **无** |
| 侧边栏入口 | `grep -rn "testPlans" apps/frontend/src/navigation/sidebar/sidebar-items.ts` | **无** |
| `test_plans` 数据库表 | `grep -rn "test_plans" apps/backend/app/seed/schema.py` | **无** |
| 后端 API 路由 | `grep -rn "test.plans\|test_plans" apps/backend/app/api/` | **无** |
| `TestPlan` 数据结构 | `grep -rn "class TestPlan\|TestPlanSchema" apps/backend/app/schemas/` | **无** |

### 2.3 已实现替代能力

| 替代模块 | 文档 | 说明 |
|----------|------|------|
| 测试集 | 00-20 | 手工 / AI 用例集合 |
| 接口场景 | 00-16 | 步骤化 API 编排 |
| 性能场景 | 00-17 | 多阶段负载曲线 |
| 报告中心 | 00-13 | 性能报告汇总（占位） |

### 2.4 已知无关字符串

以下文件含 `test_plan` 字符串，但与"测试计划"模块无关：

- `apps/backend/app/services/page_exploration/report_writer.py` — PageExploration 报告内部字符串
- `apps/backend/app/agents/ui_automation/pytest_playwright/renderer.py` — UI 自动化渲染字符串

---

## 3. 设计意向（未来实现参考）

> 以下为测试计划模块的设计意向，作为后续实施参考。当前无代码实现。

### 3.1 核心能力

| 能力 | 说明 |
|------|------|
| 计划创建 | 指定名称、版本、迭代、起止时间、Owner、环境 |
| 资产关联 | 关联测试集（测试用例）、接口场景、性能场景 |
| 批次编排 | 支持将资产分组为多个执行批次 |
| 执行触发 | 按批次或整体触发跨模块执行 |
| 进度追踪 | 实时汇总各批次执行状态 |
| 结论记录 | 支持记录"通过 / 阻塞 / 风险"结论与备注 |

### 3.2 建议数据模型落点

```
test_plans
  - id, project_id, name, version, iteration
  - owner_id, environment, start_date, end_date
  - status (draft / running / completed / blocked)
  - conclusion (pass / fail / risk) nullable
  - notes, created_at, updated_at

test_plan_batches
  - id, plan_id, name, order
  - environment override nullable

test_plan_items
  - id, plan_id, batch_id
  - item_type (test_case_set | api_scenario | performance_scenario)
  - item_id
```

### 3.3 建议前端入口与侧边栏位置

- **路由**：`/projects/{projectId}/test-plans`（未来实现）
- **侧边栏位置**：建议置于"报告中心"之后，与"测试集"同级或作为其上层聚合入口
- **详情页**：`/projects/{projectId}/test-plans/{planId}`

---

## 4. API 设计意向（V1）

> 以下为建议 API 结构，待实现后补充正式 OpenAPI 规范。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/projects/{project_id}/test-plans` | 列表 |
| POST | `/projects/{project_id}/test-plans` | 创建 |
| GET | `/projects/{project_id}/test-plans/{id}` | 详情 |
| PUT | `/projects/{project_id}/test-plans/{id}` | 更新 |
| DELETE | `/projects/{project_id}/test-plans/{id}` | 删除 |
| POST | `/projects/{project_id}/test-plans/{id}/execute` | 触发执行 |
| GET | `/projects/{project_id}/test-plans/{id}/progress` | 执行进度 |

---

## 5. 验收规则

> 以下为测试计划模块的验收规则。核对依据路径均为"无"，即当前实现不满足任意一项。

| 验收项 | 核对依据 | 状态 |
|--------|----------|------|
| 存在 `test_plans` 表 | `grep -rn "test_plans" apps/backend/app/seed/schema.py` | **无** |
| 存在 `/test-plans` 路由 | `grep -rn "test-plans" apps/frontend/src/` | **无** |
| 存在侧边栏入口 | `grep -rn "testPlans" apps/frontend/src/navigation/sidebar/sidebar-items.ts` | **无** |
| 存在后端 API | `grep -rn "test.plans\|test_plans" apps/backend/app/api/` | **无** |
| 存在前端页面 | `glob apps/frontend/src/**/test-plans/**` | **无** |
| 存在 `TestPlan` 数据结构 | `grep -rn "class TestPlan\|TestPlanSchema" apps/backend/app/schemas/` | **无** |

**结论**：当前工作区不满足任何验收项，测试计划模块为纯占位设计，待后续迭代实现。

---

## 6. 未来规划

测试计划模块计划作为后续可实施模块，建议分阶段实现：

| 阶段 | 内容 |
|------|------|
| P0 | 数据模型（`test_plans`、`test_plan_batches`、`test_plan_items`）、基础 CRUD API |
| P1 | 前端列表页、详情页、侧边栏入口 |
| P2 | 与测试集、接口场景、性能场景的关联与执行触发 |
| P3 | 执行进度追踪、报告结论汇总 |
| P4 | 与 00-13 报告中心的深度集成 |

---
