# 站点探索 Agentic Playwright 循环改造 Spec

## 背景

当前站点探索已经具备：

- `exploration_runs` 任务生命周期。
- LangChain `site_exploration_agent`。
- TypeScript + Playwright runner：`apps/backend/runners/playwright/site-explorer.mjs`。
- v2 探索产物：`run.yaml`、`summary.yaml`、`graph.yaml`、`blockers.yaml`、`pages/*.yaml`、`checks/goal-validation.yaml`、`reports/exploration-report.md`、`logs/run.log`。
- SSE 实时事件流和探索详情页展示。
- 登录态复用、手动登录和验证码策略设计。

但当前执行模型仍然是：

```text
LangChain 生成运行合同
  -> Playwright runner 按固定规则访问页面、采集元素、尝试安全点击
  -> 生成一次性探索产物
```

这会导致以下问题：

- LangChain 只做启动前规划，不参与页面观察后的下一步决策。
- Playwright runner 更像规则型爬虫，不具备“看页面 -> 判断下一步 -> 执行动作 -> 再观察”的循环。
- SPA 页面中大量按钮路由、弹窗、菜单和分页不一定能被固定规则覆盖。
- “工作台模块的全部内容”等自然语言目标无法自动拆解为可执行探索计划。
- 增删改查动作缺少显式授权、测试数据和回滚策略，当前只能默认跳过高风险动作。

本 spec 定义新一代 **Agentic Exploration Loop**：由 LangChain/Agent 基于真实页面观察逐步决策，由 Playwright 执行动作并返回新观察，最终生成可审计探索事实。

## 目标

- 将站点探索从一次性规则 runner 升级为 Agent 驱动的浏览器探索循环。
- Agent 每一步只能基于 Playwright 返回的真实观察结果做决策。
- Playwright 提供结构化工具层：观察、点击、填写、选择、回退、关闭弹窗、记录状态等。
- 每个动作都必须记录：观察、决策理由、风险等级、执行结果、产物引用。
- 支持 SPA 按钮路由、弹窗、菜单、tab、筛选、搜索、分页和详情页探索。
- 支持只读探索模式下的低风险交互。
- 支持受控 CRUD 探索模式，但必须依赖测试环境、测试数据规则和授权配置。
- 继续产出 v2 兼容事实源，并扩展 agent 决策链和动作轨迹。
- 继续复用现有任务生命周期、SSE、operation logs、artifact persistence 和探索详情页。

## 非目标

- 不默认在生产环境执行创建、保存、发布、删除、批量操作等写动作。
- 不让模型凭经验猜页面、接口、按钮、表单字段或 locator。
- 不把账号密码、cookie、storage state、验证码明文暴露给 Agent。
- 不在本次直接生成正式自动化测试代码。
- 不替代现有需求分析、知识库生成、测试用例生成模块。
- 不要求一次实现完整自主 CRUD 回滚框架；CRUD 可作为第二阶段能力。
- 不引入前端伪进度或伪页面事实。

## 核心原则

```text
Agent 负责决策，不负责伪造事实。
Playwright 负责观察和执行，不负责解释业务目标。
Orchestrator 负责任务生命周期、权限、预算、停止、产物和审计。
Artifact 是权威事实源，实时事件只是增量展示。
生产环境默认只读，写动作必须显式授权。
```

每一步必须满足：

```text
observe -> decide -> risk_check -> act -> observe -> record
```

不得出现：

```text
decide -> act
```

即任何动作前必须有当前页面观察证据。

## 总体架构

### 当前架构

```text
exploration_service.start
  -> site_orchestrator.run_exploration
  -> LangChain site_exploration_agent 生成 runner contract
  -> node site-explorer.mjs 一次性执行
  -> artifact_service.write_exploration_artifacts
```

### 目标架构

```text
exploration_service.start
  -> site_orchestrator.run_exploration
  -> AgenticExplorationOrchestrator
      -> start PlaywrightBrowserSession
      -> LangChain Agent loop
          -> observe_page()
          -> decide next action
          -> execute_browser_action()
          -> observe_page()
          -> record_step()
      -> write artifacts
      -> finish / blocked / cancelled
```

组件边界：

```text
Python Orchestrator
  - 任务生命周期
  - 权限与环境策略
  - Agent 调用
  - tool 调度
  - 预算和停止
  - 产物写入
  - SSE 事件发布

LangChain Agent
  - 根据观察选择下一步
  - 判断页面状态和覆盖缺口
  - 解释为什么执行或跳过动作
  - 产出结构化决策

Playwright Browser Session
  - 浏览器会话
  - 页面观察
  - 真实点击/填写/选择/回退
  - selector 校验
  - 截图和 snapshot
```

## 目录结构

新增：

```text
apps/backend/app/agents/site_exploration/
  agentic_agent.py
  agentic_service.py
  agentic_schemas.py
  agentic_tools.py
  prompts.py

apps/backend/app/services/exploration/
  agentic_orchestrator.py
  browser_session.py
  action_policy.py

apps/backend/runners/playwright/
  browser-session.mjs
  browser-session-protocol.mjs
  browser-observer.mjs
  browser-actions.mjs
```

保留：

```text
apps/backend/runners/playwright/site-explorer.mjs
```

第一阶段不删除旧 runner。探索任务增加执行模式：

```text
execution_mode:
- rule_runner      旧模式，默认兼容
- agentic_loop     新 Agentic 模式
```

## Agent 循环

### 单步流程

```text
1. Playwright observe_page 返回当前页面事实。
2. Agent 根据目标、范围、历史动作、风险策略和观察结果做出下一步决策。
3. Orchestrator 执行风险校验和预算校验。
4. Playwright 执行动作。
5. Playwright 再次 observe_page。
6. Orchestrator 写入 step、edge、state、log 和 SSE 事件。
7. Agent 继续下一步，直到完成、阻塞、取消或预算耗尽。
```

### 循环停止条件

任一条件满足即停止：

- Agent 返回 `finish`。
- 用户请求停止，run 状态为 `stopping`。
- 达到 `max_pages`。
- 达到 `max_actions`。
- 达到 `timeout_minutes`。
- 连续失败次数超过阈值。
- 同一页面/状态重复动作超过阈值。
- 目标范围内没有可执行低风险动作。
- 登录、验证码、权限或数据依赖阻塞。

### 预算建议

```text
max_pages: 默认 50
max_actions: 默认 1000
max_agent_turns: 默认 200
max_repeated_failures: 默认 5
max_same_state_revisits: 默认 3
timeout_minutes: 默认 120
```

`max_agent_turns` 是 Agent 决策轮数，不等同于浏览器动作数。`observe` 可计入 turn，但不计入写动作。

## Agent 输入

Agent 每轮只允许看到受控上下文：

```json
{
  "run": {
    "title": "工作台探索",
    "goal": "工作台模块全部内容",
    "scope": "工作台模块",
    "forbidden_paths": "除了工作台之外的模块",
    "execution_mode": "agentic_loop"
  },
  "policy": {
    "environment_type": "prod",
    "interaction_mode": "readonly",
    "allowed_action_risks": ["safe"],
    "forbidden_action_patterns": ["删除", "发布", "保存"]
  },
  "budget": {
    "remaining_turns": 120,
    "remaining_actions": 800
  },
  "history_summary": "已覆盖工作台入口页、分析入口，使用入口待探索。",
  "current_observation": {
    "url": "...",
    "title": "...",
    "state_id": "page-001:default",
    "elements": []
  }
}
```

Agent 不允许看到：

- 密码。
- cookie。
- storage state。
- 验证码识别结果。
- 完整 HTML。
- 未脱敏网络请求体。
- 后端内部文件绝对路径。

## Agent 输出

Agent 每轮必须输出结构化决策：

```json
{
  "decision_type": "act",
  "action": {
    "type": "click",
    "target_element_id": "button-use-001"
  },
  "reason": "该按钮是工作台卡片的低风险入口，预计进入使用页面或打开使用弹窗。",
  "expected_result": "进入智能体使用页面或出现使用配置弹窗。",
  "risk": {
    "level": "safe",
    "reason": "按钮名称为使用，不属于创建、保存、删除或发布。"
  },
  "coverage_intent": {
    "module": "工作台",
    "page_or_state": "智能体使用入口",
    "goal_fragment": "覆盖工作台卡片主要操作"
  }
}
```

允许的 `decision_type`：

```text
act       执行动作
record    仅记录当前页面事实
back      回退到上一状态或上一页面
skip      跳过当前动作并说明原因
finish    完成探索
block     阻塞，需要人工处理
```

允许的 `action.type`：

```text
navigate
click
fill
select_option
press
close_modal
go_back
wait
record_state
```

## Playwright 工具协议

### start_session

输入：

```json
{
  "start_url": "https://example.test/workspace",
  "browser_channel": "chrome",
  "storage_state_path": "internal",
  "viewport": {"width": 1440, "height": 1000}
}
```

输出：

```json
{
  "session_id": "browser-session-1",
  "status": "started",
  "url": "https://example.test/workspace"
}
```

### observe_page

输出必须足够 Agent 决策，但不能过大。

```json
{
  "url": "https://example.test/workspace",
  "normalized_url": "https://example.test/workspace",
  "title": "工作台",
  "state_signature": "hash",
  "page_text_summary": "工作台，2 个智能体卡片，筛选栏和搜索框。",
  "elements": [
    {
      "id": "button-use-001",
      "role": "button",
      "name": "使用",
      "text": "使用",
      "action_type": "click",
      "enabled": true,
      "visible": true,
      "risk_hint": "safe",
      "primary_selector": {
        "kind": "role",
        "code": "page.getByRole('button', { name: '使用' })",
        "verification": {
          "checked": true,
          "unique": true,
          "visible": true,
          "match_count": 1
        }
      }
    }
  ],
  "forms": [],
  "dialogs": [],
  "tables": [],
  "links": [],
  "breadcrumbs": [],
  "evidence": {
    "screenshot_path": "screens/page-001.png",
    "snapshot_path": "snapshots/page-001.json"
  }
}
```

### click_element

输入：

```json
{
  "element_id": "button-use-001",
  "selector": {
    "kind": "role",
    "code": "page.getByRole('button', { name: '使用' })"
  }
}
```

输出：

```json
{
  "status": "passed",
  "before_url": "...",
  "after_url": "...",
  "url_changed": true,
  "title_changed": false,
  "new_dialog_detected": false,
  "state_signature_changed": true,
  "error": ""
}
```

### fill_field

只读模式下允许用于搜索、筛选、查询输入。写模式下字段填写必须遵守测试数据策略。

输入：

```json
{
  "element_id": "textbox-search-001",
  "value": "AI_TEST_probe",
  "intent": "search"
}
```

输出：

```json
{
  "status": "passed",
  "value_applied": true,
  "result_count_changed": true
}
```

### finish_session

结束时必须关闭浏览器并释放会话。

## 行为风险策略

### 风险等级

```text
safe
  查看、详情、展开、关闭、切换 tab、搜索、筛选、分页、排序、更多菜单、回退

guarded
  新建、编辑、上传、导入、保存草稿、提交查询条件、复制、导出、批量选择

destructive
  删除、发布、提交审批、支付、发送消息、修改权限、禁用账号、批量删除、覆盖导入
```

### 模式

```text
interaction_mode:
- readonly
- safe_write
- full_crud
```

`readonly`：

- 只允许 `safe` 动作。
- 搜索/筛选可填写临时值，但不得提交写操作。
- 发现 guarded/destructive 动作时记录为跳过，不执行。

`safe_write`：

- 允许部分 guarded 动作。
- 必须使用测试数据前缀。
- 保存、提交前需要策略允许。
- destructive 仍禁止。

`full_crud`：

- 仅测试环境允许。
- 允许 create/update/delete 完整闭环。
- 必须配置测试数据前缀和清理策略。
- destructive 动作默认仍需人工确认，除非 `allow_destructive_without_confirmation=true` 且环境类型为 `test`。

### 环境约束

```text
environment_type:
- prod
- staging
- test
```

规则：

```text
prod:
  interaction_mode 强制 readonly

staging:
  可 readonly 或 safe_write
  destructive 需要人工确认

test:
  可 readonly / safe_write / full_crud
```

## CRUD 探索策略

CRUD 不是默认探索能力，必须显式开启。

### 配置字段

```text
crud_enabled: boolean
interaction_mode: readonly | safe_write | full_crud
test_data_prefix: string
cleanup_enabled: boolean
cleanup_strategy: none | delete_created | restore_snapshot
require_confirmation_for_destructive: boolean
allowed_write_modules: list[string]
forbidden_write_actions: list[string]
```

### 测试数据规则

所有写入数据必须带前缀：

```text
AI_TEST_{run_id}_{short_random}
```

示例：

```text
AI_TEST_explore123_textin_001
```

Agent 不允许自由生成真实业务名称。Playwright tool 层或 Orchestrator 负责生成测试数据值。

### 清理规则

如果 `cleanup_enabled=true`：

```text
run 结束前
  -> 查找本次 run 创建的数据
  -> 尝试删除或恢复
  -> 记录 cleanup_result
```

清理失败时 run 不应伪装 completed，必须标记 `partial` 或 `blocked`，并在 `blockers.yaml` 中写明残留数据。

## Agent Prompt 约束

核心 prompt 必须包含：

```text
你是站点探索执行智能体。
你只能基于 observe_page 返回的页面事实行动。
每次只能选择一个动作。
你不能猜测页面不存在的按钮、字段、接口或 URL。
你不能生成或修改 locator。
你必须解释选择该动作的原因和预期结果。
你必须遵守 interaction_mode 和 environment_type。
生产环境禁止执行写入或破坏性动作。
遇到登录、验证码、权限不足、危险动作或数据依赖时，记录 blocker。
如果多个低风险动作可选，优先覆盖：导航入口、详情、tab、筛选、搜索、分页、更多菜单。
```

## 产物扩展

保留 v2 schema，新增可选字段，不破坏现有读取逻辑。

### pages/*.yaml 新增

```yaml
agent_decisions:
  - id: decision-001
    turn: 1
    observation_ref: observation-001
    decision_type: act
    action_type: click
    target_element_id: button-use-001
    reason: 覆盖工作台卡片使用入口。
    expected_result: 进入使用页或打开使用弹窗。
    risk:
      level: safe
      reason: 使用按钮为只读入口。
    result_ref: action-001

actions:
  - id: action-001
    type: click
    element_id: button-use-001
    before_url: ...
    after_url: ...
    status: passed
    state_signature_changed: true
```

### graph.yaml 扩展

```yaml
edges:
  - id: edge-001
    source: page-001:default
    target: page-002:default
    type: agent_action
    action: click
    decision_id: decision-001
    result:
      status: passed
      url_changed: true
```

### blockers.yaml 扩展

```yaml
blockers:
  - id: blocker-001
    type: guarded_action_skipped
    page_ref: page-001
    action: 创建智能体
    reason: 生产环境只读模式禁止执行创建动作。
    suggested_action: 在测试环境开启 safe_write 或 full_crud 后重新探索。
    decision_id: decision-008
```

### logs/run.log

每行 JSON：

```json
{"event":"observe","turn":1,"url":"...","state_signature":"..."}
{"event":"agent_decision","turn":1,"decision_type":"act","action":"click","target":"button-use-001","risk":"safe"}
{"event":"action_result","turn":1,"status":"passed","before_url":"...","after_url":"..."}
```

## 数据库影响

第一阶段可不新增表，复用 `exploration_runs` 和现有产物路径。

建议新增字段或复用 JSON 扩展：

```text
exploration_runs.execution_mode TEXT DEFAULT 'rule_runner'
exploration_runs.interaction_mode TEXT DEFAULT 'readonly'
exploration_runs.environment_type TEXT DEFAULT 'prod'
exploration_runs.agent_turn_count INTEGER DEFAULT 0
exploration_runs.action_count INTEGER DEFAULT 0
```

如果不改表，第一阶段可把模式写入 `run.yaml`，但前端列表和任务中心无法直接筛选执行模式。

## API 影响

### 创建/编辑探索任务

新增字段：

```ts
{
  execution_mode?: "rule_runner" | "agentic_loop";
  interaction_mode?: "readonly" | "safe_write" | "full_crud";
  environment_type?: "prod" | "staging" | "test";
  crud_enabled?: boolean;
  test_data_prefix?: string;
  cleanup_enabled?: boolean;
  require_confirmation_for_destructive?: boolean;
}
```

后端校验：

```text
environment_type=prod:
  interaction_mode 必须归一为 readonly
  crud_enabled 必须 false

interaction_mode=full_crud:
  environment_type 必须 test
  test_data_prefix 必填
```

### 探索详情

详情接口可返回：

```ts
{
  execution_mode: string;
  interaction_mode: string;
  agent_turn_count: number;
  decisions: AgentDecisionSummary[];
}
```

## SSE 事件扩展

新增事件：

```text
agent_observed
agent_decision
action_started
action_completed
action_skipped
policy_blocked
cleanup_started
cleanup_completed
```

事件示例：

```json
{
  "type": "agent_decision",
  "run_id": "explore-123",
  "payload": {
    "turn": 4,
    "decision_type": "act",
    "action_type": "click",
    "target_element_name": "使用",
    "reason": "覆盖工作台卡片使用入口。",
    "risk_level": "safe"
  }
}
```

前端展示：

- AgentPlan 主树继续展示模块和页面。
- 页面详情中展示决策链。
- 高风险跳过动作展示为“策略跳过”，不能显示为系统失败。

## 实施阶段

### 阶段 1：只读 Agentic Loop

范围：

- 新增 `agentic_loop` execution mode。
- Playwright session 支持 `observe_page`、`click_element`、`fill_field`、`go_back`、`close_modal`。
- Agent 只允许 `safe` 动作。
- 覆盖详情、tab、更多菜单、搜索、筛选、分页、按钮路由。
- 产出 `agent_decisions` 和 action log。

验收重点：

- 工作台不再只停留入口页。
- 能探索“分析 / 使用 / 对话历史 / 更多”等低风险入口。
- 能记录为什么点击、点击后发生了什么。
- 遇到创建、删除、保存、发布时记录策略跳过。

### 阶段 2：Safe Write

范围：

- 测试或 staging 环境允许有限写动作。
- 支持测试数据生成。
- 支持新建弹窗打开、表单填写、取消或保存草稿。
- 写动作必须记录创建的数据标识。

验收重点：

- 不污染生产数据。
- 所有写入数据带 `AI_TEST_` 前缀。
- 报告能说明写动作是否真正提交。

### 阶段 3：Full CRUD

范围：

- 仅测试环境。
- 支持创建、查询、编辑、删除闭环。
- 支持清理策略。
- 支持 destructive 动作人工确认或强授权。

验收重点：

- 创建的数据可被查询到。
- 编辑后能验证变更。
- 删除后能验证不存在。
- 清理失败有 blocker。

## 测试计划

### 后端单元测试

- `action_policy`：
  - prod 强制 readonly。
  - destructive 在 readonly 下被拒绝。
  - full_crud 仅 test 环境允许。
- `agentic_orchestrator`：
  - observe -> decision -> action -> observe 顺序正确。
  - 停止状态能中断循环。
  - 预算耗尽能 partial 结束。
  - policy_blocked 能写入 blocker。
- `artifact_service`：
  - 能读取包含 `agent_decisions` 的 v2 扩展产物。

### Runner 测试

- `browser-session.mjs`：
  - observe 能返回稳定 element id。
  - click 后能检测 URL/state 变化。
  - fill 搜索框后能记录结果变化。
  - 弹窗打开和关闭可观测。

### 集成测试

使用本地测试页面：

```text
/workspace
  - 搜索框
  - 筛选下拉
  - 卡片：分析 / 使用 / 对话历史 / 更多
  - 创建按钮

/workspace/use
/workspace/analysis
```

断言：

- agentic_loop 至少覆盖 3 个页面或状态。
- 创建按钮被跳过，原因是 readonly policy。
- graph 包含 agent_action edge。
- run.log 包含 observe、agent_decision、action_result。

## 验收标准

- 新建探索任务可选择 `Agentic Loop` 模式。
- 只读模式下，Agent 能基于页面观察连续决策，不依赖固定爬虫规则。
- 工作台探索能进入多个低风险页面或状态，而不是只采集入口页。
- 每个执行动作都有前置观察、决策理由、风险等级和执行结果。
- 高风险动作不会在生产环境执行，并写入明确 blocker 或 skipped action。
- v2 探索详情页能展示扩展产物，不影响旧产物读取。
- SSE 能实时显示 Agent 决策和动作结果。
- 用户停止任务后，浏览器会话被关闭，产物保留到停止前状态。
- 后端测试、runner 测试和本地集成探索测试通过。

## 迁移策略

- 默认仍使用 `rule_runner`，避免影响现有用户。
- 新模式先作为可选实验能力。
- 旧产物不迁移。
- 新产物保持 v2 schema，并通过可选字段扩展。
- 当 agentic_loop 在工作台、资源库、发布管理等核心模块稳定后，再考虑设为默认。

## 风险与对策

| 风险 | 对策 |
| --- | --- |
| Agent 循环成本高 | 限制 turn、压缩观察、保留 history summary |
| Agent 重复点击同一状态 | state_signature + repeated action guard |
| 误执行写动作 | action_policy 服务端强校验，生产强制 readonly |
| 页面元素过多 | observe 返回元素上限和优先级排序 |
| selector 不稳定 | 继续使用 selector-validator 校验唯一性和可见性 |
| 登录态过期 | 写 login_required blocker，不让 Agent 接触凭据 |
| 清理测试数据失败 | cleanup blocker + partial 状态 |

