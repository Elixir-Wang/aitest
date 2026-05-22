# 需求多来源文件上传改造设计

## 目标

将当前“每个上传文件创建一个需求并立即生成 v1”的实现，改为“一个需求实体可以包含多个来源文件；每个来源文件先独立保存和转换，用户确认归并后才生成正式工作稿版本”。

本期只解决多文件上传、追加文件、来源文件列表和转换稿预览的基础闭环；智能归并差异、模块归属建议、冲突识别和澄清分类作为后续独立改造。

## 背景依据

- PRD 已明确：新建需求模式下一次上传的多个文件统一归属到同一个 `SourceDocument`，需求名称必填且同项目唯一。
- PRD 已明确：追加文件只生成来源文件记录并进入待归并，不自动修改当前工作稿，也不触发知识库更新。
- 当前代码仍保留单文件假设：`source_documents.original_file_path`、`source_document_file_mappings.version_id NOT NULL`、上传即创建 `SourceDocumentVersion v1`。

## 范围

本期包含：

- 调整需求上传数据模型，支持一个需求下多个来源文件。
- 上传接口支持 `new` 和 `append` 两种模式。
- 新增需求名称唯一性校验接口。
- 新增来源文件列表、原始文件预览、转换稿预览接口。
- 前端上传页支持模式切换、需求名称必填、多文件一次性提交、追加到已有需求。
- 需求详情页新增“来源文件”Tab，支持查看来源文件、预览原文件、查看转换稿和追加更多文件入口。

本期不包含：

- 智能归并差异预览。
- 自动判断已有模块、新模块、冲突、废弃、待澄清。
- 归并后触发知识库更新标记。
- PDF.js 深度渲染、Word 高保真 HTML 预览。
- 异步任务中心化改造。

## 数据模型设计

### source_documents

移除字段：

- `original_file_path`

保留/调整字段：

- `id`
- `project_id`
- `name`
- `document_type`
- `current_version_id NULL`
- `status`
- `created_by`
- `created_at`
- `updated_at`

约束：

- 新增唯一约束：`UNIQUE(project_id, name)`。
- `current_version_id` 在新建需求后为空，首次归并生成版本后再写入。

建议状态：

- `collecting`：已有来源文件，但尚无正式工作稿版本。
- `pending_merge`：存在待归并文件。
- `versioned`：已有当前工作稿版本。
- `archived`：已归档。

需求级目录不入库，按约定计算：

```text
data/projects/{project_id}/requirements/{document_id}/
```

### source_document_file_mappings

字段调整：

- `version_id TEXT NULL`
- `source_file_path TEXT NOT NULL`
- `original_filename TEXT NOT NULL`
- `file_format TEXT NOT NULL`
- `markdown_file_path TEXT`
- `conversion_status TEXT NOT NULL`
- `mapping_status TEXT NOT NULL`
- `conversion_summary TEXT NOT NULL DEFAULT ''`
- `conversion_quality INTEGER`
- `created_by TEXT NOT NULL`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

转换状态：

- `pending`
- `processing`
- `success`
- `warning`
- `failed`

归并状态：

- `pending_merge`
- `merged`
- `discarded`

说明：

- `conversion_status` 表示文件转换是否完成。
- `mapping_status` 表示转换稿是否已经归并进正式工作稿版本。
- `version_id` 仅在 `mapping_status = merged` 后指向对应 `SourceDocumentVersion`。

外键建议：

- `document_id` 继续 `ON DELETE CASCADE`。
- `version_id` 可空；删除版本时不应自动删除来源文件映射，优先使用 `ON DELETE SET NULL` 或业务上禁止删除已有版本。

### 文件目录

```text
requirements/{document_id}/
  raw/
    {mapping_id}-{original_filename}
  markdown/
    conversions/
      {mapping_id}.md
    versions/
      v1.md
      v2.md
```

转换稿使用 `mapping_id.md` 存储，避免同名文件覆盖。接口返回原始文件名用于展示。

## 后端接口设计

### POST /projects/{project_id}/requirements

用途：新建需求或追加文件。

表单字段：

- `mode`: `new` 或 `append`
- `document_name`: 新建需求时必填
- `existing_document_id`: 追加模式时必填
- `files`: 1 到 10 个文件

规则：

- `mode = new` 时校验 `document_name` 非空且同项目唯一，创建一个 `SourceDocument`。
- `mode = append` 时校验 `existing_document_id` 属于当前项目。
- 两种模式均为每个文件创建一条 `source_document_file_mappings`。
- 上传完成后执行文件转换并写入 `markdown/conversions/{mapping_id}.md`。
- 不自动创建 `SourceDocumentVersion`。
- 不更新 `current_version_id`。

返回：

```json
{
  "document": {
    "id": "doc-xxx",
    "project_id": "project-xxx",
    "name": "登录认证需求",
    "current_version_id": null,
    "status": "pending_merge",
    "file_count": 2
  },
  "files": [
    {
      "id": "docmap-xxx",
      "original_filename": "产品需求说明.docx",
      "conversion_status": "success",
      "mapping_status": "pending_merge"
    }
  ]
}
```

### GET /projects/{project_id}/requirements/check-name

参数：

- `name`
- `exclude_id` 可选

返回：

```json
{ "exists": true }
```

用途：

- 前端新建需求名称失焦校验。
- 后端提交仍必须重复校验，避免并发重复创建。

### GET /projects/{project_id}/requirements/{document_id}/files

返回当前需求的来源文件列表。

字段：

- `id`
- `document_id`
- `original_filename`
- `file_format`
- `created_at`
- `conversion_status`
- `mapping_status`
- `version_id`
- `version_no`
- `markdown_file_path`
- `conversion_summary`

### POST /projects/{project_id}/requirements/{document_id}/files

用途：详情页“追加更多文件”入口。

规则：

- 等价于上传接口的 `mode = append`。
- 路径中的 `document_id` 为追加目标。
- 返回结构与上传接口一致。

### GET /requirement-files/{mapping_id}/original

用途：预览或下载原始文件。

返回规则：

- `txt/md`：返回文本内容。
- `pdf`：本期返回文件流或 base64 数据，由前端 iframe 尝试展示。
- `doc/docx`：本期优先提供下载；如后端已有转换 HTML 能力，再返回 HTML 预览。

权限：

- 必须通过 mapping 反查 document 和 project，校验当前用户可访问该项目。

### GET /requirement-files/{mapping_id}/markdown

用途：返回单个来源文件转换后的 Markdown 内容。

规则：

- 仅当 `conversion_status` 为 `success` 或 `warning` 且 `markdown_file_path` 存在时返回。
- 转换失败返回明确错误码和转换摘要。

## 后端服务流

### 新建需求

1. 校验项目存在和用户权限。
2. 校验需求名称非空。
3. 校验同项目下名称唯一。
4. 创建 `SourceDocument`，`current_version_id = NULL`，`status = pending_merge`。
5. 为每个文件写入 `raw/{mapping_id}-{original_filename}`。
6. 创建 `FileMapping`，初始 `conversion_status = processing`，`mapping_status = pending_merge`，`version_id = NULL`。
7. 转换文件到 `markdown/conversions/{mapping_id}.md`。
8. 更新 `conversion_status`、`markdown_file_path`、`conversion_summary`。
9. 返回需求和文件列表。

### 追加文件

1. 校验目标需求属于当前项目。
2. 为每个文件执行同样的保存、映射创建和转换流程。
3. 不修改 `current_version_id`。
4. 将需求状态置为 `pending_merge`。
5. 返回需求和新增文件列表。

### 转换失败

转换失败不回滚已上传原始文件。

失败文件：

- `conversion_status = failed`
- `mapping_status = pending_merge`
- `markdown_file_path = NULL`
- `conversion_summary` 写入失败原因

接口整体策略：

- 如果至少一个文件保存成功，返回成功并在文件列表中展示每个文件状态。
- 如果所有文件均为空、格式不支持或保存失败，返回失败。

## 前端设计

### 上传页

模式切换：

- 默认“新建需求”。
- 切换为“追加到已有需求”后隐藏需求名称输入框，显示需求选择下拉器。

新建需求：

- 需求名称必填。
- 不再从文件名自动推断需求名称。
- 失焦调用 `check-name`。
- 重复时显示“该需求名称已存在”。
- 提交时若名称为空或重复，阻断提交并聚焦输入框。

追加到已有需求：

- 调用当前项目需求列表接口。
- 下拉器只展示需求名称。
- 支持关键词搜索。
- 选中后显示“当前已有来源文件：N 个”。

文件提交：

- 一次选择多个文件。
- 点击“提交”后统一提交一个请求。
- 禁止逐文件自动上传。

成功跳转：

- 新建需求：跳转到 `/projects/{project_id}/requirements/{document_id}?tab=source-files`。
- 追加文件：跳转到同一个来源文件 Tab，Toast 显示“文件已添加，请在来源文件列表中发起归并”。

### 详情页来源文件 Tab

新增 Tab：

- `当前工作稿`
- `来源文件`
- `版本记录`

无当前版本时：

- 默认展示“来源文件”Tab。
- 当前工作稿区域显示空态：“尚未生成工作稿，请先在来源文件中发起归并。”

来源文件列表：

- 文件名
- 格式
- 上传时间
- 转换状态
- 归并状态
- 操作

操作：

- “预览原文件”：打开侧抽屉。
- “查看转换稿”：打开侧抽屉，展示转换 Markdown。
- “发起归并”：本期可显示为禁用或进入占位说明，避免误以为智能归并已完成。
- “追加更多文件”：跳转上传页并预设追加模式和当前需求 ID。

## 测试策略

后端单元测试：

- 新建需求时一个需求对应多个 FileMapping。
- 新建需求后不创建版本，`current_version_id` 为空。
- 追加文件不会改变当前版本。
- 名称重复返回错误。
- `version_id` 可空。
- 转换失败时保留来源文件记录。

前端验证：

- 新建模式名称为空不能提交。
- 新建模式名称重复显示错误。
- 追加模式隐藏名称输入框并显示需求下拉器。
- 多文件只发起一次请求。
- 上传成功跳转到来源文件 Tab。
- 无当前版本详情页不崩溃。

## 风险与处理

- **现有 SQLite 迁移风险**：SQLite 删除列需要重建表。本期实现计划必须包含数据迁移步骤或开发库重建策略。
- **旧接口响应兼容风险**：前端列表和详情不能再依赖 `original_file_path`。
- **归并能力缺口**：来源文件可进入待归并，但本期不完成智能归并。页面文案必须明确“当前工作稿未变更”。
- **同名文件覆盖风险**：转换稿和 raw 文件使用 `mapping_id` 前缀或文件名，展示仍使用原始文件名。

## 推荐实施顺序

1. 后端测试先行，锁定新建多文件、追加文件、名称唯一、无初始版本。
2. 调整数据库初始化和迁移逻辑。
3. 重构 document repository/service/schema。
4. 增加来源文件相关接口。
5. 改造上传页为模式化一次性提交。
6. 改造详情页 Tab 和来源文件列表。
7. 跑后端测试、前端 lint/build，并用浏览器验证上传和详情页。
