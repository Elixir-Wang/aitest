# 站点探索流程与结构化产物设计方案

## 背景

当前站点探索已经具备探索任务、项目环境、运行状态、探索详情页和基础产物目录，但探索过程仍偏向“运行一次并生成报告”。后续要支撑详细测试用例和 UI 自动化测试用例生成，探索结果必须从报告型产物升级为结构化证据包。

本方案把站点探索重新定义为：为每次探索生成可追溯、可复用、可审计的页面证据、页面关系图和运行日志。探索结果不直接成为正式需求或正式测试用例，而是作为知识库、测试用例生成和 UI 自动化生成的上游页面事实来源。

## 目标

- 固化一套清晰的探索执行流程。
- 每个页面生成一个 YAML 页面证据文件，包含页面档案和无障碍树。
- 使用 `graph.yaml` 的 `edges` 表达页面之间的跳转、提交、弹窗、数据依赖和状态变化。
- 使用 `run.yaml` 记录本次探索计划、范围和执行边界。
- 使用 `blockers.yaml` 记录无法探索、禁止点击、安全拦截和失败原因。
- 使用探索日志 tab 展示 `logs/run.log`，并能追溯到页面、动作、edge 和产物。
- 为后续详细测试用例和 UI 自动化测试用例生成提供稳定输入。

## 非目标

- 不在探索阶段生成正式测试用例。
- 不在探索阶段生成正式 UI 自动化代码。
- 不把观察到的页面现象直接提升为已确认业务规则。
- 不保存截图、HTML 快照或独立 locator 文件。
- 探索报告只作为可重建的人可读总结，不作为事实源。
- 第一版不做复杂可视化图谱编辑，只输出结构化 YAML 和基础页面展示。
- 不兼容旧探索产物结构，不迁移旧 run；重构后探索详情只支持新的 YAML 事实源结构。
- 不生成独立 `locators.yaml`；定位建议以内嵌 `locator_hint` 的方式保存在 `accessibility_tree` 节点、`actions` 候选动作和 `graph.yaml` edge 触发元素中。

## 核心原则

1. 探索产物以 YAML 页面事实为核心，而不是以 Markdown 报告为核心。
2. 每个页面至少有一个结构化页面文件，页面文件内必须包含无障碍树。
3. 页面之间的关系统一使用 `edges` 记录，不使用固定“子页面、子子页面”字段表达。
4. 页面结构和页面关系必须可追溯到 `logs/run.log` 中的运行记录。
5. 探索只能记录观察到的页面事实；业务含义、规则和优先级需要由需求文档、知识库或人工确认补足。
6. YAML 文件是探索结果的主事实源；数据库只保存运行状态、摘要、索引和产物路径，用于列表、概览和查询加速。
7. 第一版 `edges` 只写入 `graph.yaml`，不新增 `exploration_edges` 数据库表；如后续需要高频关系查询，再从 `graph.yaml` 派生数据库索引。
8. 无障碍树优先来自 accessibility snapshot；当页面组件语义不足时，可以用 DOM 信息补充 `locator_hint`、`enabled`、`visible`、`href`、`input_type` 等辅助字段，但不能用 DOM 覆盖掉 accessibility tree 的主结构。
9. 跨页面数据生产和消费关系统一使用 `data_dependency` edge 表达；它只记录探索观察到的引用关系，不直接推断正式业务规则。

## 产物目录

```text
apps/backend/data/projects/{project_id}/exploration/{run_id}/
  run.yaml
  summary.yaml
  graph.yaml
  blockers.yaml
  logs/run.log
  pages/
    page-001-user-list.yaml
    page-002-user-detail.yaml
    page-003-user-edit.yaml
```

第一版最小产物只要求 `run.yaml`、`summary.yaml`、`graph.yaml`、`blockers.yaml` 和 `pages/*.yaml`。`run.yaml`、`graph.yaml`、`blockers.yaml` 和 `pages/*.yaml` 是权威探索事实；`summary.yaml` 是从事实源派生的摘要，用于探索概览和模块进度展示。数据库中的页面、模块、阻塞和摘要数据均视为索引或派生展示数据。不保存截图、HTML 快照、trace 或 video。

## 探索流程

### 1. 读取探索计划

探索运行开始前读取本次任务的环境、范围、目标和执行边界。

输入来源包括：

- 所属项目
- 测试环境
- 站点地址
- 登录策略
- 探索范围
- 禁止路径
- 探索目标
- 模块清单，适用于全部探索或全站探索
- 页面上限
- 操作上限
- 超时时间

这些信息写入 `run.yaml`，作为本次探索的运行合同。

执行边界只按整个 run 设置全局限制，不做模块级覆盖。即使全站探索按模块推进，页面上限、操作上限和超时时间也共同消耗同一组全局 limits。

当探索范围为全部探索或全站探索时，模块清单来源优先级为：

1. 用户在探索计划中手工配置的模块清单。
2. 未配置时，由 Runner 从站点导航菜单识别模块。
3. 导航识别失败时，归入“未分组模块”，并在 `blockers.yaml` 或 `summary.yaml` 中记录提示。

### 2. 启动浏览器上下文

系统根据测试环境和登录策略初始化浏览器上下文。

- 复用登录态时加载已有 storage state。
- 手动登录时进入等待人工状态，并记录等待原因。
- 账号密码登录时读取测试环境中的账号配置，自动完成登录并保存本次浏览器上下文；如果遇到验证码、MFA、动态安全校验或登录表单无法识别，进入等待人工状态并写入 `blockers.yaml`。
- 无需登录时直接进入入口页面。
- 登录失败或超时写入 `blockers.yaml`。

### 3. 入口页面访问

系统访问站点地址或指定入口路径，采集第一个页面的页面档案和无障碍树，生成第一个页面 YAML，例如 `pages/page-001-home.yaml`。

如果入口页不可访问，任务进入失败或阻塞状态，并记录 blocker。

### 4. 页面节点采集

每访问一个新页面，系统生成一个页面节点。

页面节点必须记录：

- `page.id`
- `page.title`
- `page.url`
- `page.normalized_url`
- `page.module`
- `page.page_type`
- `page.depth`
- `page.status`
- `accessibility_tree`

`page.page_type` 必须保留，用于后续测试用例生成和页面分组。第一版建议值包括：`list`、`detail`、`form`、`dashboard`、`settings`、`content`、`unknown`。弹窗和页面内 tab 不作为独立页面，因此不作为 `page_type` 主值。

`accessibility_tree` 是该页面最重要的结构化产物，用于后续生成测试用例步骤、页面元素清单和 Playwright locator 提示。

### 5. 可操作元素识别

系统基于无障碍树识别可操作元素。

第一版重点识别：

- button
- link
- textbox
- combobox
- checkbox
- radio
- tab
- menuitem
- dialog
- table

每个可操作元素应尽量记录 `role`、`name`、`locator_hint`、`enabled` 和 `visible`。

`locator_hint` 是基于 `role`、`name` 等信息生成的 Playwright 定位建议，用于后续 UI 自动化生成。`locator_hint` 可以直接内嵌在页面 YAML 中，第一版不单独生成 `locators.yaml`。

### 6. 安全动作执行

系统按探索计划中的禁止路径、禁止动作和执行边界执行点击、切换、填写、提交等动作。系统不内置固定业务动作黑名单，避免把不同项目的业务语义写死；只有明确命中本次探索配置的禁止路径或禁止动作时才拦截。

被跳过的动作写入探索日志和 `blockers.yaml`，类型为 `safety_blocked` 或 `skipped`。

### 7. 页面关系记录

每个动作执行后，系统判断结果：

- 是否 URL 变化
- 是否页面标题变化
- 是否无障碍树发生显著变化
- 是否打开弹窗
- 是否提交表单
- 是否返回上一页面
- 是否产生错误提示
- 是否触发列表刷新或筛选变化

只要动作产生可记录结果，就在 `graph.yaml` 写入一条 `edge`。

外链只记录不访问。发现外链时写入 `graph.yaml` 的 `external_link` 或 `skipped` edge，记录来源页面、触发元素、目标 URL 和跳过原因，但 Runner 不打开外链，也不继续探索外部站点。

### 8. 页面去重和归一化

系统通过 `normalized_url`、页面标题、无障碍树结构和页面类型判断页面是否已存在。

示例：

- `/users/123` 和 `/users/456` 归一化为 `/users/:id`
- 不同分页不一定是新页面，可记录为 `pagination` edge
- 同页筛选变化记录为 `filter` edge
- 弹窗不生成独立页面节点，作为当前页面的页面内状态记录；打开弹窗的动作记录为 `open_modal` edge，关闭弹窗的动作记录为 `close_modal` edge。
- 页面内 tab 切换不生成独立页面节点，作为当前页面的页面内状态记录；切换动作记录为 `tab_switch` edge。

### 9. 阻塞和失败记录

无法继续探索时，系统写入 `blockers.yaml`。

阻塞类型包括：

- login_required
- permission_denied
- captcha_required
- route_forbidden
- safety_blocked
- action_failed
- page_timeout
- duplicate_loop
- unsupported_interaction

### 10. 生成探索日志

探索过程中的关键运行信息都追加到 `logs/run.log`。不新增独立 `events.jsonl`。

为了便于前端筛选和问题定位，`run.log` 的日志行可以采用稳定前缀或 JSON Lines 风格，但 `run.log` 仍是唯一日志产物。

## run.yaml 结构

```yaml
run:
  id: explore-001
  project: 示例项目
  environment: 测试环境
  site_url: https://example.com
  started_at: "2026-05-29T10:00:00+08:00"

scope:
  include:
    - /users
    - /roles
  exclude:
    - /logout
    - /delete

goal:
  text: 探索用户管理相关页面、字段、操作和页面关系

modules:
  source: manual
  items:
    - module_key: user-management
      module_name: 用户管理
      scope:
        include:
          - /users
          - /roles
        exclude:
          - /users/delete
      goal: 探索用户、角色相关页面、字段、操作和页面关系

limits:
  max_pages: 50
  max_actions: 1000
  timeout_minutes: 120
```

## 页面 YAML 结构

每个页面一个 YAML 文件，文件名使用稳定序号加页面 slug，例如 `page-001-user-list.yaml`。页面文件同时承担页面档案、无障碍树、可操作动作、页面关系和质量信息，不再拆分 `page.yaml` 与 `accessibility-tree.yaml`。

```yaml
page:
  id: page-001
  title: 用户列表
  url: /users
  normalized_url: /users
  module: 用户管理
  page_type: list
  depth: 0
  status: explored

accessibility_tree:
  - role: heading
    name: 用户列表
  - role: button
    name: 新建用户
    locator_hint: getByRole('button', { name: '新建用户' })
    enabled: true
    visible: true
  - role: table
    name: 用户列表
  - role: link
    name: 详情
    locator_hint: getByRole('link', { name: '详情' })
    enabled: true
    visible: true

actions:
  - id: action-001
    role: button
    name: 新建用户
    locator_hint: getByRole('button', { name: '新建用户' })
    action_type: click
    enabled: true
    visible: true

relations:
  incoming_edges: []
  outgoing_edges:
    - edge_id: edge-001
      type: navigation
      to_page_id: page-002

quality:
  confidence: observed
  needs_confirmation: false
  blockers: []
```

`quality.needs_confirmation` 必须保留，用于标记需要需求文档、知识库或人工确认的页面事实、数据依赖和状态变化。

## summary.yaml 结构

`summary.yaml` 是从 `pages/*.yaml`、`graph.yaml` 和 `blockers.yaml` 派生的概览摘要，不作为权威事实源。探索概览 tab 优先读取 `summary.yaml`，避免每次打开页面都扫描完整事实包。

```yaml
run_id: explore-001
status: completed
summary: 已探索用户管理范围内 5 个页面，记录 8 条页面关系。

modules:
  - module_key: user-management
    module_name: 用户管理
    status: completed
    page_progress: 5/5
    latest_page: 编辑用户
    blocker_summary: 无
    progress_percent: 100
```

## graph.yaml 结构

`graph.yaml` 使用 `nodes` 和 `edges` 记录页面关系。页面层级、路径、跳转、提交、弹窗和数据依赖都由 `edges` 表达。

```yaml
nodes:
  - id: page-001
    title: 用户列表
    url: /users
    type: list
    module: 用户管理

  - id: page-002
    title: 用户详情
    url: /users/:id
    type: detail
    module: 用户管理

  - id: page-003
    title: 编辑用户
    url: /users/:id/edit
    type: form
    module: 用户管理
```

```yaml
edges:
  - id: edge-001
    from: page-001
    to: page-002
    type: navigation
    action: 点击「详情」
    element:
      role: link
      name: 详情
      locator_hint: getByRole('link', { name: '详情' })
    result:
      url_changed: true
      opened_modal: false
      target_page_detected: true

  - id: edge-002
    from: page-002
    to: page-003
    type: navigation
    action: 点击「编辑」
    element:
      role: button
      name: 编辑
      locator_hint: getByRole('button', { name: '编辑' })
    result:
      url_changed: true
      opened_modal: false
      target_page_detected: true

  - id: edge-003
    from: page-003
    to: page-002
    type: submit_and_return
    action: 点击「保存」
    element:
      role: button
      name: 保存
      locator_hint: getByRole('button', { name: '保存' })
    result:
      url_changed: true
      returned_to: page-002
      state_changed: true
```

## Edge 类型

第一版支持以下 edge 类型：

| 类型 | 含义 |
| --- | --- |
| navigation | 点击后进入另一个页面 |
| open_modal | 点击后打开当前页面内弹窗 |
| close_modal | 关闭当前页面内弹窗 |
| submit | 表单提交后停留当前页 |
| submit_and_return | 表单提交后返回详情页或列表页 |
| tab_switch | 页面内 tab 切换 |
| filter | 筛选导致列表刷新 |
| pagination | 分页 |
| data_dependency | A 页面创建的数据被 B 页面引用 |
| external_link | 发现外链，只记录目标地址，不访问 |
| state_change | 状态变更，例如启用、禁用、审批 |
| safety_blocked | 动作被安全策略拦截 |
| skipped | 动作被跳过 |

## 数据依赖关系

跨页面数据关系也使用 edge 表达。例如 A 页面创建角色，B 页面新建用户时在角色下拉框引用该角色。

```yaml
edges:
  - id: edge-010
    from: page-role-create
    to: page-user-create
    type: data_dependency
    entity: 角色
    producer:
      page: page-role-create
      action: 创建角色
      field: 角色名称
    consumer:
      page: page-user-create
      element:
        role: combobox
        name: 角色
      usage: 新建用户时选择角色
    evidence:
      observed_value: 自动化测试角色-001
      confidence: observed
      needs_confirmation: true
```

## 路径表达

页面的“子页面、子子页面”关系不使用嵌套字段硬编码，而是通过 `edges` 生成路径。

```yaml
paths:
  - id: path-001
    name: 用户编辑路径
    steps:
      - page: page-001
      - edge: edge-001
      - page: page-002
      - edge: edge-002
      - page: page-003
```

该路径可直接作为测试用例生成输入：

```yaml
test_seed:
  title: 编辑用户信息
  path: path-001
  steps:
    - 进入用户列表页
    - 点击「详情」
    - 进入用户详情页
    - 点击「编辑」
    - 修改用户名称
    - 点击「保存」
    - 验证返回用户详情页
```

## blockers.yaml 结构

```yaml
blockers:
  - id: blocker-001
    type: safety_blocked
    page: page-001
    action: 点击「删除」
    reason: 命中本次探索计划配置的禁止动作，已跳过
    severity: warning
    suggested_action: 如需覆盖该动作，请调整本次探索计划的禁止动作配置后重新探索

  - id: blocker-002
    type: permission_denied
    page: page-004
    url: /admin/settings
    reason: 当前账号无权限访问系统设置
    severity: blocking
    suggested_action: 使用具备系统设置权限的测试账号重新探索
```

## 探索日志 Tab 设计

探索日志 tab 的定位是运行日志查看和证据索引，不是报告页。

它需要回答：

- 探索过程中发生了什么？
- 哪个页面、哪个动作导致了跳转？
- 哪一步失败、阻塞或被跳过？
- 某个页面 YAML 是在哪一步生成的？
- 某条 edge 来源于哪个动作？

### 日志筛选

日志 tab 顶部提供筛选：

- 事件类型：全部、页面、动作、产物、阻塞、错误、安全拦截
- 页面：全部或指定页面
- 级别：全部、信息、警告、错误
- 关键词：URL、按钮名、页面标题、错误信息

### 日志类型

```yaml
log_types:
  run_started: 探索开始
  login_started: 登录开始
  login_completed: 登录完成
  page_discovered: 发现页面
  page_visited: 访问页面
  accessibility_captured: 生成无障碍树
  action_detected: 发现可操作元素
  action_executed: 执行动作
  edge_created: 记录页面关系
  artifact_written: 写入产物
  blocked: 探索阻塞
  skipped: 跳过页面或动作
  safety_blocked: 安全策略拦截
  error: 错误
  run_completed: 探索完成
```

### 日志行展示

列表中每条日志展示摘要：

```text
时间 | 类型 | 页面 | 动作或结果 | 状态
```

示例：

```text
10:21:03  访问页面      用户列表          /users
10:21:05  生成产物      页面 YAML         pages/page-001-user-list.yaml
10:21:08  执行动作      点击「详情」       page-001 -> page-002
10:21:09  记录关系      edge-001          navigation
10:21:16  安全拦截      删除按钮被跳过
```

### 日志详情

当 `run.log` 行包含结构化字段时，展开日志后展示详情：

```yaml
log:
  id: log-0008
  type: action_executed
  level: info
  time: "2026-05-29T10:21:08+08:00"

context:
  page_id: page-001
  page_title: 用户列表
  url: /users

action:
  name: 点击「详情」
  element:
    role: link
    name: 详情
    locator_hint: getByRole('link', { name: '详情' })

result:
  edge_id: edge-001
  target_page_id: page-002
  url_changed: true

artifacts:
  - type: page
    path: pages/page-001-user-list.yaml
  - type: graph
    path: graph.yaml
    edge_id: edge-001
```

## 页面 Tab 边界

探索详情页的四个 tab 分工如下：

| Tab | 定位 | 展示内容 |
| --- | --- | --- |
| 探索计划 | 输入和边界 | 环境、范围、目标、执行边界 |
| 探索概览 | 当前结果和健康度 | 当前已有概览内容；本次只调整“探索模块进度” |
| 探索日志 | 过程审计 | `run.log`、页面动作、产物写入、阻塞和错误 |
| 探索报告 | 人可读结论 | 模块覆盖、页面摘要、风险、建议、后续动作 |

## 探索概览 Tab 设计

探索概览 tab 当前只调整已有的“探索模块进度”模块。不要因为引入结构化探索产物，就在概览页新增一组面向 YAML、edge、路径、待处理事项的技术统计。

### 探索模块进度

探索模块进度用于回答“哪些业务模块已经探索到什么程度”。它面向测试人员展示模块覆盖情况，不直接展示 YAML、edge 等内部技术产物。

探索范围仍然是探索计划的入口配置。普通定向探索按用户填写的探索范围执行；当探索范围为“全部探索”“全站探索”或等价含义时，系统需要基于探索计划生成或读取模块清单，并按模块逐个探索。导航菜单、URL、页面标题只用于辅助发现页面和归入计划模块，不作为独立的模块定义来源。

每个模块展示为一行或一张紧凑卡片：

```text
模块名称 | 状态 | 页面进度 | 最近页面 | 阻塞说明 | 进度
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| 模块名称 | 探索识别或计划配置的模块名称 |
| 状态 | 未开始、探索中、已完成、部分完成、阻塞 |
| 页面进度 | 该模块已探索页面数 / 计划或已发现页面数 |
| 最近页面 | 最近访问或更新的页面 |
| 阻塞说明 | 无阻塞时显示“无”；有阻塞时显示最主要原因 |
| 进度 | 按页面和关键动作综合计算的进度 |

示例：

```text
用户管理   已完成     5/5 页面   编辑用户   无             100%
角色权限   部分完成   3/5 页面   角色详情   1 个页面未访问   60%
系统设置   阻塞       1/4 页面   权限设置   当前账号无权限   25%
```

### 模块状态规则

模块状态按以下规则计算：

- `未开始`：模块已在计划范围内，但没有访问任何页面。
- `探索中`：模块已有页面访问事件，探索任务仍在运行。
- `已完成`：模块内发现页面均已生成页面 YAML，且没有阻塞项。
- `部分完成`：模块内部分页面已生成 YAML，但仍有未访问页面、跳过动作或非关键阻塞。
- `阻塞`：模块存在登录、权限、验证码、超时或安全策略导致的关键阻塞。

### 模块进度计算

第一版进度可以使用轻量规则：

```text
模块进度 = 已探索页面数 / 计划或已发现页面数
```

如果模块没有计划页面数，则使用已发现页面数作为分母。页面 YAML 和 edge 仍然作为后台判断依据，但不直接显示为模块进度字段。

### 模块展开详情

点击模块后展示该模块下的页面和关系摘要：

```text
页面标题 | 页面类型 | URL | 状态 | 阻塞说明 | 最近事件
```

页面行可以跳转到：

- 对应 `pages/page-001-user-list.yaml` 这类页面 YAML
- 对应 `run.log` 运行记录
- 对应 graph edge
- 对应 blocker

## 下游使用方式

### 生成详细测试用例

测试用例生成优先读取：

- `graph.yaml` 中的路径和 edge
- `pages/*.yaml` 中的页面无障碍树
- `blockers.yaml` 中的阻塞和未覆盖原因

生成逻辑：

1. 从 `paths` 中识别完整业务路径。
2. 从页面 YAML 中提取可操作元素、表单字段和状态。
3. 从 `data_dependency` edge 中识别跨页面前置数据。
4. 生成测试步骤、预期结果和来源引用。
5. 对缺少需求确认的页面事实标记 `needs_confirmation`。

### 生成 UI 自动化测试用例

UI 自动化生成优先读取：

- 页面 YAML 中的 `locator_hint`
    - `graph.yaml` 中的 edge 顺序
- `submit`、`submit_and_return`、`navigation`、`open_modal` 类型的动作结果

生成逻辑：

1. 根据 `paths` 生成 Playwright 操作顺序。
2. 使用 `locator_hint` 生成 `getByRole` 优先的定位代码。
3. 如果关键元素缺少 role 或 name，标记为需要补充 locator。
4. 如果路径包含阻塞或安全拦截，不生成可执行代码，只生成待人工处理说明。

弹窗和页面内 tab 不作为独立页面节点处理，只通过 `open_modal`、`close_modal` 和 `tab_switch` edge 记录页面内状态变化。

## 当前改进路径

### 第一步：前端探索计划已完成

探索计划 tab 负责展示本次探索的环境、范围、目标和执行边界。

### 第二步：补齐结构化产物标准

新增或调整探索产物输出：

- `run.yaml`
- `summary.yaml`
- `graph.yaml`
- `blockers.yaml`
- `pages/*.yaml`

不生成截图、HTML 快照或独立 locator 文件。

### 第三步：调整探索执行器

每访问页面时：

1. 生成页面 ID。
2. 采集无障碍树。
3. 写入 `pages/page-001-user-list.yaml` 这类页面 YAML。
4. 识别可操作元素。
5. 执行动作后写入 `graph.yaml` 的 edge。
6. 同步追加 `logs/run.log` 运行记录。

### 第四步：调整探索概览

探索概览本次只调整“探索模块进度”模块，数据来源改为 `summary.yaml`：

- 模块名称
- 模块状态
- 页面进度
- 最近页面
- 阻塞说明
- 进度百分比

### 第五步：调整探索日志

探索日志继续以 `logs/run.log` 为唯一日志产物，前端基于日志行解析提供筛选和详情展示：

- 按类型筛选
- 按页面筛选
- 展开日志详情
- 关联页面 YAML
- 关联 graph edge

### 第六步：调整探索报告

探索报告只展示人可读总结，不再承担完整事实源职责。

探索报告可以从结构化 YAML 产物重新生成；当报告内容与 YAML 事实源不一致时，以 YAML 事实源为准。

报告内容来自：

- 页面 YAML
- graph edges
- blockers
- coverage summary

## 验收标准

- 每次成功探索至少生成一个 `pages/page-001-<slug>.yaml`。
- 每个页面 YAML 必须包含 `page` 和 `accessibility_tree`。
- 页面跳转、提交、弹窗、筛选或安全拦截必须生成对应 edge 或 blocker。
- `graph.yaml` 至少包含 `nodes` 和 `edges`。
- 探索日志中能查看页面访问、无障碍树采集、动作执行、edge 创建和产物写入记录。
- 探索概览的“探索模块进度”能展示模块状态、页面进度、最近页面、阻塞说明和进度百分比。
- 探索概览不把 YAML 数、edge 数、路径数作为“探索模块进度”的用户可见字段。
- 测试用例生成可从 `graph.yaml` 和 `pages/*.yaml` 找到页面路径、操作元素和来源引用。
- UI 自动化生成可从页面 YAML 中读取 `locator_hint`，并在缺少 locator 时标记需要补充。
- 页面 YAML 中的可操作节点应保留 `locator_hint`，动作、日志和 edge 之间通过稳定的 `page.id`、`action.id` 和 `edge.id` 追踪。
