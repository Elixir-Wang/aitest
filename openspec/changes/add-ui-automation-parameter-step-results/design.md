## Context

当前系统使用 pytest + pytest-playwright 执行一个资产的 `pytest_node_id`。pytest 会将 renderer 叠加生成的 `@pytest.mark.parametrize` 展开为实际测试项；当前真实资产包含一个 `target_model` 参数和 34 个值。`AutomationPlan` 已为每个生成动作保存 `source_step_id`，但 renderer 将动作和断言输出为连续 Python 语句，pytest 插件只处理浏览器 CDP 参数与父进程守护，因此执行结果只有运行级 `status` 和 `exitcode`。

运行详情页每 2 秒轮询运行记录，完成后读取 stdout、stderr 和全局截图；实时浏览器画面通过已有 MJPEG live-view 独立提供。系统明确不接入 Allure，运行产物以 `run_dir` 文件和 SQLite 运行记录为边界。

## Goals / Non-Goals

**Goals:**

- 展示 pytest 实际收集到的每个参数实例及其独立状态、耗时、当前步骤和失败步骤。
- 展示每个参数实例下的业务步骤结果，并允许展开查看生成动作、断言、错误和证据。
- 运行中可增量查看，运行完成后可稳定复现同一结构化结果。
- 复用现有自动化计划、renderer、pytest 插件、运行目录、轮询机制和实时浏览器画面。
- 兼容无参数用例、当前 `AutomationPlan v1` 资产、取消、超时和服务重启恢复。

**Non-Goals:**

- 不接入 Allure、ReportPortal 或其他报告平台。
- 不新增 pytest 重试插件，不提供单参数实例重新执行或断点续跑。
- 不改变多个 `@pytest.mark.parametrize` 的现有笛卡尔积行为，也不在本变更增加数据行参数化编辑器。
- 不把每条步骤事件实时写入 SQLite，不建设跨运行步骤分析仓库。
- 不改变现有 CDP/MJPEG 实时画面协议。
- 一期不提供参数与步骤矩阵视图；主视图采用参数列表加单实例步骤详情。

## Decisions

### 1. 以 pytest collected item 作为参数实例事实源

pytest 插件在 collection 完成后读取每个目标测试项的 `item.nodeid`、顺序和 `item.callspec.params`，生成运行内唯一的 `iteration_id`。平台不读取 YAML 后自行计算组合，因为 pytest 标记、fixture、ID 生成和未来插件都可能改变实际收集结果。

参数实例结构：

```json
{
  "iteration_id": "iteration-0001",
  "pytest_node_id": "test_file.py::test_case[qwen-plus]",
  "index": 1,
  "parameters": {"target_model": "qwen-plus"},
  "attempt": 1,
  "status": "pending"
}
```

`iteration_id` 不直接使用参数文本，避免特殊字符、超长值和敏感值成为路径。参数值经过统一的长度限制与敏感字段脱敏后才能持久化和返回前端。

替代方案是从自动化 YAML 生成参数组合；该方案会复制 pytest 参数化语义并可能与真实收集结果不一致，因此拒绝。

### 2. 显式区分业务步骤与技术动作

`AutomationPlan` 的步骤契约增加可选字段：

```json
{
  "source_step_id": "step-7-send",
  "business_step_id": "step-7",
  "title": "输入 hi 并发送",
  "visible": true,
  "kind": "click"
}
```

- `source_step_id` 标识确定性 renderer 的单个动作。
- `business_step_id` 指向来源用例中的业务步骤。
- `title` 是运行详情使用的用户可读名称。
- `visible=false` 用于关闭临时面板等内部动作；内部动作仍保留在证据中。

renderer 按 `business_step_id` 将连续动作和该检查点断言包裹在一个 `ui_case.step(...)` 上下文中。一个业务步骤失败时，该步骤记录失败；同一参数实例后续未开始的业务步骤在终态聚合时记为 `skipped`。

历史 v1 计划继续按原代码执行。不存在显式映射时，每个 `source_step_id` 作为独立可见步骤，系统不得通过字符串前缀猜测业务父步骤。资产重新生成后写入完整映射。

替代方案是解析 Python 源码、stdout 或 pytest trace 推断步骤；这些输出缺少稳定业务身份，无法可靠关联来源用例，因此拒绝。

### 3. 使用 pytest fixture 和上下文管理器采集步骤

套件初始化增加 `ui_case` fixture。fixture 依赖 `request` 和 `page`，负责：

- 建立当前参数实例上下文。
- 提供 `ui_case.step(business_step_id, title, operation_ids)`。
- 在进入和退出上下文时写入步骤事件。
- 捕获异常类型、脱敏消息和 traceback 摘要。
- 失败时将当前页面截图写入步骤级证据目录。

生成代码示例：

```python
def test_case(page, ui_case, target_model):
    with ui_case.step("step-4", f"选择模型 {target_model}", operation_ids=["step-3", "step-4"]):
        bot_settings_page.model_selector.click()
        bot_settings_page.visible_text(str(target_model)).click()
```

pytest hooks继续负责 collection、测试项 setup/call/teardown 状态和无步骤失败；业务步骤上下文负责步骤粒度。fixture异常、浏览器启动失败等发生在业务步骤之前的错误归类为 `infrastructure_error`。

### 4. JSONL 是运行中事件事实源，终态 JSON 是完成后事实源

runner 在启动子进程前设置：

```text
UI_RUN_ID
UI_RUN_EVENT_PATH=<run_dir>/events.jsonl
UI_RUN_ARTIFACT_DIR=<run_dir>/step-artifacts
```

每条事件包含递增 `sequence`、schema version、run、iteration、step、status和时间。当前执行器未启用 pytest-xdist，事件由单 pytest 进程串行追加；写入器仍使用进程内锁、单行大小限制、flush 和损坏尾行容错。

```json
{
  "schema_version": "ui-run-events/v1",
  "sequence": 18,
  "type": "step_finished",
  "run_id": "uirun-...",
  "iteration_id": "iteration-0003",
  "step_id": "step-4",
  "status": "failed",
  "timestamp": "2026-08-02T10:32:15.412Z",
  "duration_ms": 30124,
  "error": {"type": "TimeoutError", "message": "..."},
  "artifact_ids": ["artifact-..."]
}
```

执行结束后，runner 使用确定性 reducer 将事件聚合为 `result-detail.json`。`ui_automation_execution_runs.result_json` 保存运行汇总、详情 schema version 和详情文件存在标记，不保存完整步骤数组。服务重启或进程异常时，reducer可根据已落盘事件生成部分结果。

替代方案是每步更新 SQLite `result_json`；该方案会造成高频大 JSON 重写和子进程数据库锁竞争，因此拒绝。

### 5. 状态模型和聚合规则

参数实例状态：`pending`、`running`、`passed`、`failed`、`skipped`、`cancelled`、`infrastructure_error`。

步骤状态：`pending`、`running`、`passed`、`failed`、`skipped`、`cancelled`。

规则：

- pytest call 通过且所有已执行步骤通过时，参数实例为 `passed`。
- 业务步骤抛出异常时，该步骤和参数实例为 `failed`，后续步骤为 `skipped`。
- setup/fixture/browser 启动失败且未进入业务步骤时，参数实例为 `infrastructure_error`。
- 用户停止或进程被终止时，当前运行步骤和参数实例为 `cancelled`，未开始实例保持 `cancelled`，而不是错误标记为业务失败。
- 运行通过仅当所有实际收集到的参数实例均通过；存在失败、基础设施错误或取消时按既有运行终态规则收敛。
- `attempt` 一期固定为 1，作为未来重试扩展字段，不在 UI 制造不存在的重试能力。

### 6. 使用快照加 cursor 事件接口

新增只读接口：

```http
GET /projects/{project_id}/ui-automation/runs/{run_id}/result-detail
GET /projects/{project_id}/ui-automation/runs/{run_id}/events?after=18&limit=200
GET /projects/{project_id}/ui-automation/runs/{run_id}/step-artifacts/{artifact_id}
```

- `result-detail` 返回当前聚合快照；运行中可由后端即时 reduce 已有事件，完成后读取终态文件。
- `events` 返回 `items`、`next_cursor` 和 `has_more`，前端只增量读取新事件。
- artifact ID 通过运行内清单解析，API必须验证项目归属、运行目录包含关系和允许的 MIME 类型；客户端不得提交文件路径。
- 单次事件返回数量、单字段长度和总响应大小均受限。

继续复用现有 1 到 2 秒轮询，而不引入 SSE/WebSocket。当前单资产串行执行、34 个参数实例和几十个步骤的事件量适合 cursor 轮询，且与现有页面生命周期一致。

### 7. 运行详情采用参数列表与步骤详情主从布局

页面头部展示参数实例总数、通过、失败、运行中、取消和总耗时。主体：

- 左侧为参数实例列表，显示参数摘要、状态、耗时和失败步骤，支持状态与参数文本筛选。
- 右侧为所选实例的业务步骤列表，显示状态、耗时和当前步骤；失败步骤默认展开错误、截图、断言和技术动作。
- 无参数用例只有一个默认实例，页面隐藏左侧列表并直接显示步骤。
- 运行中默认选择当前实例，但用户手动选择后不得强制抢回焦点。
- 参数实例超过 100 时使用虚拟列表；参数值必须换行或截断，不能撑破布局。
- 原“运行日志”和“浏览器证据”保留为次级标签；现有“实时查看”对话框保持不变。

### 8. 安全、脱敏和保留策略

- 参数名命中 password、secret、token、cookie、authorization 等敏感规则，或未来参数元数据显式标记 sensitive 时，持久化值统一为 `***`。
- 错误消息和 traceback 沿用并扩展现有 runner 脱敏规则；不保存页面输入值、Cookie、Storage State 或请求凭证。
- 步骤截图只在失败时默认采集，避免对当前 34 × 24 场景产生大量图片；不得在截图之外新增 DOM 全量保存。
- `events.jsonl`、`result-detail.json`、清单和步骤证据随现有运行目录删除逻辑级联清理。

## Risks / Trade-offs

- [旧 v1 资产缺少业务步骤映射] -> 保持可执行并降级为技术步骤；重新生成后获得完整业务分组，禁止启发式猜测。
- [JSONL 尾行可能在强制终止时不完整] -> reducer 忽略最后一条无效 JSON，保留此前完整事件并标记结果不完整。
- [参数值或错误内容泄露敏感信息] -> 在子进程写入前和 API 返回前双重脱敏，使用运行内序号作为实例 ID。
- [失败截图增加磁盘占用] -> 仅失败步骤截图，限制单图大小、每实例数量和运行总量，并沿用运行清理机制。
- [轮询延迟不是真实时] -> 一期接受 1 到 2 秒延迟；cursor避免全量重复传输，未来有明确并发压力后再评估 SSE。
- [生成步骤分组不正确] -> 计划校验要求每个新生成动作显式引用存在的业务步骤，renderer不自行推断。

## Migration Plan

1. 先发布后端对可选步骤映射字段和 v1 计划的兼容读取，已有资产继续执行。
2. 发布事件写入、reducer和新只读 API；旧运行没有详情文件时返回 `detail_available=false`，现有日志页面仍可用。
3. 更新 renderer和套件模板；新生成或重新生成的资产开始输出 `ui_case.step(...)`。
4. 更新前端运行详情；检测到详情不可用时展示现有日志、截图和实时画面降级视图。
5. 完成验证后再把结构化详情作为新运行的默认主视图。

回滚时可关闭步骤事件环境变量和新详情入口；pytest测试代码、原运行状态、stdout/stderr、全局截图及 live-view 保持可用。新增运行文件可由既有运行目录清理，无需反向数据迁移。

## Open Questions

- 未来增加 pytest 重试时，是按参数实例下增加 Attempt 层，还是将每次 retry 显示为独立实例；本设计预留 `attempt`，但本变更不决定最终交互。
- 参数矩阵是否作为后续独立能力建设；当前主从视图已覆盖单实例排障需求。
