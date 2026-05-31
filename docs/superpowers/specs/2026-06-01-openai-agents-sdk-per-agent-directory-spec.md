# OpenAI Agents SDK 每智能体目录架构规范

## 背景

当前后端智能体代码经历过多轮演进，已经出现以下问题：

1. 自定义 `AgentDefinition`、`registry`、`runtime.run_agent(agent_id, input)` 与 OpenAI Agents SDK 的原生模型存在重复抽象。
2. 旧设计中出现过 `prompts.py`、`runner.py`、`*_agent.py`、`*_service.py` 等多层包装，导致“提示词、执行入口、业务服务、SDK Agent”边界混乱。
3. 部分 service 直接拼 prompt、直接调用 runtime、直接解析 JSON，这不符合 SDK 的 `Agent + Runner + tools + guardrails + handoffs/output_type` 模型。
4. 用户明确希望保持“每个智能体一个目录”，避免把全局 `agents/`、`tools/`、`guardrails/`、`workflows/` 拆得过碎。

本规范重新定义后端智能体目录结构：**按业务智能体聚合目录，目录内部按 OpenAI Agents SDK 原生概念组织。**

## 官方依据

本规范依据 OpenAI Agents SDK 官方文档和官方 examples：

- Quickstart 使用 `Agent(...)` 直接定义智能体，并通过 `Runner.run(agent, input)` 执行。
- `output_type` 是 Agent 的结构化输出契约。
- 多智能体场景使用 handoffs、agents-as-tools、manager/workflow 等模式。
- 官方 examples 按业务示例分目录，例如 `financial_research_agent/`，复杂示例中存在 `agents/` 子目录和 `manager.py` 编排层。
- 官方 agent patterns 覆盖 deterministic flows、handoffs/routing、agents-as-tools、guardrails 等模式。

因此，本项目不应继续维护一套与 SDK 并行的 `AgentDefinition + prompts.py + runner.py` 抽象。

## 目标

1. 每个业务智能体一个目录。
2. 目录内部使用 SDK 原生概念：`Agent`、`Runner.run`、tools、guardrails、handoffs、workflow/manager。
3. 简单智能体目录只保留必要文件，避免过度拆分。
4. 复杂智能体目录允许多个子 agent，但仍聚合在同一个业务目录下。
5. 不再新增 `prompts.py`。
6. 不再新增 `runner.py` 作为薄包装。
7. 不再新增 `*_agent.py`。
8. 不再让 service 直接拼 prompt 或 parse agent JSON。
9. 输出 schema 优先使用 SDK `output_type`。
10. 多阶段流程优先使用 workflow/manager、agents-as-tools、handoffs 或 deterministic flow。

## 非目标

- 不要求一次性把所有业务服务迁移到智能体目录。
- 不把数据库、文件存储、版本写入、操作日志迁入智能体目录。
- 不把确定性转换、确定性质量检查强行改为 LLM agent。
- 不用前端直接调用通用 agent prompt 接口。
- 不保留旧的 `AgentDefinition` 作为长期架构。
- 不让每个 agent 都必须拥有 handoffs 或 guardrails；简单场景按需使用。

## 核心原则

### 1. 目录按业务智能体聚合

每个业务智能体目录独立承载该智能体的 SDK 定义、工具、guardrails 和 workflow：

```text
app/ai_agents/{agent_name}/
```

示例：

```text
app/ai_agents/document_editor/
app/ai_agents/requirement_merge/
app/ai_agents/knowledge_builder/
```

### 2. Agent 直接使用 SDK `Agent`

正确：

```python
from agents import Agent

document_editor_agent = Agent(
    name="文档修改智能体",
    instructions=DOCUMENT_EDITOR_PROMPT,
    tools=[],
    output_type=DocumentEditOutput,
)
```

错误：

```python
agent_definition = AgentDefinition(...)
```

### 3. Prompt 常量跟 Agent 放一起

不再单独创建 `prompts.py`。官方示例通常把 `PROMPT` 常量、output model、`Agent(...)` 放在同一 agent 文件或同一业务目录内。

简单智能体：

```text
document_editor/agent.py
```

复杂智能体：

```text
requirement_merge/agents.py
```

### 4. Workflow/Manager 是产品调用入口

`workflow.py` 或 `manager.py` 负责：

- 接收业务输入 schema。
- 构造 `Runner.run` 的 input。
- 传入 `RunConfig`。
- 调用一个或多个 Agent。
- 返回 `result.final_output` 或确定性组合后的业务输出。

它不负责：

- 数据库写入。
- 操作日志。
- 文件版本管理。
- HTTP 权限。

### 5. Tools 是模型可调用能力

`tools.py` 只放 SDK tool 或 agents-as-tools。

确定性业务函数不一定要做成 tool。只有需要模型主动调用、查询、验证、转换的能力，才应暴露为 tool。

### 6. Guardrails 是执行前后约束

`guardrails.py` 放 SDK input/output guardrails，例如：

- 输入为空。
- 来源块缺失。
- 输出缺少必要字段。
- 输出污染了源文件名。
- 文档编辑新增未确认事实。

service 层仍可保留业务质量门禁，但不能替代 SDK guardrail。

### 7. Handoffs 只用于真正转交控制权

如果一个 agent 应该完全接管后续任务，使用 handoff。

如果主 agent 仍应掌控流程，只是调用另一个 agent 完成子任务，使用 agents-as-tools。

### 8. Deterministic flow 不伪装成 Agent

文件读写、Markdown 渲染、版本写入、质量报告落盘、source block 提取等确定性流程应留在 service 或 deterministic workflow，不要伪装成 LLM agent。

## 总体目录结构

```text
apps/backend/app/
  ai_agents/
    __init__.py
    run_config.py
    model_provider.py
    tracing.py

    document_editor/
      __init__.py
      agent.py
      workflow.py
      guardrails.py

    raw_requirement_converter/
      __init__.py
      agent.py
      workflow.py
      tools.py
      guardrails.py

    requirement_analysis/
      __init__.py
      agent.py
      workflow.py
      guardrails.py

    requirement_merge/
      __init__.py
      agents.py
      workflow.py
      tools.py
      guardrails.py
      handoffs.py

    knowledge_builder/
      __init__.py
      agent.py
      workflow.py
      tools.py
      guardrails.py

```

说明：

- `ai_agents/` 是新智能体根目录，区别于旧 `agents/` 自定义框架。
- 简单智能体使用 `agent.py`。
- 复杂智能体使用 `agents.py` 承载多个子 agent。
- `workflow.py` 是后端产品调用入口。
- `run_config.py`、`model_provider.py`、`tracing.py` 放在 `ai_agents/` 外层，作为所有智能体共享的 SDK 运行基础设施。

## 文件命名规范

### 必须避免

```text
prompts.py
runner.py
*_agent.py
*_agent_service.py
```

原因：

- `prompts.py` 容易把 instructions 和 runtime input 混淆。
- `runner.py` 容易退化为 `run_agent(agent_id, prompt)` 的薄包装。
- `*_agent.py` 是旧项目约定，不是 SDK 示例风格。
- `*_agent_service.py` 容易把 agent 行为写回 service。

### 推荐命名

| 文件 | 用途 |
| --- | --- |
| `agent.py` | 简单智能体 SDK Agent 定义 |
| `agents.py` | 复杂智能体的多个 SDK Agent 定义 |
| `workflow.py` | 产品级调用流程，调用 `Runner.run` |
| `tools.py` | 本智能体专用 tools 或 agents-as-tools |
| `guardrails.py` | input/output guardrails |
| `handoffs.py` | handoff 配置 |
| `schemas.py` | 仅该智能体私有 schema |

## Schema 放置规则

优先规则：

1. 如果 schema 被 API、service、repository、多智能体复用，继续放在 `app/schemas/`。
2. 如果 schema 只属于某个智能体的内部输出，可以放在该智能体目录的 `schemas.py`。
3. 不为了“每个目录完整”强行搬迁公共 schema。

示例：

```text
app/schemas/document_editor.py
app/schemas/requirement_merge.py
```

可以先保留，因为 API 和 service 也使用这些契约。

## Runtime 配置规则

不再使用自定义 `run_agent(agent_id, input)` 作为主执行模型。

统一在 `ai_agents/run_config.py` 构造 SDK `RunConfig`：

```python
def build_run_config(agent_name: str, actor_id: str | None = None) -> RunConfig:
    ...
```

workflow 调用：

```python
result = await Runner.run(
    document_editor_agent,
    input_text,
    run_config=build_run_config("document_editor", actor_id=actor_id),
)
```

模型配置、provider、trace metadata 可以在 `ai_agents/` 外层运行基础设施中统一处理。

## 与 Service 的关系

### 简单调用

```text
API -> ai_agents/document_editor/workflow.py -> Runner.run(document_editor_agent, input)
```

### 带业务持久化

```text
API -> service -> ai_agents/requirement_analysis/workflow.py -> Runner.run(requirement_analysis_agent, input)
              -> service 保存结果、日志、版本
```

### 复杂确定性 + LLM 流程

```text
API -> service
    -> source block extraction
    -> ai_agents/requirement_merge/workflow.py
       -> Runner.run(outline_agent, input)
       -> Runner.run(section_merge_agent, input)
       -> output guardrails
    -> service 写 artifacts、quality、version
```

service 可以编排确定性业务流程，但不能写 agent instructions。

## 智能体目录详细设计

### document_editor

用途：

- 根据用户明确指令修改当前 Markdown 文档。
- 保留与指令无关结构。
- 不新增未确认事实。

目录：

```text
document_editor/
  __init__.py
  agent.py
  workflow.py
  guardrails.py
```

`agent.py`：

```python
DOCUMENT_EDITOR_PROMPT = """
你是 AI 测试系统中的通用文档修改智能体。
...
"""

document_editor_agent = Agent(
    name="文档修改智能体",
    instructions=DOCUMENT_EDITOR_PROMPT,
    output_type=DocumentEditOutput,
)
```

`workflow.py`：

```python
async def edit_document(input_data: DocumentEditInput, *, actor_id: str | None = None) -> DocumentEditOutput:
    result = await Runner.run(
        document_editor_agent,
        build_document_editor_input(input_data),
        run_config=build_run_config("document_editor", actor_id=actor_id),
    )
    return result.final_output
```

`guardrails.py`：

- 输入文档不能为空。
- instruction 不能为空。
- 输出 `edited_content` 不能为空。
- 如果输出疑似删除大量无关内容，触发 warning 或 tripwire。

### raw_requirement_converter

用途：

- 对上传文件转换后的候选 Markdown 进行格式校验和标准化。
- 不生成业务结论。

目录：

```text
raw_requirement_converter/
  __init__.py
  agent.py
  workflow.py
  tools.py
  guardrails.py
```

`tools.py`：

- `pdf_to_markdown_tool`
- `docx_to_markdown_tool`
- `markdown_normalize_tool`

注意：

- 如果 PDF/DOCX 转 Markdown 已是确定性本地 CLI，可以不让 LLM 调用，而是在 service 或 workflow 前置执行。
- LLM agent 只负责审阅和结构化修正候选 Markdown。

### requirement_analysis

用途：

- 分析已归并需求工作稿。
- 输出模块、规则、澄清问题、成熟度、质量门禁。

目录：

```text
requirement_analysis/
  __init__.py
  agent.py
  workflow.py
  guardrails.py
```

Agent：

- `output_type=RequirementAnalysisOutput`
- instructions 中明确不能归并来源、不能生成知识库、不能生成测试用例。

Guardrails：

- 输入必须是已归并版本。
- 输出必须包含 `quality_gate`。
- 如果发现关键业务边界缺失但未输出澄清问题，应触发 guardrail。

### requirement_merge

用途：

- 多来源标准 Markdown 归并。
- 识别重复、冲突、待澄清。
- 输出可审计归并产物。

该智能体最复杂，必须避免单个巨大 prompt。

目录：

```text
requirement_merge/
  __init__.py
  agents.py
  workflow.py
  tools.py
  guardrails.py
  handoffs.py
```

`agents.py` 定义多个 Agent：

```python
outline_agent = Agent(...)
assignment_agent = Agent(...)
section_merge_agent = Agent(...)
conflict_review_agent = Agent(...)
coverage_verifier_agent = Agent(...)
```

推荐角色：

| Agent | 职责 |
| --- | --- |
| `outline_agent` | 根据来源标题树生成目标大纲 |
| `assignment_agent` | 将来源块归属到目标章节 |
| `section_merge_agent` | 合并单个章节内来源块 |
| `conflict_review_agent` | 识别明显冲突和待确认事项 |
| `coverage_verifier_agent` | 审核来源覆盖和输出污染 |

`workflow.py` 负责 deterministic flow：

```text
读取 source blocks
生成目标大纲
归属 source blocks
逐章节合并
冲突审查
覆盖审查
返回结构化结果
```

`tools.py`：

- 查询 source block 原文。
- 获取 source block heading path。
- 渲染 source block 引用。
- 检查 source id 是否存在。

`guardrails.py`：

- 每个 source block 必须有处理结果。
- 输出不得包含 `docmap-*`。
- 合并稿正文不得出现来源文件分组。
- 明显冲突时不得生成正式合并稿。

`handoffs.py`：

仅当需要 agent 之间交出控制权时使用。第一版可以不用 handoff，优先用 deterministic workflow + multiple Runner.run。

### knowledge_builder

用途：

- 将已确认需求和已完成探索结果编译成项目知识库。
- 使用 llm-wiki 风格。

目录：

```text
knowledge_builder/
  __init__.py
  agent.py
  workflow.py
  tools.py
  guardrails.py
```

`tools.py`：

- 读取来源摘要。
- 读取探索事实。
- 检查模块页面路径。

Guardrails：

- 不允许把待确认问题写为正式知识。
- 不允许把失败诊断写成事实。
- 输出页面必须有来源引用。

## API 设计

API 仍保留产品级 endpoint：

```text
POST /agents/document-editor/run
POST /requirements/{document_id}/analysis
POST /requirements/{document_id}/merge
POST /knowledge/{project_id}/build
```

API 不直接调用 `Runner.run`，除非是非常简单的内部 endpoint。

通用调试 endpoint 可以保留，但必须标记为管理调试能力：

```text
POST /agent-debug/{agent_name}/run
```

通用调试 endpoint 不作为产品功能主路径。

## 迁移策略

### 阶段 1：停止错误扩散

- 禁止新增 `prompts.py`。
- 禁止新增 `runner.py`。
- 禁止新增 `*_agent.py`。
- 禁止新增 `*_agent_service.py`。
- 禁止 service 直接写 agent instructions。

### 阶段 2：建立新根目录

新增：

```text
apps/backend/app/ai_agents/
```

先迁移 `document_editor`，因为它最小、风险最低。

### 阶段 3：迁移简单智能体

迁移顺序：

1. `document_editor`
2. `requirement_analysis`
3. `knowledge_builder`
4. `raw_requirement_converter`

每个迁移完成必须满足：

- 有 SDK `Agent` 对象。
- 有 `workflow.py` 调 `Runner.run`。
- 没有 `prompts.py`。
- 没有薄 `runner.py`。
- service 不再 parse JSON。

### 阶段 4：迁移 requirement_merge

分步：

1. 抽出 `outline_agent`。
2. 抽出 `assignment_agent`。
3. 抽出 `section_merge_agent`。
4. 抽出 `coverage_verifier_agent`。
5. 用 `workflow.py` 串联 deterministic flow。
6. 将 source block、artifact、quality gate 留在 service 或 deterministic modules。

### 阶段 5：移除旧框架

删除：

```text
apps/backend/app/agents/definitions.py
apps/backend/app/agents/registry.py
apps/backend/app/agents/runtime.py
apps/backend/app/agents/*/prompts.py
apps/backend/app/agents/*/runner.py
```

前提：

- 所有产品路径已迁到 `ai_agents`。
- 通用模型配置已迁到 `ai_agents/shared`。
- 后台模型分配页面如仍需要 agent list，应改为读取 `ai_agents` manifest 或显式 registry。

## 架构约束测试

新增或更新：

```text
apps/backend/tests/test_ai_agents_architecture.py
```

必须检查：

1. `app/ai_agents/**/prompts.py` 不存在。
2. `app/ai_agents/**/runner.py` 不存在。
3. `app/ai_agents/**/*_agent.py` 不存在。
4. 每个业务目录必须有 `agent.py` 或 `agents.py`。
5. 每个业务目录必须有 `workflow.py`。
6. `app/services/**/*.py` 不得包含大段 agent instructions。
7. `app/services/**/*.py` 不得直接调用 `Runner.run`。
8. `app/api/**/*.py` 不得拼接 agent instructions。

示例：

```python
def test_ai_agents_do_not_use_prompt_modules():
    assert list(AI_AGENTS_ROOT.glob("**/prompts.py")) == []
```

## 验收标准

### 结构验收

- 新增 `app/ai_agents`。
- 每个智能体一个目录。
- 简单智能体有 `agent.py + workflow.py`。
- 复杂智能体有 `agents.py + workflow.py`。
- 无 `prompts.py`。
- 无薄 `runner.py`。
- 无 `*_agent.py`。

### SDK 对齐验收

- Agent 使用 SDK `Agent`。
- 执行使用 `Runner.run(agent, input)`。
- 结构化输出使用 `output_type`。
- 需要模型工具时使用 SDK tools。
- 需要转交时使用 handoffs。
- 需要约束时使用 guardrails。

### 行为验收

- 文档编辑流程可用。
- 原始需求转换流程可用。
- 需求分析流程可用。
- 需求归并流程可用。
- 知识库构建流程可用。
- 模型配置和 tracing 不丢失。

### 边界验收

- service 不写 agent instructions。
- service 不 parse agent JSON。
- service 只负责业务持久化、日志、版本、artifact、质量门禁。
- workflow 只负责 agent 执行和 agent 间编排。

## 与前一版规范的关系

本规范替代以下错误方向：

- `AgentDefinition + registry + runtime.run_agent(agent_id, input)` 作为长期主架构。
- 每个 agent 目录下使用 `prompts.py`。
- 每个 agent 目录下使用薄 `runner.py`。
- service 通过兼容 wrapper 调 agent。

前一版 `2026-05-31-openai-agents-sdk-architecture-refactor-spec.md` 中关于“不要让 service 拼 prompt、不要让 service 直接调用 generic runtime、输出契约应归 Agent”的原则仍然有效；但其中 `prompts.py/runner.py/AgentDefinition` 相关结构不再采用。

## 最终目标形态

简单智能体：

```text
API -> service 或 workflow -> ai_agents/document_editor/workflow.py -> Runner.run(document_editor_agent, input)
```

复杂智能体：

```text
API -> service
    -> deterministic source/artifact preparation
    -> ai_agents/requirement_merge/workflow.py
       -> Runner.run(outline_agent, input)
       -> Runner.run(section_merge_agent, input)
       -> guardrails
    -> service 持久化结果
```

这是本项目后续智能体架构的目标状态。
