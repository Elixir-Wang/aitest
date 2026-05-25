---
name: site_exploration
display_name: 站点探索
description: 标准化站点探索流程、模块覆盖矩阵、页面事实、locator、需求映射、冲突项、阻塞项和探索文档输出。
enabled: true
---

# Site Exploration Skill

你负责按模块组织 Playwright CLI 采集到的页面事实，输出可审计的探索结果。你不能绕过 Playwright CLI 证据。

站点探索是页面事实来源，不是正式需求、正式知识库、正式测试用例或自动化代码生成器。探索结果可以补充 PRD/需求文档、知识库、测试用例和 UI 自动化的输入，但不能直接把页面发现提升为已确认业务规则。

## 输入

- project_id、project_name。
- exploration_run_id。
- environment_id、environment_name、site_url。
- login_strategy。
- scope。
- forbidden_paths。
- artifact_root。
- 可选：requirements_context、prd_context、knowledge_context、known_modules。

## 来源边界

- PRD/需求文档负责业务意图、业务规则、流程预期和验收口径。
- 站点探索负责真实页面结构、字段展示、按钮、弹窗、提示语、状态回显、真实操作路径和 locator。
- 如果页面事实与 PRD/需求文档不一致，生成冲突项，不要自行判断谁正确。
- 如果 PRD/需求中存在但页面未发现，标记为待探索或页面缺失。
- 如果页面中存在但 PRD/需求未描述，标记为需求缺口。
- 如果项目没有需求文档，探索结果只能作为候选需求文档来源；候选内容必须标记观察、推断或待确认。
- 探索文档不能自动进入正式知识库，必须经过知识库生成/更新流程显式选择和准入检查。

## 流程

1. 根据 scope 和站点菜单识别探索模块。
2. 如果有 PRD/需求上下文，先建立需求模块到探索模块的初始映射。
3. 对每个模块创建覆盖记录。
4. 使用 Playwright CLI 打开站点并采集页面事实。
5. 对页面结构、字段、操作、状态流转、依赖关系和 locator 做结构化整理。
6. 对禁止路径标记 skipped，不点击执行。
7. 对失败模块生成 blocker，包含原因、证据和建议动作。
8. 生成探索 Markdown 和结构化 JSON。

## 模块覆盖状态

- pending：已识别但未开始。
- running：正在探索。
- completed：模块入口、页面、字段、操作、状态和依赖完成采集。
- partial：部分页面或操作无法采集，但已有有效结果。
- blocked：权限、验证码、环境、路由错误、页面异常等导致无法探索。
- skipped：用户配置排除或禁止路径。

## 页面事实采集要求

每个页面、弹窗、抽屉、Tab、详情页和子页面都要尽量记录：

- 页面标题、URL、入口路径、所属模块。
- 可见字段、控件类型、必填、默认值、placeholder、枚举值、校验提示。
- 按钮、链接、行操作、批量操作、禁用动作和条件显示动作。
- 成功提示、失败提示、确认弹窗正文、空状态和状态标签。
- 状态流转、前置条件、依赖数据和外部服务。
- 关键元素 locator 来源：语义名称、推荐 locator、备用 locator、稳定性、来源证据。

没有 Playwright CLI 快照、截图、trace、video、页面文本或操作记录支撑的内容，只能标记为说明、推断或待确认。

## locator 准入规则

关键 UI 元素必须给出 locator 来源材料：

- 推荐 locator 优先使用 role/name、label、placeholder、test id、稳定业务文本。
- 备用 locator 可以使用局部上下文、表格行唯一字段或父子层级。
- 不要使用动态 ID、纯序号、易变样式或 AI 生成大段文本作为稳定 locator。
- 如果 locator 不足，标记为 `needs_locator`，并说明缺少页面、操作路径还是元素证据。
- UI 自动化生成只能复用已确认或稳定的 locator；缺失关键 locator 时只能触发定向探索定位。

## 需求映射与冲突项

如果输入包含 PRD/需求上下文，输出必须包含模块映射和冲突项。

映射状态：

- mapped：探索模块已映射到需求模块。
- requirement_not_found_in_page：需求中有但页面未发现。
- page_not_found_in_requirement：页面中有但需求未描述。
- conflict：字段、状态、流程、权限、提示语或 locator 与需求不一致。
- pending_confirm：证据不足，需要人工确认。

冲突项必须包含：

- conflict_id。
- module。
- requirement_source。
- exploration_source。
- conflict_type。
- description。
- impact_scope：知识库、测试用例、自动化、缺陷判断。
- suggested_question。
- status：pending_confirm。

冲突未确认前，不得写入已确认知识库事实，不得作为正式测试预期。

## 下游可用性判断

每个模块都要给出下游可用性结论：

- knowledge_ready：是否可作为知识库页面事实来源；若核心模块阻塞、关键冲突未确认或候选需求未确认，则为 false。
- testcase_ready：是否可用于正式测试用例生成；若知识库未发布或关键预期缺失，则为 false。
- automation_ready：是否可进入 UI 自动化准入；若关键 locator 缺失或核心流程无法闭环，则为 false。
- required_actions：补充探索、人工确认、生成候选需求、补 locator、处理冲突等。

## 输出要求

探索 Markdown 必须包含：

- 探索任务摘要。
- 模块覆盖矩阵。
- 页面清单。
- 字段和操作摘要。
- locator 来源。
- 需求映射、需求缺口、待探索项和冲突项。
- 知识库、测试用例、UI 自动化下游可用性判断。
- 阻塞项和建议动作。
- 附件清单。

结构化 JSON 必须包含：

- status。
- summary。
- modules。
- pages。
- elements。
- mappings。
- conflicts。
- blockers。
- artifacts。
- documents。
- downstream_readiness。

## Markdown 文档建议结构

```markdown
# 站点探索报告

## 1. 探索任务摘要
## 2. 模块覆盖矩阵
## 3. 页面事实
## 4. locator 来源材料
## 5. 需求映射与冲突项
## 6. 下游可用性判断
## 7. 阻塞项与建议动作
## 8. 附件清单
```

## 质量门禁

- 探索范围内每个模块都必须有覆盖状态。
- 禁止路径必须标记 skipped，不能点击执行。
- 无法探索必须生成 blocker，不能静默跳过。
- 页面事实必须有 Playwright CLI 证据。
- 页面事实和需求规则必须分开写。
- 关键元素必须有 locator 来源或 `needs_locator` 缺口。
- 有 PRD/需求上下文时，必须输出映射和冲突项。
- 输出必须说明知识库、测试用例、UI 自动化三个下游环节是否可用。

