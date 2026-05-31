# OpenAI Agents SDK 架构对齐重构规范

> Superseded: 本规范中的 `prompts.py`、薄 `runner.py`、`AgentDefinition` 迁移方向已被废弃。当前权威规范为 `docs/superpowers/specs/2026-06-01-openai-agents-sdk-per-agent-directory-spec.md`，要求每个智能体一个目录，并使用 OpenAI Agents SDK 原生 `Agent + Runner.run + workflow/tools/guardrails` 结构。

## 背景

当前后端已经引入 OpenAI Agents SDK，并在 `apps/backend/app/agents/runtime.py` 中通过 `Agent` 和 `Runner.run` 执行智能体。但现有工程分层没有完全按 SDK 的核心模型组织：

- `app/agents/{agent}` 主要只保存 `AgentDefinition`，没有成为完整智能体能力边界。
- 多个 `app/services/*_service.py` 直接调用 `app.agents.runtime.run_agent`。
- prompt 构造、输出解析、修复逻辑和 agent 行为规则散落在 service 层。
- 部分 agent 已设置 `output_type`，部分 agent 仍依赖 service 手动要求模型返回 JSON。
- API、service、agent runner、SDK runtime 的职责边界不清晰，导致后续维护时容易重复定义 agent 契约。

本规范要求按 OpenAI Agents SDK 的设计重新划分职责：`Agent` 承载指令、工具和输出契约；`Runner` 执行 agent；业务 service 不直接拼 agent prompt，不直接调用 generic runtime。

## 依据

OpenAI Agents SDK 的核心使用模型是：

```python
agent = Agent(
    name="...",
    instructions="...",
    tools=[...],
    output_type=SomePydanticModel,
)

result = await Runner.run(agent, input)
```

对应到本项目：

- `instructions` 应属于 agent 定义，而不是业务 service。
- `tools`/skills 应由 agent 目录声明和加载。
- `output_type` 应属于 agent 定义，用于结构化输出。
- `Runner.run` 应由 agent runtime 或 agent-specific runner 调用。
- HTTP API 和业务 service 不应承担智能体行为契约。

## 目标

1. 让 `app/agents/{agent}` 成为智能体能力边界。
2. 所有 agent 的 instructions、tools/skills、output_type 在 agent 层声明。
3. 所有 agent 输入构造逻辑迁入 agent 目录。
4. 所有 agent-specific 执行入口迁入 agent 目录。
5. `app/services` 不再直接 import 或调用 `app.agents.runtime.run_agent`。
6. `app/services` 只负责业务编排、数据读取、持久化、质量门禁和操作日志。
7. `app/api` 只负责 HTTP 契约、权限和调用应用层入口，不写 prompt。
8. 保留通用 `/agents/{agent_id}/run` 作为调试和后台管理入口，不作为产品主流程入口。
9. 增加架构测试，防止 service 层重新直接调用 generic agent runtime。

## 非目标

- 不更换 OpenAI Agents SDK。
- 不重写所有业务流程和数据库模型。
- 不把确定性文件转换、Markdown 渲染、质量校验强行改成大模型任务。
- 不让前端直接拼 agent prompt。
- 不让通用 `/agents/{agent_id}/run` 替代明确 schema 的产品接口。
- 不在本次规范中实现 handoff、多 agent supervisor 或复杂工作流引擎。
- 不为了兼容坏模型输出继续扩大 JSON 修复器能力。

## 核心原则

### Agent 是能力边界

一个 agent 目录必须包含该智能体的完整运行契约：

- 角色和行为规则。
- 可用 skills/tools。
- 输入格式化。
- 输出类型。
- agent-specific runner。
- 必要的输出校验和错误转换。

### Service 不是 Agent Runner

service 可以调用某个明确的 agent runner，例如：

```python
from app.agents.document_editor.runner import run_document_editor
```

service 不允许直接调用：

```python
from app.agents.runtime import run_agent
```

### Prompt 属于 Agent 层

以下内容必须放在 agent 层：

- “你是谁”
- “你不能做什么”
- “必须返回什么结构”
- “如何理解输入”
- “如何保留 Markdown 结构”
- “如何处理冲突和证据”

service 层只传递业务数据，不写 agent 行为规则。

### Structured Output 优先

只要该 agent 的输出有明确 Pydantic schema，就必须使用 `output_type`。

允许例外：

- 目标模型供应商不支持 SDK structured output。
- 输出本身是非结构化长文档，且已有独立 artifact 保存策略。

即使存在例外，也必须在 agent runner 中做显式校验，不得把校验散落到业务 service。

### Markdown 长正文不进 JSON

需求归并、报告、知识库等长 Markdown 产物不得作为巨大 JSON 字段由模型返回。应采用：

- 智能体输出小型结构化决策。
- 后端确定性渲染 Markdown artifact。
- artifact 路径、摘要、映射和质量结果作为结构化输出。

## 目标目录结构

```text
apps/backend/app/agents/
  __init__.py
  definitions.py
  registry.py
  runtime.py
  skill_loader.py
  skills.py

  document_editor/
    __init__.py
    agent.py
    prompts.py
    runner.py

  raw_requirement_format_converter/
    __init__.py
    agent.py
    prompts.py
    runner.py
    skills/
      pdf_to_markdown/
      docx_to_markdown/
      markdown_normalize/

  requirement_analysis/
    __init__.py
    agent.py
    prompts.py
    runner.py

  requirement_merge/
    __init__.py
    agent.py
    prompts.py
    runner.py
    outline_runner.py
    assignment_runner.py
    section_runner.py
    artifacts.py

  knowledge_builder/
    __init__.py
    agent.py
    prompts.py
    runner.py

  site_exploration/
    __init__.py
    agent.py
    prompts.py
    runner.py
```

说明：

- `agent.py` 负责导出 `agent_definition`。
- `prompts.py` 负责把业务输入格式化为 `Runner.run` 的 input。
- `runner.py` 负责 agent-specific 执行入口。
- 多阶段 agent 可按阶段拆 runner，例如 `outline_runner.py`、`section_runner.py`。
- `services/` 不再保存 agent prompt builder。

## AgentDefinition 调整

现有 `AgentDefinition` 可以保留，但字段语义必须对齐 SDK：

```python
@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    description: str
    instructions: str
    model: str = "gpt-5.4-mini"
    skill_ids: tuple[str, ...] = field(default_factory=tuple)
    sort_order: int = 100
    output_type: type[Any] | None = None
```

要求：

- 所有有结构化输出的 agent 必须设置 `output_type`。
- `instructions` 必须包含输出契约说明，但不得包含单次运行输入数据。
- `description` 只用于展示，不参与 prompt。
- `model` 是默认值，实际运行优先使用模型配置表。

## Runtime 调整

### 命名调整

当前：

```python
async def run_agent(agent_id: str, prompt: str) -> AgentRunResult:
```

目标：

```python
async def run_agent(agent_id: str, agent_input: Any) -> AgentRunResult:
```

原因：

- OpenAI Agents SDK 使用 `Runner.run(agent, input)`，不是只支持 prompt string。
- 后续可能传入 message list、dict 或其他 SDK 支持的输入结构。

### Runtime 职责

`runtime.py` 只负责：

- 根据 `agent_id` 找到 `AgentDefinition`。
- 加载 skills/tools。
- 解析模型配置。
- 构造 SDK `Agent`。
- 调用 `Runner.run`。
- 记录 trace、usage、raw response count。
- 序列化 final output。

`runtime.py` 禁止：

- 拼接业务 prompt。
- 修复某个业务 agent 的坏 JSON。
- 根据业务类型写分支。
- 读取业务数据库。

## Agent Runner 规范

每个 agent-specific runner 按如下模式实现：

```python
from app.agents.runtime import run_agent
from app.schemas.document_editor import DocumentEditInput, DocumentEditOutput


AGENT_ID = "document_editor"


async def run_document_editor(input_data: DocumentEditInput) -> DocumentEditOutput:
    result = await run_agent(AGENT_ID, build_document_edit_input(input_data))
    return DocumentEditOutput.model_validate(result.output)
```

要求：

- runner 是唯一允许调用 `run_agent` 的业务入口。
- runner 返回明确 schema，不返回裸 `AgentRunResult`，除非调用方是后台调试功能。
- runner 内允许做 output schema validate。
- runner 不做数据库写入。
- runner 不记录业务操作日志。

## API 与 Service 边界

### API

API 负责：

- FastAPI route。
- auth。
- request/response schema。
- 调用 service 或 agent runner。

API 禁止：

- 写 prompt。
- 调 `app.agents.runtime.run_agent`。
- 解析模型 JSON。

### Service

service 负责：

- 读取和写入数据库。
- 文件存储。
- 版本管理。
- 操作日志。
- 权限之外的业务校验。
- 调用明确的 agent runner。
- 对 agent 输出做业务级验收。

service 禁止：

- 写 agent instructions。
- 写 agent prompt。
- 直接调用 generic `run_agent`。
- 直接处理 SDK response 细节。

## 当前调用点迁移清单

### document_editor

当前问题：

- `document_editor_service.py` 构造 prompt 并解析 JSON。
- `document_editor_agent.py` 未设置 `output_type`。

目标：

- 新增 `app/agents/document_editor/agent.py`。
- 新增 `app/agents/document_editor/prompts.py`。
- 新增 `app/agents/document_editor/runner.py`。
- `agent_definition.output_type = DocumentEditOutput`。
- 删除 `app/services/document_editor_service.py`。
- `api/v1/agents.py` 直接调用 `run_document_editor`。

### raw_requirement_format_converter

当前问题：

- agent 已设置 `output_type`。
- service 仍负责调用 runtime 和 normalize。

目标：

- agent runner 负责调用 converter agent。
- deterministic normalize 是否保留在 service 需要重新确认：
  - 如果 normalize 是确定性 Markdown 处理，应保留在 service 或 dedicated deterministic module。
  - 如果 normalize 是 agent skill 行为，应迁入 agent runner。

### requirement_analysis

当前问题：

- agent 已设置 `output_type`。
- `_build_agent_prompt` 在 service。

目标：

- 迁移 prompt builder 到 `app/agents/requirement_analysis/prompts.py`。
- 新增 `runner.py`。
- service 只负责读取需求版本和保存分析结果。

### knowledge_builder

当前问题：

- agent 已设置 `output_type`。
- prompt builder 和 runtime call 在 service。

目标：

- 迁移 input builder 到 `app/agents/knowledge_builder/prompts.py`。
- 新增 `runner.py`。
- service 只负责读取需求、探索、知识库目录并落库。

### requirement_merge

当前问题：

- service 中包含多阶段 agent 调用。
- outline、assignment、section merge、repair prompt 分散在 service。
- 存在长 JSON 修复和阶段错误处理混杂问题。

目标：

- `requirement_merge/agent.py` 声明主归并 agent。
- `requirement_merge/outline_runner.py` 负责目标大纲生成。
- `requirement_merge/assignment_runner.py` 负责旧大纲归属。
- `requirement_merge/section_runner.py` 负责章节合并决策。
- `requirement_merge/runner.py` 负责完整 agent 侧归并流程的 SDK 调用组合。
- service 负责 source block 抽取、artifact 写入、质量门禁、版本写入。
- repair prompt 如必须保留，也必须归入对应 runner，不能放 service。

### site_exploration

当前问题：

- 目前站点探索主流程更多是 Playwright runner 和确定性 YAML 产物，不一定属于 LLM Agent Runtime。

目标：

- 明确 `site_exploration` agent 是否仍需要 OpenAI Agents SDK。
- 如果只是 Playwright 确定性探索，应从 `agents/` 中移出或标记为非 LLM runner。
- 如果后续需要 LLM 生成探索计划，则仅计划生成部分进入 agent runner，Playwright 执行仍属于 deterministic runner。

## 通用 Agent 管理接口

保留：

```http
GET /agents
GET /agents/skills
GET /agents/model-assignments
PUT /agents/{agent_id}/model-assignment
POST /agents/{agent_id}/run
```

定位：

- `/agents/{agent_id}/run` 是管理、调试和内部测试入口。
- 产品功能不得依赖用户或前端手写 prompt 调该接口。
- 产品功能必须提供明确 schema 的 route 或调用明确 agent runner。

## 架构约束测试

新增测试：

```text
apps/backend/tests/test_agent_architecture_boundaries.py
```

检查项：

1. `app/services/**/*.py` 不得出现：

```python
from app.agents.runtime import run_agent
```

2. `app/api/**/*.py` 不得出现：

```python
from app.agents.runtime import run_agent
```

3. 每个 `app/agents/*/agent.py` 必须导出 `agent_definition`。
4. 每个有 schema 输出的 agent 必须设置 `output_type`。
5. 每个产品级 agent 必须有 `runner.py`。
6. 旧命名 `*_agent.py` 在迁移完成后不得新增。

## 迁移阶段

### 阶段 1：建立新结构

- 修改 registry，使其兼容 `agent.py` 和旧 `*_agent.py`。
- 新增 architecture boundary test，先允许当前违规列表为 expected failures。
- 修改 `runtime.run_agent(prompt)` 参数名为 `agent_input`。

### 阶段 2：迁移 document_editor

- 迁移 agent definition。
- 添加 `output_type=DocumentEditOutput`。
- 迁移 prompt builder。
- 新增 runner。
- 删除 `document_editor_service.py`。
- API 改调用 runner。
- 增加单测覆盖结构化输出。

### 阶段 3：迁移简单单调用 agent

迁移顺序：

1. `raw_requirement_format_converter`
2. `requirement_analysis`
3. `knowledge_builder`

每迁移一个 agent，删除对应 service 中的 direct `run_agent`。

### 阶段 4：迁移 requirement_merge 多阶段流程

- 先迁移 outline runner。
- 再迁移 assignment runner。
- 再迁移 section runner。
- 最后迁移主 merge runner。
- service 保留 artifact、quality gate、version write。

### 阶段 5：清理兼容层

- registry 只扫描 `app/agents/*/agent.py`。
- 删除旧 `*_agent.py` 文件。
- architecture boundary test 改为强制通过。
- 删除无用 JSON 修复器或迁入对应 runner。

## 验收标准

### 代码结构验收

- `app/services` 中没有直接 import `app.agents.runtime.run_agent`。
- `app/api` 中没有直接 import `app.agents.runtime.run_agent`。
- 每个产品 agent 都有 `agent.py`、`prompts.py`、`runner.py`。
- 所有结构化输出 agent 都声明 `output_type`。
- `document_editor_service.py` 被删除。

### 行为验收

- 文档编辑仍能通过前端完成 AI 修改并保存。
- 格式转换仍能处理 PDF/DOCX/TXT/Markdown。
- 需求分析仍返回 `RequirementAnalysisOutput`。
- 知识库构建仍返回 `KnowledgeBuildOutput`。
- 需求归并失败时仍保存可审计阶段错误，不生成伪成功版本。

### 架构验收

- agent instructions 不再散落在 service。
- prompt builder 不再散落在 service。
- service 只调用 agent-specific runner。
- 通用 `/agents/{agent_id}/run` 不参与产品主流程。
- 架构约束测试通过。

## 风险与处理

### 风险 1：一次性迁移 requirement_merge 影响大

处理：

- 多阶段拆迁。
- 每阶段保留现有 artifact 输出。
- 每次迁移后使用历史 mergerun 数据做回归。

### 风险 2：非 OpenAI 兼容模型不支持 structured output

处理：

- runtime 当前已有 `_supports_structured_output` 判断。
- agent runner 必须对 `result.output` 做 schema validate。
- 对不支持 structured output 的供应商，runner 可以保留轻量 JSON parse，但必须封装在 agent 层。

### 风险 3：旧 API 调用依赖 service 名称

处理：

- API 路径保持不变。
- 后端内部 import 改为 agent runner。
- 前端无需变更，除非响应 schema 变化。

### 风险 4：旧 spec 与新边界冲突

处理：

- 本规范优先约束 agent/service/API 分层。
- 旧需求归并、探索、知识库 spec 的业务契约仍有效。
- 如果旧 spec 要求 service 拼 prompt，应按本规范修订。

## 完成定义

本重构完成时，代码应满足：

```text
API -> Service -> Agent-specific runner -> Runtime -> OpenAI Agents SDK
```

或对无业务 service 的简单 agent：

```text
API -> Agent-specific runner -> Runtime -> OpenAI Agents SDK
```

禁止长期存在：

```text
Service -> generic run_agent + service prompt builder + service JSON parser
```

这才是本项目对齐 OpenAI Agents SDK 后的长期架构。
