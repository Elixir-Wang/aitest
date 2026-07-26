# 00-13 AI测试系统 - 报告中心 PRD

## 0. 基线与事实源

- 基线日期：**2026-07-26**
- 事实源：当前工作区源码。
- 状态标签：【已实现】报告中心后端模块（API + 仓储 + 服务 + Schema）；【部分接入】报告中心前端页面（仅"性能"Tab 接入）；【未接入】报告中心前端页面（"接口" / "UI" Tab 为空态）。
- 关键结论提前说明：
  - `/reports` 页面**不再是纯静态空壳**：前端已接入 `listReportCenterItems()` API，仅"性能"Tab 调用后端并渲染 `performance_analysis_sessions` 数据；"接口" / "UI" Tab 保持空态。
  - 后端报告中心模块（`/api/v1/reports.py` + `report_center_repo.py` + `report_center_service.py` + `schemas/report_center.py`）已完整落地，支持 `performance` 类型报告查询。
  - 跨模块的"失败聚合 / 内部缺陷记录 / Allure 报告聚合 / 报告中心第三方系统对接" **均未实现**。
  - 真实报告分散在各执行详情页（探索 Mermaid 报告、接口 JSON 报告、UI 自动化日志/截图/视频/Trace、Locust HTML/CSV、性能 AI 分析报告）。

---

## 1. 适用范围与边界

### 1.1 本 PRD 覆盖

- `/reports` 页面：前端当前接入状态（性能 Tab 接入、接口/UI Tab 空态）、后端 API 与数据模型。
- 模块内已实现的报告/产物：
  - 站点探索：`exploration/[runId]/page.tsx` 渲染 Mermaid 探索报告（`ExplorationReport`）。
  - 接口自动化：运行详情页 `automation/api/runs/[runId]/page.tsx` 提供 pytest JSON 报告（`/api-runs/{id}/report`）。
  - UI 自动化：执行详情页 `automation/ui/assets/[assetId]/runs/[runId]/page.tsx` 提供 trace / video / screenshot 下载。
  - 性能测试：`locust-console.tsx` 提供 Locust HTML/CSV 下载；`performance-analysis-report.tsx` 渲染 AI 分析报告。

### 1.2 本 PRD 不覆盖

- 接口/性能/UI 自动化本身的运行/执行/分析（按 00-09 / 00-10 / 00-16 / 00-17 描述）。
- Allure 报告聚合（不存在）。
- 内部缺陷记录与外部缺陷系统对接（不存在）。
- 跨模块失败聚合服务（不存在）。
- 报告中心订阅、导出 PDF/XMind、定制仪表盘（不存在）。
- 报告中心后端尚未支持 `api` / `ui` 报告类型（`SUPPORTED_REPORT_TYPES = {"performance"}`）。

---

## 2. 入口与路由

- 前端一级入口：`/reports`（`apps/frontend/src/app/(main)/reports/page.tsx`）。
- 报告中心后端 API：
  - `GET /api/v1/reports`（`app/api/v1/reports.py`）— 性能 AI 分析报告聚合接口，支持 `report_type`（当前仅 `performance`）与 `project_id`（`all` 或具体 ID）参数。
- 其他模块报告按模块自身 URL 暴露（见 00-09 / 00-16 / 00-17）。

---

## 3. 真实报告分布

> 以下四个域的报告均**不在** `/reports` 页面聚合，而是分散在各执行详情页中。

### 3.1 站点探索报告

| 属性 | 值 |
|---|---|
| 触发条件 | 探索 run 执行完成 |
| 路由 | `/projects/[projectId]/exploration/[runId]` |
| 前端文件 | `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx` |
| 产物类型 | Mermaid 站点地图（Markdown 渲染为 SVG） |
| 用户操作 | 在运行详情页顶部查看 Mermaid 图；可截图或嵌入文档 |

### 3.2 接口自动化报告

| 属性 | 值 |
|---|---|
| 触发条件 | 接口运行完成（含场景级执行） |
| 路由 | `/projects/[projectId]/automation/api/runs/[runId]` |
| 前端文件 | `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/runs/[runId]/page.tsx`（`ApiRunDetail` 组件） |
| 产物类型 | pytest JSON 报告（`/api-runs/{id}/report`）、场景级结果（`/api-runs/{id}/scenario-result`）、修复 attempt 报告（`/api-repair-attempts/{id}/report`） |
| 用户操作 | 在运行详情页点击"报告"标签页；修复 attempt 详情页可打开 diff 对比 |

### 3.3 UI 自动化报告

| 属性 | 值 |
|---|---|
| 触发条件 | UI 执行 run 完成 |
| 路由 | `/projects/[projectId]/automation/ui/assets/[assetId]/runs/[runId]` |
| 前端文件 | `apps/frontend/src/app/(main)/projects/[projectId]/automation/ui/assets/[assetId]/runs/[runId]/page.tsx`（`UiAutomationRunDetail` 组件） |
| 产物类型 | trace（Playwright trace viewer）、视频（`.mp4`）、截图（`.png`）、运行日志（stdout/stderr） |
| 用户操作 | 在执行详情页切换 Trace / 视频 / 截图 Tab；点击下载按钮获取原始文件 |

### 3.4 性能测试报告

#### 3.4.1 Locust 运行产物

| 属性 | 值 |
|---|---|
| 触发条件 | Locust 压测 run 完成 |
| 入口组件 | `apps/frontend/src/components/ai-testing/performance-testing/locust-console.tsx` |
| 产物类型 | HTML 报告（`result.html`）、CSV 统计（`result_stats.csv`）、失败/异常 CSV |
| 用户操作 | 运行详情页点击"报告"列表 → "下载"按钮，调用 `GET /performance-test-runs/{id}/reports` 列出产物后下载 |

#### 3.4.2 性能 AI 分析报告（已接入报告中心）

| 属性 | 值 |
|---|---|
| 触发条件 | 性能 run 执行完成 → 用户发起 AI 分析 |
| 路由 | `/projects/[projectId]/performance-tests/[testId]/runs/[runId]/analysis/[analysisId]` |
| 前端文件 | `apps/frontend/src/components/ai-testing/performance-testing/performance-analysis-report.tsx` |
| 产物类型 | AI 生成的结构化分析报告（含 findings、recommendations、metric_snapshot、report_snapshot） |
| 用户操作 | 性能 run 详情页 AI 分析 Drawer；也可从 `/reports` 的"性能" Tab 点击"查看报告"跳转 |
| 报告中心接入 | ✅ 通过 `GET /api/v1/reports?report_type=performance` 聚合，展示在报告中心列表 |

---

## 4. 报告中心后端模型

### 4.1 API 路由

**文件**：`apps/backend/app/api/v1/reports.py`

```
GET /api/v1/reports
  Query Parameters:
    report_type: str = "performance"  # 当前仅支持 performance
    project_id:  str = "all"          # "all" 或具体项目 ID
  Response: ReportCenterItemOut[]
  认证：current_user（JWT Bearer）
```

### 4.2 请求/响应模型

**文件**：`apps/backend/app/schemas/report_center.py`

```python
class ReportCenterItemOut(BaseModel):
    id: str                               # performance_analysis_sessions.id
    report_type: Literal["performance"]   # 固定为 "performance"
    project_id: str
    project_name: str
    test_id: str
    test_name: str
    run_id: str
    analysis_id: str                     # 与 id 相同
    analysis_version: int
    name: str                             # "{test_name} - 性能智能分析报告"
    status: Literal["collecting", "analyzing", "completed", "failed"]
    verdict: Literal["pass", "conditional_pass", "fail", "indeterminate"]
    quality_status: Literal["complete", "partial", "invalid"]
    error_message: str
    created_at: str
    updated_at: str
    href: str                             # 跳转路径
```

### 4.3 数据仓储

**文件**：`apps/backend/app/repositories/report_center_repo.py`

- `list_performance_reports(db, project_ids: list[str]) -> list[Row]`
  - 查询 `performance_analysis_sessions` 表，JOIN `performance_test_runs`、`performance_tests`、`projects`。
  - 按 `updated_at DESC, created_at DESC` 排序。
  - 仅返回指定 project_ids 范围内的记录。

### 4.4 业务服务

**文件**：`apps/backend/app/services/report_center_service.py`

- `SUPPORTED_REPORT_TYPES = {"performance"}`
- `list_reports(report_type, project_id, actor) -> list[dict]`
  - 校验 `report_type` 是否在 `SUPPORTED_REPORT_TYPES` 中（否则返回 400）。
  - 调用 `project_repo.list_visible(db, actor)` 鉴权可见项目。
  - 调用 `report_center_repo.list_performance_reports()` 查询数据。
  - `_serialize_performance_report(row)` 负责字段映射：从 `report_snapshot_json` / `metric_snapshot_json` 提取 verdict / quality_status；构造 `href` 为 `/projects/{project_id}/performance-tests/{test_id}/runs/{run_id}/analysis/{analysis_id}`。
  - `_analysis_status(legacy_status, stored_status)` 兼容旧 `status` 与新 `analysis_status` 字段。

### 4.5 数据表依赖

> 无新增表。后端直接查询现有表：

- `performance_analysis_sessions`：存储 AI 分析会话（含 `report_snapshot_json`、`metric_snapshot_json`、`analysis_status`）。
- `performance_test_runs`：压测运行记录。
- `performance_tests`：压测任务。
- `projects`：项目表（用于联表获取 `project_name`）。

---

## 5. 前端空壳复核规则

**文件**：`apps/frontend/src/app/(main)/reports/page.tsx`

以下源码行号作为可验证证据：

| 行号范围 | 描述 | 验证要点 |
|---|---|---|
| `15` | `REPORT_TABS = ["接口", "性能", "UI"]` | 三个 Tab 常量，与设计一致 |
| `18` | `useState<ReportCenterItem[]>([])` | 初始状态为空数组 |
| `23–45` | `useEffect` — 条件触发 `listReportCenterItems` | 仅在 `activeTab === "性能"` 时调用 API；其他 Tab 直接 `setLoading(false)` |
| `47–60` | `filteredRows` 计算逻辑 | 非"性能" Tab 时 `return []`，确保接口/UI Tab 搜索结果为空 |
| `93` | 加载骨架屏条件 | `loading && activeTab === "性能"` 才渲染骨架行 |
| `141–148` | 空态文案 | "暂无性能报告……"（性能 Tab）或"`${activeTab}报告尚未接入。`"（接口/UI Tab） |

**前端接入状态总结**：

- "性能" Tab：`listReportCenterItems()` → `GET /api/v1/reports?report_type=performance` → 渲染 `ReportCenterItem[]`，支持搜索、"查看报告"跳转。
- "接口" / "UI" Tab：直接返回空态，`REPORT_TABS` 中的两个 Tab **不调用任何 API**。

---

## 6. 真实用户流程

### 6.1 报告中心 - 性能 Tab（已接入）

1. 访问 `/reports`，默认激活"性能" Tab。
2. 前端调用 `GET /api/v1/reports?report_type=performance&project_id=all`。
3. 后端鉴权可见项目，查询 `performance_analysis_sessions`，返回 `ReportCenterItem[]`。
4. 列表渲染每条报告：项目名、报告名称（"{测试名} - 性能智能分析报告"）、结论、数据质量、生成状态、更新时间。
5. 用户可搜索（按项目名/测试名/报告名/结论/状态过滤），可点击"查看报告"跳转到 `/projects/{projectId}/performance-tests/{testId}/runs/{runId}/analysis/{analysisId}`。
6. 在性能运行详情页重新触发 AI 分析后，报告中心自动出现新记录（按 `updated_at` 排序靠前）。

### 6.2 报告中心 - 接口 / UI Tab（未接入）

1. 切换到"接口"或"UI" Tab，`useEffect` 检测 `activeTab !== "性能"`，直接 `setLoading(false)` 并清空 `reports`。
2. 列表渲染空态文案："`{activeTab}报告尚未接入。`"。
3. 搜索无数据。
4. 不调用任何 API。

### 6.3 各模块报告流程（已实现）

- **探索报告**：运行详情页 `/projects/{projectId}/exploration/{runId}` 顶部渲染 Mermaid 站点地图，可截图引用。
- **接口自动化报告**：运行详情页提供 pytest JSON 报告下载；场景执行提供 `scenario-result` JSON；修复 attempt 提供 `report` + diff 对比。
- **UI 自动化报告**：执行详情页 Trace 标签（Playwright trace viewer）、视频标签、截图标签、日志标签；均支持下载原始文件。
- **性能 Locust 报告**：运行详情页报告列表 → 下载 HTML/CSV。
- **性能 AI 分析报告**：运行详情页 AI 分析 Drawer；也通过报告中心聚合。

---

## 7. 功能需求

### 7.1 报告中心列表（后端已实现，前端部分接入）

| 功能 | 状态 | 说明 |
|---|---|---|
| 性能 AI 分析报告查询 | 【已实现】 | `GET /api/v1/reports?report_type=performance` |
| 项目范围过滤 | 【已实现】 | `project_id=all` 或具体 ID，鉴权可见项目 |
| 报告搜索（前端） | 【已实现】 | 性能 Tab 支持按项目名/测试名/报告名/结论/状态搜索 |
| 接口报告查询 | 【未实现】 | 后端 `SUPPORTED_REPORT_TYPES` 不含 `api` |
| UI 报告查询 | 【未实现】 | 后端 `SUPPORTED_REPORT_TYPES` 不含 `ui` |
| 报告导出（PDF/ZIP） | 【未实现】 | 无相关路由 |
| "新建报告"按钮 | 【空态】 | 前端无绑定动作 |

### 7.2 失败聚合 / 内部缺陷（未实现）

- 不存在 `internal_bug_records` 表 / 路由 / 服务。
- 没有跨模块失败聚合接口。
- 没有对接外部缺陷系统。

---

## 8. API 路由清单（V1）

| 方法 | 路径 | 说明 | 状态 |
|---|---|---|---|
| GET | `/reports` | 报告中心聚合（当前仅性能 AI 分析报告） | 已实现 |
| GET | `/dashboard/overview` | 控制台概览（跨项目指标卡+趋势图） | 已实现 |

> 接口/性能/UI 模块的报告 API 详见对应 PRD（00-09 / 00-16 / 00-17）与失败诊断 PRD（00-10）。

---

## 9. 状态与数据

### 9.1 已实现

- `performance_analysis_sessions` 表被 `report_center_repo.list_performance_reports` 查询，用于报告中心聚合。
- 报告中心 `href` 指向性能运行详情页 AI 分析 Tab：`/projects/{projectId}/performance-tests/{testId}/runs/{runId}/analysis/{analysisId}`。
- `analysis_status` 字段（`collecting/analyzing/completed/failed`）与旧 `legacy_status` 字段并存，服务端 `_analysis_status()` 兼容处理。
- `verdict` 从 `report_snapshot_json.verdict` 或 `metric_snapshot_json.verdict` 回退到 `"indeterminate"`。
- `quality_status` 从 `metric_snapshot_json.quality.status` 提取，缺失时默认为 `"invalid"`。

### 9.2 占位 / 未实现

- `automationCases`（控制台指标卡）当前始终为 0（占位）。
- 接口/UI Tab 完全不调用 API（直接空态）。
- `internal_bug_records` 表与相关路由缺失。
- 后端 `SUPPORTED_REPORT_TYPES` 仅含 `"performance"`。

---

## 10. 失败与限制

- `/reports` 页面"接口"/"UI" Tab 展示的永远是空态；不应被理解为"已上线但暂无数据"，而是明确未接入。
- 报告中心仅聚合**性能 AI 分析报告**；Locust HTML/CSV、接口 JSON、UI trace/video 不在聚合范围内。
- 跨模块失败聚合尚未实现，涉及安全/合规要求前需先建立数据模型。
- 性能/接口/UI 运行报告只能通过各自模块的运行详情页访问；报告中心不会拉取它们（Locust/接口 JSON/UI 产物）。

---

## 11. 未来规划

将真实报告逐步接入独立报告中心的能力图：

```
报告中心（目标态）
├── 性能 AI 分析报告    ✅ 已接入（/reports "性能" Tab）
├── Locust 运行产物     🔲 待接入（HTML/CSV 下载 → 聚合列表 + 预览）
├── 接口 JSON 报告      🔲 待接入（pytest report → 聚合 + 详情跳转）
├── UI trace/video/截图  🔲 待接入（asset run → 聚合 + 在线预览）
├── 探索 Mermaid 报告   🔲 待接入（站点地图 → 缩略图聚合）
├── 失败聚合视图         🔲 规划中（跨模块失败 → internal_bug_records）
└── 导出/订阅           🔲 规划中（PDF/ZIP/XMind）
```

---

## 12. 验收标准

- **报告中心-性能 Tab**：
  - 访问 `/reports`，默认激活"性能" Tab，立即调用 `GET /api/v1/reports?report_type=performance&project_id=all`。
  - 返回数据时，列表渲染每行：项目名、报告名称（"{测试名} - 性能智能分析报告"）、结论徽章、数据质量徽章、生成状态（处理中显示 ProcessingState）、更新时间、"查看报告"操作。
  - 搜索"通过"可过滤到 `verdict === "pass"` 的记录；搜索项目名可精确过滤。
  - 点击"查看报告"跳转到 `/projects/{projectId}/performance-tests/{testId}/runs/{runId}/analysis/{analysisId}`。
- **报告中心-接口/UI Tab**：
  - 切换到"接口" Tab，立即显示空态文案："`接口报告尚未接入。`"，**不调用任何 API**。
  - 切换到"UI" Tab，同上。
- **后端 API 校验**：
  - `GET /api/v1/reports?report_type=api` 返回 `400 REPORT_TYPE_INVALID`。
  - `GET /api/v1/reports?project_id=xxx`（非法项目）返回 `404 PROJECT_NOT_FOUND`。
  - 未认证请求返回 `401 AUTH_REQUIRED`。
- **控制台指标**：`/dashboard` 4 张指标卡渲染来自 `dashboard/overview` 的 `metrics` 数组，与报告中心无关（独立验收项）。
- **真实性约束**：报告中心明确以"部分接入"身份标注，**不能伪造接口/UI 报告聚合数据**。Locust/接口 JSON/UI trace 报告**不**应被列为"只能通过报告中心访问"。

---

## 13. 实现依据

- 前端报告中心（部分接入）：`apps/frontend/src/app/(main)/reports/page.tsx`（行 15, 18, 23–45, 47–60, 93, 141–148）。
- 前端 API 客户端：`apps/frontend/src/lib/api-client.ts`（`ReportCenterItem` 类型，行 1341–1359；`listReportCenterItems` 函数，行 1745–1748）。
- 后端 API 路由：`apps/backend/app/api/v1/reports.py`。
- 后端仓储：`apps/backend/app/repositories/report_center_repo.py`。
- 后端服务：`apps/backend/app/services/report_center_service.py`。
- 后端 Schema：`apps/backend/app/schemas/report_center.py`。
- 性能 Locust 报告入口：`apps/frontend/src/components/ai-testing/performance-testing/locust-console.tsx`。
- 性能 AI 分析报告：`apps/frontend/src/components/ai-testing/performance-testing/performance-analysis-report.tsx`。
- 探索报告：`apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`。
- 接口运行报告：`apps/frontend/src/app/(main)/projects/[projectId]/automation/api/runs/[runId]/page.tsx`。
- UI 自动化报告：`apps/frontend/src/app/(main)/projects/[projectId]/automation/ui/assets/[assetId]/runs/[runId]/page.tsx`。
- 前端控制台：`apps/frontend/src/app/(main)/dashboard/page.tsx`（独立验收项）。
- 后端控制台：`apps/backend/app/api/v1/dashboard.py`（独立验收项）。
