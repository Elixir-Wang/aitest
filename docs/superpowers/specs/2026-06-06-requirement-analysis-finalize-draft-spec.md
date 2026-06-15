# 初步需求转最终需求 Spec

## 背景

`2026-06-06-requirement-analysis-primary-draft-spec.md` 已经把需求分析定义为：

```text
主需求 = 分析对象和范围边界
辅助文档 = 证据库
需求分析 = 找问题、查证据、补初步需求、输出待确认
初步需求 != 最终需求
```

但当前实现仍存在一个关键歧义：后端在需求分析完成后把 `preliminary_requirement_markdown` 直接写入 `source_document_versions`，并更新 `source_documents.current_version_id`。这会让用户没有确认动作就把“初步需求”误认为“最终需求”。

本 spec 修正该链路：需求分析只产出初步需求；用户在 `需求分析 / 初步需求` 页面右上角点击 `转为最终需求` 后，系统才把初步需求写入最终需求版本，并进入 `最终需求` tab 查看。

## 目标

- 在 `需求分析 / 初步需求` 页面右上角提供 `转为最终需求` 按钮。
- 点击按钮后，将当前初步需求转为最终需求版本。
- 转换成功后自动进入 `最终需求` tab，并展示刚生成的最终需求内容。
- 在 `最终需求` 后提供 `版本记录` tab，用于查看每次最终需求变更。
- 需求分析完成时不再自动更新 `source_documents.current_version_id`。
- 最终需求仍复用现有 `source_document_versions` 和 `current_version_id` 机制。
- 后端提供明确的 finalize 契约，避免前端直接拼装 Markdown 调通用编辑接口。
- 对存在待确认问题、阻塞状态、主需求切换后的过期分析给出明确处理规则。

## 非目标

- 不实现待确认问题的人工答复和回填流程。
- 不实现初步需求在线编辑器；初步需求只展示分析结果。
- 不改变需求分析智能体的 prompt、技能加载、补证规则。
- 不重建需求归并智能体。
- 不把辅助文档全量合并进最终需求。
- 不删除历史 `最终需求` tab。

## 术语

| 名称 | 含义 |
| --- | --- |
| 标准文件 | 原始文件转换后的 Markdown 文件，位于 `source_document_file_mappings.markdown_file_path` |
| 主需求 | 当前 `file_role = primary` 的标准文件 |
| 初步需求 | `requirement_analyses.output_json.preliminary_requirement_markdown` |
| 最终需求 | `source_documents.current_version_id` 指向的 `source_document_versions` 内容 |
| finalize | 将某次需求分析产出的初步需求写入最终需求版本 |

## 核心原则

```text
需求分析不写最终需求
初步需求由 requirement_analyses 保存
最终需求由 source_document_versions 保存
current_version_id 只在 finalize 成功后更新
```

`2026-06-06-requirement-analysis-primary-draft-spec.md` 中关于“分析完成后写入 source_document_versions 并更新 current_version_id”的描述，以本 spec 为准。

## 用户流程

```text
1. 用户进入需求详情页
2. 用户在标准文件 tab 选择或确认主需求文件
3. 用户点击“需求分析”
4. 后端生成 requirement_analysis_run
5. 智能体分析完成后生成 requirement_analyses
6. 前端进入“需求分析 / 初步需求”
7. 用户检查初步需求和待确认问题
8. 用户点击右上角“转为最终需求”
9. 后端创建最终需求版本并更新 current_version_id
10. 前端刷新 overview，并进入“最终需求” tab
```

## 页面结构

需求详情页一级 tab：

```text
概览
原始文件
标准文件
需求分析
最终需求
版本记录
```

`需求分析` 下的二级 tab：

```text
初步需求
待确认问题
```

### 初步需求页面

页面主体展示：

- `analysis.output.preliminary_requirement_markdown`
- 最近一次分析摘要
- 辅助补强数量
- 待确认问题数量
- 质量状态

页面右上角按钮：

```text
转为最终需求
```

按钮显示规则：

| 状态 | 按钮行为 |
| --- | --- |
| 未执行需求分析 | 不显示或禁用，提示 `尚未生成初步需求` |
| 分析运行中 | 禁用，提示 `需求分析中` |
| 初步需求为空 | 禁用，提示 `初步需求为空` |
| `quality_gate.result = blocked` 或 `status = blocked` | 禁用，提示 `存在阻塞问题，不能转为最终需求` |
| 存在待确认问题 | 可点击，但必须二次确认 |
| 已转为最终需求 | 显示 `已转为最终需求`，禁用，旁边可提供 `查看最终需求` |
| 主需求文件已切换导致分析过期 | 禁用，提示 `主需求已变更，请重新分析` |

二次确认文案：

```text
当前初步需求仍存在待确认问题。转为最终需求后会生成新的最终需求版本，后续可继续通过版本记录追溯。是否继续？
```

成功提示：

```text
已转为最终需求
```

成功后行为：

```tsx
await loadOverview({ silent: true });
setActiveTab("final");
```

### 最终需求页面

`最终需求` tab 只展示 `overview.initial_markdown_content`，也就是当前 `source_documents.current_version_id` 指向的版本内容。

如果仅完成了需求分析但尚未 finalize，`最终需求` tab 仍应保持空态：

```text
尚未生成最终需求，请先在初步需求中点击“转为最终需求”。
```

### 版本记录页面

`版本记录` tab 放在 `最终需求` tab 后面，展示当前需求文档的最终需求版本历史。列表只保留对用户有区分度的信息，来源动作固定为 `需求分析转为最终需求`，不在列表中单独占列。

数据来源复用现有接口：

```http
GET /api/v1/projects/{project_id}/requirements/{document_id}/versions
GET /api/v1/projects/{project_id}/requirements/{document_id}/versions/{version_id}
PUT /api/v1/projects/{project_id}/requirements/{document_id}/versions/{version_id}/current
```

表格字段：

| 字段 | 含义 |
| --- | --- |
| 版本 | `source_document_versions.version_no` |
| 摘要 | 优先展示 `source_document_versions.diff_summary`，为空时展示 `change_summary` |
| 创建时间 | `source_document_versions.created_at` |
| 操作 | 小眼睛按钮，点击查看版本详情 |

记录规则：

- 每次 `finalize` 成功创建最终需求版本后，必须刷新版本记录。
- 每个最终需求版本必须独立存储版本内容；当前实现复用 `source_document_versions.file_path` 指向 `versions/v{version_no}.md`。
- 切换版本只更新 `source_documents.current_version_id`，不复制、不覆盖历史版本文件。
- 后续如果提供“编辑最终需求”能力，每次保存也必须创建新的 `source_document_versions` 记录，并更新 `source_documents.current_version_id`。
- 需求分析草稿、待确认问题答复、标准文件修改不直接写入版本记录；只有最终需求内容实际更新时才新增版本。
- 版本详情弹窗参考日志详情弹窗样式，展示版本、来源动作、摘要、创建时间和该版本最终需求预览。
- 版本详情弹窗提供 `切换为当前版本` 操作；当前生效版本禁用切换按钮并显示当前状态。
- 版本记录为空时显示 `尚未生成最终需求版本。`

## 后端接口

### 运行需求分析

保留现有接口：

```http
POST /api/v1/projects/{project_id}/requirements/{document_id}/review
GET  /api/v1/projects/{project_id}/requirements/{document_id}/analysis
```

语义调整：

- `/review` 只创建并执行需求分析任务。
- 需求分析完成后只写 `requirement_analyses`。
- 不创建最终需求版本。
- 不更新 `source_documents.current_version_id`。

### 转为最终需求

新增接口：

```http
POST /api/v1/projects/{project_id}/requirements/{document_id}/analysis/finalize
```

请求体：

```json
{
  "analysis_id": "reqana-xxx",
  "confirm_unresolved": false
}
```

字段说明：

| 字段 | 必填 | 含义 |
| --- | --- | --- |
| `analysis_id` | 是 | 要转为最终需求的分析 ID |
| `confirm_unresolved` | 否 | 存在待确认问题时，用户是否已二次确认 |

成功响应：

```json
{
  "analysis": {
    "id": "reqana-xxx",
    "status": "completed",
    "finalized_version_id": "docver-xxx",
    "finalized_at": "2026-06-06T10:00:00",
    "finalized_by": "u-admin"
  },
  "version": {
    "id": "docver-xxx",
    "document_id": "doc-xxx",
    "version_no": 3,
    "source_action": "requirement_analysis_finalize",
    "change_summary": "初步需求转为最终需求",
    "created_by": "u-admin",
    "created_at": "2026-06-06T10:00:00"
  },
  "document": {
    "id": "doc-xxx",
    "current_version_id": "docver-xxx"
  },
  "markdown_content": "# 最终需求..."
}
```

错误响应规则：

| 场景 | HTTP | code | message |
| --- | --- | --- | --- |
| 文档不存在 | 404 | `DOCUMENT_NOT_FOUND` | `需求文档不存在。` |
| 分析不存在 | 404 | `REQUIREMENT_ANALYSIS_NOT_FOUND` | `需求分析结果不存在。` |
| 分析不属于该文档 | 404 | `REQUIREMENT_ANALYSIS_NOT_FOUND` | `需求分析结果不存在。` |
| 分析不是最新结果 | 409 | `REQUIREMENT_ANALYSIS_STALE` | `该需求分析不是最新结果，请刷新后重试。` |
| 主需求文件已切换 | 409 | `REQUIREMENT_ANALYSIS_PRIMARY_CHANGED` | `主需求文件已变更，请重新执行需求分析。` |
| 初步需求为空 | 409 | `REQUIREMENT_ANALYSIS_EMPTY_DRAFT` | `初步需求为空，不能转为最终需求。` |
| 存在阻塞问题 | 409 | `REQUIREMENT_ANALYSIS_BLOCKED` | `存在阻塞问题，不能转为最终需求。` |
| 需要二次确认 | 409 | `REQUIREMENT_ANALYSIS_CONFIRM_REQUIRED` | `当前初步需求仍存在待确认问题，请确认后再转为最终需求。` |

## 数据模型

### requirement_analyses

当前表中 `version_id` 为非空外键，这会迫使需求分析必须先创建版本。为了让“初步需求 != 最终需求”成立，需要调整该约束。

推荐调整：

```sql
-- version_id 允许为空，用于兼容旧数据和旧接口。
-- 新需求分析结果在 finalize 前不需要关联 source_document_versions。

ALTER TABLE requirement_analyses ADD COLUMN primary_mapping_id TEXT;
ALTER TABLE requirement_analyses ADD COLUMN draft_content_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE requirement_analyses ADD COLUMN finalized_version_id TEXT;
ALTER TABLE requirement_analyses ADD COLUMN finalized_at TEXT;
ALTER TABLE requirement_analyses ADD COLUMN finalized_by TEXT;
```

SQLite 不能直接移除 `version_id NOT NULL` 约束。实现时需要检测表结构；如果 `version_id` 仍为 `NOT NULL`，通过重建表迁移：

```text
1. 创建 requirement_analyses_new，version_id 允许 NULL
2. 拷贝旧数据
3. 删除旧表
4. 重命名新表
5. 重建索引和外键
```

新字段说明：

| 字段 | 含义 |
| --- | --- |
| `primary_mapping_id` | 本次分析使用的主需求文件 ID，用于识别主需求切换后的过期分析 |
| `draft_content_hash` | 初步需求内容 hash，用于 finalize 幂等 |
| `finalized_version_id` | 已生成的最终需求版本 ID |
| `finalized_at` | 转为最终需求时间 |
| `finalized_by` | 执行转换的用户 ID |

### source_document_versions

仅在 finalize 成功时新增版本。

推荐字段值：

| 字段 | 值 |
| --- | --- |
| `source_action` | `requirement_analysis_finalize` |
| `change_summary` | `初步需求转为最终需求` |
| `diff_summary` | `由需求分析结果生成最终需求。辅助补强 {n} 项，待确认 {m} 项。` |
| `markdown_content` | 保持空字符串，沿用现有文件读取模式 |
| `file_path` | `projects/{project_id}/requirements/{document_id}/versions/v{version_no}.md` |

### document_version_change_logs

finalize 成功后写入版本变更日志。

推荐字段值：

| 字段 | 值 |
| --- | --- |
| `source_action` | `requirement_analysis_finalize` |
| `change_summary` | `初步需求转为最终需求` |
| `diff_summary` | 与版本记录一致 |
| `source_mapping_ids` | `[primary_mapping_id]` |

## 后端流程

### 需求分析完成

```text
review_primary_requirement_file
  -> 读取主需求标准 Markdown
  -> 收集辅助标准 Markdown
  -> 调用 requirement_analysis agent
  -> 校验 preliminary_requirement_markdown 非空
  -> 计算 draft_content_hash
  -> 创建 requirement_analyses
  -> 如果存在 run，则 attach_analysis
  -> 不创建 source_document_versions
  -> 不更新 source_documents.current_version_id
```

### 转为最终需求

```text
finalize_requirement_analysis
  -> 校验 document 存在
  -> 查询 analysis
  -> 校验 analysis 属于 document/project
  -> 校验 analysis 是该 document 最新 analysis
  -> 校验当前 primary_mapping_id 与 analysis.primary_mapping_id 一致
  -> 解析 output_json.preliminary_requirement_markdown
  -> 校验 status / quality_gate / unresolved
  -> 如果需要确认且 confirm_unresolved=false，返回 409
  -> 如果已 finalized 且 hash 一致，返回已有 version
  -> 创建 source_document_versions
  -> 写入 versions/v{version_no}.md
  -> 更新 source_documents.current_version_id
  -> 更新 requirement_analyses.finalized_*
  -> 写 document_version_change_logs
  -> 写 operation_logs
  -> 返回 version、document、analysis、markdown_content
```

### 幂等规则

同一个 `analysis_id` 多次点击 `转为最终需求`：

- 如果 `finalized_version_id` 已存在，且 `draft_content_hash` 与当前 output_json 中的初步需求内容 hash 一致：
  - 不创建新版本。
  - 返回已存在的 `finalized_version_id`。
- 如果 `finalized_version_id` 已存在，但 hash 不一致：
  - 返回 409 `REQUIREMENT_ANALYSIS_DRAFT_CHANGED`。
  - 正常情况下不应出现，说明分析结果被异常修改。

## 前端状态

新增或扩展类型：

```ts
type RequirementAnalysisResult = {
  id: string;
  document_id: string;
  status: "completed" | "needs_clarification" | "blocked";
  finalized_version_id: string | null;
  finalized_at: string | null;
  finalized_by: string | null;
  output: {
    preliminary_requirement_markdown: string;
    applied_supplements: Array<unknown>;
    clarification_questions: Array<unknown>;
    conflicts: Array<unknown>;
    quality_gate: {
      result: "passed" | "warning" | "blocked";
      testability_score: number;
      blocking_issues: string[];
      warning_issues: string[];
    };
  };
};
```

新增状态：

```ts
const [finalizingRequirement, setFinalizingRequirement] = useState(false);
const [finalizeConfirmOpen, setFinalizeConfirmOpen] = useState(false);
```

推荐派生状态：

```ts
const preliminaryMarkdown = analysisResult?.output.preliminary_requirement_markdown ?? "";
const unresolvedCount =
  (analysisResult?.output.clarification_questions.length ?? 0) +
  (analysisResult?.output.conflicts.length ?? 0);
const hasQualityWarning = analysisResult?.output.quality_gate.result === "warning";
const isBlocked =
  analysisResult?.status === "blocked" ||
  analysisResult?.output.quality_gate.result === "blocked";
const isFinalized = Boolean(analysisResult?.finalized_version_id);
```

## 前端交互

### 点击转为最终需求

```ts
async function finalizePreliminaryRequirement(confirmUnresolved = false) {
  if (!analysisResult) return;
  setFinalizingRequirement(true);
  try {
    const result = await apiRequest(
      `/projects/${projectId}/requirements/${documentId}/analysis/finalize`,
      {
        method: "POST",
        body: JSON.stringify({
          analysis_id: analysisResult.id,
          confirm_unresolved: confirmUnresolved,
        }),
      },
    );
    setAnalysisResult(result.analysis);
    toast.success("已转为最终需求");
    await loadOverview({ silent: true });
    setActiveTab("final");
  } catch (requestError) {
    if (isConfirmRequired(requestError)) {
      setFinalizeConfirmOpen(true);
      return;
    }
    toast.error(requestError instanceof Error ? requestError.message : "转为最终需求失败");
  } finally {
    setFinalizingRequirement(false);
  }
}
```

### 确认弹窗

当后端返回 `REQUIREMENT_ANALYSIS_CONFIRM_REQUIRED` 时打开确认弹窗。用户确认后再次调用：

```ts
void finalizePreliminaryRequirement(true);
```

## 文案

| 场景 | 文案 |
| --- | --- |
| 按钮默认 | `转为最终需求` |
| 按钮 loading | `转换中` |
| 已 finalized | `已转为最终需求` |
| 成功 toast | `已转为最终需求` |
| 失败 toast | `转为最终需求失败` |
| 空最终需求 | `尚未生成最终需求，请先在初步需求中点击“转为最终需求”。` |
| 阻塞禁用提示 | `存在阻塞问题，不能转为最终需求` |
| 主需求变更提示 | `主需求已变更，请重新分析` |

## 权限

推荐权限：

- 发起需求分析：`current_user`
- 转为最终需求：`current_user`

理由：

- 需求分析产物来自系统生成，finalize 是同一分析流程的显式确认动作。
- 如果沿用 `PUT /requirements/{document_id}` 的 `require_admin`，普通用户可以分析但不能完成流程，会造成能力断层。

如果产品要求只有管理员能发布最终需求，则后端应使用 `require_admin`，前端在按钮处根据用户角色禁用并提示：

```text
仅管理员可转为最终需求
```

本 spec 默认采用 `current_user`，后续由权限设计统一收敛。

## 与现有接口的关系

不建议前端用现有 `PUT /projects/{project_id}/requirements/{document_id}` 实现该按钮，原因：

- 该接口语义是人工编辑需求，不是分析结果 finalize。
- 该接口需要前端提交 Markdown，容易绕过后端对 `analysis_id`、主需求变更、质量状态和幂等的校验。
- 该接口无法自然记录 `requirement_analyses.finalized_version_id`。

finalize 接口内部可以复用现有 repository：

- `document_repo.next_version_no`
- `document_repo.create_version`
- `document_repo.update_current_version`
- `document_repo.create_document_version_change_log`

## 验收标准

### 后端

- 需求分析完成后，不创建新的 `source_document_versions`。
- 需求分析完成后，不更新 `source_documents.current_version_id`。
- `GET /analysis` 返回最新 analysis，并包含 `finalized_version_id`。
- 初步需求为空时，finalize 返回 409。
- `status = blocked` 或 `quality_gate.result = blocked` 时，finalize 返回 409。
- 存在待确认问题且 `confirm_unresolved=false` 时，finalize 返回 409。
- 仅存在质量 warning 且无待确认问题时，finalize 直接成功。
- `confirm_unresolved=true` 时可继续创建最终版本。
- finalize 成功后创建 `source_document_versions`。
- finalize 成功后更新 `source_documents.current_version_id`。
- finalize 成功后更新 `requirement_analyses.finalized_version_id`。
- 同一个 analysis 重复 finalize 不创建重复版本。
- 主需求文件切换后，旧 analysis 不能 finalize。

### 前端

- `需求分析` tab 下显示 `初步需求 / 待确认问题`。
- 初步需求右上角显示 `转为最终需求` 按钮。
- 没有初步需求时按钮禁用或不显示。
- 阻塞状态下按钮禁用。
- 存在待确认问题时点击按钮会出现二次确认。
- 转换成功后 toast 显示 `已转为最终需求`。
- 转换成功后自动进入 `最终需求` tab。
- `最终需求` tab 展示刚生成的最终需求 Markdown。
- 尚未 finalize 时，`最终需求` tab 不展示初步需求内容。

## 测试计划

### 后端测试

新增或修改：

```text
apps/backend/tests/test_requirement_primary_file_service.py
apps/backend/tests/test_requirement_analysis_finalize.py
```

测试用例：

1. `test_review_generates_analysis_without_final_version`
   - 上传主需求和辅助文件。
   - mock 智能体返回初步需求。
   - 执行 review 核心逻辑。
   - 断言 `current_version_id is None`。
   - 断言 latest analysis 存在。

2. `test_finalize_analysis_creates_current_final_version`
   - 构造未 finalized 的 analysis。
   - 调用 finalize。
   - 断言创建版本。
   - 断言 `current_version_id` 指向新版本。
   - 断言最终 Markdown 内容等于初步需求。

3. `test_finalize_requires_confirm_when_unresolved_exists`
   - analysis 中包含 clarification question。
   - `confirm_unresolved=false` 返回 409。
   - `confirm_unresolved=true` 成功。

4. `test_finalize_blocks_blocked_analysis`
   - `status=blocked` 或 `quality_gate.result=blocked`。
   - finalize 返回 409。

5. `test_finalize_is_idempotent`
   - 同一个 analysis 连续 finalize 两次。
   - 断言版本数量只增加一次。
   - 两次返回相同 `finalized_version_id`。

6. `test_finalize_rejects_primary_changed_analysis`
   - 分析后切换主需求文件。
   - finalize 返回 409。

### 前端测试

新增或修改：

```text
apps/frontend/tests/requirement-detail-analysis-contract.test.mjs
```

测试点：

- 页面源码包含 `转为最终需求`。
- 页面源码包含 `/analysis/finalize`。
- 成功后执行 `setActiveTab("final")`。
- 仍保留 `初步需求` 和 `待确认问题`。
- 不再把 `queryTab === "initial"` 路由到 `final`。

## 实施顺序

1. 调整 `requirement_analyses` schema 和初始化迁移。
2. 调整 repository，使 analysis 可以在 `version_id = NULL` 时创建。
3. 调整 review 核心逻辑，停止自动创建最终版本。
4. 新增 finalize service 方法。
5. 新增 `POST /analysis/finalize` API。
6. 补后端测试。
7. 调整前端 `RequirementAnalysisResult` 类型。
8. 在 `初步需求` 页面增加按钮和确认弹窗。
9. 成功后刷新 overview 并跳转 `最终需求` tab。
10. 补前端契约测试。

## 风险与处理

### 风险：旧数据依赖 `requirement_analyses.version_id`

处理：

- 保留字段但允许为空。
- 旧数据继续返回旧 `version_id`。
- 新数据在 finalize 前 `version_id = NULL`。
- 新数据 finalize 后使用 `finalized_version_id` 表示最终版本。

### 风险：用户把有待确认问题的初步需求转为最终需求

处理：

- 阻塞问题禁止转换。
- 非阻塞待确认问题允许转换，但必须二次确认。
- 版本日志记录待确认数量。

### 风险：主需求切换后旧初步需求被发布

处理：

- analysis 保存 `primary_mapping_id`。
- finalize 前比较当前主需求文件 ID。
- 不一致则返回 `REQUIREMENT_ANALYSIS_PRIMARY_CHANGED`。

### 风险：重复点击生成多个最终版本

处理：

- analysis 保存 `finalized_version_id` 和 `draft_content_hash`。
- finalize 使用幂等逻辑。

## Done 定义

- 需求分析产物和最终需求版本写入彻底解耦。
- 用户必须点击 `转为最终需求` 才会更新 `current_version_id`。
- `最终需求` tab 只展示已 finalize 的版本。
- 所有新增失败场景都有明确错误码和前端文案。
- 后端和前端契约测试覆盖核心流程。
