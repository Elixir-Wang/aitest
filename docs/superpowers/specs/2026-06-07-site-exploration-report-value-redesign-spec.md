# 站点探索报告价值化改造 Spec

## 背景

当前站点探索已经升级到 v2 结构化产物，能够生成：

- `run.yaml`
- `summary.yaml`
- `graph.yaml`
- `blockers.yaml`
- `pages/*.yaml`
- `checks/goal-validation.yaml`
- `reports/exploration-report.md`
- `logs/run.log`

但从现有站点探索产物看，报告存在一类通用的价值不足问题：

- 探索确实执行了 23 个页面/状态、55 个动作，但报告无法让人快速理解探索到什么。
- 多个页面都使用相同浏览器标题，无法区分目标模块列表页、对象详情页、关联资源页、筛选状态、创建入口等。
- 页面事实大量重复 `structure_summary`，阅读体验接近原始文本 dump。
- 页面关系表显示 `- -> -`，无法还原真实动作路径。
- `goal_validation` 为 `pending`，但报告仍给出“部分覆盖/部分可用”，可信度不足。
- 运行事实不一致，例如 `run.yaml` 的 `site_url` 为空，但日志和摘要中存在起始 URL。
- 动作失败存在于 `logs/run.log`，但没有进入 `blockers.yaml`、风险缺口或待确认事项。

这说明问题不只是 Markdown 模板，而是：

```text
页面观察事实缺少语义化
  -> summary 聚合不足
  -> graph 关系缺少可读映射
  -> goal validation 没有验收规则
  -> report 只能堆低层事实
```

本 spec 定义站点探索报告从“原始采集摘要”升级为“面向测试、产品、知识库维护的可执行探索结论”的改造方案。

## 目标

- 让探索报告能回答：
  - 本次到底覆盖了哪些业务能力。
  - 哪些入口、筛选、状态、详情页、弹窗、列表和流程已验证。
  - 哪些动作失败、未验证、越界或需要人工确认。
  - 下游知识库、测试用例、UI 自动化能不能使用本次探索结果。
- 在不把报告变成事实源的前提下，提高报告的可读性和决策价值。
- 增强结构化事实源，使报告可从 `pages/*.yaml`、`graph.yaml`、`summary.yaml`、`blockers.yaml` 稳定派生。
- 修复当前报告生成中的字段映射、空字段和重复内容问题。
- 支持自然语言目标拆解成可执行验收清单。
- 明确探索失败、动作失败、越界访问和目标未验证时的报告状态。

## 非目标

- 不把报告作为知识库正文。
- 不把报告作为测试用例生成的主事实源。
- 不让报告生成器凭空补业务规则。
- 不在报告里粘贴完整 DOM、accessibility tree、locator、YAML 或日志。
- 不默认在生产环境执行写动作。
- 不通过前端伪造页面名、覆盖率或风险结论。
- 不一次性重写整个 Agentic Exploration Loop。

## 核心原则

```text
以结构化事实为源，以报告为派生总结。
以语义页面为单位，而不是以浏览器 title 为单位。
以业务能力聚合，而不是以原始页面快照堆叠。
以动作结果和目标验证定状态，而不是只看是否采集到页面。
以失败和缺口显性化为荣，以“无阻塞”掩盖失败为耻。
```

## 当前问题分析

### 1. 页面标题不可用

当前页面产物使用浏览器标题作为 `page.title`，导致同一站点下大量页面标题相同。

问题影响：

- 页面列表不可读。
- graph 节点不可读。
- 报告无法表达“目标模块列表页”“对象详情页”“关联资源页”等业务页面。
- 去重和覆盖统计失真。

改造方向：

- 新增语义标题字段，不替代原始标题。
- 语义标题从 URL、激活菜单、主区域标题、关键实体、页面状态共同推断。

示例：

```yaml
page:
  title: 示例系统
  semantic_title: 目标模块列表页
  page_kind: list
  active_module: 目标模块
  active_submodule: 对象列表
```

### 2. 页面事实没有分层

当前 `structure_summary` 混合了：

- 浏览器标题
- 元素数量
- 导航菜单
- 正文文本
- 业务对象
- 操作入口
- 状态文本

问题影响：

- 报告只能输出长文本。
- 无法稳定提取“字段、操作、状态、业务对象”。
- 后续知识库和测试用例生成会拿到噪声。

改造方向：

```yaml
business_summary:
  headline: 目标模块展示业务对象列表，支持筛选、搜索、导入和创建。
  business_objects:
    - 业务对象
  primary_actions:
    - 创建对象
    - 导入
    - 查看详情
    - 使用
    - 查看历史
  filters:
    - 类型
    - 范围
    - 状态
    - 排序
  observed_states:
    - 已发布对象
    - 空数据
    - 创建入口弹层
  key_entities:
    - 示例对象 A
    - 示例对象 B
```

### 3. Graph 字段映射错误

当前 `graph.yaml` 的 edge 使用：

```yaml
source: page-001
target: page-002
```

但报告生成读取：

```python
edge.get("from")
edge.get("to")
```

结果报告中跳转路径全部变成 `- -> -`。

改造方向：

- 报告生成读取 `source/target`。
- 用 `nodes` 映射 page id 到 `semantic_title`、`url`。
- edge 增加动作目标和动作结果摘要。

目标报告效果：

```md
| 起点 | 动作 | 目标 | 结果 | 说明 |
| --- | --- | --- | --- | --- |
| 站点首页 | 点击 目标模块 | 目标模块列表页 | passed | 进入目标范围 |
| 目标模块列表页 | 点击 示例对象卡片 | 对象详情页：示例对象 B | passed | 打开详情页面 |
```

### 4. Goal validation 不可执行

当前目标：

```text
目标模块的全部内容
```

没有被拆解成验收清单，因此 `goal_validation.status = pending`。

问题影响：

- 报告无法判断是否“全部覆盖”。
- 下游可用性只能模糊写“部分可用”。
- 用户无法知道还缺什么。

改造方向：

启动探索前或探索过程中生成目标验收清单：

```yaml
goal_plan:
  goal: 目标模块的全部内容
  acceptance_items:
    - id: target-module-list
      title: 目标模块列表页可访问
      evidence_required: page
    - id: target-module-filter
      title: 类型、范围、状态、排序筛选可见并至少尝试一次
      evidence_required: action
    - id: target-module-search
      title: 搜索业务对象输入框可填写
      evidence_required: action
    - id: object-detail
      title: 至少一个业务对象详情页可打开
      evidence_required: page
    - id: create-entry
      title: 创建对象入口可打开但不提交
      evidence_required: action
    - id: history-entry
      title: 历史记录入口可点击或记录失败原因
      evidence_required: action_or_blocker
```

`checks/goal-validation.yaml` 必须输出每项状态：

```yaml
items:
  - id: target-module-list
    status: passed
    evidence:
      - pages/page-002-target-module-list.yaml
  - id: history-entry
    status: failed
    reason: locator timeout
    evidence:
      - logs/run.log#turn-6
```

### 5. 动作失败未进入风险和阻塞

当前日志中存在：

- locator click timeout
- pointer events 被弹层遮挡
- 下拉框点击失败

但 `blockers.yaml` 为空，报告风险显示“无”。

改造方向：

- 动作失败不一定都是 blocker，但必须进入 `action_failures` 或 `blockers`。
- 影响目标验收项的失败必须进入 `blockers.yaml`。
- 非关键失败进入 `summary.warnings`。

示例：

```yaml
blockers:
  - id: blocker-001
    type: action_failed
    severity: medium
    page_ref: page-002
    action_target: 历史记录
    reason: locator.click timeout
    impact_scope: 历史记录入口未验证
    suggested_action: 人工确认 locator 或增加弹层关闭策略
    evidence_path: logs/run.log#turn-6
```

### 6. 运行事实不一致

当前 `run.yaml` 的 `site_url` 为空，但日志起始 URL 和 summary markdown 有真实 URL。

改造方向：

- `run.site_url` 必须在任务创建时持久化。
- 如果 run 缺失，artifact 写入时从 `run.url`、`initial_url`、首个 page URL 或日志 `run_started.url` 回填。
- 报告生成遇到关键字段为空时必须显示“缺失来源”，不能静默空白。

## 产物模型改造

### pages/*.yaml

保留现有字段，新增语义字段：

```yaml
page:
  id: page-002
  title: 示例系统
  semantic_title: 目标模块列表页
  url: https://example.test/module
  normalized_url: https://example.test/module
  module: 目标模块
  active_module: 目标模块
  active_submodule: 对象列表
  page_kind: list
  status: explored
  confidence: high
  structure_summary: 原始结构摘要
business_summary:
  headline: 目标模块展示业务对象列表，支持筛选、搜索、导入和创建。
  business_objects:
    - 业务对象
  key_entities:
    - 示例对象 A
  primary_actions:
    - 创建
    - 导入
    - 分析
    - 使用
    - 对话历史
  filters:
    - 类型
    - 范围
    - 状态
    - 排序
  observed_states:
    - 已发布
quality:
  needs_confirmation: false
  warnings: []
```

页面类型枚举：

```text
home
list
detail
analysis
form
modal
drawer
empty_state
settings
resource
unknown
```

### graph.yaml

保留 `nodes/edges/paths`，增强可读字段：

```yaml
edges:
  - id: edge-002
    source: page-001
    target: page-002
    source_title: 站点首页
    target_title: 目标模块列表页
    type: navigation
    action: click
    action_target: 目标模块
    decision_id: decision-002
    result:
      status: passed
      url_changed: true
      state_signature_changed: true
```

关系类型枚举：

```text
navigation
tab_switch
filter
search
open_modal
close_modal
open_detail
form_entry
data_dependency
same_state_action
failed_action
out_of_scope
```

### summary.yaml

新增聚合字段：

```yaml
coverage:
  module_count: 1
  semantic_page_count: 6
  raw_state_count: 23
  action_count: 55
  passed_action_count: 42
  failed_action_count: 13
modules:
  - module_key: target_module
    module_name: 目标模块
    status: partial
    semantic_pages:
      - 目标模块列表页
      - 对象详情页
      - 创建对象入口
    covered_capabilities:
      - 列表浏览
      - 搜索
      - 筛选
      - 详情页查看
    missing_capabilities:
      - 使用入口
      - 历史记录入口
    knowledge_base_availability: 部分可用
warnings:
  - 历史记录入口点击失败，未验证后续页面。
  - 关联资源页面曾被访问，属于探索范围外，需要标记越界而非纳入目标模块覆盖。
```

### blockers.yaml

扩展 blocker 类型：

```text
login_required
captcha_required
permission_denied
action_failed
locator_unstable
out_of_scope
goal_unparsed
goal_item_unverified
environment_risk
manual_confirmation_required
```

## 报告模板改造

报告仍保存到：

```text
reports/exploration-report.md
```

新版报告结构：

```md
# 站点探索报告：目标模块探索

## 1. 结论摘要

- 结论：
- 下游可用性：
- 最大风险：
- 建议下一步：

## 2. 目标验收结果

| 验收项 | 状态 | 证据 | 缺口 |
| --- | --- | --- | --- |

## 3. 业务能力覆盖

| 能力 | 状态 | 观察到的事实 | 证据 |
| --- | --- | --- | --- |

## 4. 页面与状态覆盖

| 页面/状态 | 类型 | URL | 关键事实 | 证据 |
| --- | --- | --- | --- | --- |

## 5. 关键路径

| 路径 | 结果 | 说明 | 证据 |
| --- | --- | --- | --- |

## 6. 失败、阻塞与越界

| 类型 | 位置 | 原因 | 影响 | 建议 |
| --- | --- | --- | --- | --- |

## 7. 待人工确认

| 事项 | 为什么需要确认 | 影响 | 建议确认人 |
| --- | --- | --- | --- |

## 8. 证据索引
```

报告禁止：

- 输出超过 300 字的单个页面结构摘要。
- 重复展示同 URL、同语义状态的页面超过 1 次。
- 把所有 `agent_action click` 原样列出。
- 对 `pending` 目标写“已覆盖”。
- 有动作失败但风险写“无”。

## 状态规则

### 报告状态

| 状态 | 条件 |
| --- | --- |
| completed | 目标验收项全部 passed，且无高风险 blocker |
| partial | 至少有有效事实，但存在 failed/unverified/warning |
| blocked | 核心目标项因登录、权限、验证码、环境或关键动作失败无法继续 |
| failed | runner、agent、artifact 写入或报告生成异常 |

### 下游可用性

| 值 | 条件 |
| --- | --- |
| 可用 | 关键页面和关键路径已验证，目标验收通过 |
| 部分可用 | 有稳定页面事实，但存在未验证入口或非关键失败 |
| 不可用 | 核心页面缺失、目标未解析、关键路径失败 |
| 待确认 | 页面事实存在，但业务含义、权限或范围需要人工确认 |

### 目标未解析

如果目标无法拆解：

- `goal_validation.status = pending`
- `blockers.yaml` 增加 `goal_unparsed`
- 报告状态不得为 `completed`
- 报告必须明确写：

```text
当前探索目标尚未拆解为可执行验收清单，因此不能判断“全部内容”是否已覆盖。
```

## 实现方案

### 第一阶段：报告硬 bug 修复

修改 `apps/backend/app/services/exploration/artifact_service.py`：

- graph 关系读取 `source/target`，兼容旧字段 `from/to`。
- 用 graph nodes 映射页面标题，优先 `semantic_title`，其次 `title`，最后 page id。
- `_limit_text` 支持 `run.run.limits.max_pages`。
- `site_url` 缺失时从首个 page URL 或日志 `run_started.url` 回填。
- 页面核心事实禁止直接 fallback 到完整 `structure_summary`。
- 有 relation_rows 但端点缺失时，不输出 `- -> -`，改为 warning。

### 第二阶段：动作失败入结构化产物

在 Agentic Loop 或 runner 产物构建阶段：

- 收集所有 `action_result.status = failed`。
- 判断是否影响 goal item。
- 写入 `blockers.yaml` 或 `summary.warnings`。
- 报告展示失败动作的目标、原因、影响和建议。

### 第三阶段：页面语义化

新增页面语义化函数：

```text
derive_semantic_page_facts(page_observation, url, active_nav, action_history)
```

输入：

- URL pathname/query
- 浏览器标题
- 页面主文本
- 激活导航项
- 可见按钮和表单
- 最近动作
- 状态签名

输出：

- `semantic_title`
- `page_kind`
- `business_summary`
- `primary_actions`
- `filters`
- `observed_states`
- `key_entities`
- `confidence`

第一版使用规则 + LLM 双层：

1. 规则先做 URL 和常见组件识别。
2. LLM 只在规则置信度不足时对页面文本做摘要。
3. LLM 输出必须落结构化 schema，不能直接写 Markdown。

### 第四阶段：目标验收清单

新增：

```text
apps/backend/app/services/exploration/goal_plan_service.py
```

职责：

- 将自然语言目标拆成 `acceptance_items`。
- 每项声明需要的证据类型。
- 探索结束后根据 pages、graph、blockers 计算状态。

对“目标模块的全部内容”这类宽泛目标，默认拆解应覆盖：

- 目标模块入口可访问。
- 目标模块列表页可展示。
- 搜索可填写。
- 类型/范围/状态/排序筛选至少被识别。
- 创建入口可打开但不提交。
- 至少一个业务对象详情页可打开。
- 详情页关键筛选或切换控件可尝试。
- 使用入口可点击或记录失败原因。
- 历史记录入口可点击或记录失败原因。
- 空数据状态可识别。
- 越界页面不计入目标覆盖。

## 前端展示改造

探索报告 tab 继续展示 Markdown，但需要配合后端报告质量：

- 保留 Markdown 渲染。
- 对 `report.status = partial/blocked/failed` 显示状态提示。
- 如果 `goal_validation.status = pending`，提示“目标未完成验收拆解”。
- 报告为空或关键字段缺失时，不显示“暂无明显缺口”，而显示后端原因。

本 spec 不要求前端解析 Markdown 内容。

## 兼容性

- v2 schema 保持兼容。
- 新增字段均为可选字段。
- 老产物缺少 `semantic_title` 时，报告生成可 fallback 到旧字段。
- 老 graph 如果存在 `from/to`，继续兼容。
- 不迁移历史产物，只影响新探索和重新生成报告。

## 测试计划

### 单元测试

新增或更新：

```text
apps/backend/tests/test_exploration_artifact_v2.py
apps/backend/tests/test_exploration_service_artifact_v2.py
apps/backend/tests/test_exploration_agentic_loop.py
```

覆盖：

- graph `source/target` 能正确生成可读路径。
- `site_url` 缺失时能从页面或日志回填。
- `limits` 正确显示。
- 页面事实不会输出超长 `structure_summary`。
- 动作失败进入 blockers 或 warnings。
- `goal_validation.pending` 时报告不得写 completed。
- 同 URL 重复状态能聚合。

### 集成测试

构造一个模拟“目标模块”探索产物：

- 页面：站点首页、目标模块列表、对象详情、创建弹层、空数据状态。
- 动作：目标模块导航、搜索、筛选、详情页打开、历史记录失败。
- 目标：目标模块的全部内容。

断言：

- 报告含业务能力覆盖。
- 报告含目标验收表。
- 报告含失败动作。
- 报告不出现大量重复的浏览器标题。
- 报告不出现 `- | click | -`。

## 验收标准

1. 任意目标模块探索报告能在前 30 行说明本次覆盖价值、关键缺口和下一步建议。
2. 页面列表显示语义页名，而不是全部显示浏览器标题。
3. 关键路径表能展示起点、动作目标、终点和结果。
4. 目标未拆解时，报告明确说明不能判断“全部覆盖”。
5. 动作失败不会被隐藏，至少进入 warnings 或 blockers。
6. 报告中不再重复输出 20 行以上几乎相同的 `structure_summary`。
7. `run.yaml`、`summary.yaml`、`graph.yaml`、`blockers.yaml` 和报告之间核心事实一致。
8. 下游可用性基于目标验收和 blocker 计算，不只基于页面数量。

## 分阶段交付

### P0：可信度修复

- 修 graph 字段映射。
- 修 `site_url` 和 limits 空字段。
- 修目标 pending 时的状态文案。
- 修报告中 `structure_summary` 长文本直接 fallback。

### P1：失败显性化

- 动作失败进入 warnings/blockers。
- 报告展示失败、影响和建议。
- 越界访问进入 warning 或 blocker。

### P2：语义页面与能力聚合

- 新增 `semantic_title`、`page_kind`、`business_summary`。
- 报告按业务能力聚合。
- 同 URL 同状态去重。

### P3：目标验收清单

- 新增目标拆解服务。
- 输出 `goal_plan` 和完整 `goal_validation.items`。
- 报告展示验收项通过、失败、未验证。

## 风险与注意事项

- 语义化不能把观察到的页面文本提升为正式业务规则。
- LLM 摘要必须有结构化 schema 和事实来源，不允许自由发挥。
- 生产环境写动作仍必须受策略限制。
- 页面名语义化可能有误，低置信度必须标记 `needs_confirmation`。
- 报告变短不等于事实丢失，完整事实仍在 YAML 和日志中。

## 与既有 Spec 的关系

- 继承 `2026-05-30-site-exploration-report-template-spec.md` 的“报告不是事实源”原则。
- 补充 `2026-06-06-site-exploration-langchain-playwright-artifacts-spec.md` 中报告从结构化产物派生的要求。
- 对 `2026-06-07-site-exploration-agentic-playwright-loop-spec.md` 的 Agentic Loop 产物质量提出更具体的报告和事实聚合要求。
