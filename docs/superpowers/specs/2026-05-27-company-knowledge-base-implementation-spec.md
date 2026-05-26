# 公司知识库实施 Spec

## 背景

已有 PRD `docs/00-产品文档/00-22-AI测试系统-全局知识库PRD.md` 定义了全局知识库。产品界面按用户口径展示为“公司知识库”，用于沉淀跨项目复用的测试规范、用例模板、评审规则、自动化规范、平台 PRD、通用术语和团队方法论。

当前知识库页面已有 `项目知识库 / 公司知识库` 页签，但公司知识库仍显示“本期暂不实现”。本 spec 用于把公司知识库补成可上传、可转换、可预览、可版本化、可废弃的独立能力。

## 目标

- 公司知识库独立于项目知识库，不绑定 `project_id`。
- 管理员可上传公司知识文件，并维护元数据。
- 系统保存原始文件，转换为 Markdown，支持详情预览。
- 公司知识支持版本化和历史查看。
- 管理员可废弃公司知识，废弃后不再作为新任务默认上下文。
- 测试工程师和访客可查看公司知识，但不能维护。
- 下游 Agent 后续可读取公司知识作为通用规范上下文，并记录具体版本引用。

## 非目标

- 不把项目知识库自动提炼为公司知识库。
- 不让公司知识库替代项目知识库。
- 不把公司知识写回项目需求文档。
- 不实现向量数据库。
- 不实现审批流、外部知识系统同步、Git 同步。
- 不在本次实现复杂全文检索，只做列表筛选和 Markdown 预览。

## 术语

| 页面文案 | 后端命名 | 含义 |
| --- | --- | --- |
| 公司知识库 | `global_knowledge` | 跨项目通用知识 |
| 公司知识 | `global_knowledge_document` | 一份可复用知识文档 |
| 公司知识版本 | `global_knowledge_version` | 文档的某个 Markdown 版本 |
| 公司知识文件 | `global_knowledge_file` | 版本下的原始上传文件 |

说明：前端统一显示“公司知识库”，后端/API 沿用 PRD 的 `global-knowledge` 命名。

## 信息架构

知识库页面保留两个范围页签：

- `项目知识库`：按项目隔离，基于项目来源材料生成 `llm-wiki`。
- `公司知识库`：不按项目过滤，上传并管理跨项目复用知识。

顶部项目切换器规则：

- 顶部为“全部项目”时，知识库页面默认进入 `公司知识库`。
- 顶部为具体项目时，知识库页面默认进入 `项目知识库`。
- 用户仍可在页面内手动切换页签。
- 公司知识库页签不显示、不提交、不存储 `project_id`。

## 权限

| 角色 | 查看列表 | 查看详情 | 上传 | 编辑元数据 | 新增版本 | 废弃 |
| --- | --- | --- | --- | --- | --- | --- |
| 管理员 | 是 | 是 | 是 | 是 | 是 | 是 |
| 测试工程师 | 是 | 是 | 否 | 否 | 否 | 否 |
| 访客 | 是 | 是 | 否 | 否 | 否 | 否 |

后端必须校验权限；前端只展示后端返回的 `available_actions`。

## 知识类型

存储枚举建议：

| 中文 | 枚举 |
| --- | --- |
| 平台 PRD | `platform_prd` |
| 测试规范 | `test_standard` |
| 用例模板 | `case_template` |
| 评审规则 | `review_rule` |
| 自动化规范 | `automation_standard` |
| 通用术语 | `term` |
| 通用流程 | `workflow` |
| 其他 | `other` |

## 状态

| 中文 | 枚举 | 说明 | 可被新任务引用 |
| --- | --- | --- | --- |
| 转换中 | `processing` | 已上传，正在转换 Markdown | 否 |
| 可用 | `available` | 当前版本转换成功 | 是 |
| 转换失败 | `conversion_failed` | 当前版本文件转换失败 | 否 |
| 已废弃 | `archived` | 管理员废弃 | 否 |

## 数据模型

### global_knowledge_documents

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | text pk | `gkdoc-xxx` |
| name | text | 知识名称 |
| knowledge_type | text | 知识类型枚举 |
| scope | text | 适用范围，默认“全部项目” |
| source_note | text | 来源说明 |
| description | text | 描述 |
| status | text | `processing/available/conversion_failed/archived` |
| current_version_id | text nullable | 当前版本 |
| created_by | text | 创建人 |
| created_at | text | 创建时间 |
| updated_at | text | 更新时间 |
| archived_at | text nullable | 废弃时间 |

约束：

- `name + knowledge_type` 建议唯一，但允许管理员后续通过版本管理维护同一文档。
- 不包含 `project_id`。

### global_knowledge_versions

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | text pk | `gkver-xxx` |
| document_id | text fk | 公司知识 ID |
| version_no | text | 用户填写或系统生成，如 `v1` |
| markdown_content | text | Markdown 正文 |
| markdown_path | text | Markdown 文件路径 |
| change_summary | text | 变更摘要 |
| conversion_status | text | `queued/running/success/failed` |
| conversion_summary | text | 转换摘要或失败原因 |
| created_by | text | 创建人 |
| created_at | text | 创建时间 |

### global_knowledge_files

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | text pk | `gkfile-xxx` |
| version_id | text fk | 公司知识版本 ID |
| original_filename | text | 原始文件名 |
| file_path | text | 原始文件路径 |
| file_type | text | `md/txt/docx/pdf` 等 |
| file_size | integer | 字节数 |
| created_at | text | 创建时间 |

### global_knowledge_usage_logs

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | text pk | `gkuse-xxx` |
| global_knowledge_version_id | text | 被引用的公司知识版本 |
| usage_type | text | `requirement_analysis/knowledge_build/testcase_generation/automation_generation/failure_diagnosis` |
| target_project_id | text nullable | 使用时关联的项目 |
| target_object_id | text | 业务对象 ID |
| summary | text | 使用摘要 |
| created_at | text | 创建时间 |

## 文件存储

公司知识库使用独立目录，不混入项目目录：

```text
data/
  global-knowledge/
    documents/
      {document_id}/
        versions/
          {version_id}/
            raw/
            markdown/
```

路径存储继续使用相对存储路径，读取时通过 Storage 层解析，前端不得直接拼接本地路径。

## API

所有响应继续走现有 `/api/v1` 包装。

### 查询列表

```http
GET /api/v1/global-knowledge/documents
```

查询参数：

- `keyword`
- `knowledge_type`
- `status`
- `page`
- `page_size`

返回字段：

- `items`
- `pagination`
- `filters`

列表项字段：

- `id`
- `name`
- `knowledge_type`
- `knowledge_type_label`
- `version`
- `scope`
- `status`
- `status_label`
- `file_count`
- `description`
- `updated_at`
- `created_by`
- `available_actions`

### 上传公司知识

```http
POST /api/v1/global-knowledge/documents
Content-Type: multipart/form-data
```

字段：

- `name` 必填
- `knowledge_type` 必填
- `version` 可选，默认 `v1`
- `scope` 可选，默认“全部项目”
- `source_note` 可选
- `description` 可选
- `files` 必填，允许一个或多个

禁止：

- 请求中出现 `project_id` 时返回 `400 GLOBAL_KNOWLEDGE_PROJECT_ID_FORBIDDEN`。
- 不接收需求上传模式字段，如 `mode/document_name/existing_document_id`。

### 查看详情

```http
GET /api/v1/global-knowledge/documents/{document_id}
```

返回：

- `document`
- `current_version`
- `files`
- `versions`
- `usage_logs`
- `available_actions`

### 更新元数据

```http
PATCH /api/v1/global-knowledge/documents/{document_id}
```

允许更新：

- `name`
- `knowledge_type`
- `scope`
- `source_note`
- `description`

不允许直接覆盖文件内容。

### 新增版本

```http
POST /api/v1/global-knowledge/documents/{document_id}/versions
Content-Type: multipart/form-data
```

字段：

- `version`
- `source_note`
- `change_summary`
- `files`

转换成功后将新版本设为 `current_version_id`，旧版本保留。

### 废弃

```http
POST /api/v1/global-knowledge/documents/{document_id}/archive
```

废弃后：

- 文档状态变为 `archived`。
- 不再作为新任务默认上下文。
- 历史任务仍可查看当时引用的版本。

## 转换规则

复用现有需求文件转换能力中的底层转换逻辑，但不能复用需求上传接口和需求文档表。

转换策略：

- Markdown/TXT：本地直接保存为 Markdown。
- DOCX/PDF：复用已有格式转换能力。
- 转换失败：保留原始文件，版本状态为 `failed`，文档状态为 `conversion_failed`。

转换摘要必须面向用户，例如：

- `Markdown 文件已保存为公司知识预览。`
- `DOCX 已转换为 Markdown。`
- `文件转换失败：无法识别文件格式。`

## 前端行为

### 公司知识库列表

页签为 `公司知识库` 时：

- 列表标题：`公司知识库列表`
- 主按钮：`上传公司知识`
- 搜索提示：`搜索公司知识、类型或版本`
- 表头：`知识名称 / 状态 / 知识类型 / 更新时间 / 操作`
- 不显示项目来源数、探索数、构建编号。

操作：

- 查看
- 编辑
- 新增版本
- 废弃

测试工程师/访客：

- 上传、编辑、新增版本、废弃按钮禁用或不显示，具体以后端 `available_actions` 为准。

### 上传弹窗

字段：

- 知识名称
- 知识类型
- 版本号
- 适用范围
- 来源说明
- 描述
- 上传文件

禁止出现：

- 关联项目
- 需求名称
- 新建需求/追加到已有需求
- 是否触发项目知识库更新

### 详情区

列表下方或详情页展示：

- 基础信息
- 当前版本 Markdown 预览
- 文件列表
- 版本记录
- 使用记录

## 下游 Agent 使用规则

后续 Agent 读取上下文时按优先级：

```text
项目知识库 > 公司知识库 > 模型通用知识
```

规则：

- 公司知识只能作为通用规范、模板、术语和方法论。
- 公司知识不得被当作项目业务事实。
- 项目知识库和公司知识冲突时，以项目知识库为准。
- 下游任务必须记录引用的 `global_knowledge_version_id`。

## 操作日志

以下动作必须写 `operation_logs`：

- 上传公司知识：`module=knowledge`、`action=upload_global_knowledge`
- 更新元数据：`action=update_global_knowledge`
- 新增版本：`action=create_global_knowledge_version`
- 废弃：`action=archive_global_knowledge`

日志不得记录文件本地绝对敏感路径、API Key、账号密码等敏感内容。

## 验收标准

- 公司知识库页签不受顶部项目切换器过滤。
- 管理员可上传公司知识，上传表单没有任何项目字段。
- 上传接口收到 `project_id` 时返回明确错误。
- 上传成功后列表出现记录，状态为 `转换中`、`可用` 或 `转换失败`。
- Markdown/TXT 可直接形成 Markdown 预览。
- DOCX/PDF 走现有转换能力，失败时展示失败原因。
- 管理员可查看详情、版本记录和文件列表。
- 管理员可新增版本，新版本成功后成为当前版本。
- 管理员可废弃公司知识，废弃后不再被新任务默认引用。
- 测试工程师和访客可查看，不可上传、编辑、新增版本或废弃。
- 项目知识库列表不展示公司知识。
- 公司知识库列表不展示项目需求文档。
- 前端 lint/build 通过。
- 后端测试覆盖上传、禁止 `project_id`、列表、详情、新增版本、废弃和权限。

## 实施顺序

1. 新增数据表和 repository。
2. 新增 `global_knowledge_service`，复用底层文件转换能力。
3. 新增 `/api/v1/global-knowledge/documents` 路由。
4. 知识库页面公司知识库页签接真实接口。
5. 增加上传弹窗、详情区、版本记录。
6. 补权限和操作日志。
7. 补后端测试和前端验证。
