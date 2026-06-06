# 站点探索 LangChain 智能体与 Playwright Runner 产物改造 Spec

## 背景

当前站点探索已经能创建任务、调用 `apps/backend/runners/playwright/site-explorer.mjs` 执行真实浏览器探索，并落盘 YAML 产物包。现有产物包括 `run.yaml`、`summary.yaml`、`graph.yaml`、`blockers.yaml`、`pages/*.yaml`、`checks/goal-validation.yaml`、`documents/exploration-v1.md` 和 `logs/run.log`。

这套产物已经比早期截图/HTML 快照更接近事实源，但仍存在边界不清：

- `pages/*.yaml` 只有 `locator_hint`，没有主定位、备用定位和唯一性验证结果。
- 点击后出现的弹窗、下拉、菜单、tab 内容等页面内状态没有结构化为 `states`。
- Playwright runner 已经负责真实浏览器探索，但 Python 编排层仍承担较多探索语义整理，智能体边界不够清楚。

本次改造目标是把站点探索拆成两个稳定边界：

- **LangChain 站点探索智能体**：负责任务理解、探索策略、产物归档、报告生成、阻塞归因和下游可用性判断。
- **TypeScript + Playwright Runner**：负责所有真实浏览器动作、页面状态采集、selector 生成与验证，不臆造页面事实。

## 目标

- 使用 LangChain 构建 `site_exploration_agent`，作为站点探索的唯一业务智能体。
- 探索执行继续使用 TypeScript + Playwright，浏览器动作不迁到 Python agent 内。
- 将 `pages/*.yaml` 升级为页面事实、页面内状态、元素、主备 selector、selector 唯一性验证的核心产物。
- 将弹窗、下拉、菜单、日期面板、tab 切换等记录为页面内 `states`，不拆成独立页面。
- 保留 `graph.yaml` 表达页面之间和重要状态之间的流转关系。
- 保留 `summary.yaml` 作为探索概览摘要产物，供详情页和概览页快速读取。
- 保留 `blockers.yaml` 作为机器可读阻塞事实产物，探索报告负责汇总展示阻塞影响和建议。
- 生成面向人的探索报告 `reports/exploration-report.md`，报告从结构化事实源派生。
- 为后续测试用例生成和 UI 自动化生成提供稳定输入。

## 非目标

- 不在本次实现正式测试用例生成。
- 不在本次实现正式 Playwright 测试代码生成。
- 不引入 DeepAgents。
- 不把浏览器操作迁移到 LangChain tool 的 Python 侧模拟。
- 不让模型根据经验猜测页面、按钮、接口或 locator。
- 不将探索结果直接提升为正式业务需求。
- 不做旧探索 run 的迁移。
- 不兼容旧探索产物格式；旧 run 只提示“历史产物格式不支持新版详情，请重新探索”。

## 目标目录结构

```text
apps/backend/app/agents/site_exploration/
  __init__.py
  agent.py
  service.py
  schemas.py
  tools.py
  prompts.py

apps/backend/runners/playwright/
  site-explorer.mjs
  selector-generator.mjs
  selector-validator.mjs
  artifact-schema.mjs

apps/backend/data/projects/{project_id}/exploration/{run_id}/
  run.yaml
  summary.yaml
  graph.yaml
  blockers.yaml
  pages/
    page-001.yaml
    page-002.yaml
  checks/
    goal-validation.yaml
  reports/
    exploration-report.md
  logs/
    run.log
```

`summary.yaml` 保留为探索概览摘要产物，面向前端详情页、概览页和列表快速展示。它不替代 `pages/*.yaml`、`graph.yaml`、`checks/*.yaml` 的明细事实。

`blockers.yaml` 保留为机器可读阻塞事实产物。探索报告应汇总 `blockers.yaml` 中的阻塞、影响范围和建议动作，但报告不是阻塞事实的唯一存储位置。

## 组件职责

### LangChain 智能体

路径：

```text
apps/backend/app/agents/site_exploration/
```

职责：

- 读取探索任务、项目环境、探索目标、范围、禁止路径和执行边界。
- 根据任务目标生成 runner 输入合同。
- 调用 Playwright runner tool。
- 校验 runner 返回的结构化产物是否完整。
- 调用报告生成 tool，生成 `reports/exploration-report.md`。
- 根据 runner 返回的阻塞、未验证项和目标验证结果决定最终状态：`completed`、`partial`、`waiting_human`、`blocked`、`failed`。
- 把关键摘要回写数据库，用于列表、详情和任务状态展示。

不负责：

- 不直接操作浏览器。
- 不生成未经 Playwright 观察的页面事实。
- 不手写 CSS/XPath 作为首选 locator。
- 不修改页面 YAML 中的已验证 selector 结果。

### TypeScript + Playwright Runner

路径：

```text
apps/backend/runners/playwright/
```

职责：

- 访问页面。
- 采集 accessibility snapshot。
- 补充必要 DOM 属性：`data-testid`、`id`、`name`、`placeholder`、`aria-label`、`label`、`href`、`type`、可见性、启用状态。
- 识别可操作元素。
- 生成每个元素最多两个 locator：`primary_selector` 和 `fallback_selector`。
- 调用独立 selector 校验步骤，对每个候选 selector 逐个验证唯一性和可见性。
- 点击按钮、链接、tab、菜单、下拉等安全动作，并采集点击后的页面内状态。
- 记录弹窗、下拉、菜单、datepicker、tab 内容等 `states`。
- 生成 `pages/*.yaml`、`summary.yaml`、`graph.yaml`、`blockers.yaml`、`checks/goal-validation.yaml` 和 `logs/run.log` 的原始结构化结果。

不负责：

- 不解释业务规则。
- 不生成正式测试用例。
- 不把阻塞写成人类报告结论。
- 不做跨模块知识库总结。

## 页面产物结构

每个页面一个 YAML 文件。页面内默认态、弹窗、下拉、菜单、tab 内容都作为 `states`。

```yaml
page:
  id: page-001
  title: 用户列表
  url: https://example.test/users
  normalized_url: https://example.test/users
  module: 用户管理
  page_type: list
  status: explored

states:
  - id: default
    type: page
    title: 用户列表
    root_selector:
      kind: role
      code: page.getByRole('main')
      verified_unique: true
      verified_visible: true
    elements:
      - id: create_user_button
        name: 新建用户
        role: button
        action: click
        primary_selector:
          kind: role
          code: page.getByRole('button', { name: '新建用户' })
          verified_unique: true
          verified_visible: true
        fallback_selector:
          kind: testid
          code: page.getByTestId('create-user')
          verified_unique: true
          verified_visible: true

  - id: create_user_dialog
    type: dialog
    parent_state: default
    trigger:
      element_id: create_user_button
      action: click
    root_selector:
      kind: role
      code: page.getByRole('dialog', { name: '新建用户' })
      verified_unique: true
      verified_visible: true
    elements:
      - id: username_input
        name: 用户名
        role: textbox
        action: fill
        primary_selector:
          kind: label
          code: page.getByLabel('用户名')
          verified_unique: true
          verified_visible: true
        fallback_selector:
          kind: role
          code: page.getByRole('textbox', { name: '用户名' })
          verified_unique: true
          verified_visible: true

quality:
  needs_confirmation: false
  blockers:
    - id: blocker-001
      state_id: create_user_dialog
      element_id: role_select
      type: unsupported_interaction
      reason: 下拉选项需要登录后权限数据，当前环境未返回选项。
      suggested_action: 使用具备角色数据的测试账号重新探索。
```

## Selector 生成规则

每个可操作元素最多生成两个 selector。

优先级：

```text
1. getByRole(role, { name })
2. getByLabel(label)
3. getByTestId(testId)
4. getByText(text)
5. locator(css)
6. XPath 不生成，除非人工明确允许
```

生成规则：

- `primary_selector` 必须来自可恢复的语义定位，优先 `role`、`label`、`testid`。
- `fallback_selector` 从剩余候选中选择一个优先级最高的候选。
- selector 生成阶段只负责产出候选，不负责判定最终是否可用。
- `ref` 只允许保存在 raw snapshot 或运行日志中，不进入正式 selector manifest。

## Selector 校验规则

selector 校验是独立步骤，由 `selector-validator.mjs` 或 runner 中等价的独立函数完成。

每个候选 selector 必须验证：
  - `count === 1`
  - `visible === true`
- 校验结果写入 `verification`。
- 未通过唯一性或可见性校验的 selector 可以保留为候选证据，但不能标记为可直接生成自动化代码。

示例：

```yaml
primary_selector:
  kind: role
  code: page.getByRole('button', { name: '保存' })
  verification:
    checked: true
    unique: true
    visible: true
    match_count: 1
fallback_selector:
  kind: testid
  code: page.getByTestId('save-button')
  verification:
    checked: true
    unique: true
    visible: true
    match_count: 1
```

示例：

```yaml
primary_selector:
  kind: role
  code: page.getByRole('button', { name: '保存' })
  verified_unique: true
  verified_visible: true
fallback_selector:
  kind: testid
  code: page.getByTestId('save-button')
  verified_unique: true
  verified_visible: true
```

## graph.yaml 结构

`graph.yaml` 记录页面之间和关键状态之间的流转。

```yaml
nodes:
  - id: page-001
    title: 用户列表
    url: /users
    type: page
    page_type: list
  - id: page-001:create_user_dialog
    title: 新建用户弹窗
    type: state
    state_type: dialog
    page_id: page-001

edges:
  - id: edge-001
    from: page-001
    to: page-001:create_user_dialog
    type: open_modal
    trigger:
      page_id: page-001
      state_id: default
      element_id: create_user_button
    result:
      opened_state: create_user_dialog
      url_changed: false
      verified: true
```

页面内状态是否写入 `graph.yaml` 的原则：

- 会影响测试步骤生成的状态，写入 graph。
- 纯展示 hover、临时 tooltip、无测试价值的视觉状态，不写入 graph，只可作为 page state 细节记录。

## checks 结构

目标验证单独保留在 `checks/goal-validation.yaml`。

```yaml
goal: 每篇文章内容的超链接和按钮不能跳转到登录页面
status: partial
summary: 链接全部通过，按钮存在未验证项。
stats:
  link_checked_count: 101
  link_failed_count: 0
  button_checked_count: 0
  button_unverified_count: 50
items:
  - page_id: page-001
    state_id: default
    element_id: article_link
    element_type: link
    action: href_check
    before_url: /document/manual/87
    after_url: /document/manual/82
    result: passed
    reason: 链接目标未命中登录页特征。
  - page_id: page-001
    state_id: default
    element_id: unnamed_button_001
    element_type: button
    action: click
    result: unverified
    reason: 按钮缺少可访问名称，无法生成稳定唯一 selector。
```

## 探索报告

报告路径：

```text
reports/exploration-report.md
```

报告是人可读结论，不是事实源。报告必须从 `pages/*.yaml`、`graph.yaml`、`checks/*.yaml` 和数据库 run 快照派生。

报告内容包括：

- 探索任务和环境摘要。
- 探索目标完成情况。
- 页面和模块覆盖情况。
- 关键页面事实。
- 页面关系和关键路径。
- 阻塞项、未验证项和影响范围。
- locator 稳定性风险。
- 后续建议。

阻塞项在报告中展示，但阻塞事实来自页面、edge 或 check item。

## 数据库边界

数据库继续负责：

- 任务列表查询。
- 状态流转。
- 项目、环境、运行参数。
- 页面数、动作数、阻塞数、目标验证状态等摘要索引。
- 前端详情初始快照。

数据库不负责：

- 保存完整页面状态树。
- 保存完整 selector manifest。
- 保存完整目标验证明细。
- 替代 `pages/*.yaml` 和 `graph.yaml` 作为事实源。

## run.yaml 边界

`run.yaml` 可以保留，但只作为本次产物包的运行快照。

规则：

- 创建、编辑、启动任务以数据库为准。
- 探索启动时从数据库复制一份运行合同到 `run.yaml`。
- `run.yaml` 不反向更新数据库。
- 下游脱库消费产物包时，可以用 `run.yaml` 理解上下文。

## 运行流程

1. 用户创建探索任务。
2. 后端数据库保存 run、环境、目标、范围和限制。
3. 启动探索时，探索 service 调用 LangChain `site_exploration_agent`。
4. Agent 读取 run 上下文，生成 runner input。
5. Agent 调用 Playwright runner tool。
6. TS runner 执行真实探索，生成页面状态、selector、graph、checks 和 log。
7. Agent 校验产物完整性。
8. Agent 生成探索报告。
9. Service 回写数据库摘要和状态。
10. 前端详情读取数据库摘要和产物文件展示。

## LangChain Tool 设计

### run_playwright_explorer

输入：

```python
class PlaywrightExplorerInput(BaseModel):
    run_id: str
    site_url: str
    artifact_root: str
    goal: str
    include_paths: list[str]
    exclude_paths: list[str]
    max_pages: int
    max_actions: int
    timeout_minutes: int
```

输出：

```python
class PlaywrightExplorerOutput(BaseModel):
    status: Literal["completed", "partial", "waiting_human", "blocked", "failed"]
    page_files: list[str]
    graph_path: str
    check_paths: list[str]
    log_path: str
    summary: str
    stats: dict
    blockers: list[dict]
```

### generate_exploration_report

输入：

```python
class ExplorationReportInput(BaseModel):
    artifact_root: str
    run_context: dict
```

输出：

```python
class ExplorationReportOutput(BaseModel):
    report_path: str
    summary: str
    status_recommendation: str
```

## 前端展示影响

探索详情继续保留四个 tab：

```text
探索计划
探索概览
探索日志
探索报告
```

调整点：

- 探索计划读数据库 run 字段。
- 探索概览读数据库摘要和必要的 page/graph 索引。
- 探索日志读 `logs/run.log`。
- 探索报告读 `reports/exploration-report.md`。
- 不直接展示 `summary.yaml`。
- 页面详情后续可新增“页面事实”入口，读取 `pages/*.yaml`。

## 验收标准

- 新探索 run 生成：
  - `run.yaml`
  - `graph.yaml`
  - `pages/*.yaml`
  - `checks/goal-validation.yaml`
  - `reports/exploration-report.md`
  - `logs/run.log`
- 新探索 run 继续生成 `summary.yaml` 作为概览摘要产物。
- 新探索 run 继续生成 `blockers.yaml` 作为机器可读阻塞事实产物。
- 每个页面 YAML 至少包含 `page` 和 `states`。
- 每个可操作元素最多包含一个 `primary_selector` 和一个 `fallback_selector`。
- `primary_selector` 和 `fallback_selector` 必须包含独立 selector 校验步骤写入的唯一性和可见性验证结果。
- 点击后出现的弹窗、下拉、菜单和 tab 内容必须作为 `states` 记录。
- `graph.yaml` 能表达页面跳转和关键状态流转。
- 探索报告能汇总阻塞项和未验证项。
- 若按钮缺少可访问名称，产物必须标记为 `unverified` 或 `needs_confirmation`，不能生成伪稳定 selector。
- 后端测试覆盖 agent service、runner 输出契约、artifact schema 和报告生成。

## 测试策略

### 后端 Python

- Agent service 单元测试：
  - 能从 run 构造 runner input。
  - 能处理 runner `completed`、`partial`、`waiting_human`、`blocked`。
  - 能写入报告路径和数据库摘要。
- Artifact 读取测试：
  - 能读取新 `pages/*.yaml` state 结构。
  - 能从 `checks/goal-validation.yaml` 汇总目标验证状态。
  - 能读取 `summary.yaml` 的概览摘要。
  - 能读取 `blockers.yaml` 的阻塞事实。

### TS Runner

- selector 生成测试：
  - role/name 唯一时生成 primary。
  - label 唯一时生成 primary 或 fallback。
  - test id 唯一时生成候选。
  - 多个同名按钮时不生成假唯一 selector。
- state 捕获测试：
  - 点击新建按钮后记录 dialog state。
  - 点击 select 后记录 dropdown state 和 option。
  - tab 切换后记录 tab state。
- graph 测试：
  - 页面跳转生成 navigation edge。
  - 弹窗打开生成 open_modal edge。
  - 安全跳过生成 blocker/check item，而不是伪造成功。

### 前端

- 探索详情页不依赖 `summary.yaml`。
- 探索详情页可以读取 `summary.yaml` 作为概览摘要，但不能用它替代页面明细事实。
- 探索报告 tab 能展示 `reports/exploration-report.md`。
- 探索概览仍能展示模块进度、页面数、阻塞摘要和目标验证状态。

## 迁移策略

- 老 run 不做批量迁移。
- 前端详情不兼容旧产物结构。
- 后端报告接口不 fallback 到旧 `documents/exploration-v1.md`。
- 新 run 使用 `artifact_schema_version: 2`。
- 前端详情只支持 `artifact_schema_version: 2`。
- 如果 run 缺少 `artifact_schema_version: 2` 或缺少新版必需产物，详情页展示历史格式提示，并引导重新探索。
- 后端报告接口只读取新路径 `reports/exploration-report.md`；缺失时返回明确错误或空报告状态，不读取旧报告路径。

## 风险与约束

- 一些站点可访问性语义差，`getByRole` 质量会受限；这种情况必须标记为未验证，而不是自动降级成 XPath。
- 下拉、日期面板、虚拟列表等组件可能需要专门适配，但仍应统一进入 `states` 模型。
- 测试账号权限不足时，探索结果可能大量 `waiting_human` 或 `partial`，报告必须清楚说明影响范围。
- LangChain agent 只做编排和归纳，不应成为隐藏浏览器执行器。

## 推荐实施顺序

1. 定义 artifact schema v2 和测试样例。
2. 改造 TS runner，先完成 selector 主备候选生成。
3. 增加独立 selector 校验步骤，写入唯一性和可见性验证结果。
4. 增加页面 state 捕获：dialog、dropdown、menu、tab。
5. 调整 artifact service，写入 v2 目录结构。
6. 新增 LangChain `site_exploration_agent` 和 tool 封装。
7. 调整 orchestration service 调用 agent。
8. 调整报告生成到 `reports/exploration-report.md`。
9. 调整前端详情只读取新版产物；旧产物展示重新探索提示。
10. 补充后端、runner、前端验证。
