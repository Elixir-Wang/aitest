# 需求分析两阶段智能体拆分 Spec

## 背景

当前需求分析链路把“主需求质量分析”和“辅助文档找答案补强”放在同一个 LangChain agent 中执行。该 agent 同时挂载：

- DeepAgents `FilesystemMiddleware`
- DeepAgents `SkillsMiddleware`
- DeepAgents `SummarizationMiddleware`
- `search_auxiliary_documents` 工具
- `ToolStrategy(RequirementAnalysisOutput)`

这导致一次固定业务流程变成开放式工具循环：模型需要先理解任务、读取 skill、决定是否搜索辅助文档、反复调用搜索工具、再生成结构化输出并可能自修复。实际运行中已经出现上下文膨胀、长时间运行、超时和成本不可控问题。

本 spec 将需求分析拆成两个阶段：

```text
阶段一：主需求分析
阶段二：辅助文档增强
```

核心变化是：主需求分析先快速完成，不查辅助文档；辅助文档增强阶段把“阶段一发现的问题 + 多个辅助文章 Markdown”直接交给智能体，让智能体在这些文章中找答案、给推荐选项、识别冲突，并输出可合并的增强结果。

## 目标

- 将首次需求分析耗时降到可预期的分钟级。
- 首次分析只依赖主需求 Markdown，不读取辅助文档，不调用辅助搜索。
- 将辅助文档补强变成独立的可选后台任务，不阻塞用户看到主需求分析结果。
- 辅助文档增强阶段直接把多个辅助文章交给智能体，不再让智能体循环调用文件工具。
- 避免让模型自由循环调用文件工具或搜索工具。
- 复用现有 `RequirementAnalysisOutput`、`requirement_analyses`、澄清问题、最终需求确认流程。
- 保留“主需求是范围边界，辅助文档只是证据库”的产品原则。
- 增加调用次数、问题数、证据数和上下文预算的硬上限。

## 非目标

- 不恢复需求归并智能体。
- 不让辅助文档主动扩大主需求范围。
- 不让辅助文档增强阶段重新做完整需求分析。
- 不在前端展示内部 prompt、模型消息、完整证据检索日志。
- 不要求第一版引入 RAG、向量库或 embedding 检索。
- 不要求第一版重构所有历史 specs；本 spec 是对现有需求分析架构的补充和替代实现方向。

## 核心原则

```text
主需求分析 = 快速发现主需求自身问题
辅助文档增强 = 把问题和多个辅助文章交给智能体找答案
辅助文章 = 后端读取到的辅助 Markdown 文档
模型 = 只看本次输入中的主问题和辅助文章，不自由调用文件工具
```

允许辅助文档补强必须同时满足：

1. 阶段一已经识别出主需求问题或缺口。
2. 问题有明确主需求锚点。
3. 辅助文章中存在可引用片段。
4. 证据能直接回答该问题。
5. 证据与主需求不冲突。
6. 补入内容保留来源文件、来源摘录和问题 ID。

以下情况不得补入初步需求：

- 辅助文档没有命中证据。
- 证据弱，只能推测。
- 证据之间互相冲突。
- 证据与主需求冲突。
- 辅助文档内容没有主需求锚点。
- 模型引用了本次输入辅助文章之外的内容。

## 两阶段用户流程

```text
1. 用户设置主需求文件
2. 用户点击“需求分析”
3. 后端启动阶段一：主需求分析
4. 阶段一完成后，前端展示初步需求和待确认问题
5. 如果存在辅助文件，前端展示“辅助文档增强”入口
6. 用户点击增强，或系统按配置自动启动阶段二
7. 后端读取多个辅助文章 Markdown
8. 阶段二模型基于问题列表和辅助文章生成增强 delta
9. 后端校验 delta，并合并到原需求分析结果
10. 前端刷新初步需求、待确认问题、冲突和补强来源
```

## 阶段一：主需求分析智能体

### 名称

```text
RequirementPrimaryAnalysisAgent
```

### 职责

- 只分析 `primary_markdown_content`。
- 识别主需求自身的缺口、歧义、冲突、不可测点、缺失验收标准。
- 使用测试视角反推前置条件、角色、边界值、异常路径、预期结果缺口。
- 生成初步需求草稿。
- 生成待确认问题。
- 生成质量门禁结果。

### 禁止行为

- 不读取辅助文档。
- 不注册 `search_auxiliary_documents`。
- 不使用 `FilesystemMiddleware`。
- 不使用 `SkillsMiddleware`。
- 不在运行时读取 `requirement-review` 或 `test-scenarios` skill 文件。
- 不生成辅助补强内容。
- 不引用辅助文件作为来源。

### 输入

```python
class RequirementPrimaryAnalysisInput(BaseModel):
    project_id: str
    document_id: str
    document_name: str
    primary_mapping_id: str
    primary_filename: str
    primary_markdown_content: str
```

### 输出

第一版继续复用 `RequirementAnalysisOutput`，但字段约束如下：

```python
RequirementAnalysisOutput(
    applied_supplements=[],
    preliminary_requirement_markdown="基于主需求生成的初步需求",
    clarification_questions=[...],
    conflicts=[...],
    quality_gate=...,
)
```

阶段一输出不得包含辅助文档 evidence。

### 模型调用

推荐普通文档最多 2 次 LLM：

```text
Call 1: 主需求分析并生成 RequirementAnalysisOutput JSON
Call 2: 仅在 JSON/Pydantic/业务校验失败时 repair
```

如果使用支持原生 structured output 的模型，应优先使用 provider-native structured output；不要用 `ToolStrategy` 把结构化输出作为工具调用再塞回消息历史。

### Prompt 来源

不再运行时加载 84KB skill 文档。将 `requirement-review` 和 `test-scenarios` 萃取为短 checklist：

```text
REQUIREMENT_REVIEW_CHECKLIST <= 2k tokens
TEST_SCENARIO_CHECKLIST <= 2k tokens
```

checklist 放在 `prompts.py` 或版本化配置中，由后端直接拼入 prompt。

## 阶段二：辅助文档增强智能体

### 名称

```text
RequirementAuxiliaryEnhancementAgent
```

### 职责

- 只处理阶段一已产生的问题、冲突或缺口。
- 输入阶段一问题列表和多个辅助文章 Markdown。
- 智能体自己在这些辅助文章中查找能回答问题的内容。
- 生成推荐答案、补强建议或冲突说明。
- 输出 delta，由后端合并到原 `RequirementAnalysisOutput`。

### 禁止行为

- 不重新分析完整主需求。
- 不自由调用 `read_file`、`glob`、`grep`、`search_auxiliary_documents`。
- 不把本次输入的辅助文章之外的内容当作证据。
- 不直接覆盖完整 `RequirementAnalysisOutput`。

### 输入

```python
class RequirementAuxiliaryEnhancementInput(BaseModel):
    project_id: str
    document_id: str
    analysis_id: str
    primary_mapping_id: str
    primary_filename: str
    questions: list[RequirementEnhancementQuestion]
    auxiliary_articles: list[RequirementAuxiliaryArticleForEnhancement] = Field(default_factory=list)
```

```python
class RequirementEnhancementQuestion(BaseModel):
    id: str
    module_key: str
    module_name: str
    question: str
    reason: str
    impact: str
    severity: Literal["blocker", "major", "minor"]
    primary_excerpt: str = ""
```

```python
class RequirementAuxiliaryArticleForEnhancement(BaseModel):
    mapping_id: str
    filename: str
    markdown_content: str
```

### 输出

阶段二不返回完整 `RequirementAnalysisOutput`，只返回 delta：

```python
class RequirementAuxiliaryEnhancementOutput(BaseModel):
    enhancement_summary: str
    applied_supplements: list[RequirementAppliedSupplement] = Field(default_factory=list)
    resolved_question_options: list[RequirementResolvedQuestionOptions] = Field(default_factory=list)
    new_conflicts: list[RequirementUnresolvedFinding] = Field(default_factory=list)
    unchanged_question_ids: list[str] = Field(default_factory=list)
    auxiliary_coverage: list[RequirementAuxiliaryCoverage] = Field(default_factory=list)
```

```python
class RequirementResolvedQuestionOptions(BaseModel):
    question_id: str
    recommended_options: list[RequirementClarificationOption] = Field(default_factory=list, max_length=2)
    evidence: list[RequirementEvidenceReference] = Field(default_factory=list)
    resolution: Literal["answered", "weak_evidence", "conflict", "not_found"]
    reason: str
```

```python
class RequirementAuxiliaryCoverage(BaseModel):
    question_id: str
    matched_article_count: int
    coverage: Literal["answered", "partial", "conflict", "none"]
    filenames: list[str] = Field(default_factory=list)
```

## 辅助文章输入设计

### 辅助文章来源

第一版不做 RAG。后端直接读取多个辅助 Markdown，把阶段一问题和这些辅助文章一起交给阶段二智能体。

```text
阶段一问题列表
  -> 后端读取辅助 Markdown
  -> 组成 auxiliary_articles
  -> 交给阶段二智能体找答案
```

第一版的重点不是检索最优，而是先把“需求分析”和“辅助文档找答案”拆开，让阶段一快速完成，让阶段二独立运行。辅助文档增强阶段可以接受多个辅助文章全文。

### Schema

```python
class RequirementAuxiliaryArticleForEnhancement(BaseModel):
    mapping_id: str
    filename: str
    markdown_content: str
```

### 输入规则

第一版按用户当前产品取舍，直接把多个辅助文章交给智能体。为避免恢复到原先的开放工具循环，仍需遵守：

1. 阶段二不暴露文件系统工具。
2. 阶段二不暴露辅助搜索工具。
3. 辅助文章必须带 `mapping_id` 和 `filename`。
4. 模型输出中的来源必须引用输入中的 `mapping_id` 或 `filename`。
5. 模型不得引用输入文章之外的内容。

示例：

```json
{
  "questions": [
    {
      "id": "q-001",
      "question": "导出失败后是否允许重试？重试次数和时间限制是什么？",
      "primary_excerpt": "用户可导出报表，系统应提示导出结果。"
    }
  ],
  "auxiliary_articles": [
    {
      "mapping_id": "file-map-002",
      "filename": "报表导出规则.md",
      "markdown_content": "# 报表导出规则\n\n## 异常处理\n导出失败后，用户可在 10 分钟内重新发起导出，最多重试 3 次。"
    }
  ]
}
```

### 第一版局限

- 如果辅助文件很多或内容重复，模型仍可能难以定位答案。
- 如果问题很宽，模型可能在多个文件中看到大量相关但不直接回答的内容。
- 如果辅助文章总体很长，阶段二仍可能慢或超过模型上下文。

这些局限后续通过 RAG 证据包解决。

## 后续 RAG 证据包优化

### 证据包来源

后续版本可以把“直接传多个辅助文章”升级为“后端先检索，再传 Top-K 证据包”。这不是第一版目标。

```text
阶段一问题列表
  -> 后端为每个问题生成 query
  -> 后端读取辅助 Markdown
  -> 按标题/段落切 chunk
  -> 本地检索相关 chunk
  -> 去重、限量、裁剪 excerpt
  -> 形成 evidence_packet
  -> 交给阶段二模型裁决
```

### 可复用现有代码

现有代码可改造成后端内部能力：

```text
apps/backend/app/agents/requirement_analysis/tools.py
  build_auxiliary_chunks
  search_auxiliary_chunks
```

后续可以先复用当前词频/标题加权检索，再升级为 BM25 或 embedding hybrid search。

### Schema

```python
class RequirementEvidencePacket(BaseModel):
    question_id: str
    query: str
    primary_excerpt: str = ""
    evidence: list[RequirementRankedEvidence] = Field(default_factory=list)
```

```python
class RequirementRankedEvidence(BaseModel):
    mapping_id: str
    filename: str
    section_hint: str = ""
    excerpt: str
    score: float
```

### 示例

```json
{
  "question_id": "q-001",
  "query": "导出失败 重试 次数 时间限制",
  "primary_excerpt": "用户可导出报表，系统应提示导出结果。",
  "evidence": [
    {
      "mapping_id": "file-map-002",
      "filename": "报表导出规则.md",
      "section_hint": "导出异常处理",
      "excerpt": "导出失败后，用户可在 10 分钟内重新发起导出，最多重试 3 次。",
      "score": 0.86
    }
  ]
}
```

### Query 生成

后续 RAG 版本不需要第一时间使用 LLM 生成 query。后端可从问题中提取关键词：

- `question`
- `reason`
- `impact`
- `module_name`
- `primary_excerpt`
- `dimension`

对中文使用当前 `_query_terms` 逻辑即可。后续如检索质量不足，再增加一次轻量 LLM query rewrite，但必须有调用次数上限。

## 预算和上限

### 阶段一

```python
PRIMARY_MAX_LLM_CALLS = 2
PRIMARY_MAX_INPUT_CHARS = 80000
PRIMARY_MAX_FINDINGS = 20
PRIMARY_MAX_MODULES = 12
PRIMARY_MAX_CLARIFICATION_QUESTIONS = 25
PRIMARY_MAX_CONFLICTS = 10
PRIMARY_MAX_COVERAGE_AUDIT = 40
PRIMARY_TIMEOUT_SECONDS = 300
```

### 阶段二

```python
ENHANCEMENT_MAX_LLM_CALLS = 2
ENHANCEMENT_MAX_QUESTIONS_PER_BATCH = 8
ENHANCEMENT_MAX_AUXILIARY_ARTICLES = 5
ENHANCEMENT_MAX_TOTAL_AUXILIARY_CHARS = 80000
ENHANCEMENT_MAX_APPLIED_SUPPLEMENTS = 20
ENHANCEMENT_MAX_NEW_CONFLICTS = 10
ENHANCEMENT_TIMEOUT_SECONDS = 300
```

后续 RAG 证据包预算：

```python
ENHANCEMENT_MAX_RECALL_CANDIDATES = 100
ENHANCEMENT_MAX_RERANK_CANDIDATES = 30
ENHANCEMENT_MAX_EVIDENCE_PER_QUESTION = 5
ENHANCEMENT_MAX_EVIDENCE_CHARS_PER_QUESTION = 3000
ENHANCEMENT_MIN_EVIDENCE_SCORE = 0.45
```

### 大文档策略

如果主需求超过 `PRIMARY_MAX_INPUT_CHARS`：

1. 第一版可以直接失败，返回明确错误码 `REQUIREMENT_ANALYSIS_INPUT_TOO_LARGE`。
2. 第二版再支持章节分片分析：
   - 最多 4 个分片分析调用。
   - 1 个汇总调用。
   - 1 个 repair 调用。
   - 总调用上限 6 次。

## 后端模块设计

新增或改造：

```text
apps/backend/app/agents/requirement_analysis/
  service.py
  primary_agent.py
  enhancement_agent.py
  prompts.py
  validators.py
  merge.py
```

### service.py

职责：

- 对接 document service。
- 解析模型配置。
- 调用阶段一或阶段二 pipeline。
- 不直接拼复杂 prompt。
- 不暴露 LangChain agent loop。

### primary_agent.py

职责：

- 直接调用模型生成主需求分析结果。
- 不使用 `create_agent`。
- 不注册工具。
- 不读取辅助文件。

### enhancement_agent.py

职责：

- 接收阶段一问题列表和多个辅助文章 Markdown。
- 在辅助文章中查找每个问题的答案。
- 输出 `RequirementAuxiliaryEnhancementOutput`。
- 不自由调用工具。

### validators.py

职责：

- 校验阶段一输出。
- 校验阶段二 delta。
- 校验阶段二引用来源必须来自本次输入的辅助文章。
- 校验补强锚点存在。
- 校验列表数量上限。
- 校验空草稿。

### merge.py

职责：

- 将阶段二 delta 合并到原 `RequirementAnalysisOutput`。
- 更新 `applied_supplements`。
- 更新问题的 `recommended_options`。
- 添加新 conflicts。
- 保留未解决问题。
- 重新计算 status 和 quality gate 摘要。

## API 设计

### 阶段一：启动主需求分析

保留现有入口：

```text
POST /api/v1/projects/{project_id}/requirements/{document_id}/review
```

语义调整为：

```text
启动主需求分析任务
```

返回仍为 task-start response。

### 阶段二：启动辅助文档增强

新增：

```text
POST /api/v1/projects/{project_id}/requirements/{document_id}/analysis/{analysis_id}/enhance
```

返回：

```json
{
  "id": "reqenh-abc",
  "source_type": "requirement_auxiliary_enhancement_run",
  "source_id": "reqenh-abc",
  "project_id": "project-1",
  "document_id": "doc-1",
  "analysis_id": "analysis-1",
  "status": "queued",
  "summary": "辅助文档增强已提交。"
}
```

### 查询分析结果

复用：

```text
GET /api/v1/projects/{project_id}/requirements/{document_id}/analysis
```

响应中可增加增强状态：

```json
{
  "analysis": {},
  "latest_enhancement_run": {
    "id": "reqenh-abc",
    "status": "completed",
    "summary": "辅助文档增强完成，补强 3 项，仍待确认 5 项。"
  }
}
```

## 数据库设计

阶段一继续使用：

```text
requirement_analysis_runs
requirement_analyses
```

阶段二新增运行表：

```sql
CREATE TABLE IF NOT EXISTS requirement_auxiliary_enhancement_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  analysis_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN (
    'queued',
    'running',
    'completed',
    'failed'
  )),
  summary TEXT NOT NULL DEFAULT '',
  failure_reason TEXT NOT NULL DEFAULT '',
  enhanced_question_count INTEGER NOT NULL DEFAULT 0,
  applied_supplement_count INTEGER NOT NULL DEFAULT 0,
  conflict_count INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
  FOREIGN KEY(analysis_id) REFERENCES requirement_analyses(id) ON DELETE CASCADE
);
```

索引：

```sql
CREATE INDEX IF NOT EXISTS idx_requirement_aux_enhancement_project_created
ON requirement_auxiliary_enhancement_runs(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_requirement_aux_enhancement_document_created
ON requirement_auxiliary_enhancement_runs(document_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_requirement_aux_enhancement_analysis_created
ON requirement_auxiliary_enhancement_runs(analysis_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_requirement_aux_enhancement_status
ON requirement_auxiliary_enhancement_runs(status);
```

## 任务状态

阶段一状态沿用：

```text
queued -> running -> completed
                  -> needs_clarification
                  -> blocked
                  -> failed
```

阶段二状态：

```text
queued -> running -> completed
                  -> failed
```

辅助增强失败不应让阶段一分析失效。用户仍可查看和处理主需求分析结果。

## Operation Logs

阶段一沿用现有动作：

- `submit_requirement_analysis`
- `start_requirement_analysis`
- `finish_requirement_analysis`
- `fail_requirement_analysis`

阶段二新增动作：

- `submit_requirement_auxiliary_enhancement`
- `start_requirement_auxiliary_enhancement`
- `finish_requirement_auxiliary_enhancement`
- `fail_requirement_auxiliary_enhancement`

日志不得写入：

- 完整主需求 Markdown
- 完整辅助文档
- 完整 prompt
- 完整模型响应

日志可以写入：

- 问题数量
- 命中证据数量
- 补强数量
- 冲突数量
- 失败阶段
- 脱敏错误摘要

## 前端设计

需求分析 tab 中增加增强入口：

```text
初步需求
待确认问题
辅助文档增强状态
```

展示规则：

- 阶段一运行中：显示“正在分析主需求”。
- 阶段一完成且存在辅助文件：显示“辅助文档增强”按钮。
- 阶段二运行中：显示“正在从辅助文档查找答案”。
- 阶段二完成：显示补强数量、仍待确认数量、冲突数量。
- 阶段二失败：显示失败摘要，但保留阶段一分析结果。

按钮文案：

```text
从辅助文档找答案
```

不建议使用“自动合并辅助文档”等文案，避免让用户误解为需求归并。

## 验证和测试

### 后端单测

- 阶段一 input 不包含辅助文档全文。
- 阶段一不注册 `search_auxiliary_documents`。
- 阶段一 fake model 调用数最多 2 次。
- 阶段一输出 `applied_supplements` 必须为空。
- 阶段二 input 包含阶段一问题列表和多个辅助文章。
- 阶段二不注册 `search_auxiliary_documents`。
- 阶段二不暴露文件系统工具。
- 阶段二 fake model 调用数最多 2 次。
- 阶段二 delta 引用了输入辅助文章之外的文件或摘录时，validator 拒绝。
- 辅助文章无法回答的问题保持待确认。
- 辅助文章内容与主需求冲突时进入 conflicts。
- 阶段二失败不删除或覆盖原 analysis。

### 集成测试

- `/review` 创建阶段一 run，并最终写入 `requirement_analyses`。
- `/analysis/{analysis_id}/enhance` 创建阶段二 run。
- 阶段二完成后，`GET /analysis` 能看到合并后的补强结果。
- 阶段二失败时，`GET /analysis` 仍返回阶段一结果。
- 任务中心能展示两个 run 类型。

### 性能测试

构造：

- 主需求 20k chars。
- 辅助文档 5 个，每个 30k chars。
- 待确认问题 20 个。

断言：

- 阶段一 LLM 调用数 <= 2。
- 阶段二单批 LLM 调用数 <= 2。
- 不出现百万 token 级上下文。
- 普通阶段一目标耗时 <= 5 分钟。

## 迁移策略

第一步：

- 新增阶段一 `primary_agent.py`。
- `/review` 先切到主需求-only 分析。
- 保持现有 `RequirementAnalysisOutput` 和前端展示不变。

第二步：

- 新增 `enhancement_agent.py`。
- 新增辅助增强 API 和 run 表。
- 前端增加“从辅助文档找答案”按钮。

第三步：

- 下线当前 requirement_analysis 热路径中的 `create_agent + SkillsMiddleware + FilesystemMiddleware + ToolStrategy`。
- 保留旧文件一段时间作为 deprecated fallback，但默认不再使用。

第四步：

- 增加预算指标和性能回归测试。
- 后续如辅助文章过多或上下文仍不稳定，再新增 `evidence_index.py`，升级为 RAG 证据包。
- 如词频检索质量不足，再升级 BM25 或 embedding hybrid search。

## 风险和取舍

- 阶段一不查辅助文档，首次结果可能比旧流程少一些自动补强，但速度和稳定性显著提升。
- 阶段二直接传多个辅助文章，符合第一版快速落地目标，但辅助文章过多时仍可能慢或超过上下文。
- 阶段二不做 RAG，模型可能在长文章中漏找答案；这是第一版接受的取舍。
- 后续 RAG 版本会引入检索质量问题，需要通过 coverage 和用户反馈迭代。
- 两阶段会增加任务和状态管理复杂度，但能让失败隔离，辅助增强失败不影响主分析可用。
- 不让模型自由翻文件会降低“偶然发现答案”的概率，但换来可控成本和稳定耗时。

## 验收标准

- 点击“需求分析”后，阶段一不读取辅助文档、不调用辅助搜索工具。
- 阶段一完成后，即使存在辅助文档，也能先展示主需求分析结果。
- 点击“从辅助文档找答案”后，阶段二输入为阶段一问题列表和多个辅助文章 Markdown。
- 阶段二智能体在输入辅助文章中找答案、给推荐选项、识别冲突。
- 阶段二不能引用输入辅助文章之外的内容。
- 第一版不要求 RAG 或 evidence_packet。
- 普通文档阶段一最多 2 次 LLM 调用。
- 辅助增强单批最多 2 次 LLM 调用。
- 辅助增强失败不影响阶段一分析结果。
- 单测和集成测试覆盖上述约束。
