# 需求归并 Agent 与 Skill 边界规范

## 目标

修正当前“需求合并”实现边界，确保多来源需求归并由 `RequirementMergeAgent` 结合专用 Skill 完成分析、去重、冲突识别和业务模块重组，后端合并服务只负责流程编排、数据读取、输出校验和持久化。

本规范用于指导后续实现，不直接替代已有 `2026-05-23-requirement-merge-agent-implementation-spec.md`。已有规范偏数据契约和版本流程；本规范补足 Agent 代码、Skill 代码、合并服务职责边界。

## 问题背景

当前实现存在职责混乱风险：

- `RequirementMergeAgent` 只有 agent definition，缺少专用归并 Skill。
- 合并服务容易退化为本地算法或简单拼接，导致“看起来合并了，实际没有智能分析”。
- fallback 逻辑容易被误认为主路径。
- Agent prompt、Skill 规则、输出契约没有分层，后续维护时容易把业务判断写进服务层。

需要明确：

```text
API /merge
  -> 合并服务：读数据、组装输入、调用 Agent、校验输出、落库
  -> RequirementMergeAgent：执行需求分析和归并决策
  -> requirement_markdown_merge Skill：提供稳定的归并规则、冲突边界和输出格式要求
```

## 范围

本期包含：

- 新增 `RequirementMergeAgent` 专属 Skill。
- 将 `RequirementMergeAgent` 绑定该 Skill。
- 明确合并服务不得承担智能归并职责。
- 明确 Agent 输入、输出和失败处理。
- 增加测试验证 Agent、Skill、Service 的边界。

本期不包含：

- 文件上传、DOCX/PDF 转 Markdown。
- 需求评审问答。
- 知识库生成。
- 测试用例生成。
- 前端交互重设计。

## 文件结构

建议文件结构：

```text
apps/backend/app/agents/requirement_merge/
  __init__.py
  requirement_merge_agent.py
  skills/
    requirement_markdown_merge/
      SKILL.md
```

服务与契约：

```text
apps/backend/app/schemas/requirement_merge.py
apps/backend/app/services/requirement_merge_service.py
apps/backend/app/services/document_service.py
```

测试：

```text
apps/backend/tests/test_requirement_merge_service.py
apps/backend/tests/test_skill_loader.py
apps/backend/tests/test_agent_runtime.py
apps/backend/tests/test_document_service.py
```

## 职责边界

### RequirementMergeAgent

Agent 职责：

- 分析多个标准 Markdown 文件的业务含义。
- 识别重复、同义、补充、覆盖、废弃、冲突和待澄清内容。
- 按业务模块重组需求，不按来源文件简单拼接。
- 根据已解决冲突生成统一表述。
- 输出结构化 JSON，供服务层校验和落库。

Agent 不负责：

- 不读取数据库。
- 不读取本地文件路径。
- 不写入版本、冲突、覆盖矩阵或运行记录。
- 不调用上传或转换能力。
- 不把待澄清内容伪装为确定需求。
- 不绕过用户确认解决冲突。

### requirement_markdown_merge Skill

Skill 职责：

- 定义需求归并规则。
- 定义冲突与待澄清边界。
- 定义来源覆盖矩阵要求。
- 定义输出 JSON 格式要求。
- 定义 Markdown 输出结构。
- 明确禁止行为。

Skill 不负责：

- 不包含数据库、文件系统或 HTTP 接口逻辑。
- 不包含具体项目数据。
- 不要求模型调用外部工具。

### requirement_merge_service

合并服务职责：

- 从数据库读取当前需求文档、当前版本、可合并标准 Markdown、已解决冲突。
- 构造 `RequirementMergeInput`。
- 调用 `RequirementMergeAgent`。
- 校验 Agent 输出为 `RequirementMergeOutput`。
- 根据输出持久化：
  - `merged`：写入新版本、覆盖矩阵、变更日志，更新来源文件状态。
  - `conflict`：写入冲突记录，不生成新版本。
  - `preview`：写入预览运行记录，等待用户确认。
- 记录 Agent 运行失败、输出不合法等错误。

合并服务不负责：

- 不做业务模块智能归并。
- 不自行判断冲突最终结果。
- 不把简单拼接作为正常主流程。
- 不创造需求。

### fallback

fallback 仅允许作为兜底：

- 模型未配置。
- Agent Runtime 抛错。
- Agent 输出不是合法 JSON。
- Agent 输出不满足 `RequirementMergeOutput`。

fallback 要求：

- 必须显式记录 `fallback_used = true` 或在运行记录中留下可审计信息。
- 结果摘要必须体现是 fallback 生成，不能伪装为 Agent 分析结果。
- fallback 只能做保守合并：去重、按标题分组、显式标记来源。
- fallback 不得自动解决冲突。

## Agent Definition 要求

`requirement_merge_agent.py` 应定义：

```python
agent_definition = AgentDefinition(
    id="requirement_merge",
    name="需求归并智能体",
    description="分析并归并多来源标准 Markdown，识别冲突并输出覆盖矩阵。",
    instructions="...",
    skill_ids=("requirement_markdown_merge",),
    sort_order=20,
)
```

Agent instructions 只保留高优先级职责：

- 你是需求归并智能体。
- 必须遵循 `requirement_markdown_merge` Skill。
- 必须只返回符合契约的 JSON。
- 不得臆造需求。
- 不得绕过人工确认解决冲突。

详细归并规则必须放在 Skill 中，不应堆在 agent definition。

## Skill 内容要求

`SKILL.md` 必须至少包含以下章节：

```text
# Requirement Markdown Merge

## Mission
## Inputs
## Merge Rules
## Conflict Rules
## Clarification Rules
## Source Coverage Rules
## Markdown Output Rules
## JSON Output Contract
## Forbidden Behavior
## Final Checklist
```

### Merge Rules

必须包含：

- 按业务模块归并，不按文件顺序拼接。
- 同义需求只保留一份，但覆盖矩阵中标记重复来源。
- 补充性需求合入同一模块。
- 已有当前版本时，以当前版本为基线做增量分析。
- 已解决冲突是强约束，必须优先于来源文件原文。

### Conflict Rules

冲突仅指来源之间不能同时成立：

- 数值、阈值、流程互斥。
- 权限范围互斥。
- 状态机或业务规则互斥。
- 一个来源要求启用，另一个来源明确禁止。

不属于冲突：

- 表述不清。
- 缺少验收标准。
- 粒度不同但可以共存。
- 一个来源比另一个来源更详细。

### Clarification Rules

待澄清内容应进入 `coverage_status = pending_clarification`，不得写成确定需求。

### Source Coverage Rules

每个来源文件中的有效需求片段必须有覆盖项：

```json
{
  "mapping_id": "docmap-001",
  "source_heading": "登录认证",
  "source_excerpt": "连续 5 次登录失败后锁定账号",
  "target_module": "账号安全",
  "target_heading": "登录失败锁定",
  "coverage_status": "merged",
  "reason": "合入账号安全模块"
}
```

允许的 `coverage_status`：

- `merged`
- `duplicate`
- `conflict`
- `pending_clarification`
- `not_testable`
- `discarded`

### JSON Output Contract

Agent 必须只返回 JSON 对象：

```json
{
  "status": "merged",
  "markdown_content": "# 初始需求\n\n## 登录认证\n\n...",
  "markdown_preview": "",
  "merge_summary": "已归并 2 个标准文件，去重 3 处。",
  "diff_summary": "新增账号锁定规则。",
  "affected_modules": ["登录认证", "账号安全"],
  "source_file_ids": ["docmap-001", "docmap-002"],
  "coverage_items": [],
  "conflicts": []
}
```

`status` 取值：

- `merged`：可直接写版本。
- `conflict`：存在冲突，不得写版本。
- `preview`：增量合并预览，等待用户确认。

## 合并服务流程

### 初始合并

```text
1. 查询 document。
2. 查询所有 conversion_status in success/warning 且 mapping_status != discarded 的标准文件。
3. 读取 markdown_content。
4. 查询 resolved_conflicts。
5. 构造 RequirementMergeInput，merge_mode=initial。
6. 调用 RequirementMergeAgent。
7. 校验 RequirementMergeOutput。
8. status=merged 时写入版本、覆盖矩阵、变更日志。
9. status=conflict 时写入冲突，不写版本。
```

### 增量合并

```text
1. 查询 current_version 作为 base_version。
2. 查询 pending_merge 标准文件。
3. 构造 RequirementMergeInput，merge_mode=incremental。
4. 调用 RequirementMergeAgent。
5. status=preview 时保存预览，不更新 current_version。
6. 用户确认 preview 后再写入新版本。
```

### 冲突解决后再合并

```text
1. 用户保存 conflict resolution。
2. 再次调用 /merge。
3. resolved_conflicts 注入 Agent 输入。
4. Agent 必须把 resolution 作为强约束。
5. 无新冲突时生成版本。
```

## 错误处理

Agent 调用失败：

- 记录失败原因。
- 如果配置允许 fallback，则执行 fallback。
- 如果配置不允许 fallback，则返回明确错误。

Agent 输出非法：

- 不写版本。
- 不写冲突。
- 记录 merge_run.status = failed。
- 返回 `AGENT_OUTPUT_INVALID`。

建议第一版允许 fallback，但必须在返回和运行记录中可见。

## 验收标准

### Agent 与 Skill

- `requirement_merge` agent 能被 registry 发现。
- `requirement_markdown_merge` skill 能被 skill loader 发现。
- `build_agent(requirement_merge)` 后 instructions 包含 Skill 内容。
- `requirement_merge_agent.py` 绑定 `skill_ids=("requirement_markdown_merge",)`。

### 服务调用

- `/merge` 调用 `RequirementMergeAgent`，而不是直接执行本地拼接。
- Agent 返回 `merged` 时生成版本。
- Agent 返回 `conflict` 时只生成冲突，不生成版本。
- Agent 返回 `preview` 时只生成预览，不更新当前版本。
- Agent 输出非法时不会写入版本。

### 归并质量

- 两个文件中同义需求只在最终 Markdown 出现一次。
- 不同业务模块不会被统一塞进“合并需求”。
- 冲突内容不会被自动择一写入最终版本。
- 待澄清内容不会被写成确定需求。
- 每个来源有效片段都有 coverage item。

### 回归测试

必须通过：

```bash
cd apps/backend
./.venv/bin/python -m unittest tests.test_requirement_merge_service
./.venv/bin/python -m unittest tests.test_skill_loader
./.venv/bin/python -m unittest tests.test_document_service.DocumentServiceTest.test_merge_document_markdown_deduplicates_and_creates_initial_version
./.venv/bin/python -m unittest tests.test_document_service.DocumentServiceTest.test_merge_document_markdown_returns_conflict_without_creating_version
./.venv/bin/python -m unittest tests.test_document_service.DocumentServiceTest.test_resolved_conflict_allows_merge_to_continue
./.venv/bin/python -m unittest tests.test_document_service.DocumentServiceTest.test_incremental_merge_returns_preview_and_confirm_creates_version
```

如果 `tests.test_document_service` 全量存在与存储路径相关的既有失败，应单独记录，不得混同为需求归并失败。

## 实施顺序

1. 新增 `requirement_markdown_merge` Skill。
2. 修改 `RequirementMergeAgent` 绑定 Skill。
3. 修改合并服务，明确 Agent 主路径和 fallback 审计。
4. 增加 Agent/Skill loader 测试。
5. 增加 Agent 输出解析和非法输出测试。
6. 增加 `/merge` 编排测试。
7. 跑回归测试并记录剩余非归并问题。

## 禁止事项

- 禁止把本地 fallback 当主实现。
- 禁止在合并服务里写复杂业务归并规则。
- 禁止没有 Skill 只有几句 Agent instructions。
- 禁止 Agent 返回自然语言后由服务层猜 JSON。
- 禁止冲突未解决时写入新版本。
- 禁止没有覆盖矩阵就标记来源文件已合并。
