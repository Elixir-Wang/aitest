# Tasks

## 1. 契约和目录边界

- [x] 新增 `apps/backend/app/agents/page_exploration_loop/` 及其 `agent.py`、`schemas.py`、`prompts/`、`state/`、`tools/`、`services/` 子目录。
- [x] 明确 Loop Agent 不 import 现有 `app.agents.page_exploration.agent`、Prompt 或 `CoverageState`；通过适配器复用浏览器和产物基础设施。
- [x] 定义 `LoopExplorationState`、`FrontierItem`、`ActionDecision`、`VerificationResult`、`TransitionRecord` 和 `MergeSummary`。
- [x] 将 `exploration_mode` API/TypeScript 类型扩展为包含 `loop`，保持 `goal` / `autonomous` 兼容。

## 2. Loop 编排

- [x] 实现初始化、frontier 选择、预算检查、scope/forbidden path 检查和结构化 stop reason。
- [x] 实现页面观察、元素发现、状态指纹、页面/状态/元素去重。
- [x] 实现 Loop Agent 的结构化局部动作决策，禁止模型生成自由 locator 或直接写产物。
- [x] 复用受控 snapshot/click/fill/navigate 适配器，并为每次动作记录 before/after state。
- [x] 实现动作后确定性验证、有限重试、no_effect、blocked 和 failed 分类。
- [x] 实现从新状态扩展 frontier，并阻止同一状态/元素无限循环。
- [x] 支持取消、超时、max_pages、max_actions 和中断后从 checkpoint 恢复。
- [x] 将 Loop 专属 runtime 的 observe/decide/execute/verify 循环接入真实浏览器运行，使每个浏览器动作由 frontier 驱动，而不是只由 Agent 内部工具循环驱动。

## 3. 项目产物和合并

- [x] 实现 Loop run 的 baseline 快照，包括既有页面 YAML、索引和 page edges。
- [x] 实现 Loop delta 产物：页面、状态、元素、交互、边、frontier、transition 和报告。
- [x] 新增独立 `loop_artifact_merge_service`，按稳定键执行 duplicate/added/updated/conflict 合并。
- [x] 冲突写入 run conflicts 目录，保留 baseline/delta/summary，不静默覆盖既有项目事实。
- [x] 保证相同 run 重复合并幂等，并注册现有 exploration artifacts。
- [x] 将合并摘要、冲突数量和覆盖率写入运行结果和报告。

## 4. 运行和 API

- [x] 在现有页面探索 run 创建/启动服务中接入 `loop` 分支，但不改变 `goal` / `autonomous` 执行路径。
- [ ] 为 Loop 运行暴露详情、实时事件、frontier/coverage、恢复和冲突查询能力。
- [ ] 保证环境归属、登录策略、权限、停止和后台任务语义与现有探索任务一致。
- [ ] 前端增加 Loop 模式配置和运行状态展示，明确展示 stop reason、待探索项、阻塞项和合并冲突。

## 5. 风险控制和可观测性

- [ ] 实现 low/medium/high/destructive 风险分类和运行级自动执行策略。
- [ ] 高风险/破坏性动作在未授权时进入人工确认，不使用模型自行降级绕过。
- [ ] 登记本轮创建的数据、清理动作和清理验证结果；敏感值统一脱敏。
- [ ] 发布 frontier、observe、decide、execute、verify、state、transition、merge 和 blocked 事件。

## 6. 测试和验证

- [x] 为状态指纹、元素/状态去重、frontier 优先级和终止条件增加单元测试。
- [x] 为动作验证、有限重试、阻塞和恢复增加服务测试。
- [x] 为 baseline/delta 合并的 duplicate、added、updated、conflict 和幂等性增加契约测试。
- [x] 验证 Loop 模式不会改变 `goal` / `autonomous` 的现有测试和产物行为。
- [ ] 使用受控本地网站执行至少一个跨页面、弹窗、Tab、表单和分页的端到端探索。
- [ ] 验证运行取消、超时、权限阻塞、人工确认和清理失败均生成稳定结果和报告。
