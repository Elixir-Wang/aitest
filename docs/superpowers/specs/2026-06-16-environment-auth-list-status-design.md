# 环境列表登录态展示与自动登录日志设计

## 目标

保存「字母 AI 校验」环境后关闭弹窗回到列表；列表「登录态」列在自动登录进行中显示转圈「登录中」，成功后显示「有效」，失败显示红色「登录失败」；失败与成功均写入系统操作日志。

## 展示状态派生

`auth_state_status` 对用户展示合并 `auto-login-status.json` 与 `storage-state.json`：

| 条件 | auth_state_status | 说明 |
|------|-------------------|------|
| 非账号密码或未复用登录态 | none | 不变 |
| auto_auth ∈ queued, running | logging_in | 列表转圈 |
| auto_auth = failed | login_failed | 红色，与 expired 区分 |
| 否则 | valid / expired / none | 由文件推导 |

新增 `auth_state_message` 供 Tooltip（进度或失败原因）。

## 前端交互

- 保存 ai_letter 环境 → 关弹窗 → 列表行 logging_in
- 工作区级轮询环境列表（存在 logging_in 时每 2s）
- 成功 Toast + 列表变 valid；失败 Toast + login_failed

## 系统日志

`auto_auth_service` 在自动登录成功/失败时调用 `operation_log_service.record_task_event`：

- module: environment
- action: auto_auth_login
- result: success | failed
- failure_reason: 错误码摘要（不含密码/验证码明文）
