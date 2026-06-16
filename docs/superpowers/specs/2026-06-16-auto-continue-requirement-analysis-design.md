# 需求标准化自动衔接分析与进度指示 Spec

## 背景

当前新建需求的处理链路为：

```text
上传文件 → 后台标准化 → [用户手动点击「需求分析」] → 需求分析 → [用户手动「转为最终需求」] → 最终需求
```

需求详情页顶部已有 `需求处理进度` 四步指示器（`RequirementProgressSteps`），每步支持三种视觉状态：

| 状态 | 视觉 |
| --- | --- |
| `upcoming` | 灰色圆点 |
| `running` | 主色圆环 + `Loader2` 转圈 |
| `completed` | 绿色圆环 + 勾选 |

但存在两个缺口：

1. **流程断层**：标准化完成后不会自动进入需求分析，用户必须回到页面手动点击。
2. **进度与任务不同步**：自动衔接后，顶部第 3 步「需求分析」应随后台 `requirement_analysis_run` 进入 `running`，而不依赖用户是否点击过按钮；第 2 步完成后应无缝切换到第 3 步转圈。

本 spec 定义：**新建需求首次流水线**在标准化成功后由后端自动启动需求分析，并保证页面顶部四步进度条与真实任务生命周期一一对应、逐步转圈、逐步完成。

## 目标

- 新建需求（`mode=new`）上传后，主需求文件标准化成功时，自动创建并执行 `requirement_analysis_run`。
- 用户无需手动点击「需求分析」即可进入分析阶段（仍可在分析中停止）。
- 页面顶部四步进度条与后台任务状态实时对齐：当前步骤显示转圈，已完成步骤显示勾选，未开始步骤显示灰点。
- 标准化完成 → 需求分析启动时，进度条从「标准需求」running 过渡到「标准需求」completed +「需求分析」running，无需用户刷新。
- 自动衔接失败不阻断标准化成功结果，仅记日志；用户仍可手动发起分析。
- 与 `2026-06-06-requirement-analysis-task-lifecycle-spec.md` 任务生命周期、顶部任务指示器（`2026-06-04-realtime-task-indicator-design.md`）保持一致。

## 非目标

- 不为追加文件（`mode=append`）、手动重转、换主需求后自动重分析。
- 不自动执行「转为最终需求」；第 4 步仍须用户确认（见 `2026-06-06-requirement-analysis-finalize-draft-spec.md`）。
- 不在 v1 增加「是否自动分析」UI 开关。
- 不改变需求分析智能体逻辑、输出结构或 finalize 契约。
- 不重建需求归并智能体。

## 术语

| 名称 | 含义 |
| --- | --- |
| 流水线 | 单次新建需求从上传到最终需求的四步处理过程 |
| 自动衔接 | 标准化成功后后端链式启动需求分析 |
| 进度步 | 顶部 `RequirementProgressSteps` 中的四个节点 |
| 任务转圈 | 进度步 `status=running` 时圆环内 `Loader2` 动画 |

## 核心原则

```text
业务编排放后端（upload → convert → analyze 链式后台任务）
进度展示放前端（读 overview + run 状态驱动四步指示器）
顶部任务指示器与进度步共用同一任务数据源
自动衔接 = 首次新建流水线特权，其余场景保持手动
```

## 四步进度与任务映射

页面最上方 `需求处理进度` 区域，每一步的 `running` 转圈必须绑定明确数据源，不得仅靠本地瞬时 state。

### 步骤 1：原始需求

| 字段 | 值 |
| --- | --- |
| `id` | `raw` |
| `title` | 原始需求 |
| `running` 条件 | `uploadSubmitting === true`（详情页内追加/重传文件时） |
| `completed` 条件 | `overview.stats.total_files > 0` 且不在上传中 |
| `upcoming` 条件 | 尚无文件且未在上传 |

任务关联：上传成功时 `notifyAiTaskStarted()` 触发顶部任务指示器展示 `requirement_file` 转换任务（已有）。

### 步骤 2：标准需求

| 字段 | 值 |
| --- | --- |
| `id` | `standard` |
| `title` | 标准需求 |
| `running` 条件 | 任一文件 `conversion_status ∈ {pending, processing}` |
| `completed` 条件 | `stats.conversion_success + stats.conversion_warning > 0` 且无运行中转换 |
| `upcoming` 条件 | 有文件但尚无成功/警告转换，且无运行中转换 |

任务关联：`requirement_file` 任务（`task_service` 聚合 `source_document_file_mappings` 转换状态）。

轮询：当 `hasRunningConversions` 为 true 时，每 3 秒 silent 刷新 overview（已有，保持）。

### 步骤 3：需求分析

| 字段 | 值 |
| --- | --- |
| `id` | `review` |
| `title` | 需求分析 |
| `running` 条件 | `reviewLoading === true` **或** `latest_requirement_analysis_run.status ∈ REQUIREMENT_REVIEW_ACTIVE_STATUSES`（`queued`、`running`、`stopping`） |
| `completed` 条件 | 最新分析 `status ∈ {completed, needs_clarification}` 且非 blocked |
| `upcoming` 条件 | 无运行中分析且未完成分析 |

任务关联：`requirement_analysis_run` → 顶部任务指示器 `module=requirement`、`module_label=需求分析`。

**关键**：自动衔接创建 run 后，即使 `reviewLoading` 为 false（用户未点击按钮），也必须通过 `overview.document.latest_requirement_analysis_run` 将本步置为 `running`。

轮询：当 run 处于 active 状态时，按 `REQUIREMENT_REVIEW_POLL_INTERVAL_MS` 刷新 overview 与 analysis（已有，保持）。

### 步骤 4：最终需求

| 字段 | 值 |
| --- | --- |
| `id` | `final` |
| `title` | 最终需求 |
| `running` 条件 | `finalizingRequirement === true`（用户点击「转为最终需求」到 API 返回期间） |
| `completed` 条件 | `isFinalized && hasFinalRequirementContent` |
| `upcoming` 条件 | 分析未完成 finalize，或尚未点击转换 |

任务关联：finalize 为同步 API，无独立后台 run；`running` 仅由前端 `finalizingRequirement` 驱动。

### 进度步状态互斥规则

- 同一步骤同一时刻只有一个状态；优先级：`running` > `completed` > `upcoming`。
- 允许多步同时 `completed`（例如标准化与分析均已完成）。
- 仅允许一步 `running` 为常态；新建流水线自动衔接时，第 2 步与第 3 步可在极短窗口内交替（标准化刚结束、分析刚入队），最终应稳定为第 2 步 completed + 第 3 步 running。
- 转换失败时第 2 步保持 `upcoming` 或展示错误（不在本 spec 扩展失败态 UI，维持现状）。

### 视觉规范（沿用现有组件）

`RequirementStepMarker` 行为不变：

```text
completed → 绿色边框/背景 + Check 图标
running   → 主色边框/背景 + Loader2 animate-spin
upcoming  → 灰色边框 + 小圆点
```

步骤标题颜色随状态变化（completed 翠绿、running 主色、upcoming -muted）。

## 自动衔接：触发条件

`maybe_auto_start_requirement_analysis` 仅在**全部**满足时执行：

| # | 条件 | 说明 |
| --- | --- | --- |
| 1 | `auto_continue === true` | 仅上传 API `mode=new` 时传入 |
| 2 | 当前 mapping 为 `file_role=primary` | 辅助文件转换不触发 |
| 3 | `conversion_status ∈ {success, warning}` 且 `markdown_file_path` 非空 | 标准化成功 |
| 4 | 该 `document_id` 无任何 `requirement_analysis_runs` 记录 | 首次流水线 |
| 5 | 无 active analysis run | 防重复 |
| 6 | `source_documents.current_version_id` 为空 | 无已生效最终需求 |

不满足时静默跳过，标准化结果正常返回。

## 自动衔接：后端设计

### 入口改造

`POST /projects/{project_id}/requirements` 上传成功后：

```python
background_tasks.add_task(
    document_service.convert_pending_file_mappings,
    [item["id"] for item in result["files"]],
    dict(actor),
    auto_continue=(mode == "new"),
)
```

`convert_pending_file_mappings` 签名扩展：

```python
async def convert_pending_file_mappings(
    mapping_ids: list[str],
    actor: dict,
    *,
    auto_continue: bool = False,
) -> None:
    for mapping_id in mapping_ids:
        result = await convert_source_file_mapping(mapping_id)
        if auto_continue:
            await maybe_auto_start_requirement_analysis(
                mapping_id=mapping_id,
                conversion_result=result,
                actor=actor,
            )
```

手动重转 API `POST /requirement-files/{mapping_id}/convert` **不传** `auto_continue`，行为不变。

### `maybe_auto_start_requirement_analysis`

伪代码：

```python
async def maybe_auto_start_requirement_analysis(mapping_id, conversion_result, actor):
    if not _should_auto_continue(mapping_id, conversion_result):
        return
    try:
        task = start_requirement_review_run(project_id, document_id, actor)
        await execute_requirement_review_run(task["source_id"], actor)
    except Exception as exc:
        logger.warning("auto_continue_requirement_analysis_failed", ...)
```

- 复用现有 `start_requirement_review_run` + `execute_requirement_review_run`，与 `POST /review` 同路径。
- `actor` 使用上传时的用户，保证 `created_by`、操作日志、任务归属一致。
- 异常只记 warning，不抛出让转换失败。

### 任务与日志

自动衔接产生的 run 与手动点击无区别：

- `requirement_analysis_runs.status`: `queued` → `running` → 终态
- `operation_logs`: `submit_requirement_analysis`、`start_requirement_analysis` 等事件照常写入
- `task_service` 聚合后进入顶部任务指示器

## 自动衔接：前端设计

### 原则

前端**不**在标准化完成时主动 `POST /review`，避免与后端双触发。前端只响应 overview 中的 run 状态变化。

### 标准化完成检测

在 `hasRunningConversions` 从 `true` → `false` 且主需求 `conversion_status ∈ {success, warning}` 时：

1. silent 刷新 overview（已有轮询会覆盖，可加一次即时刷新确保低延迟）
2. 若 `latest_requirement_analysis_run.status ∈ {queued, running}`：
   - Toast：`标准文件已生成，正在自动开始需求分析`
   - `setActiveTab("analysis")` + `setAnalysisTab("analysis-report")`
3. 顶部第 2 步变 completed，第 3 步变 running（由 `requirementProgressSteps` 计算属性自动完成）

### 分析完成检测

保持现有逻辑：run 离开 active 状态且 `loadLatestAnalysis()` 有结果时，切到 `analysis` tab 并展示报告。

### 确认弹窗

自动衔接场景跳过 `setReviewClearConfirmOpen`：仅当用户**主动点击**「需求分析」且存在需清空的最终需求/分析结果时才弹窗。自动启动不经过 `reviewPrimaryRequirement()`。

### 顶部任务指示器

自动衔接创建 run 后，通过已有 SSE / `notifyAiTaskStarted` 机制展示「需求分析」运行中任务。若 run 由纯后端创建、前端未调用 start 端点，则依赖：

- overview 轮询发现 active run 后，可选调用 `running-task-store.upsertTask` 补齐乐观状态；或
- 依赖 `/tasks/stream` 服务端事件（`task_service` 在 run 创建时发布事件，若尚未发布则本 spec 要求补齐）。

**本 spec 要求**：`start_requirement_review_run` 成功创建 run 后，必须触发与手动 `POST /review` 相同的任务事件发布，确保顶部全局任务指示器与页面内第 3 步转圈同时出现。

## 用户流程（新建需求）

```text
1. 用户在项目内新建需求并上传主需求文件
2. 跳转需求详情页 ?tab=source-files
3. 顶部进度：第 1 步 completed，第 2 步 running（转圈）
4. 后台标准化完成 → 自动创建 requirement_analysis_run
5. 顶部进度：第 2 步 completed，第 3 步 running（转圈）
6. 页面自动切到「需求分析」tab（可选 Toast 提示）
7. 分析完成 → 第 3 步 completed，展示初步需求/分析报告
8. 用户点击「转为最终需求」→ 第 4 步 running（转圈）
9. finalize 成功 → 第 4 步 completed，进入「最终需求」tab
```

## 与相关 Spec 的关系

| Spec | 关系 |
| --- | --- |
| `2026-06-06-requirement-analysis-task-lifecycle-spec.md` | 自动衔接复用 `requirement_analysis_runs` 生命周期 |
| `2026-06-06-requirement-analysis-finalize-draft-spec.md` | 第 4 步仍手动 finalize，不自动 |
| `2026-06-04-realtime-task-indicator-design.md` | 第 2、3 步对应任务须出现在顶部全局指示器 |
| `2026-05-22-requirement-overview-workflow-design.md` | 四步进度条结构沿用 |

## 错误处理

| 场景 | 行为 |
| --- | --- |
| 标准化失败 | 第 2 步不 completed；不自动分析；用户可重转或换文件 |
| 自动分析启动失败 | 记日志；第 2 步仍 completed；第 3 步 upcoming；用户可手动分析 |
| 分析 run 失败 | 第 3 步回 upcoming 或保持 completed 视产品定义（维持现有：无 completed 除非成功终态） |
| 用户离开页面 | 后台分析继续；回页后 overview 轮询恢复第 3 步 running/completed |

## 测试要点

### 后端

| 用例 | 期望 |
| --- | --- |
| `mode=new` 上传单文件，mock 标准化成功 | 自动创建一条 `requirement_analysis_run` |
| `mode=append` 追加文件 | 不自动创建 run |
| 手动 `POST /convert` 重转主需求 | 不自动创建 run |
| 已有 analysis run 记录后重转 | 不自动创建 run |
| 标准化成功但 `start_requirement_review_run` 抛错 | 转换结果仍为 success，无 run |
| 多文件上传，仅 primary 转换完成时检查 | 仅在 primary 成功且为最后一个触发条件时启动一次 |

### 前端

| 用例 | 期望 |
| --- | --- |
| 新建需求，标准化进行中 | 第 2 步转圈 |
| 标准化完成且 run 为 queued | 第 2 步勾选，第 3 步转圈 |
| 分析完成 | 第 3 步勾选 |
| 点击转为最终需求 | 第 4 步转圈，完成后勾选 |
| 用户未在页面上传、从列表进入已自动分析中的需求 | 第 3 步转圈（读 overview，不依赖 reviewLoading） |

## 实现文件（参考）

| 层级 | 文件 |
| --- | --- |
| 后端编排 | `apps/backend/app/services/document/file_service.py` |
| 后端服务门面 | `apps/backend/app/services/document/service.py` |
| 上传 API | `apps/backend/app/api/v1/requirements.py` |
| 前端进度与轮询 | `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx` |
| 测试 | `apps/backend/tests/test_requirement_primary_file_service.py`（新增 auto_continue 用例） |

## 验收标准

- [ ] 新建需求上传后，无需点击「需求分析」，标准化成功即自动进入分析队列。
- [ ] 页面顶部四步指示器在对应任务运行时均显示 `Loader2` 转圈。
- [ ] 自动衔接时第 2→3 步过渡无需手动刷新。
- [ ] 追加文件、手动重转不触发自动分析。
- [ ] 顶部全局任务指示器在自动分析启动后可见「需求分析」任务。
- [ ] 自动衔接失败时标准化结果不受影响，可手动补救。
