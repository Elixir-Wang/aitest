## ADDED Requirements

### Requirement: 统一 API 响应
系统 SHALL 对 `/api/v1` 下的 API 返回统一响应结构，并且每个响应 MUST 包含 trace_id。

#### Scenario: 成功响应
- **WHEN** API 成功处理详情或操作请求
- **THEN** 系统返回包含 data 和 trace_id 的响应

#### Scenario: 列表响应
- **WHEN** API 返回列表数据
- **THEN** 系统在 data 中返回 items、pagination 和可选 filters

#### Scenario: 错误响应
- **WHEN** API 请求失败
- **THEN** 系统返回 error.code、error.message、error.detail 和 error.trace_id，且 message 为中文用户可读文案

### Requirement: available_actions
系统 SHALL 由后端根据用户、项目、对象状态和业务门禁计算 available_actions。

#### Scenario: 访客写操作禁用
- **WHEN** 访客查看项目详情
- **THEN** 系统返回查看类 enabled 动作，并返回编辑、归档、执行类 disabled 动作和禁用原因

#### Scenario: 归档项目禁止写入
- **WHEN** 用户查看已归档项目
- **THEN** 系统返回新增任务、编辑项目资产和执行类动作 disabled，禁用原因说明项目已归档

### Requirement: 权限与状态门禁
系统 SHALL 在 Service 层执行权限校验、状态门禁和事务控制。

#### Scenario: 后端拒绝越权写入
- **WHEN** 前端隐藏按钮被绕过，非授权用户直接调用写接口
- **THEN** 后端拒绝请求并返回 PERMISSION_DENIED

#### Scenario: 状态门禁失败
- **WHEN** 用户对不允许当前状态执行的对象发起操作
- **THEN** 后端拒绝请求并返回明确错误码和中文禁用原因

### Requirement: 审计事件
系统 SHALL 对高风险操作、权限相关操作和核心状态变化记录审计事件。

#### Scenario: 记录项目归档审计
- **WHEN** 管理员归档项目
- **THEN** 系统记录操作人、操作时间、对象类型、对象 ID、旧状态、新状态和 trace_id

#### Scenario: 记录用户禁用审计
- **WHEN** 管理员禁用用户
- **THEN** 系统记录用户状态变化审计事件，并阻止该用户后续登录
