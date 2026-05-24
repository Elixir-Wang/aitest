# 站点探索智能体 Playwright CLI 实施方案

## 背景

站点探索 PRD 要求探索基于 Playwright CLI、`playwright-cli` skill、探索 skill 和探索 Agent。当前系统已有探索任务 CRUD、项目环境配置、AgentRuntime 和按目录自动发现智能体的机制，但探索任务创建后只保存 `exploration_runs`，没有执行智能体、没有探索产物，也没有覆盖矩阵。

本方案补齐第一版可运行闭环：探索任务创建后由后台编排服务调用站点探索智能体边界，使用 Playwright CLI 作为唯一浏览器执行能力，生成探索文档、模块覆盖、页面事实、locator 和阻塞证据的最小产物。

## 范围

本期负责：

- 注册 `site_exploration` 站点探索智能体。
- 新增 `playwright_cli` skill，明确所有浏览器动作必须来自 Playwright CLI。
- 新增 `site_exploration` skill，明确探索文档、覆盖矩阵、locator、阻塞项输出规范。
- 新增探索产物数据表和 repository。
- 新增探索编排服务，创建标准产物目录并生成第一版可追踪产物。
- 创建探索任务后异步触发探索编排，回写 `exploration_runs.status`。

本期不负责：

- 不接完整 TaskRun/TaskEvent 表，等待任务中心基础模型落地。
- 不做验证码自动识别闭环，只记录等待人工或阻塞。
- 不生成正式知识库、正式需求文档、测试用例或自动化代码。
- 不把探索结果直接提升为业务需求。

## 设计约束

- 浏览器动作只能通过 Playwright CLI 执行，不能由模型臆造页面、字段、按钮或 locator。
- 没有 Playwright CLI 证据的内容只能作为说明，不能作为正式页面事实。
- 禁止路径只能识别和记录，不能点击执行。
- 每个探索范围内模块必须有覆盖记录。
- 无法探索必须记录原因、证据路径和建议动作。
- 密码、token、验证码不能写入日志、任务输入摘要、Markdown 或 JSON 产物。

## 智能体与 Skill

新增智能体：

- 路径：`apps/backend/app/agents/site_exploration/site_exploration_agent.py`
- ID：`site_exploration`
- Skill：`playwright_cli`、`site_exploration`

新增 Skill：

- `apps/backend/app/agents/site_exploration/skills/playwright_cli/SKILL.md`
- `apps/backend/app/agents/site_exploration/skills/site_exploration/SKILL.md`

`playwright_cli` 只描述命令能力和证据产物，不承载业务判断。`site_exploration` 承载业务探索流程、文档模板和验收规则。

## 数据模型

新增表：

- `exploration_module_coverages`
- `exploration_pages`
- `exploration_elements`
- `exploration_blockers`
- `exploration_artifacts`
- `exploration_document_versions`

扩展 `exploration_runs`：

- `artifact_root`
- `result_summary`
- `started_at`
- `finished_at`

第一版只落最小字段，后续可继续扩展字段级、操作级、状态流转级详情。

## 执行流程

1. 用户在探索页创建探索任务。
2. 后端保存 `ExplorationRun(status=queued)`。
3. FastAPI `BackgroundTasks` 调用 `site_exploration_orchestrator.run_exploration(run_id)`。
4. 编排服务加载项目、环境、探索任务。
5. 创建产物目录：
   - `storage/state.json`
   - `screenshots/`
   - `traces/`
   - `snapshots/`
   - `videos/`
   - `documents/`
   - `outputs/`
   - `logs/`
6. 检查 Playwright CLI 可用性。
7. 回写运行状态。
8. 生成首页级页面事实、模块覆盖、locator、文档和 JSON 摘要。
9. 如果 Playwright CLI 不可用，任务进入 `blocked` 并写 blocker。
10. 如果有有效产物，任务进入 `completed`；如果只有部分产物或存在阻塞，任务进入 `partial` 或 `blocked`。

## 产物目录

```text
apps/backend/data/projects/{project_id}/exploration/{run_id}/
  storage/state.json
  traces/*.zip
  screenshots/*.png
  snapshots/*.html
  videos/*.webm
  documents/exploration-v1.md
  outputs/result.json
  logs/run.log
```

## 验收标准

- `/agents` 能列出 `site_exploration`。
- `/agents/skills` 能列出该智能体下的 `playwright_cli` 和 `site_exploration`。
- 创建探索任务后会生成标准产物目录。
- 探索任务状态会从 `queued` 变为 `completed`、`partial` 或 `blocked`。
- 至少生成一条模块覆盖记录。
- 至少生成一条页面记录或一条 blocker。
- 生成探索 Markdown 和结果 JSON。
- Playwright CLI 不可用时不能假装探索成功，必须记录 blocker。

