# task-center-foundation Specification

## Purpose
TBD - created by archiving change bootstrap-ai-testing-system-foundation. Update Purpose after archive.
## Requirements
### Requirement: 任务记录
系统 SHALL 使用 TaskRun 记录所有长耗时任务，并使用 TaskEvent 记录关键过程事件。

#### Scenario: 创建任务
- **WHEN** 系统创建异步任务
- **THEN** 系统立即保存 TaskRun，返回 task_id、queued 状态、结果跳转地址和 trace_id

#### Scenario: 写入任务事件
- **WHEN** 任务创建、开始、进度更新、等待人工、失败、取消、重试或成功
- **THEN** 系统写入对应 TaskEvent，供任务详情时间线展示

### Requirement: 任务状态展示
系统 SHALL 支持 queued、running、waiting_human、success、failed、cancelled、expired 状态，并以前端中文展示。

#### Scenario: 等待人工任务
- **WHEN** 任务进入 waiting_human 状态
- **THEN** 任务详情展示等待原因、处理入口、等待时长和可继续动作

#### Scenario: 失败任务
- **WHEN** 任务进入 failed 状态
- **THEN** 任务详情展示错误码、错误摘要、日志摘要或日志路径、建议动作和重试入口

### Requirement: 任务列表与筛选
系统 SHALL 提供任务列表，并支持按项目、任务类型、状态、发起人、时间范围和是否等待人工筛选。

#### Scenario: 管理员查看任务列表
- **WHEN** 管理员打开任务中心
- **THEN** 系统返回全部项目任务，并允许按全部项目或指定项目过滤

#### Scenario: 测试工程师查看任务列表
- **WHEN** 测试工程师打开任务中心
- **THEN** 系统只返回分配项目范围内的任务

#### Scenario: 访客查看任务列表
- **WHEN** 访客打开任务中心
- **THEN** 系统返回可见任务，但取消和重试操作禁用

### Requirement: 取消与重试框架
系统 SHALL 支持对允许操作的任务请求取消和创建重试任务。

#### Scenario: 取消排队任务
- **WHEN** 有权限用户取消 queued 状态任务
- **THEN** 系统将任务标记为 cancelled，并写入取消事件

#### Scenario: 重试失败任务
- **WHEN** 有权限用户重试 failed 状态任务
- **THEN** 系统创建新的 queued TaskRun，并在新旧任务中记录 retry_from_task_id 或关联事件

#### Scenario: 成功任务不可取消
- **WHEN** 用户尝试取消 success 状态任务
- **THEN** 系统拒绝操作，并返回 TASK_NOT_CANCELLABLE

