# 00-11 AI测试系统 - 模型配置与 Agent Runtime PRD

> **事实源日期**：2026-07-26
>
> **事实源**：
> - `apps/backend/app/agents/capabilities.py:11-72`（12 项 capability 枚举）
> - `apps/backend/app/agents/model_selection.py`（`resolve_model_selection / build_agent_model / thinking_disabled_extra_body`）
> - `apps/backend/app/api/v1/ai.py`（`/ai/capabilities`、`/model-assignments`）
> - `apps/backend/app/api/v1/models.py`（`/models/providers`、`/models/providers/{id}/test`）
> - `apps/backend/app/agents/page_exploration/agent.py`（`deepagents.create_deep_agent + FilesystemBackend + ToolCallLimitMiddleware`）
> - `apps/backend/pyproject.toml`（`deepagents>=0.6.7 / langchain>=1.3.13 / langchain-openai>=1.3.5 / langchain-deepseek>=1.1.0`）
> - `apps/backend/app/seed/schema.py`（`model_providers / model_assignments` 表定义）
> - `apps/backend/app/schemas/model.py`
> - `apps/frontend/src/app/(main)/settings/models/page.tsx`（Provider 管理页面）
> - `apps/frontend/src/app/(main)/settings/models/assignments/page.tsx`（能力分配页面）

---

## 1. 范围与目标

本文档细化模型配置、Agent 编排、Skill 接入和任务运行时的实现规范。

核心规则：

- 管理员统一配置模型 Provider。
- 系统支持配置多个 Provider、Base URL、API Key 和模型名。
- **不使用 OpenAI Agents SDK**，当前使用 `deepagents>=0.6.7` SDK + `langchain>=1.3.13`。
- 采用"统一 Agent Runtime + 模块专用 Agent + Skill + 后端领域服务"的组合架构。
- 不同 Agent 可以选择不同模型。
- 测试代码生成和自愈建议优先使用 coding 能力强的模型。
- 模型分配以 capability_id 为 PK，按 AI 能力映射到 model_provider_id。

---

## 2. 业务边界

### 2.1 本模块负责

- 配置模型 Provider（名称、类型、Base URL、API Key、模型名、状态）
- 配置模型用途（capability 到 provider 的映射）
- 管理 AI capability 类型
- 记录 Agent 任务输入、输出、状态和日志
- 控制任务超时、重试、人工确认点

### 2.2 本模块不负责

- 不负责具体业务文档内容
- 不负责直接执行浏览器动作
- 不负责存储大文件产物，只保存引用路径
- 不负责存储 AI 推理的完整 prompt/响应上下文（只保存摘要和产物路径）

---

## 3. 模型 Provider 管理

### 3.1 Provider CRUD

管理员可在前端对模型 Provider 进行增删改操作，后端 API Key 按原文保存。

| 操作 | 路由 | 权限 | 说明 |
| --- | --- | --- | --- |
| 列表 | `GET /models/providers` | 登录用户 | 返回脱敏 API Key |
| 新增 | `POST /models/providers` | `require_admin` | 按原文保存 API Key |
| 编辑 | `PATCH /models/providers/{id}` | `require_admin` | 可选不传 API Key（保留旧值） |
| 删除 | `DELETE /models/providers/{id}` | `require_admin` | 需无 cascade 冲突 |
| 连通性测试 | `POST /models/providers/{id}/test` | 登录用户 | 实时调用模型，返回成功/失败消息 |

### 3.2 API Key 显示/隐藏

- 前端展示脱敏 Key（原文保存，按需显示）
- 列表页 API Key 列默认隐藏
- 编辑弹窗支持 Show/Hide 切换（`Eye / EyeOff` 图标）
- 旧文档错误说明已废弃：API Key **按原文保存用于调用**，不做哈希（哈希只用于 operation log 快照）

### 3.3 健康状态（health_status）

| 状态值 | 说明 |
| --- | --- |
| `unknown` | 默认值，未测试 |
| `healthy` | 最近一次连通性测试成功 |
| `unhealthy` | 连通性测试失败（服务端异常） |
| `timeout` | 连通性测试超时 |
| `testing` | 测试进行中（前端临时状态） |

Provider 记录 `last_test_at`（最近测试时间）和 `last_test_message`（最近测试消息）。

### 3.4 Provider 数据模型

表 `model_providers`（SQLite）：

```sql
CREATE TABLE model_providers (
  id                  TEXT PRIMARY KEY,
  provider            TEXT NOT NULL,          -- "OpenAI"、"DeepSeek" 等
  model               TEXT NOT NULL,          -- "gpt-4o"、"deepseek-chat" 等
  base_url            TEXT NOT NULL,          -- "https://api.openai.com/v1"
  api_key             TEXT NOT NULL DEFAULT '',
  description         TEXT NOT NULL DEFAULT '',
  status              TEXT NOT NULL CHECK(status IN ('enabled','disabled')),
  health_status       TEXT NOT NULL DEFAULT 'unknown'
                       CHECK(health_status IN ('unknown','healthy','unhealthy','timeout','testing')),
  last_test_at        TEXT,
  last_test_message   TEXT NOT NULL DEFAULT '',
  created_by          TEXT NOT NULL,
  created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, model, base_url)
);
```

注意：一条 Provider 记录绑定一个具体模型名；如同一 Provider 需使用多个模型，需创建多条配置。

---

## 4. 模型能力分配

### 4.1 分配规则

- 表 `model_assignments`：PK = `capability_id`（每个 capability 只能分配一个模型）
- 前端支持按行单独分配，也支持"模型统一配置"（批量 PUT）
- 前端下拉框只展示 `status='enabled'` 的 Provider
- 前端支持展示当前已分配的 provider/model 名称

### 4.2 分配数据模型

```sql
CREATE TABLE model_assignments (
  capability_id      TEXT PRIMARY KEY,
  model_provider_id  TEXT NOT NULL,
  created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(model_provider_id) REFERENCES model_providers(id) ON DELETE CASCADE
);
```

API：

| 路由 | 说明 |
| --- | --- |
| `GET /ai/capabilities` | 列出全部 12 项 AI capability（含 id/name/description） |
| `GET /model-assignments` | 列出所有 capability 的当前分配（含 capability 详情 + provider 详情） |
| `PUT /model-assignments/{capability_id}` | 更新单个 capability 的模型分配（body: `{ model_provider_id }`） |

---

## 5. AI 能力枚举（12 项）

`apps/backend/app/agents/capabilities.py:11-72` 定义：

| Capability ID | 名称 | 用途说明 |
| --- | --- | --- |
| `document_editor` | 文档修改 | 根据用户指令修改 Markdown 文档，返回修改后的文档、修改摘要和风险提示。 |
| `requirement_standardization` | 需求标准化 | 负责将上传的 PDF、Word、TXT 和 Markdown 需求文件标准化为结构稳定的标准 Markdown。 |
| `requirement_analysis` | 需求分析 | 基于当前主需求 Markdown 工作稿，生成模块分析、澄清问题、可测试性检查和质量门禁结果。 |
| `knowledge_query` | 项目知识库查询 | 基于最终需求文档执行 agentic 检索，返回带来源引用的项目知识库答案。 |
| `test_case_generation` | 测试用例生成 | 根据最终需求文档生成完整、系统、可执行的测试用例集。 |
| `test_point_generation` | 测试点生成 | 根据指定最终需求版本生成结构化、可追溯、可评审的业务测试点。 |
| `api_test_generation` | 接口自动化用例生成 | 根据 OpenAPI 接口定义、接口环境摘要和测试重点生成结构化接口自动化用例。 |
| `api_scenario_orchestration` | 接口自动化场景编排 | 根据业务目标和当前项目接口资产生成可审阅的接口自动化场景计划。 |
| `ui_test_generation` | UI 自动化代码生成 | 根据已采纳测试用例和站点探索证据生成受控 pytest + Playwright UI 自动化代码。 |
| `page_exploration` | 站点探索 | 负责自动化探索 Web 应用，包括页面分析、元素识别、登录表单分析和验证码识别等多模态任务。 |
| `performance_script_generation` | 性能测试脚本计划生成 | 根据脱敏后的单接口配置生成受控 LocustScriptPlan。 |
| `performance_report_analysis` | 性能测试报告分析 | 根据脱敏后的 Locust 统计事实生成性能问题、证据和优化建议。 |

> 旧 PRD 声称 14 种能力，已废弃；当前实现为 12 种。

---

## 6. Agent Runtime

### 6.1 技术栈

**不使用 OpenAI Agents SDK**。当前运行时基于：

- `deepagents>=0.6.7`：核心 Agent 框架，提供 `create_deep_agent`
- `langchain>=1.3.13`：Agent 构建与工具集成
- `langchain-openai>=1.3.5`：OpenAI 兼容模型（OpenAI / 通义 / 硅基流动等）
- `langchain-deepseek>=1.1.0`：DeepSeek 模型专用集成

### 6.2 探索 Agent 示例

`apps/backend/app/agents/page_exploration/agent.py` 是当前 Agent Runtime 的典型实现：

```python
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import ToolCallLimitMiddleware

def page_exploration_agent(model, tools=None, skill_names=None,
                           max_actions: int = 80, exploration_mode: str = "goal"):

    backend = FilesystemBackend(
        root_dir=str(backend_root),
        virtual_mode=True,       # 虚拟模式，不落真实文件
    )

    skills = [
        "app/agents/page_exploration/skills/page-explorer/",
        "app/agents/page_exploration/skills/locator-best-practices/",
    ]

    middleware = [
        InvalidToolCallRecoveryMiddleware(max_retries=2),
        ToolCallLimitMiddleware(thread_limit=max_actions, run_limit=max_actions),
    ]

    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=SYSTEM_PROMPT,
        backend=backend,         # FilesystemBackend：Skill 自动发现 + 历史存储
        skills=skills,           # Skill 自动加载（deepagents 管理汇总中间件）
        middleware=middleware,
    )
```

关键组件说明：

| 组件 | 职责 |
| --- | --- |
| `FilesystemBackend` | 虚拟文件系统后端，用于 Skill 自动发现、汇总中间件历史存储 |
| `ToolCallLimitMiddleware` | LangChain 中间件，硬截断单次 run 内的工具调用次数，防止死循环 |
| `InvalidToolCallRecoveryMiddleware` | 捕获工具调用异常并重试（最多 2 次） |
| `create_deep_agent` | deepagents 提供，自动追加汇总中间件和 Skill 注入 |

### 6.3 架构层次

```
统一 Agent Runtime（deepagents + langchain）
  -> 模块专用 Agent（page_exploration_agent 等）
      -> Skill（.skill/ SKILL.md 自动加载）
      -> Middleware（ToolCallLimit / Recovery）
      -> Backend（FilesystemBackend）
          -> Tools（Playwright CLI / 数据库 / 存储）
```

职责边界：

| 层级 | 职责 | 不负责 |
| --- | --- | --- |
| Agent Runtime | 任务编排、模型选择、Skill 调用、日志、审计、权限、人工确认点 | 不写具体业务规则 |
| 模块专用 Agent | 明确业务目标、输入输出 Schema、调用哪些 Skill、生成结构化结果 | 不直接绕过后端修改业务状态 |
| Skill | 封装稳定能力（探索 / 需求分析 / 代码生成等），按 SKILL.md 自动加载 | 不决定最终业务状态 |
| 后端领域服务 | 校验、落库、版本化、状态流转、权限控制 | 不直接生成大段 AI 内容 |

---

## 7. 模型选择策略

`apps/backend/app/agents/model_selection.py` 实现运行时模型解析：

### 7.1 `resolve_model_selection(capability_id)`

从数据库读取 `model_assignments` → 验证 `status='enabled'` 且 `api_key` 非空 → 返回 `ModelSelection(provider, model, base_url, api_key)`。

如未分配或未启用，抛出 `ValueError` 并阻止 Agent 启动。

### 7.2 `build_agent_model(selection, *, extra_body=None)`

根据 `ModelSelection.provider` 判断模型类型，构建 LangChain 模型实例：

| 判断条件 | 模型类 | 包 |
| --- | --- | --- |
| provider 或 model 含 `deepseek` | `ChatDeepSeek` | `langchain-deepseek` |
| 否则 | `ChatOpenAI` | `langchain-openai` |

### 7.3 `thinking_disabled_extra_body(selection)`

- DeepSeek 模型：返回 `{"thinking": {"type": "disabled"}}`（关闭深度思考，提升响应速度）
- MiniMax 模型：同样关闭思考
- 其他模型：返回 `None`

### 7.4 完整调用链

```
运行时入口（如 performance_report_analysis）
  -> resolve_model_selection("performance_report_analysis")
       -> model_repo.find_model_assignment(db, "performance_report_analysis")
       -> 验证 enabled + api_key 非空
       -> 返回 ModelSelection
  -> build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
       -> 判断 deepseek/openai
       -> 构造 ChatDeepSeek 或 ChatOpenAI 实例（temperature=0）
  -> 注入 page_exploration_agent() 或其他 Agent
```

---

## 8. 数据模型（完整）

### 8.1 `model_providers`

见 §3.4。

### 8.2 `model_assignments`

见 §4.2。

### 8.3 关联说明

- `model_assignments.model_provider_id` → `model_providers.id`（ON DELETE CASCADE）
- `model_providers.created_by` → `users.id`
- Provider 唯一约束：`UNIQUE(provider, model, base_url)`（同名同模型同地址只允许一条记录）

---

## 9. API 路由清单

| 路由 | 方法 | 权限 | 说明 |
| --- | --- | --- | --- |
| `/ai/capabilities` | GET | 登录用户 | 列出全部 12 项 AI capability |
| `/model-assignments` | GET | 登录用户 | 列出所有 capability 的分配 |
| `/model-assignments/{capability_id}` | PUT | 登录用户 | 更新单个 capability 的分配 |
| `/models/providers` | GET | 登录用户 | 列出所有模型 Provider |
| `/models/providers` | POST | `require_admin` | 新增模型 Provider |
| `/models/providers/{id}` | PATCH | `require_admin` | 编辑模型 Provider |
| `/models/providers/{id}` | DELETE | `require_admin` | 删除模型 Provider |
| `/models/providers/{id}/test` | POST | 登录用户 | 连通性测试 |

---

## 10. 前端页面清单

| 路径 | 功能 | 权限 |
| --- | --- | --- |
| `/settings/models` | 模型管理：列表、新增、编辑、删除、测试连通性、API Key Show/Hide | 管理员可见全部操作；非管理员仅"测试" |
| `/settings/models/assignments` | 模型分配：按 capability 分配模型（单行下拉 + 批量统一配置） | 登录用户可见 |

---

## 11. 验收规则

### 11.1 Provider 管理

- [ ] 管理员能新增模型 Provider（provider/model/base_url 必填）
- [ ] 管理员能编辑模型 Provider（API Key 可选留空，保留旧值）
- [ ] 管理员能删除模型 Provider（无引用冲突）
- [ ] 管理员能点击"测试"触发连通性测试，显示 healthy/unhealthy/timeout
- [ ] 列表页 API Key 默认脱敏，可切换 Show/Hide
- [ ] 访客和测试工程师无法通过前端修改 Provider

### 11.2 能力分配

- [ ] 列表页展示全部 12 项 capability 的当前分配状态
- [ ] 下拉框只展示 `status='enabled'` 的 Provider
- [ ] 单行分配保存后即时生效
- [ ] "模型统一配置"弹窗可批量应用到全部 capability
- [ ] 模型分配更新写入 `operation_logs`（log_type='config'）

### 11.3 Agent Runtime

- [ ] 探索 Agent 使用 `deepagents.create_deep_agent` + `FilesystemBackend`
- [ ] 工具调用通过 `ToolCallLimitMiddleware` 硬截断（防止死循环）
- [ ] 运行时通过 `resolve_model_selection` 读取数据库分配，无分配则拒绝启动
- [ ] DeepSeek 模型调用时自动注入 `thinking=disabled`

### 11.4 模型选择

- [ ] `resolve_model_selection` 检查 assignment 存在性、enabled 状态、api_key 非空
- [ ] `build_agent_model` 根据 provider 名称正确选择 ChatDeepSeek / ChatOpenAI
- [ ] `thinking_disabled_extra_body` 仅对 deepseek/minimax 返回 extra_body
- [ ] 异常信息明确指出哪个 capability 未分配或未启用
