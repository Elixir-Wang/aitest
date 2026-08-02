## Why

当前 UI 自动化执行只保存整次 pytest 进程的状态、退出码、日志和全局截图。参数化用例会被 pytest 展开为多个测试项，但系统无法展示每个参数实例的状态，也无法回答某个参数实例执行到哪个业务步骤、在哪一步失败以及该步骤对应的证据。

## What Changes

- 在 UI 自动化运行内增加“参数实例 -> 业务步骤 -> 技术动作”的结构化执行结果。
- 以 pytest 实际收集到的测试项和 `callspec.params` 作为参数实例事实源，不在平台侧重新计算参数组合。
- 扩展自动化计划和确定性 renderer，使生成代码显式标记业务步骤，并将断言纳入对应步骤结果。
- 扩展现有 pytest 插件，增量记录参数实例和步骤生命周期事件，并在失败步骤保留截图和错误摘要。
- 在运行目录保存版本化 JSONL 事件流和终态详情文件；SQLite 运行记录只保存汇总与产物引用。
- 增加运行详情和增量事件只读 API，支持运行中轮询和完成后查看完整结果。
- 将运行详情页改为参数实例列表与步骤详情的主从布局，保留现有日志、截图和实时浏览器画面能力。
- 保持现有参数笛卡尔积语义、运行状态机和无 Allure 架构不变。

## Capabilities

### New Capabilities

- `ui-automation-parameter-step-results`: UI 自动化参数实例发现、业务步骤采集、结果持久化、查询和运行详情展示。

### Modified Capabilities

无。当前 `openspec/specs/` 中没有已归档的 UI 自动化执行结果能力。

## Impact

- 后端生成契约与 renderer：`apps/backend/app/agents/ui_automation/pytest_playwright/`。
- pytest 执行采集：`apps/backend/app/services/ui_automation/live_pytest_plugin.py` 及新增的运行事件模块。
- 执行器与服务：`runner.py`、`service.py`、`ui_automation_repo.py`。
- API Schema 与路由：`app/schemas/ui_automation.py`、`app/api/v1/ui_automation.py`。
- 前端 API 类型和运行详情：`apps/frontend/src/lib/api-client.ts`、`ui-automation-run-detail.tsx`。
- 运行目录新增 `events.jsonl`、`result-detail.json` 和步骤级证据目录；不新增外部报告服务或运行时依赖。
