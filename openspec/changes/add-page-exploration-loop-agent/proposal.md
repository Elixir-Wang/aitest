# 新增 Loop 全站探索 Agent

## 背景

当前页面探索提供 `goal` 和 `autonomous` 两种模式。两种模式都通过现有 `apps/backend/app/agents/page_exploration/` Agent 驱动浏览器操作；`autonomous` 虽然会在运行结束后检查发现元素是否执行，但页面 frontier、状态去重、动作验证、失败重试和恢复主要依赖模型上下文，无法稳定表达“整个网站探索完成”。

本变更新增一个独立的 Loop 探索 Agent 目录和显式循环编排器。Loop Agent 以页面状态图和 frontier 队列为核心，负责持续发现页面、状态和交互边，逐动作验证并生成项目级探索产物。它不改造或混入现有 `page_exploration` Agent；只复用已稳定的浏览器会话、页面快照工具、运行事件和产物注册/合并基础设施。

当项目已有页面探索产物时，Loop 运行必须先读取版本化基线，完成后按稳定键进行确定性合并。重复事实幂等更新，兼容事实补充，冲突事实保留冲突文件并将运行标记为 `partial` 或 `blocked`，不得静默覆盖已有事实。

## 目标

- 新增独立的 `apps/backend/app/agents/page_exploration_loop/` Agent 包，不复用现有页面探索 Agent 的目录、Prompt、状态类或主编排器。
- 增加 `loop` 探索模式，使用显式 frontier/state/transition 循环探索网站，而不是让单个模型隐式维护全局待办。
- 复用现有 Playwright browser session、snapshot/click/fill 工具、运行事件、页面 YAML 产物、报告注册和权限边界。
- 在每次动作后执行确定性验证，实时记录页面状态、动作边和失败原因。
- 支持状态指纹去重、预算限制、重复状态保护、超时、取消和中断恢复。
- 生成与现有项目页面探索兼容的页面、边、操作和报告产物。
- 对已有项目产物执行基线快照和确定性合并，支持 duplicate、added、updated、conflict 结果。
- 对高风险和破坏性操作提供运行策略和人工确认边界，禁止通过 Loop 默认扩大副作用范围。
- 为 Loop Agent、状态循环、合并、恢复和覆盖率提供契约测试与集成测试。

## 非目标

- 不删除、重命名或改变现有 `goal` / `autonomous` Agent 的行为。
- 不把 Loop 实现为 `page_exploration_agent(..., exploration_mode="loop")` 的 Prompt 分支。
- 第一阶段不引入多 Agent 协作；局部动作决策可使用一个模型，但全局循环由确定性编排器控制。
- 不让模型直接写页面 YAML、状态树、合并结果或任意 locator。
- 不在生产环境默认执行删除、发布、授权、清空、转账等破坏性操作。
- 不用“发现 URL 数量”替代页面状态、元素和交互覆盖率。

## 预期收益

- 全站探索进度可解释、可暂停、可恢复、可审计。
- 项目页面产物可以从多次探索中持续累积，而不会被后一次运行静默覆盖。
- 探索完成度从事后猜测变为实时可计算的 frontier/coverage 状态。
- 为后续基于 traces 的探索策略优化保留稳定事件和状态契约。
