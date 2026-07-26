# 00-20 AI测试系统 - 测试集管理 PRD

## 0. 基线与事实源

- **基线日期：2026-07-26**
- **事实源：**
  - 数据库 schema：`apps/backend/app/seed/schema.py`
  - 后端 API：`apps/backend/app/api/v1/ui_automation.py`、`apps/backend/app/api/v1/api_automation.py`
  - 前端页面：`apps/frontend/src/app/(main)/test-cases/page.tsx`、`apps/frontend/src/app/(main)/automation/ui/page.tsx`、`apps/frontend/src/app/(main)/automation/api/page.tsx`、`apps/frontend/src/app/(main)/projects/[projectId]/automation/api/scenarios/[scenarioId]/page.tsx`
  - API 客户端类型：`apps/frontend/src/lib/api-client.ts`
- **状态标签：**【已实现】/【未实现】/【占位说明】

---

## 1. 范围与目标

### 1.1 "测试集"的真实含义

本 PRD 中的"测试集"是**两套独立的子模型**，分别服务于 UI 自动化和接口自动化两条不同链路，**不可混淆**：

| 子模型 | 数据库表 | 功能定位 | 前端入口 |
| --- | --- | --- | --- |
| **UI 自动化用例集** | `test_case_sets` | 按需求生成手工用例、评审、导出 XMind | `/test-cases` |
| **接口自动化用例集** | `api_test_case_sets` | 接口用例分类聚合（当前仅名称/备注层） | `/automation/api` |
| **接口自动化场景** | `api_scenarios` | 端点顺序编排、变量提取、断言、AI 计划生成、版本管理、执行 | `/projects/{projectId}/automation/api/scenarios/{scenarioId}` |

> **注意：** `test_case_sets` 表名容易产生误解——其实为"需求驱动的测试用例集（评审流水线）"，而非 UI 自动化批处理集合。真正的 UI 自动化执行单元是 `ui_automation_assets`（资产）。

### 1.2 本 PRD 覆盖

- `test_case_sets`（UI 自动化用例集）的数据模型、状态、列表、详情、重新生成接口；
- `api_test_case_sets`（接口自动化用例集）的 CRUD；
- `api_scenarios` + `api_scenario_steps` + `api_scenario_revisions` + `api_scenario_ai_plans`（接口自动化场景编排）的完整生命周期；
- UI 自动化资产（`ui_automation_assets`）与生成运行（`ui_automation_generation_runs`）、执行运行（`ui_automation_execution_runs`）的关系。

### 1.3 本 PRD 不覆盖

- 测试用例本身的产生 / 评审 / 驳回知识检索（00-08）；
- 接口自动化脚本生成 / 自愈（00-10 / 00-16）；
- UI 自动化自愈（00-09，未实现）；
- 测试计划（00-21，未实现）。

---

## 2. 入口与路由

### 2.1 前端入口

| 资源 | 路由 | 说明 |
| --- | --- | --- |
| 测试用例集 | `/test-cases` | UI 自动化用例集列表，含"测试用例"（手工）+ "测试用例集"（AI 生成）两个视图入口 |
| 测试用例集详情/评审 | `/test-cases/{setId}/review?project={projectId}` | 评审已生成的用例 |
| 手工用例详情 | `/test-cases/manual/{caseId}?project={projectId}` | 查看/编辑手工用例 |
| UI 自动化列表 | `/automation/ui` | UI 自动化资产+生成运行统一列表 |
| UI 资产详情 | `/projects/{projectId}/automation/ui/assets/{assetId}` | 单个 UI 资产详情 |
| 接口自动化列表 | `/automation/api` | 接口用例集（`api_test_case_sets`）列表 |
| 接口场景编辑 | `/projects/{projectId}/automation/api/scenarios/{scenarioId}` | React Flow 场景编排编辑器 |
| 新建接口场景 | `/projects/{projectId}/automation/api/scenarios/new` | 创建新场景 |

### 2.2 后端路由

| 资源 | 路径 | 所在文件 |
| --- | --- | --- |
| 测试用例集 | `/projects/{project_id}/test-case-sets` | `test_cases.py`（不在本文件，但从 API 客户端确认存在） |
| UI 自动化生成运行 | `/projects/{project_id}/ui-automation/generation-runs` | `ui_automation.py` |
| UI 自动化资产 | `/projects/{project_id}/ui-automation/assets` | `ui_automation.py` |
| UI 自动化执行运行 | `/projects/{project_id}/ui-automation/runs` | `ui_automation.py` |
| 接口用例集 | `/projects/{project_id}/api-case-sets` | `api_automation.py` |
| 接口场景 | `/projects/{project_id}/api-scenarios` | `api_automation.py` |
| 接口场景步骤 | `/projects/{project_id}/api-scenarios/{scenario_id}/steps` | `api_automation.py` |
| 接口场景 AI 计划 | `/projects/{project_id}/api-scenarios/ai-plan` | `api_automation.py` |
| 接口场景发布 | `/projects/{project_id}/api-scenarios/{scenario_id}/publish` | `api_automation.py` |
| 接口场景执行 | `/projects/{project_id}/api-scenarios/{scenario_id}/execute` | `api_automation.py` |
| 接口场景版本 | `/projects/{project_id}/api-scenarios/{scenario_id}/revisions` | `api_automation.py` |
| 接口场景版本回滚 | `/projects/{project_id}/api-scenarios/{scenario_id}/revisions/{revision}/restore` | `api_automation.py` |

---

## 3. UI 自动化用例集（test_case_sets）

### 3.1 定位澄清

`test_case_sets` 表的原始设计意图是"UI 自动化用例集"，但**实际实现为需求驱动的测试用例生成与评审流水线**：

- 用户基于需求文档（`requirement_doc_id`）创建用例集；
- AI Agent 按需求内容生成结构化测试用例（`test_cases`）；
- 用例集状态推进：`generating` → `ready_for_review` → `review_completed`；
- 评审通过后可导出 XMind；
- 生成后可重新触发（`regenerate`），会替换集内用例。

### 3.2 状态机

```
generating → ready_for_review → review_completed
    ↓              ↓
  failed        archived
```

| 状态 | 含义 |
| --- | --- |
| `generating` | AI 正在生成用例，对应 `test_case_generation_runs` 运行中 |
| `ready_for_review` | 用例已生成，可进入评审页逐条 approve/reject |
| `review_completed` | 全部用例已评审（通过/驳回），可导出 XMind |
| `failed` | 生成失败 |
| `archived` | 归档 |

### 3.3 与下游模型的关系

```
test_case_sets
    └── test_case_generation_runs（生成运行）
    └── test_cases（生成后的用例，状态: draft/ready_for_review/approved/rejected）
    └── ui_automation_generation_runs（可选：基于已采纳用例触发生成 UI 自动化资产）
    └── ui_automation_assets（UI 自动化资产）
    └── ui_automation_execution_runs（执行运行）
```

**重要说明：** `test_case_sets` 与 UI 自动化之间的连接是**间接的**——通过已采纳（`status=approved`）的 `test_cases` 触发 `ui_automation_generation_runs`，进而生成 `ui_automation_assets`。`test_case_sets` 本身并不直接持有"UI 批量执行"语义。

### 3.4 用户流程

1. 用户在 `/test-cases` 点击"新建测试用例集"；
2. 选择需求文档（`requirement_doc_id`），填写生成范围（全部/指定），提交；
3. 后端创建 `test_case_sets`（status=`generating`）并调度 AI 生成任务 `test_case_generation_runs`；
4. 用例生成完成后，状态变为 `ready_for_review`；
5. 用户进入评审页 `/test-cases/{setId}/review`，对每条用例 `approve` / `reject`；
6. 全部评审后，状态变为 `review_completed`；
7. 用户可点击"导出 XMind"将用例集导出为标准格式；
8. 可对已完成的用例集触发"重新生成"（`regenerate`），会替换集内用例。

---

## 4. 接口自动化用例集（api_test_case_sets）

### 4.1 定位

`api_test_case_sets` 是接口自动化域的**用例分类聚合单元**：

- 当前实现为轻量级名称/备注管理（`name` + `notes`）；
- 不绑定 `api_test_cases`——用例集通过 endpoint_id 关键字聚合（绑定逻辑在 `api_test_case_set_bindings` 表）；
- 状态：`draft / generating / ready / failed / archived`；
- 可跟踪最近一次生成运行（`latest_generation_run_id`）。

### 4.2 CRUD 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/projects/{project_id}/api-case-sets` | 列表 |
| POST | `/projects/{project_id}/api-case-sets` | 创建（admin） |
| PATCH | `/projects/{project_id}/api-case-sets/{set_id}` | 修改（admin） |

前端入口：`/automation/api`，通过接口集名称链接进入 `/projects/{projectId}/automation/api?set={setId}`。

---

## 5. 接口自动化场景（api_scenarios）【已实现核心能力】

### 5.1 定位

`api_scenarios` 是**真正可编程的端点场景编排系统**，通过 `api_scenario_steps` 定义每个步骤的请求行为：

- 每个步骤引用 `api_endpoints`（HTTP 端点）或 `api_test_cases`（接口用例）；
- 支持变量提取（`extractors`）、请求覆盖（`request_overrides`）、断言（`assertions`）；
- 支持步骤级失败策略（`on_failure: stop/continue/always_run`）；
- AI 计划生成（`api_scenario_ai_plans`）：用户描述目标，AI 生成场景蓝图，可预览（preview）、应用（applied）或废弃（discarded）；
- 版本管理（`api_scenario_revisions`）：发布时生成快照，支持任意版本回滚（`restore`）；
- 执行（`execute`）：创建 `api_automation_run`，返回执行报告。

### 5.2 场景编排核心概念

```
api_scenarios
    └── variables_json：场景级变量（可被步骤提取/引用）
    └── revision：当前版本号（每次发布+1）
    └── published_snapshot_json：已发布快照
    └── api_scenario_steps（有序步骤）
            ├── step_type = "api_request"
            ├── endpoint_id 或 api_test_case_id
            ├── request_overrides_json（覆盖请求参数/头/体）
            ├── extractors_json（从响应提取变量）
            ├── assertions_json（断言配置）
            └── on_failure（失败策略）
    └── api_scenario_revisions（历史版本快照）
    └── api_scenario_ai_plans（AI 计划提案，preview/applied/discarded）
```

### 5.3 场景 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/projects/{project_id}/api-scenarios` | 列表 |
| POST | `/projects/{project_id}/api-scenarios` | 创建场景 |
| GET | `/projects/{project_id}/api-scenarios/{scenario_id}` | 详情（含步骤） |
| PATCH | `/projects/{project_id}/api-scenarios/{scenario_id}` | 修改场景 |
| DELETE | `/projects/{project_id}/api-scenarios/{scenario_id}` | 删除场景 |
| PUT | `/projects/{project_id}/api-scenarios/{scenario_id}/steps` | 全量替换步骤 |
| POST | `/projects/{project_id}/api-scenarios/{scenario_id}/steps` | 新增单个步骤 |
| POST | `/projects/{project_id}/api-scenarios/{scenario_id}/validate` | 验证场景配置 |
| POST | `/projects/{project_id}/api-scenarios/{scenario_id}/publish` | 发布场景（生成快照） |
| GET | `/projects/{project_id}/api-scenarios/{scenario_id}/revisions` | 列出历史版本 |
| POST | `/projects/{project_id}/api-scenarios/{scenario_id}/revisions/{revision}/restore` | 回滚到指定版本 |
| POST | `/projects/{project_id}/api-scenarios/{scenario_id}/execute` | 执行场景 |
| POST | `/projects/{project_id}/api-scenarios/ai-plan` | AI 计划生成 |
| POST | `/projects/{project_id}/api-scenarios/ai-plans/{plan_id}/apply` | 应用 AI 计划 |

### 5.4 用户流程（场景编排）

1. 用户在 `/automation/api` 点击"新建接口集"或直接进入场景编辑器；
2. 进入 `/projects/{projectId}/automation/api/scenarios/new` 创建场景，填写名称/描述；
3. 在 React Flow 编辑器中编排步骤（拖拽端点/用例节点，设置提取器/断言）；
4. 可通过"AI 计划生成"描述目标，AI 提案步骤编排，确认后应用；
5. 点击"验证"检查配置合法性；
6. 点击"发布"生成快照（`revision`+1，`published_snapshot_json` 存档）；
7. 可从历史版本列表回滚到任意已发布版本；
8. 点击"执行"，选择环境，创建 `api_automation_run`，返回场景级执行报告。

---

## 6. UI 自动化资产与批运行

### 6.1 定位

UI 自动化**不是测试集模型**，而是**资产-运行模型**：

- 资产（`ui_automation_assets`）由单个已采纳用例（`test_case_id`）或手工用例（`manual_test_case_id`）触发生成；
- 一次生成运行（`ui_automation_generation_runs`）对应一个资产；
- 资产可执行多次（`ui_automation_execution_runs`），每次产生独立报告；
- **不存在"批量 UI 测试集"**——旧 PRD 中此描述属于错误遗留，已在本轮更正。

### 6.2 资产状态

`ui_automation_assets.status`：`ready / degraded / deprecated`

### 6.3 用户流程

1. 用户在 `/automation/ui` 点击"新建 UI 自动化"；
2. 选择已采纳测试用例（或手工用例）+ 运行环境；
3. 触发生成运行 → 创建 `ui_automation_generation_runs`；
4. 生成成功后，资产 `ui_automation_assets` 可执行；
5. 点击执行，选择环境，创建 `ui_automation_execution_runs`，跳转到执行详情页。

---

## 7. 数据模型

### 7.1 test_case_sets（UI 自动化用例集）

```sql
CREATE TABLE test_case_sets (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  requirement_doc_id TEXT NOT NULL,        -- 关联需求文档
  exploration_run_id TEXT NOT NULL DEFAULT '',
  include_company_knowledge INTEGER NOT NULL DEFAULT 0,
  generation_scope_type TEXT NOT NULL CHECK(generation_scope_type IN ('all', 'specified')),
  generation_scope_text TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN (
    'generating', 'ready_for_review', 'review_completed', 'failed', 'archived'
  )),
  case_count INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

关联：`test_case_generation_runs`（生成运行）、`test_cases`（用例）。

### 7.2 api_test_case_sets（接口自动化用例集）

```sql
CREATE TABLE api_test_case_sets (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN ('draft', 'generating', 'ready', 'failed', 'archived')) DEFAULT 'draft',
  case_count INTEGER NOT NULL DEFAULT 0,
  latest_generation_run_id TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 7.3 api_scenarios（接口自动化场景）

```sql
CREATE TABLE api_scenarios (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN ('draft', 'ready', 'archived')) DEFAULT 'draft',
  variables_json TEXT NOT NULL DEFAULT '{}',          -- 场景级变量
  revision INTEGER NOT NULL DEFAULT 0,                -- 每次发布+1
  published_snapshot_json TEXT NOT NULL DEFAULT '{}', -- 已发布快照
  published_hash TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  updated_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 7.4 api_scenario_steps（场景步骤）

```sql
CREATE TABLE api_scenario_steps (
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  step_type TEXT NOT NULL DEFAULT 'api_request',
  endpoint_id TEXT,                    -- 引用 HTTP 端点
  api_test_case_id TEXT,               -- 或引用接口用例
  step_order INTEGER NOT NULL DEFAULT 0,
  name TEXT NOT NULL DEFAULT '',
  request_overrides_json TEXT NOT NULL DEFAULT '{}',  -- 请求覆盖
  bindings_json TEXT NOT NULL DEFAULT '[]',            -- 变量绑定
  extractors_json TEXT NOT NULL DEFAULT '[]',         -- 提取器
  assertions_json TEXT NOT NULL DEFAULT '[]',         -- 断言
  control_config_json TEXT NOT NULL DEFAULT '{}',
  on_failure TEXT NOT NULL CHECK(on_failure IN ('stop', 'continue', 'always_run')) DEFAULT 'stop',
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 7.5 api_scenario_revisions（场景历史版本）

```sql
CREATE TABLE api_scenario_revisions (
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL,          -- 完整场景快照
  published_hash TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(scenario_id, revision)
);
```

### 7.6 api_scenario_ai_plans（AI 场景计划）

```sql
CREATE TABLE api_scenario_ai_plans (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  scenario_id TEXT,
  expected_revision INTEGER,
  goal TEXT NOT NULL,                   -- 用户描述的编排目标
  request_json TEXT NOT NULL DEFAULT '{}',
  plan_json TEXT NOT NULL DEFAULT '{}', -- AI 生成的步骤编排方案
  validation_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL CHECK(status IN ('preview', 'applied', 'discarded', 'expired')) DEFAULT 'preview',
  model_provider TEXT NOT NULL DEFAULT '',
  model_name TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  applied_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TEXT NOT NULL,
  applied_at TEXT
);
```

---

## 8. API 总表

### 8.1 测试用例集（test_case_sets）

| 资源 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| 测试用例集 | GET | `/projects/{project_id}/test-case-sets` | 列表 |
| 测试用例集 | POST | `/projects/{project_id}/test-case-sets` | 创建（AI 生成） |
| 测试用例集 | GET | `/projects/{project_id}/test-case-sets/{set_id}` | 详情（含用例） |
| 测试用例集 | POST | `/projects/{project_id}/test-case-sets/{set_id}/regenerate` | 重新生成 |
| 测试用例集 | DELETE | `/projects/{project_id}/test-case-sets/{set_id}` | admin |
| 测试用例评审 | POST | `/projects/{project_id}/test-cases/{case_id}/review` | approve / reject |
| 手工用例 | GET | `/projects/{project_id}/test-cases` | 列表 |
| 手工用例 | POST | `/projects/{project_id}/test-cases` | 创建 |
| 手工用例 | DELETE | `/projects/{project_id}/test-cases/{case_id}` | admin |

### 8.2 UI 自动化

| 资源 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| UI 生成运行 | POST | `/projects/{project_id}/ui-automation/generation-runs` | 触发生成（admin） |
| UI 生成运行 | GET | `/projects/{project_id}/ui-automation/generation-runs` | 列表 |
| UI 生成运行 | GET | `/projects/{project_id}/ui-automation/generation-runs/{run_id}` | 详情 |
| UI 资产 | GET | `/projects/{project_id}/ui-automation/assets` | 列表 |
| UI 资产 | GET | `/projects/{project_id}/ui-automation/assets/{asset_id}` | 详情 |
| UI 资产 | GET | `/projects/{project_id}/ui-automation/assets/{asset_id}/generation-runs` | 关联生成运行 |
| UI 资产 | GET | `/projects/{project_id}/ui-automation/assets/{asset_id}/runs` | 关联执行运行 |
| UI 执行运行 | POST | `/projects/{project_id}/ui-automation/assets/{asset_id}/runs` | 创建执行（admin） |
| UI 执行运行 | GET | `/projects/{project_id}/ui-automation/runs/{run_id}` | 详情 |
| UI 执行运行 | POST | `/projects/{project_id}/ui-automation/runs/{run_id}/stop` | 停止（admin） |
| UI 执行运行 | DELETE | `/projects/{project_id}/ui-automation/runs/{run_id}` | admin |
| UI 执行日志 | GET | `/projects/{project_id}/ui-automation/runs/{run_id}/logs` | 日志流 |
| UI 执行直播 | GET | `/projects/{project_id}/ui-automation/runs/{run_id}/live-view` | 实时视图 |

### 8.3 接口用例集

| 资源 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| 接口用例集 | GET | `/projects/{project_id}/api-case-sets` | 列表 |
| 接口用例集 | POST | `/projects/{project_id}/api-case-sets` | 创建（admin） |
| 接口用例集 | PATCH | `/projects/{project_id}/api-case-sets/{set_id}` | 修改（admin） |

### 8.4 接口场景（api_scenarios）

| 资源 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| 接口场景 | GET | `/projects/{project_id}/api-scenarios` | 列表 |
| 接口场景 | POST | `/projects/{project_id}/api-scenarios` | 创建（admin） |
| 接口场景 | GET | `/projects/{project_id}/api-scenarios/{scenario_id}` | 详情 |
| 接口场景 | PATCH | `/projects/{project_id}/api-scenarios/{scenario_id}` | 修改（admin） |
| 接口场景 | DELETE | `/projects/{project_id}/api-scenarios/{scenario_id}` | admin |
| 场景步骤 | PUT | `/projects/{project_id}/api-scenarios/{scenario_id}/steps` | 全量替换 |
| 场景步骤 | POST | `/projects/{project_id}/api-scenarios/{scenario_id}/steps` | 新增步骤 |
| 场景验证 | POST | `/projects/{project_id}/api-scenarios/{scenario_id}/validate` | 验证配置 |
| 场景发布 | POST | `/projects/{project_id}/api-scenarios/{scenario_id}/publish` | 发布（admin） |
| 场景历史 | GET | `/projects/{project_id}/api-scenarios/{scenario_id}/revisions` | 版本列表 |
| 场景回滚 | POST | `/projects/{project_id}/api-scenarios/{scenario_id}/revisions/{revision}/restore` | 回滚（admin） |
| 场景执行 | POST | `/projects/{project_id}/api-scenarios/{scenario_id}/execute` | 执行（admin） |
| AI 计划 | POST | `/projects/{project_id}/api-scenarios/ai-plan` | AI 生成计划（admin） |
| AI 计划 | POST | `/projects/{project_id}/api-scenarios/ai-plans/{plan_id}/apply` | 应用计划（admin） |

---

## 9. 已知实现边界

1. **`test_case_sets` ≠ UI 自动化批量执行**：表名为"测试用例集"，实为需求驱动用例生成流水线；真正的 UI 自动化执行单元是 `ui_automation_assets`，不存在"UI 批量测试集"实体。
2. **`api_test_case_sets` 当前仅为名称/备注管理**：不直接持有用例绑定关系，用例聚合通过 endpoint_id 关键字实现。
3. **`test_case_sets` 无 XMind 导出接口**（旧 PRD 中提到导出，源码中未找到导出端点——`test_case_xmind_exporter` 可能存在但未在 API 层暴露）。
4. **UI 自动化生成不支持探索产物注入**（前端 "使用探索产物" 选项目前 disabled）。
5. **所有场景执行均为 admin 权限**（`require_admin` 装饰器）。
6. **AI 计划有失效时间**（`expires_at` 字段），过期后不可应用。

---

## 10. 与旧 PRD 的差异说明

以下为旧版 00-20 PRD（2026-07-25 基线）中的**已过时描述**及本轮更正：

| 旧版描述 | 状态 | 本轮更正 |
| --- | --- | --- |
| "旧 PRD 中提到'UI 批量测试集 / UI 测试集 API / UI 测试集管理页面' **未实现**" | ❌ 旧表述 | 本轮**删除此描述**——旧版错误地将 UI 自动化资产列表理解为"UI 批量测试集"，已在本 PRD 中明确区分 |
| "场景编排（`api_scenarios`）是独立模块，不在本 PRD 范围" | ❌ 旧表述 | 本轮**删除此描述**——`api_scenarios` 已完整实装，包含步骤编排/AI 计划/版本管理/执行，本 PRD 第 5 章已完整覆盖 |
| "`api_test_case_sets` 与 `api_test_cases` 没有绑定关系" | ⚠️ 部分过时 | 本轮更正：`api_test_case_sets` 仍然**不直接持有**用例绑定，但场景步骤（`api_scenario_steps`）可通过 `api_test_case_id` 引用具体用例，实现间接聚合 |
| "UI 资产执行不支持'批量/编排'概念" | ✅ 仍然成立 | UI 自动化为单资产-多次执行模型，确实无批量编排能力 |
| "旧 PRD 中'暂不做创建/编辑/执行'描述" | ❌ 旧表述 | 本轮**删除**——`api_scenarios` 的创建/编辑/执行均已实现 |

---

## 11. 验收标准

- `test_case_sets` 生成后状态从 `generating` 推进到 `ready_for_review`，前端评审页可逐条 approve/reject；
- `test_case_sets` 重新生成会替换集内用例；
- `api_test_case_sets` 支持通过 `/api-case-sets` 接口创建、修改；
- `api_scenarios` 支持完整生命周期：创建 → 编排步骤 → AI 计划生成 → 发布 → 执行 → 回滚；
- `ui_automation_assets` 支持从已采纳用例触发生成、执行，不存在跨资产的"批量执行"；
- 三套模型（`test_case_sets` / `api_test_case_sets` / `api_scenarios`）在 API 层分明，前端入口不混淆。

---

## 12. 实现依据

- 测试用例集：`apps/backend/app/api/v1/test_cases.py`（路由定义）、`apps/backend/app/services/test_case_service.py`
- UI 自动化：`apps/backend/app/api/v1/ui_automation.py`、`apps/backend/app/services/ui_automation/service.py`
- 接口用例集/场景：`apps/backend/app/api/v1/api_automation.py`、`apps/backend/app/services/api_automation/service.py`
- 前端：`apps/frontend/src/app/(main)/test-cases/page.tsx`、`apps/frontend/src/app/(main)/automation/ui/page.tsx`、`apps/frontend/src/app/(main)/automation/api/page.tsx`、`apps/frontend/src/app/(main)/projects/[projectId]/automation/api/scenarios/[scenarioId]/page.tsx`
- API 客户端类型：`apps/frontend/src/lib/api-client.ts`（`ApiTestCaseSet` / `ApiAutomationCaseSet` / `ApiScenario` 等）
- 数据库 Schema：`apps/backend/app/seed/schema.py`
