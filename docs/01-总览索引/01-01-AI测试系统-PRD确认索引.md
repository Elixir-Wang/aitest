# 01-01 AI测试系统 - PRD确认索引

> **事实源日期**: 2026-07-26 审计结论
> **实现基线**: `docs/` 目录下全部 PRD 文档
> **本版本以当前工作区源码（pyproject.toml / package.json / schema.py / page.tsx / sidebar-items.ts）为唯一事实源。**

---

## 更新日期

**2026-07-26**

---

## 1. PRD 文档清单

### 1.1 产品文档（00-01 ~ 00-23）

按文件编号顺序列出所有正式 PRD（`00-18`、`00-19` 不存在，非 PRD 文件）：

| 编号 | 文件名 | 当前状态 | 当前主题/说明 |
| --- | --- | --- | --- |
| 00-01 | `00-01-AI测试系统-PRD.md` | 已实现 | 总体范围、一期边界、角色、主流程 |
| 00-02 | `00-02-AI测试系统-权限管理PRD.md` | 已实现 | 管理员/测试工程师/访客权限 |
| 00-03 | `00-03-AI测试系统-需求文档分析与版本管理PRD.md` | 已实现 | 需求文档上传、转换、版本、澄清写回、模块评审 |
| 00-04 | `00-04-AI测试系统-站点探索PRD.md` | 已实现 | Playwright 站点探索、模块覆盖、障碍记录 |
| 00-05 | `00-05-AI测试系统-知识库生成与更新PRD.md` | 已实现 | llm-wiki 知识库、全局知识库 |
| 00-06 | `00-06-AI测试系统-项目管理PRD.md` | 已实现 | 项目字段、项目成员、项目设置 |
| 00-07 | `00-07-AI测试系统-控制台PRD.md` | 已实现 | 控制台指标、待办、趋势 |
| 00-08 | `00-08-AI测试系统-测试用例生成PRD.md` | 已实现 | 用例生成（AI + 手动）、评审、覆盖矩阵 |
| 00-09 | `00-09-AI测试系统-自动化测试与Allure报告PRD.md` | 已实现 | UI 自动化（pytest + Playwright）、本地执行；文件名含 Allure 但 pyproject.toml 无 Allure 依赖 |
| 00-10 | `00-10-AI测试系统-失败诊断与自愈PRD.md` | 已实现 | 接口自动化自愈（诊断 + 修复 + 验证） |
| 00-11 | `00-11-AI测试系统-模型配置与AgentRuntimePRD.md` | 已实现 | 模型 Provider、模型分配（capability 映射）、Agent Runtime（LangChain/deepagents） |
| 00-12 | `00-12-AI测试系统-任务中心PRD.md` | 已实现 | 统一任务中心（按 source_type/source_id 聚合） |
| 00-13 | `00-13-AI测试系统-报告中心PRD.md` | 已实现（空壳） | `/reports` 为静态空壳页面；真实报告分散在各项执行详情页（UI 自动化、接口自动化、性能测试） |
| 00-14 | `00-14-AI测试系统-用户配置PRD.md` | 占位 | 个人资料/密码/偏好均未实现；目前由管理员在 `/settings/users` 维护账号 |
| 00-15 | `00-15-AI测试系统-系统设置PRD.md` | 占位 | `/settings/system` 内容为"系统设置暂不开放"；文件存储/SQLite/Runner/Playwright/Allure/Agent 安全策略等全局配置未实现 |
| 00-16 | `00-16-AI测试系统-接口自动化预留PRD.md` | **已实现（文件名遗留）** | 正文内容为已实现的接口自动化（pytest + requests），非预留；旧文件名含"预留"为历史遗留 |
| 00-17 | `00-17-AI测试系统-非功能需求测试分析PRD.md` | **已实现（当前承担性能测试）** | 实际承担性能测试（Locust 脚本生成 + 运行 + SSE 流 + 智能分析），非泛化非功能测试 |
| 00-20 | `00-20-AI测试系统-测试集管理PRD.md` | 部分实现 | 明确两套边界：UI 自动化用例集（`test_case_sets`）和接口自动化场景（`api_scenarios`）；高级编排功能尚不完整 |
| 00-21 | `00-21-AI测试系统-测试计划PRD.md` | **未实现** | 面向版本/迭代/变更的测试活动编排；无对应 `page.tsx` 路由，侧栏无 `testPlans` 入口 |
| 00-22 | `00-22-AI测试系统-全局知识库PRD.md` | 已实现 | 公司/全局知识库（跨项目 Markdown 素材库，独立于项目，与 00-05 检索来源对接） |
| 00-23 | `00-23-AI测试系统-日志模块PRD.md` | 已实现 | 操作审计、配置变更、任务生命周期、日志保留 |

**说明**:
- `00-18`（不存在）和 `00-19`（不存在）不是 PRD 文件。
- `00-16` 文件名含"预留"但正文已实现；`00-17` 承担了性能测试功能。
- `00-13` 报告中心虽为"已实现"，但当前 `/reports` 为静态空壳，真实报告分散在执行详情。

### 1.2 前端方案文档

| 编号 | 文件名 | 当前状态 | 当前主题/说明 |
| --- | --- | --- | --- |
| 05-01 | `05-01-AI测试系统-前端总体方案PRD.md` | 已实现 | 补充：`app/page.tsx` 与 `app/(external)/page.tsx` 存在路由冲突（均映射根路径 `/`）；`app/page.tsx` 隐藏了 Next.js 默认 Dashboard 模板页 |
| 05-02 | `05-02-AI测试系统-导航与页面映射清单.md` | 已实现 | 接口自动化是正式入口（**非 Soon**）；模型评测（Model Evaluation）是 `comingSoon` 状态 |

### 1.3 后端与数据文档

| 编号 | 文件名 | 当前状态 | 当前主题/说明 |
| --- | --- | --- | --- |
| 03-01 | `03-01-AI测试系统-后端架构PRD.md` | 已实现 | 补充：30 个 `include_router` 注册、启动恢复序列（SQLite WAL checkpoint + Agent 恢复）、12 个 capability 映射 |
| 03-02 | `03-02-AI测试系统-数据模型PRD.md` | 已实现 | 补充：19 张接口自动化表（含 `obligation` / `self_healing` / `scenario`）、11 张性能测试表（含 `scenarios` / `gate_results`）、5 张知识库表 |

---

## 2. 统一口径（2026-07-26 最新）

| 口径 | 内容 | 依据 |
| --- | --- | --- |
| Agent 框架 | LangChain + deepagents（**非 OpenAI Agents SDK**） | `apps/backend/pyproject.toml` |
| UI 自动化 | pytest + pytest-playwright（本地执行） | `pyproject.toml`、`services/ui_automation/runner.py` |
| 接口自动化 | pytest + requests（本地执行） | `pyproject.toml`、`services/api_automation/runner.py` |
| 性能测试 | Locust（子进程 headless 运行 + SSE 流推送） | `pyproject.toml`、`services/performance_testing/` |
| 报告 | UI 自动化无 Allure 报告（无 Allure 依赖）；性能测试使用 Locust HTML 报告 | `pyproject.toml` 无 Allure |
| 前端框架 | Next.js 16 + React 19 + TypeScript + Tailwind 4 + shadcn/ui | `apps/frontend/package.json` |
| 状态管理 | Zustand | `package.json` |
| 图表 | Recharts（控制台 + 性能测试） | `package.json` |
| 流程图 | React Flow（接口自动化场景编辑器） | `package.json`、`page.tsx` |
| 数据库 | SQLite（`data/ai_testing.db`） | `apps/backend/app/core/settings.py` |
| 知识库 | llm-wiki 思路（文件系统存储产物，无向量检索） | `agents/knowledge/` |
| 全局知识库 | 独立上传管理，不复用项目需求上传接口 | `apps/backend/app/api/v1/global_knowledge.py` |
| 任务 | 各运行表（`*_runs`）管理；`task_service.py` 提供聚合视图 | `services/task_service.py` |
| 导航 | 接口自动化是正式入口（**非 Soon**）；模型评测是 `comingSoon`；无"测试计划"一级导航 | `sidebar-items.ts` |
| 00-13 报告中心 | `/reports` 为静态空壳；真实报告分散在执行详情页 | `apps/frontend/src/app/(main)/reports/page.tsx` |
| 00-14 用户配置 | 占位；个人资料/密码/偏好均未实现 | `/settings/profile`、`/settings/password`、`/settings/preferences` 不存在 |
| 00-15 系统设置 | 占位；`/settings/system` 内容为"系统设置暂不开放" | `apps/frontend/src/app/(main)/settings/system/page.tsx` |
| 00-16 接口自动化 | 已实现（文件名"预留"为历史遗留） | `apps/backend/app/api/v1/api_automation.py`、`apps/frontend/src/app/(main)/automation/api/page.tsx` |
| 00-17 性能测试 | 当前承担性能测试（Locust） | `apps/backend/app/api/v1/performance_tests.py`、`apps/frontend/src/app/(main)/performance-tests/` |
| 00-20 测试集管理 | 部分实现（两套边界：`test_case_sets` vs `api_scenarios`） | `apps/backend/app/seed/schema.py` |
| 00-21 测试计划 | 未实现（无测试计划 `page.tsx` 路由） | 全库无 `test-plans` 路由，侧栏无 `testPlans` 入口 |
| 前端路由冲突 | `app/page.tsx` 与 `app/(external)/page.tsx` 均映射 `/` | `apps/frontend/src/app/page.tsx` vs `apps/frontend/src/app/(external)/page.tsx` |
| 后端 Router 注册 | 30 个 `include_router` | `apps/backend/app/api/v1/__init__.py` |
| 后端启动恢复 | SQLite WAL checkpoint + Agent 恢复序列 | `apps/backend/app/main.py` |
| 12 个 capability | 能力映射到模型分配 | `apps/backend/app/core/settings.py` |
| 接口自动化表 | 19 张（含 obligation/self_healing/scenario） | `apps/backend/app/seed/schema.py` |
| 性能测试表 | 11 张（含 scenarios/gate_results） | `apps/backend/app/seed/schema.py` |
| 知识库表 | 5 张 | `apps/backend/app/seed/schema.py` |

---

## 3. 已实现 PRD 索引

### 3.1 按状态统计

| 状态 | 数量 | 编号 |
| --- | --- | --- |
| **已实现** | 17 | 00-01~00-12、00-22~00-23、05-01~05-02、03-01~03-02 |
| **占位** | 2 | 00-14（用户配置）、00-15（系统设置） |
| **已实现（文件名遗留）** | 2 | 00-16（接口自动化）、00-17（性能测试） |
| **已实现（空壳）** | 1 | 00-13（报告中心 `/reports` 为空壳） |
| **部分实现** | 1 | 00-20（测试集管理：`test_case_sets` + `api_scenarios` 边界明确） |
| **未实现** | 1 | 00-21（测试计划：无路由无侧栏入口） |
| **合计** | **24** | 20 产品 + 2 前端 + 2 后端 |

### 3.2 已实现明细

- **00-01 ~ 00-12**：项目管理、权限、需求分析、站点探索、知识库、控制台、用例生成、自动化测试（UI）、失败诊断、模型配置、任务中心
- **00-13**：报告中心（已实现但 `/reports` 为空壳，真实报告分散在执行详情）
- **00-16**：接口自动化（已实现，文件名"预留"为遗留）
- **00-17**：性能测试（已实现，文件名为"非功能需求测试分析"遗留）
- **00-22**：全局知识库
- **00-23**：日志模块
- **05-01**：前端总体方案（已更新路由冲突说明）
- **05-02**：导航与页面映射（接口自动化非 Soon，模型评测是 comingSoon）
- **03-01**：后端架构（30 个 include_router、启动恢复、12 capability）
- **03-02**：数据模型（19+11+5 张表）

---

## 4. 验收/核对规则

| 规则 | 核对依据路径 |
| --- | --- |
| 00-13 报告中心为空壳 | `apps/frontend/src/app/(main)/reports/page.tsx` 内容为静态空壳 |
| 00-14 用户配置为占位 | `/settings/profile`、`/settings/password`、`/settings/preferences` 无对应路由 |
| 00-15 系统设置为占位 | `apps/frontend/src/app/(main)/settings/system/page.tsx` 内容为"系统设置暂不开放" |
| 00-16 标注为已实现（非预留） | `apps/backend/app/api/v1/api_automation.py` + `apps/frontend/src/app/(main)/automation/api/page.tsx` |
| 00-17 标注为当前承担性能测试 | `apps/backend/app/api/v1/performance_tests.py`、`apps/frontend/src/app/(main)/performance-tests/` |
| 00-20 标注为部分实现 | `apps/backend/app/seed/schema.py` 中 `test_case_sets` 和 `api_scenarios` 表存在 |
| 00-21 标注为未实现 | 全库无 `test-plans` 路由，侧栏无 `testPlans` 入口 |
| 接口自动化为正式入口（非 Soon） | `sidebar-items.ts` 中接口自动化无 `comingSoon: true` |
| 模型评测为 comingSoon | `sidebar-items.ts` 中模型评测有 `comingSoon: true` |
| 前端路由冲突 | `apps/frontend/src/app/page.tsx` 与 `apps/frontend/src/app/(external)/page.tsx` 均映射 `/` |
| 技术栈口径统一 | `apps/backend/pyproject.toml`、`apps/frontend/package.json` |
| 30 个 include_router | `apps/backend/app/api/v1/__init__.py` |
| 19 张接口自动化表 | `apps/backend/app/seed/schema.py`（含 obligation/self_healing/scenario 相关表） |
| 11 张性能测试表 | `apps/backend/app/seed/schema.py`（含 scenarios/gate_results 相关表） |
| 5 张知识库表 | `apps/backend/app/seed/schema.py` |
| 12 个 capability | `apps/backend/app/core/settings.py` |
| 启动恢复序列 | `apps/backend/app/main.py`（SQLite WAL checkpoint + Agent 恢复） |

---

## 5. 关键修订条目（与 2026-07-26 审计结论一致）

1. **00-13 报告中心**：新增标注"已实现（空壳）"，说明 `/reports` 为静态空壳，真实报告分散在执行详情。
2. **00-14 用户配置**：明确为占位状态（个人资料/密码/偏好未实现）。
3. **00-15 系统设置**：明确为占位状态（`/settings/system` 内容为"系统设置暂不开放"）。
4. **00-16 接口自动化**：已实现（文件名"预留"遗留），维持原标注。
5. **00-17 性能测试**：已实现（文件名"非功能需求测试分析"遗留，实际承担性能测试），维持原标注。
6. **00-20 测试集管理**：调整为"部分实现"，明确两套边界（UI 自动化 `test_case_sets` + 接口自动化 `api_scenarios`）。
7. **00-21 测试计划**：调整为"未实现"（无对应 `page.tsx` 路由，侧栏无 `testPlans` 入口）。
8. **05-01 前端总体方案**：新增路由冲突说明（`app/page.tsx` vs `app/(external)/page.tsx`）。
9. **05-02 导航与页面映射**：明确接口自动化非 Soon，模型评测是 comingSoon。
10. **03-01 后端架构**：新增 30 个 `include_router`、启动恢复序列、12 个 capability。
11. **03-02 数据模型**：新增 19 张接口自动化表、11 张性能测试表、5 张知识库表。
12. **更新日期**：从 2026-07-25 更新至 2026-07-26。
