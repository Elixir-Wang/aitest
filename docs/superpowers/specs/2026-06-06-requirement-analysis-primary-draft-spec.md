# 主需求锚定的需求分析前后端改造 Spec

> 状态：已被 `2026-06-07-requirement-analysis-two-stage-agent-spec.md` 收敛。
> 本文中“一次分析同时读取辅助文档并补入初步需求”的设计不再作为实现依据。当前实现边界是：阶段一只分析主需求；阶段二通过独立的辅助文档增强入口处理辅助文档。

## 背景

当前需求详情页已经有 `需求澄清` tab、`/review` 和 `/analysis` 接口，以及旧的 `requirement_analysis` 能力。现有链路更像“主需求标准文件 -> 生成最终需求版本 -> 运行需求分析 -> 展示澄清问题”。这和新的产品目标不一致：

1. 用户希望顶层入口叫 `需求分析`，不再把核心体验定位为“澄清问题列表”。
2. 用户希望 `requirement-review` 和 `test-scenarios` 作为后台分析能力，而不是单独展示一份分析报告。
3. 用户希望先快速看到主需求自身的分析结果和待确认问题。
4. 辅助需求文件找答案应作为独立增强阶段，不阻塞主需求分析结果。
5. 不能回到“需求归并智能体”：辅助文档不能主动扩大主需求范围，也不能无锚点合并。

本规范原先尝试把“主需求锚定 + 辅助文档补证 + 初步需求产出”放在一次分析中；该设计已被拆分为两阶段。

## 目标

- 将需求详情页中的 `需求澄清` 入口改为 `需求分析`。
- 在 `需求分析` 下提供两个子 tab：
  - `初步需求`
  - `待确认问题`
- `初步需求` 展示主需求分析产出的草稿。
- `待确认问题` 展示主需求自身无法确认、证据冲突、来源不明或需要人工确认的问题。
- 使用 `requirement-review` 思路识别主需求缺陷，包括遗漏、歧义、冲突、不可测、规则缺失、验收标准缺失。
- 使用 `test-scenarios` 思路反推测试前置条件、边界值、异常路径、预期结果和验收标准缺口。
- 阶段一不读取辅助文档、不调用辅助文档搜索、不生成辅助补强。
- 辅助文档只通过独立的 `analysis/{analysis_id}/enhance` 增强入口处理。
- 后端返回结构化结果，前端不解析自由文本来判断业务状态。

## 非目标

- 不恢复或重建需求归并智能体。
- 不把所有辅助文档合并成一份新需求。
- 不让辅助文档主动扩展主需求范围。
- 不把 `requirement-review` 和 `test-scenarios` 原始报告作为独立用户 tab 展示。
- 不在本次改造中实现人工确认后自动生成正式最终需求。
- 不改造原始文件转换、标准文件编辑、版本记录、项目切换等无关流程。
- 不在前端暴露内部 prompt、agent 分步日志或 token 细节。

## 核心原则

```text
主需求 = 分析对象和范围边界
辅助文档 = 阶段二证据库
需求分析 = 主需求找问题、输出初步需求和待确认
初步需求 != 最终需求
```

阶段一不得补入任何来自辅助文档的内容。辅助文档能否回答问题、是否冲突、是否可补强，只能在阶段二增强中裁决。

## 用户流程

```text
1. 用户在标准文件中设置主需求文件
2. 用户点击“需求分析”
3. 后端读取主需求标准 Markdown
4. 智能体只分析主需求，生成初步需求、分析报告和待确认问题
5. 前端默认打开“需求分析 / 初步需求”
6. 如存在辅助文件，用户可另行触发“从辅助文档找答案”
```

## 页面结构

需求详情页一级 tab 调整为：

```text
概览
原始文件
标准文件
需求分析
最终需求
```

`需求分析` 下的二级 tab：

```text
初步需求
待确认问题
```

### 初步需求

展示 `analysis.output.preliminary_requirement_markdown`。

辅助补强内容应在 Markdown 中保留轻量标记，例如：

```markdown
> 辅助补强
> 来源：登录流程说明.md / 验证码规则
> 证据：验证码有效期为 5 分钟，连续输错 5 次后锁定 15 分钟。
```

如果用户不希望 Markdown 正文太重，前端可把同类来源标记渲染成紧凑标签，但后端 Markdown 必须保留可追溯信息。

### 待确认问题

展示 `analysis.output.clarification_questions` 和 `analysis.output.conflicts`。

每个问题展示：

- 严重级别。
- 问题类型。
- 关联模块。
- 问题描述。
- 为什么需要人工确认。
- 主需求摘录。
- 需要人工确认的问题。

空态：暂无待确认问题。

未执行分析空态：

```text
尚未执行需求分析。完成分析后会生成初步需求和待确认问题。
```

## 后端设计

### 目录结构

新增或改造：

```text
apps/backend/app/agents/requirement_analysis/
  __init__.py
  agent.py
  service.py
  schemas.py
  prompts.py
  skills/
    requirement-review/
      SKILL.md
    test-scenarios/
      SKILL.md
```

保留现有接口路径：

```text
POST /api/v1/projects/{project_id}/requirements/{document_id}/review
GET  /api/v1/projects/{project_id}/requirements/{document_id}/analysis
```

`/review` 的语义从“生成最终需求并分析”调整为“生成或更新初步需求分析结果”。为了兼容前端，可继续调用同一路径；如果后续需要更清晰 API，可新增 `/analysis/run`，但第一版不强制。

### 输入 Schema

阶段一 `RequirementAnalysisInput` 只保留主需求字段：

```python
class RequirementAnalysisInput(BaseModel):
    project_id: str
    document_id: str
    document_name: str
    primary_mapping_id: str
    primary_filename: str
    primary_markdown_content: str
```

说明：

- `primary_markdown_content` 是唯一分析对象。
- 阶段一不接收 `auxiliary_documents`。
- 不再要求先生成 `current_version_id` 才能分析。

### 输出 Schema

扩展 `RequirementAnalysisOutput`：

```python
class RequirementEvidenceReference(BaseModel):
    mapping_id: str
    filename: str
    excerpt: str
    section_hint: str = ""


class RequirementAppliedSupplement(BaseModel):
    id: str
    source_question_id: str
    module_key: str
    module_name: str
    insertion_anchor: str
    inserted_markdown: str
    evidence: RequirementEvidenceReference
    reason: str
    confidence: Literal["high", "medium"]


class RequirementUnresolvedFinding(BaseModel):
    id: str
    module_key: str
    module_name: str
    issue_type: Literal[
        "conflict",
        "out_of_scope",
        "weak_evidence",
        "source_unclear",
        "other",
    ]
    question: str
    reason: str
    impact: str
    severity: Literal["blocker", "major", "minor"]
    primary_excerpt: str = ""
    evidence: list[RequirementEvidenceReference] = Field(default_factory=list)


class RequirementAnalysisOutput(BaseModel):
    status: Literal["completed", "needs_clarification", "blocked"]
    analysis_summary: str
    preliminary_requirement_markdown: str
    applied_supplements: list[RequirementAppliedSupplement] = Field(default_factory=list)
    clarification_questions: list[RequirementUnresolvedFinding] = Field(default_factory=list)
    conflicts: list[RequirementUnresolvedFinding] = Field(default_factory=list)
    quality_gate: RequirementQualityGate
    next_actions: list[str] = Field(default_factory=list)
```

兼容策略：

- 旧字段 `modules`、`coverage_audit`、`key_gaps` 可保留在 schema 中，避免前端和测试一次性大改。
- 前端新 UI 主要依赖 `preliminary_requirement_markdown`、`applied_supplements`、`clarification_questions`、`conflicts`。

### Agent 与 Skills 设计

阶段一不再使用 DeepAgents `FilesystemMiddleware`、`SkillsMiddleware`、`SummarizationMiddleware` 或辅助搜索工具。当前实现由 Codex runner 在隔离工作目录中执行：

```text
input/primary.md
skills/requirement-review/SKILL.md
output/analysis.json
output/analysis.md
```

阶段一只允许读取工作目录内的主需求和 `requirement-review` skill，不读取辅助文档，也不注册 `search_auxiliary_documents`。测试场景视角通过 prompt 中的短 checklist 表达，不再把 `test-scenarios` 作为运行时 skill 读入。

辅助文档增强由独立的 `RequirementAuxiliaryEnhancementAgent` 负责，输入为阶段一问题列表和辅助文章 Markdown。

### Skill 内容边界

`skills/requirement-review/SKILL.md` 从 `requirement-review` 沉淀以下内容：

- 完整性。
- 清晰度。
- 一致性。
- 可测试性。
- 可追溯性。
- 可行性。
- 严重级别划分。
- 常见反模式。

`skills/test-scenarios/SKILL.md` 从 `test-scenarios` 沉淀以下内容：

- 测试目标。
- 前置条件。
- 用户角色。
- 操作步骤。
- 预期结果。
- 边界值。
- 异常路径。
- 验收标准反推。

这两个 skill 只提供分析方法，不拥有写库、写版本或合并文档的权限。

### Agent Prompt 约束

Prompt 必须包含：

```text
你是主需求锚定的需求分析智能体。
你只能把 primary_markdown_content 作为分析对象。
本阶段不得读取、引用或推测任何辅助文档。
你必须识别主需求中的缺陷和不可测点。
applied_supplements 必须为空数组。
不得生成归并需求，不得把辅助文档全量合并。
```

内部分析步骤：

1. 使用 `requirement-review` 维度检查主需求：
   - 完整性。
   - 清晰度。
   - 一致性。
   - 可测试性。
   - 可追溯性。
   - 可行性。
2. 使用 `test-scenarios` 维度反推缺口：
   - 前置条件。
   - 用户角色。
   - 操作步骤。
   - 预期结果。
   - 边界值。
   - 异常路径。
   - 验收标准。
3. 生成 `preliminary_requirement_markdown`、`analysis_report_markdown`、`clarification_questions`、`conflicts` 和 `quality_gate`。
4. 无法由主需求自身确认的问题，进入 `clarification_questions` 或 `conflicts`。

### Service 设计

`document.service.review_primary_requirement_file()` 调整为：

```text
读取主需求 mapping
  -> 读取主需求标准 Markdown
  -> 构造 RequirementAnalysisInput
  -> 调用 requirement_analysis.service.analyze_requirement(...)
  -> 保存 requirement_analysis 记录
  -> 不写入 source_document_versions
  -> 不更新 current_version_id
  -> 返回分析结果
```

注意：

- 如果分析失败，不创建新版本。
- 阶段一无论是否存在辅助文件，都只生成基于主需求的初步需求和待确认问题。
- 只有 `finalize_requirement_analysis` 才能把初步需求写成最终版本。

### Repository

现有 `requirement_analyses` 表可继续保存 `output_json`。第一版不强制新增表。

需要确认当前表字段能承载：

- `status`
- `analysis_summary`
- `quality_result`
- `testability_score`
- `output_json`

如果需要查询补强明细，先从 `output_json` 读取，不新增 `requirement_analysis_supplements` 表。

## 前端设计

### 类型调整

在需求详情页补充类型：

```ts
type RequirementEvidenceReference = {
  mapping_id: string;
  filename: string;
  excerpt: string;
  section_hint: string;
};

type RequirementAppliedSupplement = {
  id: string;
  source_question_id: string;
  module_key: string;
  module_name: string;
  insertion_anchor: string;
  inserted_markdown: string;
  evidence: RequirementEvidenceReference;
  reason: string;
  confidence: "high" | "medium";
};

type RequirementUnresolvedFinding = {
  id: string;
  module_key: string;
  module_name: string;
  issue_type: string;
  question: string;
  reason: string;
  impact: string;
  severity: "blocker" | "major" | "minor";
  primary_excerpt: string;
  evidence: RequirementEvidenceReference[];
};
```

`RequirementAnalysisResult.output` 增加：

```ts
preliminary_requirement_markdown: string;
applied_supplements: RequirementAppliedSupplement[];
clarification_questions: RequirementUnresolvedFinding[];
conflicts: RequirementUnresolvedFinding[];
```

### Tab 调整

一级 tab：

```tsx
<TabsTrigger value="analysis">需求分析</TabsTrigger>
```

`clarification` query 兼容：

```text
?tab=clarification -> analysis
?tab=initial -> analysis
```

`需求分析` tab 内部：

```text
初步需求
待确认问题
```

默认进入：

- 分析完成后进入 `需求分析 / 初步需求`。
- 如果没有分析结果，仍显示 `需求分析` tab 和空态。
- 不再只有存在 `clarification_questions` 时才显示入口。

### 初步需求 UI

展示优先级：

1. `analysisResult.output.preliminary_requirement_markdown`
2. `overview.initial_markdown_content`
3. 空态

展示元素：

- Markdown 预览。
- 右上角状态摘要：
  - 已补强 N 项。
  - 待确认 M 项。
  - 质量门禁结果。
- 辅助补强内容通过 Markdown 中的引用块展示。

### 待确认问题 UI

展示合并列表：

```ts
const pendingItems = [
  ...analysisResult.output.clarification_questions,
  ...analysisResult.output.conflicts,
];
```

展示字段：

- 严重级别 badge。
- 问题类型 badge。
- 模块名。
- 问题。
- 原因。
- 影响。
- 主需求摘录。
- 辅助证据摘录。

冲突类问题展示更醒目的说明，但危险色保持克制。

### 文案调整

| 旧文案 | 新文案 |
| --- | --- |
| 需求澄清 | 需求分析 |
| 需求评审 | 需求分析 |
| 评审中 | 分析中 |
| 最终需求 | 初步需求 |
| 尚未生成最终需求 | 尚未生成初步需求 |
| 完成评审后会在这里展示澄清问题 | 完成分析后会生成初步需求和待确认问题 |

如果当前业务仍保留 `最终需求` 一级 tab，本次仅把 `需求分析` 下的主产物命名为 `初步需求`，不强行删除历史 `最终需求` tab。后续再单独统一版本语义。

## 数据兼容

历史分析结果可能没有 `preliminary_requirement_markdown`。

兼容规则：

- 如果缺少 `preliminary_requirement_markdown`，前端使用 `overview.initial_markdown_content`。
- 如果只有旧 `clarification_questions`，继续展示到 `待确认问题`。
- 如果旧数据没有 `conflicts`，按空数组处理。
- 旧 query `?tab=clarification` 跳转到 `需求分析`。

## 测试策略

### 后端单元测试

更新或新增：

```text
apps/backend/tests/test_requirement_primary_file_service.py
apps/backend/tests/test_requirement_analysis_agent.py
apps/backend/tests/test_ai_agent_model_assignments.py
```

覆盖：

- 主需求分析不再要求已有 `current_version_id`。
- `review_primary_requirement_file` 读取 primary mapping 作为主需求。
- 阶段一 input 不包含 `auxiliary_documents`。
- 阶段一不读取辅助标准 Markdown。
- 阶段一输出 `applied_supplements=[]`。
- 分析失败时不创建新版本。
- 分析完成时不创建最终需求版本。
- `output_json` 保存完整结构化分析结果。

### 前端验证

建议执行：

```powershell
npm --prefix apps/frontend run typecheck
```

手工或组件验证：

- 需求详情页始终显示 `需求分析` tab。
- 需求分析下显示 `初步需求 / 待确认问题`。
- 点击标准文件里的按钮文案为 `需求分析`，loading 为 `分析中`。
- 分析完成后默认进入 `需求分析 / 初步需求`。
- 有待确认问题时显示在 `待确认问题`，无问题显示空态。
- 历史 `?tab=clarification` 可正常进入新 `需求分析`。

### 回归验证命令

建议执行：

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_requirement_primary_file_service.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_ai_agent_model_assignments.py -q
npm --prefix ..\frontend run typecheck
```

## 验收标准

- 用户看到的是 `需求分析`，不是 `需求澄清`。
- `需求分析` 下只有 `初步需求` 和 `待确认问题` 两个子 tab。
- `requirement-review` 和 `test-scenarios` 作为后台分析维度，不作为独立报告 tab。
- 阶段一只分析主需求，不读取辅助文档。
- 辅助文档只能通过独立增强入口回答阶段一问题。
- 阶段一不会把辅助文档补入初步需求。
- 分析结果会保存为 `requirement_analyses.output_json`。
- 初步需求 Markdown 不会自动成为当前最终版本。
- 旧的 `clarification` 路由参数和历史分析数据仍能展示。

## 风险与处理

### 风险：流程再次变成需求归并

处理：

- 阶段一 schema 删除 `auxiliary_documents`。
- 阶段一 service 不收集辅助文档。
- 辅助文档增强使用独立 API 和独立输出 delta。

### 风险：初步需求被误认为最终需求

处理：

- 前端文案统一使用 `初步需求`。
- 版本 `source_action` 使用 `requirement_analysis`。
- `change_summary` 不出现“最终需求”。

### 风险：分析结果过重，页面难读

处理：

- 不展示原始分析报告。
- 默认展示初步需求正文。
- 待确认问题只展示需要人工处理的问题。

### 风险：辅助增强证据不稳定

处理：

- 辅助增强项必须包含来源文件名和摘录。
- 无摘录不得在阶段二生成补强项。
- 置信度只允许 `high` 或 `medium`，不展示伪精确分数。
