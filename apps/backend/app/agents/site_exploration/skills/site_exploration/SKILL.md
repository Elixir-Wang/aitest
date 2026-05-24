---
name: site_exploration
display_name: 站点探索
description: 标准化站点探索流程、模块覆盖矩阵、页面事实、locator、阻塞项和探索文档输出。
enabled: true
---

# Site Exploration Skill

你负责按模块组织 Playwright CLI 采集到的页面事实，输出可审计的探索结果。你不能绕过 Playwright CLI 证据。

## 输入

- project_id、project_name。
- exploration_run_id。
- environment_id、environment_name、site_url。
- login_strategy。
- scope。
- forbidden_paths。
- artifact_root。

## 流程

1. 根据 scope 和站点菜单识别探索模块。
2. 对每个模块创建覆盖记录。
3. 使用 Playwright CLI 打开站点并采集页面事实。
4. 对页面结构、字段、操作、状态流转、依赖关系和 locator 做结构化整理。
5. 对禁止路径标记 skipped，不点击执行。
6. 对失败模块生成 blocker，包含原因、证据和建议动作。
7. 生成探索 Markdown 和结构化 JSON。

## 模块覆盖状态

- pending：已识别但未开始。
- running：正在探索。
- completed：模块入口、页面、字段、操作、状态和依赖完成采集。
- partial：部分页面或操作无法采集，但已有有效结果。
- blocked：权限、验证码、环境、路由错误、页面异常等导致无法探索。
- skipped：用户配置排除或禁止路径。

## 输出要求

探索 Markdown 必须包含：

- 探索任务摘要。
- 模块覆盖矩阵。
- 页面清单。
- 字段和操作摘要。
- locator 来源。
- 阻塞项和建议动作。
- 附件清单。

结构化 JSON 必须包含：

- status。
- summary。
- modules。
- pages。
- elements。
- blockers。
- artifacts。
- documents。

