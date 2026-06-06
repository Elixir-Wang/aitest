# 站点探索验证码与登录态方案

## 背景

站点探索任务目前已经支持在探索环境中配置登录策略，并由探索任务继承环境的登录策略。现有 Playwright runner 负责真实浏览器访问、页面采集、selector 校验和产物写入；模型只负责启动前的规划判断，不应该接触账号密码、验证码明文、cookie 或登录态文件。

本方案为探索环境补充验证码策略和登录态复用能力，使需要登录的站点可以先完成登录，再进入现有页面探索流程。

## 目标

- 探索环境支持两类登录方式：无需登录、账号密码。
- 账号密码模式下支持复用登录态，默认开启。
- 账号密码模式下支持验证码策略：无、字母 AI 校验、人工登录。
- 人工登录必须开启复用登录态，因为人工登录的产物是保存 `storageState`。
- 无需登录时不显示用户名、密码、复用登录态和验证码策略。
- 模型只接收登录策略摘要，不接触账号密码、验证码结果或登录态文件。
- Playwright runner 在探索前完成登录态加载、自动登录或人工登录态复用。

## 非目标

- 不做通用验证码破解能力。
- 不支持短信验证码、滑块验证码、图片点选验证码等复杂人机校验自动识别。
- 不把账号密码、验证码明文、cookie、storage state 暴露给前端下载、探索报告或运行日志。
- 不把人工登录作为顶层登录方式；它是账号密码模式下的一种验证码/登录辅助策略。
- 不把 `auth_state_path` 作为用户配置字段。
- 不把 `auth_state_saved_at` 作为必需数据库字段；如需展示上次保存时间，可先从文件修改时间推导。

## 概念模型

### 环境配置字段

```text
login_strategy:
- skip_login        无需登录
- account_password  账号密码

reuse_auth_state: boolean
- 仅 account_password 下有效
- 默认 true

captcha_strategy:
- none       无
- ai_letter  字母验证码，AI 校验
- manual     人工登录
```

### 系统派生字段

```text
auth_state_status:
- none      未保存
- valid     已保存且可复用
- expired   已保存但检测失效
- unknown   暂未检测
```

`auth_state_status` 不由用户选择。后端根据环境登录方式、登录态文件是否存在、必要时的轻量检测结果返回给前端。

登录态路径由后端内部推导，不入库、不展示：

```text
PROJECT_FILE_STORAGE_ROOT/{project_id}/environments/{environment_id}/auth/storage-state.json
```

## UI 规则

### 无需登录

当 `login_strategy = skip_login`：

- 隐藏用户名。
- 隐藏密码。
- 隐藏复用登录态。
- 隐藏验证码策略。
- 提交时后端强制归一：
  - `username = ""`
  - `password` 不保存
  - `reuse_auth_state = false`
  - `captcha_strategy = none`

### 账号密码

当 `login_strategy = account_password`：

- 显示用户名。
- 显示密码。
- 显示复用登录态，默认开启。
- 显示验证码策略。
- 新建环境时用户名和密码必填。
- 编辑环境时用户名必填；密码不填表示沿用已保存凭据。

验证码策略选项受 `reuse_auth_state` 控制：

```text
reuse_auth_state = true
  可选：无 / 字母 AI 校验 / 人工登录

reuse_auth_state = false
  可选：无 / 字母 AI 校验
  如果当前已选人工登录，前端自动重置为无
```

前端应直接隐藏不可选的“人工登录”选项，后端也必须校验接口绕过场景。

## 后端校验规则

合法值：

```text
LOGIN_STRATEGIES = {"skip_login", "account_password"}
CAPTCHA_STRATEGIES = {"none", "ai_letter", "manual"}
```

校验规则：

```text
login_strategy = skip_login:
  captcha_strategy 必须归一为 none
  reuse_auth_state 必须归一为 false
  username/password 清空

login_strategy = account_password:
  username 必填
  新建时 password 必填
  captcha_strategy 必须合法

captcha_strategy = manual:
  reuse_auth_state 必须为 true
```

当前环境表只保存 `password_mask`，runner 无法用它自动登录。实现账号密码自动登录前，需要补充受控凭据存储能力。接口仍只返回 `password_mask`，真实密码只能由后端在启动 runner 时解密并注入执行环境。

## 执行流程

### 无需登录

```text
run 启动
  -> runner 直接打开 site_url
  -> 进入现有探索循环
```

### 账号密码且可复用登录态

```text
run 启动
  -> 后端推导 auth_state_path
  -> 如果 reuse_auth_state=true 且登录态文件可用
      runner 加载 storageState
      进入探索循环
  -> 否则进入账号密码登录流程
```

### 账号密码登录，无验证码

```text
runner 打开登录页或 site_url
  -> 填写用户名、密码
  -> 提交登录
  -> 如检测到验证码，写入 captcha_required blocker
  -> 登录成功后，如果 reuse_auth_state=true，保存 storageState
  -> 进入探索循环
```

### 字母 AI 校验

```text
runner 打开登录页或 site_url
  -> 填写用户名、密码
  -> 定位验证码图片或验证码区域
  -> 截图保存为受控临时证据
  -> 调用后端 captcha_solver
  -> 后端调用多模态模型识别字母验证码
  -> runner 填写验证码并提交
  -> 最多重试 2-3 次
  -> 登录成功后，如果 reuse_auth_state=true，保存 storageState
  -> 进入探索循环
```

失败处理：

- 识别失败、验证码定位失败或登录失败时，写入 `captcha_required` 或 `login_required` blocker。
- 可以保存验证码截图作为阻塞证据，但不得在日志、报告、yaml 中写入验证码明文。

### 人工登录

```text
前端点击「手动登录并保存状态」
  -> 后端启动 headed Playwright 登录会话
  -> 用户在真实浏览器窗口完成账号密码、验证码和二次验证
  -> 前端点击「已完成登录，保存登录态」
  -> 后端调用 context.storageState() 保存到内部 auth_state_path
  -> 后续探索任务复用该登录态
```

人工登录仅在 `account_password + reuse_auth_state=true + captcha_strategy=manual` 下可用。

本地开发环境可先使用本机 headed browser。若后续部署到服务器，需要单独设计远程浏览器视图或登录态采集服务。

## Runner 输入边界

模型输入只允许包含登录前置摘要，例如：

```text
login_strategy: account_password
reuse_auth_state: true
captcha_strategy: ai_letter
has_login_credentials: true
```

模型不得接收：

- 用户名。
- 密码。
- 验证码识别结果。
- cookie。
- storage state 路径或内容。

后端启动 runner 时可通过受控环境变量注入执行信息：

```text
AI_TESTING_LOGIN_STRATEGY
AI_TESTING_REUSE_AUTH_STATE
AI_TESTING_CAPTCHA_STRATEGY
AI_TESTING_LOGIN_USERNAME
AI_TESTING_LOGIN_PASSWORD
AI_TESTING_AUTH_STATE_PATH
```

runner 日志必须脱敏，不得输出密码、验证码明文、cookie 或 storage state 内容。

## 安全与审计

- 字母 AI 校验仅用于自有或授权测试环境。
- 失败时记录“验证码识别失败/登录失败”等摘要，不记录验证码明文。
- `storageState` 是敏感资产，只允许后端内部读取。
- 删除环境时应同步删除对应登录态文件。
- 修改账号、密码、登录方式或验证码策略时，应将旧登录态标记为失效或删除。
- 运行产物中只允许出现登录状态摘要和 blocker，不允许出现凭据内容。

## 数据与接口影响

### 旧值兼容

现有后端曾支持：

```text
login_strategy:
- reuse_state
- manual
- account_password
- skip_login
```

本方案实施后，顶层登录方式只保留 `skip_login` 和 `account_password`。旧值迁移规则：

```text
reuse_state:
  login_strategy = account_password
  reuse_auth_state = true
  captcha_strategy = none

manual:
  login_strategy = account_password
  reuse_auth_state = true
  captcha_strategy = manual
```

迁移后，前端不再展示 `reuse_state` 和 `manual` 作为登录方式；后端接口如收到旧值，应在过渡期按上述规则归一，或在迁移完成后返回明确错误。

### project_environments

新增字段建议：

```text
captcha_strategy TEXT NOT NULL DEFAULT 'none'
reuse_auth_state INTEGER NOT NULL DEFAULT 1
password_secret TEXT NOT NULL DEFAULT ''
```

`password_secret` 需要加密或使用本地安全存储；若暂时没有加密能力，应先实现手动登录态保存，不启用账号密码自动登录。

### 环境 API

环境响应新增派生字段：

```text
captcha_strategy
reuse_auth_state
auth_state_status
auth_state_updated_at  可选
```

环境创建/更新请求新增：

```text
captcha_strategy
reuse_auth_state
password
```

响应仍只返回：

```text
password_mask
```

不返回 `password_secret`。

## 测试要求

- 无需登录时，前端隐藏用户名、密码、复用登录态和验证码策略。
- 无需登录提交后，后端清空登录字段并归一验证码策略。
- 账号密码模式默认开启复用登录态。
- 关闭复用登录态时，前端不能选择人工登录。
- 接口绕过提交 `manual + reuse_auth_state=false` 时，后端返回明确错误。
- 编辑环境时不输入新密码不会清空既有凭据。
- 修改登录配置后旧登录态失效。
- 手动登录保存后，后续探索可复用 `storageState`。
- 字母验证码识别失败时产生 blocker，不静默跳过。
- 日志、报告和 yaml 产物不包含密码、cookie、验证码明文。

## 分阶段实施建议

1. 环境字段、校验和 UI 显隐规则。
2. 登录态路径推导、状态展示、删除/失效处理。
3. 手动登录并保存状态。
4. 账号密码无验证码自动登录。
5. 字母验证码 AI 校验。
