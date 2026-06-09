# 主需求锚定的需求分析前后端改造 Spec

## 背景

当前需求详情页已经有 `需求澄清` tab、`/review` 和 `/analysis` 接口，以及旧的 `requirement_analysis` 能力。现有链路更像“主需求标准文件 -> 生成最终需求版本 -> 运行需求分析 -> 展示澄清问题”。这和新的产品目标不一致：

1. 用户希望顶层入口叫 `需求分析`，不再把核心体验定位为“澄清问题列表”。
2. 用户希望 `requirement-review` 和 `test-scenarios` 作为后台分析能力，而不是单独展示一份分析报告。
3. 用户希望分析主需求后，如果问题能在辅助需求文件中找到明确答案，就把答案补入 `初步需求`。
4. 找不到答案或发现冲突时，问题进入 `待确认问题`。
5. 不能回到“需求归并智能体”：辅助文档不能主动扩大主需求范围，也不能无锚点合并。

本规范将需求分析调整为“主需求锚定 + 辅助文档补证 + 初步需求产出”的流程。

## 目标

- 将需求详情页中的 `需求澄清` 入口改为 `需求分析`。
- 在 `需求分析` 下提供两个子 tab：
  - `初步需求`
  - `待确认问题`
- `初步需求` 展示主需求内容，以及由辅助文档明确回答后补入的内容。
- `待确认问题` 展示辅助文档无法回答、证据冲突、来源不明或需要人工确认的问题。
- 使用 `requirement-review` 思路识别主需求缺陷，包括遗漏、歧义、冲突、不可测、规则缺失、验收标准缺失。
- 使用 `test-scenarios` 思路反推测试前置条件、边界值、异常路径、预期结果和验收标准缺口。
- 后端 LangChain agent 通过 DeepAgents `SkillsMiddleware` 按需加载 repo-local 的 `requirement-review` 和 `test-scenarios` skill。
- 只有被主需求问题锚定的辅助文档内容，才允许补入 `初步需求`。
- 补入内容必须保留来源文件、来源片段、补入位置和问题 ID。
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
辅助文档 = 证据库
需求分析 = 找问题、查证据、补初步需求、输出待确认
初步需求 != 最终需求
```

允许补入 `初步需求` 的内容必须同时满足：

1. 主需求中存在明确锚点，例如功能、流程、字段、状态、权限、验收点。
2. `requirement-review` 或 `test-scenarios` 先识别出问题。
3. 辅助文档能直接回答该问题。
4. 辅助文档内容与主需求不冲突。
5. 能记录来源文件、来源段落或摘录。
6. 不是辅助文档主动扩展出的新范围。

以下内容必须进入 `待确认问题`，不得补入 `初步需求`：

- 辅助文档找不到答案。
- 辅助文档与主需求冲突。
- 辅助文档有内容，但主需求没有锚点。
- 辅助文档只描述技术实现，不能证明业务规则。
- 辅助文档来源不明、版本不明或证据不足。
- 智能体只能推测，无法直接引用证据。

## 用户流程

```text
1. 用户在标准文件中设置主需求文件
2. 用户点击“需求分析”
3. 后端读取主需求标准 Markdown
4. 后端读取同需求文档下的辅助标准 Markdown
5. 智能体只分析主需求，先生成问题清单
6. 智能体围绕问题清单查辅助文档证据
7. 能明确回答的问题补入初步需求
8. 找不到答案或冲突的问题进入待确认问题
9. 前端默认打开“需求分析 / 初步需求”
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
- 为什么无法补入初步需求。
- 主需求摘录。
- 辅助文档证据状态。
- 需要人工确认的问题。

空态：

```text
暂无待确认问题。当前辅助文档已能回答本次分析识别出的可补强问题。
```

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

扩展 `RequirementAnalysisInput`：

```python
class RequirementAuxiliaryDocument(BaseModel):
    mapping_id: str
    filename: str
    markdown_content: str


class RequirementAnalysisInput(BaseModel):
    project_id: str
    document_id: str
    document_name: str
    primary_mapping_id: str
    primary_filename: str
    primary_markdown_content: str
    auxiliary_documents: list[RequirementAuxiliaryDocument] = Field(default_factory=list)
```

说明：

- `primary_markdown_content` 是唯一分析对象。
- `auxiliary_documents` 只用于围绕问题查证据。
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

`agent.py` 使用 LangChain `create_agent` 创建单 agent，并通过 DeepAgents middleware 加载技能。

第一版不使用 deepagents 子智能体。这里使用的是 middleware，不是 subagent 拓扑。

推荐结构：

```python
from pathlib import Path

from deepagents.backends import StateBackend
from deepagents.middleware import FilesystemMiddleware, SkillsMiddleware, SummarizationMiddleware
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_analysis.schemas import RequirementAnalysisOutput


SKILLS_DIR = Path(__file__).parent / "skills"


SYSTEM_PROMPT = """
你是主需求锚定的需求分析智能体。
你必须使用可用 skills 中的 requirement-review 和 test-scenarios 完成分析。
primary_markdown_content 是唯一分析对象。
auxiliary_documents 只作为证据库。
不得生成归并需求。
""".strip()


def requirement_analysis_agent(model):
    backend = StateBackend()
    return create_agent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            FilesystemMiddleware(
                backend=backend,
                system_prompt="只使用文件系统读取已加载的技能说明和中间上下文，不要把结果写入持久文件。",
            ),
            SkillsMiddleware(
                backend=backend,
                sources=[str(SKILLS_DIR)],
            ),
            SummarizationMiddleware(model=model, backend=backend),
        ],
        response_format=ToolStrategy(RequirementAnalysisOutput),
    )
```

middleware 角色：

| Middleware | 用途 |
| --- | --- |
| `SkillsMiddleware` | 把 `skills/` 下的 skill 元数据注入 agent，让 agent 按需读取 `SKILL.md` |
| `FilesystemMiddleware` | 提供 `read_file` 能力，使 agent 能读取被 SkillsMiddleware 暴露的 skill 文件 |
| `SummarizationMiddleware` | 长需求或多辅助文档时压缩上下文，降低超上下文风险 |

不建议使用 `MemoryMiddleware` 作为第一版能力，因为需求分析应只依赖本次输入的主需求、辅助文档和 repo-local skills，不应读取用户机器上的长期记忆或旧项目知识。

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
你必须先读取 requirement-review skill，再读取 test-scenarios skill。
你只能把 primary_markdown_content 作为分析对象。
auxiliary_documents 只作为证据库。
你必须先识别主需求中的缺陷和不可测点，再围绕这些问题查辅助文档。
没有主需求锚点的辅助内容不得补入初步需求。
辅助文档与主需求冲突时不得补入初步需求。
补入初步需求的每一段都必须包含来源文件和证据摘录。
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
3. 对问题逐条查辅助文档。
4. 能直接回答的问题，补入 `preliminary_requirement_markdown`。
5. 无法回答或冲突的问题，进入 `clarification_questions` 或 `conflicts`。

### Service 设计

`document.service.review_primary_requirement_file()` 调整为：

```text
读取主需求 mapping
  -> 读取主需求标准 Markdown
  -> 读取同 document 下非 primary 且已转换成功的辅助标准 Markdown
  -> 构造 RequirementAnalysisInput
  -> 调用 requirement_analysis.service.analyze_requirement(...)
  -> 保存 requirement_analysis 记录
  -> 如果 preliminary_requirement_markdown 非空，则写入一个 source_document_versions 版本
  -> current_version_id 指向该初步需求版本
  -> 返回分析结果
```

版本写入规则：

- `source_action = "requirement_analysis"`
- `change_summary = "需求分析生成初步需求"`
- `diff_summary` 记录补强数量和待确认数量。
- 文件路径继续使用 `versions/v{version_no}.md`。
- 不再使用“最终需求”文案描述该版本。

注意：

- 如果分析失败，不创建新版本。
- 如果没有辅助文件，仍生成基于主需求的初步需求，问题进入待确认。
- 如果辅助文件全部未转换完成，只使用主需求分析，提示辅助文件不可用。

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
- 辅助文件只包含同 document 下非 primary 且转换成功的标准 Markdown。
- 没有辅助文件时仍生成初步需求和待确认问题。
- 辅助文档能回答问题时，输出 `applied_supplements` 并写入初步需求 Markdown。
- 辅助文档冲突时，不写入初步需求，进入 `conflicts`。
- 分析失败时不创建新版本。
- 创建版本时 `source_action="requirement_analysis"`。
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
- 主需求中的问题如果能由辅助文档明确回答，会补入 `初步需求`。
- 补入内容带来源文件和证据摘录。
- 辅助文档无法回答、证据冲突、无主需求锚点的内容进入 `待确认问题`。
- 辅助文档不会全量合并进初步需求。
- 分析结果会保存为 `requirement_analyses.output_json`。
- 初步需求 Markdown 会作为当前版本内容展示，但文案不再称为“最终需求”。
- 旧的 `clarification` 路由参数和历史分析数据仍能展示。

## 风险与处理

### 风险：流程再次变成需求归并

处理：

- Prompt 中明确辅助文档没有主动写入权。
- 输出中每个补强项必须绑定 `source_question_id`。
- 后端测试覆盖“辅助文档有内容但主需求无锚点时不得补入”。

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

### 风险：辅助证据不稳定

处理：

- 补强项必须包含来源文件名和摘录。
- 无摘录不得补入初步需求。
- 置信度只允许 `high` 或 `medium`，不展示伪精确分数。
