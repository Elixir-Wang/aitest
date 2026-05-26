# 亦庄登录sso

## 需求概述

建设统一登录认证授权中心，实现官网统一身份入口，支持百系产品通过标准化 SSO 票据链路接入。认证中心负责用户注册、登录、统一 UID 管理、票据签发、UserInfo 服务、业务上下文透传和登录审计；各产品继续负责本地账号、本地 Session、租户、角色、权限、邀请码和企业标识等业务逻辑。首期采用 login_ticket + UserInfo + 本地 Session 的最小接入模式，不强制迁移存量登录入口。

## 登录认证

### 官网注册与登录

- 用户可通过手机号或邮箱在官网完成注册与登录。
- 官网维护用户登录态，并为用户生成全局唯一的 unified_uid。
- 找回密码功能支持手机号或邮箱方式。

### 用户身份信息 (UserInfo)

- 票据校验成功后，认证中心向产品后端返回可信用户身份信息。
- UserInfo 包含：unified_uid、user_type（UNKNOWN/C/B/B+C，仅作参考）、脱敏手机号、手机号验证状态、邮箱、邮箱验证状态、昵称、头像、注册来源、身份上下文列表（identity_contexts）。
- 默认返回脱敏手机号；产品如需完整手机号/邮箱，需在接入配置中申请并遵循最小必要原则。
- user_type 不代表用户在某产品内拥有 B 端或 C 端权限，产品侧需基于本地策略自行判断。
- 用户状态（account_status）在响应中返回，可取值为 ACTIVE、DISABLED、CANCELLED。

### 产品进入前状态查询

- 提供接口供前端判断用户是否已完成指定产品的首次接入（NOT_CONNECTED / CONNECTED）。
- 认证中心维护轻量状态：针对每个 unified_uid 和 product_code，记录其首次接入状态。
- 当产品配置为需要邀请码且用户未连接时，前端展示邀请码输入弹窗；否则直接生成 ticket。

## 产品接入配置

### 接入登记与配置

- 各产品接入前必须填写产品接入配置表，包含 product_code、product_name、product_owner、tech_owner、product_user_mode、product_domain、sso_entry_url、allowed_redirect_domains、logout_callback_url（可选）、legacy_login_keep、allow_auto_create_user、require_enterprise_email（可选）、require_enterprise_code（可选）、require_invite_code（可选）、support_default_role、default_role（可选）、no_account_action、support_context_register（可选）、support_third_party_bind（可选）、local_user_key、local_tenant_key（可选）、remark（可选）。
- product_code 全局唯一。
- no_account_action 枚举值包括：AUTO_CREATE（自动创建本地账号，C 端推荐）、GUIDE_APPLY（引导用户申请开通）、LEAD_FORM（跳转留资表单，B 端推荐）、CONTACT_ADMIN（提示联系企业管理员）、NEED_INVITE_CODE（邀请制产品，无邀请码不放行）、SELECT_PERSONAL_OR_ENTERPRISE（B+C 产品，引导用户选择个人或企业身份）。
- 认证中心侧配置 product_code、sso_entry_url、allowed_redirect_domains 等信息。

### 产品用户模式

- 产品用户模式分为：C（面向个人用户）、B（面向企业客户）、B+C（同时支持个人和企业用户）、INVITE_ONLY（邀请制或灰度开放）、UNKNOWN（待确认）。
- 不同模式的准入原则：
    - C 模式：官网注册后可尝试直接进入，若产品允许则自动创建或绑定本地账号。
    - B 模式：不建议直接进入，需有本地账号和权限方可进入；否则引导留资、申请试用或联系管理员。
    - B+C 模式：视用户意图和产品策略分流，进入个人空间或企业空间，可要求企业代码或企业邮箱。
    - INVITE_ONLY 模式：不允许无邀请码直接进入，必须由产品侧校验邀请码。
    - UNKNOWN 模式：不开放自动进入，默认引导留资或人工确认。

## SSO 票据与跳转

### login_ticket 生成 (ticket/create)

- 用户在官网已登录后，官网向认证中心申请产品登录票据。该接口由官网服务端调用，不直接暴露给产品前端。
- 必须参数：product_code、state（防 CSRF）。可选参数：return_url、source、campaign、biz_context、context_id。
- biz_context 与 context_id 可二选一；复杂业务场景推荐使用 context_id。
- 票据在生成时必须绑定：product_code、unified_uid、state、return_url、biz_context/context_id、expires_at、used_status。

### 官网跳转产品 (sso_entry_url)

- 官网获取 login_ticket 后，跳转至产品提供的 sso_entry_url，URL 参数包含 login_ticket、state、source（可选）。
- 不建议在 URL 中直接携带完整 biz_context；return_url 和 biz_context 应在 ticket 生成阶段绑定。
- 产品侧收到请求后必须：
    1. 不直接信任 login_ticket；
    2. 将 login_ticket 发送到产品后端；
    3. 产品后端调用 ticket 校验接口；
    4. 校验成功后获取 UserInfo + account_status + biz_context；
    5. 产品按本地策略判断是否允许进入；
    6. 产品创建本地 session；
    7. 清理 URL 中的 login_ticket，避免泄露。

### login_ticket 校验 (ticket/verify)

- 产品后端使用 login_ticket 调用认证中心，换取可信用户身份信息。该接口必须由产品后端调用，不允许产品前端直接调用。
- 必须参数：product_code、login_ticket、state。建议参数：nonce（防重放）、timestamp。
- 产品不应在校验时提交 return_url、biz_context、invite_code 等字段；这些应在 ticket 生成阶段绑定。
- 响应包含：verified、ticket_status、account_status、user_info、product_context（product_code、product_user_mode、entry_scene）、return_url、biz_context、issued_at、expires_at。
- 票据规则：
    - 一次性：只能使用一次，校验成功后立即置为 used。
    - 短时效：建议 3～5 分钟。
    - 产品绑定：只能被指定 product_code 使用。
    - 用户绑定：绑定生成时的 unified_uid。
    - 上下文绑定：绑定 return_url / biz_context / context_id。
    - 后端校验：只能由产品后端调用。
    - 不可复用、不可长期保存、不可作为 session。

### 首次接入确认

- 产品后端在用户首次成功接入（如验证邀请码通过）后，通过接口回调认证中心，标记用户对该产品的接入状态为 CONNECTED。
- 鉴权使用 product_access_key，必须属于请求体中的 product_code。
- 认证中心维护 auth_product_user_access 表，记录 product_code、unified_uid、access_status、bind_source、首次连接时间和最近连接时间。
- 不存储邀请码、local_user_id、local_tenant_id、权限等信息。

## 业务上下文透传

### 上下文预注册 (context/register)

- 用于产品深链、面试链接、专家邀请、小程序跳转等场景。产品可先把业务上下文注册到认证中心，认证中心返回 context_id，后续官网使用 context_id 申请 login_ticket。
- 必须参数：product_code、scene、return_url。可选参数：biz_context、expire_minutes（默认 30 分钟）。
- 设计约束：
    - context_id 短时有效。
    - context_id 绑定 product_code，不能跨产品复用。
    - biz_context 不承载敏感明文。
    - 认证中心只保存和返回上下文，不解释产品业务含义。

### biz_context 使用

- biz_context 用于传递邀请码、推荐码、专家邀请、灰度准入、面试链接、活动来源等业务上下文。
- 简单上下文可放 biz_context；复杂上下文建议通过 context_id 预注册。
- 上下文应在 login_ticket 生成阶段绑定；产品校验 ticket 时不应重新提交上下文作为可信来源。
- 认证中心只负责保存和透传，不判断业务有效性，产品负责最终业务校验。

## 产品本地账号映射

### 映射要求

- 通过官网统一认证中心进入产品的用户，建议都建立或复用 unified_uid ↔ local_user_id 映射。
- 推荐映射字段：id、product_code、unified_uid、local_user_id、local_tenant_id（可选）、bind_type（auto/manual/created/invite/enterprise）、bind_status（bound/pending/conflict/disabled）、bind_source、first_bind_time、last_login_time、created_at、updated_at。
- 首次进入处理规则：
    1. 按 unified_uid 查本地映射；
    2. 若有映射，直接建立本地 session；
    3. 若无映射，按手机号/邮箱/企业标识/ openid/ unionid 查询本地用户；
    4. 若唯一命中，自动绑定或提示确认绑定；
    5. 若未命中，按产品策略创建本地账号或提示申请开通；
    6. 若多账号冲突，进入人工处理。

### 产品侧本地 Session

- 产品不能直接把 login_ticket 当作登录态，必须在校验成功后自行创建本地 session。
- 推荐 session 内容：local_user_id、unified_uid、local_tenant_id、role、permissions、login_source、login_time、session_expire_time。

## 邀请码与准入控制

### 邀请码处理规则

- 邀请码属于产品业务准入机制，由产品生成和校验。认证中心只负责接收、保存、绑定到 login_ticket、返回给产品，不判断业务有效性。
- 对于邀请制产品（如百工），用户若从官网普通入口进入且无邀请码，产品需提示需要邀请码、展示申请入口、加入候补名单、分配受限角色或提示暂未开放。
- 产品后端收到 invite_code 后自行校验有效性，有效则创建本地用户并建立 Session，同时可回调确认接口标记首次接入状态。

### 准入结果枚举

- 产品侧建议统一定义准入结果，方便前端提示与测试验收。推荐的 code 包括：ACCESS_GRANTED、NEED_BINDING_CONFIRM、NEED_ENTERPRISE_EMAIL、NEED_ENTERPRISE_CODE、NEED_INVITE_CODE、NEED_TRIAL_APPLY、NEED_CONTACT_ADMIN、NO_PRODUCT_PERMISSION、ACCOUNT_CONFLICT、LEGACY_LOGIN_REQUIRED、PRODUCT_NOT_OPEN_TO_PUBLIC、ACCOUNT_DISABLED、INTERNAL_ERROR。

## 安全要求

### login_ticket 安全

- 一次性、短时效（3～5 分钟）、产品绑定、用户绑定、上下文绑定、后端校验、日志脱敏、URL 清理（建议）、HTTPS（生产必须）。

### biz_context 安全

- 不建议在 URL 明文传递复杂上下文；简单字段可作为上下文透传；复杂上下文使用 context_id。
- 上下文应绑定 product_code，不允许跨产品使用。
- 不允许产品校验 ticket 时临时提交上下文作为可信来源。

### 密钥安全

- 产品密钥不得写入前端代码、不得提交 Git、不得打印日志、按环境分开；泄露后必须支持轮换。
- product_access_key 仅存储在服务端，不入前端、不入 URL、不入日志。

### 安全规范

- 所有 redirect_uri 必须统一白名单管理。
- 所有授权请求必须校验 state，防止 CSRF。
- access_token/refresh_token 不暴露于前端或 URL。
- client_secret 仅允许服务端保存。
- 生产环境必须全链路 HTTPS。
- 日志必须脱敏处理，不记录敏感信息。

## 登出机制

### 本地登出

- 仅退出当前产品，不影响官网及其他产品登录状态。

### 全局登出（可选/二期）

- 用户从官网统一认证中心退出时，认证中心可通知已接入产品清理本地 session。首期不强制实现。
- 通知内容包含 product_code、unified_uid、session_id、logout_time、reason。
- 产品侧收到通知后根据 unified_uid 查询本地 session、清理登录态、记录登出日志。

## 错误码规范

### 认证中心错误码

| 错误码 | 说明 | 产品侧建议处理 |
| --- | --- | --- |
| SUCCESS | 成功 | 正常处理 |
| TICKET_INVALID | ticket 无效 | 重新发起登录 |
| TICKET_EXPIRED | ticket 过期 | 重新发起登录 |
| TICKET_USED | ticket 已使用 | 重新发起登录 |
| PRODUCT_INVALID | product_code 无效 | 检查接入配置 |
| PRODUCT_DISABLED | 产品接入禁用 | 联系官网团队 |
| STATE_INVALID | state 不匹配 | 重新发起登录 |
| CONTEXT_INVALID | context_id 无效 | 重新发起流程 |
| CONTEXT_EXPIRED | context_id 过期 | 重新生成上下文 |
| USER_DISABLED | 用户被冻结 | 提示用户联系支持 |
| USER_NOT_FOUND | 用户不存在 | 重新登录或注册 |
| RATE_LIMITED | 请求过于频繁 | 稍后重试 |
| INTERNAL_ERROR | 系统异常 | 记录日志，稍后重试 |
| SESSION_INVALID | 未登录或 session 过期 | 重新登录 |
| PARAM_INVALID | 参数错误 | 检查请求参数 |
| PRODUCT_ACCESS_DENIED | product_access_key 错误 | 检查密钥配置 |

## 验收标准

### 通用验收

| 验收项 | 标准 |
| --- | --- |
| 官网登录 | 用户可通过手机号/邮箱登录官网 |
| 官网跳产品 | 点击产品入口可跳转 |
| ticket 校验 | 产品后端可校验 ticket |
| UserInfo 获取 | 产品可获取 unified_uid |
| account_status | 产品能识别账号状态 |
| biz_context | 产品可获取绑定上下文 |
| 本地映射 | 产品可建立 unified_uid ↔ local_user_id |
| 本地 session | 产品可创建自己的登录态 |
| 免二次登录 | 用户无需再次输入产品账号密码 |
| 异常处理 | ticket 过期、无权限、冲突有提示 |
| 正向链路 | 完成 context/register → login → ticket/create → ticket/verify → 建立 Session → return_url 跳转 |
| 异常链路 | 票据重用、state 不符、nonce 重放、product_access_key 无效等场景均需验证 |
| 审计日志 | 无敏感明文（手机号、邮箱、密钥、token 等脱敏） |

### C 端产品验收

| 验收项 | 标准 |
| --- | --- |
| 新用户 | 可自动创建或进入产品指定流程 |
| 老用户 | 可自动绑定或确认绑定 |
| 邀请制 | 无邀请码不可进入 |
| 个人空间 | 可进入个人默认空间 |

### B 端产品验收

| 验收项 | 标准 |
| --- | --- |
| 已有账号 | 可绑定后进入 |
| 无账号 | 不自动开通，进入留资或申请 |
| 企业邮箱 | 可按产品策略校验 |
| 企业代码 | 可按产品策略校验 |
| 企业权限 | 由产品本地判断 |
| 原登录入口 | 可继续使用 |