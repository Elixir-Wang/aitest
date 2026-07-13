# 接口自动化 Agent 能力拆分改造 Spec

## 背景

当前接口自动化后端已经具备两类本质不同的生成能力：

1. 根据 OpenAPI、环境摘要、历史用例和生成目标，生成结构化接口测试用例。
2. 根据已落库的结构化接口测试用例，生成可执行的 `pytest + Requests` 自动化代码。

现有实现没有清晰表达这两个能力边界：

- 结构化接口用例生成 Agent 位于 `apps/backend/app/agents/api_automation/` 根目录。
- pytest 代码生成逻辑位于 `apps/backend/app/services/api_automation/script_generator.py`。
- pytest 工程目录与 `project_id` 绑定，由 `script_workspace.py` 计算为项目级目录。
- Agent 配置、确定性代码生成、业务编排和生成制品存储存在概念混合。

当前 `apps/backend/app/agents` 的项目约定是存放 Agent 定义、结构化输入输出、模型调用服务、Skill 和参考规则。该目录不是项目数据目录，也不是运行制品目录。因此需要把接口自动化的两类 Agent 能力明确拆分，同时把 `project_id` 从 Agent 配置和生成能力目录中移除。

## 目标

- 将接口自动化拆分为“接口用例生成”和“pytest + Requests 代码生成”两个独立 Agent 子能力。
- 将现有接口用例生成 Agent 迁移到 `api_automation/case_generation/`。
- 在 `api_automation/pytest_requests/` 中建立代码生成 Agent 配置和契约。
- 明确 `project_id` 只属于外层业务上下文，不参与 Agent 目录结构和 Agent 配置路径计算。
- 将生成规则、代码结构要求、请求映射和断言映射放入 pytest Agent Skill。
- 保持 API、Repository、运行器和业务权限仍由 `services/api_automation` 编排。
- 迁移后保持现有接口用例生成和脚本生成行为兼容。
- 为未来增加 Playwright API、JMeter 或其他代码生成能力保留清晰扩展点。

## 非目标

- 本轮不重新设计 OpenAPI 导入、接口资产、接口环境、接口场景和运行报告。
- 本轮不修改前端交互流程和页面信息架构。
- 本轮不引入新的 Agent 框架或替换现有 LangChain `create_agent`。
- 本轮不允许 Agent 直接访问数据库、文件系统或项目权限信息。
- 本轮不把运行器、pytest 子进程管理和报告解析迁入 `agents`。
- 本轮不改变脚本生成 API 的 URL。
- 本轮不引入按 `project_id` 创建 Agent 配置、Skill 或模板目录的机制。
- 本轮不要求一次性支持多种自动化框架。

## 核心判断

### `agents` 目录的职责

`apps/backend/app/agents` 只存放 AI 能力相关定义：

- Agent 创建与模型绑定。
- Agent 输入和结构化输出模型。
- Prompt、Skill 和参考规则。
- Agent 调用封装和结果校验。
- 与具体项目无关的确定性转换能力。

以下内容不属于 `agents`：

- 项目鉴权。
- 项目、接口、用例数据库查询。
- API 路由。
- 数据库 Repository。
- 项目文件存储路径计算。
- pytest 子进程执行。
- 运行日志和报告持久化。

### 两个 Agent 能力的区别

| 能力 | 输入 | 输出 | 核心问题 |
|---|---|---|---|
| `case_generation` | OpenAPI endpoint、环境摘要、历史用例、生成目标 | 结构化接口测试用例 | 测什么 |
| `pytest_requests` | 已确认的结构化接口测试用例、endpoint 定义、框架配置 | 结构化代码文件集合 | 如何用 pytest + Requests 执行 |

两个能力必须分别定义 schemas、service、agent 和 Skill，不共享模糊的 `agent.py` 根入口。

## 目标目录结构

```text
apps/backend/app/agents/
└── api_automation/
    ├── __init__.py
    │
    ├── case_generation/
    │   ├── __init__.py
    │   ├── agent.py
    │   ├── schemas.py
    │   ├── service.py
    │   └── skills/
    │       └── api-automation-case-generation/
    │           ├── SKILL.md
    │           └── references/
    │               ├── assertion-guidelines.md
    │               ├── generation-principles.md
    │               └── request-data-rules.md
    │
    └── pytest_requests/
        ├── __init__.py
        ├── agent.py
        ├── schemas.py
        ├── service.py
        └── skills/
            └── pytest-requests-code-generation/
                ├── SKILL.md
                └── references/
                    ├── project-structure.md
                    ├── generation-rules.md
                    ├── request-mapping.md
                    └── assertion-mapping.md
```

### 顶层 `api_automation/__init__.py`

顶层包只承担命名空间职责，不重新暴露含义模糊的 `generate_api_test_cases` 或通用 `agent`。

允许按能力显式导出：

```python
from app.agents.api_automation.case_generation import generate_api_test_cases
from app.agents.api_automation.pytest_requests import generate_pytest_requests_code
```

业务代码应优先直接导入具体子能力，避免重新形成大而全的 facade。

## `case_generation` 能力

### 迁移范围

现有以下文件整体迁入 `case_generation/`：

```text
apps/backend/app/agents/api_automation/agent.py
apps/backend/app/agents/api_automation/schemas.py
apps/backend/app/agents/api_automation/service.py
apps/backend/app/agents/api_automation/skills/api-automation-case-generation/
```

迁移后的职责和行为保持不变：

- 使用 `CAPABILITY_ID = "api_test_generation"` 选择模型。
- 使用 `SkillMiddleware` 加载 `api-automation-case-generation/SKILL.md` 和 references。
- 使用结构化输出返回 `ApiAutomationGenerationResult`。
- 不编造接口、字段、状态码、业务规则和敏感数据。
- 不负责保存接口用例和更新生成任务状态。

### 导入路径调整

旧路径：

```python
from app.agents.api_automation.schemas import ApiAutomationGenerationInput
from app.agents.api_automation import service as api_generation_agent_service
```

新路径：

```python
from app.agents.api_automation.case_generation.schemas import ApiAutomationGenerationInput
from app.agents.api_automation.case_generation import service as api_generation_agent_service
```

所有调用点必须迁移完成，不长期保留旧模块兼容壳。

## `pytest_requests` 能力

### 职责

`pytest_requests` 根据已经通过业务服务校验的 endpoint 和结构化用例，生成代码文件集合。它不查询数据库、不识别项目权限、不计算项目存储根目录。

职责包括：

- 识别请求方法、路径、path/query/header/body/files 数据映射。
- 识别普通 JSON、表单、multipart 上传和二进制下载。
- 将结构化断言映射为执行器支持的 pytest 断言调用。
- 生成端点级测试模块和数据文件。
- 声明共享 fixture、HTTP client、认证和断言支持文件。
- 返回稳定、可验证、与物理存储路径解耦的结构化文件结果。

禁止承担：

- 根据 `project_id` 查询接口或用例。
- 拼接 `PROJECT_FILE_STORAGE_ROOT`。
- 直接写入项目目录。
- 创建或更新脚本数据库记录。
- 启动 pytest。
- 读取真实 token、密码、cookie 或本机上传文件。

### 输入契约

建议定义：

```python
class PytestRequestsGenerationInput(BaseModel):
    endpoint: PytestRequestsEndpoint
    cases: list[PytestRequestsCase]
    framework_config: PytestRequestsFrameworkConfig
```

输入必须是单个 endpoint 及其用例集合。批量接口由外层 Service 分组后分别调用，避免 Agent 自行判断文件归属。

输入不包含：

- `project_id`
- 数据库连接
- 用户信息
- 物理输出目录
- 明文环境密钥

`framework_config` 只允许描述稳定框架能力，例如：

- Python 目标版本。
- pytest 配置。
- Requests client 能力。
- 执行器支持的断言类型。
- 文件逻辑根目录约定。

### 输出契约

建议定义：

```python
class GeneratedCodeFile(BaseModel):
    key: str
    kind: Literal["test", "data", "support", "config", "documentation"]
    language: Literal["python", "json", "toml", "ini", "markdown"]
    content: str


class PytestRequestsGenerationResult(BaseModel):
    endpoint_id: str
    endpoint_key: str
    files: list[GeneratedCodeFile]
    case_count: int
    warnings: list[str] = []
```

`key` 是逻辑文件键，例如：

```text
tests/test_post_users_apiend_abcd.py
data/test_post_users_apiend_abcd.json
support/client.py
support/auth.py
support/assertions.py
conftest.py
pytest.ini
pyproject.toml
README.md
```

Agent 输出逻辑文件键，不输出磁盘绝对路径或包含 `project_id` 的路径。

### Agent 与确定性代码生成边界

Agent 负责理解和归一化：

- 请求数据应放入哪个位置。
- 哪些断言可以执行。
- 上传和下载应采用什么执行语义。
- 用例中是否存在无法生成的缺失数据。
- 输入结构与 pytest 文件模型之间的转换决策。

确定性代码模板负责输出最终 Python、JSON、TOML 和 INI 内容。

不允许 LLM 自由编写整个 pytest 工程框架。推荐流程：

```text
结构化接口用例
    ↓
pytest_requests Agent 归一化为代码生成模型
    ↓
确定性渲染器生成文件内容
    ↓
Service 持久化文件和脚本记录
```

如果当前阶段不需要 LLM 判断，可以让 `service.py` 调用确定性渲染器，但该能力仍归属 `agents/api_automation/pytest_requests`，并继续遵守相同输入输出契约。

## Skill 设计

### `pytest-requests-code-generation/SKILL.md`

Skill 至少规定：

- 只消费输入中存在的 endpoint 和 cases。
- 每次只处理一个 endpoint。
- 一个 endpoint 对应一个测试模块和一个数据文件。
- 每条用例通过 `pytest.mark.parametrize` 独立报告。
- 不在测试函数中遍历项目全部数据文件。
- 不生成输入中不存在的字段、路径、状态码和业务断言。
- 不嵌入 base URL、token、cookie、密码和本机绝对路径。
- 不生成执行器不支持的断言类型。
- 上传文件路径必须使用环境变量占位。
- 下载响应不能使用 JSONPath 断言。

### references

`project-structure.md`：

- 逻辑 pytest 工程文件结构。
- 配置、support、tests 和 data 的文件职责。
- 文件 key 命名规则。

`generation-rules.md`：

- 单 endpoint 生成单位。
- 幂等生成规则。
- 共享文件和端点文件边界。
- 代码格式及禁止项。

`request-mapping.md`：

- path、query、headers、JSON body、form body 和 files 映射。
- 环境变量替换。
- Content-Type 和序列化约定。

`assertion-mapping.md`：

- 当前执行器支持的断言类型。
- JSON、header、content type、body 和 hash 断言映射。
- 不支持断言的 warning 处理方式。

## Service 层职责

`apps/backend/app/services/api_automation/service.py` 继续作为业务编排入口：

1. 校验管理员权限和项目可见性。
2. 校验 endpoint 属于当前项目。
3. 查询 endpoint 当前已落库用例。
4. 按 endpoint 分组并过滤可生成用例。
5. 构造不含 `project_id` 的 Agent 输入。
6. 调用 `pytest_requests.service`。
7. 将逻辑文件结果交给制品存储组件。
8. upsert endpoint 对应脚本记录。
9. 返回本次创建、更新和未变化的脚本。

`project_id` 在步骤 1、2、3、7、8 中可以存在，但不得进入 Agent 配置路径或 Skill 路径。

## 文件持久化边界

本 Spec 区分“Agent 能力目录”和“生成制品目录”。

### Agent 能力目录

固定为：

```text
apps/backend/app/agents/api_automation/pytest_requests/
```

该目录随代码仓库发布，与 `project_id` 无关。

### 生成制品

生成制品的物理存储策略由 Service/Storage 决定。Agent 只返回逻辑文件键和内容。

本次改造至少要求：

- 删除 Agent 对项目存储路径的依赖。
- 删除生成器对 `project_id` 的目录拼接责任。
- 物理路径必须由独立的制品存储函数解析。
- 数据库只保存可解析的制品标识或受控路径。
- 所有路径解析必须防止越界访问。

物理制品是否继续按项目隔离属于存储设计问题，不影响 Agent 能力目录。即使存储层按项目隔离，也不能把该目录理解为 Agent 配置目录。

## 现有文件迁移

### 移动

```text
apps/backend/app/agents/api_automation/agent.py
  → apps/backend/app/agents/api_automation/case_generation/agent.py

apps/backend/app/agents/api_automation/schemas.py
  → apps/backend/app/agents/api_automation/case_generation/schemas.py

apps/backend/app/agents/api_automation/service.py
  → apps/backend/app/agents/api_automation/case_generation/service.py

apps/backend/app/agents/api_automation/skills/api-automation-case-generation/
  → apps/backend/app/agents/api_automation/case_generation/skills/api-automation-case-generation/
```

### 新增

```text
apps/backend/app/agents/api_automation/pytest_requests/__init__.py
apps/backend/app/agents/api_automation/pytest_requests/agent.py
apps/backend/app/agents/api_automation/pytest_requests/schemas.py
apps/backend/app/agents/api_automation/pytest_requests/service.py
apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/SKILL.md
apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/references/project-structure.md
apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/references/generation-rules.md
apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/references/request-mapping.md
apps/backend/app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/references/assertion-mapping.md
```

### 删除或收缩

```text
apps/backend/app/services/api_automation/script_generator.py
apps/backend/app/services/api_automation/script_workspace.py
```

处理原则：

- 属于生成能力、模板和文件 key 规则的代码迁入 `pytest_requests`。
- 属于物理路径、锁和原子写入的代码保留在 Service/Storage 层，但重命名为制品存储职责，不能继续叫 Agent workspace。
- 不保留两套并行生成器。

## API 兼容性

现有接口保持不变：

```http
POST /api/v1/projects/{project_id}/api-automation/scripts/generate
```

现有请求继续使用 endpoint 选择：

```json
{
  "endpoint_ids": ["apiend-1"],
  "force": false
}
```

API 层不得直接调用 Agent。调用链保持：

```text
API Router
  → services/api_automation/service.py
    → agents/api_automation/pytest_requests/service.py
      → Agent/确定性渲染器
```

现有脚本列表、文件查看、编辑和执行 API 不因 Agent 目录拆分改变。

## 数据与幂等性

- endpoint 仍是脚本生成和更新的最小所有权单位。
- `project_id + endpoint_id` 仍可作为数据库脚本记录唯一业务键。
- Agent 输出的 `endpoint_key` 必须由稳定 endpoint 身份、method 和 path 生成。
- 相同 endpoint 和 cases 输入必须生成相同逻辑文件 key。
- 未选择的 endpoint 文件不得被删除或覆盖。
- 共享文件由 Service 在制品层合并，不得因单 endpoint 生成产生重复数据库脚本记录。
- `force=false` 时可继续通过 source hash 跳过未变化 endpoint。

## 架构约束

### 必须满足

- `api_automation/case_generation` 和 `api_automation/pytest_requests` 均有明确入口。
- 两个子能力分别拥有自己的 schemas、service、agent 和 Skill。
- `pytest_requests` 输入模型不存在 `project_id` 字段。
- `pytest_requests` 不导入 Repository、数据库连接或项目权限模块。
- API Router 不直接创建或运行 Agent。
- Runner 不迁入 `agents`。
- Skill 路径通过当前文件相对路径定位，不使用项目存储路径。

### 禁止出现

- `agents/api_automation/<project_id>/...`
- `agents/api_automation/pytest_requests/<project_id>/...`
- Agent 内拼接 `PROJECT_FILE_STORAGE_ROOT`。
- Agent 内调用 `api_automation_repo`。
- Service 和 Agent 同时保留两套 pytest 模板。
- 顶层 `api_automation/agent.py` 同时承载两种生成能力。
- 使用模糊名称如 `generate_code()`、`generation_agent()` 作为公共入口。

## 测试要求

### Agent 架构测试

新增或更新架构测试，验证：

- `case_generation/agent.py` 存在。
- `pytest_requests/agent.py` 存在。
- 顶层 `api_automation/agent.py`、`schemas.py`、`service.py` 已删除。
- 两个 Skill 的 `SKILL.md` 均存在。
- pytest Agent 不导入 Repository、数据库和项目 storage root。
- 业务 Service 使用具体子能力导入路径。

### case generation 回归测试

迁移并保持：

```text
apps/backend/tests/test_api_automation_generation_agent.py
```

验证原结构化用例输出、Skill 加载、模型选择和错误处理行为不变。

### pytest requests 生成测试

重构：

```text
apps/backend/tests/test_api_automation_script_generator.py
```

至少覆盖：

- 单 endpoint 生成一个 test 文件和一个 data 文件。
- 多条用例通过参数化表达。
- JSON、query、path、header 和 form 请求映射。
- 单文件和多文件上传映射。
- 下载断言映射。
- 不支持断言返回 warning 或明确失败。
- 输入中不需要 `project_id`。
- 输出只有逻辑文件 key，不包含绝对路径。
- 相同输入输出稳定。
- 不生成明文凭据和本机绝对路径。

### Service 集成测试

验证：

- Service 完成项目权限和 endpoint 归属校验后才调用 Agent。
- Service 只把选择 endpoint 的用例传给 pytest Agent。
- 新 endpoint 追加，已有 endpoint 更新，未选择 endpoint 保留。
- source hash 未变化时不重复调用生成能力。
- 制品保存失败时不写入成功脚本记录。

### 推荐验证命令

```powershell
uv run pytest tests/test_ai_agents_architecture.py tests/test_agent_architecture_boundaries.py -q
uv run pytest tests/test_api_automation_generation_agent.py -q
uv run pytest tests/test_api_automation_script_generator.py -q
uv run pytest tests/test_api_automation_runner.py tests/test_api_automation_schema_repo.py -q
```

## 迁移顺序

1. 创建 `case_generation` 包并移动现有 Agent 文件和 Skill。
2. 更新所有旧导入路径并通过 case generation 回归测试。
3. 定义 `pytest_requests` 输入输出 schemas。
4. 创建 pytest Agent、Skill 和 references。
5. 将现有 script generator 转换为该能力下的确定性渲染实现。
6. 将物理路径、锁和原子写入收敛到 Service/Storage 制品层。
7. 更新 `generate_project_scripts` 调用链。
8. 删除旧根模块和旧并行生成器。
9. 更新架构测试和 API 自动化相关测试。
10. 执行完整后端回归。

## 验收标准

### 目录验收

- 存在 `agents/api_automation/case_generation/`。
- 存在 `agents/api_automation/pytest_requests/`。
- 两个目录职责清晰且均有独立 Skill。
- 不再存在含义模糊的顶层 `api_automation/agent.py`、`schemas.py`、`service.py`。

### 能力验收

- 接口用例生成功能迁移后行为不变。
- pytest 代码生成通过 `pytest_requests` 能力完成。
- pytest Agent 输入和配置与 `project_id` 无关。
- 相同 endpoint 和 cases 输入产生稳定逻辑文件结果。
- 代码生成不包含输入外接口、用例、字段和敏感数据。

### 分层验收

- API 层只处理 HTTP 契约和依赖注入。
- Service 层处理项目权限、数据库读取、批量分组和制品持久化。
- Agent 层处理生成规则、结构化决策和确定性渲染。
- Repository 层只处理数据库。
- Runner 层只处理 pytest 执行和报告输出。

### 回归验收

- 现有接口用例生成测试通过。
- 现有脚本生成、脚本查看、编辑、执行和报告测试通过。
- Agent 架构边界测试通过。
- 前端现有 API 合同不需要修改。

## 与历史 Spec 的关系

本 Spec 是以下历史设计中 Agent 目录和 pytest 代码生成职责的增量修正：

- `docs/superpowers/specs/2026-07-08-api-automation-openapi-design.md`
- `docs/superpowers/specs/2026-07-09-api-automation-case-structure-design.md`
- `docs/superpowers/specs/2026-07-10-api-automation-batch-generation-design.md`

如历史 Spec 与本 Spec 冲突，以本 Spec 为准，特别是以下内容：

- pytest 生成能力归属 `agents/api_automation/pytest_requests`。
- 现有接口用例生成能力归属 `agents/api_automation/case_generation`。
- `project_id` 不参与 Agent 目录结构和 Agent 配置路径。
- `services/api_automation/script_generator.py` 不再作为独立的生成能力归属点。

