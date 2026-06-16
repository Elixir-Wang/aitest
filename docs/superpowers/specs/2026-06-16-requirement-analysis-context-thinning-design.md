# 需求分析 LangGraph 上下文瘦身规范

## 背景

当前需求分析流程已经拆成多个 LangGraph 节点：

```text
understand -> assess_quality -> clarify -> enhance
```

代码层面，节点之间共享同一个 `RequirementAnalysisState`，但 LLM 调用时并不会自动继承上一个节点的上下文。现有实现的问题不是 LangGraph 本身，而是节点间传参过厚：

- `quality.py` 把完整 `primary_markdown_content` 和完整 `understanding_result.model_dump_json(indent=2)` 一起塞进 prompt。
- `clarification.py` 再把完整 `understanding_result`、完整 `quality_assessment_result`，以及所有辅助文档全文一起拼进 prompt。

这会导致：

1. 上下文重复膨胀。
2. 下游节点被迫重读上游完整结果。
3. 三个节点的职责边界被 prompt 再次冲淡。
4. 长文档和大 JSON 更容易触顶。

本规范只解决一件事：**完成上一个节点后，不再把全部内容原样传给下一个节点**。

## 目标

- 保留当前三步 LLM 流程：`understand -> assess_quality -> clarify`。
- 保留 `enhance` 作为最终组装节点。
- 让每个下游节点只接收它真正需要的最小上下文。
- 保留完整结果用于最终输出和调试，但不再直接塞进下游 prompt。
- 用结构化 brief + evidence snippet 替代全文传递。

## 非目标

- 不合并成一个大 agent。
- 不引入新的 report 层来解决上下文问题。
- 不改变最终输出的结构化字段语义。
- 不要求 LangGraph 节点自动共享聊天历史。
- 不重做前端展示边界。

## 现状定位

### 1. 状态是共享的，但 prompt 不是自动共享的

`RequirementAnalysisState` 目前保存：

- `primary_content`
- `auxiliary_docs`
- `understanding`
- `quality`
- `clarification`
- `analysis_report`
- `enhanced_requirement`

这些字段可以继续保留在 state 中，但不应默认全部进入每个 LLM 节点 prompt。

### 2. 主要膨胀点

当前膨胀点在：

- `apps/backend/app/agents/requirement_analysis/agents/quality.py`
- `apps/backend/app/agents/requirement_analysis/agents/clarification.py`

质量节点把完整理解结果重新注入 prompt。澄清节点把完整理解结果、完整质量结果和所有辅助文档全文再次注入 prompt。

## 设计原则

1. **state 可厚，prompt 必薄**。
2. **完整结果留存，prompt 只传 brief**。
3. **证据可引用，不全文复述**。
4. **下游只看决策所需信息**。
5. **质量与澄清分工不倒退**。

## 方案

### 1. 需求理解节点

`understand` 仍然负责生成完整 `RequirementUnderstandingOutput`。

新增一个面向下游的轻量理解摘要：

```json
{
  "business_goal": "...",
  "modules": ["..."],
  "actors": ["..."],
  "p0_flows": ["..."],
  "p1_flows": ["..."],
  "state_objects": ["..."],
  "external_dependencies": ["..."],
  "evidence_refs": ["REQ-001", "REQ-008"]
}
```

这个摘要只用于下游节点 prompt，不用于替代最终完整理解结果。

### 2. 质量评估节点

`assess_quality` 仍然负责生成完整 `QualityAssessmentOutput`，但输入改为：

- 主需求文档的关键切片
- `understanding_brief`

不再传完整 `understanding_result.model_dump_json(indent=2)`。

质量节点额外生成 `quality_brief`，只保留下游澄清所需内容：

```json
{
  "decision": "needs_clarification",
  "blockers": [...],
  "top_issues": [
    {
      "id": "Q-001",
      "severity": "P0",
      "category": "testability",
      "summary": "...",
      "impact": "...",
      "evidence_refs": ["REQ-008"],
      "needs_human_decision": true
    }
  ]
}
```

### 3. 澄清节点

`clarify` 不再直接接收完整理解结果、完整质量结果和全文辅助文档。

它的输入改为：

- `quality_brief`
- 与 issue 关联的 evidence snippets

证据片段应按 issue 或关键词检索得到，而不是全文拼接。辅助文档只在命中的地方局部注入。

示例：

```json
{
  "issue_id": "Q-001",
  "evidence_snippets": [
    {
      "source": "primary",
      "ref": "REQ-008",
      "text": "..."
    },
    {
      "source": "auxiliary",
      "filename": "xxx.md",
      "text": "..."
    }
  ]
}
```

## 数据契约

建议在 `core/schemas.py` 中新增轻量结构：

- `RequirementUnderstandingBrief`
- `QualityAssessmentBrief`
- `EvidenceSnippet`

建议在 `core/state.py` 中增加可选字段：

- `understanding_brief`
- `quality_brief`
- `evidence_map`

完整结果字段继续保留：

- `understanding`
- `quality`
- `clarification`

## 节点边界

### understand

职责：

- 提取事实
- 形成完整理解结果
- 生成下游可复用的理解 brief

### assess_quality

职责：

- 识别质量问题
- 做 blocker / severity 判断
- 生成面向澄清的质量 brief

### clarify

职责：

- 把质量问题转成可人工裁决项
- 只使用最少证据片段
- 不回读完整上游结果

### enhance

职责：

- 组装最终输出
- 不再参与上下文传递设计

## 约束

- 不允许在 `quality.py` 中再把完整 `understanding_result` 作为 prompt 主体。
- 不允许在 `clarification.py` 中再把完整 `understanding_result`、完整 `quality_assessment_result` 和所有辅助文档全文直接拼接进 prompt。
- 不允许把完整上下文从 state 复制到下游 prompt。
- 不要求历史结果回写。

## 验收标准

- `quality` 节点不再注入完整 `understanding_result.model_dump_json(indent=2)`。
- `clarify` 节点不再注入完整 `understanding_result`、完整 `quality_assessment_result` 和所有辅助文档全文。
- 下游节点只接收 brief + snippets。
- 完整结构化结果仍然保留在最终输出中。
- 不需要把三个步骤合并成一个 skill。

## 推荐实现顺序

1. 在 state 和 schema 中增加 brief / evidence 结构。
2. 改造 `quality.py`，让它消费 `understanding_brief`。
3. 改造 `clarification.py`，让它消费 `quality_brief` + snippets。
4. 补 prompt 构造测试，确保不再传全文。
5. 跑后端验证，确认输出字段不变。

## 结论

这次改造的核心不是“换框架”，也不是“合并 skill”，而是把 LangGraph 的节点契约改成：

```text
完整结果留在 state
下游 prompt 只传 brief 和证据
```

这样可以保留现有三步职责，同时把上下文成本压下来。
