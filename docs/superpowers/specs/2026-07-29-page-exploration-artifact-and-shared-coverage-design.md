# 页面探索产物精简与共享覆盖改造规范

**项目**：AI 测试系统页面探索  
**日期**：2026-07-29  
**状态**：待评审  
**目标版本**：探索产物 Schema 4.0  

---

## 1. 背景

页面探索当前支持自主探索和 Loop 探索，并已经能够将页面快照合并到项目级 `page_exploration/pages/*.yaml`。Loop 探索还具备单次运行内的 `visited_states`、`frontier` 去重以及运行前 baseline、运行后增量合并能力。

现有能力仍有两个主要问题：

1. 当前页面产物包含大量重复、动态或只适合调试的信息，例如整块可见文本、重复 DOM 节点、长 `context.name`、空集合和合并历史，不利于后续稳定消费。
2. 自主探索和 Loop 探索只知道本次运行探索过什么，下一次运行不能直接复用项目中已经验证过的页面状态和交互，因此仍可能重复访问同一页面、重复点击同一元素。

本次改造只处理探索层，不改造详细测试用例生成和 UI 自动化测试生成。后续消费者可以读取改造后的探索产物，但本次不修改其数据模型、生成逻辑或代码结构。

---

## 2. 目标

### 2.1 核心目标

1. 将项目级页面探索产物精简为稳定、语义化、可复用的页面事实。
2. 明确记录页面状态、可操作元素、可断言元素和经过验证的状态转换。
3. 为自主探索和 Loop 探索提供同一份跨运行覆盖记录。
4. 已完成的页面、状态和元素操作默认不再重复探索。
5. 未完成或失败的内容仍可在后续运行中继续探索。
6. 用户可显式要求强制重新探索，忽略已有覆盖记录。
7. 保留当前 run 日志、trace、snapshot、screenshot 等原始证据，但不把这些调试信息写入精简页面产物。

### 2.2 成功标准

- 同一个项目中，自主探索完成的操作可被后续 Loop 探索跳过。
- Loop 探索完成的操作可被后续自主探索识别为已完成。
- Loop 构建 frontier 时不再加入已标记为 `completed` 的元素操作。
- 页面产物不再包含 `assertion_texts`、`merge_history` 和超长上下文文本。
- 同一语义元素只保留一条正式记录。
- 弹窗、Popover 等子状态不再复制背景页面元素。
- 覆盖记录只保存完成状态和最后来源，不保存复杂历史、指纹或有效期。
- 重新探索开关开启后，可忽略原覆盖记录并重新采集。

---

## 3. 非目标

本次明确不做：

- 不修改详细测试用例 Schema。
- 不修改测试用例生成 Agent。
- 不修改 UI 自动化测试用例 Schema。
- 不修改 POM 生成规则。
- 不修改 pytest-playwright 代码生成流程。
- 不增加页面指纹、结构指纹或 Locator 指纹。
- 不增加有效期、过期时间或自动失效策略。
- 不按租户、角色、语言、设备建立复杂复用维度。
- 不实现自动识别前端版本变化。
- 不保留每个页面的完整探索历史。
- 不新增数据库表；项目级 YAML 文件足以满足本阶段需求。
- 不提供 Schema 3.0 向 Schema 4.0 的转换或兼容读取。

页面发生较大变化时，由用户通过“强制重新探索”显式触发重新采集。

---

## 4. 设计原则

### 4.1 页面产物记录事实

页面产物只回答：

- 这是哪个页面。
- 页面有哪些可测试状态。
- 每个状态有哪些可操作或可验证元素。
- 元素支持什么动作。
- 哪个动作会产生哪个状态变化。
- 元素真实可用的定位器是什么。

页面产物不负责记录运行过程、模型思考、合并过程和完整 DOM。

### 4.2 覆盖文件记录完成情况

共享覆盖文件只回答：

- 哪个页面是否探索完成。
- 哪个状态是否探索完成。
- 哪个元素操作是否执行并验证完成。
- 最后由哪个 run、哪种探索模式完成。

覆盖文件不复制元素名称、Locator、页面文本或完整 transition。

### 4.3 稳定 Key 是唯一关联方式

页面产物、覆盖文件、Loop frontier 和自主探索上下文统一使用稳定 Key：

```text
page_id
state_id
element_key
element_key:action
```

不得使用动态用户名、编辑时间、列表序号或完整卡片文本作为 Key。

### 4.4 完成必须经过验证

仅在操作执行成功，并观察到动作后的页面状态时，才可将操作标记为 `completed`。

以下情况不能标记完成：

- 只在 snapshot 中看到了元素，但没有执行动作。
- 动作调用失败。
- 动作执行后无法确认页面结果。
- 操作被风险规则拦截。
- 用户取消运行。
- 元素已过时或无法定位。

---

## 5. 整体架构

```text
┌──────────────────────────────────────────────┐
│ 自主探索 / Loop 探索                         │
└──────────────────────┬───────────────────────┘
                       │ 启动时读取
                       ▼
┌──────────────────────────────────────────────┐
│ exploration-coverage.yaml                    │
│ - 已完成页面                                 │
│ - 已完成状态                                 │
│ - 已完成元素操作                             │
└──────────────────────┬───────────────────────┘
                       │ 过滤已完成内容
                       ▼
┌──────────────────────────────────────────────┐
│ 执行增量探索                                 │
│ - 自主探索只接收待探索摘要                   │
│ - Loop 只 enqueue 未完成 frontier            │
└──────────────────────┬───────────────────────┘
                       │ 保存和合并
                       ▼
┌──────────────────────────────────────────────┐
│ pages/*.yaml                                 │
│ - 页面事实                                   │
│ - 状态、元素、转换、Locator                  │
└──────────────────────┬───────────────────────┘
                       │ 运行成功后更新
                       ▼
┌──────────────────────────────────────────────┐
│ exploration-coverage.yaml                    │
│ - completed / pending                        │
│ - run_id / mode                              │
└──────────────────────────────────────────────┘
```

---

## 6. 文件布局

```text
page_exploration/
├── exploration-coverage.yaml
├── page_edges.yaml
├── pages/
│   ├── pages-index.yaml
│   ├── page-workspace.yaml
│   └── page-agent-editor.yaml
└── runs/
    └── {run_id}/
        ├── loop_state.json
        ├── timeline_events.jsonl
        ├── raw_events.jsonl
        ├── baseline/
        ├── conflicts/
        └── evidence/
```

### 6.1 文件职责

| 文件 | 职责 |
|---|---|
| `pages/*.yaml` | 当前项目最新的规范化页面事实 |
| `pages-index.yaml` | 页面列表展示、最近写入 run 和时间 |
| `exploration-coverage.yaml` | 自主探索与 Loop 探索共享的完成记录 |
| `page_edges.yaml` | 跨页面跳转关系 |
| `runs/{run_id}` | 单次运行日志、checkpoint、baseline、冲突和原始证据 |

`pages-index.yaml` 继续承担页面列表索引职责，不扩展为覆盖记录。`exploration-coverage.yaml` 不替代页面产物，也不复制页面产物内容。

---

## 7. 页面探索产物 Schema 4.0

### 7.1 顶层结构

```yaml
schema_version: '4.0'

page:
  id: page-workspace
  title: 百融百工
  normalized_path: /workspace

objects: []
states: []
elements: []
collections: []
transitions: []
quality:
  status: complete
  unresolved: []
```

只保留七类正式信息：

- `page`
- `objects`
- `states`
- `elements`
- `collections`
- `transitions`
- `quality`

空集合在序列化时省略，但读取端必须按空集合处理缺失字段。

### 7.2 `page`

```yaml
page:
  id: page-workspace
  title: 百融百工
  normalized_path: /workspace
```

规则：

- `id` 由 normalized path 稳定生成。
- `normalized_path` 不包含环境域名。
- 动态路由参数使用占位符，例如 `/agent/{agent_id}`。
- 页面标题只保存一次，不在 state 中重复。
- 不保存每次 snapshot 的完整 URL。

### 7.3 `objects`

`objects` 用于区分页面和页面内独立交互容器。

```yaml
objects:
  - key: workspace
    type: page
    name: 百融百工

  - key: create_agent_popover
    type: popover
    name: 创建智能体
    parent: workspace
    container_locator:
      strategy: css
      value: .create-agent-dropdown
```

支持的最小类型：

```text
page
dialog
popover
drawer
region
```

规则：

- Root 页面必须有一个 `page` object。
- Dialog、Popover、Drawer 等有独立作用域的容器建立 object。
- 普通布局 `div` 不建立 object。
- object 不包含 POM 类名、Python 文件路径等自动化实现信息。

### 7.4 `states`

```yaml
states:
  - id: workspace.root
    type: root
    object: workspace

  - id: workspace.create_agent_popover
    type: popover
    object: create_agent_popover
    parent: workspace.root
```

状态只用于表达会影响测试行为的可观察 UI 状态，例如：

- 根页面。
- Dialog、Popover、Drawer 打开。
- Tab 切换。
- 编辑状态。
- 提交中、成功、失败。
- 关键结果区域出现。

不为动画、hover、动态时间刷新和列表顺序变化建立 state。

所有 state 使用扁平列表，通过 `parent` 建立关系，不再把完整子状态嵌套到父状态的 `children` 中。

### 7.5 `elements`

只保存：

1. 可操作元素。
2. 可作为明确验证目标的元素。
3. 为动态子元素提供作用域的业务容器。

普通按钮示例：

```yaml
elements:
  - key: workspace.create_agent_trigger
    object: workspace
    states:
      - workspace.root
    role: button
    name: 创建
    actions:
      - click
    locator:
      strategy: role
      role: button
      name: 创建
      exact: true
```

输入框示例：

```yaml
  - key: agent_editor.agent_name_input
    object: agent_editor
    states:
      - agent_editor.root
    role: textbox
    name: 智能体名称
    actions:
      - fill
      - clear
      - assert_value
    locator:
      strategy: label
      value: 智能体名称
      exact: true
    input:
      type: string
      required: true
      max_length: 50
```

状态元素示例：

```yaml
  - key: workspace.agent_status
    object: workspace
    states:
      - workspace.root
    role: status
    name: 发布状态
    actions:
      - assert_visible
      - assert_text
```

规则：

- `key` 在项目页面范围内稳定且唯一。
- `object` 必须引用已存在 object。
- `states` 表示元素在哪些状态可用。
- `actions` 表示真实能力，不根据 DOM 标签盲目推断。
- 不可点击的状态文字不得声明 `click`。
- `input` 只记录真实观察到的约束；未知字段直接省略。
- 无定位器的断言元素可暂时保留，但必须在 `quality.unresolved` 中记录。

### 7.6 支持的元素动作

```text
click
fill
clear
select_option
check
uncheck
upload
press
assert_visible
assert_hidden
assert_text
assert_value
assert_enabled
assert_disabled
```

探索工具产生的动作需要映射到以上标准动作。无法识别的动作不写入正式页面产物，并记录到当前 run 日志。

### 7.7 动态列表元素

动态卡片、表格行和列表项不得使用具体数据组成稳定 Key。

错误示例：

```yaml
key: clickable-ExploreBot_2026-已发布-hongbao.wang1-2026-07-23
```

正确示例：

```yaml
  - key: workspace.agent_card
    object: workspace
    states:
      - workspace.root
    role: card
    name: 智能体卡片
    repeatable: true
    parameters:
      - agent_name
    actions:
      - click
      - assert_visible
    locator:
      strategy: css
      value: .agent-item-card
      filters:
        - type: has_text
          value_ref: agent_name
```

动态卡片内的按钮通过 scope 关联：

```yaml
  - key: workspace.agent_card.use_button
    object: workspace
    states:
      - workspace.root
    role: button
    name: 使用
    parameters:
      - agent_name
    actions:
      - click
    scope:
      element: workspace.agent_card
      arguments:
        agent_name: agent_name
    locator:
      strategy: text
      value: 使用
      exact: true
```

### 7.8 集合代表性探索

对于可新增、删除的卡片、表格行和列表项，不逐条执行相同操作。探索器先读取可见条目的类型、状态和按钮，再按以下规则选择代表项：

1. 按“类型 + 状态”分组。
2. 每组只选择一条代表项执行探索。
3. 同组其他条目跳过。
4. 如果同组条目的按钮列表不同，将按钮不同的条目作为额外代表项探索一次。
5. 新增条目只有出现新类型、新状态或新按钮列表时才需要探索。

例如智能体卡片可分为：

```text
Multi-Agent + 草稿
Multi-Agent + 已发布
自主规划 Agent + 已发布
任务流 Agent + 已发布
写作 Agent + 已发布
```

正式页面产物只保存分组和代表项，不保存全部重复实例：

```yaml
collections:
  - key: workspace.agent_cards
    item_element: workspace.agent_card
    group_by:
      - type
      - status
    groups:
      - type: Multi-Agent
        status: 草稿
        representative: test
        actions:
          - 编辑
          - 更多

      - type: Multi-Agent
        status: 已发布
        representative: Multi-Agent-go第三方渠道
        actions:
          - 使用
          - 对话历史
          - 更多

      - type: 自主规划 Agent
        status: 已发布
        representative: tmp
        actions:
          - 分析
          - 使用
          - 对话历史
          - 更多

      - type: 任务流 Agent
        status: 已发布
        representative: 任务流-测试
        actions:
          - 分析
          - 使用
          - 调用历史
          - 更多

      - type: 写作 Agent
        status: 已发布
        representative: 写作Agent
        actions:
          - 分析
          - 使用
          - 任务历史
          - 更多
```

规则：

- `representative` 只是本次用于探索的实例名称，不作为元素 Key。
- 不保存同组全部实例名称、用户名、编辑时间或列表序号。
- 同一“类型 + 状态”下按钮列表相同，视为重复条目。
- 同一“类型 + 状态”下按钮列表不同，允许存在多个 group 记录。
- 集合扫描只读取卡片信息，不执行点击；只有选中的代表项进入实际探索。

### 7.9 Locator

Locator 采用结构化字段，不再只保存待解析的代码字符串。

```yaml
locator:
  strategy: role
  role: button
  name: 创建智能体
  exact: true
```

每个元素最多保存：

- 一个主 `locator`。
- 一个可选 `fallback_locator`。

优先级：

1. `role + accessible name`
2. `label`
3. `placeholder`
4. `test_id`
5. 稳定文本
6. CSS
7. XPath

规则：

- 主 Locator 必须来自真实 snapshot 或成功交互。
- 纯 `nth-of-type` 结构 Locator 只能作为 fallback。
- 不保存大量等价 Locator。
- Locator 内不包含动态时间、用户名或随机 ID。
- Dialog、Popover 内元素必须通过 `object` 或 `scope` 限定作用域。

### 7.10 `transitions`

Transition 记录经过实际操作验证的状态变化。

```yaml
transitions:
  - id: workspace.open_create_agent_popover
    from_state: workspace.root
    action: click
    target: workspace.create_agent_trigger
    to_state: workspace.create_agent_popover
    observations:
      - kind: visible
        target: create_agent_popover
    url_changed: false
```

规则：

- `target` 必须引用已存在元素。
- `action` 必须包含在目标元素的 `actions` 中。
- `from_state` 和 `to_state` 必须存在。
- 只有操作执行并观察到目标状态后才写入 transition。
- 失败、被阻塞或结果不明确的操作不写入正式 transition，保留在 run 日志和 coverage pending 中。
- 跨页面跳转除写 transition 外，还应更新 `page_edges.yaml`。

### 7.11 `quality`

```yaml
quality:
  status: partial
  unresolved:
    - id: workspace.filter_1
      type: unknown_semantics
      reason: 已发现 combobox，但无法确认业务含义
```

状态只使用：

```text
complete
partial
```

- `complete`：当前探索范围内没有待处理状态或操作。
- `partial`：仍有未识别、未执行、失败或被阻塞内容。

`unresolved` 只保存会影响产物使用的问题，不保存普通探索日志。

---

## 8. 页面产物裁剪规则

### 8.1 从正式页面 YAML 删除

- `assertion_texts`
- `merge_history`
- 超长 `context.name`
- state 中重复的页面标题
- state 中重复的完整 URL
- 空的 `regions`
- 空的 `interactions`
- 空的 `blockers`
- 空的 `children`
- 完整可见文本块
- 完整 accessibility tree
- DOM ancestor chain
- 用户名、编辑时间和动态计数组成的 Key
- 同一元素父节点和子节点的重复记录
- Popover、Dialog 中重复采集的背景页面元素
- 无业务意义且不可操作、不可验证的 `div/span/svg`
- 每个元素超过两个的 Locator
- run 合并过程和冲突历史

### 8.2 保留在 run 原始证据中

- 完整 snapshot
- accessibility tree
- visible text blocks
- trace
- screenshot
- timeline events
- raw events
- 工具调用输入输出
- merge summary
- conflict 文件

正式页面产物不复制原始证据。需要排障时通过 run_id 和 run 目录定位。

### 8.3 元素去重

满足以下条件时视为同一语义元素：

- 相同 object。
- 相同 state。
- 相同 role。
- 相同稳定 name。
- Locator 指向相同交互目标。

父 `div` 和子 `span` 同时代表同一状态文字时，只保留最接近真实语义角色的一条记录。

### 8.4 子状态元素范围

Dialog、Popover、Drawer state 只保存：

- 容器本身。
- 容器内部可操作元素。
- 容器内部可验证元素。
- 关闭方式。

背景页面元素由其原 state 维护，不在子状态重复保存。

---

## 9. 共享探索覆盖文件

### 9.1 文件路径

```text
page_exploration/exploration-coverage.yaml
```

这是项目级唯一覆盖记录，自主探索和 Loop 探索共同读写。

### 9.2 Schema

```yaml
schema_version: '1.0'

pages:
  page-workspace:
    path: /workspace
    artifact: pages/page-workspace.yaml
    status: partial

    states:
      workspace.root:
        status: completed
        run_id: exp_AAA
        mode: autonomous

      workspace.create_agent_popover:
        status: completed
        run_id: exp_BBB
        mode: loop

    actions:
      workspace.create_agent_trigger:click:
        status: completed
        from_state: workspace.root
        to_state: workspace.create_agent_popover
        run_id: exp_BBB
        mode: loop

      create_agent_popover.autonomous_agent_option:click:
        status: pending

    collections:
      workspace.agent_cards:
        groups:
          Multi-Agent:草稿:
            status: completed
            representative: test
            run_id: exp_BBB
            mode: loop

          Multi-Agent:已发布:
            status: completed
            representative: Multi-Agent-go第三方渠道
            run_id: exp_BBB
            mode: loop

          自主规划Agent:已发布:
            status: completed
            representative: tmp
            run_id: exp_BBB
            mode: loop
```

### 9.3 状态集合

页面状态：

```text
complete
partial
```

state 和 action 状态：

```text
completed
pending
```

不增加其他中间状态。

### 9.4 Action Key

Action Key 固定为：

```text
{element_key}:{action}
```

示例：

```text
workspace.create_agent_trigger:click
workspace.agent_filter:select_option
agent_editor.agent_name_input:fill
```

对于参数化动态元素，覆盖记录表示“该交互模式已探索”，不为每个具体数据值生成一条覆盖记录。

集合覆盖 Key 默认使用：

```text
{type}:{status}
```

例如：

```text
Multi-Agent:草稿
Multi-Agent:已发布
自主规划Agent:已发布
```

如果同一类型和状态存在不同按钮列表，可在组名后追加简短序号：

```text
自主规划Agent:已发布:2
```

不生成复杂签名，也不为每张具体卡片建立 coverage。

### 9.5 最小来源信息

每个完成项只保存最后一次完成来源：

```yaml
run_id: exp_BBB
mode: loop
```

`mode` 只允许：

```text
autonomous
loop
```

不保存完整来源历史。运行历史由 `runs/{run_id}` 目录承担。

---

## 10. 覆盖更新规则

### 10.1 State 完成

当 state 已成功采集，并且其正式元素已写入页面产物：

```yaml
states:
  workspace.root:
    status: completed
    run_id: exp_AAA
    mode: autonomous
```

只看到一个不完整 snapshot，或页面采集发生错误时保持 `pending`。

### 10.2 Action 完成

Action 只有同时满足以下条件才标记 `completed`：

1. 目标元素成功定位。
2. 动作执行成功。
3. 执行后重新观察页面。
4. 观察结果与 transition 一致。
5. transition 已写入正式页面产物。

完成记录：

```yaml
workspace.create_agent_trigger:click:
  status: completed
  from_state: workspace.root
  to_state: workspace.create_agent_popover
  run_id: exp_BBB
  mode: loop
```

### 10.3 Action 保持 pending

以下情况保持或写入 `pending`：

- 动作没有执行。
- 定位失败。
- 操作失败。
- 验证失败。
- 操作受风险规则阻塞。
- 操作需要人工处理。
- 运行取消或异常终止。

`pending` 项不需要保存失败详情；失败详情保存在 run 的 timeline 和 failures 中。

### 10.4 页面完成

页面满足以下条件时标记 `complete`：

- 当前范围内所有已发现 state 均为 `completed`。
- 当前范围内所有需要执行的 action 均为 `completed`。
- 页面 `quality.unresolved` 为空。

否则标记为 `partial`。

### 10.5 更新时机

探索过程中继续使用当前 run checkpoint，不在每一步直接覆盖项目级 coverage。

项目级 coverage 在以下时机更新：

1. 页面产物成功保存或合并。
2. transition 已通过验证。
3. 本次运行的可用结果已经确定。

运行失败或取消时，可以合并已经验证成功的 state 和 action，但不得把未完成项标记为完成。

### 10.6 集合分组完成

当代表项的可用按钮均已完成必要探索后，将对应“类型 + 状态”分组标记为 `completed`：

```yaml
collections:
  workspace.agent_cards:
    groups:
      自主规划Agent:已发布:
        status: completed
        representative: tmp
        run_id: exp_BBB
        mode: loop
```

同组其他实例不重复探索。代表项探索未完成时，分组保持 `pending`。

---

## 11. Loop 探索复用流程

### 11.1 启动流程

```text
1. 读取 exploration-coverage.yaml。
2. 获取起始页面 snapshot。
3. 识别 page_id 和 state_id。
4. 检查页面覆盖记录。
5. 页面 complete 且未强制重新探索：跳过该页面。
6. 页面 partial：继续观察并只 enqueue 未完成 action。
7. 页面无记录：按当前 Loop 逻辑完整探索。
```

### 11.2 Frontier 过滤

Loop 当前从 snapshot 候选构建 frontier。改造后，在 enqueue 前增加覆盖检查：

```python
coverage_key = f"{element_key}:{action_type}"

if not force_reexplore and coverage.is_action_completed(page_id, coverage_key):
    continue

state.enqueue(candidate)
```

规则：

- 已完成 action 不进入 frontier。
- `pending` action 正常进入 frontier。
- coverage 无记录的 action 正常进入 frontier。
- `force_reexplore=true` 时不执行过滤。

对于重复卡片或列表条目，Loop 在构建候选前先按“类型 + 状态”分组：

```text
1. 已 completed 的组不再选择代表项。
2. pending 或无记录的组只选择一条代表项。
3. 同组按钮列表不同时，再选择一条按钮不同的代表项。
4. 未选中的重复实例不进入 frontier。
```

### 11.3 页面跳过

当页面为 `complete` 且未强制重新探索时：

- 不执行页面内候选操作。
- 当前 run 记录 `page_reused` 事件。
- 已有页面产物保持不变。
- 不把复用行为重新写成一次“完成来源”。

### 11.4 Loop 结束

Loop 结束后：

1. 按现有 baseline 合并页面产物。
2. 冲突页面保持当前冲突处理行为。
3. 从本次已验证 transition 更新 coverage action。
4. 从成功保存的 state 更新 coverage state。
5. 重新计算页面是 `complete` 还是 `partial`。

存在合并冲突时，冲突相关 action 保持 `pending`，页面保持 `partial`。

---

## 12. 自主探索复用流程

### 12.1 启动前生成复用摘要

自主探索启动前，由确定性服务读取 coverage，生成受控上下文：

```yaml
exploration_coverage:
  completed_pages:
    - page-workspace

  completed_states:
    - workspace.root
    - workspace.create_agent_popover

  completed_actions:
    - workspace.create_agent_trigger:click

  pending_actions:
    - create_agent_popover.autonomous_agent_option:click

  completed_collection_groups:
    - collection: workspace.agent_cards
      type: 自主规划 Agent
      status: 已发布

  pending_collection_groups:
    - collection: workspace.agent_cards
      type: 写作 Agent
      status: 草稿
```

自主探索 Agent 只接收摘要，不直接读取完整历史 run。

### 12.2 Agent 约束

自主探索提示中增加固定规则：

```text
1. 不要重复探索 completed_pages、completed_states 和 completed_actions。
2. 优先探索 pending_actions。
3. 新发现且无覆盖记录的元素可以继续探索。
4. 只有动作执行并验证成功后，才能报告为完成。
5. 强制重新探索开启时，忽略以上完成记录。
```

### 12.3 自主探索结束

自主探索结束后，与 Loop 使用同一个 coverage 更新服务：

- 成功保存的 state 标记 `completed`。
- 成功验证的 transition 对应 action 标记 `completed`。
- 未执行、失败和阻塞 action 保持 `pending`。
- 页面按相同规则计算 `complete/partial`。

不得分别维护 `autonomous-coverage.yaml` 和 `loop-coverage.yaml`。

---

## 13. 强制重新探索

探索请求增加统一参数：

```yaml
force_reexplore: false
```

行为：

| 参数 | 行为 |
|---|---|
| `false` | 读取共享 coverage，跳过 completed 内容 |
| `true` | 忽略共享 coverage，按正常逻辑重新探索 |

重新探索成功后：

- 页面产物按现有合并规则更新。
- coverage 对应完成项更新为本次 run。
- 强制重新探索开始前清除目标页面的旧 coverage；本次未验证成功的内容保持 `pending`。

为保持本期简单，不自动判断页面是否变化。页面变化由用户主动选择强制重新探索。

---

## 14. 页面删除与覆盖清理

当正式页面产物被明确删除时，应同步删除 coverage 中对应 page 节点。

当页面产物合并后确认某个 state、element 或 transition 已被正式删除时：

- 删除不存在 state 的 coverage state。
- 删除目标 element 不存在的 coverage action。
- 删除正式 transition 不存在的 completed action。

不进行基于时间的自动清理。

---

## 15. 当前 Workspace 重新探索产物示例

### 15.1 当前问题

现有 `page-workspace.yaml` 包含：

- `assertion_texts` 整页长文本。
- 多个无明确业务语义的 `combobox-element-*`。
- 父 `div` 和子 `span` 重复的“已发布”。
- 用户名、编辑时间和完整卡片文本组成的 Key。
- Popover state 中重复的背景页面卡片。
- `triggered_by.element_key` 引用 root state 中不存在的创建按钮。
- `combobox-element-4` 在不同 state 中具有不同含义。

### 15.2 重新探索后的页面产物

```yaml
schema_version: '4.0'

page:
  id: page-workspace
  title: 百融百工
  normalized_path: /workspace

objects:
  - key: workspace
    type: page
    name: 百融百工

  - key: create_agent_popover
    type: popover
    name: 创建智能体
    parent: workspace
    container_locator:
      strategy: css
      value: .create-agent-dropdown

states:
  - id: workspace.root
    type: root
    object: workspace

  - id: workspace.create_agent_popover
    type: popover
    object: create_agent_popover
    parent: workspace.root

elements:
  - key: workspace.create_agent_trigger
    object: workspace
    states: [workspace.root]
    role: button
    name: 创建智能体
    actions: [click]
    locator:
      strategy: role
      role: button
      name: 创建智能体
      exact: true

  - key: create_agent_popover.autonomous_agent_option
    object: create_agent_popover
    states: [workspace.create_agent_popover]
    role: option
    name: 自主规划 Agent
    actions: [click]
    locator:
      strategy: text
      value: 自主规划 Agent
      exact: true

  - key: workspace.agent_card
    object: workspace
    states: [workspace.root]
    role: card
    name: 智能体卡片
    repeatable: true
    parameters: [agent_name]
    actions: [click, assert_visible]
    locator:
      strategy: css
      value: .agent-item-card
      filters:
        - type: has_text
          value_ref: agent_name

  - key: workspace.agent_status
    object: workspace
    states: [workspace.root]
    role: status
    name: 发布状态
    repeatable: true
    parameters: [agent_name]
    actions: [assert_visible, assert_text]

transitions:
  - id: workspace.open_create_agent_popover
    from_state: workspace.root
    action: click
    target: workspace.create_agent_trigger
    to_state: workspace.create_agent_popover
    observations:
      - kind: visible
        target: create_agent_popover
    url_changed: false

quality:
  status: partial
  unresolved:
    - id: workspace.filters
      type: unknown_semantics
      reason: 三个筛选框缺少可确认的业务标签和选项
```

示例中的名称和 Locator 必须以重新采集到的真实页面证据为准；不得读取旧长文本推测缺失语义。

### 15.3 对应 coverage

```yaml
schema_version: '1.0'

pages:
  page-workspace:
    path: /workspace
    artifact: pages/page-workspace.yaml
    status: partial

    states:
      workspace.root:
        status: completed
        run_id: exp_AAA
        mode: autonomous

      workspace.create_agent_popover:
        status: completed
        run_id: exp_BBB
        mode: loop

    actions:
      workspace.create_agent_trigger:click:
        status: completed
        from_state: workspace.root
        to_state: workspace.create_agent_popover
        run_id: exp_BBB
        mode: loop

      create_agent_popover.autonomous_agent_option:click:
        status: pending
```

---

## 16. 后端模块边界

本次改造建议形成三个明确职责模块。

### 16.1 页面产物规范化器

职责：

- 将 snapshot 和探索事件转换为 Schema 4.0。
- 生成稳定 object、state 和 element Key。
- 去重元素。
- 结构化 Locator。
- 生成经过验证的 transition。
- 计算 `quality.complete/partial`。

不负责：

- 决定是否跳过探索。
- 保存 run 日志。
- 生成测试用例。

### 16.2 覆盖登记服务

职责：

- 读取和写入 `exploration-coverage.yaml`。
- 查询 page、state、action 是否完成。
- 根据页面产物和已验证结果更新 coverage。
- 删除页面产物已不存在的覆盖项。
- 生成自主探索复用摘要。

建议最小接口：

```python
load(project_id) -> Coverage
is_page_complete(project_id, page_id) -> bool
is_state_completed(project_id, page_id, state_id) -> bool
is_action_completed(project_id, page_id, element_key, action) -> bool
build_autonomous_summary(project_id, scope) -> dict
update_from_run(project_id, run_id, mode, page_artifacts, verified_transitions) -> None
remove_page(project_id, page_id) -> None
```

### 16.3 探索模式适配

Loop 和自主探索保持各自执行方式，只通过覆盖登记服务共享信息。

- Loop 在 frontier enqueue 前调用 `is_action_completed`。
- 自主探索在 Agent 启动前调用 `build_autonomous_summary`。
- 两种模式结束后调用同一个 `update_from_run`。

不在 Loop 与自主探索之间直接共享内部运行状态。

---

## 17. 并发与写入安全

虽然本期不引入数据库，coverage 文件仍可能被两个探索 run 同时更新。

最小安全要求：

1. 使用项目级文件锁保护 `exploration-coverage.yaml`。
2. 锁内重新读取最新文件。
3. 只合并本次已验证的 state 和 action。
4. 原子写入临时文件后替换正式文件。
5. 不允许后写入的旧快照覆盖其他 run 已完成的 action。

合并规则：

- `completed` 优先于 `pending`。
- 新的 `completed` 可以更新最后 `run_id/mode`。
- `pending` 不能把已有 `completed` 降级。
- 强制重新探索开始前先删除目标页面的旧 coverage，再根据本次真实结果重新写入。

---

## 18. 一次性切换与旧产物清理

### 18.1 切换原则

Schema 4.0 采用一次性切换：

- 不读取 Schema 3.0 页面产物。
- 不将旧 state、element、`triggered_by` 或 Locator 转换为新结构。
- 不根据旧产物初始化 coverage。
- 切换后所有正式页面事实必须由自主探索或 Loop 探索重新采集。

### 18.2 删除范围

部署 Schema 4.0 前，一次性删除每个项目的旧探索产物：

```text
page_exploration/pages/
page_exploration/runs/
page_exploration/page_edges.yaml
page_exploration/operations.yaml
page_exploration/operations.yaml.lock
page_exploration/subgoals.yaml
page_exploration/exploration-coverage.yaml
```

删除规则：

- 删除整个旧 `pages` 目录，由新探索重新创建页面 YAML 和 `pages-index.yaml`。
- 删除整个旧 `runs` 目录，包括旧 baseline、报告、事件和冲突文件。
- 删除旧 `page_edges.yaml`，避免页面边引用已删除页面。
- 删除旧 `operations.yaml`、锁文件和 `subgoals.yaml`，避免复用由 Schema 3.0 产物派生的操作和目标。
- 删除已有试验版 coverage。
- 清理数据库中指向上述旧文件的探索产物登记和旧探索 run 记录，避免页面或产物列表出现失效引用。
- 不删除项目配置、登录状态或探索任务定义。

### 18.3 保留内容

一次性清理只针对旧探索产物和旧运行记录，以下内容继续保留：

- 项目定义。
- 环境配置。
- 登录和认证状态。
- 用户创建的探索任务定义。
- 与页面探索无关的其他业务产物。

### 18.4 切换步骤

1. 停止正在执行的页面探索任务。
2. 部署 Schema 4.0 页面产物和共享 coverage 代码。
3. 删除项目级旧探索文件、历史 runs 和旧派生产物。
4. 清理数据库中的旧探索产物登记和旧 run 记录。
5. 确认项目下不存在旧 `pages`、`runs`、页面边、操作、子目标和 coverage。
6. 重新启动探索服务。
7. 由用户重新发起自主探索或 Loop 探索。
8. 首次新探索生成 Schema 4.0 页面产物和 coverage。

### 18.5 切换失败

如果新探索写入失败：

- 不恢复旧 Schema 3.0 正式产物。
- 保留本次 Schema 4.0 run 日志和 conflict 文件用于排查。
- 页面保持未探索状态。
- 修复问题后重新发起探索。

---

## 19. 事件与可观测性

新增最小事件：

```text
coverage_loaded
page_reused
state_reused
action_skipped_completed
coverage_updated
force_reexplore_enabled
```

事件示例：

```json
{
  "event": "action_skipped_completed",
  "page_id": "page-workspace",
  "action_key": "workspace.create_agent_trigger:click",
  "source_run_id": "exp_BBB"
}
```

每次运行报告增加精简摘要：

```yaml
coverage_summary:
  pages_reused: 1
  states_reused: 2
  actions_skipped: 5
  actions_completed: 3
  actions_pending: 1
```

不增加复杂收益评分和可信度评分。

---

## 20. 错误处理

### 20.1 Coverage 文件不存在

按空覆盖处理，探索正常执行；首次产生可用结果后创建文件。

### 20.2 Coverage 文件损坏

- 不阻塞探索。
- 记录告警。
- 将损坏文件复制到当前 run 目录用于排查。
- 按空覆盖执行。
- 运行成功后重建 coverage。

### 20.3 Coverage 引用不存在页面

读取时忽略该 page，更新时清理对应记录。

### 20.4 Coverage action 引用不存在元素

不得继续跳过该 action；将其视为无覆盖，并在下一次保存时清理。

### 20.5 页面合并冲突

- 页面保持 `partial`。
- 冲突 action 不更新为 `completed`。
- 保留 `runs/{run_id}/conflicts`。
- 其他无冲突且已验证内容可以正常更新。

---

## 21. 测试策略

### 21.1 页面产物规范化测试

- 删除 `assertion_texts` 和 `merge_history`。
- 空集合不输出。
- state 扁平化并保留 parent。
- Popover 不复制背景元素。
- 父子重复节点合并为一个元素。
- 状态文字不错误声明 `click`。
- Locator 按优先级选择并最多保留两个。
- 动态卡片生成参数化 Key，不包含具体用户名和时间。
- 动态卡片按“类型 + 状态”分组，每组只保存一个代表项。
- 同组按钮相同时不产生重复 group。
- 同组按钮不同时允许补充一个 group。
- 悬空 transition 被拒绝并写入 unresolved。

### 21.2 Coverage 服务测试

- 文件不存在时返回空覆盖。
- state/action completed 查询正确。
- `completed` 不被后续 `pending` 降级。
- 更新只保存最后 run_id 和 mode。
- 页面删除后 coverage 同步删除。
- 不存在元素的 action 自动清理。
- 集合分组 completed 查询正确。
- 同一“类型 + 状态”的重复实例不会生成多条 coverage。
- 文件损坏时按空覆盖继续并记录告警。
- 并发写入不会丢失不同 run 的 completed action。

### 21.3 Loop 集成测试

- 已 completed action 不进入 frontier。
- 已 completed 集合分组不选择代表项。
- pending 集合分组只选择一条代表项。
- 同组按钮列表不同时额外选择一条代表项。
- pending action 仍进入 frontier。
- 无 coverage 时保持原探索行为。
- 页面 complete 时记录 page_reused。
- force_reexplore 时 completed action 重新进入 frontier。
- 操作成功并验证后写 completed。
- 操作失败后保持 pending。
- 合并冲突不写 completed。

### 21.4 自主探索集成测试

- Agent 上下文包含 completed 和 pending 摘要。
- 摘要不包含完整历史 run 和敏感信息。
- 自主探索完成的 action 可被后续 Loop 跳过。
- Loop 完成的 action 出现在后续自主探索 completed 摘要。
- 自主探索摘要包含 completed/pending 集合分组。
- force_reexplore 时不向 Agent 应用跳过约束。

### 21.5 回归测试

- 现有项目页面列表仍能读取 `pages-index.yaml`。
- 现有 baseline 和 conflict 机制继续工作。
- 现有 Loop checkpoint 和恢复能力不受影响。
- 现有探索报告可继续生成。
- 清理旧产物后，页面列表为空且不会读取历史 run 作为正式页面。
- 首次新探索能够重新生成 Schema 4.0 页面、索引、页面边和 coverage。
- 旧 operations、subgoals、run 目录和数据库产物登记已清理。

---

## 22. 验收标准

### AC-1：页面产物精简

给定一次 Workspace 页面探索，生成的页面 YAML：

- 不含 `assertion_texts`。
- 不含 `merge_history`。
- 不含超长完整卡片文本 Key。
- “已发布”只保留一个语义状态元素。
- Popover state 不重复保存背景卡片。

### AC-2：稳定关联

页面产物中的每个 transition：

- `from_state` 存在。
- `to_state` 存在。
- `target` 元素存在。
- `action` 是目标元素支持的动作。

### AC-3：Loop 跨运行复用

第一次 Loop 完成：

```text
workspace.create_agent_trigger:click
```

第二次 Loop 在 `force_reexplore=false` 时，不再将该操作加入 frontier。

### AC-4：自主与 Loop 双向复用

- 自主探索完成的 action 可被 Loop 跳过。
- Loop 完成的 action 会出现在自主探索复用摘要中。

### AC-5：失败不冒充完成

动作定位、执行或验证失败时，coverage 中该 action 不得变为 `completed`。

### AC-6：强制重新探索

`force_reexplore=true` 时，已有 completed page、state 和 action 不阻止重新探索。

### AC-7：简单持久化

系统只新增一个项目级 `exploration-coverage.yaml`，不新增指纹、有效期、数据库表或复杂历史文件。

### AC-8：旧产物一次性清理

Schema 4.0 部署前，旧页面、历史 runs、页面边、operations、subgoals、试验 coverage 及对应数据库登记被删除；系统不读取或转换 Schema 3.0 产物，页面必须重新探索。

### AC-9：重复卡片代表性探索

给定同一页面存在多张“自主规划 Agent + 已发布”卡片，且按钮均为“分析、使用、对话历史、更多”：

- 探索器只选择一张代表卡片执行操作。
- 其他同组卡片不进入 frontier。
- 页面产物只保存一个“自主规划 Agent + 已发布”group。
- coverage 只保存一个对应 group。

如果同组存在按钮不同的卡片，允许额外选择一张代表卡片探索。

---

## 23. 实施阶段建议

### 阶段一：Coverage 基础能力

- 新增 coverage 模型和文件服务。
- 实现项目级锁和原子写入。
- 实现 completed/pending 查询与更新。
- 增加 `force_reexplore` 参数。

### 阶段二：Loop 接入

- Loop 构建 frontier 前过滤 completed action。
- 页面 complete 时支持跳过。
- Loop 结束后更新共享 coverage。
- 增加复用事件和摘要。

### 阶段三：自主探索接入

- 构建自主探索复用摘要。
- 在 Agent 提示中加入跳过规则。
- 自主探索结束后更新共享 coverage。

### 阶段四：页面产物 Schema 4.0

- 实现 object、state、element、transition 规范化。
- 删除旧噪音字段。
- 实现元素去重和子状态范围过滤。
- 读取端只接受 Schema 4.0。

### 阶段五：旧产物清理与回归

- 停止运行中的探索任务。
- 删除旧页面、历史 runs、页面边、operations、subgoals、试验 coverage 和对应数据库登记。
- 重新探索 Workspace 样例并生成 Schema 4.0 产物。
- 补齐单元、集成和回归测试。
- 验证自主探索与 Loop 双向复用。
- 确认系统不会读取或转换 Schema 3.0 产物。

阶段顺序允许阶段二、三与阶段四部分并行，但 coverage 必须始终通过稳定 Key 与页面产物关联。

---

## 24. 最终决策摘要

1. 正式探索产物升级为精简 Schema 4.0。
2. 页面产物只保留 `page/objects/states/elements/collections/transitions/quality`。
3. 原始 snapshot、trace、日志和合并历史留在 run 目录。
4. 新增唯一项目级共享文件 `exploration-coverage.yaml`。
5. 覆盖粒度为 page、state 和 `element_key:action`。
6. 覆盖状态保持最小集合：页面 `complete/partial`，state/action `completed/pending`。
7. 自主探索和 Loop 探索共同读写 coverage。
8. Loop 在 frontier enqueue 前过滤 completed action。
9. 自主探索通过精简覆盖摘要避免重复探索。
10. 只有执行并验证成功的 action 才能标记 completed。
11. 用户通过 `force_reexplore` 显式重新探索。
12. 不引入指纹、有效期、自动失效、复杂环境维度或新数据库表。
13. 本次不改详细测试用例和 UI 自动化测试生成。
14. 重复卡片按“类型 + 状态”分组，每组只探索一个代表项；按钮不同时才补充探索。
