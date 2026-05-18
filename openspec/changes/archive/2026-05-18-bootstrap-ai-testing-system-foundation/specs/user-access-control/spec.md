## ADDED Requirements

### Requirement: 登录与当前用户
系统 SHALL 提供登录、退出和当前用户查询能力，并且 MUST 不提供公开注册入口。

#### Scenario: 管理员创建账号后用户登录
- **WHEN** 管理员创建启用状态的用户账号，并且用户使用正确用户名或邮箱和密码登录
- **THEN** 系统返回当前用户信息、角色、可见项目范围和 `trace_id`

#### Scenario: 禁用用户不能登录
- **WHEN** 禁用状态用户提交正确账号和密码
- **THEN** 系统拒绝登录，并返回不泄露账号存在性的中文错误信息

#### Scenario: 未登录访问业务页面
- **WHEN** 未登录用户访问后台业务页面
- **THEN** 前端跳转登录页，后端业务 API 返回 AUTH_REQUIRED 错误

### Requirement: 三类角色权限
系统 SHALL 只支持 管理员、测试工程师、访客 三类角色，且 MUST 由后端执行权限校验。

#### Scenario: 管理员拥有全量权限
- **WHEN** 管理员访问项目、任务、用户与系统设置
- **THEN** 系统允许查看全部数据，并返回可写操作的 enabled available_actions

#### Scenario: 测试工程师只能访问分配项目
- **WHEN** 测试工程师查询项目和项目任务
- **THEN** 系统只返回已分配项目及其任务

#### Scenario: 访客全局只读
- **WHEN** 访客访问管理员可见的项目、任务和配置页面
- **THEN** 系统允许查看脱敏信息，并且所有写操作 available_actions 均为 disabled

### Requirement: 用户管理
系统 SHALL 允许管理员创建、编辑、启用、禁用用户，并为测试工程师分配项目。

#### Scenario: 管理员创建用户
- **WHEN** 管理员提交唯一用户名、唯一邮箱、初始密码、昵称、角色和状态
- **THEN** 系统创建用户，密码以哈希形式保存，并记录审计事件

#### Scenario: 非管理员不能创建用户
- **WHEN** 测试工程师或访客调用创建用户接口
- **THEN** 系统拒绝请求并返回 PERMISSION_DENIED

#### Scenario: 用户名或邮箱重复
- **WHEN** 管理员提交已存在的用户名或邮箱
- **THEN** 系统拒绝创建并返回字段级错误详情
