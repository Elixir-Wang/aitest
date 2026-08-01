# 页面探索旧产物硬切换设计

**项目**：AI 测试系统页面探索  
**日期**：2026-08-01  
**状态**：已确认  
**目标版本**：页面探索 Schema 4.0 纯净运行时

---

## 1. 背景

页面探索已经完成 Schema 4.0 页面产物、共享覆盖记录和 Loop 确定性执行链路的建设，但仓库中仍保留多组 Schema 2.0/3.0 时代的运行逻辑、项目级文件、API、测试脚手架和无引用代码。

当前残留包括：

- 自主/目标探索的 URL 检查器只识别 Schema 2.0/3.0 页面。
- `write_todos` 时间线仍写入项目级 `subgoals.yaml`。
- 项目级 `operations.yaml` 及 Replay API 仍依赖 Schema 3.0 页面。
- 手工测试用例生成仍读取 `operations.yaml`。
- 运行详情和报告仍返回 `artifact_schema_version: 3`。
- 第一版 Loop Agent、LoopOrchestrator 和 CoverageState 已被当前生产链路替代，但仍由独立测试维持。
- 多个旧产物构造函数、Repository 方法、响应模型和前端类型没有生产调用。
- 部分前端契约测试仍检查组件重构前的源码位置。

本次采用一次性硬切换，不提供旧 Schema 转换、兼容读取或 API 过渡期。

---

## 2. 目标

1. 页面探索生产代码只读写 Schema 4.0 页面产物和共享覆盖文件。
2. 删除 `operations.yaml`、`subgoals.yaml` 及其锁文件和运行时依赖。
3. 删除项目级 Operations/Replay API 和 Replay 服务。
4. 删除已经被当前 Loop 运行时替代的原型代码。
5. 删除仅用于维持旧实现的测试和无引用代码。
6. 提供安全、可审计、幂等的一次性旧产物清理命令。
7. 保证现有 Schema 4.0 页面、共享覆盖、运行证据和报告不会被误删。
8. 让 `goal`、`autonomous` 和 `loop` 三种模式共享同一套跨运行覆盖事实。

---

## 3. 非目标

本次明确不做：

- 不把 Schema 2.0/3.0 页面转换为 Schema 4.0。
- 不保留旧 Operations/Replay API 的兼容端点。
- 不保留 `operations.yaml` 的只读能力。
- 不新增数据库表。
- 不修改 UI 自动化、API 自动化或性能测试的数据模型。
- 不重构与旧产物删除无直接关系的探索页面 UI。
- 不删除 Schema 4.0 页面、共享覆盖文件、当前运行证据、截图、trace、snapshot 或报告。
- 不自动执行清理；实际删除前必须先完成人工审阅的 dry-run。

---

## 4. 硬切换原则

### 4.1 单一事实源

页面事实只来自：

```text
page_exploration/pages/*.yaml        # schema_version: "4.0"
page_exploration/exploration-coverage.yaml
```

运行过程证据继续来自：

```text
page_exploration/runs/<run_id>/
```

不得再读取或写入：

```text
page_exploration/operations.yaml
page_exploration/operations.yaml.lock
page_exploration/subgoals.yaml
page_exploration/replay-runs/
```

### 4.2 不做静默兼容

发现 Schema 2.0/3.0 页面时，不尝试转换、不当作已探索页面使用，也不混入 Schema 4.0 合并流程。清理命令将其列入删除清单。

### 4.3 先切代码，再删数据

必须先完成生产代码切换并通过测试，确保运行时不再依赖旧文件；之后才能 dry-run 和实际删除存量旧产物。

### 4.4 删除操作可审计

清理命令必须输出每个项目的候选路径、类型、识别原因和最终动作。实际删除结果必须包含删除数量、缺失数量、跳过数量和错误数量。

---

## 5. 生产运行时改造

### 5.1 URL 与覆盖检查

删除 `apps/backend/app/agents/page_exploration/tools/url_tools.py` 中基于 Schema 2.0/3.0 页面和 `subgoals.yaml` 的判断。

保留 Agent 工具名 `check_explored_url_tool`，避免无意义地修改 Prompt 和模型工具契约，但其实现改为：

1. 根据当前运行时上下文取得 `project_id` 和存储根目录。
2. 读取 `exploration-coverage.yaml`。
3. 根据规范化路径找到对应 Schema 4.0 `page_id`。
4. 返回页面、状态和操作的共享覆盖摘要。
5. `force_reexplore=true` 时忽略 completed 覆盖。

工具返回值固定为：

```json
{
  "explored": true,
  "page_id": "page-home",
  "page_completed": true,
  "completed_states": 3,
  "completed_operations": 12,
  "pending_operations": 2
}
```

不再返回 `subgoals`。

### 5.2 Todo 时间线

`write_todos` 继续投影为前端可读计划事件，但不再写入项目级文件。

删除 `timeline_projection.py` 中对 `write_subgoals_snapshot` 的动态 import、文件写入和异常降级日志。Todo 只属于 run 时间线，不是项目级探索事实。

### 5.3 产物版本

运行详情和报告中的 `artifact_schema_version` 统一返回 `4`。

如果后续需要支持多个版本，应从实际产物读取并验证；本次不增加多版本抽象。

---

## 6. Operations/Replay 删除

### 6.1 API 删除

从 `apps/backend/app/api/v1/page_exploration/artifacts.py` 删除以下端点：

- `GET /projects/{project_id}/operations`
- `PUT /projects/{project_id}/operations/{operation_key}`
- `POST /projects/{project_id}/replay`
- `GET /projects/{project_id}/replay-runs/{run_id}`
- `POST /projects/{project_id}/replay-runs/{run_id}/stop`
- `POST /projects/{project_id}/replay-runs/{run_id}/retry`

覆盖查询、产物列表、产物内容和报告端点继续保留。

### 6.2 服务和 Schema 删除

删除：

```text
apps/backend/app/services/page_exploration/replay/
```

删除仅服务于 Replay API 的请求模型和响应模型，包括：

- `ReplayOperationRequest`
- `SaveReplayOperationRequest`
- `ReplayOperation`
- `ReplayExpectation`
- `ReplayParameter`

删除 Replay 专属测试。

### 6.3 手工用例生成消费者

`exploration_context_builder.py` 不再读取 `operations.yaml`。

手工测试用例生成上下文只包含 Schema 4.0 页面事实：

- 页面基本信息。
- 状态。
- 可操作元素。
- 可断言元素。
- 已验证 transition。

删除 `ExplorationOperationContext` 及相关 Prompt/Schema 字段。已有 transition 足以描述“从什么状态执行什么动作到达什么状态”，不再维护第二套操作定义。

---

## 7. 旧实现代码删除

### 7.1 Loop 原型

当前生产 Loop 由 `apps/backend/app/services/page_exploration/loop/service.py` 驱动真实浏览器的 observe/decide/execute/verify 循环，只使用 `loop_action_decider`。

删除：

```text
apps/backend/app/agents/page_exploration_loop/services/orchestrator.py
apps/backend/app/agents/page_exploration_loop/tools/
apps/backend/app/agents/page_exploration_loop/prompts/
```

精简 `apps/backend/app/agents/page_exploration_loop/agent.py`，仅保留 `loop_action_decider`。

删除包级 `page_exploration_loop_agent` 懒加载导出，并同步删除只测试完整 Agent 工厂或 LoopOrchestrator 的测试。

### 7.2 旧覆盖和签名模型

删除只被测试引用、未进入生产调用链的：

```text
apps/backend/app/agents/page_exploration/state/coverage_state.py
apps/backend/app/agents/page_exploration/utils/dom_signature.py
apps/backend/app/agents/page_exploration/utils/state_id.py
```

同步清理对应 `__init__.py` 导出和测试。

保留当前生产使用的：

- `coverage_registry.py`
- `LoopExplorationState`
- `make_state_key`
- `element_key.py`
- `page_id.py`

### 7.3 无引用代码

删除经全仓引用扫描确认无调用的函数和类型，包括：

- `build_system_prompt`
- `_build_match_groups`
- `_upsert_snapshot_state`
- `_snapshot_overlay_container`
- `_snapshot_assertion_texts`
- `normalize_url`
- `list_run_artifacts`
- `ExplorationRunResponse`

Repository 无引用方法只有在全仓静态搜索和对应测试均确认无调用后删除，不顺带重构 Repository 结构。

---

## 8. 存量旧产物清理命令

### 8.1 命令位置

新增：

```text
apps/backend/scripts/cleanup_page_exploration_legacy_artifacts.py
```

命令从 `settings.PROJECT_FILE_STORAGE_ROOT` 开始扫描项目目录，不接受任意绝对存储根目录，避免误删仓库外文件。

### 8.2 命令接口

```bash
python scripts/cleanup_page_exploration_legacy_artifacts.py --dry-run
python scripts/cleanup_page_exploration_legacy_artifacts.py --apply --manifest <dry-run-manifest.json>
python scripts/cleanup_page_exploration_legacy_artifacts.py --project-id <project_id> --dry-run
```

规则：

- 默认模式必须是 `--dry-run`。
- `--apply` 必须同时提供由同一脚本生成的 manifest。
- manifest 记录绝对解析后的路径、文件大小、类型和内容摘要。
- apply 前重新校验路径、文件大小和内容摘要；发生变化则跳过并报错。
- `--project-id` 只能匹配存储根目录下的单层项目目录。
- 不提供通配符删除参数。

### 8.3 删除候选

无条件旧产物：

```text
operations.yaml
operations.yaml.lock
subgoals.yaml
replay-runs/
```

条件删除：

- `pages/*.yaml` 中 `schema_version` 为 `2.0` 或 `3.0` 的文件。
- 缺少 `schema_version` 且结构符合旧 `page.normalized_path + state_tree` 格式的页面文件。
- 只引用已删除旧页面的索引项和 page edge。

必须保留：

- `schema_version: "4.0"` 页面。
- `exploration-coverage.yaml`。
- 当前 `runs/` 目录及其证据。
- 当前 `page_edges.yaml` 中仍指向 Schema 4.0 页面的边。
- 项目目录下与页面探索无关的文件。

### 8.4 索引修复

删除旧页面后，清理命令必须原子更新：

- 项目页面索引。
- 指向已删除页面的 page edge。
- 共享覆盖中指向已删除页面、状态或操作的记录。

索引和覆盖更新使用临时文件写入后原子替换。任一更新失败时，不提交该项目的实际删除。

### 8.5 输出

dry-run manifest 至少包含：

```json
{
  "generated_at": "2026-08-01T00:00:00+08:00",
  "storage_root": "...",
  "projects": [
    {
      "project_id": "project-1",
      "delete": [],
      "rewrite": [],
      "preserve": [],
      "warnings": []
    }
  ],
  "summary": {
    "projects": 1,
    "delete_files": 3,
    "delete_directories": 1,
    "rewrite_files": 2,
    "warnings": 0
  }
}
```

实际执行输出同样结构，并增加 `deleted`、`rewritten`、`skipped` 和 `errors`。

---

## 9. 测试策略

### 9.1 后端单元测试

必须覆盖：

1. Schema 4.0 页面可通过规范化路径识别。
2. Schema 2.0/3.0 页面不进入生产读取链路。
3. completed 页面、状态和操作能被 `goal`、`autonomous` 和 `loop` 共享跳过。
4. `force_reexplore` 忽略共享覆盖。
5. `write_todos` 不生成 `subgoals.yaml`。
6. 运行详情和报告返回 `artifact_schema_version: 4`。
7. Operations/Replay 路由不存在。
8. 手工用例生成上下文不读取或返回 operations。

### 9.2 清理命令测试

必须覆盖：

1. dry-run 不修改任何文件。
2. apply 只删除 manifest 中未变化的目标。
3. 路径越界被拒绝。
4. 内容在 dry-run 后变化时跳过删除。
5. 重复执行保持幂等。
6. Schema 4.0 页面和运行证据始终保留。
7. 删除旧页面后索引、边和覆盖同步修复。
8. 单项目过滤不会影响其他项目。

### 9.3 前端契约测试

更新探索列表动作测试，使其读取：

```text
apps/frontend/src/components/ai-testing/exploration-runs-table.tsx
```

测试继续验证编辑、开始、重新探索、停止和删除动作，但不依赖动作位于 `exploration-workspace.tsx`。

### 9.4 静态残留检查

验证生产代码和测试中不再出现以下内容：

```text
operations.yaml
subgoals.yaml
ReplayRunService
ReplayService
CoverageState
LoopOrchestrator
schema_version in {"2.0", "3.0"}
artifact_schema_version: 3
```

清理脚本及其测试可以保留旧文件名和旧版本字符串，用于识别删除目标。

---

## 10. 实施顺序

### Phase 1：切换生产读取链路

- 共享覆盖替换旧 URL/subgoals 判断。
- 停止写入 `subgoals.yaml`。
- 修正产物版本元数据。
- 保持磁盘旧文件不动。

### Phase 2：删除旧产品能力

- 删除 Operations/Replay API、服务、Schema 和消费者字段。
- 删除旧 Loop、Coverage 和无引用代码。
- 更新前后端测试。

### Phase 3：构建和验证清理命令

- 实现 dry-run manifest。
- 实现受 manifest 约束的 apply。
- 完成清理命令测试。

### Phase 4：执行存量清理

1. 在目标环境运行 dry-run。
2. 人工审阅 manifest。
3. 备份待删除旧文件或保留存储快照。
4. 使用已审阅 manifest 执行 apply。
5. 运行完整验证。

---

## 11. 验收标准

- 新运行不会创建 `operations.yaml`、`subgoals.yaml` 或 `replay-runs/`。
- 生产代码不再读取 Schema 2.0/3.0 页面。
- Schema 4.0 页面能被所有探索模式正确识别并复用覆盖。
- 页面探索 API 不再暴露 Operations/Replay 端点。
- 手工用例生成只使用 Schema 4.0 页面事实和 transition。
- 当前 Loop 生产链路不依赖完整 Loop Agent 工厂或 LoopOrchestrator。
- 清理 dry-run 和 apply 均有机器可读 manifest。
- 清理后所有 Schema 4.0 页面、共享覆盖和运行证据保持完整。
- 后端探索专项测试全部通过。
- 前端探索契约测试全部通过。
- 全仓静态残留检查只在清理脚本及其测试中命中旧文件名或版本。

---

## 12. 风险与回滚

### 12.1 外部 Replay API 消费者

硬切换会直接删除 API。上线前必须检查网关访问日志和外部集成清单。发现外部调用时，应停止本次发布，而不是在代码中恢复兼容层。

### 12.2 存量旧页面唯一数据

Schema 2.0/3.0 页面不会转换。实际删除前必须保留存储快照或 manifest 对应的文件备份，以便人工查阅；备份不重新接入生产读取链路。

### 12.3 清理中断

按项目执行原子清理。单个项目失败不影响其他项目；失败项目保持原文件不变并记录错误。

### 12.4 代码回滚

代码回滚只能恢复代码版本，不自动恢复已经删除的数据。数据恢复必须从执行前存储快照完成。因此实际 apply 必须晚于代码部署和测试验证。

