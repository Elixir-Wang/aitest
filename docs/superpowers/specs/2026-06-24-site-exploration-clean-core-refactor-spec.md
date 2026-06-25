# 站点探索干净核心重构 Spec

## 背景

当前站点探索已经形成三层结构：

- Agent 决策层：`apps/backend/app/agents/site_exploration/execution_decision/`
- Python 编排层：`apps/backend/app/services/exploration/unified_orchestrator.py`
- Node Playwright 执行层：`apps/backend/runners/playwright/browser-session.mjs`

这套结构的方向是对的，但经过多轮改造后，探索模块出现了明显的补丁式复杂度：

- `ExplorationStep` 同时承载计划、执行、前端展示和重试策略，字段越来越多。
- `target_description`、`target_selector`、`execution_strategy` 让 LLM 先猜步骤，再由执行层二次匹配页面，和“只能基于真实观察行动”的原则冲突。
- `UnifiedExplorationOrchestrator` 同时负责任务生命周期、规划、执行、Agent 调用、事件发布、artifact 聚合和报告字段拼装。
- Agentic Loop 目前每轮只能返回一个 action，动作越多，模型调用次数越多。
- Node runner 已经生成 `placeholder` selector，但 `selector-validator.mjs` 还不支持 `placeholder`。
- `graph.yaml` 已被 v2 artifact 消费，但当前新编排链路的 graph edge 记录不足。
- 复用执行尚未形成独立能力，成功探索得到的稳定 locator 和动作序列没有沉淀为零 LLM replay。

本次重构目标是按新的目标目录完整重构探索模块，保留外部任务入口和 v2 artifact 消费契约，但内部包结构、数据模型和执行链路重新收敛为干净核心。

## 当前备份

在开始重构前，已备份当前探索相关目标到：

```text
D:\project\test_project\.codex\backups\site-exploration-clean-refactor-20260624-174625
```

备份内容包括：

- `apps/backend/app/services/exploration/`
- `apps/backend/app/agents/site_exploration/`
- `apps/backend/runners/playwright/browser-session.mjs`
- `apps/backend/runners/playwright/selector-generator.mjs`
- `apps/backend/runners/playwright/selector-validator.mjs`
- 相关 Node runner 测试
- 相关 backend 探索集成测试
- 当前 `git status` 快照
- 关键引用关系检索结果

该备份只作为本地回退参照，不参与运行时逻辑，不替代 git 历史。

## 目标

- 将探索执行链收敛为单一主循环：`observe -> decide -> policy -> act -> record`。
- 保留现有任务生命周期、SSE 事件、v2 artifact 和探索详情页消费契约。
- 删除或弱化旧 `Plan-and-Execute` 中需要模型猜页面元素的字段和流程。
- 让 Agent 只基于当前 `Observation` 中真实存在的 `element_id` 决策。
- 支持受控 `action_batch`，减少连续安全动作带来的额外模型调用。
- 用 `Recorder` 统一记录 observations、actions、findings、blockers、graph edges 和 replay operations。
- 修复 Node selector 验证链路中的 `placeholder` 缺口。
- 新增 replay service，支持成功 operation 的零 LLM 复用执行。
- 保持迁移过程可测试、可回退；外部入口兼容，内部目录允许完整替换。

## 非目标

- 不重写整个站点探索产品流。
- 不删除 v2 artifact 的兼容能力，但允许把现有 `artifact_service.py` 重构迁移到 `artifacts/` 包。
- 不让模型生成 CSS、XPath 或 Playwright locator 代码。
- 不默认执行破坏性动作。
- 不把探索事实直接提升为正式需求或测试用例。
- 不一次性迁移历史探索 run。
- 不把浏览器执行迁到 LangChain tool 内。

## 核心原则

```text
Agent 负责决策，不负责生成页面事实。
BrowserSession 负责观察和执行，不解释业务目标。
Policy 负责风险边界，不混在 Agent prompt 里兜底。
Recorder 是探索事实的唯一写入入口。
ArtifactService 是 v2 artifact 兼容适配层。
Replay 只执行已验证 locator 和已保存 operation，不调用 LLM。
```

每一个可改变页面状态的动作前必须有当前页面观察证据。

禁止链路：

```text
LLM plan -> guessed selector -> direct click
```

目标链路：

```text
Playwright observe -> LLM choose element_id -> policy check -> Playwright act -> Recorder write fact
```

## 目标架构

```text
exploration.service / site_orchestrator
  -> run_unified_exploration_sync(...)      保持现有外部入口兼容
  -> ExplorationEngine
      -> browser.session.PlaywrightBrowserSession
          -> observe 当前页面事实
      -> ExplorationDecisionService
          -> LangChain Agent 决策下一步
      -> ExplorationPolicy
          -> 校验风险和范围
      -> ExplorationRecorder
          -> 记录观察、决策、动作、结果
      -> artifacts.writer ArtifactWriter
```

### 模块职责

#### `site_exploration Agent`

探索 Agent 是决策层，负责在每一轮观察后决定下一步做什么。

Agent 不直接执行浏览器动作，但必须输出可执行的结构化决策：

- 当前页面是否值得记录。
- 是否点击、填写、按键、返回、关闭弹窗、等待或导航。
- 是否将多个安全动作合并为 `action_batch`。
- 当前动作的意图和风险等级。
- 是否跳过、阻塞或结束探索。

Agent 输入来自 `ExplorationEngine` 构造的受控上下文：

- 探索目标。
- 当前 `Observation`。
- 当前页面元素列表。
- 历史摘要。
- 剩余预算。
- 禁止路径和风险规则摘要。

Agent 输出 `ExplorationDecision`。Engine 只消费结构化决策，不解析自由文本来执行动作。

Agent 不是页面事实来源。页面事实只能来自 Playwright observe。

Agent 不是浏览器执行器。浏览器执行只能通过 `browser.session.PlaywrightBrowserSession`。

#### `ExplorationEngine`

主循环引擎，只负责执行流程：

- 启动和关闭 `browser.session.PlaywrightBrowserSession`
- 导航起始 URL
- 调用 `observe`
- 构造 Agent 决策上下文
- 调用 `ExplorationDecisionService`
- 调用 `ExplorationPolicy`
- 执行动作或批量动作
- 调用 `ExplorationRecorder`
- 控制预算、完成、阻塞、取消和异常

`Engine` 不直接拼 v2 YAML，不直接组织前端展示结构。

#### `ExplorationDecisionService`

Agent 决策服务，只负责：

- 加载 `site_exploration` skill prompt
- 构造模型输入
- 返回结构化 `ExplorationDecision`

它不持有浏览器 session，不执行动作，不写 artifact。

#### `ExplorationPolicy`

策略检查模块，只负责：

- 禁止路径检查
- action 风险检查
- batch 动作约束
- destructive 动作阻断
- guarded 动作的单步限制
- URL scope 检查

风险判断不能只依赖模型自报，应结合 action 类型、目标元素文本、URL、forbidden patterns 和运行模式。

#### `ExplorationRecorder`

统一记录器，只负责：

- 保存观察记录
- 保存动作和动作结果
- 保存发现
- 保存阻塞
- 构建 graph nodes 和 graph edges
- 从成功动作序列沉淀 replay operation 草稿
- 调用 artifact adapter 输出 v2 artifact
- 发布可选的生命周期事件载荷

`Recorder` 是事实写入入口，避免 orchestrator、executor、artifact service 多处拼结构。

#### `browser.session.PlaywrightBrowserSession`

作为 Python 到 Node runner 的长生命周期协议层，承接现有 `browser_session.py` 能力。

保留现有能力：

- `start`
- `observe`
- `click(element_id)`
- `fill(element_id, value)`
- `navigate(url)`
- `go_back`
- `close_modal`
- `wait`
- `close_run_session`

新增能力：

- `get_state_signature()`
- `validate_locator(locator)`
- `click_locator(locator)`
- `fill_locator(locator, value)`
- `press_key(key)`

探索阶段优先用 `element_id`，replay 阶段才使用 `locator`。

#### `artifacts.writer`

作为 v2 artifact 兼容适配层，承接现有 `artifact_service.py` 写入、读取和报告生成能力。

职责调整为：

- 接收 `Recorder` 的标准事实包
- 写出当前前端和报告消费所需的 v2 artifact
- 读取历史 artifact
- 生成报告

它不再负责从执行过程的散乱字段里推断事实。

#### `replay.service.ReplayService`

零 LLM 复用执行器：

- 加载 `operations.yaml`
- 根据 operation name 查找可执行流程
- 替换运行时参数
- 每步执行前验证 locator
- 执行 `navigate/click/fill/press/wait`
- 校验 expected result
- 更新 success count 和 last validated

Replay 不调用 Agent，不读取页面自然语言目标。

## 目标目录结构

本次按目标目录完整重构，旧目录只作为迁移来源和临时兼容 facade。

```text
apps/backend/
├── app/
│   ├── agents/
│   │   └── site_exploration/
│   │       ├── __init__.py
│   │       ├── agent.py
│   │       ├── schemas.py
│   │       ├── service.py
│   │       ├── middleware.py
│   │       └── skills/
│   │           └── site-exploration/
│   │               ├── SKILL.md
│   │               └── references/
│   │                   ├── locator-best-practices.md
│   │                   └── risk-levels.md
│   └── services/
│       └── exploration/
│           ├── __init__.py
│           ├── engine.py
│           ├── models.py
│           ├── policy.py
│           ├── recorder.py
│           ├── browser/
│           │   ├── __init__.py
│           │   ├── session.py
│           │   └── locator.py
│           ├── replay/
│           │   ├── __init__.py
│           │   ├── service.py
│           │   └── validator.py
│           └── artifacts/
│               ├── __init__.py
│               ├── writer.py
│               └── schemas.py
└── runners/
    └── playwright/
        ├── browser-session.mjs
        ├── selector-generator.mjs
        └── selector-validator.mjs
```

说明：

- `apps/backend/app/agents/site_exploration/execution_decision/` 的能力迁移到扁平化 `agent.py`、`schemas.py`、`service.py`。
- `apps/backend/app/agents/site_exploration/middleware.py` 复用需求分析模块的 Skill Middleware 模式。
- `apps/backend/app/services/exploration/browser_session.py` 的能力迁移到 `browser/session.py`。
- `apps/backend/app/services/exploration/artifact_service.py` 的能力迁移到 `artifacts/writer.py` 和 `artifacts/schemas.py`。
- `replay/validator.py` 负责 Python 侧 replay locator 校验编排，实际 locator 验证仍调用 Node runner。
- `unified_orchestrator.py`、`plan_and_execute/`、旧 `execution_decision/` 在迁移完成后删除；迁移期间只允许作为兼容 facade，不再新增业务逻辑。

## 新旧模块映射

| 旧模块 | 新模块 | 处理方式 |
| --- | --- | --- |
| `agents/site_exploration/execution_decision/agent.py` | `agents/site_exploration/agent.py` | 迁移并改为 Skill Middleware |
| `agents/site_exploration/execution_decision/schemas.py` | `agents/site_exploration/schemas.py` | 合并旧 schema，新增 `actions` batch |
| `agents/site_exploration/execution_decision/service.py` | `agents/site_exploration/service.py` | 保留模型选择，输出 `structured_response` |
| `services/exploration/unified_orchestrator.py` | `services/exploration/engine.py` | 主循环迁移，旧文件临时 facade |
| `services/exploration/browser_session.py` | `services/exploration/browser/session.py` | 移动协议层，保留取消会话能力 |
| `services/exploration/action_risk.py` | `services/exploration/policy.py` | 合并风险和禁止路径检查 |
| `services/exploration/artifact_service.py` | `services/exploration/artifacts/writer.py` | 迁移 v2 写入、读取、报告能力 |
| `services/exploration/plan_and_execute/*` | 删除 | Engine 稳定后删除 |
| `runners/playwright/selector-validator.mjs` | 原路径 | 修复 `placeholder` |

## 核心数据模型

### `ExplorationTask`

```python
class ExplorationTask(BaseModel):
    id: str
    title: str = ""
    goal: str
    start_url: str
    scope: Literal["single_site", "cross_site"] = "single_site"
    forbidden_patterns: list[str] = Field(default_factory=list)
    max_pages: int = 50
    max_actions: int = 1000
    max_agent_turns: int = 200
    timeout_minutes: int = 120
    mode: Literal["explore", "replay"] = "explore"
```

### `Locator`

```python
class Locator(BaseModel):
    kind: Literal["role", "label", "placeholder", "text", "testid", "css"]
    role: str = ""
    name: str = ""
    label: str = ""
    placeholder: str = ""
    text: str = ""
    testid: str = ""
    selector: str = ""
    verification: dict = Field(default_factory=dict)
```

`Locator` 不存静态 Playwright `code`。需要执行时由 Node runner 按 descriptor 动态生成 locator。

### `PageElement`

```python
class PageElement(BaseModel):
    id: str
    type: str = ""
    text: str = ""
    role: str = ""
    name: str = ""
    disabled: bool = False
    visible: bool = True
    locators: list[Locator] = Field(default_factory=list)
```

### `Observation`

```python
class Observation(BaseModel):
    page_id: str
    url: str
    title: str = ""
    state_signature: str
    elements: list[PageElement] = Field(default_factory=list)
    timestamp: str
```

### `BrowserAction`

```python
class ActionTarget(BaseModel):
    element_id: str = ""
    locator: Locator | None = None


class BrowserAction(BaseModel):
    type: Literal[
        "navigate",
        "click",
        "fill",
        "press",
        "go_back",
        "close_modal",
        "wait",
        "record",
    ]
    target: ActionTarget | None = None
    value: str = ""
    url: str = ""
    key: str = ""
    intent: str = ""
    risk: Literal["safe", "guarded", "destructive"] = "safe"
```

探索阶段 `target.element_id` 必须来自当前 observation。Replay 阶段才允许使用 `target.locator`。

### `ExplorationDecision`

```python
class ExplorationDecision(BaseModel):
    decision_type: Literal[
        "act",
        "action_batch",
        "record",
        "skip",
        "finish",
        "block",
    ]
    actions: list[BrowserAction] = Field(default_factory=list)
    reasoning: str = Field(min_length=1)
    findings: list[str] = Field(default_factory=list)
```

兼容期可以保留旧 `action: AgenticAction | None` 字段，但新执行链只消费 `actions`。

## Agent 决策规则

Agent 只能看到：

- 当前 task goal
- 当前 URL、title、state signature
- 当前 observation 的元素摘要
- 历史摘要
- 剩余预算
- forbidden patterns 摘要

Agent 不能看到：

- 账号密码
- storage state
- cookie
- 未暴露给 observation 的 DOM 细节
- 可以诱导它猜测的历史 locator code

Agent 输出限制：

- click/fill 只能引用当前 observation 中存在的 `element_id`
- 不允许生成 CSS/XPath
- 不允许生成 Playwright code
- 不允许构造未知 URL，除非 action 类型是从当前页面链接触发或 start_url 范围内的明确相对路径
- 写动作必须标记 `guarded` 或 `destructive`
- 无法确认安全性时返回 `skip` 或 `block`

## 批量动作规则

`action_batch` 只用于减少模型调用，不用于绕过安全检查。

允许批量的动作：

- `fill`
- `press`
- 安全 `click`
- `wait`

限制：

- 默认最多 5 步
- 所有动作必须是 `safe`
- 任何一步 URL 变化后停止剩余动作
- 任何一步 state signature 变化后停止剩余动作
- 出现新 dialog 后停止剩余动作
- 任一步失败后停止剩余动作
- `guarded` 和 `destructive` 不允许进入 batch

典型可批量场景：

- 搜索框填值 + Enter
- 多字段筛选表单填值
- 非提交型筛选条件设置

不允许批量场景：

- 保存
- 删除
- 发布
- 清空
- 批量修改
- 需要确认弹窗的动作

## Artifact 设计

继续保留 v2 artifact：

```text
run.yaml
summary.yaml
graph.yaml
blockers.yaml
pages/*.yaml
checks/goal-validation.yaml
reports/exploration-report.md
logs/run.log
```

新增：

```text
operations.yaml
```

### `graph.yaml`

`graph.yaml` 继续表达页面和状态关系。

新增 edge 记录来源：

- click 后 URL 变化
- click 后 title 变化
- click 后 state signature 变化
- go_back 后 URL 变化
- navigate 成功

edge 示例：

```yaml
edges:
  - id: edge-001
    source: page-001
    target: page-002
    action: click
    intent: 进入用户详情
    locator:
      kind: role
      role: link
      name: 查看详情
    result_status: passed
    url_changed: true
    state_changed: true
```

### `operations.yaml`

`operations.yaml` 记录可复用操作模板，和 `graph.yaml` 平级。

```yaml
artifact_schema_version: 2
operations:
  - id: op-001
    name: search_user
    description: 在用户列表按关键字搜索用户
    entry_url: /users
    params:
      - name: keyword
        type: string
        required: true
    sequence:
      - step: 1
        action: fill
        locator:
          kind: placeholder
          placeholder: 搜索用户
        value: "{{keyword}}"
      - step: 2
        action: press
        key: Enter
        expected_result:
          state_changed: true
    recorded_at: "2026-06-24T00:00:00+08:00"
    success_count: 1
    last_validated: "2026-06-24T00:00:00+08:00"
```

operation 初期只从成功且非破坏性动作序列生成，不从失败动作和 destructive 动作生成。

## Replay 设计

Replay 执行顺序：

```text
load operations.yaml
  -> find operation
  -> navigate entry_url
  -> for each step:
      -> replace params
      -> validate locator
      -> execute action
      -> verify expected result
  -> return result
```

Locator 验证结果：

- `valid`
- `not_found`
- `not_unique`
- `not_visible`
- `unsupported_kind`

Replay 失败时不调用 LLM 自动修复，只返回明确失败步骤和原因。

## Node Runner 改造

### `selector-validator.mjs`

补齐：

- `placeholder` -> `page.getByPlaceholder(...)`
- `css` 同时兼容 `selector` 和旧 `css`
- `testid` 同时兼容 `testid`、`testId`、`test_id`

### `browser-session.mjs`

新增协议命令：

- `get_state_signature`
- `validate_locator`
- `click_locator`
- `fill_locator`
- `press_key`

现有 `click(element_id)`、`fill(element_id)` 保持不变。

动作结果需要返回：

- `status`
- `used_locator`
- `before_url`
- `after_url`
- `url_changed`
- `state_signature_changed`
- `new_dialog_detected`
- `attempts`
- `error_type`
- `error_summary`

## 重构实施策略

### Phase 0：建立目标目录骨架和兼容入口

目标：

- 创建 `agents/site_exploration/agent.py`、`schemas.py`、`service.py`、`middleware.py`。
- 创建 `services/exploration/browser/`、`replay/`、`artifacts/` 子包。
- 保留现有外部入口函数名和 API 调用链。
- 让旧 `unified_orchestrator.py` 临时转调新 `engine.py` 或明确标记 deprecated。

验收：

- `test_ai_agents_architecture.py` 更新为检查新的扁平 Agent 结构。
- 原探索启动入口 import 不报错。

### Phase 1：修补定位器内核并抽出 browser 层

目标：

- 修复 `placeholder` validator 缺口。
- 统一 Python `Locator` descriptor。
- 确保 Node runner 可以验证 descriptor，而不是依赖静态 code。
- 将 `services/exploration/browser_session.py` 迁移到 `services/exploration/browser/session.py`。
- 新增 `services/exploration/browser/locator.py`，负责 Python 侧 locator descriptor 规范化。

验收：

- `selector-validator.test.mjs` 覆盖 `placeholder`。
- 现有 `browser-session.test.mjs` 继续通过。
- backend 中引用 `PlaywrightBrowserSession` 的位置改为新路径。

### Phase 2：引入干净 models、policy、recorder

目标：

- 新增 `models.py`
- 新增 `policy.py`
- 新增 `recorder.py`
- 不替换运行链路，只用单元测试验证模型和记录逻辑。

验收：

- `Recorder` 能从 action result 生成 graph edge。
- `Policy` 能阻断 forbidden path 和 destructive batch。

### Phase 3：重构 Agent 层为 Skill Middleware

目标：

- 将旧 `execution_decision` 能力迁移到 `agents/site_exploration/agent.py`、`schemas.py`、`service.py`。
- 新增 `middleware.py`，对齐 `requirement_analysis` 的 Skill Middleware 模式。
- 新增 `skills/site-exploration/SKILL.md` 和 references。
- 将现有 `AgenticDecisionOutput` 演进为 `ExplorationDecision`，支持 `actions`。
- 更新 Agent prompt，要求优先返回 1 到 5 步安全 batch。

验收：

- `service.py` 从 LangChain result 读取 `structured_response`。
- 新测试覆盖 `action_batch`。
- Agent schema 测试证明 click/fill 使用 `element_id`，不要求 locator code。

### Phase 4：Engine 接管主循环

目标：

- 新增 `engine.py`。
- `run_unified_exploration_sync` 保持外部函数名不变，内部走新 Engine。
- `UnifiedExplorationOrchestrator` 变成兼容 facade，不再承载新业务逻辑。

验收：

- 现有探索入口测试不需要改 API。
- 新 Engine 能用 fake session + fake decision service 完成 `observe -> act -> record`。

### Phase 5：重构 artifacts 包和 operations

目标：

- 将 `artifact_service.py` 能力迁移到 `artifacts/writer.py` 和 `artifacts/schemas.py`。
- `Recorder.finalize()` 输出 artifacts writer 所需的标准事实包。
- 新增 `operations.yaml` 写入。
- `graph.yaml` 有真实 edges。

验收：

- `test_exploration_artifact_v2.py` 继续通过。
- 新测试断言成功动作会生成 graph edge。
- 新测试断言安全动作序列可沉淀 operation。

### Phase 6：重构 replay 包

目标：

- 新增 `replay/service.py`。
- 新增 `replay/validator.py`。
- 支持零 LLM 执行已保存 operation。
- 每步执行前验证 locator。

验收：

- Fake session 下成功执行 operation。
- locator not found 时返回明确失败步骤。
- replay 不调用 Agent service。

### Phase 7：删除旧冗余

完成前置阶段后再删除：

- 旧 `PlanExecutor._find_element()` 自然语言匹配路径
- 非 navigate 场景的 `target_selector`
- `execution_strategy=direct/agentic` 分叉
- 已无引用的 `plan_and_execute` 代码
- 旧 `execution_decision/` 包
- 旧 `browser_session.py` facade
- 旧 `artifact_service.py` facade
- 旧 `unified_orchestrator.py` facade
- 根目录实验脚本中确认无引用的探索 demo 文件

删除前必须 `rg` 搜引用，并保留测试覆盖。

## 测试策略

Backend 单元测试：

- `test_exploration_models.py`
- `test_exploration_policy.py`
- `test_exploration_recorder.py`
- `test_exploration_engine.py`
- `test_exploration_replay.py`

Node 测试：

- `selector-validator.test.mjs`
- `browser-session.test.mjs`

集成测试：

- 现有 `test_site_exploration_agent_integration.py`
- 现有 `test_exploration_artifact_v2.py`
- 现有 `test_exploration_service_artifact_v2.py`

关键断言：

- Agent 不能执行 observation 之外的 element id。
- destructive action 被 policy 阻断。
- action batch 遇到状态变化会停止。
- `placeholder` locator 可验证。
- graph edge 来自动作结果，不是报告阶段猜测。
- replay 执行不触发 Agent。
- v2 artifact 读取和报告生成兼容。

## 验证命令

Backend：

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests\test_site_exploration_agent_integration.py tests\test_exploration_artifact_v2.py tests\test_exploration_service_artifact_v2.py -q
```

Node：

```powershell
cd apps/backend/runners/playwright
node --test selector-validator.test.mjs browser-session.test.mjs
```

全量探索相关回归：

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests\test_site_exploration_agent_integration.py tests\test_exploration_artifact_v2.py tests\test_exploration_service_artifact_v2.py tests\test_exploration_run_restart.py -q
```

## 回退策略

- 本地备份目录保留当前探索相关源码快照。
- 每个 Phase 单独提交，禁止一次性大改。
- `run_unified_exploration_sync` 外部入口保持不变，方便在兼容期从新 Engine 回退到旧 orchestrator。
- `artifacts/writer.py` 必须兼容 v2 artifact，避免前端详情页被迫同步大改。
- `plan_and_execute`、旧 `execution_decision`、旧 `browser_session.py`、旧 `artifact_service.py` 只在新目录测试稳定后删除。

## 成功标准

- 新探索主循环可以通过 fake browser 和 fake decision service 单测验证。
- Agent 决策 schema 比旧 `ExplorationStep` 更小，且不要求模型猜 selector。
- 连续安全动作可以通过 `action_batch` 降低模型调用次数。
- 成功动作能生成 `graph.yaml` edge。
- 成功安全动作序列能生成 `operations.yaml`。
- Replay 能在 0 LLM 调用下执行 operation。
- 现有 v2 artifact 详情页和报告读取不破。
- 旧补丁式字段逐步减少，而不是迁移到新文件继续累积。
