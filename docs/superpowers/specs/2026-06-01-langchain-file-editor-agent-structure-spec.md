# LangChain 文档修改智能体改造方案

## 当前状态

当前后端目录状态：

```text
apps/backend/app/
  agents_bak/
  ai_agents/
  ai_runtime/
  api/
  llm_tasks/
  services/
```

说明：

- 旧 `agents` 已被备份为 `agents_bak`。
- 新 `agents` 目录当前不存在，应作为 LangChain 新智能体目录重建。
- 当前可运行的文档修改实现仍在 `app/llm_tasks/document_editor.py`。
- `app/api/v1/agents.py` 里的 `/agents/document-editor/run` 仍调用 `app.llm_tasks.document_editor.edit_document`。
- `app/ai_runtime/model_selection.py` 已经能按 `capability_id` 解析模型配置。
- `document_editor` 当前在 `AI_CAPABILITIES` 中仍是 `kind="llm_task"`。

本次改造目标是：**在新的 `app/agents` 目录下先构建文档修改智能体，使用 LangChain 最新 `create_agent`，并通过现有 `services/` 层对接 FastAPI。**

## 目标

1. 新建 `apps/backend/app/agents/` 作为新 LangChain 智能体目录。
2. 第一阶段只实现文档修改智能体：`apps/backend/app/agents/document_editor/`。
3. 文档修改智能体目录只保留核心文件：`agent.py`、`schemas.py`、`tools.py`。
4. `agent.py` 只负责定义 system prompt 和创建 LangChain agent。
5. 业务调用入口放在现有 `apps/backend/app/services/document_editor_service.py`。
6. FastAPI route 只调用 service，不直接创建或调用 LangChain agent。
7. 模型配置继续通过 `resolve_model_selection("document_editor")` 获取。
8. 新增 LangChain model 构建适配，支持 OpenAI 和 DeepSeek / OpenAI-compatible provider。
9. 停止使用 `app/llm_tasks/document_editor.py` 作为文档修改运行入口。

## 非目标

- 不恢复旧 `agents_bak` 框架。
- 不迁移 `requirement_merge`、`site_exploration`、`knowledge_builder` 等其他智能体。
- 不设计 LangGraph。
- 不设计 DeepAgents skills。
- 不创建 `runner.py`。
- 不创建 `skills.py`。
- 不创建 `prompts.py`。
- 不创建 `subagents.py`。
- 不创建 `evals/`。
- 不创建额外 `runtime/`。

## 依赖

后端需要新增依赖：

```text
langchain
langchain-openai
```

原因：

- `langchain` 提供最新 `create_agent`。
- `langchain-openai` 提供 OpenAI 与 OpenAI-compatible chat model 适配。

## 目标目录

```text
apps/backend/app/
  agents/
    __init__.py
    document_editor/
      __init__.py
      agent.py
      schemas.py
      tools.py

  ai_runtime/
    langchain_model.py

  services/
    document_editor_service.py

  api/v1/
    agents.py
```

本阶段不新增独立 `api/v1/document_editor.py`，先复用现有：

```text
POST /agents/document-editor/run
```

这样前端和已有 API 路径不需要在第一阶段一起改。

## 目录职责

### apps/backend/app/agents/

新的 LangChain 智能体根目录。

这个目录不再承载旧 `AgentDefinition` registry 语义。旧实现已在 `agents_bak/`，新 `agents/` 只放重构后的 LangChain / DeepAgents 智能体。

### apps/backend/app/agents/document_editor/agent.py

职责：

1. 定义文档修改智能体 system prompt。
2. 使用 LangChain `create_agent` 创建 agent。
3. 使用 `response_format=DocumentEditOutput`。
4. 不解析模型配置。
5. 不调用 `agent.invoke()`。
6. 不处理 FastAPI 入参。

示意：

```python
from langchain.agents import create_agent

from .schemas import DocumentEditOutput
from .tools import tools


SYSTEM_PROMPT = """
你是 AI 测试系统中的文档修改智能体。
你只根据用户明确指令修改当前文档。
你不能新增未经文档支持或用户确认的业务事实。
你必须保留与修改指令无关的内容、标题层级、Markdown 表格、代码块、列表和整体结构。
你必须返回结构化结果。
""".strip()


def create_document_editor_agent(model):
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        response_format=DocumentEditOutput,
    )
```

### apps/backend/app/agents/document_editor/schemas.py

职责：

1. 定义 `DocumentEditInput`。
2. 定义 `DocumentEditOutput`。
3. 保持与现有 API response 语义一致。

字段沿用当前 `app/schemas/document_editor.py`：

```python
from typing import Literal

from pydantic import BaseModel, Field


class DocumentEditInput(BaseModel):
    document_type: str = Field(min_length=1, max_length=80)
    document_title: str = Field(default="", max_length=200)
    content: str = Field(min_length=1)
    instruction: str = Field(min_length=1, max_length=4000)


class DocumentEditOutput(BaseModel):
    status: Literal["edited", "unchanged"]
    edited_content: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
```

实现时可选择：

```text
方案 A：直接把现有 app/schemas/document_editor.py 移入 agents/document_editor/schemas.py
方案 B：agents/document_editor/schemas.py 复用 app.schemas.document_editor
```

第一阶段推荐方案 B，减少 API schema import 改动。

### apps/backend/app/agents/document_editor/tools.py

职责：

1. 声明当前文档修改智能体使用的 tools。
2. 第一阶段不额外创建文件读写工具。
3. 文档内容由 API payload 传入，agent 只需要基于输入内容生成结构化修改结果。

第一阶段：

```python
tools = []
```

说明：

- 之前讨论的文件读写工具适合“真实文件修改智能体”。
- 当前项目的文档修改入口是“修改 payload 中的 Markdown 文档内容”，不需要文件系统工具。
- 先不加没用工具，避免设计膨胀。

### apps/backend/app/ai_runtime/langchain_model.py

职责：

1. 接收当前项目已有 `ModelSelection`。
2. 根据 provider 创建 LangChain chat model。
3. 支持 `openai` 和 `openai-compatible`。
4. DeepSeek 通过 `normalize_provider("deepseek") -> "openai-compatible"` 走 OpenAI-compatible 路径。

示意：

```python
from langchain.chat_models import init_chat_model

from app.ai_runtime.model_selection import ModelSelection, normalize_provider


def build_langchain_model(selection: ModelSelection):
    provider = normalize_provider(selection.provider)
    model_provider = "openai" if provider == "openai-compatible" else provider
    return init_chat_model(
        model=selection.model,
        model_provider=model_provider,
        api_key=selection.api_key,
        base_url=selection.base_url,
        temperature=0,
    )
```

### apps/backend/app/services/document_editor_service.py

职责：

1. 作为文档修改业务调用入口。
2. 校验输入空白内容。
3. 调用 `resolve_model_selection("document_editor")`。
4. 调用 `build_langchain_model(selection)`。
5. 调用 `create_document_editor_agent(model)`。
6. 调用 `agent.invoke(...)`。
7. 读取 `structured_response`。
8. 执行输出保护校验。
9. 返回 `DocumentEditOutput`。

示意：

```python
from app.agents.document_editor.agent import create_document_editor_agent
from app.schemas.document_editor import DocumentEditInput, DocumentEditOutput
from app.ai_runtime.langchain_model import build_langchain_model
from app.ai_runtime.model_selection import resolve_model_selection


def edit_document(input_data: DocumentEditInput) -> DocumentEditOutput:
    _validate_document_edit_input(input_data)
    selection = resolve_model_selection("document_editor")
    model = build_langchain_model(selection)
    agent = create_document_editor_agent(model)

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": _build_document_editor_input(input_data),
                }
            ]
        }
    )

    output = result.get("structured_response")
    if output is None:
        raise ValueError("文档修改智能体未返回结构化结果。")

    _validate_document_edit_output(input_data, output)
    return output
```

`_build_document_editor_input`、`_validate_document_edit_input`、`_validate_document_edit_output` 可从当前 `app/llm_tasks/document_editor.py` 迁移到 service。

### apps/backend/app/api/v1/agents.py

保留现有 route：

```text
POST /agents/document-editor/run
```

但调用目标改为：

```python
from app.services.document_editor_service import edit_document
```

不再调用：

```python
from app.llm_tasks.document_editor import edit_document
```

## 能力类型调整

当前：

```python
AiCapability(id="document_editor", kind="llm_task")
```

本次改造后建议改为：

```python
AiCapability(id="document_editor", kind="agent")
```

原因：

- 文档修改将由 LangChain `create_agent` 执行。
- 模型分配页应把它归为“智能体”。
- 旧 `llm_task` 语义不再准确。

如果产品上仍希望“文档修改”显示在普通 LLM 能力中，可以暂时不改 `kind`，但从架构语义看，推荐改为 `agent`。

## 旧文件处理

本次改造后停止使用：

```text
apps/backend/app/llm_tasks/document_editor.py
```

可在实现阶段选择：

```text
方案 A：直接删除
方案 B：保留为空代理，内部调用 document_editor_service.edit_document
```

用户已明确不要求向前兼容，推荐方案 A：直接删除旧实现。

## 测试要求

必须覆盖：

1. `document_editor` capability 类型改为 `agent`。
2. `document_editor` 出现在 agent capability 列表中。
3. `document_editor` 不再出现在 llm_task capability 列表中。
4. `create_document_editor_agent(model)` 调用 LangChain `create_agent`。
5. `create_document_editor_agent(model)` 传入 `response_format=DocumentEditOutput`。
6. `document_editor_service.edit_document` 会调用 `resolve_model_selection("document_editor")`。
7. `document_editor_service.edit_document` 会调用 LangChain agent 的 `invoke`。
8. `document_editor_service.edit_document` 返回 `structured_response`。
9. 缺少 `structured_response` 时明确失败。
10. `api/v1/agents.py` 的 document editor route 只调用 service。
11. 不再 import `app.llm_tasks.document_editor`。
12. 不创建 `runner.py`、`skills.py`、`prompts.py`、`subagents.py`、`evals/`。

## 验收标准

1. 新增 `apps/backend/app/agents/document_editor/agent.py`。
2. 新增 `apps/backend/app/agents/document_editor/tools.py`。
3. 新增 `apps/backend/app/agents/document_editor/__init__.py`。
4. 不新增 `runner.py`、`skills.py`、`prompts.py`、`subagents.py`、`evals/`。
5. 文档修改业务入口位于 `apps/backend/app/services/document_editor_service.py`。
6. FastAPI route 调用 service。
7. 模型配置通过 `resolve_model_selection("document_editor")` 获取。
8. DeepSeek / OpenAI-compatible provider 不再被文档修改能力直接拒绝。
9. 旧 `app/llm_tasks/document_editor.py` 不再被引用。
10. 后端测试通过。
