## ADDED Requirements

### Requirement: 系统设置入口
系统 SHALL 提供文件存储、本地 Runner、Playwright、Allure 和 Agent 安全策略的基础配置入口。

#### Scenario: 管理员查看系统设置
- **WHEN** 管理员打开系统设置页面
- **THEN** 系统展示文件存储、本地 Runner、Playwright、Allure、Agent 安全策略配置 Tabs

#### Scenario: 非管理员查看系统设置
- **WHEN** 测试工程师或访客打开系统设置页面
- **THEN** 系统只展示允许查看的脱敏配置，并禁用保存操作

### Requirement: 配置保存和脱敏
系统 SHALL 允许管理员保存基础配置，并且 MUST 对敏感值脱敏返回。

#### Scenario: 管理员保存存储根目录
- **WHEN** 管理员提交文件存储根目录
- **THEN** 系统保存配置，并校验后续文件路径必须位于该根目录内

#### Scenario: 敏感值脱敏
- **WHEN** 用户查询包含密钥、token、密码或验证码相关配置
- **THEN** 系统不得返回明文敏感值

### Requirement: 可用性检查占位
系统 SHALL 提供本地 Runner、Playwright、Allure 和 Agent 安全策略的检查入口，但第一阶段不 MUST 执行真实 Agent 编排。

#### Scenario: 执行 Playwright 配置检查
- **WHEN** 管理员点击 Playwright 检查
- **THEN** 系统返回检查任务或检查结果占位，并记录 trace_id

#### Scenario: Agent Runtime 真实编排不在范围
- **WHEN** 用户尝试发起真实 Agent 模型调用或 Skill 调度
- **THEN** 系统展示暂未启用或后续接入说明，不执行真实编排
