# 需求文档分析实施计划

> **给执行型 agent：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐项执行本计划。步骤使用 `- [ ]` 复选框跟踪。

**目标：** 为单个已选项目实现需求文档分析 MVP，让用户能上传需求材料、形成 Markdown 工作稿、发起分析、查看覆盖矩阵、按模块评审并处理澄清问题。

**架构：** 后端负责文档元数据、版本、转换任务、分析任务、覆盖矩阵、模块评审和澄清写回记录；原始文件和大型 Markdown/分析产物保存在文件系统，SQLite 保存结构化状态、路径、版本和来源引用。前端使用当前模板化壳层，在项目内 `requirements` 页面补齐列表、详情、上传、分析、评审、澄清和版本视图。

**技术栈：** 当前后端栈、SQLite、文件系统产物、Next.js 16、React 19、shadcn/ui、TanStack Table、React Hook Form、Zod、Zustand。

---

## MVP 边界

- [ ] 支持在指定项目内上传 Markdown、Word、PDF 需求材料。
- [ ] 上传文件保存为 `SourceDocument`，原始文件保存在文件系统。
- [ ] Markdown 可直接形成工作稿版本；Word/PDF 先进入转换任务，转换结果形成 Markdown 工作稿版本。
- [ ] 多个来源材料汇总为一份项目级需求工作稿，不按上传文件拆成多份正式需求。
- [ ] 支持查看文档列表、当前版本、来源材料、版本记录。
- [ ] 支持 Markdown 预览和源码查看。
- [ ] 支持发起需求分析任务，生成分析状态和结构化结果占位。
- [ ] 支持展示原文覆盖矩阵。
- [ ] 支持按模块评审需求，模块状态为：待评审、评审中、有澄清、已完成、已废弃。
- [ ] 支持结构化澄清问题列表。
- [ ] 支持录入澄清答案，并生成“待写回”状态。
- [ ] 澄清写回必须生成新的 `SourceDocumentVersion`，不覆盖原始上传文件。
- [ ] 本阶段不直接生成正式知识库、测试用例或自动化代码。

---

## 关键对象

### 后端对象

- `SourceDocument`
- `SourceDocumentVersion`
- `DocumentConversionJob`
- `RequirementAnalysis`
- `SourceCoverageItem`
- `RequirementReviewModule`
- `RequirementReviewVerification`
- `ClarificationQuestion`
- `ClarificationApplyRecord`
- `DocumentVersionChangeLog`
- `SourceReference`
- `TaskRun`
- `TaskEvent`

### 前端页面

- `apps/frontend/src/app/(main)/projects/[projectId]/requirements/page.tsx`
- `apps/frontend/src/components/ai-testing/page-shell.tsx`
- `apps/frontend/src/components/ai-testing/project-switcher.tsx`
- 后续可新增 `apps/frontend/src/components/ai-testing/requirements/*`

---

## 阶段 1：数据模型与接口边界

### 任务 1：确认后端模型

**文件：**
- 阅读：`docs/00-产品文档/00-03-AI测试系统-需求文档分析与版本管理PRD.md`
- 阅读：`docs/03-后端架构与数据/03-02-AI测试系统-数据模型PRD.md`
- 修改：后端模型文件，具体路径以当前后端项目实际结构为准

- [ ] **步骤 1：定位后端目录和现有模型**

运行：

```powershell
rg --files apps | rg "models|schemas|api|routers|migrations"
```

预期：找到后端模型、schema、router 和迁移目录。

- [ ] **步骤 2：补齐需求文档核心表**

至少覆盖：

```text
source_documents
source_document_versions
document_conversion_jobs
requirement_analyses
source_coverage_items
requirement_review_modules
requirement_review_verifications
clarification_questions
clarification_apply_records
document_version_change_logs
```

- [ ] **步骤 3：运行后端测试或类型检查**

按后端实际技术栈运行测试。若当前没有后端测试，至少运行启动检查并记录缺口。

---

## 阶段 2：上传与版本

### 任务 2：实现来源材料上传和版本列表

**文件：**
- 修改：后端需求文档 router/service
- 修改：`apps/frontend/src/app/(main)/projects/[projectId]/requirements/page.tsx`
- 需要时新增：`apps/frontend/src/components/ai-testing/requirements/requirement-document-table.tsx`

- [ ] **步骤 1：实现上传接口**

接口建议：

```text
POST /api/v1/projects/{project_id}/requirements/documents
```

请求支持文件上传和文档类型。

- [ ] **步骤 2：实现列表接口**

接口建议：

```text
GET /api/v1/projects/{project_id}/requirements/documents
```

返回文档名称、类型、当前版本、状态、上传人、更新时间、可用操作。

- [ ] **步骤 3：前端接入列表和上传入口**

需求页保留当前 `PageShell`，把静态表格替换为接口数据。

---

## 阶段 3：Markdown 工作稿

### 任务 3：实现工作稿预览与源码查看

**文件：**
- 修改：后端版本详情接口
- 修改：需求详情或需求页内详情面板

- [ ] **步骤 1：实现版本详情接口**

接口建议：

```text
GET /api/v1/projects/{project_id}/requirements/documents/{document_id}/versions/{version_id}
```

返回 Markdown 正文或 Markdown 文件路径、来源动作、变更摘要和来源清单。

- [ ] **步骤 2：前端展示预览和源码**

使用 Tabs：

```text
预览
源码
版本
来源
```

---

## 阶段 4：分析、覆盖矩阵与模块评审

### 任务 4：实现需求分析任务和评审视图

**文件：**
- 修改：后端分析任务接口
- 修改：需求页分析结果和评审 Tab

- [ ] **步骤 1：实现发起分析接口**

接口建议：

```text
POST /api/v1/projects/{project_id}/requirements/documents/{document_id}/analysis
```

返回 `TaskRun` 和 `RequirementAnalysis`。

- [ ] **步骤 2：实现覆盖矩阵查询**

接口建议：

```text
GET /api/v1/projects/{project_id}/requirements/versions/{version_id}/coverage
```

覆盖状态包括：

```text
已覆盖
待归类
待澄清
无需测试
已废弃
```

- [ ] **步骤 3：实现模块评审列表**

接口建议：

```text
GET /api/v1/projects/{project_id}/requirements/versions/{version_id}/review-modules
```

模块状态包括：

```text
待评审
评审中
有澄清
已完成
已废弃
```

---

## 阶段 5：澄清问题与写回

### 任务 5：实现澄清闭环

**文件：**
- 修改：后端澄清问题和写回接口
- 修改：需求页澄清问题 Tab

- [ ] **步骤 1：实现澄清问题列表**

接口建议：

```text
GET /api/v1/projects/{project_id}/requirements/versions/{version_id}/clarifications
```

每个澄清问题必须包含原文引用、影响范围、当前假设、测试影响、写回位置和状态。

- [ ] **步骤 2：实现澄清答案保存**

接口建议：

```text
POST /api/v1/projects/{project_id}/requirements/clarifications/{clarification_id}/answer
```

- [ ] **步骤 3：实现澄清写回**

接口建议：

```text
POST /api/v1/projects/{project_id}/requirements/clarifications/{clarification_id}/apply
```

写回必须生成新的 `SourceDocumentVersion` 和 `DocumentVersionChangeLog`。

---

## 验收标准

- [ ] 上传 Markdown 后能直接预览。
- [ ] 上传 Word/PDF 后能进入转换任务并形成 Markdown 工作稿版本。
- [ ] 文档列表能看到状态、当前版本、上传人和更新时间。
- [ ] 每个版本都有来源动作、变更摘要和版本记录。
- [ ] 发起分析后能看到分析状态。
- [ ] 覆盖矩阵能展示已覆盖、待归类、待澄清、无需测试、已废弃。
- [ ] 模块评审能逐模块更新状态。
- [ ] 澄清问题能填写答案。
- [ ] 澄清写回生成新版本，不覆盖原始上传文件。
- [ ] 未完成模块、待归类原文、关键待澄清项未处理时，整份需求不能标记为已确认。
- [ ] 本阶段产物只作为知识库来源证据，不直接写入正式知识库。
