# 页面探索 - 嵌套 State 树 + 触发链设计 Spec

**项目**: 基于 Playwright CLI + LangChain 的页面探索功能
**创建日期**: 2026-07-04
**最后更新**: 2026-07-04
**版本**: 2.1
**状态**: ✅ 已实施并通过验证

**前置文档**:
- `docs/superpowers/specs/page-exploration-complete-spec.md`（v1.4，现状）
- `docs/superpowers/specs/2026-07-01-page-exploration-minimal-contract-cleanup-spec.md`（已执行的清理）

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [核心问题与设计决策](#2-核心问题与设计决策)
3. [嵌套 State 树 Schema](#3-嵌套-state-树-schema)
4. [触发链设计 triggered_by](#4-触发链设计-triggered_by)
5. [合并算法与状态判定](#5-合并算法与状态判定)
6. [Agent Tool 与运行时契约](#6-agent-tool-与运行时契约)
7. [事件流与契约](#7-事件流与契约)
8. [删除旧产物与配置迁移](#8-删除旧产物与配置迁移)
9. [目录与文件布局](#9-目录与文件布局)
10. [测试计划](#10-测试计划)
11. [验收标准](#11-验收标准)
12. [非目标与后续候选](#12-非目标与后续候选)
13. [更新日志](#13-更新日志)

---

## 1. 背景与目标

### 1.1 现状

`page_exploration` 模块当前在项目级 `pages/page-*.yaml` 中使用**扁平**的 `states: [...]` 结构记录每页可见元素：

```yaml
# 现状（要被删除的旧结构示意）
page:
  id: "page-001"
  title: "智能体工作台"
  normalized_path: "/workspace/agents"
states:
  - id: "default"
    type: "page"
    title: "智能体工作台 - 默认状态"
    elements:
      - id: "create_agent_btn"
        ...
      - id: "type_select_dialog"
        ...
```

> 数据来自 `2026-06-26-page-exploration-playwright-cli-langchain-spec.md` 第 4.5 节 Schema 定义。

### 1.2 暴露的问题

1. **无层级，弹窗、抽屉、嵌套表单全部摊在 root `default` state 的 `elements` 数组里**，无法表达"这是工作台 → 点创建按钮 → 出来的弹窗里才有创建表单"这种语义。
2. **无触发链**：看不到某个 state / element 是从哪个 state 的哪个元素触发的。一旦下游用 state 树生成测试用例，路径不明确。
3. **跨 run 合并不可信**：没有 `state.id`、`triggered_by` 这种稳定键，"同一个弹窗第二次出来"靠 YAML 解析或字符串匹配来比对，结果飘忽。
4. **扁平结构鼓励覆盖式重写**：下游实现为了"刷新"一个 state，往往整页重写，丢失其它 state 元素。
5. **重复元素难去重**：没有稳定的 element-level 标识，新旧两次跑的元素 diff 没有清晰边界。

### 1.3 目标（按优先级）

1. **支持嵌套 state 树（单 page yaml 内）**：每页产物是一个文件，state 在文件内以 `state.children[]` 嵌套表达——这正是用户口中的"树形结构层级"。弹窗、抽屉、表单组件这种**嵌套包含关系**必须能在 yaml 文件结构上自然呈现。
2. **支持触发链 `triggered_by`（对元素，不对 state）**：每个非根 state 记录"从哪个直接父 state 出发、点了哪个元素、URL 是否变化"，完整可追溯。
3. **支持跨 run、跨环境的稳定合并**：`state.id` 全局稳定，同 id 出现 → 补字段；新 id 出现 → 加入。元素层同理。
4. **变更最小**：保留现有 page 产物文件位置（`data/projects/{project_id}/page_exploration/pages/page-*.yaml`）、保留 API 形态、保留事件总线，不重做执行链路。
5. **绝不做隐式向后兼容**：旧 schema 直接删除，配置/产物迁移到新 schema 是独立 spec。

### 1.4 非目标（**强制约束**）

| 不做什么 | 原因 |
|---|---|
| ❌ **不**给每个 state 单独拆独立 yaml 文件 | 用户决策（2026-07-04 13:54 评审确认）：保持 page 单 yaml，所有 state 树写入同一文件 |
| ❌ **不**把 `state.elements` 拆出去成 element-level yaml | 同上：元素写入所属 state 的 `elements` 数组 |
| ❌ **不**做旧 yaml 自动迁移 / 自动包一层 | 用户明确要求：旧产物直接删除，无迁移 |
| ❌ **不**保留旧扁平 `states: [...]` 兼容路径 | 旧 schema 整体删除 |
| ❌ **不**保留为兼容而存在的旧代码/旧字段 | spec 实施时必须删除关联的死代码 |
| ❌ **不**限制嵌套层数 | 用户决策：无上限，靠 agent 探索深度自收敛，16 层硬上限作为安全护栏 |
| ❌ **不**支持跨祖父级的 `triggered_by` | 用户决策：只能指直接父 state，禁止跨级 |
| ❌ **不**支持 `state` 维度的 `triggered_by`（即不让某 state 触发某 state） | 用户决策：触发只记录元素层级 |
| ❌ **不**生成测试用例 | 留给下游 spec |
| ❌ **不**做删除元素的操作（保留历史） | 历史观察的所有元素必须一直在产物里 |
| ❌ **不**进 toast / snackbar / 非阻塞通知 | 它们触发后会自动消失，纳入将造成 state 抖动 |
| ❌ **不**支持登录态注入、iframe 跨域、验证码 | 独立特性，本轮范围之外 |
| ❌ **不**自动为用户数据列表行派生 state（如每行一个 row state） | 元素可加，state 不增 |
| ❌ **不**推断"页面类型"成强语义（`form / list / table / wizard`） | `state.type` 仅 `page / dialog / drawer / form / list` 五种，且必须基于 DOM 实读 |

---

## 2. 核心问题与设计决策

### Q1. 一页到底是一个 yaml 还是多个 yaml？

**决策**：**一个 page 一份 yaml，state 树以 `state.children[]` 嵌套在该文件内**。

```text
pages/page-{normalized_slug}.yaml     (一份文件，state tree 以 yaml 数组嵌套)
```

- 这就是用户要的"树形结构层级"：树形在**单文件内**表达，不是每 state 一份 yaml
- 跨 run 合并边界清晰：文件级锁 + 顺序 read-modify-write
- 前端展示天然按页聚合，不用 join 多文件
- git diff 友好：state 树增长只追加同一文件末段，不散到多文件

### Q2. state 是扁平行还是嵌套树？

**决策**：**嵌套树**。`page.states` 数组中每个 state 可以有 `children: []`，每条 child 也是 state。树的根是页面本身的 "root" state。

理由：弹窗、抽屉、表单容器天然是嵌套结构。扁平虽实现简单但下游用不起。

**约束**：元素 (`state.elements[]`) 写在 state 内，**不**拆成独立 yaml——所有产物聚拢在 `pages/page-*.yaml` 这一个文件树里。

### Q3. 触发关系记在哪里？

**决策**：每个**非根** state 都带，且只记录**元素层级**的触发（不对 state 记触发）：

```yaml
triggered_by:
  from_state: "page-001__page_root_001"
  element_key: "create_agent_btn"
  action: "click"
  url_changed: true
  observed_url: "/workspace/agents?dialog=create"
```

- `from_state` 必须等于**直接父 state.id**（不允许跨祖父级）
- `element_key` 是触发元素的稳定 key（详见 Q5）
- `observed_url` 记录触发后页面真实 URL（即使前端没路由变化也要记）
- 根 state **不**带 `triggered_by`

### Q4. state.id 怎么生成才全局稳定？

**决策**：使用**模板生成 id**，agent **不参与命名**，避免 LLM 起名漂移。

模板：

```text
{page_id}__{type}__{seq3}
```

- `page_id`：从 `page.id`（稳定 ID）传入
- `type`：`root / dialog / drawer / form / list`（与 `state.type` 取值一致）
- `seq3`：0 填充 3 位序号，按 state 在 `page.states` 数组里出现的顺序分配，跨 type 不互相串号（即 dialog 自己数到 001，form 自己数到 001）

命名规则：

| 序号池 | 谁占用 | 例 |
|---|---|---|
| 0、1、2... | root state 的第一个 | `page-001__root__001` |
| root 之后每个 state | 按 `states` 数组顺序分配，**先到先得** | `page-001__dialog__001`, `page-001__form__001`, `page-001__dialog__002` |
| child state | 用同样模板（seq3 在**整页**内单调递增） | `page-001__dialog__001__form__002` |

> **简化（实施备选）**：如果觉得 `page-001__dialog__001__form__002` 太冗长，可以只对**顶层** state 使用模板生成，**子 state** 命名为 `{parent.state.id}__{type}__{seq3}`。最终在 plan 阶段定稿。

### Q5. element_key 怎么生成才稳定？

**决策**：element_key = `f"{role}-{name-slug}"`：

- **DOM 实读字段**：`role`、`name`、`aria-label`
- **`inferred` 标**记：`label / placeholder / test_id / text`（LLM 推断或 DOM 中可以弱信号找到的）
- **slug 规则**：lowercase + 把非 `[a-z0-9]` 替换成 `-` + 折叠连续 `-` + 去掉首尾 `-`，最长 40 字符
- **冲突处理**：同 state 内出现相同 `element_key`，后到的用 `-2 / -3` 后缀区分，但只在同 state 内的元素列表里递增，**不**影响其它 state
- **`unstable` 标记**：纯靠 `text` / CSS 类名推断的、用 `unstable: true` 标，下次合并不主动用其做判定依据

例：

```yaml
elements:
  - key: "button-create-agent"
    source:
      role: "button"
      name: "创建智能体"
      aria_label: "创建按钮"
    inferred: false
  - key: "input-search"
    source:
      role: "textbox"
      label: "搜索"
      placeholder: "请输入智能体名称"
    inferred: true   # placeholder 视为推断
```

### Q6. 合并的边界在哪？谁负责？

**决策**：**单一入口**。新增 `PageArtifactWriter.merge_states(...)`，所有"追加 state / element"动作都走它，包括旧 `artifact_write_tool`（保留 ID、签名扩展）。

接口：

```python
@dataclass
class MergeResult:
    added_state_ids: list[str]
    updated_state_ids: list[str]
    added_element_keys: list[str]
    updated_element_keys: list[str]
    skipped_due_to_lock: bool = False

class PageArtifactWriter:
    def merge_states(
        self,
        page_id: str,
        run_id: str,
        observed_states: list[NewStateObservation],  # 新观察到
    ) -> MergeResult:
        ...
```

- **文件级互斥锁**（`fcntl.flock`），**acquire 阶段**等待 5s，超时返回 `skipped_due_to_lock=True`，已 acquire 后 read-modify-write 阶段不受同一锁的二次等待影响
- **顺序 read-modify-write**：永远不会写到一半的状态
- **幂等保证**：相同输入的 `observed_states` 重复调，state/element **不**增加
- **冲突策略**：见 §5.5

### Q7. 已探索 URL 检查怎么演进？

**决策**：保留 `explored_urls.yaml`，但其角色**仅限循环检测**（不阻止重跑）。新增 `check_explored_url_tool` 返回 `(explored, has_state_tree)` 二维：

| `explored` | `has_state_tree` | 含义 | Agent 行为 |
|---|---|---|---|
| False | False | 未探索过 | 全量探索 |
| True | False | 旧 yaml，**没有嵌套结构** | spec 第 8 节定义行为：跳过或重探（见下） |
| True | True | 已探索过且有新结构 | **不**阻止，agent 可以再 explore 触发新的合并 |
| False | True | 不可能出现 | 报错 |

> **实施严格性**：因为用户明确不迁移，任何 `has_state_tree=False` 的旧 yaml **必须**被视为该 page 从未探索过，触发重新探索。Agent 不会读旧 yaml。

### Q8. agent 是否能删除元素？

**决策**：**永远不能删除元素**。仅能"添加"和"补字段"。
- 元素消失后 yaml 仍保留记录 + `last_seen_at` 时间戳
- 该元素**不**计入"当前可见元素"
- 这是 spec 写明的硬约束，artifact writer 不提供删除接口

### Q9. toast / snackbar / 计时自动关闭类元素怎么处理？

**决策**：明确**不进入** state 树。

- DOM 检测 + Playwright 快照后，由工具/中间件过滤
- 过滤规则（agent tool 入参侧校验 + 提取工具侧都遵守）：
  - 角色 `status / alert` 且**没有** `data-static="true"`、`role="dialog"`、`aria-modal="true"`
  - DOM 路径位于 `#root > toast-container / .ant-message / .ant-notification` 等已知容器
  - timeout <= 5s 的非阻塞提示（实施时维护一个小名单）

### Q10. 跨 run 元素的"是否新增"如何判定？

**决策**：

- 一个 element 的 `key` 在 state 内**未出现过** → 新增
- 出现过但字段为 null → 补字段
- 字段值已存在但不同 → **保留先到值**，但记录 `conflicts` 字段（每元素一项，记录"后来观察到但不采纳的字段值"），便于调试
- 同 key 完全相同 → 静默跳过

> **不做** "新版本覆盖旧版本" 的合并策略。保留先到为强一致。

---

## 3. 嵌套 State 树 Schema

### 3.1 完整 yaml 示例

```yaml
schema_version: "2.0"
page:
  id: "page-workspace-agents"
  title: "智能体工作台"
  normalized_path: "/workspace/agents"
  url: "https://test.example.com/workspace/agents"
  observed_url: "/workspace/agents"
  screenshot: "screenshots/page-workspace-agents.png"
  first_observed_at: "2026-07-04T10:00:00Z"
  last_observed_at: "2026-07-04T10:15:00Z"
  observed_by_runs:
    - run-001
    - run-002

states:
  - id: "page-workspace-agents__root__001"
    type: "root"
    title: "智能体工作台 - 列表状态"
    triggered_by: null
    depth: 1
    last_observed_at: "2026-07-04T10:15:00Z"
    observed_by_runs:
      - run-001
      - run-002
    dom_signature: "sha256:5e7c..."
    elements:
      - key: "button-create-agent"
        source:
          role: "button"
          name: "创建智能体"
        inferred: false
        last_seen_at: "2026-07-04T10:15:00Z"
        seen_count: 12
        children: []

      - key: "input-search-agent"
        source:
          role: "textbox"
          label: "搜索"
          placeholder: "搜索智能体"
        inferred: true
        last_seen_at: "2026-07-04T10:15:00Z"
        seen_count: 5
        children: []

    children:
      - id: "page-workspace-agents__dialog__001"
        type: "dialog"
        title: "选择创建类型"
        triggered_by:
          from_state: "page-workspace-agents__root__001"
          element_key: "button-create-agent"
          action: "click"
          url_changed: false
          observed_url: "/workspace/agents"
        depth: 2
        last_observed_at: "2026-07-04T10:15:00Z"
        observed_by_runs:
          - run-001
        dom_signature: "sha256:8a3f..."
        elements:
          - key: "button-create-autonomous"
            source:
              role: "button"
              name: "自主规划"
            inferred: false
            last_seen_at: "2026-07-04T10:15:00Z"
            seen_count: 3
            children: []

          - key: "button-create-template"
            source:
              role: "button"
              name: "从模板创建"
            inferred: false
            last_seen_at: "2026-07-04T10:15:00Z"
            seen_count: 2
            children: []

        children:
          - id: "page-workspace-agents__form__001"
            type: "form"
            title: "新建智能体表单"
            triggered_by:
              from_state: "page-workspace-agents__dialog__001"
              element_key: "button-create-autonomous"
              action: "click"
              url_changed: true
              observed_url: "/workspace/agents?dialog=create&type=auto"
            depth: 3
            last_observed_at: "2026-07-04T10:15:00Z"
            observed_by_runs:
              - run-001
            dom_signature: "sha256:c1d4..."
            elements:
              - key: "input-agent-name"
                source:
                  role: "textbox"
                  label: "智能体名称"
                inferred: false
                last_seen_at: "2026-07-04T10:15:00Z"
                seen_count: 4
                children: []

              - key: "textarea-agent-description"
                source:
                  role: "textbox"
                  label: "智能体描述"
                inferred: false
                last_seen_at: "2026-07-04T10:15:00Z"
                seen_count: 4
                children: []

              - key: "button-submit"
                source:
                  role: "button"
                  name: "创建"
                inferred: false
                last_seen_at: "2026-07-04T10:15:00Z"
                seen_count: 1
                children: []

            children: []
```

### 3.2 Schema 字段约束

#### 顶层

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `schema_version` | 是 | string | 必须等于 `"2.0"` |
| `page.id` | 是 | string | 全局稳定，slug + uuid hash 都行 |
| `page.title` | 是 | string | 用户可见 |
| `page.normalized_path` | 是 | string | URL 归一化路径，和 v1.4 完全一致 |
| `page.url` | 否 | string | 最近一次观察到的完整 URL |
| `page.observed_url` | 是 | string | 等同于 `page.url`，但语义明确"这是观察到的事实"，实施时可去重 |
| `page.first_observed_at` | 是 | ISO datetime | 该页产物首次创建时间 |
| `page.last_observed_at` | 是 | ISO datetime | 最近一次合并时间 |
| `page.observed_by_runs` | 是 | list[string] | 累计观察到该页的 run_id |
| `page.screenshot` | 否 | string | 截图相对路径 |

#### `states`

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `states[]` | 是 | list[State] | state 数组，包含根 state（type=`root`），type 见 §3.3 |
| `state.id` | 是 | string | 模板生成，见 Q4 |
| `state.type` | 是 | enum | `root / dialog / drawer / form / list`，见 §3.3 |
| `state.title` | 是 | string | 人类可读 |
| `state.triggered_by` | 条件 | object\|null | **根 state = null；其它必须有**，见 §4 |
| `state.depth` | 是 | int | 嵌套层级（root=1，直系 child=2，依此类推），运行时使用，配合硬上限 16 做安全护栏 |
| `state.last_observed_at` | 是 | ISO datetime | 最近一次合并时间 |
| `state.observed_by_runs` | 是 | list[string] | 哪些 run 见过该 state |
| `state.dom_signature` | 是 | string | 哈希，用于"是否同一 state 实例"的快速判定 |
| `state.elements` | 是 | list[Element] | 该 state 顶层元素（递归） |
| `state.children` | 是 | list[State] | 嵌套子 state，可为空数组。**层数无理论上限**，受 16 层安全护栏约束 |

#### `elements`

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `element.key` | 是 | string | 稳定 key，见 Q5 |
| `element.source` | 是 | object | 实际观察到的字段集合（DOM 实读字段） |
| `source.role` | 条件 | string | DOM 实读则 `inferred=false`，LLM 推断则 `inferred=true` |
| `source.name` | 条件 | string | 同上 |
| `source.aria_label` | 条件 | string | 同上 |
| `source.label` | 推断 | string | 仅当 `inferred=true` |
| `source.placeholder` | 推断 | string | 仅当 `inferred=true` |
| `source.test_id` | 推断 | string | 仅当 `inferred=true` |
| `source.text` | 推断 | string | 仅当 `inferred=true` |
| `element.inferred` | 是 | bool | 整元素使用的定位字段是否全部实读 |
| `element.last_seen_at` | 是 | ISO datetime | 该元素最近被看到时间 |
| `element.seen_count` | 是 | int | 该元素累计被观察到的次数 |
| `element.children` | 是 | list[Element] | 嵌套子元素（如表单字段的 `<option>` 项，或 `select` 下的子节点） |

> **不存**：元素的绝对 XPath、ref、CSS 选择器字符串、动态 className、url path 等瞬态值。
> **存**：稳定的"语义定位字段集合"（role / name / aria / label / placeholder / testid / text）+ 推导出的 `key`。

### 3.3 state.type 取值

仅五种，且必须**来自 DOM 实读**：

| type | 实读依据 | 不应该从 LLM 推断 |
|---|---|---|
| `root` | 该页 URL 加载完毕后的初始状态 | 永远不推断 |
| `dialog` | DOM 含 `role="dialog"` 或 `aria-modal="true"` | 永远不推断 |
| `drawer` | DOM 含 `role="dialog"` + class 名命中"drawer" / `aria-label*=侧边` / 滑入式组件特征 | 永远不推断 |
| `form` | DOM 含 `<form>` 元素 | 永远不推断 |
| `list` | DOM 含 `role="list"` 或 `<ul>` / `<table>` 顶带 `role="rowgroup"` | 永远不推断 |

如果 agent 拿不准，**不写** `state.type`（即该 observation 不进树，进入"待定"队列，留给人审视），但 YAGNI 法则下本期**不做**待定队列，**直接丢弃** observation 并在事件流里发 `page_artifact_state_rejected`。

### 3.4 dom_signature

用于"这次观察到的 state 是否已经存在"的快速判定。

```python
def dom_signature(snapshot_dom: str, elements: list[Element]) -> str:
    # 1. 移除所有 ref / 动态 class / 时间戳 / uuid
    # 2. 保留 role + name + aria-label + stable testid
    # 3. sha256
    ...
```

约束：
- **不**依赖 ref、CSS、XPath、绝对路径
- **不**依赖瞬态文本（如 toast、时间、动态 banner）
- **应当**对"菜单加了一项 / tab 多一个"敏感（这类变化会被识别为新元素并合并到现有 state）

---

## 4. 触发链设计 triggered_by

### 4.1 契约

仅当 `state.type != "root"` 时存在。Schema：

```yaml
triggered_by:
  from_state: "page-workspace-agents__root__001"  # 该页 state 树内可解析的 state.id
  element_key: "button-create-agent"               # 触发元素在该 state 里的 key
  action: "click"                                  # click / fill / submit / navigate / hover / unknown
  url_changed: true                                # 是否 URL 发生显著变化（规范化后判断）
  observed_url: "/workspace/agents?dialog=create"  # 触发后立刻观察到的 URL
```

### 4.2 规则

1. **`from_state` 必须可解析**到该 yaml 中某个 state.id。如果解析不到，**拒绝**整个 observation（agent 端和 writer 端都校验）。
2. **`from_state` 必须等于直接父 state.id**（不允许指向祖父级、叔级等跨级）。违反者**拒绝**整个 observation。**理由**：跨级触发语义模糊（如：dialog 里点出来的元素，到底是 dialog 内的还是 dialog 父页面里的？强制单层避免歧义）。
3. **`element_key` 必须可解析**到 `from_state.elements` 中某元素。如果解析不到，**拒绝**整个 observation。
4. **`action` 仅取白名单**：`click / fill / submit / navigate / hover / unknown`。
5. **`url_changed` 判定**：触发前 `from_state` 所属的 root state 的 `observed_url` 与触发后的 `observed_url` 做规范化比对（去除 hash、不区分 query 顺序），不等则为 true。
6. **`observed_url` 必须**是触发后的 URL；如果快照获取失败导致 URL 不可知，记为 `"unknown"`。

### 4.3 链的可达性

- 根 state 没有 `triggered_by`
- 任何非根 state 的 `from_state` 必须指向其**直接父 state**（§4.2 第 2 条）
- 嵌套层数**不设上限**，由 agent 探索深度决定
- **断言**：从任何 state 出发，重复取 `triggered_by.from_state`，应在 ≤ 当前 state 嵌套层数跳内到达根 state

### 4.4 父子关系 vs 触发关系

state 树本身就是嵌套结构，`state.children[]` 表示**当前观察到的嵌套可见性**。

`triggered_by` 是"这个嵌套是**怎么**来的"。两者可以独立：

- 弹窗 A 被点开 → 弹窗 A 的 children 是它内部显示的内容
- 弹窗 A 关闭 → 弹窗 A 的 children 内容**仍保留在 yaml**，但下次再观察时如果没出来，children 列表中元素 `last_seen_at` 不更新（`seen_count` 也不增加）
- **不会**因为子 state 关闭而删除它，更不会删除 state 自己

`triggered_by` 也类似：**永远不会被清空或重写**。它就是历史日志。

---

## 5. 合并算法与状态判定

### 5.1 输入

```python
@dataclass
class NewStateObservation:
    """一次新的观察 - 一个完整 state 树（root + 子 state + 子 state...）。"""
    page: PageIdentifier
    parent_path: list[str]                      # 用于"嵌套层"提示；实际靠 triggered_by 解析
    states: list[StateSnapshot]                 # 至少含一个 root state
    observed_url: str
    observed_at: str                            # ISO datetime
    run_id: str

@dataclass
class StateSnapshot:
    type: str                                   # root / dialog / drawer / form / list
    title: str
    dom_signature: str
    triggered_by: TriggeredBy | None            # None 表示 root
    elements: list[ElementSnapshot]
```

### 5.2 判定流程

```text
check_explored_url_tool return (explored, has_state_tree)
  ↓
  if not has_state_tree（脏旧数据/不存在）→ 全新建文件（lock + write）
  if has_state_tree → 走 merge_states
```

```text
merge_states(observed_states):
  1. acquire lock (5s 超时)
  2. read yaml
  3. for each observed state:
       a. by triggered_by.path 或 signature 找匹配 state.id
          - 命中 → 合并 elements + 更新 last_observed_at / seen_count
          - 未命中 → 分配新 state.id（模板生成）
  4. for each 新 element:
       a. by key 在 state.elements 中找匹配
          - 命中 → 补字段（先到优先冲突策略见 §5.5）
          - 未命中 → 追加
  5. write yaml
  6. release lock
  7. return MergeResult
```

### 5.3 关键决策表

| 场景 | 行为 |
|---|---|
| 文件不存在 | **新建** yaml（新 schema），**不**写旧兼容层 |
| 旧 yaml（无 `schema_version`）被 reader 遇到 | 视为"该 page 从未探索过"，**不**尝试解析元素，进入重探流程（见 §8） |
| yaml 文件存在但**解析失败**（格式损坏、空文件、IO 异常） | reader 失败视为不存在，**全量重建**新 schema，并发 `page_artifact_yaml_corrupt` 事件（见 §7.4） |
| 锁竞争 5s 超时 | 返回 `skipped_due_to_lock=True`，**不**改文件，发 `artifact_lock_timeout` 事件 |
| 同 `state.id` 重复观察 | state 数量不变；仅更新 `last_observed_at`、`seen_count`、`observed_by_runs`（追加 run_id），元素按 §5.5 合并 |
| 完全不同 dom_signature 但同 state.id | **冲突**，按 §5.5 处理 |
| 新 dom_signature 但无触发链可达 | 拒绝该 observation，发 `page_artifact_state_rejected` 事件 |

### 5.4 "新 state" vs "已有 state"

按以下顺序尝试定位现有 state：

1. `state.id` 精确匹配 → 直接命中
2. `state.triggered_by.from_state + element_key` 命中（同一父 state 同一元素触发） → 检查 `dom_signature`：
   - 一致 → 是同一个 state，命中
   - 不一致 → 当成"状态变化"，按 §5.5 冲突处理
3. 都未命中 → 创建新 state（分配新 id）

### 5.5 冲突策略（先到为强）

| 冲突类型 | 决策 |
|---|---|
| 元素 key 重复出现，新观察字段为 null | 保留原值 |
| 元素 key 重复出现，新观察字段为非 null 但与原值不同 | **保留原值**，记录到该元素的 `conflicts` 列表：`{run_id, observed_at, attempted_value}` |
| state `dom_signature` 不同但 `state.id` 命中 | **保留原 dom_signature**，记录到 state 的 `conflicts` 列表 |
| `observed_by_runs` 新增 | 追加到列表，**重复 run_id 跳过**（保持列表内元素唯一） |
| `seen_count` | 原子 +1 |
| `last_seen_at` / `last_observed_at` | 更新为更晚者（取 max） |

永不删除、永远不用"后来版本覆盖先前版本"。先到为强 = 跨 run 一致性的基础。

### 5.6 嵌套层数与 N 跳可达性

- **嵌套层数不设上限**（用户决策），由 agent 在 `page_exploration_skills / locator_best_practices` 的引导下决定探索深度
- §4.3 的可达性断言必须被测试覆盖
- 实施侧需要 capacity 校验：state 树深度的硬上限（如 16 层）作为**安全护栏**，超出即发 `page_artifact_state_rejected` 事件 + agent 端中止，避免 agent 死循环

---

## 6. Agent Tool 与运行时契约

### 6.1 工具清单

| Tool 名 | 用途 | 入参关键字段 | 出参关键字段 |
|---|---|---|---|
| `playwright_cli_*_tool` | 操控浏览器 | （已有，不变） | （已有） |
| `check_explored_url_tool` | URL 探测 | `normalized_path: string` | `{explored: bool, has_state_tree: bool}` |
| `read_page_artifact_tool` | 读取整页 yaml | `page_id: string` | `{exists: bool, page: PageArtifact\|None, schema_version: string\|None}` |
| `merge_page_artifact_tool` | 追加合并 observation | `page_id`, `observed_states: [NewStateObservation]` | `{added_state_ids, updated_state_ids, added_element_keys, updated_element_keys, skipped_due_to_lock}` |
| `cache_lookup_tool` | 兼容性保留 | 兼容 v1.4 入参 | 转调 `check_explored_url_tool` |

> **删除** 旧 `artifact_write_tool`（被 `merge_page_artifact_tool` 完全取代）。
> **删除** 旧 `cache_write_tool` / `update_cache_index_tool`（已被 §6.2 替代）。

### 6.2 Tool 边界 / 校验

`merge_page_artifact_tool` 必须做入参校验：

| 校验 | 失败行为 |
|---|---|
| 缺 `triggered_by`（非根 state） | 报错，整个 observation 被拒，发 `page_artifact_state_rejected` 事件 |
| `from_state` 解析不到 | 同上 |
| `from_state` 不等于直接父 state.id（跨级触发） | 同上，reason: `triggered_by_from_state_not_parent` |
| `element_key` 解析不到 | 同上 |
| `state.type` 不在白名单 | 同上 |
| `dom_signature` 为空 | 同上 |
| `state.depth` 超过 16（硬上限） | 同上，reason: `depth_exceeds_safety_limit` |
| 同时收到 root + 没有 triggered_by | 允许（这是合理的入口观察） |

### 6.3 Agent 系统提示要点

```text
- 每观察到一个新 state，必须填齐 type / title / triggered_by / depth / elements
- root state 是页面初始状态（depth=1）；其它 state 必须有 triggered_by
- triggered_by.from_state 只能填**直接父 state.id**，不准跨祖父级、叔级；如果不确定是不是直接父，不要瞎编，整 observation 丢弃
- 找不到 triggered_by 来源（可能截断了），不要瞎编，整 state observation 丢弃
- 元素必须按 role / name / label 顺序填 element.source；纯文本猜测的字段标 inferred=true
- 不要使用 css / ref / xpath，只用语义定位字段
- 不要因为"看着像菜单项"就强行把 menu item 当成 state
- 历史元素（上次看到这次没看到）不要从产物里删，下游会用 seen_count / last_seen_at 判断
- state 嵌套深度超过 16 时停止探索，立即汇报
```

---

## 7. 事件流与契约

### 7.1 既有事件保留

沿用既有 event 总线（`RunEventBus`）。既有事件（参考 `2026-07-01-page-exploration-minimal-contract-cleanup-spec.md` 第 6 章）保持不变：

```text
run_snapshot
run_completed
run_failed
run_cancelled
error
agent_thought
agent_tool_started
agent_tool_completed
agent_tool_failed
agent_plan_updated
```

### 7.2 新增事件

只新增**三个**，且都**与 artifact 合并动作直接相关**：

```yaml
type: "page_artifact_state_merge"
run_id: "run-001"
occurred_at: "2026-07-04T10:15:00Z"
payload:
  page_id: "page-workspace-agents"
  normalized_path: "/workspace/agents"
  added_state_ids: ["page-workspace-agents__dialog__001"]
  updated_state_ids: ["page-workspace-agents__root__001"]
  added_element_keys: ["button-create-template"]
  updated_element_keys: ["button-create-agent"]
  trigger: "click:button-create-agent"
```

```yaml
type: "page_artifact_lock_timeout"
run_id: "run-001"
occurred_at: "2026-07-04T10:15:00Z"
payload:
  page_id: "page-workspace-agents"
  waited_seconds: 5.0
```

```yaml
type: "page_artifact_state_rejected"
run_id: "run-001"
occurred_at: "2026-07-04T10:15:00Z"
payload:
  page_id: "page-workspace-agents"
  reason: "triggered_by_from_state_unresolved"  # enum
  rejected_state_title: "新建智能体表单"
```

（`page_artifact_yaml_corrupt` 事件见 §7.4）

### 7.3 事件消费

| 事件 | 前端消费 | 后端存储 |
|---|---|---|
| `page_artifact_state_merge` | 可选：用于右上角"产物实时增长"提示 | 写入 `events.jsonl` |
| `page_artifact_lock_timeout` | 作为 warning 提示 | 写入 `events.jsonl` |
| `page_artifact_state_rejected` | **不**展示给用户 | 写入 `events.jsonl` + 触发告警（实施细节可省） |

### 7.4 异常事件

```yaml
type: "page_artifact_yaml_corrupt"
run_id: "run-001"
occurred_at: "2026-07-04T10:15:00Z"
payload:
  page_id: "page-workspace-agents"
  file_path: "data/projects/{project_id}/page_exploration/pages/page-workspace-agents.yaml"
  reason: "yaml_parse_error"   # 或 io_error / empty_file / schema_mismatch
  action: "rebuild_from_scratch"
```

消费：写入 `events.jsonl`；可选触发轻量告警（实施细节），**不**展示给用户。

---

## 8. 删除旧产物与配置迁移

### 8.1 强制规则

**用户明确决策**：**删除旧产物，不迁移**。

- 旧 schema yaml（无 `schema_version` 或 `schema_version < 2.0`）**直接删除**，**不**做自动包一层兼容
- 旧 schema reader 代码**直接删除**，**不**保留 graceful fallback
- 测试 fixtures、fake page yaml **一并更新**为新 schema
- 旧 schema 注释、文档、示例 yaml 文件 **全部删除**

### 8.2 实施时一次性清理动作

1. `find` / `rg` 全仓搜索下列关键字，定位所有受影响位置：
   - `states:`（在 page yaml 顶层）
   - `state.id` / `states[].id`
   - `state.type` 中含 `page / default`
   - `cache_index.yaml`
   - `artifact_write_tool`
   - `cache_write_tool`
2. 删除：
   - 旧 yaml schema 的 reader / writer
   - 旧 tool 函数 + system prompt 提及
   - 引用旧工具的 agent 系统提示段落
   - 测试 fixture
3. 新增：
   - 新 schema 的 reader / writer
   - §6.1 列出的工具（删除旧 `artifact_write_tool`）
   - 新 schema 的测试 fixture
4. 不需要"转换旧 yaml 到新 yaml"脚本——它们会被自然覆盖

### 8.3 配置 / 运行期参数迁移

- 旧配置项（如 `cache_ttl_seconds`）在 v1.4 已经废弃，本 spec **不再保留**任何历史配置项
- 新配置项（如锁等待时间，**默认 5s**）写入项目配置中心
- **不**做配置兼容层

### 8.4 前端

- 探索详情页如果对 state 做了旧结构假设（`states: [...]`），**更新**前端组件展示新树结构
- 不展示旧字段，但**不**写"for 旧版本兼容"的判断

---

## 9. 目录与文件布局

### 9.0 文件归属原则（2026-07-04 评审确认）

- **page 单 yaml**：每个 page 一份 yaml，state 树**完全**写在 `pages/page-*.yaml` 这一个文件内，以 `states[]` / `state.children[]` 嵌套
- **state 树不拆为独立文件**：本轮**不**引入 `pages/page-xxx/states/state-yyy.yaml` 这种二级拆分
- **elements 跟着 state**：elements 写在 `state.elements[]` 数组下，不拆出 element-level yaml

### 9.1 文件位置（沿用）

```text
apps/backend/
├── app/
│   ├── agents/
│   │   └── page_exploration/
│   │       ├── agent.py
│   │       ├── schemas.py
│   │       ├── service.py
│   │       ├── skills/
│   │       │   ├── page_explorer/
│   │       │   └── locator_best_practices/
│   │       ├── tools/
│   │       │   ├── playwright_tools.py        # 不变
│   │       │   ├── url_tools.py               # NEW: check_explored_url_tool
│   │       │   ├── artifact_tools.py          # MODIFIED: 删除旧 artifact_write, 新增 read_page_artifact + merge_page_artifact
│   │       │   └── runtime_context.py
│   │       └── prompts/
│   │           └── system_prompt.py
│   │
│   └── services/
│       └── page_exploration/
│           ├── orchestrator.py
│           ├── artifact_service.py            # MODIFIED: 删除旧 write 接口, 只暴露 PageArtifactWriter
│           └── project_pages_service.py
│
├── data/
│   └── projects/
│       └── {project_id}/
│           └── page_exploration/
│               ├── pages/                     # MODIFIED: yaml 内容全部 v2.0
│               │   └── page-workspace-agents.yaml  # ★ 仅这里装着一整棵 state 树
│               │
│               ├── explored_urls.yaml
│               │
│               └── runs/
│                   └── {run_id}/
│                       ├── run.yaml
│                       ├── discovered_pages.yaml
│                       └── ...
```

> 所有产物聚拢在 `pages/page-*.yaml`，**没有** `states/` 子目录、**没有** `elements/` 子目录。这是用户 2026-07-04 13:54 评审的明确决定。

### 9.2 模块添加

| 模块 | 文件 | 作用 |
|---|---|---|
| `PageArtifactWriter` | `apps/backend/app/services/page_exploration/page_artifact_writer.py` | 单一入口的文件级写（含锁，针对**单文件** `page-*.yaml`） |
| `dom_signature` | `apps/backend/app/agents/page_exploration/utils/dom_signature.py` | 哈希工具 |
| `state_id` | `apps/backend/app/agents/page_exploration/utils/state_id.py` | 模板生成器 |
| `element_key` | `apps/backend/app/agents/page_exploration/utils/element_key.py` | slug 化 + 冲突处理 |
| `toast_filter` | `apps/backend/app/agents/page_exploration/utils/toast_filter.py` | 过滤 toast / snackbar |

> 上述模块 **都必须**有单元测试覆盖。

---

## 10. 测试计划

### 10.1 单元测试（必须）

| 范围 | 必测用例 |
|---|---|
| `PageArtifactWriter.merge_states` | 幂等矩阵：同输入重复调，state 数不变；元素 key 重复，元素数不变，字段被补；锁超时 mock，文件未变，MergeResult 标识失败；新 schema 创建；冲突策略（先到为强，记录到 `conflicts`） |
| `dom_signature` | 不依赖 ref；同一内容稳态相同；改文本改字段 → 变；仅 className 改 → 不变（除非 role/aria 变）；大 yaml 不退化（性能） |
| URL 归一化 | query 区分 / hash 不区分 / fragment 区分 |
| `state_id` 模板 | 模板生成正确；seq3 编号正确；跨 type 不串号 |
| `element_key` slug | lowercase / 非字符替换 / 连续 `-` 折叠 / 长度截断 / 同 state 冲突 `-N` 后缀 |
| `toast_filter` | 已知容器剔除；`role="status"` + `role="alert"` + 5s timeout 识别；`role="dialog"` 不剔除 |
| Pydantic schema 校验 | `triggered_by` 必填（非根）；`state.type` 白名单；`source.*` 字段类型 |

### 10.2 Tool 层测试

| Tool | 必测 |
|---|---|
| `merge_page_artifact_tool` | 入参校验：缺 `triggered_by`（非根）报错；`from_state` 解析不到报错；`from_state` 不等于直接父（跨级）报错，reason `triggered_by_from_state_not_parent`；`element_key` 解析不到报错；state.type 越界报错；depth > 16 报错，reason `depth_exceeds_safety_limit` |
| `read_page_artifact_tool` | 不存在返回 `exists=False`；存在返回完整树 |
| `check_explored_url_tool` | 二维化四种组合均符合预期；旧 schema 必须 `has_state_tree=False` |

### 10.3 Agent 集成测试（**至少 4 个 case**，必须可重复）

1. **单页单弹窗**：进入工作台 → 点创建按钮 → 出类型选择弹窗 → 弹窗里有 2 个按钮（自主规划 / 模板）→ 关闭。
   - 断言：yaml 包含 root + dialog 共 2 个 state，dialog 的 `triggered_by.from_state == root.id`，`element_key == "button-create-agent"`，`url_changed == false`。
2. **嵌套弹窗（双层）**：进入工作台 → 点创建 → 出类型选择 → 选"自主规划" → 出表单弹窗（URL 加 query）→ 关闭。
   - 断言：3 层 state 结构；每层 `triggered_by.from_state` 指向上一层根 state；最深层 `url_changed == true`、`observed_url` 包含 `dialog=create&type=auto`。
3. **跨 run 合并幂等**：运行 case 1，跑两次，第二次跑前**人工把第一次的 elements count +1**（模拟新版本）。
   - 断言：第二次调 `merge_states` 后所有原 state 都还在，state 数无新增；新元素被合并进现有 state；无重复 state；`conflicts` 列表里记录第二次尝试覆盖但未采纳的值。
4. **跨祖父级触发拒绝**：构造一个 observation，让孙子 state 的 `triggered_by.from_state` 指向祖父（不是父）。
   - 断言：observation 被拒，事件流出现 `page_artifact_state_rejected`，reason `triggered_by_from_state_not_parent`，文件未被损坏。
5. **超深嵌套护栏**：构造一棵 depth=17 的观察树。
   - 断言：observation 被拒，reason `depth_exceeds_safety_limit`，文件未被损坏。

### 10.4 端到端契约测试（**至少 2 个**）

1. **事件流差异**：
   - 订阅 RunEventBus
   - mock `merge_page_artifact_tool` 真实调一次
   - 断言：SSE 上先出现 `page_artifact_state_merge` 事件，`added_state_ids` 包含新 state.id
2. **并发写竞争**：
   - 两个并发线程对同一 page 调 `merge_states`
   - 断言：第二个等锁；锁 5s 超时后文件未变；事件流出现 `page_artifact_lock_timeout`

### 10.5 旧产物删除验证测试

- `rg` 旧关键字 `states:` `cache_index.yaml` `artifact_write_tool` 在最终代码中应**零命中**
- CI 跑 lint 配置正则规则作为门禁

### 10.6 回归测试

- 既有 `apps/backend/tests/agents/requirement_analysis/test_*.py` 不应受影响（不依赖 page_exploration）
- 既有 page_exploration 端到端 / contract 测试**必须**更新 fixture 走新 schema 才能保留

---

## 11. 验收标准

每条都必须可测：

- [x] 同一 url 跨 N 次 run 跑过后，state 树持续累积不丢失
- [x] 同 state 重复调 `merge_states` 不会产生重复条目（state 数不变）
- [x] 同 state 内同元素 key 重复不会产生重复元素（元素数不变）
- [x] **任意**嵌套层数下，`triggered_by.from_state` 链能从任何 state 回溯到根 state（≤ 当前 state 嵌套层数跳）
- [x] 嵌套深度超过 16 层（安全护栏）时发 `page_artifact_state_rejected`，文件不被损坏
- [x] `triggered_by.from_state` 指向祖父级 / 叔级 / 跨级 state 时，observation 被拒
- [x] toast / snackbar 不会出现在 state 树里（toast_filter 测试通过）
- [x] 用户数据列表的条目数变化**不**触发新 state；只触发元素合并到现有 state
- [x] 内置菜单项 / tab 的出现或消失**会**触发元素合并到现有 state
- [x] 元素的弱字段推断字段标 `inferred=true`
- [x] 锁 5s 超时后页面文件不变，事件流出现 `page_artifact_lock_timeout`
- [x] 旧 yaml 在 CI 全仓 grep 中**零命中**；首次发现旧 yaml 直接视为从未探索
- [x] 旧 tool 名 `artifact_write_tool` / `cache_write_tool` 在所有 Python 文件中**零命中**
- [x] `check_explored_url_tool` 在 `has_state_tree=False` 时**不**阻断 agent 重新探索
- [x] `dom_signature` 对纯 ref 变化不敏感；对 role / name / aria 变化敏感（构造 fixture 测试）

验证命令（2026-07-04）：

```bash
cd apps/backend
.venv/bin/python -m pytest tests/agents/page_exploration -q
```

结果：83 passed, 1 warning。

---

## 12. 非目标与后续候选

### 12.1 本轮不做（已说明外）

| 项 | 推后到 |
|---|---|
| 测试用例生成（基于 state 树 + triggered_by） | v3.0 独立 spec |
| 旧 yaml 全量迁移脚本 | 不做（用户决策：删除旧产物） |
| iframe / 跨标签 / 验证码 / 登录态注入 | 各自独立 spec |
| 视觉差异 / 截图比对 / 多浏览器并行 | 各独立 spec |
| 元素级可见性验证（Playwright eval count/visible） | 已决定不做（错误驱动即可） |

### 12.2 后续 spec 候选清单（仅供记录）

1. 测试用例生成（基于嵌套 state + triggered_by）
2. iframe 跨域探索
3. 登录态 / Cookie 注入
4. Playwright session 并发 / 多浏览器
5. 视觉差异告警
6. 对照真实用户路径自动生成 navigation graph

---

## 13. 更新日志

### v2.0（2026-07-04）🔥 **新 spec 起点**

**核心变更（相对 v1.4）**：

- ✅ 新增嵌套 state 树（`state.children[]`）
- ✅ 新增 `triggered_by` 触发链契约
- ✅ 新增 `PageArtifactWriter.merge_states` 单一写入口（替换覆盖式写）
- ✅ 新增 `state.dom_signature`、`element.inferred`、`state.type` 五种取值约束
- ✅ 新增三个事件类型（`page_artifact_state_merge` / `page_artifact_lock_timeout` / `page_artifact_state_rejected`）
- ✅ 新增 `check_explored_url_tool` 二维返回
- ✅ **删除** 旧扁平 `states: [...]` 兼容层
- ✅ **删除** 旧 `artifact_write_tool` / `cache_write_tool`
- ✅ **删除** 旧 yaml 自动包一层 / 自动迁移
- ✅ **删除** 旧 cache_index.yaml schema 相关实现（v1.4 状态是 `explored_urls.yaml` 仅供循环检测，本 spec 不保留多余兼容层）

**核心约束**：

- 先到为强（不覆盖、只累加）
- 永不删除元素 / state
- toast / snackbar 不过滤掉就失败
- `triggered_by` 缺一不可解析就拒整 observation

---

**文档版本**: 2.1
**最后更新**: 2026-07-04
**状态**: ✅ 已实施并通过验证

### v2.1（2026-07-04）— 评审对齐

**变更（相对 v2.0）**：

- ✅ 明确产物结构为 **page 单 yaml + 文件内嵌套 state 树**（用户决策：每 page 一份 yaml，state 在文件内以 `states[]`/`state.children[]` 嵌套；不拆 sub state yaml；elements 跟随 state 不拆 element-level yaml）
- ✅ 嵌套层数**不设上限**（用户决策），引入运行时字段 `state.depth` 追踪层数，16 层硬上限作为安全护栏
- ✅ `triggered_by.from_state` **只能指向直接父 state.id**（用户决策：禁止跨祖父级），新增校验 reason `triggered_by_from_state_not_parent`
- ✅ `triggered_by` 限定为**元素层级触发**（用户决策：不对 state 记触发）
- ✅ 新增集成测试 case 4（跨祖父级拒绝）和 case 5（超深嵌套护栏）
- ✅ §9.0 新增"文件归属原则"小节
