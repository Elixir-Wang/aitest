# 00-03 AI 测试系统 · 需求文档分析与版本管理 PRD

> 范围声明：本文档描述 AI 测试系统内"需求文档"的完整生命周期管理能力，覆盖上传 → 转换 → 版本 → 分析 → 澄清 → 定稿 → 测试点联动的全部功能点。如需与其他模块配合，请参见对应 PRD。

---

## 0. 基线与事实源

- **基线日期：2026-07-26**
- **事实源：** 本仓库当前工作区源码（含未提交代码）
  - 前端：`apps/frontend/src/app/(main)/requirements/`、`apps/frontend/src/components/ai-testing/requirements-page.tsx` / `requirement-upload-page.tsx` / `test-points-panel.tsx`
  - 后端：`apps/backend/app/api/v1/requirements/`（含 `__init__.py`、`documents.py`、`files.py`、`uploads.py`、`versions.py`、`analysis_runs.py`、`analysis.py`、`test_points.py`、`metadata.py`）
  - 后端服务：`apps/backend/app/services/document/`、`apps/backend/app/services/test_point_service.py`
  - 数据库：`apps/backend/app/seed/schema.py`
- **实现状态总览：**
  - 已实现：文档上传（multipart）、后台文件转换、文档版本管理、需求分析 run（启动/停止/轮询）、澄清问答写入 Markdown 版本、最终化（finalize）→ 测试点自动入队、元数据更新触发新一轮测试点、覆盖矩阵展示
  - 部分实现：文档 Tab 顺序（7 个 Tab）、版本差异对比（仅版本列表，预览页面独立路由）、版本内 Markdown 编辑

---

## 1. 范围与目标

### 1.1 目标

让"原始需求文档 → 标准化 Markdown → 初步需求（带澄清）→ 最终需求 → 测试点"这条链路全程可追溯、可版本化、可重放。

- **可追溯**：每次操作均落操作日志（`operation_log_service`）
- **可版本化**：每次上传、转换、AI 编辑、人工编辑均生成新版本（`source_document_versions`）
- **可联动**：最终化后自动触发测试点生成任务；元数据（需求名称/内容）更新后自动触发新一轮测试点

### 1.2 链路总览

```
文档上传（multipart）
  → convert_pending_file_mappings（后台 PDF/Word → Markdown）
  → 启动需求分析 run（queued → running）
  → 初步需求 Markdown + 待澄清问题表
  → 澄清问答（推荐选项/自定义/跳过 → 写入初步需求 Markdown）
  → finalize（finalize_requirement_analysis → source_document_versions）
  → test_point_service.enqueue_generation（自动入队）
  → 测试点覆盖矩阵展示
```

---

## 2. 文档上传

### 2.1 支持格式

| 格式 | 扩展名 | 处理方式 |
| --- | --- | --- |
| PDF | `.pdf` | 后台 OCR/解析 → Markdown |
| Word | `.doc` / `.docx` | 后台解析 → Markdown |
| TXT | `.txt` | 直接保存为 Markdown |
| Markdown | `.md` / `.markdown` | 直接保存为 Markdown |

### 2.2 上传方式

- **分片上传（multipart）**：大文件分片传输，断点续传
- 上传前计算文件 SHA256 作为 `signature`，用于断点续传与一致性校验
- 前端配置来源：`GET /api/v1/requirement-uploads/config`（返回 `max_files` / `max_file_size` / `chunk_size` / `max_batch_size`）

### 2.3 上传流程（session 模式）

1. `POST /api/v1/requirement-uploads/sessions` 创建分片上传 session（mode：`new` 或 `append`）
2. `PUT /api/v1/requirement-uploads/sessions/:sessionId/parts/:partNumber` 上传分片（带 `X-Chunk-SHA256` 头）
3. `POST /api/v1/requirement-uploads/sessions/:sessionId/complete` 完成后端合并，触发 `convert_pending_file_mappings` 排队
4. 取消：`DELETE /api/v1/requirement-uploads/sessions/:sessionId`

> 实现依据：`uploads.py`（路由）+ `upload_sessions.py`（服务）+ `requirement-upload-client.ts`（前端客户端）

### 2.4 校验项

| 校验项 | 限制 |
| --- | --- |
| 单次最多上传文件数 | `max_files`（来自上传配置） |
| 单文件最大大小 | `max_file_size`（来自上传配置） |
| 单次上传总大小上限 | `max_batch_size`（来自上传配置） |
| 不支持格式 | 客户端前置拦截，提示"仅支持 PDF、Word、TXT、MD 文件" |

### 2.5 新建 vs 追加

- **新建模式（mode=new）**：创建新需求文档，自动以第一个文件名为默认需求名称
- **追加模式（mode=append）**：向已有文档追加源文件，新文件作为非主需求文件加入；追加后文档状态保持 `versioned`

> 实现依据：`documents.py:26-50`（路由 multipart）+ `requirement-upload-page.tsx:88-117`（追加模式选择已有文档）

---

## 3. 文档转换

### 3.1 转换触发

- 上传完成（`complete_session`）后，通过 `BackgroundTasks` 触发 `convert_pending_file_mappings`
- `mode=new` 时自动设置 `auto_continue=True`，转换成功后自动启动需求分析 run
- `mode=append` 时 `auto_continue=False`，不自动启动分析

### 3.2 转换状态

| 状态值 | 含义 |
| --- | --- |
| `pending` | 排队中 |
| `running` | 转换中 |
| `success` | 转换成功（可直接用于分析） |
| `warning` | 转换成功但有质量问题（可用但建议人工确认） |
| `failed` | 转换失败（`conversion_error` 字段记录原因） |

> 实现依据：`source_document_file_mappings.conversion_status` + `file_service.py`

### 3.3 转换失败处理

- `conversion_status=failed` 时，前端展示失败原因（`conversion_error` 字段）
- 用户可删除该源文件或重新上传替换，不影响其他源文件

---

## 4. 文档版本

### 4.1 版本生成时机

每次以下操作均生成新版本：

| 触发操作 | `source_action` |
| --- | --- |
| 文件上传 + 转换成功 | `create` |
| 需求分析最终化 | `requirement_analysis_finalize` |
| 概览 Tab 编辑需求内容 | `edit` |
| 版本预览页 Markdown 编辑 | `edit` |
| 切换版本（设置 `current_version_id`） | 不生成新版本，只更新指针 |

> 实现依据：`source_document_versions` 表 + `document_repo.py` 的 `create_version` / `update_current_version`

### 4.2 版本数据结构

```
source_document_versions(
  id, document_id, version_no,
  markdown_content / file_path,
  source_action, change_summary, diff_summary,
  created_by, created_at
)
```

### 4.3 版本切换

- 入口：`PUT /api/v1/projects/:projectId/requirements/:documentId/versions/:versionId/current`
- **限制**：只能切换 `source_action ∈ {requirement_analysis, requirement_analysis_finalize}` 的版本（非最终需求版本不可切换）
- 切换不生成新版本，只更新 `documents.current_version_id`
- 切换后，下游（知识检索、测试点）自动使用新版本

> 实现依据：`versions.py:49-86`（`switch_document_current_version`）

### 4.4 版本列表

- `GET /api/v1/projects/:projectId/requirements/:documentId/versions`
- 每条记录：`version_no / source_action / change_summary / diff_summary / created_by / created_at`
- 前端独立版本列表页：`/projects/:projectId/requirements/:documentId/versions`

### 4.5 版本预览与 Markdown 编辑

- 版本预览页：`/projects/:projectId/requirements/:documentId/versions/:versionId`
- 版本 Markdown 内容在预览页内展示
- 版本切换功能在预览页内提供（见 §4.3）

---

## 5. 标准化 Markdown

### 5.1 标准化文件来源

- 主需求文件（`source_document_file_mappings.is_primary=1` / `file_role=primary`）的转换结果
- 仅当主需求文件 `conversion_status ∈ {success, warning}` 且存在 `markdown_file_path` 时才允许发起需求分析

### 5.2 标准化 Markdown 手动编辑

概览 Tab 支持对当前最终需求 Markdown 进行在线编辑：

- 编辑入口：`PUT /api/v1/projects/:projectId/requirements/:documentId`
- 入参：`SourceDocumentUpdateIn`（含 `markdown_content`）
- 副作用：生成新版本（`source_action=edit`），更新 `current_version_id`，触发 `test_point_service.enqueue_generation`

> 实现依据：`documents.py:64-77`（`update_requirement`）+ `test_point_service.enqueue_generation`

---

## 6. 需求分析

### 6.1 分析 Run 状态机

| 状态 | 含义 |
| --- | --- |
| `queued` | 排队中 |
| `running` | 分析中 |
| `stopping` | 停止中（中间态） |
| `cancelled` | 已取消 |
| `completed` | 分析完成（无澄清问题） |
| `needs_clarification` | 产出 ≥1 条澄清问题 |
| `blocked` | Agent 输出不合规（schema 校验失败） |
| `failed` | 异常或超时（默认 30 分钟） |

### 6.2 启动分析

- 入口：`POST /api/v1/projects/:projectId/requirements/:documentId/analysis-runs`
- 前置条件：
  - 文档存在
  - 存在主需求文件且转换状态为 `success` 或 `warning`
  - 当前没有 `queued/running/stopping` 的活动 run
- 副作用：
  - 清空 `current_version_id`（状态回到 `pending_review`）
  - 保存 `previous_current_version_id` 用于取消/失败时回退
  - 创建 `requirement_analysis_runs`（id = `reqrun-<hex8>`）
  - 提交 `task_service` → 后台执行 `execute_requirement_review_run`

> 实现依据：`analysis_runs.py`（路由）+ `analysis_runs.py`（服务）

### 6.3 轮询与状态更新

- 前端每 2.5 秒轮询一次 run 状态（仅在 `queued/running` 时）
- 服务重启恢复：`recover_stale_requirement_analysis_runs` 将 `running/queued/stopping` 标记为 `failed`

### 6.4 分析报告

- `GET /api/v1/projects/:projectId/requirements/:documentId/analysis`
- 返回字段：`understanding_markdown`（初步需求）、`clarification_items[]`（澄清问题）、`analysis_summary`、`quality_result`、`testability_score`

### 6.5 停止分析

- 入口：`POST /api/v1/projects/:projectId/requirements/:documentId/analysis-runs/:runId/stop`
- `queued`/`running` 直接置 `stopping`，完成后转为 `cancelled`
- 二次点击同步直接完成取消

---

## 7. 澄清问答

### 7.1 澄清问题结构

每条澄清问题包含：

- `id` / `question` / `title`（问题描述）
- `priority`（优先级：P0/P1/P2）
- `module_name` / `module_key`（所属模块，用于定位写入位置）
- `option_a` / `option_b`（推荐选项 A/B）
- `impact`（影响说明）
- `decision_point`（决策点描述，用于生成标题）

### 7.2 回答方式

| 回答类型 | 行为 |
| --- | --- |
| `recommended_option` | 选择推荐答案 A 或 B（仅选一项） |
| `custom` | 自定义 Markdown 答复 |
| `defer` | 跳过该问题，不写入初步需求 |

### 7.3 写入 Markdown 机制

- 回答后自动改写 `understanding_markdown`：在匹配模块章节下追加，匹配失败则落到 `## 需求补充`
- 写入使用 HTML 注释锚点标记：`<!-- clarification-answer:{id}:start -->...<!-- clarification-answer:{id}:end -->`
- 同一问题重复回答时：先删除旧块，再插入新块

> 实现依据：`analysis.py:146-282`（13 个 Markdown patch helper：`_apply_clarification_answer_to_markdown` / `_remove_existing_clarification_answer` / `_append_to_matching_section` 等）

### 7.4 答案持久化

- 写入 `requirement_clarification_answers` 表
- 答案快照写入 `output_json` 中对应 `clarification_items[id].answer`

### 7.5 最终化前置校验

- 高优先级问题（P0/P1）必须全部回答（`applied`）或跳过（`not_applicable`）后才允许 finalize
- `confirm_unresolved=true` 可强制 finalize（需前端显式确认）

---

## 8. 最终化（finalize）

### 8.1 最终化入口

- 入口：`POST /api/v1/projects/:projectId/requirements/:documentId/analysis/:analysisId/finalize`
- 入参：`{ analysis_id, confirm_unresolved: bool }`

### 8.2 最终化流程

1. 校验分析结果未最终化、分析是最新、主需求文件未变更、初步需求非空
2. 调 `run_requirement_finalization`（Agent）合成最终需求 Markdown
3. 创建 `source_document_versions`（`source_action=requirement_analysis_finalize`），落 Markdown 到存储路径
4. 写 `document_version_change_logs`
5. 设置 `documents.current_version_id`，状态置为 `versioned`
6. 标记 `requirement_analyses.finalized_version_id`
7. **自动触发 `test_point_service.enqueue_generation`**（后台入队，不阻塞返回）

> 实现依据：`analysis.py:410-570`（`finalize_requirement_analysis`）+ `documents.py:44-54`（API 层触发测试点入队）

### 8.3 测试点自动联动

- `finalize_requirement_analysis` 返回中包含 `test_point_generation_run`
- 后台任务 `test_point_service.execute_generation_run` 异步执行
- 覆盖矩阵（coverage）状态实时更新

---

## 9. 测试点联动

### 9.1 测试点生成时机

| 触发时机 | 触发方式 |
| --- | --- |
| finalize 完成后 | `finalize_requirement_analysis` 自动调用 `test_point_service.enqueue_generation` |
| 概览 Tab 更新元数据/内容 | `update_requirement` 触发 `test_point_service.enqueue_generation` |
| 用户主动点击"生成测试点" | `POST /api/v1/projects/:projectId/requirements/:documentId/test-points/generate` |

### 9.2 测试点生成 run 状态

| 状态 | 含义 |
| --- | --- |
| `queued` | 排队中 |
| `running` | 生成中（多轮补充，最高达 4 轮） |
| `completed` | 完成（覆盖完整） |
| `failed` | 失败（覆盖不完整或异常） |

### 9.3 覆盖矩阵

- 测试点生成完成后计算覆盖状态：`complete / incomplete / invalid / pending`
- 概览数据：`obligation_count`（总义务数）/ `covered_obligation_count`（已覆盖数）/ `missing_obligations[]`（未覆盖义务）
- 前端展示在概览 Tab（`TestPointCoverageSummary` 组件）

### 9.4 测试点编辑

- 全量 Markdown 编辑：`PUT /api/v1/projects/:projectId/requirements/:documentId/test-points/markdown`
- 单条编辑：`PATCH /api/v1/projects/:projectId/requirements/:documentId/test-points/:pointId`
- 删除：`DELETE /api/v1/projects/:projectId/requirements/:documentId/test-points/:pointId`
- AI 辅助编辑：调用 `POST /agents/document-editor/run`（`test-points-panel.tsx:134-159`）

> 实现依据：`test_points.py`（路由）+ `test_point_service.py`（服务）

---

## 10. 版本管理

### 10.1 版本列表

- 路由：`GET /api/v1/projects/:projectId/requirements/:documentId/versions`
- 字段：`version_no / source_action / change_summary / diff_summary / created_by / created_at`
- 前端页面：`/projects/:projectId/requirements/:documentId/versions`

### 10.2 版本详情

- 路由：`GET /api/v1/projects/:projectId/requirements/:documentId/versions/:versionId`
- 返回：`version_no / source_action / markdown_content / is_current`
- 前端页面：`/projects/:projectId/requirements/:documentId/versions/:versionId`

### 10.3 版本切换

- 路由：`PUT /api/v1/projects/:projectId/requirements/:documentId/versions/:versionId/current`
- 限制：仅 `source_action ∈ {requirement_analysis, requirement_analysis_finalize}` 的版本可切换
- 副作用：更新 `current_version_id`，下游自动使用新版本

### 10.4 版本 Markdown 编辑

- 在版本预览页可编辑 Markdown 并保存
- 编辑生成新版本（`source_action=edit`）

---

## 11. Tab 顺序（需求详情页）

需求详情页包含 7 个 Tab，顺序固定：

| 顺序 | Tab 名称 | 路由值 | 主要内容 |
| --- | --- | --- | --- |
| 1 | 概览 | `overview` | 文档元信息、原始文件列表、进度步骤、覆盖矩阵入口 |
| 2 | 原始文件 | `original` | 源文件列表（文件名/上传时间/转换状态/角色） |
| 3 | 标准文件 | `standard` | Markdown 预览、转换后内容展示 |
| 4 | 需求分析 | `analysis` | 初步需求 Markdown + 澄清问题表（含两个子 Tab：需求分析 / 待澄清） |
| 5 | 最终需求 | `final` | 当前最终需求 Markdown 预览与编辑 |
| 6 | 测试要点 | `test-points` | 测试点列表/脑图、覆盖矩阵、生成/编辑/重新生成 |
| 7 | 版本记录 | `versions` | 版本列表、版本切换入口 |

> 实现依据：`page.tsx:1742-1752`（TabsTrigger）+ `page.tsx:2033-2038`（分析 Tab 内部子 Tab）

---

## 12. 校验项

### 12.1 最终化前置校验

| 校验项 | 失败提示 |
| --- | --- |
| 主需求文件未指定或转换未成功 | "主需求标准文件未生成" |
| 尚未生成初步需求 | "尚未生成初步需求" |
| 初步需求为空 | "需求理解为空，不能转为最终需求" |
| 主需求文件已变更 | "主需求文件已变更，请重新执行需求分析" |
| 高优先级（P0/P1）澄清问题未全部处理 | 前端拦截，不允许点击"转为最终需求" |
| 分析被阻塞（`blocked`） | "存在阻塞问题，不能转为最终需求" |

### 12.2 前端最终化按钮状态

```
canFinalizeRequirement = requirementReviewPassed && !finalizeDisabledReason && requiredPendingAnalysisHandled
```

- `requirementReviewPassed`：`status ∈ {completed, needs_clarification}` 且非 `blocked`
- `finalizeDisabledReason`：见 §12.1 各校验项
- `requiredPendingAnalysisHandled`：所有 P0/P1 问题均已 `applied` 或 `not_applicable`

---

## 13. 数据模型

### 13.1 核心表（8 张）

```sql
-- 需求文档
source_documents(
  id, project_id, name, document_type,
  current_version_id,
  status('pending_review'|'versioned'),
  created_by, created_at, updated_at
)

-- 源文件映射
source_document_file_mappings(
  id, document_id, version_id,
  source_file_path, original_filename, file_format,
  markdown_file_path, preview_file_path,
  conversion_status('pending'|'running'|'success'|'warning'|'failed'),
  mapping_status, file_role('primary'|'supporting'),
  conversion_summary, conversion_quality,
  created_by, created_at
)

-- 文档版本
source_document_versions(
  id, document_id, version_no,
  markdown_content, file_path,
  source_action, change_summary, diff_summary,
  created_by, created_at
)

-- 版本变更日志
document_version_change_logs(
  id, document_id, version_id,
  source_action, change_summary, diff_summary,
  affected_modules(JSON), source_mapping_ids(JSON),
  created_by, created_at
)

-- 需求分析结果
requirement_analyses(
  id, project_id, document_id, version_id, primary_mapping_id,
  status, analysis_summary,
  output_json(JSON), quality_result, testability_score,
  draft_content_hash,
  finalized_version_id, finalized_at, finalized_by,
  created_by, created_at, updated_at
)

-- 需求分析运行
requirement_analysis_runs(
  id, project_id, document_id, primary_mapping_id, analysis_id,
  status('queued'|'running'|'stopping'|'cancelled'|'completed'|'needs_clarification'|'blocked'|'failed'),
  summary, failure_reason, previous_current_version_id,
  created_by, created_at, updated_at
)

-- 澄清问答答案
requirement_clarification_answers(
  id, project_id, document_id, analysis_id, question_id,
  answer_type('recommended_option'|'custom'|'defer'),
  selected_option_id, answer_markdown, user_note,
  apply_status('applied'|'not_applicable'|'failed'),
  insertion_anchor, failure_reason,
  created_by, created_at, updated_at
)

-- 最终化运行
requirement_finalization_runs(
  id, project_id, document_id, analysis_id,
  status('running'|'completed'|'failed'),
  summary, failure_reason,
  created_by, created_at, updated_at
)
```

### 13.2 测试点相关表（3 张）

```sql
-- 测试点生成运行
test_point_generation_runs(
  id, project_id, document_id, requirement_version_id, task_id,
  status('queued'|'running'|'completed'|'failed'),
  input_json, error_message,
  coverage_status, obligation_count, covered_obligation_count,
  missing_obligations_json(JSON), obligations_json(JSON),
  unsupported_assumptions_json(JSON), supplement_round,
  created_by, created_at, updated_at, finished_at
)

-- 测试点
test_points(
  id, project_id, document_id, requirement_version_id, generation_run_id,
  point_key, title, module, category, priority,
  description, preconditions_json(JSON), verification_points_json(JSON),
  source_refs_json(JSON), notes,
  created_at, updated_at
)

-- 需求义务
test_point_requirement_obligations(
  id, project_id, document_id, requirement_version_id,
  obligation_key, source_section, statement,
  obligation_type, modules_json(JSON), thresholds_json(JSON),
  explicit, test_required,
  created_at
)
```

### 13.3 索引

```sql
CREATE INDEX idx_requirement_analysis_runs_project_created ON requirement_analysis_runs(project_id, created_at);
CREATE INDEX idx_requirement_analysis_runs_document_created ON requirement_analysis_runs(document_id, created_at);
CREATE INDEX idx_requirement_analysis_runs_status ON requirement_analysis_runs(status);
CREATE INDEX idx_requirement_clarification_answers_document ON requirement_clarification_answers(document_id, created_at);
CREATE INDEX idx_test_points_document_version ON test_points(document_id, requirement_version_id);
CREATE INDEX idx_test_point_obligations_document_version ON test_point_requirement_obligations(document_id, requirement_version_id);
CREATE UNIQUE INDEX uq_test_point_generation_version ON test_point_generation_runs(document_id, requirement_version_id);
```

---

## 14. API 路由清单

### 14.1 上传会话

| 方法 | 路径 |
| --- | --- |
| GET | `/api/v1/requirement-uploads/config` |
| POST | `/api/v1/requirement-uploads/sessions` |
| GET | `/api/v1/requirement-uploads/sessions/:upload_id` |
| DELETE | `/api/v1/requirement-uploads/sessions/:upload_id` |
| PUT | `/api/v1/requirement-uploads/sessions/:upload_id/files/:file_id/parts/:part_number` |
| POST | `/api/v1/requirement-uploads/sessions/:upload_id/complete` |

### 14.2 项目内文档 CRUD

| 方法 | 路径 |
| --- | --- |
| GET | `/api/v1/projects/:projectId/requirements` |
| POST | `/api/v1/projects/:projectId/requirements` |
| GET | `/api/v1/projects/:projectId/requirements/:documentId` |
| PUT | `/api/v1/projects/:projectId/requirements/:documentId` |
| DELETE | `/api/v1/projects/:projectId/requirements/:documentId` |

### 14.3 文件操作

| 方法 | 路径 |
| --- | --- |
| GET | `/api/v1/projects/:projectId/requirements/:documentId/files` |
| POST | `/api/v1/projects/:projectId/requirements/:documentId/files` |
| PUT | `/api/v1/projects/:projectId/requirements/:documentId/files/:mapping_id/primary` |

### 14.4 分析运行

| 方法 | 路径 |
| --- | --- |
| POST | `/api/v1/projects/:projectId/requirements/:documentId/analysis-runs` |
| POST | `/api/v1/projects/:projectId/requirements/:documentId/analysis-runs/:runId/stop` |
| GET | `/api/v1/projects/:projectId/requirements/:documentId/analysis-runs` |

### 14.5 分析产物

| 方法 | 路径 |
| --- | --- |
| GET | `/api/v1/projects/:projectId/requirements/:documentId/analysis` |
| PUT | `/api/v1/projects/:projectId/requirements/:documentId/analysis/:analysisId/preliminary` |
| POST | `/api/v1/projects/:projectId/requirements/:documentId/analysis/:analysisId/finalize` |
| GET | `/api/v1/projects/:projectId/requirements/:documentId/analysis/:analysisId/clarification-answers` |
| POST | `/api/v1/projects/:projectId/requirements/:documentId/analysis/:analysisId/clarification-answers` |

### 14.6 版本管理

| 方法 | 路径 |
| --- | --- |
| GET | `/api/v1/projects/:projectId/requirements/:documentId/versions` |
| GET | `/api/v1/projects/:projectId/requirements/:documentId/versions/:versionId` |
| PUT | `/api/v1/projects/:projectId/requirements/:documentId/versions/:versionId/current` |

### 14.7 测试点

| 方法 | 路径 |
| --- | --- |
| GET | `/api/v1/projects/:projectId/requirements/:documentId/test-points` |
| POST | `/api/v1/projects/:projectId/requirements/:documentId/test-points/generate` |
| PUT | `/api/v1/projects/:projectId/requirements/:documentId/test-points/markdown` |
| PATCH | `/api/v1/projects/:projectId/requirements/:documentId/test-points/:pointId` |
| DELETE | `/api/v1/projects/:projectId/requirements/:documentId/test-points/:pointId` |

### 14.8 元数据

| 方法 | 路径 |
| --- | --- |
| GET | `/api/v1/projects/:projectId/requirements/check-name` |
| GET | `/api/v1/projects/:projectId/requirements/:documentId/overview` |

### 14.9 全局路由

| 方法 | 路径 |
| --- | --- |
| GET | `/api/v1/requirements` |

---

## 15. 前端页面清单

| 页面 | 路由 | 说明 |
| --- | --- | --- |
| 需求列表（全局） | `/requirements` | 全部项目的需求文档列表，支持过滤 |
| 需求列表（项目内） | `/projects/:projectId/requirements` | 当前项目内需求列表 |
| 新建需求 | `/requirements/upload` | 上传新需求文档（mode=new） |
| 追加文件 | `/requirements/upload?mode=append&documentId=...` | 向已有需求追加文件 |
| 需求详情 | `/projects/:projectId/requirements/:documentId` | 7-Tab 详情页 |
| 版本列表 | `/projects/:projectId/requirements/:documentId/versions` | 所有版本记录 |
| 版本预览 | `/projects/:projectId/requirements/:documentId/versions/:versionId` | 单个版本预览与切换 |

---

## 16. 验收规则

### 16.1 上传与转换

| 编号 | 验收条件 | 验证方式 |
| --- | --- | --- |
| AC-01 | 上传 1 个 docx 主需求文件后，转换状态经历 `pending → running → success`；UI 显示转换成功 | 手动测试 |
| AC-02 | 上传文件总数超 `max_files` 时，前端提示"单次最多上传 N 个文件" | 手动测试 |
| AC-03 | 单文件超 `max_file_size` 时，前端提示"单文件不能超过 X MB" | 手动测试 |
| AC-04 | 不支持格式文件被客户端拦截，提示"仅支持 PDF、Word、TXT、MD 文件" | 手动测试 |
| AC-05 | 断网后重连，可从上次分片位置继续上传（signature 校验） | 手动测试 |

### 16.2 版本管理

| 编号 | 验收条件 | 验证方式 |
| --- | --- | --- |
| AC-06 | finalize 后 `source_document_versions` 新增一条记录；`current_version_id` 指向新版本 | API 检查 |
| AC-07 | 概览 Tab 编辑需求内容后，新版本号递增，旧版本仍可预览/切换 | 手动测试 |
| AC-08 | 版本列表页可来回切换 `current_version_id`；切换后下游（知识检索/测试点）自动使用新版本 | 手动测试 |
| AC-09 | 非最终需求版本（`source_action` 非 `requirement_analysis/finalize`）切换时返回 409 | API 检查 |

### 16.3 需求分析

| 编号 | 验收条件 | 验证方式 |
| --- | --- | --- |
| AC-10 | 点击"开始需求评审"后，run 进入 `queued → running → completed/needs_clarification` | 手动测试 |
| AC-11 | 未指定主需求文件时，点击"开始需求评审"返回 409 `DOCUMENT_PRIMARY_FILE_REQUIRED` | API 检查 |
| AC-12 | 分析运行中再次发起新 run，返回 409 `REQUIREMENT_ANALYSIS_RUN_ACTIVE` | API 检查 |
| AC-13 | 服务重启后，正在运行的 run 被标记为 `failed`，UI 可见失败原因 | 重启测试 |

### 16.4 澄清问答

| 编号 | 验收条件 | 验证方式 |
| --- | --- | --- |
| AC-14 | 对每条澄清选择推荐答案/自定义/跳过，初步需求 Markdown 对应位置更新并落库 | 手动测试 |
| AC-15 | 同一问题重复回答，旧答案块被替换而非追加 | 手动测试 |
| AC-16 | P0/P1 澄清问题未全部处理时，"转为最终需求"按钮被禁用 | 手动测试 |

### 16.5 最终化与测试点联动

| 编号 | 验收条件 | 验证方式 |
| --- | --- | --- |
| AC-17 | finalize 后，测试点生成任务自动入队（`test_point_generation_run` 状态为 `queued`） | API 检查 |
| AC-18 | finalize 后文档状态变为 `versioned`，下游知识检索命中该版本 | 知识检索测试 |
| AC-19 | 概览 Tab 更新需求名称/内容，触发新一轮测试点生成 | 手动测试 |
| AC-20 | 测试点生成完成后，覆盖矩阵展示义务总数/已覆盖数/未覆盖义务列表 | 手动测试 |

### 16.6 权限与可见性

| 编号 | 验收条件 | 验证方式 |
| --- | --- | --- |
| AC-21 | 非项目成员无法访问文档详情（返回 403） | 权限测试 |
| AC-22 | 非管理员无法生成/编辑测试点（`require_admin` 拦截） | API 检查 |
| AC-23 | 删除已关联测试用例集的需求文档时返回 409 并提示 | API 检查 |

---

## 17. 与其它 PRD 的边界

| 关联 PRD | 边界说明 |
| --- | --- |
| PRD 00-04（站点探索） | 探索结果可作为测试用例生成的输入，不回写到需求文档 |
| PRD 00-05（知识库） | 知识检索的"最终需求来源"读取 `source_document_versions` 中 `current_version_id` 对应版本 |
| PRD 00-21（测试计划） | 测试点生成以"当前最终需求"为输入；测试用例集通过 `requirement_doc_id` 关联需求文档 |
| PRD 00-22（全局知识库） | 本 PRD 上传路径为项目级需求文档；全局知识库为独立路径 |
