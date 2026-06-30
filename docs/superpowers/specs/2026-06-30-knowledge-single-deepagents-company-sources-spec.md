# 知识库问答单 DeepAgents 重构 Spec

## 背景

当前知识库问答链路经历过多次演进，历史上存在过 Codex CLI agentic search、LangChain tool-calling chat agent、deepagents 文件检索 agent 等多种实现口径。运行时已经逐步迁移到 LangChain / deepagents，但知识库问答仍保留“两层 Agent”结构：

```text
Knowledge Chat Agent (LangChain create_agent)
  -> search_project_knowledge tool
      -> Knowledge Query Agent (deepagents)
```

该结构带来几个问题：

- 职责重复：外层 Agent 判断是否查库并改写答案，内层 Agent 又需要判断是否读取知识库文件。
- 来源易丢失：工具返回 `KnowledgeQueryOutput` 后，外层 Agent 需要再合并来源和最终回答。
- 流式复杂：外层 LangChain `astream(stream_mode=["messages", "values"])` 会暴露模型网关兼容问题。
- 架构难维护：旧 Codex 设计、LangChain chat agent 和 deepagents query agent 的边界不清晰。

本 spec 将知识库问答统一重构为一个 deepagents agent：服务层只负责收集项目最终需求和公司知识库文件，单个 deepagents agent 同时完成意图判断、文件检索、回答生成和来源引用输出。

## 目标

- 知识库问答只保留一个 deepagents agent 作为唯一智能体执行核心。
- 默认检索当前选择项目的最终需求文档和公司知识库。
- 保留普通闲聊能力；闲聊不读取知识库，`knowledge_queried=false`。
- 项目事实、需求规则、流程、接口、测试建议、来源依据类问题必须读取知识库，`knowledge_queried=true`。
- 项目最终需求优先级高于公司知识库。
- 公司知识库作为通用测试方法、平台规范、模板、跨项目经验和团队方法论来源。
- 保留现有对话历史、SSE 流式输出、operation log、fallback 摘要和前端结果形状。
- 清理旧 Codex agentic-search 和 LangChain `knowledge_chat` 双 Agent 口径。

## 非目标

- 不引入向量库、embedding、外部 RAG 服务或索引构建。
- 不改变公司知识库 Obsidian 式目录维护能力。
- 不改变最终需求文档生成、版本发布和归档逻辑。
- 不让前端决定是否查项目最终需求或公司知识库；后端默认收集。
- 不在本次拆分 `knowledge_chat` 和 `knowledge_query` 两套模型配置。
- 不让模型直接访问真实文件系统路径；agent 只读取后端提供的虚拟文件。

## 目标架构

```text
前端知识库问答
  -> POST /api/v1/projects/{project_id}/knowledge/query/stream
  -> app.services.knowledge.service
      -> 校验项目、用户、对话归属
      -> 收集对话历史
      -> 收集当前项目最终需求文档
      -> 收集公司知识库 Markdown 文件
      -> 构造 KnowledgeQueryInput
      -> app.agents.knowledge.service.stream_knowledge_agent
          -> create_deep_agent(...)
          -> 虚拟文件系统检索
          -> KnowledgeQueryOutput
      -> 持久化 user / assistant message
      -> 记录 operation log
      -> SSE 返回 message_delta / metadata / done
```

同步兼容接口仍保留：

```text
POST /api/v1/projects/{project_id}/knowledge/query
```

该接口直接调用同一个 deepagents agent 的非流式执行入口。

## 默认检索范围

默认来源包含两类：

| 来源 | 默认启用 | 用途 | 优先级 |
| --- | --- | --- | --- |
| 项目最终需求文档 | 是 | 当前项目业务事实、流程、接口、状态、权限、验收规则 | 最高 |
| 公司知识库 | 是 | 通用测试方法、平台规范、模板、跨项目经验、团队方法论 | 次高 |

冲突处理规则：

- 如果项目最终需求和公司知识库冲突，以项目最终需求为准。
- 公司知识库不能覆盖项目需求中的业务事实。
- 如果公司知识库只提供通用建议，回答中需要表达为“可参考”而不是项目事实。
- 如果项目最终需求缺失而公司知识库有通用规则，需要说明“项目需求未明确，以下为公司知识库通用建议”。

## 目录与模块边界

目标文件结构：

```text
apps/backend/app/agents/knowledge/
  __init__.py
  agent.py
  prompts.py
  schemas.py
  service.py
```

### `agent.py`

职责：

- 构造唯一 deepagents agent。
- 使用 `StateBackend` 或等价内存后端承载虚拟文件。
- 设置 `response_format=KnowledgeQueryOutput`。
- 不挂载额外业务 tool；只使用 deepagents 内置文件操作能力。

### `service.py`

职责：

- 提供 `run_knowledge_agent(input_data)`。
- 提供 `stream_knowledge_agent(input_data, show_thinking=False)`。
- 构建 deepagents payload：
  - `messages`
  - `files`
- 解析 deepagents 结果为 `KnowledgeQueryOutput`。
- 流式输出只暴露用户可见自然语言和最终 metadata。

### `schemas.py`

合并并替代原 `app.agents.knowledge_chat.schemas`。

建议模型：

```python
class KnowledgeSourceDocumentInput(BaseModel):
    source_type: Literal["requirement", "company_knowledge"]
    source_id: str
    source_title: str
    project_id: str = ""
    project_name: str = ""
    document_id: str = ""
    document_name: str = ""
    version_id: str = ""
    version_no: int | None = None
    base_id: str = ""
    base_name: str = ""
    folder_path: str = ""
    file_id: str = ""
    file_name: str = ""
    markdown_content: str
```

`KnowledgeSourceRef` 需要支持来源类型：

```python
class KnowledgeSourceRef(BaseModel):
    source_type: Literal["requirement", "company_knowledge"]
    source_id: str
    source_title: str
    project_id: str = ""
    project_name: str = ""
    document_id: str = ""
    document_name: str = ""
    version_id: str = ""
    version_no: int | None = None
    base_id: str = ""
    base_name: str = ""
    file_id: str = ""
    file_name: str = ""
    excerpt: str = ""
```

`KnowledgeQueryOutput` 保持现有字段，并增加公司知识库使用记录：

```python
class KnowledgeQueryOutput(BaseModel):
    answer: str
    source_refs: list[KnowledgeSourceRef] = Field(default_factory=list)
    used_requirement_versions: list[str] = Field(default_factory=list)
    used_company_knowledge_files: list[str] = Field(default_factory=list)
    used_exploration_runs: list[str] = Field(default_factory=list)
    knowledge_queried: bool = False
```

`used_exploration_runs` 暂时保留兼容字段，但本次默认检索范围不包含探索记录；后续如恢复探索来源，应按同一 source document 模型扩展 `source_type="exploration"`。

## 虚拟文件系统

deepagents 只读取后端构造的虚拟文件：

```text
README.md
requirements/{project_name}/{document_name}-v{version_no}.md
company-knowledge/{base_name}/{folder_path}/{file_name}.md
```

每个文件顶部必须包含元数据注释：

```markdown
<!-- source_metadata: {"source_type":"requirement","source_id":"docver-xxx",...} -->
```

```markdown
<!-- source_metadata: {"source_type":"company_knowledge","source_id":"gkfile-xxx",...} -->
```

Agent 生成 `source_refs` 时必须使用 `source_metadata` 中的字段，不能凭文件名猜测来源 ID。

`README.md` 内容包含：

- 本次可检索来源清单。
- 来源类型说明。
- 来源优先级。
- 冲突处理规则。

## Prompt 规则

系统提示必须包含以下规则：

```text
你是 AI 测试系统的知识库问答智能体。

你只能使用本次提供的虚拟 Markdown 文件作为项目事实和公司知识来源。

默认来源包含：
1. requirements/ 下的当前项目最终需求文档。
2. company-knowledge/ 下的公司知识库文件。

来源优先级：
1. 项目最终需求文档是当前项目业务事实的最高依据。
2. 公司知识库只提供通用规范、测试方法、模板和跨项目经验。
3. 模型通用知识只能用于语言组织，不得补充业务事实。

如果用户只是问候、闲聊、确认在线或询问你能做什么，不要读取知识库，直接简短回答，knowledge_queried=false。

如果用户询问需求、业务规则、模块范围、页面、流程、接口、权限、状态、测试风险、测试建议、来源依据，必须先读取知识库文件，knowledge_queried=true。

如果项目最终需求和公司知识库冲突，以项目最终需求为准。

回答项目事实时必须来自项目最终需求。
回答通用测试建议时可以引用公司知识库。
如果只有公司知识库有依据而项目最终需求未说明，必须明确说明项目需求未明确。

所有 source_refs 必须来自文件顶部 source_metadata。
```

## 后端收集逻辑

### 项目最终需求

继续复用现有最终需求收集逻辑：

```text
document_repo.list_by_project
  -> doc.current_version_id
  -> document_repo.find_version
  -> resolve_stored_path(version.file_path)
  -> markdown_content
```

如果项目没有最终需求：

- 问题需要项目事实时，返回 blocker。
- 如果只有公司知识库可用，agent 可以回答通用建议，但必须说明项目需求缺失。

### 公司知识库

新增收集函数：

```python
def _collect_company_knowledge_sources(db, request) -> tuple[list[KnowledgeSourceDocumentInput], list[str]]:
    ...
```

第一版默认收集所有可用公司知识库 Markdown 文件。

可用条件：

- 公司知识库未删除。
- 文件转换成功或已有 Markdown 内容。
- 当前用户有读取公司知识库权限。

文件内容读取：

- 优先读取 `markdown_path`。
- 如果 markdown 文件缺失，跳过该文件并记录 blocker 或 warning。
- 不读取 raw 原始文件作为 agent 输入。

性能保护：

- 单文件内容超过上限时截断，并在文件头标记已截断。
- 总输入字符超过上限时按知识库更新时间、文件 sort_order 或目录顺序截断。
- 截断行为需要在 `README.md` 中说明。

## 请求参数

`KnowledgeQueryRequest` 建议增加字段：

```python
include_requirements: bool = True
include_company_knowledge: bool = True
```

如果前端暂时不提供开关：

- 后端默认 `include_requirements=True`。
- 后端默认 `include_company_knowledge=True`。

保留历史字段兼容：

- `include_explorations` 如仍存在，第一版不默认启用。
- 如果前端传入 `include_explorations=true`，可以先忽略并在后端注释说明探索来源不在本次默认范围。

## 流式输出契约

SSE 事件保持：

```text
message_delta
thinking_delta
metadata
done
error
```

约束：

- `message_delta` 只包含用户可见自然语言。
- 不透传 deepagents 内部 tool event。
- 不把 `KnowledgeQueryOutput` JSON 作为聊天气泡内容。
- `metadata.result` 包含完整结构化结果。

`metadata.result`：

```python
{
    "conversation": KnowledgeConversation,
    "messages": [user_message, assistant_message],
    "answer": str,
    "source_refs": list[KnowledgeSourceRef],
    "used_requirement_versions": list[str],
    "used_company_knowledge_files": list[str],
    "used_exploration_runs": list[str],
    "knowledge_queried": bool,
}
```

## Fallback 行为

如果 deepagents 调用失败：

- 继续使用确定性 fallback。
- fallback 基于已收集的项目最终需求和公司知识库做关键词摘要。
- fallback 不编造来源。
- fallback 设置 `knowledge_queried=true`，因为已经尝试检索来源。

Fallback 输出文案：

```text
知识库智能检索暂不可用，已基于当前可用来源做确定性摘要：
```

如果没有任何可用来源：

```text
无法查询知识库：
- 当前项目没有可用于查询的最终需求文档。
- 当前没有可读取的公司知识库文件。
```

## 模型运行时约束

本次知识库重构只保留一个 deepagents agent，但 deepagents 底层仍通过 LangChain model 调用模型。因此模型适配必须保留统一运行时策略：

- 官方 OpenAI 端点可以使用默认策略。
- OpenAI-compatible 端点默认禁用 Responses API，走 Chat Completions。
- 业务代码不得直接实例化 `ChatOpenAI`。
- 模型健康检查和 agent 执行必须复用同一模型构建策略。

该约束用于避免 MiniMax、DeepSeek 等兼容端点误走 `/responses`。

## 删除与迁移

删除运行时不再需要的模块：

```text
apps/backend/app/agents/knowledge_chat/
apps/backend/app/services/knowledge/query_service.py
apps/backend/app/services/knowledge/codex_query.py
apps/backend/tests/test_knowledge_query_codex.py
```

如果为了短期兼容保留 `query_service.py`，它只能薄封装到 `app.agents.knowledge.service.run_knowledge_agent`，并添加 TODO；最终必须删除。

清理文档：

- 标记 `2026-06-10-knowledge-chat-tool-calling-design.md` 为历史设计。
- 删除或更新 Codex CLI agentic-search 运行口径。
- 所有新文档统一使用“单 deepagents 知识库问答 Agent”表述。

## 测试要求

### 单元测试

新增或更新：

```text
tests/test_knowledge_agentic_search.py
tests/test_knowledge_conversations.py
tests/test_model_selection.py
```

必须覆盖：

- 闲聊不读取知识库，`knowledge_queried=false`。
- 项目事实问题读取项目最终需求，返回 `used_requirement_versions`。
- 通用测试建议读取公司知识库，返回 `used_company_knowledge_files`。
- 项目最终需求和公司知识库冲突时，以项目最终需求为准。
- 公司知识库文件缺失时跳过，不导致整轮失败。
- 没有任何来源时返回 blocker。
- SSE 不输出结构化 JSON 气泡。
- deepagents 异常时 fallback 可用。
- MiniMax / DeepSeek 模型配置不走 Responses API。

### 架构测试

新增架构边界断言：

- `app.agents.knowledge_chat` 不存在。
- `app.services.knowledge.codex_query` 不存在。
- 知识库问答运行入口只依赖 `app.agents.knowledge.service`。
- 除模型运行时和模型健康检查外，不允许业务模块直接 import `ChatOpenAI`。

## 验收标准

- 知识库问答只有一个 deepagents agent 执行核心。
- 当前项目最终需求和公司知识库默认进入检索上下文。
- 闲聊不消耗知识库检索。
- 项目事实回答不被公司知识库覆盖。
- 来源引用能区分 `requirement` 和 `company_knowledge`。
- 流式输出稳定，不泄漏 JSON，不依赖外层 LangChain chat agent。
- 旧 Codex 和 `knowledge_chat` 双 Agent 口径从运行时移除。
