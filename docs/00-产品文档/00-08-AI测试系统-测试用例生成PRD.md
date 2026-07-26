# 00-08 AI测试系统 - 测试用例生成 PRD

## 0. 基线与事实源

- 基线日期：2026-07-26
- 事实源：当前工作区源码（含未提交代码），不再参考旧 PRD 内容。
- 事实源路径清单：
  - 前端列表：`apps/frontend/src/app/(main)/test-cases/page.tsx`
  - 前端手工用例：`apps/frontend/src/app/(main)/test-cases/manual/[caseId]/page.tsx`
  - 前端评审：`apps/frontend/src/app/(main)/test-cases/[setId]/review/page.tsx`
  - 后端 API 路由：`apps/backend/app/api/v1/test_cases.py`
  - 后端服务（用例集）：`apps/backend/app/services/test_case_service.py`
  - 后端服务（测试点）：`apps/backend/app/services/test_point_service.py`
  - 后端 Agent（AI 用例生成）：`apps/backend/app/agents/test_case_generation/service.py`
  - 后端 Agent（手工用例生成）：`apps/backend/app/agents/manual_test_case_generation/service.py`
  - 后端 Agent（测试点生成）：`apps/backend/app/agents/test_point_generation/service.py`
  - 手工用例生成编排：`apps/backend/app/services/manual_test_case_generation/service.py`
  - 拒绝用例知识化：`apps/backend/app/services/rejected_case_knowledge/service.py`
  - XMind 导出：`apps/backend/app/services/test_case_xmind_exporter.py`
  - 数据库 Schema：`apps/backend/app/seed/schema.py`
  - 排序逻辑：`apps/backend/app/seed/seeds.py`（`_ensure_test_case_display_order`）
- 实现状态标签：
  - 【已实现】基于代码已可直接运行的能力。
  - 【未实现】代码中不存在的功能或说明。
  - 【占位说明】仅 UI 层占位，无后端能力。

---

## 1. 范围与目标

本模块覆盖"AI 测试用例 + 手工用例"双轨并行：

1. **AI 测试用例集**：基于需求文档的最终需求版本，从已生成的测试点出发，AI 按模块分批批量生成测试用例集（TestCaseSet）。
2. **手工用例**：支持用户手工创建单条测试用例（ManualTestCase），并可选择由 AI 辅助生成草稿。
3. **测试点（TestPoint）**：从最终需求版本提取业务义务（Obligation），进而生成测试点，作为测试用例的生成输入。
4. **评审与采纳**：对 AI 生成用例进行逐条评审，结果分为已采纳/未采纳/待评审。
5. **拒绝用例知识化**：被拒绝的用例原因自动沉淀到公司知识库，供后续生成参考。
6. **XMind 导出**：将已评审用例导出为 XMind Workbook 格式。

UI 自动化代码生成、接口自动化代码生成、报告中心、KPI 面板不在本文范围内。

---

## 2. 业务边界

### 2.1 本模块负责

- 基于项目最终需求版本的测试用例集生成、状态轮询、评审与采纳。
- 基于最终需求版本提取业务义务并生成测试点（TestPoint）。
- 基于手工输入（含 AI 辅助）的单条测试用例创建、查看、删除。
- 已采纳/未采纳/待评审用例的状态切换、拒绝原因强制保存。
- 拒绝记录沉淀到全局"不采纳用例库"，供后续生成时 Agentic Search 检索。
- XMind Workbook 导出（用例集粒度）。

### 2.2 本模块不负责

- 站点探索、登录自动化（属于 00-04 站点探索模块）。
- 知识库生成与维护（属于 00-05 知识库模块）。
- 用例直接驱动 UI 自动化或接口自动化代码生成（属于 00-09 / 00-16）。
- 报告中心（00-13）、控制台（00-07）、系统设置（00-15）。
- 需求文档的分析与版本管理（属于 00-03 需求文档分析与版本管理模块）。

---

## 3. 页面入口与路由

| 前端页面 | 路由 | 说明 |
| --- | --- | --- |
| 测试用例列表 | `/test-cases` | 混显 AI 生成用例集（TestCaseSet）与手工用例（ManualTestCase）；支持搜索、筛选、新建、删除 |
| 手工用例详情 | `/test-cases/manual/[caseId]?project=<projectId>` | 查看单条手工用例正文 |
| 用例集评审台 | `/test-cases/[setId]/review?project=<projectId>` | 列表/思维导图切换；逐条评审；统计与采纳率；XMind 导出 |

实现依据：
- 前端：`apps/frontend/src/app/(main)/test-cases/page.tsx`（列表）、`apps/frontend/src/app/(main)/test-cases/manual/[caseId]/page.tsx`（手工用例）、`apps/frontend/src/app/(main)/test-cases/[setId]/review/page.tsx`（评审台）。
- 前端 API 类型：`apps/frontend/src/lib/api-client.ts`（`ApiTestCaseSet`、`ApiTestCase`、`ApiManualTestCase`、`ApiTestCaseReviewStats`、`ApiTestCaseReviewResult` 等）。
- 后端路由：`apps/backend/app/api/v1/test_cases.py`，双 router：`router`（用例集）、`manual_router`（手工用例）。

---

## 4. 测试用例集（TestCaseSet）生命周期

### 4.1 状态枚举

```
generating → ready_for_review → review_completed
    ↓              ↓                  ↓
  failed        (评审中)           archived
    ↓
  archived（手动）
```

| 状态 | 含义 |
| --- | --- |
| `generating` | 用例正在 AI 生成中，关联的 `test_case_generation_run` 状态为 `queued/running` |
| `ready_for_review` | 用例生成完成，等待评审 |
| `review_completed` | 全部用例已完成评审（采纳/拒绝） |
| `failed` | 生成失败（服务重启中断、Agent 异常等） |
| `archived` | 已归档（手动或生成失败后自动归档） |

### 4.2 关联需求文档

用例集必须绑定该项目下一个已有的需求文档（`requirement_doc_id`），且该需求文档必须已生成最终需求版本（`source_action ∈ {requirement_analysis, requirement_analysis_finalize, edit}`）。

### 4.3 生成范围

| 类型 | 字段 | 说明 |
| --- | --- | --- |
| `all` | - | 基于最终需求版本的全部测试点生成 |
| `specified` | `generation_scope_text`（必填） | 用户填写范围说明，AI 仅在指定范围内生成 |

---

## 5. AI 生成

### 5.1 生成流程

1. 管理员在 `/test-cases` 选择"新建测试用例集"，填写名称、选择需求文档、确定生成范围。
2. 系统创建 `test_case_sets`（`status='generating'`）与 `test_case_generation_runs`（`status='queued'`）。
3. 后台任务 `execute_test_case_generation_run` 启动：
   - 收集该最终需求版本的全部测试点（`test_points`，按 `requirement_doc_id + requirement_version_id` 索引）。
   - 调用 `rejected_case_search` Agent 检索"全局不采纳用例库"中与该需求/测试点相关的活跃记录（最多 20 条，按 relevance `high`/`medium` 过滤，并通过 `matched_test_point_keys` 校验）。
   - 将命中的不采纳记录写入 `test_case_generation_runs.input_snapshot.knowledge_search` 元数据。
   - 调用 `test_case_generation` Agent 按测试点分模块、按 `TEST_POINT_BATCH_SIZE=5` 批量生成 `TestCaseGenerationResult`，并行批次数受 `asyncio.Semaphore(MAX_CONCURRENT_BATCHES=3)` 限制。
   - 首次返回与历史不采纳记录冲突时注入冲突说明触发一次重试；重试后仍存在的 `duplicate` 用例会被删除；`uncorrected` 错误直接抛出。
4. 用例集状态置为 `ready_for_review`，每条用例 `status='ready_for_review'`，按模块与 P0/P1/P2/P3 优先级排序并重新编号。
5. 前端列表每 5 秒轮询一次活动生成任务（`TEST_CASE_SET_POLL_INTERVAL_MS=5000`）。
6. 管理员可对用例集触发"重新生成"（`POST /test-case-sets/{set_id}/regenerate`），系统会创建新的 generation run 替换全部已有用例。

### 5.2 测试点（TestPoint）作为生成输入

AI 用例生成的输入不直接是需求文本，而是从最终需求版本生成的**测试点**：

- **测试点来源**：从最终需求版本提取业务义务（Obligation），由 `test_point_generation` Agent 生成测试点。
- **测试点字段**：`point_key / title / module / category / priority / description / verification_points / requirement_obligation_keys`。
- **覆盖率评估**：生成后计算 `obligation_count / covered_obligation_count`，缺失义务展示在覆盖摘要中。
- **补充轮次**：若覆盖不完整，自动进入补充轮次（最多 4 轮，`supplement_round` 字段记录）。

### 5.3 生成依赖链

```
最终需求版本（source_action 满足条件）
    → test_point_generation_runs + test_points
    → test_case_generation_runs + test_cases
```

任何一步缺失均无法进入下一步。

---

## 6. 手工用例（ManualTestCase）

手工用例独立于用例集体系，不走评审状态机，无版本与采纳状态字段。

### 6.1 CRUD

| 操作 | 路由 | 权限 |
| --- | --- | --- |
| 列表 | `GET /projects/{project_id}/test-cases` | 全部用户 |
| 详情 | `GET /projects/{project_id}/test-cases/{case_id}` | 全部用户 |
| 创建 | `POST /projects/{project_id}/test-cases` | admin |
| AI 辅助生成 | `POST /projects/{project_id}/test-cases/ai-generate` | admin |
| 删除 | `DELETE /projects/{project_id}/test-cases/{case_id}` | admin |

### 6.2 AI 辅助生成

- 前端在"新建测试用例"对话框内集成 AI 生成入口（`Sparkles` 按钮）。
- 调用 `build_exploration_context` 从探索产物抽取页面/操作/元素上下文。
- 调用 `manual_test_case_generation` Agent 产出单条用例草稿。
- 返回 `ManualTestCaseAiGenerateOut`，附带 `source_summary`（`exploration_artifacts_requested / exploration_artifacts_used / page_count / operation_count / truncated`）。
- 表单已有内容时会弹覆盖确认对话框。

---

## 7. 评审

### 7.1 用例评审状态

```
ready_for_review → approved / rejected
```

| 状态 | 含义 |
| --- | --- |
| `ready_for_review` | 待评审（生成后默认状态） |
| `approved` | 已采纳 |
| `rejected` | 未采纳（必须填写拒绝原因 `review_feedback`） |

### 7.2 评审功能（评审台）

| 功能 | 说明 |
| --- | --- |
| 列表/思维导图切换 | 评审台支持两种视图切换（`TestCaseMindMap` 组件） |
| 过滤 | 按状态筛选（待评审 / 已采纳 / 未采纳） |
| 搜索 | 按用例标题/内容搜索 |
| 单条评审 | 逐条点击采纳/拒绝 |
| 反馈 | 拒绝时必须填写原因；采纳时可选填写备注 |
| 自动跳转下一条 | 评审完成后自动滚动到下一条待评审用例 |
| 评审统计 | 展示 `case_count / approved_count / rejected_count / pending_count / reviewed_count / adoption_rate / review_progress` |
| 正文修改 | 评审时支持同步传 `preconditions / steps / expected_result` 修改用例正文 |
| 导出 XMind | `GET /projects/{project_id}/test-case-sets/{set_id}/export/xmind` |

### 7.3 评审流程

1. `PATCH /test-case-sets/{set_id}/cases/{case_id}/review` 支持三种状态切换。
2. `status='rejected'` 时 `review_feedback` 必填（后端返回 `422`）。
3. 后端依赖链校验：项目可见性 → 用例集存在 → 用例存在 → 关联需求与 generation_run（已完成）存在；否则返回 `409 TEST_CASE_GENERATION_ORIGIN_MISSING`。
4. `rejected` 时调用 `rejected_case_knowledge.upsert_rejected_case(...)` 写入或激活 Markdown 知识库记录；`approved` 或其他值会触发 `deactivate_record(...)`。
5. 全部用例完成评审后，用例集状态自动置 `review_completed`。

---

## 8. 拒绝用例知识化

### 8.1 知识库结构

- 知识库名称：**不采纳用例库**（首次调用时自动创建为全局 Vault）。
- 按项目名建立子目录，需求级 Markdown 文件由 `markdown_codec.upsert_record` 维护。
- 记录 ID 由 `derive_record_id`（SHA256 哈希）生成，保证全局唯一。

### 8.2 记录归类

`_classify_reason` 按关键字归类拒绝原因：

| 归类 | 关键字 | handling |
| --- | --- | --- |
| 重复用例 | 含"重复" | `block_duplicate` |
| 已被其他用例覆盖 | 含"已被"+"覆盖" | `block_duplicate` |
| 业务场景不成立 | 含"不存在/不成立/超出需求/不支持" | `block_duplicate` |
| 预期结果错误 | 含"缺少/步骤/预期/前置/不可执行/不准确/错误" | `generate_with_correction` |
| 其他 | 其他情况 | `warning_only` |

### 8.3 Agentic Search

- `rejected_case_search` Agent 一次最多返回 20 条，只接受 `high`/`medium` 等级。
- 强制校验 `record_id` / `source_file_id` 来自虚拟文件树，否则抛出 `ValueError`。
- 每批次最多注入 10 条相关记录到用例生成 prompt。

### 8.4 状态切换与去激活

- 用例从 `rejected` 切换到 `approved`/`ready_for_review` 时，调用 `deactivate_record` 将对应 Markdown 记录标记为 `inactive`（`deactivated_at` 时间戳）。

---

## 9. 测试点（TestPoint）模型

### 9.1 从最终需求生成

- `test_point_generation` Agent 接收最终需求内容，调用 `extract_requirement_obligations` 提取业务义务列表。
- `_atomize_module_obligations` 将多模块义务拆分为独立原子义务（保证每个模块可独立覆盖）。
- Agent 生成测试点，关联到对应的义务 key。

### 9.2 支持手动编辑

- `PATCH /projects/{project_id}/requirements/{document_id}/test-points/{point_id}`：更新测试点正文。
- 标题去重检查：同一需求版本下标题不能重复。
- 支持 Markdown 批量编辑（`save_markdown`）。

### 9.3 AI 修改测试点

- 测试点生成 Agent 可在补充轮次中补充缺失义务对应的测试点。

### 9.4 覆盖率评估

- `evaluate_test_point_coverage`：对比义务列表与测试点关联的义务 key，计算覆盖率状态（`complete / incomplete / invalid`）。
- `coverage_summary` 返回：`obligation_count / covered_obligation_count / missing_obligations / unsupported_assumptions / supplement_round`。

### 9.5 缺失义务展示

- 覆盖不完整时，`missing_obligations` 展示缺失义务的 `obligation_key / source_section / statement`。

### 9.6 补充轮次

- 最多 4 轮补充（`supplement_round` 字段）。
- 每一轮补充后重新评估覆盖率；若覆盖无进展则提前终止。
- 补充完成后，若覆盖率状态为 `complete` 则 `test_point_generation_runs.status='completed'`，否则为 `failed`。

---

## 10. 测试点义务（Obligation）模型

### 10.1 数据结构

`test_point_requirement_obligations` 表存储从最终需求版本提取的业务义务：

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `project_id / document_id / requirement_version_id` | 绑定到特定需求版本 |
| `obligation_key` | 义务唯一标识（如 `OBL-001`） |
| `source_section` | 义务所在的需求章节 |
| `statement` | 义务描述语句 |
| `obligation_type` | 义务类型 |
| `modules_json` | 关联的模块列表 |
| `thresholds_json` | 阈值配置 |
| `explicit` | 是否显式提取（1=显式，0=隐含） |
| `test_required` | **是否必须测试**（关键字段，`True` 时计入覆盖率） |

### 10.2 关联关系

- `test_point_obligations`：测试点与义务的多对多关联表。
  - `test_point_id` → `test_points.id`
  - `obligation_id` → `test_point_requirement_obligations.id`
  - `requirement_version_id` → `source_document_versions.id`

### 10.3 覆盖率计算逻辑

在 `_compute_coverage_summary` 中：
- 遍历所有义务，筛除 `test_required=False` 的义务。
- 统计已关联义务 key 的测试点数量，计算 `covered_obligation_count`。
- 缺失义务展示在 `missing_obligations` 中，供补充轮次使用。

---

## 11. 状态机与查询

### 11.1 测试用例集状态机

```
test_case_sets.status: generating → ready_for_review → review_completed / failed / archived
test_case_generation_runs.status: queued → running → completed / failed
```

- 正在生成时由 `test_case_generation_runs.status in {queued, running}` 触发前端轮询。
- 应用启动时 `recover_interrupted_test_case_generation_runs()` 会把所有 `queued/running` 的 generation run 标记为 `failed`，用例集置为 `failed`，错误信息为"服务已重启，内存中的测试用例生成任务已中断，请重新创建测试用例集。"。

### 11.2 测试用例状态机

```
test_cases.status: draft → ready_for_review → approved / rejected
```

- `approved` 与 `rejected` 之间可由前端"再次编辑"路径在更新正文的同时保持/重置状态。

### 11.3 测试点状态机

```
test_point_generation_runs.status: queued → running → completed / failed
```

- 应用启动时 `recover_interrupted_generation_runs()` 把所有 `queued/running` 的 run 标记为 `failed`。

---

## 12. 字段 `display_order` 与排序索引

### 12.1 排序逻辑

`test_cases` 表含 `display_order` 字段（`INTEGER NOT NULL DEFAULT 0`），按以下规则排序：

1. **模块顺序**（`module_order`）：用例按模块名首次出现的顺序编号。
2. **优先级**：`P0 → P1 → P2 → P3`（对应 rank 0~3）。
3. **同模块同优先级内**：按 `created_at` 升序。

索引：`idx_test_cases_set_display_order ON test_cases(test_case_set_id, display_order)`

### 12.2 排序填充时机

- 用例生成完成后，`_complete_generation_run` 按上述规则填充 `display_order`。
- 数据库迁移时 `_ensure_test_case_display_order`（`seeds.py:462-500`）会为已有数据填充 `display_order` 并创建索引。

---

## 13. API 路由清单（V1）

挂在 `/api/v1`，前缀 `/projects/{project_id}`：

### 13.1 用例集路由（`router`，前缀 `/projects/{project_id}/test-case-sets`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/projects/{project_id}/test-case-sets` | 列表（返回全部用例集，含最新 generation_run 与 review_stats） |
| POST | `/projects/{project_id}/test-case-sets` | 新建用例集（admin），返回用例集与 generation_run 摘要，后台异步执行生成 |
| GET | `/projects/{project_id}/test-case-sets/{set_id}` | 详情（含用例列表与不采纳原因） |
| GET | `/projects/{project_id}/test-case-sets/{set_id}/export/xmind` | XMind Workbook 下载（`application/vnd.xmind.workbook`） |
| PATCH | `/projects/{project_id}/test-case-sets/{set_id}/cases/{case_id}/review` | 评审（含拒绝原因写入知识库） |
| POST | `/projects/{project_id}/test-case-sets/{set_id}/regenerate` | 重新生成（admin） |
| DELETE | `/projects/{project_id}/test-case-sets/{set_id}` | 删除用例集及全部用例（admin） |

### 13.2 手工用例路由（`manual_router`，前缀 `/projects/{project_id}/test-cases`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/projects/{project_id}/test-cases` | 列表 |
| GET | `/projects/{project_id}/test-cases/{case_id}` | 详情 |
| POST | `/projects/{project_id}/test-cases` | 新建手工用例（admin） |
| POST | `/projects/{project_id}/test-cases/ai-generate` | AI 辅助生成单条手工用例（admin） |
| DELETE | `/projects/{project_id}/test-cases/{case_id}` | 删除（admin） |

### 13.3 错误码

| 状态码 | code | 说明 |
| --- | --- | --- |
| 400 | `NO_FINAL_REQUIREMENT` | 需求文档尚未生成最终需求 |
| 400 | `INVALID_REQUIREMENT_DOCUMENT` | 请选择当前项目下的需求 |
| 409 | `TEST_CASE_GENERATION_RUNNING` | 该用例集正在生成中 |
| 409 | `TEST_CASE_GENERATION_ORIGIN_MISSING` | 用例缺少可追溯的生成来源 |
| 409 | `NO_FINAL_REQUIREMENT` | 请先生成最终需求 |
| 409 | `TEST_POINTS_NOT_GENERATED` | 当前最终需求尚未生成测试点 |
| 409 | `TEST_POINT_TITLE_DUPLICATE` | 测试点标题已存在 |
| 502 | `AI_GENERATION_FAILED` | AI 生成智能体未返回结构化结果 |
| 503 | `REJECTED_CASE_KNOWLEDGE_UNAVAILABLE` | 拒绝用例知识库不可用 |

---

## 14. 数据模型

### 14.1 表总览

| 表名 | 用途 |
| --- | --- |
| `test_case_sets` | 用例集主表 |
| `test_case_generation_runs` | 用例集生成运行记录（含 input_snapshot 快照） |
| `test_cases` | 单条 AI 生成用例（步骤以 `steps_json` 持久化，含 display_order） |
| `test_point_generation_runs` | 测试点生成运行记录（含覆盖率元数据） |
| `test_points` | 测试点主表 |
| `test_point_requirement_obligations` | 需求义务表（绑定 requirement_version_id，含 test_required） |
| `test_point_obligations` | 测试点-义务多对多关联表 |
| `manual_test_cases` | 手工用例主表 |

### 14.2 test_case_sets

```sql
CREATE TABLE IF NOT EXISTS test_case_sets (
  id TEXT PRIMARY KEY,                          -- tcs-<hex>
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,                            -- 用户填写，最长 120 字符
  requirement_doc_id TEXT NOT NULL,              -- 必须为该项目下已有最终需求版本的需求
  exploration_run_id TEXT NOT NULL DEFAULT '',   -- 探索产物 run ID（保留字段）
  include_company_knowledge INTEGER NOT NULL DEFAULT 0,
  generation_scope_type TEXT NOT NULL,           -- 'all' / 'specified'
  generation_scope_text TEXT NOT NULL DEFAULT '', -- specified 模式必填
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,                         -- generating/ready_for_review/review_completed/failed/archived
  case_count INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(requirement_doc_id) REFERENCES source_documents(id) ON DELETE RESTRICT
);
CREATE INDEX idx_test_case_sets_project_updated ON test_case_sets(project_id, updated_at);
CREATE INDEX idx_test_case_sets_requirement ON test_case_sets(requirement_doc_id);
```

### 14.3 test_case_generation_runs

```sql
CREATE TABLE IF NOT EXISTS test_case_generation_runs (
  id TEXT PRIMARY KEY,                           -- tcgr-<hex>
  test_case_set_id TEXT NOT NULL,
  task_id TEXT NOT NULL UNIQUE,                  -- test_case_generation:<run_id>
  status TEXT NOT NULL,                          -- queued/running/completed/failed
  input_json TEXT NOT NULL DEFAULT '{}',          -- 快照含 knowledge_search 元数据
  error_message TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  FOREIGN KEY(test_case_set_id) REFERENCES test_case_sets(id) ON DELETE CASCADE
);
CREATE INDEX idx_test_case_generation_runs_set ON test_case_generation_runs(test_case_set_id, created_at);
```

### 14.4 test_cases

```sql
CREATE TABLE IF NOT EXISTS test_cases (
  id TEXT PRIMARY KEY,                           -- <set_id>-tc-<序号>
  test_case_set_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  title TEXT NOT NULL,
  test_description TEXT NOT NULL DEFAULT '',
  module TEXT NOT NULL DEFAULT '',
  priority TEXT NOT NULL DEFAULT '',
  display_order INTEGER NOT NULL DEFAULT 0,      -- 按模块+优先级排序
  preconditions TEXT NOT NULL DEFAULT '',
  steps_json TEXT NOT NULL DEFAULT '[]',         -- [{action, expected_result}]
  expected_result TEXT NOT NULL DEFAULT '',
  source_requirement_refs TEXT NOT NULL DEFAULT '[]',
  source_exploration_refs TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL,                          -- draft/ready_for_review/approved/rejected
  review_feedback TEXT NOT NULL DEFAULT '',
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(test_case_set_id) REFERENCES test_case_sets(id) ON DELETE CASCADE,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX idx_test_cases_set_display_order ON test_cases(test_case_set_id, display_order);
```

### 14.5 test_point_generation_runs

```sql
CREATE TABLE IF NOT EXISTS test_point_generation_runs (
  id TEXT PRIMARY KEY,                           -- tpgr-<hex>
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  requirement_version_id TEXT NOT NULL,
  task_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,                          -- queued/running/completed/failed
  input_json TEXT NOT NULL DEFAULT '{}',
  error_message TEXT NOT NULL DEFAULT '',
  coverage_status TEXT NOT NULL DEFAULT 'pending', -- pending/complete/incomplete/invalid
  obligation_count INTEGER NOT NULL DEFAULT 0,
  covered_obligation_count INTEGER NOT NULL DEFAULT 0,
  missing_obligations_json TEXT NOT NULL DEFAULT '[]',
  obligations_json TEXT NOT NULL DEFAULT '[]',
  unsupported_assumptions_json TEXT NOT NULL DEFAULT '[]',
  supplement_round INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
  FOREIGN KEY(requirement_version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX uq_test_point_generation_version ON test_point_generation_runs(document_id, requirement_version_id);
```

### 14.6 test_points

```sql
CREATE TABLE IF NOT EXISTS test_points (
  id TEXT PRIMARY KEY,                           -- tp-<hex>
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  requirement_version_id TEXT NOT NULL,
  generation_run_id TEXT NOT NULL,
  point_key TEXT NOT NULL,                      -- SHA1(module + title)，同版本唯一
  title TEXT NOT NULL,
  module TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL,
  priority TEXT NOT NULL DEFAULT 'P1',
  description TEXT NOT NULL DEFAULT '',
  preconditions_json TEXT NOT NULL DEFAULT '[]',
  verification_points_json TEXT NOT NULL DEFAULT '[]',
  source_refs_json TEXT NOT NULL DEFAULT '[]',
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
  FOREIGN KEY(requirement_version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE,
  FOREIGN KEY(generation_run_id) REFERENCES test_point_generation_runs(id) ON DELETE CASCADE,
  UNIQUE(requirement_version_id, point_key)
);
CREATE INDEX idx_test_points_document_version ON test_points(document_id, requirement_version_id);
```

### 14.7 test_point_requirement_obligations

```sql
CREATE TABLE IF NOT EXISTS test_point_requirement_obligations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  requirement_version_id TEXT NOT NULL,
  obligation_key TEXT NOT NULL,
  source_section TEXT NOT NULL,
  statement TEXT NOT NULL,
  obligation_type TEXT NOT NULL,
  modules_json TEXT NOT NULL DEFAULT '[]',
  thresholds_json TEXT NOT NULL DEFAULT '[]',
  explicit INTEGER NOT NULL DEFAULT 1,
  test_required INTEGER NOT NULL DEFAULT 1,     -- 是否必须测试，False 时不计入覆盖率
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
  FOREIGN KEY(requirement_version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE,
  UNIQUE(requirement_version_id, obligation_key)
);
CREATE INDEX idx_test_point_obligations_document_version ON test_point_requirement_obligations(document_id, requirement_version_id);
```

### 14.8 test_point_obligations

```sql
CREATE TABLE IF NOT EXISTS test_point_obligations (
  test_point_id TEXT NOT NULL,
  obligation_id TEXT NOT NULL,
  requirement_version_id TEXT NOT NULL,
  PRIMARY KEY(test_point_id, obligation_id),
  FOREIGN KEY(test_point_id) REFERENCES test_points(id) ON DELETE CASCADE,
  FOREIGN KEY(obligation_id) REFERENCES test_point_requirement_obligations(id) ON DELETE CASCADE,
  FOREIGN KEY(requirement_version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE
);
```

### 14.9 manual_test_cases

```sql
CREATE TABLE IF NOT EXISTS manual_test_cases (
  id TEXT PRIMARY KEY,                           -- mtc-<hex>
  project_id TEXT NOT NULL,
  title TEXT NOT NULL,
  preconditions TEXT NOT NULL DEFAULT '',
  steps_json TEXT NOT NULL DEFAULT '[]',         -- [{action, expected_result}]
  notes TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX idx_manual_test_cases_project_updated ON manual_test_cases(project_id, updated_at);
```

---

## 15. 验收规则

| 序号 | 规则 | 核对依据路径 |
| --- | --- | --- |
| 1 | 项目内无最终需求版本时新建用例集被拒，返回 `400 NO_FINAL_REQUIREMENT` | `test_case_service._require_final_requirement_version` |
| 2 | 用例集可指定 `all` 或 `specified` 范围；`specified` 缺 `generation_scope_text` 时 pydantic 校验拒绝 | `schemas.test_case.TestCaseSetCreateIn` |
| 3 | 单项目内同一用例集存在状态为 `generating` 时，再次提交重新生成被拒，返回 `409 TEST_CASE_GENERATION_RUNNING` | `test_case_service.regenerate_test_case_set` |
| 4 | 评审 `rejected` 缺 `review_feedback` 时返回 `422` | `schemas.test_case.TestCaseReviewIn` |
| 5 | 评审 `rejected` 后对应 Markdown 知识库记录被创建/激活；`approved`/`ready_for_review` 后会被 `deactivate_record` | `rejected_case_knowledge.service` |
| 6 | 全部用例完成评审后，用例集状态自动置 `review_completed` | `test_case_service._sync_set_review_status` |
| 7 | XMind 导出返回 `application/vnd.xmind.workbook`，模块与步骤结构完整，可被 XMind 客户端打开 | `test_case_xmind_exporter.py` |
| 8 | 手工用例：标题为空、步骤缺 `expected_result` 时接口拒绝（pydantic 校验） | `schemas.test_case.ManualTestCaseCreateIn` |
| 9 | AI 辅助手工用例：`include_exploration_artifacts` 关闭且无探索产物时 `source_summary.exploration_artifacts_used=false` | `manual_test_case_generation/service.py` |
| 10 | AI 辅助手工用例返回 `502 AI_GENERATION_FAILED` 仅在 Agent 抛错或返回格式错误时触发 | `manual_test_case_generation/service.py` |
| 11 | 应用重启后处于 `queued/running` 的用例集被自动标记 `failed`，前端可观察到错误信息 | `test_case_service.recover_interrupted_test_case_generation_runs` |
| 12 | 用例按模块+优先级排序，`display_order` 正确填充，`idx_test_cases_set_display_order` 索引存在 | `seeds.py:_ensure_test_case_display_order` |
| 13 | 拒绝用例搜索每批次最多注入 10 条记录到 prompt | `test_case_generation/service.py:_references_for_batch` |
| 14 | 测试点义务 `test_required=False` 时不计入覆盖率缺失义务 | `test_point_service._compute_coverage_summary` |
| 15 | 拒绝用例归类正确：`duplicate`→`block_duplicate`，`error`→`generate_with_correction`，其他→`warning_only` | `rejected_case_knowledge.service._classify_reason` |

---

## 16. 实现依据

- 后端 API：`apps/backend/app/api/v1/test_cases.py`
- 后端服务（用例集）：`apps/backend/app/services/test_case_service.py`
- 后端服务（测试点）：`apps/backend/app/services/test_point_service.py`
- 后端 Agent（AI 用例生成）：`apps/backend/app/agents/test_case_generation/service.py`
- 后端 Agent（手工用例生成）：`apps/backend/app/agents/manual_test_case_generation/service.py`
- 后端 Agent（测试点生成）：`apps/backend/app/agents/test_point_generation/service.py`
- 手工用例生成编排：`apps/backend/app/services/manual_test_case_generation/service.py`
- 拒绝用例知识化：`apps/backend/app/services/rejected_case_knowledge/service.py`
- XMind 导出：`apps/backend/app/services/test_case_xmind_exporter.py`
- 数据库 Schema：`apps/backend/app/seed/schema.py`
- 排序迁移：`apps/backend/app/seed/seeds.py`（`_ensure_test_case_display_order`）
- 前端列表：`apps/frontend/src/app/(main)/test-cases/page.tsx`
- 前端手工用例详情：`apps/frontend/src/app/(main)/test-cases/manual/[caseId]/page.tsx`
- 前端评审台：`apps/frontend/src/app/(main)/test-cases/[setId]/review/page.tsx`
- 前端思维导图组件：`apps/frontend/src/components/ai-testing/test-case-mind-map.tsx`
- 前端 API 类型定义：`apps/frontend/src/lib/api-client.ts`
