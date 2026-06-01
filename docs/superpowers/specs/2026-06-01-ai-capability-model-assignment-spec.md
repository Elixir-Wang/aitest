# AI 能力与模型分配统一规范

## 背景

当前系统的模型配置以“智能体”为中心：

- `apps/backend/app/ai_agents/manifest.py` 使用 `AiAgentManifestItem` 声明可分配模型的智能体。
- `agent_model_assignments` 表通过 `agent_id` 绑定模型配置。
- 前端模型分配页调用 `/agents/model-assignments` 和 `/agents/{agent_id}/model-assignment`。
- `document_editor` 当前被放入智能体清单，但它的实际能力只是单次文档修改，不需要 OpenAI Agents SDK 的 tools、handoffs、workflow 或 guardrails 编排。

这导致一个边界问题：**并不是所有需要模型配置的 AI 能力都是 Agent。**

本规范将“模型分配对象”从 `agent` 升级为统一的 `AI Capability`。系统只保留一套模型分配概念，不做旧接口兼容。

## 目标

1. 使用统一 `AiCapability` 清单描述所有需要模型配置的 AI 能力。
2. `AiCapability.kind` 只允许 `agent` 和 `llm_task` 两类。
3. `agent` 表示使用 OpenAI Agents SDK 的复杂智能体。
4. `llm_task` 表示普通 OpenAI SDK 调用的单次 LLM 能力。
5. 删除旧的 `agent_model_assignments` 设计，数据迁移到新的 `model_assignments`。
6. 删除旧的 `/agents/model-assignments` 和 `/agents/{agent_id}/model-assignment` 接口。
7. 前端模型分配页改为展示“AI 能力模型分配”，按 `kind` 分组。
8. `document_editor` 从 `ai_agents` 移出，改为 `llm_tasks/document_editor.py`。
9. Agents SDK 与 OpenAI SDK 共享同一套模型解析逻辑。

## 非目标

- 不保留旧模型分配接口兼容层。
- 不保留旧 `agent_model_assignments` 表作为长期结构。
- 不把 `workflow` 设计成第三类 capability。
- 不把 skill/tool 运行时配置放入统一能力清单。
- 不在本规范中实现 OpenAI Hosted Skills、ShellTool 或 ToolSearch。
- 不把所有 LLM 调用都改成 Agents SDK Agent。
- 不让前端在业务调用时下发 `api_key`、`base_url` 或 `model`。

## 核心概念

### AI Capability

`AiCapability` 是系统中所有可被前端感知、可分配模型、可由业务调用的 AI 能力。

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AiCapability:
    id: str
    name: str
    description: str
    kind: Literal["agent", "llm_task"]
```

字段含义：

- `id`：稳定能力标识，用于模型分配、运行时解析和日志。
- `name`：前端展示名称。
- `description`：前端展示说明。
- `kind`：能力类型，只允许 `agent` 或 `llm_task`。

示例：

```python
AI_CAPABILITIES = (
    AiCapability(
        id="document_editor",
        name="文档修改",
        description="根据用户指令修改 Markdown 文档，返回修改后的文档、修改摘要和风险提示。",
        kind="llm_task",
    ),
    AiCapability(
        id="raw_requirement_format_converter",
        name="格式转换智能体",
        description="负责将上传的 PDF、Word、TXT 和 Markdown 需求文件解析为 Markdown 工作稿。",
        kind="agent",
    ),
    AiCapability(
        id="requirement_merge",
        name="需求归并智能体",
        description="分析并归并多来源标准 Markdown，识别冲突并输出覆盖矩阵。",
        kind="agent",
    ),
)
```

### Agent

`agent` 是使用 OpenAI Agents SDK 的能力。它可以包含：

- `Agent(...)`
- `Runner.run(...)`
- tools
- guardrails
- handoffs
- agents-as-tools
- workflow/manager

`workflow.py` 是 agent 的产品调用入口，不是单独的模型分配对象。

### LLM Task

`llm_task` 是普通 OpenAI SDK 调用，不使用 Agents SDK。

适用场景：

- 文档修改
- 摘要生成
- 标题生成
- 简单结构化抽取
- 单次 Markdown 改写

## 后端目录结构

目标结构：

```text
apps/backend/app/
  ai_runtime/
    __init__.py
    capabilities.py
    model_selection.py
    openai_client.py
    run_config.py

  ai_agents/
    raw_requirement_converter/
    requirement_analysis/
    requirement_merge/
    site_exploration/
    knowledge_builder/

  llm_tasks/
    __init__.py
    document_editor.py
```

说明：

- `ai_runtime/capabilities.py` 保存统一能力清单。
- `ai_runtime/model_selection.py` 负责 `capability_id -> model provider` 解析。
- `ai_runtime/openai_client.py` 负责普通 OpenAI SDK client 构建。
- `ai_runtime/run_config.py` 负责 Agents SDK `RunConfig` 构建。
- `ai_agents/` 只放真正 Agents SDK 智能体。
- `llm_tasks/` 放普通 OpenAI SDK LLM 能力。

## 数据库设计

### 新表

```sql
CREATE TABLE model_assignments (
  capability_id TEXT PRIMARY KEY,
  model_provider_id TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(model_provider_id) REFERENCES model_providers(id) ON DELETE CASCADE
);
```

`capability_id` 必须对应 `AI_CAPABILITIES` 中存在的能力。

### 数据迁移

迁移旧数据：

```sql
INSERT INTO model_assignments (capability_id, model_provider_id, updated_at)
SELECT agent_id, model_provider_id, updated_at
FROM agent_model_assignments;
```

迁移完成后删除旧表：

```sql
DROP TABLE agent_model_assignments;
```

### 不再使用

以下概念删除：

- `agent_model_assignments`
- `agent_id` 作为模型分配专属字段
- agent-only 模型分配 repository 方法

## 模型解析

新增：

```text
apps/backend/app/ai_runtime/model_selection.py
```

职责：

```python
resolve_model_selection(capability_id: str) -> ModelSelection
```

返回结构：

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ModelSelection:
    capability_id: str
    capability_kind: Literal["agent", "llm_task"]
    model_provider_id: str
    provider: str
    model: str
    base_url: str | None
    api_key: str
    model_status: str
```

必须校验：

1. `capability_id` 存在。
2. 该 capability 已分配模型。
3. 关联 `model_provider` 存在。
4. `model_provider.status == "enabled"`。
5. `model_provider.api_key` 非空。

失败时返回明确业务错误，不允许静默 fallback 到默认模型。

## OpenAI SDK Client

新增：

```text
apps/backend/app/ai_runtime/openai_client.py
```

职责：

```python
from openai import OpenAI

from app.ai_runtime.model_selection import ModelSelection


def build_openai_client(selection: ModelSelection) -> OpenAI:
    return OpenAI(
        api_key=selection.api_key,
        base_url=selection.base_url or None,
    )
```

`llm_task` 必须通过 `resolve_model_selection(capability_id)` 获取模型配置，不允许业务调用方传入 `model`、`api_key` 或 `base_url`。

## Agents SDK RunConfig

将当前 Agents SDK 的模型 provider/run config 构建逻辑统一移动到：

```text
apps/backend/app/ai_runtime/run_config.py
```

职责：

```python
build_agent_run_config(capability_id: str, *, actor_id: str | None = None, trace_metadata: dict | None = None) -> RunConfig
```

内部必须调用：

```python
resolve_model_selection(capability_id)
```

`capability_kind` 必须为 `agent`，否则拒绝构建 Agents SDK `RunConfig`。

## API 设计

### 新增接口

```text
GET /ai/capabilities
```

返回所有 AI 能力。

```text
GET /model-assignments
```

返回所有 AI 能力及其当前模型分配。

```text
PUT /model-assignments/{capability_id}
```

请求体：

```json
{
  "model_provider_id": "provider-xxx"
}
```

### 保留但调整语义

```text
GET /agents
```

只返回 `kind == "agent"` 的 capability，用于智能体管理或调试入口。

### 删除接口

```text
GET /agents/model-assignments
PUT /agents/{agent_id}/model-assignment
```

所有前端和后端调用必须改用新的模型分配接口。

## 前端设计

模型分配页仍位于：

```text
/settings/models/assignments
```

页面标题改为：

```text
AI 能力模型分配
```

数据源：

```text
GET /model-assignments
GET /models/providers
```

保存接口：

```text
PUT /model-assignments/{capability_id}
```

展示分组：

```text
普通 LLM 能力
- 文档修改

智能体
- 格式转换智能体
- 需求归并智能体
- 需求分析智能体
- 站点探索智能体
- 知识库构建智能体
```

前端不再调用：

```text
/agents/model-assignments
/agents/{agent_id}/model-assignment
```

## 文档修改迁移

删除：

```text
apps/backend/app/ai_agents/document_editor/
```

新增：

```text
apps/backend/app/llm_tasks/document_editor.py
```

运行方式：

```python
selection = resolve_model_selection("document_editor")
client = build_openai_client(selection)

response = client.responses.parse(
    model=selection.model,
    input=...,
    text_format=DocumentEditOutput,
)
```

原 Agents SDK output guardrail 改为本地校验函数：

```python
validate_document_edit_output(input_data, output)
```

要求：

- `document_editor` 必须出现在 `AI_CAPABILITIES`。
- `document_editor.kind == "llm_task"`。
- `document_editor` 不得出现在 `GET /agents` 返回值中。
- 文档修改业务调用不得依赖 Agents SDK `Runner.run`。

## 操作日志

模型分配变更日志的对象类型改为：

```text
model_assignment
```

对象 ID 使用：

```text
capability_id
```

日志摘要使用 capability 名称，例如：

```text
配置 AI 能力模型：文档修改
```

Agent 运行日志仍可使用 `agent` 作为模块或对象类型，但模型分配日志不得再使用 `agent_model_assignment`。

## 测试要求

### 后端测试

必须覆盖：

1. `AI_CAPABILITIES` 同时包含 `agent` 和 `llm_task`。
2. `document_editor` 是 `llm_task`，不是 `agent`。
3. `GET /agents` 只返回 `kind == "agent"`。
4. `GET /model-assignments` 返回全部 capability。
5. `PUT /model-assignments/{capability_id}` 可以更新模型分配。
6. 未知 capability 更新模型分配时返回错误。
7. 禁用 provider 不能被分配。
8. `resolve_model_selection` 返回 provider/model/base_url/api_key。
9. 未分配模型时运行能力返回明确错误。
10. `document_editor` 使用 OpenAI SDK 路径，不调用 Agents SDK `Runner.run`。

### 前端测试或验证

必须验证：

1. 模型分配页标题为“AI 能力模型分配”。
2. 页面按 `kind` 分成“普通 LLM 能力”和“智能体”。
3. 文档修改出现在“普通 LLM 能力”。
4. 保存模型分配后刷新可回显。
5. 页面不再请求旧 `/agents/model-assignments` 接口。

## 删除清单

实现本规范时应删除或替换：

```text
apps/backend/app/ai_agents/manifest.py
apps/backend/app/ai_agents/model_provider.py
apps/backend/app/ai_agents/run_config.py
apps/backend/app/ai_agents/document_editor/
agent_model_assignments table
GET /agents/model-assignments
PUT /agents/{agent_id}/model-assignment
frontend calls to /agents/model-assignments
frontend calls to /agents/{agent_id}/model-assignment
```

如果某些文件仍有非旧模型分配职责，应移动到 `ai_runtime/` 后再删除原路径。

## 实施顺序

1. 新增 `ai_runtime/capabilities.py`，定义 `AiCapability` 和 `AI_CAPABILITIES`。
2. 新增 `model_assignments` 表，迁移旧数据，删除 `agent_model_assignments`。
3. 改造 `model_repo.py`，删除 agent-only assignment 方法，新增 capability assignment 方法。
4. 新增 `ai_runtime/model_selection.py`。
5. 新增 `ai_runtime/openai_client.py`。
6. 将 Agents SDK run config/provider 构建迁移到 `ai_runtime/run_config.py`。
7. 改造后端 API，删除旧模型分配接口，新增 capability 模型分配接口。
8. 改造前端模型分配页，使用新接口并按 `kind` 分组。
9. 将 `document_editor` 迁移到 `llm_tasks/document_editor.py`，改用 OpenAI SDK。
10. 删除旧 `ai_agents/document_editor/`。
11. 更新测试并运行后端、前端验证。

## 验收标准

1. 代码中不再存在 `agent_model_assignments` 运行时依赖。
2. 前端不再调用旧 agent model assignment 接口。
3. `document_editor` 不再出现在智能体列表中。
4. `document_editor` 出现在模型分配页的普通 LLM 能力分组中。
5. 所有 AI 能力都通过 `model_assignments.capability_id` 关联模型配置。
6. Agent 和 LLM task 都通过 `resolve_model_selection` 获取模型配置。
7. 未配置模型时，不允许 fallback 到默认模型。
8. 后端测试通过。
9. 前端模型分配页手动验证通过。
