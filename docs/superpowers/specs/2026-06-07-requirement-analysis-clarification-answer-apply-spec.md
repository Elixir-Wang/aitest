# 待确认问题答复回写初步需求 Spec

## 背景

现有需求分析流程已经把分析结果分为：

- `初步需求`：`requirement_analyses.output_json.preliminary_requirement_markdown`
- `待确认问题`：`output_json.clarification_questions` 与 `output_json.conflicts`
- `最终需求`：用户点击 `转为最终需求` 后才写入 `source_document_versions`

下一步需要让用户在 `待确认问题` 页面逐条处理问题：系统给出问题、两个推荐选项、一个暂不处理选项，以及手动输入框。用户选择或输入后，后端应把确认答案可追溯地写回当前 `初步需求`，但不能绕过最终需求确认流程。

## 目标

- 每个待确认问题展示固定交互结构：问题、两个推荐选项、暂不处理、自定义输入。
- 用户提交答案后，保存人工答复记录。
- 对需要写入需求的答案，更新当前分析结果的 `preliminary_requirement_markdown`。
- 保留问题 ID、答案来源、应用状态、写入位置和审计日志。
- 已答复的问题不再作为未处理待确认项展示，但仍可查看历史。
- 初步需求被人工答复更新后，仍需用户点击 `转为最终需求` 才生成最终需求版本。

## 非目标

- 不让辅助文档主动扩大主需求范围。
- 不把人工答复直接写入最终需求版本。
- 不重跑完整需求分析作为答复提交的默认动作。
- 不为第一版创建一个新的长流程智能体。
- 不要求前端解析 Markdown 来判断问题是否已处理。

## 页面交互

待确认问题每个条目使用如下结构：

```text
问题：xxx

推荐选项：
1. 选项 A
2. 选项 B
3. 暂不处理

自定义说明：
[手动输入框]

[保存答复]
```

推荐选项要求：

- 必须是可以直接落入需求文本的业务答案，不是解释性废话。
- 每个选项携带 `answer_markdown`，便于后端写入初步需求。
- `暂不处理` 不更新初步需求，只记录该问题被用户跳过。
- 如果用户填写自定义说明，以自定义说明为最终答案；已选推荐项可作为参考来源。

前端状态：

| 状态 | 展示 |
| --- | --- |
| 未答复 | 显示选项和输入框 |
| 已应用 | 显示已写入初步需求、写入时间、答案摘要，可允许重新编辑 |
| 暂不处理 | 显示暂不处理，可重新打开 |
| 应用失败 | 显示失败原因，可重试 |

## 输出 Schema 扩展

在现有 `RequirementUnresolvedFinding` 上补充推荐选项，不改变问题本身含义：

```python
class RequirementClarificationOption(BaseModel):
    id: str
    label: str
    answer_markdown: str
    rationale: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"


class RequirementUnresolvedFinding(BaseModel):
    id: str
    module_key: str
    module_name: str
    issue_type: Literal[
        "missing_answer",
        "conflict",
        "out_of_scope",
        "weak_evidence",
        "source_unclear",
        "other",
    ]
    question: str
    reason: str
    impact: str
    severity: Literal["blocker", "major", "minor"] = "major"
    primary_excerpt: str = ""
    evidence: list[RequirementEvidenceReference] = Field(default_factory=list)
    recommended_options: list[RequirementClarificationOption] = Field(default_factory=list, max_length=2)
```

说明：

- 第一版让需求分析智能体直接生成两个推荐选项。
- 如果历史数据没有 `recommended_options`，前端仍展示问题和自定义输入框。
- 推荐选项不足两个时，前端展示已有选项，不伪造答案。

## 数据模型

新增表 `requirement_clarification_answers`，不要把答复混进 `operation_logs` 或只塞在 `output_json` 里。答复是业务数据，需要可重放和可审计。

```sql
CREATE TABLE IF NOT EXISTS requirement_clarification_answers (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  analysis_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  answer_type TEXT NOT NULL CHECK(answer_type IN (
    'recommended_option',
    'custom',
    'defer'
  )),
  selected_option_id TEXT NOT NULL DEFAULT '',
  answer_markdown TEXT NOT NULL DEFAULT '',
  user_note TEXT NOT NULL DEFAULT '',
  apply_status TEXT NOT NULL CHECK(apply_status IN (
    'not_applicable',
    'applied',
    'failed'
  )),
  insertion_anchor TEXT NOT NULL DEFAULT '',
  failure_reason TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
  FOREIGN KEY(analysis_id) REFERENCES requirement_analyses(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_requirement_clarification_answers_latest
ON requirement_clarification_answers(analysis_id, question_id);
```

如果需要保留多次编辑历史，把唯一索引去掉，增加 `superseded_by_answer_id` 或 `is_current`。第一版推荐唯一记录覆盖更新，复杂度更低。

## 后端接口

### 保存并应用答复

```http
POST /api/v1/projects/{project_id}/requirements/{document_id}/analysis/{analysis_id}/clarification-answers
```

请求体：

```json
{
  "question_id": "q-001",
  "answer_type": "recommended_option",
  "selected_option_id": "option-a",
  "custom_answer": "",
  "defer": false
}
```

字段规则：

| 字段 | 规则 |
| --- | --- |
| `question_id` | 必须存在于该 analysis 的 `clarification_questions` 或 `conflicts` |
| `answer_type=recommended_option` | `selected_option_id` 必须存在于该问题的 `recommended_options` |
| `answer_type=custom` | `custom_answer` 必须非空 |
| `answer_type=defer` | 不更新初步需求，只记录暂不处理 |

成功响应：

```json
{
  "answer": {
    "id": "reqanswer-xxx",
    "question_id": "q-001",
    "answer_type": "recommended_option",
    "selected_option_id": "option-a",
    "answer_markdown": "验证码有效期为 5 分钟。",
    "apply_status": "applied",
    "insertion_anchor": "登录验证/验证码规则",
    "created_at": "2026-06-07T10:00:00"
  },
  "analysis": {
    "id": "reqana-xxx",
    "status": "needs_clarification",
    "output": {
      "preliminary_requirement_markdown": "# 更新后的初步需求..."
    }
  }
}
```

### 查询答复

```http
GET /api/v1/projects/{project_id}/requirements/{document_id}/analysis/{analysis_id}/clarification-answers
```

返回当前 analysis 下所有问题答复，用于页面回显。

## 回写初步需求流程

后端保存答复时执行：

```text
1. 校验 analysis 属于 document 和 project
2. 校验 analysis 不是已 finalize 状态
3. 从 output_json 中找到 question_id
4. 解析最终答案：
   - 推荐选项：使用 option.answer_markdown
   - 自定义：使用 custom_answer
   - 暂不处理：只保存 answer，不改初步需求
5. 定位写入位置
6. 更新 output_json.preliminary_requirement_markdown
7. 更新 output_json.clarification_questions/conflicts 中该问题的 answer 状态
8. 更新 requirement_analyses.output_json、analysis_summary、draft_content_hash
9. 写 operation_logs
10. 返回最新 analysis
```

### 写入位置

第一版不要让模型自由改整篇 Markdown。推荐使用确定性规则：

1. 优先使用问题的 `module_name` 或 `module_key` 找初步需求中的对应章节。
2. 找到章节后，在章节末尾追加：

```markdown
> 人工确认
> 问题：xxx
> 答案：xxx
```

3. 找不到章节时，追加到文档末尾的 `## 人工确认补充`。
4. 每次写入带稳定标记，方便重复编辑时替换而不是重复追加：

```markdown
<!-- clarification-answer:q-001:start -->
> 人工确认
> 问题：xxx
> 答案：xxx
<!-- clarification-answer:q-001:end -->
```

如果用户重新编辑同一个问题，后端只替换该标记块。

## 是否需要单独智能体

第一版不需要单独智能体。

推荐架构：

```text
需求分析智能体
  负责：识别问题、生成两个推荐选项、产出初步需求

ClarificationAnswerService
  负责：校验用户答案、保存答复、确定性写回初步需求、记录日志
```

原因：

- 用户已经给出答案，回写是受控编辑，不是开放式分析任务。
- 单独智能体容易把用户答案改写、扩展或引入新范围。
- 确定性写入更容易测试、追溯和回滚。

只有在后续出现以下需求时，再考虑新增一个轻量 `requirement_clarification_apply` 智能体：

- 需要把答案自然融合到原章节语句中，而不是追加确认块。
- 需要同时改写多个章节并保持全文风格一致。
- 需要根据答案重新计算测试场景、验收标准或风险项。

即便新增，也应该是小型编辑智能体，不是新的需求分析智能体；输入必须限制为 `preliminary_requirement_markdown + question + user_answer`，输出必须是结构化 patch，不能直接产出自由文本整篇需求。

## 前端数据契约

前端每个问题条目需要组合：

- `question`
- `recommended_options[0..1]`
- 固定 `defer` 选项
- `custom_answer` 输入框
- 已保存的 `answer`

提交策略：

- 选择推荐项后可以直接保存。
- 填写自定义内容后，以自定义内容优先。
- 选择暂不处理时清空待提交自定义内容，但保留输入框草稿由前端自行决定。

## 验证

后端测试至少覆盖：

- 推荐选项答复能写入初步需求。
- 自定义答复能写入初步需求。
- 暂不处理不修改初步需求。
- 同一问题重复答复会替换原标记块，不重复追加。
- 已 finalize 的 analysis 禁止继续修改。
- question_id 不存在时报错。
- selected_option_id 不存在时报错。

前端测试至少覆盖：

- 每个问题展示两个推荐选项、暂不处理、自定义输入框。
- 保存后问题状态变为已应用。
- 暂不处理后问题状态变为暂不处理。
- 初步需求 tab 能看到人工确认补充内容。
