# 站点探索模块进度重构规范

## 背景

当前探索详情页的“探索模块进度”虽然按模块展示，但每一行的描述几乎完全相同，核心原因是模块级摘要直接复用 run 级总摘要，模块之间缺少独立的页面覆盖、最近页面和阻塞信息。结果是模块进度看起来像重复的运行状态列表，而不是业务模块覆盖视图。

本规范定义一次彻底重构：把探索模块进度从“总摘要复用展示”改成“按业务模块聚合的覆盖视图”，并同步调整后端产物、详情接口和前端渲染。

## 目标

- 探索模块进度按业务模块聚合展示，不再复用 run 级摘要。
- 每个模块具备独立的页面进度、最近页面、阻塞说明和进度百分比。
- 模块状态由页面事实、阻塞事实和覆盖情况共同计算。
- 全站/全部探索场景下，模块来源优先来自页面事实分组，而不是单一 run 摘要。
- 前端展示保持 `AgentPlan` 容器，但模块描述和展开内容必须有明显差异。
- 接口和数据结构向后兼容，旧 run 仍可读取，但新 run 使用新聚合逻辑。

## 非目标

- 不重做探索 runner 的采集流程。
- 不把 YAML、edge、path 等内部技术产物直接暴露成模块进度主字段。
- 不新增独立的“进度解释器”页面。
- 不要求历史 run 全量回填重算。
- 不把日志页改造成模块进度页。

## 当前问题

现状存在三类问题：

1. 模块描述重复
   - 模块行使用同一份 `completion_summary`，导致每个模块看起来一样。
2. 模块粒度不足
   - 现有聚合更像“一个 run 对应一个模块”，没有真正按页面归属拆分模块。
3. 展示信息不够稳定
   - 前端需要自己拼接模块状态时，容易依赖自然语言摘要，导致表达不一致。

## 重构原则

1. 模块是一级聚合单元，不是 run 摘要的别名。
2. 页面事实是模块进度的唯一依据。
3. 状态、进度、阻塞、最近页面必须分字段表达。
4. 文案可以 human-readable，但不能承载唯一语义。
5. 旧字段可保留，新增字段优先供前端使用。

## 设计方案

### 1. 模块聚合来源

完成一次探索后，后端按页面事实聚合模块，而不是只写一个总模块。

模块来源优先级：

1. 页面 YAML 中的 `page.module`
2. 页面事实中的 `module_key`
3. 探索计划中的模块清单
4. 兜底为 `unclassified`

### 2. 模块进度字段

每个模块至少具备以下字段：

| 字段 | 含义 |
| --- | --- |
| `module_key` | 模块唯一键 |
| `module_name` | 模块展示名 |
| `entry_path` | 模块入口或首个入口路径 |
| `planned_page_count` | 计划页面数 |
| `explored_page_count` | 已探索页面数 |
| `blocked_page_count` | 阻塞页面数 |
| `action_count` | 动作数 |
| `field_count` | 字段数 |
| `state_transition_count` | 状态变化数 |
| `completion_status` | 模块状态 |
| `completion_summary` | 模块摘要 |
| `recent_page_title` | 最近页面标题 |
| `recent_page_url` | 最近页面 URL |
| `blocker_summary` | 主要阻塞说明 |
| `progress_percent` | 进度百分比 |

### 3. 状态规则

| 状态 | 规则 |
| --- | --- |
| `pending` | 已纳入计划，但没有页面事实 |
| `running` | 有页面事实，且 run 仍在执行中 |
| `completed` | 页面均已覆盖，且无关键阻塞 |
| `partial` | 有页面事实，但存在未覆盖、跳过或非关键阻塞 |
| `blocked` | 存在登录、权限、验证码、超时或安全策略类关键阻塞 |

### 4. 摘要生成规则

模块摘要不得直接复用 run 总摘要，应由模块事实生成，例如：

- `已覆盖 5/5 个页面，最近页面：编辑用户，无阻塞。`
- `已覆盖 3/5 个页面，最近页面：角色详情，1 个页面阻塞：当前账号无权限。`
- `已纳入探索计划，等待探索执行。`

### 5. 进度百分比规则

建议计算方式：

```text
progress_percent = explored_page_count / max(planned_page_count, explored_page_count, 1)
```

含义：

- 有计划页数时，以计划页数为分母。
- 没有计划页数时，以已发现页数作为分母兜底。
- 保证不会出现除零。

## 数据契约

### 详情接口

接口仍使用：

```http
GET /api/v1/projects/{project_id}/exploration-runs/{run_id}/detail
```

`modules[]` 中的每个模块需要支持上述字段。旧字段 `completion_summary` 保留，新字段逐步被前端采用。

### 页面事实

页面对象保持原有结构，但模块聚合时必须优先读取：

- `page.module`
- `page.page_type`
- `page.status`
- `page.recent_event`
- `page.blocker_reason`

### SSE 增量

模块更新事件仍可沿用现有事件通道，但模块 payload 需要携带新字段，避免前端依赖摘要猜测：

- `recent_page_title`
- `recent_page_url`
- `blocker_summary`
- `progress_percent`

## 前端展示

### 模块行

模块行展示顺序建议为：

`模块名称 | 状态 | 页面进度 | 最近页面 | 阻塞说明 | 进度`

其中：

- 状态使用 badge。
- 页面进度展示 `已探索/计划`。
- 最近页面只展示一个短标题。
- 阻塞说明无阻塞时显示“无”。
- 进度使用百分比或细条进度条。

### 展开详情

展开模块后，展示页面列表：

`页面标题 | 页面类型 | URL | 状态 | 阻塞说明 | 最近事件`

页面层不再承担模块摘要职责。

### AgentPlan 约束

`AgentPlan` 仍可作为容器，但：

- 一级节点必须是模块。
- 二级节点必须是页面。
- 模块描述必须来自模块事实拼接，而不是 run 总摘要。
- 页面描述必须来自页面事实，而不是模块摘要重复。

## 后端改造范围

### 1. 重新实现模块聚合

在探索完成持久化阶段，按页面事实生成多个模块覆盖记录。

### 2. 扩展模块覆盖构建逻辑

建议抽出纯函数，负责：

- 页面按模块分组
- 最近页面选择
- 阻塞归因
- 进度百分比计算
- 模块摘要生成

### 3. 保留旧摘要字段

`completion_summary` 继续保留，作为兼容字段，但其内容必须由模块级事实生成。

### 4. 更新测试

需要新增或调整测试覆盖：

- 模块按页面分组
- 模块摘要不再全部相同
- 阻塞模块能输出阻塞说明
- 进度百分比计算正确
- 前端详情接口能读取新字段

## 迁移策略

1. 新建逻辑优先用于新探索 run。
2. 历史 run 继续按旧聚合读取，不做强制回填。
3. 前端先兼容旧字段，再逐步切换到新字段。
4. 旧摘要字段保留一个版本窗口，确认稳定后再决定是否收窄。

## 验收标准

- 详情页中不同模块的摘要不再完全一致。
- 每个模块都能看到自己的页面进度、最近页面和阻塞说明。
- 进度为 0 的模块不会伪装成已完成。
- 阻塞模块能明确显示阻塞原因。
- 页面层信息与模块层信息不重复承担同一职责。
- 旧 run 不会因为字段缺失导致接口报错。

## 相关文件

- [site_exploration_orchestrator.py](/Users/wanghongbao/project/test_project/apps/backend/app/services/site_exploration_orchestrator.py)
- [exploration_service.py](/Users/wanghongbao/project/test_project/apps/backend/app/services/exploration_service.py)
- [exploration.py](/Users/wanghongbao/project/test_project/apps/backend/app/schemas/exploration.py)
- [page.tsx](/Users/wanghongbao/project/test_project/apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx)
- [site-exploration-flow-artifacts-spec.md](/Users/wanghongbao/project/test_project/docs/superpowers/specs/2026-05-29-site-exploration-flow-artifacts-spec.md)

