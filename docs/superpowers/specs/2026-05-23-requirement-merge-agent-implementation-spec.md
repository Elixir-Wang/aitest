# 需求归并智能体实现规范

## 目标

将当前需求概览中的确定性 Markdown 合并能力升级为“需求归并智能体”，支持多来源标准 Markdown 的业务归并、冲突识别、来源覆盖、增量维护和版本变更日志。

本规范只定义功能实现边界、数据契约、服务职责、Agent 行为和验收标准。具体逐步编码任务应另行拆分到 `docs/superpowers/plans/`。

## 背景依据

- PRD 已明确：上传文件先转换为独立标准 Markdown，用户手动触发归并后才生成需求工作稿版本。
- PRD 已明确：新增需求材料归并必须先生成差异预览，由用户确认后才写入新版本。
- PRD 已明确：需求文档版本变化日志是知识库增量更新的触发输入。
- 现有 `apps/backend/app/services/document_service.py` 已提供 `/merge`、`/conflicts` 和基础版本写入能力，但当前实现是简单去重拼接，不具备业务模块归并、覆盖矩阵、结构化冲突和增量差异维护能力。
- 现有 `source_document_merge_conflicts` 表已承担初始冲突处理，但字段不足以表达冲突类型、来源引用、处理证据和 Agent 建议。

## 范围

本期包含：

- 新增 `RequirementMergeAgent` 作为需求归并的 Agent 边界。
- 将 `document_service.merge_document_markdown` 调整为编排服务，负责校验、读取文件、调用 Agent、保存结果。
- 支持初始合并：多个标准 Markdown 生成第一份需求工作稿版本。
- 支持增量合并：已有当前版本时，将待归并标准 Markdown 合并到当前版本，生成差异预览或新版本。
- 支持重复内容去重、同义内容归并、按业务模块重组。
- 支持结构化冲突识别、人工解决冲突、解决后重新合并。
- 支持来源引用和来源覆盖矩阵，证明每个来源片段被覆盖、废弃、待澄清或判定无需纳入。
- 支持版本变化日志，供知识库更新判断影响模块。

本期不包含：

- 文件上传和 DOCX/PDF 转 Markdown。
- 需求评审和澄清问答表单。
- 知识库生成或更新。
- 测试用例生成。
- 自动修改已发布知识库。
- 向量检索或外部知识库。

## 现有实现边界

当前后端已有接口应保留：

```text
POST /projects/{project_id}/requirements/{document_id}/merge
GET /projects/{project_id}/requirements/{document_id}/conflicts
PUT /projects/{project_id}/requirements/{document_id}/conflicts/{conflict_id}
```

这些接口的路径不改。允许扩展返回字段，但不得删除已有字段：

- `status`
- `version_id`
- `version_no`
- `markdown_content`
- `merge_summary`
- `source_file_ids`
- `conflict_count`
- `conflicts`

现有 `document_service.merge_document_markdown` 后续只做编排，不再承载合并算法本身。

## 核心对象

### RequirementMergeAgent

新增 Agent：

```text
RequirementMergeAgent
```

职责：

- 读取当前需求下所有可参与合并的标准 Markdown。
- 读取当前工作稿版本，作为增量合并基线。
- 读取已解决冲突，将解决结果作为强约束。
- 识别重复、补充、覆盖、废弃、冲突和待澄清内容。
- 输出业务模块化需求 Markdown。
- 输出合并摘要、差异摘要、影响模块、来源覆盖矩阵和冲突清单。

不负责：

- 不读取原始 Word/PDF 二进制文件。
- 不生成知识库。
- 不生成测试用例。
- 不绕过用户确认写入冲突内容。
- 不把待澄清假设伪装为已确认需求。

### RequirementMergeRun

建议新增表 `requirement_merge_runs`。

| 字段 | 说明 |
| --- | --- |
| id | 合并运行 ID |
| project_id | 项目 ID |
| document_id | 需求 ID |
| base_version_id | 合并基线版本，初始合并时可为空 |
| output_version_id | 合并成功后生成的版本 ID，冲突或预览时为空 |
| merge_mode | `initial`、`incremental`、`rebuild` |
| status | `running`、`preview`、`conflict`、`merged`、`failed`、`cancelled` |
| input_mapping_ids | 输入来源文件 ID JSON |
| resolved_conflict_ids | 已采纳冲突处理 ID JSON |
| merge_summary | 合并摘要 |
| diff_summary | 差异摘要 |
| affected_modules | 影响模块 JSON |
| output_preview_path | 差异预览 Markdown 路径 |
| created_by | 创建人 |
| created_at | 创建时间 |
| finished_at | 完成时间 |

### RequirementMergeConflict

现有 `source_document_merge_conflicts` 可继续使用，但建议扩展字段。

| 字段 | 说明 |
| --- | --- |
| id | 冲突 ID |
| run_id | 关联合并运行，可为空以兼容旧数据 |
| document_id | 需求 ID |
| conflict_type | `contradiction`、`mutual_exclusion`、`scope_overlap`、`obsolete_rule` |
| severity | `high`、`medium`、`low` |
| title | 冲突标题 |
| source_refs | 来源引用 JSON |
| fragment_a | 冲突片段 A |
| fragment_b | 冲突片段 B |
| agent_suggestion | Agent 建议，仅作为建议 |
| resolution | 用户确认后的最终表述 |
| resolution_type | `keep_a`、`keep_b`、`manual`、`unified` |
| status | `open`、`resolved`、`ignored` |
| created_at | 创建时间 |
| updated_at | 更新时间 |

### RequirementSourceCoverageItem

建议新增表 `requirement_source_coverage_items`。

| 字段 | 说明 |
| --- | --- |
| id | 覆盖项 ID |
| run_id | 合并运行 ID |
| document_id | 需求 ID |
| version_id | 覆盖项所属输出版本 |
| mapping_id | 来源文件 ID |
| source_heading | 来源标题 |
| source_excerpt | 来源片段 |
| target_module | 归并到的模块 |
| target_heading | 归并到的工作稿标题 |
| coverage_status | `merged`、`duplicate`、`conflict`、`pending_clarification`、`not_testable`、`discarded` |
| reason | 处理原因 |

## 合并模式

### 初始合并

触发条件：

- `SourceDocument.current_version_id` 为空。
- 至少一个标准 Markdown 文件满足：
  - `conversion_status in ('success', 'warning')`
  - `mapping_status != 'discarded'`

输出：

- 无冲突时生成 `SourceDocumentVersion`。
- `source_action = 'merge'`。
- 所有参与来源文件标记为 `merged`，`version_id` 指向新版本。
- 写入覆盖矩阵和合并运行记录。

### 增量合并

触发条件：

- `SourceDocument.current_version_id` 不为空。
- 存在 `mapping_status = 'pending_merge'` 的可合并标准文件。

输出：

- 默认先生成差异预览，不直接覆盖当前版本。
- 差异预览包含新增、修改、废弃、冲突、待澄清和影响模块。
- 用户确认差异后，后端再生成新的 `SourceDocumentVersion`。

第一版可以暂时把“确认差异”并入 `/merge` 的二次调用，但接口返回必须能表达：

```json
{
  "status": "preview",
  "preview_id": "merge-run-xxx",
  "merge_summary": "发现 3 个新增点、2 个修改点。",
  "diff_summary": "影响登录、权限两个模块。",
  "affected_modules": ["登录认证", "权限管理"]
}
```

### 重建合并

触发条件：

- 管理员或系统任务要求基于全部标准文件重新生成工作稿。

规则：

- 不覆盖历史版本。
- 必须生成新版本。
- 必须记录重建原因。

## Agent 输入契约

```json
{
  "project_id": "project-xxx",
  "document_id": "doc-xxx",
  "document_name": "登录认证需求",
  "merge_mode": "initial",
  "base_version": {
    "id": "docver-001",
    "version_no": 1,
    "markdown_content": "# 登录认证需求..."
  },
  "source_files": [
    {
      "mapping_id": "docmap-001",
      "original_filename": "登录需求.docx",
      "markdown_content": "# 登录需求\n\n...",
      "conversion_status": "success",
      "mapping_status": "pending_merge"
    }
  ],
  "resolved_conflicts": [
    {
      "id": "conflict-001",
      "title": "登录失败锁定次数不一致",
      "resolution": "连续 5 次登录失败后锁定账号。",
      "resolution_type": "manual"
    }
  ],
  "merge_rules": {
    "preserve_source_references": true,
    "do_not_promote_pending_clarification_to_fact": true,
    "organize_by_business_module": true,
    "return_conflicts_before_version_write": true
  }
}
```

## Agent 输出契约

### 合并成功

```json
{
  "status": "merged",
  "markdown_content": "# 登录认证需求\n\n...",
  "merge_summary": "已合并 3 个标准文件，去重 12 处，新增 2 个模块。",
  "diff_summary": "新增登录锁定规则，补充验证码异常流程。",
  "affected_modules": ["登录认证", "账号安全"],
  "source_file_ids": ["docmap-001", "docmap-002"],
  "coverage_items": [
    {
      "mapping_id": "docmap-001",
      "source_heading": "登录失败处理",
      "source_excerpt": "连续 5 次失败后锁定账号。",
      "target_module": "登录认证",
      "target_heading": "登录失败锁定",
      "coverage_status": "merged",
      "reason": "作为登录失败处理规则写入工作稿。"
    }
  ],
  "change_log": {
    "added_modules": ["账号安全"],
    "updated_modules": ["登录认证"],
    "deprecated_items": [],
    "pending_clarifications": []
  }
}
```

### 发现冲突

```json
{
  "status": "conflict",
  "merge_summary": "发现 2 个来源冲突，未生成新版本。",
  "conflict_count": 2,
  "conflicts": [
    {
      "title": "登录失败锁定次数不一致",
      "conflict_type": "contradiction",
      "severity": "high",
      "source_refs": [
        {
          "mapping_id": "docmap-001",
          "filename": "登录需求.docx",
          "heading": "账号锁定"
        },
        {
          "mapping_id": "docmap-002",
          "filename": "安全补充.md",
          "heading": "登录安全"
        }
      ],
      "fragment_a": "连续 5 次失败后锁定账号。",
      "fragment_b": "连续 3 次失败后锁定账号。",
      "agent_suggestion": "两处规则互斥，需要用户确认最终锁定次数。"
    }
  ]
}
```

### 差异预览

```json
{
  "status": "preview",
  "preview_id": "merge-run-xxx",
  "markdown_preview": "# 登录认证需求\n\n...",
  "merge_summary": "新增 4 条需求，修改 2 条旧规则。",
  "diff_summary": "影响登录认证、权限管理。",
  "affected_modules": ["登录认证", "权限管理"],
  "source_file_ids": ["docmap-003"],
  "coverage_items": []
}
```

## Markdown 工作稿格式

合并后的需求工作稿必须按业务模块组织，禁止按文件简单拼接。

推荐结构：

```markdown
# {需求名称}

## 1. 范围

## 2. 业务角色

## 3. 业务模块

### 3.1 {模块名称}

#### 业务目标

#### 功能规则

#### 流程与状态

#### 字段与数据

#### 权限与约束

#### 异常与边界

#### 验收标准

#### 来源引用

## 4. 待澄清问题

## 5. 已废弃或不采纳内容
```

规则：

- 每个关键需求点必须有来源引用。
- 待澄清问题可以出现在工作稿中，但必须明确标记为待澄清，不能写成已确认规则。
- 已废弃内容必须说明废弃原因和来源。
- 同一业务规则出现多个来源时，应合并为一个规则，并在来源引用中列出多个来源。

## 冲突识别规则

必须识别为冲突：

- 同一业务条件下数值、阈值、次数、时间限制不一致。
- 同一角色权限互相矛盾。
- 同一流程状态流转互斥。
- 一个来源要求启用某能力，另一个来源明确禁止。
- 新增材料明确废弃旧规则，但旧规则仍在当前工作稿中。

不应识别为冲突：

- 一个来源比另一个来源更详细，但不矛盾。
- 两个来源描述不同模块。
- 表述不同但业务含义一致。
- 信息不完整但没有互斥关系，此类应进入待澄清。

## 服务编排规则

`document_service.merge_document_markdown` 应执行：

1. 校验项目和需求存在。
2. 查询可合并标准文件。
3. 查询当前版本作为 `base_version`。
4. 查询已解决冲突。
5. 创建 `RequirementMergeRun`，状态为 `running`。
6. 调用 `RequirementMergeAgent`。
7. 如果 Agent 返回 `conflict`：
   - 写入冲突表。
   - 合并运行状态置为 `conflict`。
   - 不创建 `SourceDocumentVersion`。
8. 如果 Agent 返回 `preview`：
   - 保存预览 Markdown。
   - 合并运行状态置为 `preview`。
   - 不创建 `SourceDocumentVersion`。
9. 如果 Agent 返回 `merged`：
   - 写入 `versions/vN.md`。
   - 创建 `SourceDocumentVersion`。
   - 创建 `DocumentVersionChangeLog`。
   - 写入覆盖矩阵。
   - 更新参与来源文件为 `merged`。
   - 更新 `SourceDocument.current_version_id`。
   - 合并运行状态置为 `merged`。

## 接口规范

### POST /projects/{project_id}/requirements/{document_id}/merge

请求：

```json
{
  "merge_mode": "initial",
  "confirm_preview_id": "",
  "force_rebuild": false
}
```

第一版可以继续无请求体调用，但服务内部必须按当前版本和待归并文件自动判断模式。

返回 `merged`、`conflict` 或 `preview`。

### GET /projects/{project_id}/requirements/{document_id}/conflicts

返回当前未解决冲突。后续可支持 `status` 查询参数。

### PUT /projects/{project_id}/requirements/{document_id}/conflicts/{conflict_id}

请求：

```json
{
  "resolution": "连续 5 次登录失败后锁定账号。",
  "resolution_type": "manual"
}
```

规则：

- `resolution` 不能为空。
- 只能解决当前需求下的冲突。
- 解决后不自动生成版本，用户需要重新触发合并。

### GET /projects/{project_id}/requirements/{document_id}/merge-runs/{run_id}

建议新增，用于查看合并运行、预览、覆盖矩阵和影响模块。

## 前端交互规则

需求概览页沿用既有 Tab：

```text
概览 / 原始文件 / 标准文件 / 初始需求
```

存在未解决冲突时显示：

```text
冲突处理
```

新增状态展示：

- 合并中
- 存在冲突
- 待确认差异
- 已生成初始需求
- 存在待归并来源

用户操作：

- 在“标准文件”Tab 点击合并。
- 合并返回 `conflict` 时切换到“冲突处理”Tab。
- 冲突解决后，用户再次点击合并。
- 合并返回 `preview` 时展示差异预览和影响模块，由用户确认后写入版本。
- 合并返回 `merged` 时刷新“初始需求”Tab。

## 验收标准

后端验收：

- 无标准文件时返回明确错误，不创建版本。
- 存在未解决冲突时返回 `status = conflict`，不创建版本。
- 解决冲突后重新合并可以生成版本。
- 初始合并成功后 `current_version_id` 指向新版本。
- 参与合并的 `source_document_file_mappings.version_id` 指向新版本。
- 增量合并不会原地覆盖旧版本。
- 每次成功合并写入版本变化日志。
- 每个输入来源片段都有覆盖状态。

Agent 验收：

- 不按文件简单拼接。
- 能识别重复内容并合并。
- 能识别互斥规则并阻断版本写入。
- 能把解决后的冲突作为强约束。
- 能将伪需求改写为可测试需求，同时保留来源引用。
- 不把待澄清内容伪装为已确认事实。

前端验收：

- 合并按钮只在存在可合并标准文件时可用。
- 冲突 Tab 只在存在未解决冲突时显示。
- 冲突解决后 Tab 可隐藏。
- 合并成功后初始需求内容刷新。
- 状态枚举显示中文，不直接暴露后端英文枚举。

## 测试要求

后端至少覆盖：

- `test_merge_without_files_returns_error`
- `test_initial_merge_creates_version_and_marks_files_merged`
- `test_merge_detects_conflict_without_creating_version`
- `test_resolved_conflict_is_used_as_merge_constraint`
- `test_incremental_merge_creates_new_version_not_overwrite_current`
- `test_merge_writes_source_coverage_items`
- `test_merge_writes_document_version_change_log`

前端至少覆盖或手工验证：

- 标准文件发起合并。
- 冲突返回后显示冲突处理。
- 冲突解决后可重新合并。
- 合并成功后初始需求 Tab 展示 Markdown。

## 实施顺序建议

1. 固化当前 `/merge` 和 `/conflicts` 接口测试，防止回归。
2. 新增 `RequirementMergeAgent` 输入输出 schema，不直接接入模型。
3. 将当前简单合并逻辑迁移到独立 `requirement_merge_service`，保留确定性 fallback。
4. 新增合并运行、覆盖矩阵、版本变化日志数据写入。
5. 接入 Agent 输出解析和校验。
6. 增量合并先返回 `preview`，确认后再写版本。
7. 前端补齐差异预览、覆盖矩阵和影响模块展示。

## 未决问题

- 增量合并的“确认差异”是否新增独立接口，还是复用 `/merge` 加 `confirm_preview_id`。
- `RequirementMergeAgent` 第一版是否真实调用模型，还是先以确定性规则服务作为可替换实现。
- 覆盖矩阵是否复用后续 `SourceCoverageItem`，还是为合并过程单独保留 `RequirementSourceCoverageItem`。
- 冲突表是否直接迁移扩展现有 `source_document_merge_conflicts`，还是新增通用 `source_conflict_items` 并兼容旧接口。
