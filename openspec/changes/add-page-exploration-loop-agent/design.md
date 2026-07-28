# 设计方案

## 1. 架构总览

```text
创建 loop 运行
      ↓
读取项目产物并创建 baseline
      ↓
初始化 LoopExplorationState
      ↓
┌──────────────────────────────────────────────┐
│ Loop Orchestrator                             │
│ select frontier → observe → discover         │
│ → decide → execute → verify → persist        │
│ → expand frontier → repeat                    │
└──────────────────────────────────────────────┘
      ↓
清理本轮测试数据
      ↓
全局覆盖率与合并校验
      ↓
项目产物、报告、合并摘要
```

Loop Agent 是局部决策者，不是全局流程控制者。它只能从服务端最近一次 snapshot 提供的候选元素中选择动作；frontier 调度、状态去重、预算判断、验证和持久化由 Loop 服务/图编排器负责。

## 2. 独立目录和复用边界

后端目录边界固定为“独立 Agent 包、独立 Loop 服务、通用页面探索 API/运行表复用”：

```text
apps/backend/app/
├── agents/
│   ├── page_exploration/              # 现有 goal/autonomous，保持不变
│   └── page_exploration_loop/        # 新增 Loop Agent，不嵌套在上者
│       ├── agent.py
│       ├── schemas.py
│       ├── prompts/system_prompt.py
│       ├── state/{models.py,reducer.py}
│       ├── tools/loop_tools.py
│       └── services/{orchestrator.py,frontier.py,verifier.py,checkpoint.py}
├── services/page_exploration/
│   ├── service.py                     # 通用 facade，按 mode 分发
│   ├── runner.py                      # 通用后台生命周期
│   └── loop/
│       ├── service.py                 # Loop 运行入口
│       └── loop_artifact_merge_service.py
├── api/v1/page_exploration/            # 复用 runs/events/artifacts API
└── repositories/
    ├── exploration_run_repo.py         # 复用主运行记录
    └── exploration_loop_*_repo.py      # 需要高频查询时再新增
```

`page_exploration_loop` 可以 import 浏览器会话、runtime context、事件和稳定身份工具，但不得 import 现有 `page_exploration.agent`、Prompt 或 `CoverageState`。Loop-specific checkpoint 首版优先落在 `runs/{run_id}` 文件中，避免为了验证算法立即改变数据库；只有 frontier/state/transition 需要高频分页查询时才增加专用 repository。

新增目录：

```text
apps/backend/app/agents/page_exploration_loop/
├── __init__.py
├── agent.py                 # 当前页面的局部动作决策 Agent
├── schemas.py               # 动作决策、候选、验证契约
├── prompts/
│   └── system_prompt.py
├── state/
│   ├── __init__.py
│   ├── models.py             # LoopExplorationState、FrontierItem
│   └── reducer.py
├── tools/
│   ├── __init__.py
│   └── loop_tools.py         # 只暴露 loop 所需的受控工具适配器
└── services/
    ├── __init__.py
    ├── orchestrator.py
    ├── frontier.py
    ├── verifier.py
    └── checkpoint.py
```

以下内容保持原目录不变：

- `apps/backend/app/agents/page_exploration/agent.py`
- 原有 `SYSTEM_PROMPT`、`AUTONOMOUS_SYSTEM_PROMPT`
- 原有 `CoverageState`
- `goal` / `autonomous` 的终止和调用语义

允许 Loop 复用的基础设施：

- `PlaywrightBrowserSession` 和 runtime context
- `playwright_snap_tool`、`playwright_click_tool`、`playwright_fill_tool`
- 页面身份、元素稳定键和 URL 规范化工具
- 现有 event bus、timeline/raw events 和取消检查
- 页面产物注册、操作草稿、报告写入和数据库 artifact 注册

复用通过适配器完成，Loop Agent 不直接 import 现有页面 Agent 的 Prompt 或状态实现。

## 3. Loop 状态

```python
class LoopExplorationState(TypedDict):
    run_id: str
    project_id: str
    start_url: str
    scope: str
    forbidden_paths: list[str]
    current_state_key: str
    frontier: list[FrontierItem]
    visited_states: dict[str, StateRecord]
    discovered_pages: dict[str, PageRecord]
    discovered_elements: dict[str, ElementRecord]
    transitions: list[TransitionRecord]
    pending_verifications: list[str]
    created_test_data: list[TestDataRecord]
    cleanup_results: list[CleanupRecord]
    failures: list[FailureRecord]
    counters: ExplorationCounters
    budget: ExplorationBudget
    stop_reason: str | None
```

稳定状态键至少由规范化 URL、页面标题、可交互元素稳定键、浮层签名和关键选择状态组成；不得包含 observation id、临时 DOM id、时间戳或随机 token。

`FrontierItem` 至少包含：`state_key`、`page_key`、`element_key`、`action_type`、`priority`、`retry_count`、`status` 和 `source_transition_id`。

## 4. 循环节点

首版可用服务内显式异步循环实现；编排抽象必须与 LangGraph StateGraph 兼容，以便后续接入 checkpointer、interrupt 和恢复。

节点职责固定为：

1. `select_frontier`：按优先级取一项，检查 scope、禁止路径和预算。
2. `observe_page`：调用 snapshot，生成当前页面事实和状态签名。
3. `discover_candidates`：合并页面、元素、状态和待执行候选，不执行模型输出。
4. `decide_action`：Loop Agent 只返回结构化 `ActionDecision`，必须引用候选 `element_key`。
5. `execute_action`：通过受控工具适配器执行 click/fill/navigate；禁止自由 locator。
6. `verify_action`：验证 URL、标题、浮层、Toast、表单值、状态签名和预期效果。
7. `persist_transition`：写入动作、前后状态、证据、失败/阻塞原因和 timeline event。
8. `expand_frontier`：从新状态发现新页面、元素、Tab、分页和流程分支。
9. `cleanup`：清理本轮创建的数据，并验证清理结果。
10. `finish`：执行全局覆盖率、合并和报告注册。

循环条件：

```text
frontier 非空
且未取消
且未超出 max_pages / max_actions / timeout
且不存在待人工确认
```

完成条件：frontier 为空、pending 元素为零、pending verification 为零、cleanup pending 为零。停止原因必须是结构化枚举，不得只写自然语言。

## 5. Agent 决策契约

```python
class ActionDecision(BaseModel):
    action_type: Literal[
        "click", "fill", "navigate", "observe_overlay",
        "skip", "request_human", "finish_state"
    ]
    element_key: str | None = None
    value: str | None = None
    expected_effect: str
    risk_level: Literal["low", "medium", "high", "destructive"]
    reason: str
    confidence: float = Field(ge=0, le=1)
```

模型不得返回总体完成状态、页面 YAML、locator 字符串或未经候选列表确认的元素 id。`request_human` 只能用于高风险动作或明确阻塞，不得作为逃避普通探索的终止手段。

## 6. Verification loop

工具返回成功不等于业务动作验证成功。动作后至少执行一次受控观察；验证结果分为：

- `verified`：达到预期效果，并产生可信 after-state。
- `no_effect`：动作成功但状态无变化，有限等待/重观察后仍无变化。
- `blocked`：权限、遮挡、人工审批或环境阻塞。
- `failed`：工具或页面执行失败。

重试策略固定且有上限：同一 `state_key + element_key + action_type` 最多重试两次；连续无变化不超过一次定向重观察；超过阈值进入 blocked/failed，不得无限调用模型。

## 7. 产物和合并

Loop 运行仍生成现有项目级产物：

```text
{project_root}/{project_id}/page_exploration/
├── pages/*.yaml
├── pages/pages-index.yaml
├── page_edges.yaml
└── runs/{run_id}/
    ├── baseline/
    ├── loop_state.json
    ├── frontier.jsonl
    ├── transitions.jsonl
    ├── timeline_events.jsonl
    ├── raw_events.jsonl
    ├── conflicts/
    └── report.md
```

运行开始时复制 `pages/*.yaml` 和 `page_edges.yaml` 到 `runs/{run_id}/baseline/`，形成不可变基线。运行过程可以写入本次 delta 文件；完成时由独立的 `loop_artifact_merge_service` 合并到项目产物。

合并规则：

- 页面身份按 `identity_key/page_id/canonical_path` 校验。
- `regions`、`elements`、`states`、`interactions`、`blockers` 按稳定键幂等合并。
- 完全相同的事实记为 `duplicate`。
- 同一稳定键且事实兼容时补充字段并记为 `updated`。
- 同一稳定键且关键字段冲突时写入 `runs/{run_id}/conflicts/*.yaml`，保留 baseline 和 delta，记为 `conflict`。
- 冲突不得覆盖既有项目事实；存在冲突时运行结果最多为 `partial`，不能宣称全量完成。
- `page_edges.yaml` 按稳定 edge id upsert，重复边只更新最近观测元数据。
- 合并必须幂等：对同一个 run 重复执行不产生重复元素、重复边或重复 merge history。

现有 `artifact_merge_service.py` 可作为算法基础，但 Loop 使用独立服务入口和独立测试，不能直接改变 goal 合并行为。

## 8. 数据库和 API

新增 `exploration_mode` 值 `loop`，现有 API 的 `goal` / `autonomous` 保持兼容。Loop-specific 运行状态优先写入 run artifact；若需要查询和恢复的高频字段，再增加以下表：

- `exploration_loop_states`
- `exploration_loop_frontier`
- `exploration_loop_transitions`

至少需要支持：创建、启动、停止、恢复、详情、覆盖率、合并摘要和冲突详情。已有通用探索 run API 继续承载鉴权、环境归属、任务状态和事件流。

## 9. 风险和人工确认

动作按 `low/medium/high/destructive` 分级。运行配置决定 `high/destructive` 是否允许自动执行：

- 测试环境可使用本轮测试数据执行并登记 cleanup。
- 生产或未知环境默认进入 `request_human`。
- 密码、Token、Cookie、密钥和个人敏感数据不得写入产物。
- 创建/编辑/发布/删除等副作用动作必须具备本轮数据标识和回收记录。

## 10. 可观测性

每次 Loop 迭代至少发布：`frontier_selected`、`page_observed`、`candidates_discovered`、`action_decided`、`action_completed`、`action_verified`、`state_discovered`、`transition_persisted`、`merge_completed` 或 `loop_blocked`。事件 payload 只记录脱敏摘要、稳定 key、状态签名和引用路径，不记录敏感值。

## 11. 分阶段交付

### Phase 1

独立 Agent 目录、显式 frontier 循环、状态去重、动作验证、JSONL checkpoint、Loop 产物和兼容 API。

### Phase 2

LangGraph checkpointer/interrupt、人工确认、高频状态表、前端 Loop 进度和状态图视图。

### Phase 3

基于历史 trace 的失败聚类、策略建议和人工审核后的探索策略改进。
