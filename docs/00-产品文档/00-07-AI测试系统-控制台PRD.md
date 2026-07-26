# 00-07 AI测试系统 - 控制台 PRD

> **基线日期**：2026-07-26
> **事实源**：`apps/frontend/src/app/(main)/dashboard/page.tsx`、`apps/backend/app/api/v1/dashboard.py`、`apps/backend/app/services/dashboard_service.py`、`apps/backend/app/schemas/dashboard.py`、`apps/backend/app/repositories/dashboard_repo.py`、`apps/frontend/src/app/(main)/dashboard/_components/asset-trend-chart.tsx`、`apps/frontend/src/lib/api-client.ts`
> **状态标签**：`已实现`

---

## 1. 这份文档解决什么问题

本文细化控制台（Dashboard）。控制台是用户进入系统后的第一工作台，用于展示测试资产健康度趋势。

权限管理见 `00-02-AI测试系统-权限管理PRD.md`。
项目管理见 `00-06-AI测试系统-项目管理PRD.md`。

---

## 2. 控制台定位

控制台是测试资产的"健康驾驶舱"，用于回答：

- 当前测试资产建设的规模如何
- 用例采纳情况是否健康
- 自动化建设进度如何
- 各项指标随时间如何演变

---

## 3. 可见范围受项目切换器约束

控制台必须受页面右上角项目切换器约束。项目切换器控制台所有指标的数据范围。

项目切换器支持两类分区：

| 分区 | 含义 | 控制台展示 |
| --- | --- | --- |
| 全部项目 | 当前用户可见项目的汇总视图 | 展示跨项目总览和汇总趋势 |
| 指定项目 | 某一个项目的健康视图 | 展示该项目的资产指标和趋势 |

---

## 4. 核心指标

当前实现 4 个指标卡：

| 指标 | 计算口径 | helper 描述 |
| --- | --- | --- |
| 项目数 | 活跃项目数量（`status = 'active'`） | `活跃项目 N 个` |
| 用例资产数 | 待评审 + 已采纳 + 不采纳测试用例总数（`test_cases` 表行数） | `已采纳 N 条` |
| 测试用例采纳率 | 已采纳用例数 / 用例资产总数 | `较上周 ±X%`（对比 8 天前数据） |
| 自动化用例数量 | 当前为占位值（`automationCases = 0`），待 UI 自动化模块接入后填充 | `用例数量 N 条` |

**当前未实现的指标**（ PRD v1 中曾列出但未实现）：

- UI 自动化覆盖率
- 发现缺陷数量
- 待处理事项数

> 说明：上述 3 项指标在后端 `dashboard_service.py` 和 `dashboard_repo.py` 中尚未计算，待相关模块接入后可逐步补充。

---

## 5. 趋势图

### 图表说明

- 组件：`AssetTrendChart`（`apps/frontend/src/app/(main)/dashboard/_components/asset-trend-chart.tsx`）
- 技术栈：Recharts（`ComposedChart`）
- 展示内容：近 N 天测试资产沉淀趋势
- 数据点字段：`date`、`caseAssets`（用例资产累计）、`adoptedCases`（已采纳累计）、`automationCases`（自动化用例累计，当前为 0）

### days 参数

| 参数 | 值 | 说明 |
| --- | --- | --- |
| 默认值 | `30` | 首次加载展示近 30 天 |
| 最小值 | `1` | API 层校验 `ge=1` |
| 最大值 | `90` | API 层校验 `le=90` |
| 前端可选值 | `7d`、`15d`、`30d` | 下拉选择器提供 3 个快捷选项 |

### 数据计算逻辑

1. 从 `test_cases` 表按项目 ID 过滤，按 `created_at` 分组统计每日新增用例数和采纳数
2. 趋势数据为累计值：起点为锚定日期往前 N 天的历史存量，后续每日累加当日增量
3. 锚定日期为 `MAX(created_at)` 和 `today` 中的较大值

---

## 6. 任务流 / 失败 / 待办说明

当前 Dashboard **未实现**以下模块：

- 待处理事项列表
- 最近任务流
- 质量风险区

上述功能待任务中心（`00-12-AI测试系统-任务中心PRD.md`）和报告中心（`00-13-AI测试系统-报告中心PRD.md`）模块完成后联动接入。

---

## 7. 隐藏的 Dashboard 模板页

以下路径存在于 `apps/frontend/src/app/(main)/dashboard/` 下，**不属于 AI 测试主业务**：

| 路径 | 说明 | 是否在导航 |
| --- | --- | --- |
| `dashboard/default/` | 英文演示模板（MetricCards、RecentCustomers） | 否 |
| `dashboard/analytics/` | 英文演示模板（TrafficSources、TopPages） | 否 |
| `dashboard/finance/` | 英文演示模板（TransactionsOverview、Wallet） | 否 |
| `dashboard/productivity/` | 英文演示模板（TasksSection、CalendarPanel） | 否 |
| `dashboard/ecommerce/` | 英文演示模板（StoreTraffic、RecentOrders） | 否 |
| `dashboard/crm/` | 英文演示模板（PipelineActivity、Opportunities） | 否 |
| `dashboard/academy/` | 英文演示模板（ClassSchedule、AssignmentStatus） | 否 |
| `dashboard/coming-soon/` | 占位页 | 否 |
| `dashboard/[...not-found]/` | 404 Not Found 处理 | 否 |

这些页面可通过 URL 直接访问，但不在系统一级导航中，属于 shadcn/ui 模板代码保留，供后续业务扩展参考。

---

## 8. 数据模型

### `dashboard_daily_stats` 表

> **注意**：当前实现中，数据直接从 `test_cases` 表实时查询，未使用 `dashboard_daily_stats` 预聚合表。以下为设计预留表结构。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | TEXT | 主键 |
| `project_id` | TEXT | 项目 ID |
| `date` | TEXT | 统计日期（ISO 格式） |
| `case_assets` | INTEGER | 当日用例资产数（累计） |
| `adopted_cases` | INTEGER | 当日已采纳用例数（累计） |
| `automation_cases` | INTEGER | 当日自动化用例数（累计） |
| `created_at` | TEXT | 创建时间 |

---

## 9. API 路由清单

| 方法 | 路径 | 响应模型 | 说明 |
| --- | --- | --- | --- |
| GET | `/dashboard/overview` | `DashboardOut` | 获取控制台概览数据 |

**Query 参数**：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `project_id` | `str` | `"all"` | 项目 ID，`"all"` 表示全部可见项目 |
| `days` | `int` | `30` | 趋势图天数，范围 `[1, 90]` |

**响应字段**：

```json
{
  "scope": "all" | "project",
  "project_id": "string | null",
  "project_name": "string | null",
  "metrics": [
    { "label": "项目数", "value": "string", "helper": "string" },
    { "label": "用例资产数", "value": "string", "helper": "string" },
    { "label": "测试用例采纳率", "value": "string", "helper": "string" },
    { "label": "自动化用例数量", "value": "string", "helper": "string" }
  ],
  "trend": [
    { "date": "YYYY-MM-DD", "caseAssets": 0, "adoptedCases": 0, "automationCases": 0 }
  ]
}
```

---

## 10. 前端页面清单

| 页面路径 | 组件 | 说明 |
| --- | --- | --- |
| `dashboard/page.tsx` | `Page` | 主控制台页面（AI 测试业务） |
| `dashboard/layout.tsx` | `AppSidebar` + 布局 | 侧边栏布局 |
| `dashboard/_components/asset-trend-chart.tsx` | `AssetTrendChart` | 趋势图组件（Recharts） |

> 模板页（`default`、`analytics`、`finance`、`productivity`、`ecommerce`、`crm`、`academy`、`coming-soon`、`[...not-found]`）不属于 AI 测试主业务，保留但不维护。

---

## 11. 验收规则

| # | 规则 | 验证方式 |
| --- | --- | --- |
| 1 | 控制台加载时调用 `GET /dashboard/overview`，默认 `project_id=all&days=30` | Network 面板检查请求 |
| 2 | 4 个指标卡正确展示：项目数、用例资产数、采纳率、自动化用例数 | 页面视觉检查 |
| 3 | 指标卡 `helper` 展示附加说明（如采纳率的"较上周"变化） | 悬停 Tooltip 或辅助文本 |
| 4 | 趋势图展示用例资产累计、已采纳累计两条曲线 | 图表验证 |
| 5 | days 选择器可切换 7d / 15d / 30d，切换后趋势图重新请求 | 点击选择器验证 |
| 6 | days 参数超过 90 时 API 返回 422 校验错误 | 手动构造请求验证 |
| 7 | 项目切换器切换到指定项目后，指标和趋势只反映该项目数据 | 切换项目验证 |
| 8 | 切换到无权访问的项目时，API 返回 404 | 切换项目验证 |
| 9 | 无任何项目时，控制台展示 4 个指标全为 0 | 空数据验证 |
| 10 | 英文模板页（`/dashboard/analytics` 等）不在导航中，但可通过 URL 直接访问 | URL 直接访问验证 |
