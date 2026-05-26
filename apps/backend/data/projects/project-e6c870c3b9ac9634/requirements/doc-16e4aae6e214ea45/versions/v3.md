# 亦庄登录sso

## 需求概述

官网统一认证中心作为百系产品统一身份基础设施，提供用户注册、登录、统一UID管理、SSO票据签发与校验、业务上下文透传等核心认证能力。各产品保留本地账号体系、角色权限和业务逻辑，通过login_ticket + UserInfo + 本地session的最小接入模式实现官网进入产品免二次登录。首期支持手机号/邮箱注册登录，产品可保留原有登录入口，后续逐步扩展。

## 产品接入配置

### 接入登记表

各产品接入前必须填写接入配置表，包含但不限于以下字段：

- `product_code`（必填）：产品编码，全局唯一。
- `product_name`（必填）：产品中文名称。
- `product_owner`（必填）：产品负责人。
- `tech_owner`（必填）：技术负责人。
- `product_user_mode`（必填）：产品用户模式，枚举C / B / B+C / INVITE_ONLY。
- `product_domain`（必填）：产品域名。
- `sso_entry_url`（必填）：产品接收login_ticket的入口地址。
- `allowed_redirect_domains`（必填）：允许回跳域名白名单。
- `legacy_login_keep`（必填）：是否保留原登录入口。
- `allow_auto_create_user`（必填）：是否允许自动创建本地用户。
- `no_account_action`（必填）：无本地账号时处理方式，枚举AUTO_CREATE / GUIDE_APPLY / LEAD_FORM / CONTACT_ADMIN / NEED_INVITE_CODE / SELECT_PERSONAL_OR_ENTERPRISE。
- `local_user_key`（必填）：本地用户主键。
- `logout_callback_url`（可选）：登出回调地址。
- `require_enterprise_email`（可选）：是否要求企业邮箱。
- `require_enterprise_code`（可选）：是否要求企业代码。
- `require_invite_code`（可选）：是否要求邀请码。
- `support_default_role`（必填）：是否支持默认角色。
- `default_role`（可选）：默认角色。
- `support_context_register`（可选）：是否需要产品深链上下文预注册。
- `support_third_party_bind`（可选）：是否需要第三方身份绑定。
- `local_tenant_key`（可选）：本地租户主键。
- `remark`（可选）：备注。

### 产品用户模式

- **C**：面向个人用户，可自助注册或使用，典型产品如百工C端、部分百智个人场景。
- **B**：面向企业客户，通常需企业租户、管理员开通、商务签约，典型产品如百才、百察、百灵。
- **B+C**：同时支持个人和企业用户，典型产品如百智、百工。
- **INVITE_ONLY**：邀请制或灰度开放，典型场景如百工当前C端邀请码场景。

产品用户模式决定准入规则：

- C模式：官网注册后若产品允许自动创建，可自动创建或绑定本地账号。
- B模式：不建议直接进入，需有本地账号和权限，否则引导留资/申请试用/联系管理员。
- B+C模式：根据用户意图和产品策略分流至个人空间或企业空间。
- INVITE_ONLY模式：无邀请码不允许直接进入，需校验产品侧邀请码。

## 统一UID与本地账号映射

### 映射要求

通过官网统一认证中心进入产品的用户，必须建立或复用`unified_uid ↔ local_user_id`映射，以支持免二次登录、老用户绑定、多登录方式统一、产品内审计及账号状态治理。

### 推荐映射字段

- `id`：主键。
- `product_code`：产品编码。
- `unified_uid`：统一UID。
- `local_user_id`：产品本地用户ID。
- `local_tenant_id`（可选）：产品本地租户ID。
- `bind_type`：绑定类型，枚举auto / manual / created / invite / enterprise。
- `bind_status`：绑定状态，枚举bound / pending / conflict / disabled。
- `bind_source`：绑定来源，固定为official_website_sso。
- `first_bind_time`：首次绑定时间。
- `last_login_time`：最近登录时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

### 首次进入处理规则

1. 按unified_uid查询本地映射。
2. 若已有映射：直接建立本地session。
3. 若无映射：按手机号/邮箱/企业标识/unionid等查询本地用户。
4. 若唯一命中：自动绑定或提示确认绑定。
5. 若未命中：按产品策略创建本地账号或提示申请开通。
6. 若多账号冲突：进入人工处理。

## 核心接口

### 上下文预注册接口

- **说明**：用于产品深链、面试链接、专家邀请、小程序跳转等场景。产品可先把业务上下文注册到统一认证中心，返回`context_id`，后续官网使用`context_id`申请`login_ticket`。
- **请求方式**：POST /api/sso/context/register
- **鉴权**：Authorization: Bearer {product_access_key}
- **请求体字段**：
  - `product_code`（必填）：产品编码。
  - `scene`（必填）：业务场景。
  - `return_url`（必填）：登录后目标页。
  - `biz_context`（可选）：业务上下文。
  - `expire_minutes`（可选）：上下文有效期，默认30分钟。
- **响应**：`{ "code": "SUCCESS", "data": { "context_id": "CTX_xxx", "login_url": "...", "expires_at": "..." } }`
- **设计约束**：
  - `context_id`短时有效。
  - `context_id`绑定`product_code`。
  - `context_id`不能跨产品复用。
  - `biz_context`不承载敏感明文。
  - 复杂上下文建议用`context_id`，不要全部放URL。
  - 认证中心只保存和返回上下文，不解释产品业务含义。

### login_ticket生成接口

- **说明**：用户在官网已登录后，官网向统一认证中心申请产品登录票据。由官网服务端调用，不直接暴露给产品前端。
- **请求方式**：POST /api/sso/ticket/create
- **鉴权**：Authorization: Bearer {website_access_key}
- **请求体字段**：
  - `product_code`（必填）：目标产品编码。
  - `state`（必填）：防CSRF / 防串流程。
  - `return_url`（可选）：登录后产品内目标地址。
  - `source`（可选）：来源。
  - `campaign`（可选）：营销活动。
  - `biz_context`（可选）：简单上下文。
  - `context_id`（可选）：已预注册上下文ID。
- **说明**：`biz_context`与`context_id`可二选一，复杂业务场景推荐使用`context_id`。
- **响应**：`{ "code": "SUCCESS", "data": { "login_ticket": "LTK_xxx", "state": "...", "sso_entry_url": "...", "expires_at": "..." } }`
- **票据绑定规则**：`login_ticket`生成时必须绑定product_code、unified_uid、state、return_url、biz_context/context_id、expires_at、used_status。

### 官网跳转产品入口

- **说明**：官网拿到`login_ticket`后，跳转至产品提供的`sso_entry_url`。
- **请求方式**：GET {sso_entry_url}?login_ticket={login_ticket}&state={state}&source=official_website
- **请求参数**：
  - `login_ticket`（必填）：一次性登录票据。
  - `state`（必填）：防CSRF / 防串流程。
  - `source`（可选）：来源标识。
- **注意事项**：
  - 不建议在URL中直接携带完整`biz_context`，`return_url`和`biz_context`应在`login_ticket`生成阶段绑定，产品校验ticket后由认证中心返回。
  - 产品侧收到请求后必须：不直接信任`login_ticket`、将`login_ticket`发送到产品后端、调用ticket校验接口、校验成功后获取UserInfo+account_status+biz_context、按本地策略判断是否允许进入、创建本地session、清理URL中的`login_ticket`。

### login_ticket校验接口

- **说明**：产品后端使用`login_ticket`调用官网统一认证中心，换取可信用户身份信息。必须由产品后端调用，不允许产品前端直接调用。
- **请求方式**：POST /api/sso/ticket/verify
- **鉴权**：Authorization: Bearer {product_access_key}
- **请求体字段**：
  - `product_code`（必填）：产品编码。
  - `login_ticket`（必填）：一次性登录票据。
  - `state`（必填）：与跳转时一致。
  - `nonce`（建议）：防重放随机串。
  - `timestamp`（建议）：请求时间戳。
- **不应在校验时提交的字段**：return_url、biz_context、invite_code、job_id/company_id/hr_id、product_user_mode（应在ticket生成阶段绑定）。
- **成功响应**：`{ "code": "SUCCESS", "data": { "verified": true, "ticket_status": "used", "account_status": "ACTIVE", "user_info": { "unified_uid": "...", "user_type": "UNKNOWN", "phone": "138****8888", "phone_verified": true, "email": "user@example.com", "email_verified": true, "nickname": "张三", "avatar": "...", "register_source": "official_website", "identity_contexts": [...] }, "product_context": { "product_code": "...", "product_user_mode": "...", "entry_scene": "..." }, "return_url": "/", "biz_context": {...}, "issued_at": "...", "expires_at": "..." } }`
- **失败响应示例**：`{ "code": "TICKET_EXPIRED", "message": "login_ticket 已过期", "data": { "verified": false } }`
- **票据规则**：
  - 一次性，只能使用一次。
  - 短时效，建议3～5分钟。
  - 产品绑定，只能被指定product_code使用。
  - 用户绑定，绑定生成时的unified_uid。
  - 上下文绑定，绑定return_url / biz_context / context_id。
  - 后端校验，只能由产品后端调用。
  - 不可复用，校验成功后立即置为used。
  - 不可长期保存，产品侧不应长期保存。
  - 不可作为session，产品必须自行创建本地session。

### UserInfo用户信息结构

- **返回字段**（来自ticket/verify响应）：
  - `unified_uid`（必返）：官网全局用户ID。
  - `user_type`（必返）：UNKNOWN / C / B / B+C，仅作参考，不作为产品权限判断。
  - `phone`（可选）：脱敏手机号。
  - `phone_verified`（可选）：手机号是否已验证。
  - `email`（可选）：邮箱。
  - `email_verified`（可选）：邮箱是否已验证。
  - `nickname`（可选）：昵称。
  - `avatar`（可选）：头像。
  - `register_source`（必返）：注册来源。
  - `identity_contexts`（可选）：身份上下文。
- **关于user_type**：`user_type`只是统一认证中心侧的基础判断或参考值，不代表用户在某产品内一定拥有B端或C端权限。
- **关于手机号与邮箱**：
  - 默认返回脱敏手机号。
  - 产品如需完整手机号/邮箱用于绑定，需在接入配置中申请。
  - 完整手机号和邮箱按最小必要原则返回。
  - 产品侧日志不得打印完整手机号、邮箱。
  - 是否企业邮箱由产品侧判断。

### 查询产品进入状态接口

- **说明**：为前端判断是否弹邀请码，为产品后端回写首次接入状态。认证中心维护轻量状态：某个unified_uid是否已完成某个product_code的首次接入。
- **请求方式**：GET /api/sso/product-entry/status
- **鉴权**：Authorization: Bearer {session_token}（官网登录用户）
- **参数**：`product_code`（query string，必填）
- **业务逻辑**：
  1. 校验session_token，获取unified_uid。
  2. 查询产品配置（不存在→PRODUCT_INVALID，禁用→PRODUCT_DISABLED）。
  3. 如果require_invite_code=false：action=CREATE_TICKET_DIRECTLY。
  4. 如果require_invite_code=true：查询auth_product_user_access是否存在CONNECTED记录；存在→action=CREATE_TICKET_DIRECTLY；不存在→action=SHOW_INVITE_DIALOG。
- **成功响应（需弹邀请码）**：`{ "code": "SUCCESS", "data": { "product_code": "baigong", "product_name": "百工", "require_invite_code": true, "invite_required_for_current_user": true, "access_status": "NOT_CONNECTED", "action": "SHOW_INVITE_DIALOG", "sso_entry_url": "..." } }`
- **成功响应（不需弹邀请码）**：`{ "code": "SUCCESS", "data": { "product_code": "baigong", "product_name": "百工", "require_invite_code": true, "invite_required_for_current_user": false, "access_status": "CONNECTED", "action": "CREATE_TICKET_DIRECTLY", "sso_entry_url": "..." } }`
- **错误码**：SESSION_INVALID（未登录或session过期）、PRODUCT_INVALID（产品不存在）、PRODUCT_DISABLED（产品已禁用）、PARAM_INVALID（product_code为空）。

### 确认产品首次接入接口

- **说明**：产品后端在用户完成首次接入（如邀请码校验通过、自动创建账号等）后调用，回写该用户对该产品的首次接入状态。
- **请求方式**：POST /api/sso/product-entry/confirm
- **鉴权**：Authorization: Bearer {product_access_key}（产品后端）
- **请求体**：
  - `product_code`（必填）：产品编码。
  - `unified_uid`（必填）：统一用户ID。
  - `access_status`（必填）：当前仅支持CONNECTED。
  - `bind_source`（可选）：接入来源，枚举INVITE_CODE / ADMIN / IMPORT / UNKNOWN。
- **鉴权逻辑**：
  1. 校验Authorization: Bearer {product_access_key}。
  2. product_access_key必须属于请求体中的product_code。
  3. 产品必须ENABLED。
  4. 鉴权失败→PRODUCT_ACCESS_DENIED。
- **业务逻辑**：
  1. 校验unified_uid对应用户存在。
  2. 校验access_status=CONNECTED。
  3. Upsert `auth_product_user_access`：不存在则插入（first_connected_at=now, last_connected_at=now）；已存在则更新access_status=CONNECTED且last_connected_at=now（不覆盖first_connected_at）。
- **成功响应**：`{ "code": "SUCCESS", "data": { "product_code": "baigong", "unified_uid": "{unified_uid}", "access_status": "CONNECTED" } }`
- **错误码**：PRODUCT_ACCESS_DENIED、PRODUCT_INVALID、PRODUCT_DISABLED、USER_NOT_FOUND、PARAM_INVALID。

## 产品准入处理

### 产品本地Session建立要求

- 产品不能直接把`login_ticket`当作登录态。
- 产品必须在校验成功后自行创建本地session。
- 推荐session内容：`local_user_id`、`unified_uid`、`local_tenant_id`、`role`、`permissions`、`login_source`（official_website_sso）、`login_time`、`session_expire_time`。

### 产品准入结果枚举

产品侧建议统一定义准入结果：

- `ACCESS_GRANTED`：允许进入。
- `NEED_BINDING_CONFIRM`：需要确认绑定。
- `NEED_ENTERPRISE_EMAIL`：需要企业邮箱。
- `NEED_ENTERPRISE_CODE`：需要企业编码。
- `NEED_INVITE_CODE`：需要邀请码。
- `NEED_TRIAL_APPLY`：需要申请试用。
- `NEED_CONTACT_ADMIN`：需要联系企业管理员。
- `NO_PRODUCT_PERMISSION`：无产品权限。
- `ACCOUNT_CONFLICT`：账号冲突。
- `LEGACY_LOGIN_REQUIRED`：请使用原入口。
- `PRODUCT_NOT_OPEN_TO_PUBLIC`：暂不开放。
- `ACCOUNT_DISABLED`：账号禁用。
- `INTERNAL_ERROR`：系统异常。

### B端产品处理建议

- 官网注册/登录不代表自动开通B端产品权限。
- 需继续判断：是否已有本地账号、是否属于企业租户、是否有产品权限、是否开通对应功能模块、是否需要企业管理员邀请、是否需要企业邮箱/企业代码/商务开通。
- 推荐规则：
  - 已有本地账号和权限→进入产品。
  - 有账号但无租户→提示选择企业或联系管理员。
  - 有租户但无产品授权→提示产品未开通。
  - 新企业客户→走申请试用/留资/商务开通。
  - 企业成员→由企业管理员邀请或产品侧授权。
  - 多企业身份→进入产品侧身份选择页。
  - 个人邮箱访问→可进入留资页。
  - 企业邮箱命中→产品侧判断是否属于已开通企业。
  - 原后台登录入口→首期可保留。

### B+C产品处理建议

- 个人使用：可创建/绑定个人空间。
- 企业使用：需要企业代码/企业邮箱/企业微信等。
- 已有企业账号：绑定unified_uid后进入。
- 未开通企业：留资/申请试用。
- 邀请制C端：校验产品邀请码。

## 邀请码与业务上下文

### biz_context设计目的

用于解决邀请码、推荐码、专家邀请、百工灰度准入、百才面试链接、小程序场景、活动来源、登录后目标页恢复、产品深链参数防丢等场景。

### 安全原则

1. 简单上下文可放`biz_context`。
2. 复杂上下文建议通过`context_id`预注册。
3. 上下文应在`login_ticket`生成阶段绑定。
4. 产品校验ticket时不应重新提交上下文作为可信来源。
5. 认证中心不解释产品业务含义。
6. 产品负责最终业务校验。

### 邀请码/推荐码处理原则

- 邀请码、推荐码属于产品业务准入机制，由产品生成和校验。
- 统一认证中心只负责接收、保存、绑定到login_ticket、返回给产品，不判断业务有效性。

## 登出机制

### 本地登出

仅退出当前产品，不影响官网及其他产品登录状态。

### 全局登出（二期/可选）

- 退出统一认证中心，同时清理官网及接入产品登录状态。
- 登出回调接口：认证中心可通知已接入产品清理本地session。
- 请求方式：POST {logout_callback_url}，请求体包含product_code、unified_uid、session_id、logout_time、reason。
- 产品侧处理：根据unified_uid查询本地session、清理当前用户本地登录态、记录登出日志、返回处理结果。

## 原产品登录入口保留策略

首期不强制各产品关闭原登录入口。适用场景包括：企业管理员已分配账号密码、企业用户已收藏后台链接、产品自有App/小程序登录、邀请码登录、企业微信扫码、存量客户后台登录。

## 安全规范

### login_ticket安全要求

- 一次性（必须）、短时效3～5分钟（必须）、产品绑定（必须）、用户绑定（必须）、上下文绑定（必须）、后端校验（必须）、日志脱敏（必须）、URL清理（建议）、HTTPS（生产必须）。

### biz_context安全要求

- 不建议在URL明文传递复杂上下文。
- 简单字段可作为上下文透传。
- 复杂上下文使用`context_id`。
- 上下文应绑定product_code。
- 不允许跨产品使用。
- 不允许产品校验ticket时临时提交上下文作为可信来源。
- 认证中心只透传，不解释产品业务规则。

### 密钥安全要求

- 产品密钥不得写入前端代码。
- 不得提交Git。
- 不得打印日志。
- 按环境分开。
- 泄露后必须支持轮换。

### redirect_uri安全

所有redirect_uri必须统一白名单管理。

### state安全

所有授权请求必须校验state，防止CSRF。

### HTTPS

生产环境必须全链路HTTPS。

### 日志安全

日志必须脱敏处理，不记录敏感信息。

### 产品进入状态接口安全说明

- status接口使用官网session_token鉴权，只返回当前用户自己的状态。
- confirm接口使用product_access_key鉴权，只有合法产品后端才能调用。
- 日志中不打印session_token、product_access_key、邀请码。
- 不存储邀请码明文。
- 不存储local_user_id / local_tenant_id。

## 错误码规范

### 认证中心错误码

- `SUCCESS`：成功。
- `TICKET_INVALID`：ticket无效。
- `TICKET_EXPIRED`：ticket过期。
- `TICKET_USED`：ticket已使用。
- `PRODUCT_INVALID`：product_code无效。
- `PRODUCT_DISABLED`：产品接入禁用。
- `STATE_INVALID`：state不匹配。
- `CONTEXT_INVALID`：context_id无效。
- `CONTEXT_EXPIRED`：context_id过期。
- `USER_DISABLED`：用户被冻结。
- `USER_NOT_FOUND`：用户不存在。
- `RATE_LIMITED`：请求过于频繁。
- `INTERNAL_ERROR`：系统异常。

## 联调与验收

### 联调前置条件

- 产品接入配置表已填写（产品团队）。
- sso_entry_url已提供（产品团队）。
- 产品后端可调用ticket verify（产品团队）。
- 产品本地映射逻辑已准备（产品团队）。
- 产品准入策略已确定（产品团队）。
- 官网认证中心配置product_code（官网团队）。
- 测试账号已准备（双方）。
- 测试环境可访问（双方）。

### 联调步骤

1. 官网侧配置产品接入信息。
2. 产品侧配置接入密钥。
3. 用户在官网测试环境登录。
4. 用户点击产品入口。
5. 官网生成login_ticket。
6. 官网跳转产品sso_entry_url。
7. 产品接收login_ticket。
8. 产品后端校验login_ticket。
9. 产品拿到UserInfo + account_status + biz_context。
10. 产品查本地映射。
11. 产品按准入策略处理。
12. 产品创建本地session。
13. 用户进入产品或进入准入提示页。
14. 双方确认日志、异常处理和安全要求。

### 验收标准

**通用验收**：
- 官网登录（手机号/邮箱）通过。
- 官网跳产品通过。
- ticket校验通过。
- UserInfo获取通过（unified_uid）。
- account_status识别通过。
- biz_context获取通过。
- 本地映射建立通过。
- 本地session创建通过。
- 免二次登录通过。
- 异常处理（ticket过期、无权限、冲突）有提示。

**C端产品验收**：
- 新用户可自动创建或进入产品指定流程。
- 老用户可自动绑定或确认绑定。
- 邀请制产品无邀请码不可进入。
- 个人空间可进入。

**B端产品验收**：
- 已有账号可绑定后进入。
- 无账号不自动开通，进入留资或申请。
- 企业邮箱可按产品策略校验。
- 企业代码可按产品策略校验。
- 企业权限由产品本地判断。
- 原登录入口可继续使用。

## 数据库表

### auth_product_user_access

- `id`：BIGINT UNSIGNED AUTO_INCREMENT。
- `product_code`：VARCHAR(64) NOT NULL。
- `unified_uid`：VARCHAR(64) NOT NULL。
- `access_status`：VARCHAR(32) NOT NULL，取值CONNECTED / REVOKED。
- `bind_source`：VARCHAR(32) DEFAULT NULL。
- `first_connected_at`：DATETIME(3)。
- `last_connected_at`：DATETIME(3)。
- `created_at`：DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)。
- `updated_at`：DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)。
- `is_deleted`：TINYINT NOT NULL DEFAULT 0。
- 唯一索引：`uk_product_uid` (product_code, unified_uid)。
- 不存储邀请码、local_user_id、local_tenant_id、权限。