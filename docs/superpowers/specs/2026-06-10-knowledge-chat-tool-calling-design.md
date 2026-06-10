# 项目知识库对话工具调用 Spec

## 背景

当前项目知识库页面把每一次用户输入都当作知识库查询处理。即使用户只输入“你好”，后端也会收集最终需求文档和探索记录，并进入 `run_knowledge_query` 的 agentic search 链路。前端因此展示“正在读取最终需求文档和探索记录，并执行 agentic search。”，用户会误以为普通寒暄也在消耗项目知识库查询能力。

现有链路的核心入口是：

```text
POST /projects/{project_id}/knowledge/query
  -> query_project_knowledge
  -> _collect_query_input
  -> knowledge_query_service.run_knowledge_query
  -> codex_query.run_knowledge_query_with_codex
```

这个链路适合回答项目事实、需求规则、探索结果和来源依据问题，但不适合作为项目知识库 AI 的全部对话模式。

本 spec 将项目知识库 AI 调整为“LangChain 流式 Tool-Calling Chat Agent + Codex CLI Agentic Search 工具”的结构。LangChain Agent 默认正常多轮对话并流式输出自然语言；只有判断当前问题需要项目知识库内容时，才调用 `search_project_knowledge` 工具。该工具内部执行现有 Codex CLI agentic search。

## 目标

- 普通问候、闲聊、能力说明、写作辅助和基于用户当前输入的讨论，不触发知识库查询。
- 涉及项目需求、探索记录、业务规则、页面事实、测试风险和来源依据的问题，必须调用知识库查询工具。
- 保留现有 `/projects/{project_id}/knowledge/query` 兼容接口，并新增 `/projects/{project_id}/knowledge/query/stream` 作为页面主路径。
- 复用现有 `KnowledgeQueryInput`、`KnowledgeQueryOutput`、`source_refs`、`used_requirement_versions`、`used_exploration_runs` 和对话持久化表。
- 由 LangChain Agent 的 tool-calling 决策完成意图识别，而不是前端模式开关、关键词规则或独立意图分类接口。
- 普通聊天和知识库查询都写入同一套 `knowledge_conversations` / `knowledge_conversation_messages`，保持历史对话连续。
- 前端流式展示只展示用户可见自然语言，不把 `KnowledgeQueryOutput` JSON 作为聊天气泡内容。
- 前端通过流式 metadata 更新 `knowledge_queried`、来源引用和使用记录。

## 非目标

- 不做公司知识库问答。
- 不引入向量库、embedding 或 RAG 索引。
- 不改变项目知识库页面的基础布局。
- 不把 Codex CLI agentic search 暴露成新的公开 HTTP 接口；它只作为 LangChain 工具内部实现。
- 不让模型在知识库查询工具外读取项目文件。
- 不改变现有 Codex agentic search 的文件产物格式。

## 推荐方案

采用 LangChain 流式 tool-calling Agent：

```text
项目知识库聊天入口
  -> Knowledge Chat Agent (LangChain)
      -> 默认直接流式回答普通对话
      -> 必要时调用 search_project_knowledge LangChain tool
          -> _collect_query_input
          -> query_service.run_knowledge_query
          -> codex_query.run_knowledge_query_with_codex
          -> fallback_query_output
  -> 持久化 user / assistant message
  -> 流式返回 message_delta + metadata + done
```

不推荐独立 intent classifier，原因是：

- 会额外增加一次模型调用。
- 容易把“这个模块呢？”这类依赖历史上下文的问题误判。
- 分类器和最终回答模型割裂，边界会变成两套 prompt。
- 仍需要回答模型再次判断如何使用分类结果。
- LangChain 的 tool-calling 决策已经承担了意图识别职责，独立分类器会制造重复边界。

不推荐纯关键词规则，原因是：

- “你好”“帮我改写这段话”很好判，但真实项目问题经常是上下文省略表达。
- 关键词规则无法可靠区分“登录是什么”与“这个项目登录规则是什么”。
- 后续补规则会持续膨胀，维护成本高。

不推荐前端模式开关作为主方案，原因是：

- 用户并不总是知道当前问题是否需要查资料。
- 同一个输入框里自然会混合普通对话和项目事实提问。
- 这会把模型应该承担的判断转嫁给用户。

## Agent 职责

新增知识库聊天 Agent，建议放在：

```text
apps/backend/app/agents/knowledge_chat/
  agent.py
  service.py
  schemas.py
```

职责边界：

- `agent.py` 构造 LangChain agent，挂载 `search_project_knowledge` 工具。
- `service.py` 执行一次聊天，整理模型输入、调用 agent、解析输出。
- `schemas.py` 定义内部结构化输出模型。

知识库 service 仍负责：

- 校验项目和对话归属。
- 读取历史消息。
- 创建或更新 conversation。
- 调用知识库聊天 Agent。
- 持久化 user / assistant message。
- 记录 operation log。

## 模型选择

第一版复用现有 `knowledge_query` capability。

理由：

- 当前知识库查询已经有独立模型分配。
- 聊天 Agent 和查询工具都属于项目知识库 AI 能力边界。
- 避免新增模型配置项导致管理员必须重新配置。

后续如果需要区分普通聊天模型和 agentic search 模型，可以新增 capability：

```text
knowledge_chat
knowledge_query
```

第一版不做这个拆分。

## 工具定义

Agent 只挂载一个业务工具：

```text
search_project_knowledge(question: str) -> KnowledgeQueryOutput
```

这是 LangChain tool-calling Agent 可调用的工具。Codex CLI agentic search 不直接暴露给前端或聊天模型自由调用，而是作为该工具的内部执行器。

工具输入：

- `question`：模型重写后的知识库查询问题。

工具上下文由后端闭包提供，不暴露给模型自由选择：

- `project_id`
- `include_requirements`
- `include_explorations`
- `conversation_history`

工具内部复用现有逻辑：

```text
_collect_query_input(project_id, request, history)
  -> blockers 存在：返回“无法查询项目知识库”
  -> blockers 不存在：query_service.run_knowledge_query(input_data)
      -> codex_query.run_knowledge_query_with_codex(input_data)
      -> Codex CLI --search exec
  -> run_knowledge_query 异常：fallback_query_output(input_data)
```

工具返回的是结构化 `KnowledgeQueryOutput`，用于给 LangChain Agent 提供项目事实、来源引用和使用记录。Agent 必须基于工具结果生成最终用户可见回答；工具返回 JSON 本身不得直接进入聊天气泡。

## Prompt 规则

系统提示必须包含以下边界：

```text
你是 AI 测试系统的项目知识库 AI。

默认情况下，你可以像普通助手一样进行多轮对话。
以下情况不要调用 search_project_knowledge：
- 问候、闲聊、确认在线状态。
- 介绍你能做什么。
- 普通写作、改写、翻译、总结用户刚输入的文本。
- 只讨论对话本身，不需要项目事实。

以下情况必须调用 search_project_knowledge：
- 用户询问当前项目的需求、业务规则、模块范围、页面、流程、接口、测试风险。
- 用户要求基于最终需求文档或探索记录回答。
- 用户要求来源、依据、引用、文档位置。
- 用户追问上一轮中已经涉及的项目事实。

不得凭常识编造项目事实。
如果问题需要项目事实，要调用工具；如果工具没有找到依据，要说明缺口。
如果没有调用工具，source_refs 必须为空。
```

## 流式输出契约

项目知识库页面使用 SSE 流式接口：

```text
POST /projects/{project_id}/knowledge/query/stream
```

流式事件：

```text
message_delta：只包含用户可见自然语言增量。
metadata：包含持久化后的 KnowledgeQueryResult。
done：本轮完成。
error：本轮失败。
```

`message_delta` 严禁发送完整 `KnowledgeQueryOutput` JSON。结构化字段只允许出现在 `metadata.result` 中。

`metadata.result` 保持现有响应形状并增加 `knowledge_queried`：

```python
{
    "conversation": KnowledgeConversation,
    "messages": [user_message, assistant_message],
    "answer": str,
    "source_refs": list[KnowledgeSourceRef],
    "used_requirement_versions": list[str],
    "used_exploration_runs": list[str],
    "knowledge_queried": bool,
}
```

兼容接口 `POST /projects/{project_id}/knowledge/query` 可以继续返回同一结构，但项目知识库页面主路径应使用 `/query/stream`。

普通聊天输出：

```text
source_refs = []
used_requirement_versions = []
used_exploration_runs = []
```

知识库查询输出：

```text
source_refs = 工具返回的来源引用
used_requirement_versions = 工具使用的需求版本
used_exploration_runs = 工具使用的探索记录
knowledge_queried = true
```

## 后端数据流

### 普通聊天

```text
1. 用户输入“你好”
2. query_project_knowledge 创建或读取 conversation
3. 读取最近 MAX_HISTORY_MESSAGES 条历史
4. 调用 Knowledge Chat Agent
5. Agent 判断不需要项目事实，不调用工具
6. Agent 通过 LangChain 流式消息输出普通回答
7. 后端将回答文本保存为 assistant message
8. metadata 返回 source_refs=[]、knowledge_queried=false
```

### 知识库查询

```text
1. 用户输入“登录规则是什么？”
2. query_project_knowledge 创建或读取 conversation
3. 读取最近 MAX_HISTORY_MESSAGES 条历史
4. 调用 Knowledge Chat Agent
5. Agent 判断需要项目事实，调用 search_project_knowledge
6. 工具收集最终需求文档和探索记录
7. 工具执行 Codex CLI agentic search
8. 工具返回结构化 KnowledgeQueryOutput 给 LangChain Agent
9. Agent 基于工具结果流式生成最终自然语言回答
10. 后端保存 user message 和 assistant message
11. metadata 返回 source_refs、used_* 字段和 knowledge_queried=true
```

## 前端行为

前端项目知识库聊天使用 `/query/stream`。

`knowledge_queried` 用途：

- `false`：普通聊天，本轮没有查询知识库。
- `true`：本轮调用过知识库查询工具。

前端不得通过 `source_refs.length > 0 || used_requirement_versions.length > 0 || used_exploration_runs.length > 0` 推断是否查询过知识库，因为“查了但没有来源”也必须显示为一次知识库查询。

聊天气泡渲染规则：

```text
message_delta -> 追加到 assistant 气泡正文。
metadata.result.source_refs -> 渲染来源引用。
metadata.result.used_* -> 保存使用记录。
metadata.result.knowledge_queried -> 记录本轮是否查库。
error -> 移除空 assistant 气泡或显示错误气泡。
```

如果后端在调用工具前没有阶段事件，前端只显示普通等待状态，避免对所有问题都展示“正在读取最终需求文档和探索记录”。

## Operation Log

现有 operation log 的 action 仍可使用 `query`，但 summary 应区分：

```text
普通聊天：项目知识库 AI 普通对话。
知识库查询：查询项目知识库。
```

`after` 建议增加：

```python
{
    "question": question,
    "conversation_id": conversation_id,
    "knowledge_queried": bool,
    "source_versions": source_version_ids,
    "exploration_runs": exploration_run_ids,
}
```

普通聊天时 `source_versions` 和 `exploration_runs` 为空。

## 测试策略

### 后端单元测试

新增或扩展 `apps/backend/tests/test_knowledge_conversations.py`：

1. 普通问候不调用知识库工具。
   - 输入：`你好`
   - 断言：`run_knowledge_query` 未被调用。
   - 断言：返回 assistant message。
   - 断言：`source_refs=[]`、`used_requirement_versions=[]`、`knowledge_queried=false`。

2. 项目事实问题调用知识库工具。
   - 输入：`登录规则是什么？`
   - 断言：`run_knowledge_query` 被调用一次。
   - 断言：返回来源字段。
   - 断言：`knowledge_queried=true`。

3. 多轮追问能基于历史决定调用工具。
   - 第一轮：`登录规则是什么？`
   - 第二轮：`这个模块还要补哪些测试？`
   - 断言：第二轮历史包含前一轮 user 和 assistant。
   - 断言：第二轮可以调用工具。

4. 工具异常时仍使用现有 fallback。
   - monkeypatch `run_knowledge_query` 抛错。
   - 断言：返回 `_fallback_query_output` 的确定性摘要。

5. 流式普通对话不把结构化 JSON 发给前端。
   - 模拟 Agent 输出 `KnowledgeQueryOutput` 或最终 assistant message。
   - 断言：`message_delta` 只包含 answer 文本。
   - 断言：`metadata.result` 包含 `knowledge_queried=false` 和空来源字段。

6. 流式知识库查询通过 metadata 返回来源。
   - 模拟工具返回 `source_refs`、`used_requirement_versions`。
   - 断言：assistant 气泡正文是自然语言回答。
   - 断言：来源引用只从 `metadata.result.source_refs` 更新。

### Agent 边界测试

为了避免测试依赖真实模型，Knowledge Chat Agent service 应支持 monkeypatch 模型结果或工具调用结果。

测试重点不是模型智能，而是后端路由：

- Agent 不调用工具时，后端不收集知识库输入。
- Agent 调用工具时，后端只通过封装工具访问项目材料。
- 工具返回的 `source_refs` 被写入 assistant message。
- Codex CLI agentic search 只在 `search_project_knowledge` 工具内部被调用。

### 前端冒烟测试

手动或 Playwright 冒烟：

- 打开 `/knowledge`。
- 输入 `你好`。
- assistant 气泡流式展示自然语言，不显示 `{ "answer": ... }` JSON。
- 页面不出现“正在读取最终需求文档和探索记录”固定文案。
- 输入 `登录规则是什么？`。
- 回答区域能展示来源引用。

## 迁移步骤

1. 使用或扩展 `KnowledgeQueryOutput` 作为聊天 Agent 的结构化结果，包含 `knowledge_queried`。

2. 新增 Knowledge Chat Agent，并使用 LangChain `create_agent` 挂载 `search_project_knowledge` 工具。

3. 将现有知识库查询逻辑包成 `search_project_knowledge` LangChain 工具，工具内部调用 Codex CLI agentic search。

4. 修改 `query_project_knowledge`：
   - 不再直接调用 `_collect_query_input`。
   - 改为调用 Knowledge Chat Agent。
   - 根据 Agent 输出持久化消息和 operation log。

5. 新增 `stream_project_knowledge_query`：
   - 对 `message_delta` 只转发自然语言文本。
   - 在最终 `metadata` 中返回 conversation、messages、answer、source_refs、used_* 和 `knowledge_queried`。
   - 保存消息和 operation log 后再发最终 metadata。

6. 保留 `_collect_query_input`、`_fallback_query_output` 和 Codex query 链路，供工具复用。

7. 前端改用 `/query/stream`，将 `message_delta` 追加到同一个 assistant 气泡，将 `metadata.result` 用于来源引用和会话状态。

8. 补后端测试、前端 lint 和前端冒烟验证。

## 风险与约束

- 模型可能误判是否需要调用工具。通过 prompt 边界和回归测试覆盖常见输入降低风险。
- 第一版可以没有“工具开始/结束”阶段事件，前端无法实时知道工具何时被调用。固定 loading 文案应避免误导。
- LangChain structured output 可能把 `KnowledgeQueryOutput` JSON 放在消息内容里。后端必须从结构化结果或最终消息中提取 answer，不能把完整 JSON 作为 `message_delta`。
- 普通聊天也依赖 `knowledge_query` 模型配置；如果该能力未配置，普通聊天也会失败。第一版接受这个约束，因为原知识库查询本来也依赖该配置。
- 如果后续希望普通聊天降级到确定性回复，需要另行定义无模型 fallback，本 spec 不包含。

## 验收标准

- 用户输入“你好”时，不执行 `run_knowledge_query`。
- 用户输入“你好”时，聊天气泡只显示自然语言回答，不显示 `KnowledgeQueryOutput` JSON。
- 用户输入“登录规则是什么？”时，LangChain Agent 调用 `search_project_knowledge` 工具，工具内部执行现有 Codex CLI agentic search 链路。
- 普通聊天和知识库查询都能保留同一个 conversation 的多轮历史。
- 普通聊天返回空来源字段。
- 知识库查询返回来源引用和使用过的需求/探索 ID。
- 前端通过 `/query/stream` 流式更新同一个 assistant 气泡，并通过 metadata 更新来源引用。
- 前端不再对所有输入显示“正在读取最终需求文档和探索记录”。
