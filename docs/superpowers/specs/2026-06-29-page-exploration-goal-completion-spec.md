# 页面探索目标完成与人类可读产物 Spec

## 背景

当前页面探索运行路径会通过 DeepAgents/LangGraph 让 Agent 连续思考、执行工具、观察结果，再继续思考和执行。这个模式符合页面探索的自然过程，但如果停止条件只依赖框架默认递归限制，就会出现以下问题：

- LangGraph 默认 `recursion_limit=25` 只是框架保险丝，不代表页面探索目标完成。
- 页面探索常常需要多轮 `snapshot -> decide -> click/fill/navigate -> snapshot -> record`，25 个内部 graph step 很容易不够。
- 当前失败摘要只写入探索任务结果，没有持久化每轮 Agent 事件，事后无法还原到底执行了哪些工具调用。
- 当前页面产物偏机器消费，缺少给人看的页面说明文档，无法快速理解页面内容、功能、阻塞点和测试建议。

本规范目标是把页面探索从“Agent 自由跑到框架上限”改为“服务层托管探索循环，按业务目标完成度停止”。

## 目标

1. 支持两类探索模式：
   - 目标明确时，按页面/业务模板探索。
   - 目标不明确时，对当前页面做全功能盘点。
2. 停止规则以“目标是否完成”为核心，不以 LangGraph 25 次递归限制为业务完成标准。
3. 每个页面同时生成机器可读产物和人类可读产物。
4. 持久化探索事件，支持失败后复盘每轮思考、动作、工具结果和停止原因。
5. 服务层负责预算、去重、风险控制、目标完成判断；LLM 只负责单轮决策和内容归纳。
6. 保留“思考 -> 执行 -> 再思考 -> 再执行”的探索能力，但循环由确定性 orchestrator 控制。

## 非目标

- 不让 Agent 无限制自主探索整站。
- 不把 `recursion_limit` 调大作为唯一解决方案。
- 不要求每次探索都覆盖全站。
- 不执行危险操作，例如删除、支付、登出、重置、清空。
- 不为了完成目标强制绕过登录、验证码、权限控制。
- 不在本次设计中直接生成自动化测试代码。

## 总体架构

```text
Frontend
  -> 创建探索任务：目标、范围、禁止路径、预算
  -> 查看实时事件、页面产物、人类可读文档

ExplorationService
  -> 创建 run
  -> 启动 ExplorationOrchestrator
  -> 持久化状态、事件、产物、完成摘要

ExplorationOrchestrator
  -> GoalClassifier
  -> TemplateRegistry
  -> 循环：
      1. 获取当前页面状态和探索上下文
      2. 调用 DecisionAgent 生成下一步决策
      3. ActionExecutor 执行动作
      4. ArtifactWriter 写页面产物
      5. GoalCompletionEvaluator 判断是否完成
      6. EventStore 持久化每轮事件

Page Artifacts
  -> pages/{page_id}.yaml  机器可读
  -> pages/{page_id}.md    人类可读
```

## 核心组件

### ExplorationOrchestrator

职责：

- 托管探索主循环。
- 管理 `max_pages`、`max_actions`、单页最大动作数、连续失败次数、连续无新增信息次数。
- 维护 explored URLs、候选动作、页面队列、当前页面状态。
- 每轮只允许执行一个明确动作。
- 调用 `GoalCompletionEvaluator` 判断是否停止。
- 结束时写入 run summary 和停止原因。

Orchestrator 是业务循环的唯一控制者。Agent 不直接决定“继续无限探索”，只能返回结构化下一步建议。

### GoalClassifier

职责：

- 判断用户探索目标是否明确。
- 选择探索模式和模板。

目标明确示例：

- “探索登录页”
- “探索工作台的创建智能体流程”
- “探索某列表页筛选和详情入口”
- “探索新增表单”

目标不明确示例：

- “探索工作台”
- “看看这个页面有什么”
- “探索这个系统”
- scope 只有模块名，没有具体动作或页面类型

输出：

```json
{
  "mode": "template" | "page_inventory",
  "template_id": "login_page" | "list_page" | "form_page" | "detail_page" | "workspace_page" | null,
  "confidence": 0.0,
  "reason": ""
}
```

### TemplateRegistry

职责：

- 管理页面探索模板。
- 每个模板定义必采集内容、允许动作、禁止动作、完成条件、产物字段。

首批模板：

- `login_page`
- `list_page`
- `form_page`
- `detail_page`
- `workspace_page`
- `dialog_page`

模板结构：

```json
{
  "template_id": "login_page",
  "required_observations": [
    "username_field",
    "password_field",
    "login_button",
    "captcha_or_mfa",
    "agreement_checkbox",
    "error_feedback"
  ],
  "allowed_actions": ["snapshot", "safe_fill", "safe_click", "record"],
  "forbidden_actions": ["submit_payment", "delete", "logout"],
  "completion_rules": [
    "all_required_observations_recorded",
    "page_yaml_written",
    "page_markdown_written"
  ]
}
```

### DecisionAgent

职责：

- 根据当前页面快照、目标、模板、历史事件和预算，返回下一步结构化决策。
- 不直接执行工具。
- 不直接判断 run 最终完成，只能给出建议。

输出结构：

```json
{
  "thought_summary": "为什么下一步要这样做",
  "action": "snapshot" | "navigate" | "click" | "fill" | "record_page" | "finish_page" | "block",
  "target": {
    "url": "",
    "locator": "",
    "value": "",
    "description": ""
  },
  "expected_gain": "本动作预期补齐什么信息",
  "risk_level": "safe" | "caution" | "dangerous",
  "skip_reason": "",
  "completion_signal": {
    "page_goal_done": false,
    "run_goal_done": false,
    "reason": ""
  }
}
```

如果 `risk_level=dangerous`，Orchestrator 不执行动作，只记录跳过原因。

### ActionExecutor

职责：

- 执行浏览器动作和产物写入动作。
- 统一返回成功、失败、页面变化、新发现信息。
- 对 Playwright 工具失败做错误分类，例如 locator 不唯一、元素不存在、超时、导航失败。

ActionExecutor 不做目标判断，只负责可靠执行和返回事实。

### GoalCompletionEvaluator

职责：

- 根据目标、模板、当前页面事实、已写产物、事件历史和预算判断是否完成。
- 产生明确停止原因。

输出：

```json
{
  "done": true,
  "status": "completed" | "blocked" | "partial",
  "reason": "模板必采集项已完成，页面 YAML 和 Markdown 已生成。",
  "missing_items": [],
  "blockers": []
}
```

### ExplorationEventStore

职责：

- 持久化每轮探索事件，支持事后复盘。
- 记录 Agent 思考摘要、工具输入、工具输出、失败原因、页面 URL、动作编号、预算消耗。

建议路径：

```text
data/projects/{project_id}/page_exploration/runs/{run_id}/events.jsonl
```

事件格式：

```json
{
  "event_id": "evt-000001",
  "run_id": "exp_xxx",
  "page_id": "page-workspace",
  "iteration": 1,
  "type": "decision" | "action_started" | "action_completed" | "action_failed" | "artifact_written" | "completion_check",
  "payload": {},
  "occurred_at": "2026-06-29T00:00:00Z"
}
```

## 探索模式

### 模板探索模式

适用于目标明确的任务。

流程：

```text
1. GoalClassifier 选择模板
2. Orchestrator 初始化模板检查清单
3. 获取页面快照
4. DecisionAgent 逐项补齐模板必采集信息
5. ActionExecutor 执行安全动作
6. ArtifactWriter 更新 page.yaml 和 page.md
7. GoalCompletionEvaluator 判断模板完成
8. 完成后停止当前页面或进入下一个模板目标页面
```

示例：登录页模板完成条件：

- 账号输入框已识别。
- 密码输入框已识别。
- 登录按钮已识别。
- 验证码、多因子认证、协议勾选等阻塞项已识别或确认不存在。
- 登录错误反馈区域已记录，或说明未触发提交。
- 页面 YAML 已写入。
- 页面 Markdown 已写入。

### 页面全功能盘点模式

适用于目标不明确的任务。

范围默认是“当前页面”，不是无限全站。

必须输出：

- 页面用途。
- 页面主要区域。
- 页面可见内容。
- 页面功能入口。
- 表单、列表、筛选、弹窗、导航、卡片、按钮。
- 安全可探索动作。
- 跳过动作及原因。
- blocker。
- 后续测试建议。

完成条件：

- 当前页面主要区域已识别。
- 所有主要功能入口已分类。
- 可安全触发的轻量交互已探索或记录。
- 危险操作已跳过并记录。
- 页面 YAML 已写入。
- 页面 Markdown 已写入。
- 连续一轮没有新增页面事实时，可判定当前页面盘点完成。

## 产物设计

### 机器可读页面产物

路径：

```text
data/projects/{project_id}/page_exploration/pages/{page_id}.yaml
```

核心字段：

```yaml
page:
  id: page-workspace
  title: 工作台
  url: https://example.com/workspace
  normalized_path: /workspace
  page_type: workspace_page
  explored_at: 2026-06-29T00:00:00Z
  exploration_mode: page_inventory
  goal: 探索工作台
  completion:
    status: completed
    reason: 当前页面主要功能已完成盘点。
    missing_items: []
    blockers: []
  regions: []
  functions: []
  elements: []
  actions: []
  skipped_actions: []
  test_opportunities: []
```

### 人类可读页面产物

路径：

```text
data/projects/{project_id}/page_exploration/pages/{page_id}.md
```

模板：

```md
# 页面名称

## 页面用途

说明该页面面向用户解决什么问题。

## 页面内容

列出页面主要区域和可见信息。

## 页面功能

列出可执行功能、入口和交互方式。

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|

## 跳过和阻塞

列出危险操作、权限不足、登录、验证码、数据缺失等情况。

```

人类可读文档必须来源于已观察事实，不能凭空编业务能力。

## 停止规则

业务停止由 `GoalCompletionEvaluator` 决定，LangGraph `recursion_limit` 只作为技术保险丝。

### 明确目标停止规则

满足以下条件之一即可停止：

- 模板必采集项全部完成，且页面 YAML 和 Markdown 均已写入。
- 目标所需页面已完成，且没有待探索的安全候选动作。
- 遇到登录、验证码、权限或业务前置条件导致无法继续，已记录 blocker 和已完成部分。
- 目标路径超出 scope 或命中 forbidden_paths，已记录跳过原因。

### 不明确目标停止规则

满足以下条件之一即可停止当前页面：

- 当前页面主要区域、功能入口、关键元素、可测试点已完成盘点。
- 连续一轮没有发现新的页面事实或安全候选动作。
- 所有候选动作均为危险、重复、超范围或需要人工前置条件。
- 页面 YAML 和 Markdown 均已写入。

### 通用预算停止规则

以下规则优先级高于目标继续探索：

- `explored_pages >= max_pages`
- `action_count >= max_actions`
- 单页动作数达到 `max_actions_per_page`
- 连续工具失败达到阈值，例如 3 次
- 连续无新增信息达到阈值，例如 2 次
- 运行超时
- 用户主动停止

预算停止状态应区分：

- `completed`：目标完成。
- `partial`：达到预算但已有可用产物。
- `blocked`：登录、权限、验证码、系统错误等阻塞。

## LangGraph 递归限制策略

如果继续使用 DeepAgents/LangGraph，调用时应设置足够的技术保险丝，例如：

```python
config = {"recursion_limit": max(100, max_pages * 8)}
```

但该配置不得作为业务停止条件。业务停止必须由 Orchestrator 和 GoalCompletionEvaluator 控制。

当触发 `GRAPH_RECURSION_LIMIT` 时，系统应：

- 将 run 标记为 `partial` 或 `blocked`，取决于是否已有可用产物。
- 在 `events.jsonl` 中记录最后一次 decision/action。
- 在结果摘要中说明是技术保险丝触发，不等同于目标完成。
- 提示可查看事件日志定位循环原因。

## 数据流

```text
Create Run
  -> load environment entry URL
  -> classify goal
  -> initialize page queue
  -> loop iteration
      -> snapshot current page
      -> build context
      -> DecisionAgent returns one decision
      -> validate decision risk and scope
      -> execute action
      -> update page facts
      -> write artifacts when facts changed
      -> evaluate completion
      -> persist event
  -> finish run with status and summary
```

## 错误处理

### 工具失败

- locator 不唯一：要求 DecisionAgent 基于错误优化定位器。
- 元素不存在：刷新快照后重试一次。
- 导航失败：记录 blocker，回到上一个可用页面或停止当前分支。
- 超时：记录当前页面状态，计入连续失败。

### 危险动作

危险动作不执行，只记录：

- 动作名称。
- 元素描述。
- 跳过原因。
- 对测试建议的影响。

### 登录、验证码、权限

如果页面需要人工前置条件：

- 写入 blocker。
- 页面产物状态为 `blocked` 或 `partial`。
- 人类可读文档说明阻塞点。

## 前端展示

探索详情页应展示：

- run 状态和停止原因。
- 页面列表。
- 页面 YAML 产物入口。
- 页面 Markdown 文档入口。
- 事件时间线入口。
- blocker 和跳过动作。

如果探索因递归限制或预算停止，应展示“部分完成”而不是笼统失败，并提供已生成页面产物。

## 验收标准

1. 目标明确时，系统能选择模板并按模板完成条件停止。
2. 目标不明确时，系统能生成当前页面全功能盘点。
3. 每个完成或部分完成的页面都有 `.yaml` 和 `.md` 两类产物。
4. 探索停止原因可解释，不能只显示 `Recursion limit of 25`。
5. 失败后可以通过 `events.jsonl` 还原每轮决策和动作。
6. 危险操作不会被执行，并会进入跳过记录。
7. 达到预算时，已有产物仍可查看。
8. `recursion_limit` 只作为保险丝，目标完成判断由业务代码完成。

## 实施分阶段

### 阶段一：可观测性和止血

- 为 Agent stream event 增加 `events.jsonl` 落盘。
- 调整 LangGraph 调用配置，设置合理 `recursion_limit`。
- 失败摘要区分技术保险丝、业务阻塞、目标未完成。

### 阶段二：人类可读产物

- 增加 `HumanPageDocWriter`。
- 在页面产物写入时同步生成 `page_id.md`。
- 前端支持查看 Markdown 页面说明。

### 阶段三：目标完成判断

- 增加 `GoalClassifier`。
- 增加 `GoalCompletionEvaluator`。
- 明确 completed、partial、blocked 的状态转换。

### 阶段四：受控探索循环

- 将 DeepAgent 一口气自由运行改为 Orchestrator 托管循环。
- DecisionAgent 每轮只返回一个结构化动作。
- Orchestrator 负责执行、预算、去重、停止。

### 阶段五：模板体系

- 增加 TemplateRegistry。
- 首批支持登录页、列表页、表单页、详情页、工作台页、弹窗页。
- 为模板完成条件补充单元测试和集成测试。

