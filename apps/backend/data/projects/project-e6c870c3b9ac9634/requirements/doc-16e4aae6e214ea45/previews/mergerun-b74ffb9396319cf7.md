# 亦庄登录sso

## 需求概述
- 建设统一登录认证授权中心，实现统一注册、统一登录、统一认证、统一身份标识、单点登录（SSO）。
- 官网统一认证中心负责用户身份认证，各产品负责业务权限与应用内能力。
- 各产品首期通过最小接入链路（login_ticket + UserInfo + 本地 session）接入。

## 官网统一认证中心职责

### 注册与登录
- 支持手机号注册、邮箱注册。
- 支持手机号登录、邮箱登录。
- 支持找回密码。
- 为官网用户生成全局唯一 `unified_uid`。
- 维护官网侧登录态。

### SSO 票据
- 签发一次性短效产品登录票据 `login_ticket`。
- `login_ticket` 生成时必须绑定：product_code、unified_uid、state、return_url（可选）、biz_context/context_id（可选）、expires_at、used_status。
- 票据有效期建议 3～5 分钟。
- 票据为一次性，使用后立即置为 used。
- 票据不可作为 session 使用；产品必须自行创建本地 session。

### 票据校验
- 提供 ticket 校验接口，产品后端通过 ticket 换取可信身份信息。
- 校验接口仅允许产品后端调用，不允许产品前端直接调用。
- 校验时建议提交 nonce 与 timestamp 用于防重放。

### 用户信息
- 返回统一身份基础信息（UserInfo）。
- UserInfo 字段包括：unified_uid（必返）、user_type（必返）、phone（脱敏）、phone_verified、email、email_verified、nickname、avatar、register_source、identity_contexts。
- 默认返回脱敏手机号；产品如需完整手机号/邮箱需在接入配置中申请。
- 产品侧日志不得打印完整手机号、邮箱。
- `user_type` 仅为参考值，不代表产品内权限。

### 账号状态
- 返回官网统一账号状态 `account_status`（ACTIVE / DISABLED / CANCELLED）。

### 业务上下文
- 绑定并透传业务上下文 `biz_context`。
- 支持产品预注册业务上下文（context/register 接口），返回 context_id。
- 简单上下文可放在 `biz_context` 中；复杂上下文建议通过 `context_id` 预注册。
- 上下文应在 `login_ticket` 生成阶段绑定；产品校验 ticket 时不应重新提交上下文作为可信来源。
- 认证中心只保存和透传上下文，不解释产品业务含义。
- 上下文必须绑定 product_code，不允许跨产品复用。

### 限流与审计
- 对关键接口（ticket/create、ticket/verify 等）实施分钟桶限流（HTTP 429）。
- 记录官网侧认证和产品跳转审计日志，敏感字段脱敏。

## 产品接入职责

### 产品接入配置
- 产品接入前需填写接入配置表，包含：product_code、product_name、product_owner、tech_owner、product_user_mode、product_domain、sso_entry_url、allowed_redirect_domains、logout_callback_url（可选）、legacy_login_keep、allow_auto_create_user、require_enterprise_email（可选）、require_enterprise_code（可选）、require_invite_code（可选）、support_default_role、default_role（可选）、no_account_action、support_context_register（可选）、support_third_party_bind（可选）、local_user_key、local_tenant_key（可选）、remark（可选）。
- `product_user_mode` 枚举值：C、B、B_PLUS_C、INVITE_ONLY。接口响应用枚举值（如 B_PLUS_C）。
- `no_account_action` 枚举值：AUTO_CREATE、GUIDE_APPLY、LEAD_FORM、CONTACT_ADMIN、NEED_INVITE_CODE、SELECT_PERSONAL_OR_ENTERPRISE。

### 产品侧必须实现

#### 接收 sso_entry_url
- 产品需提供 HTTP GET 回调地址，接收 login_ticket + state + source（可选）。
- 产品收到请求后：不直接信任 login_ticket；将 login_ticket 发送到产品后端；产品后端调用 ticket 校验接口；校验成功后获取 UserInfo + account_status + biz_context；产品按本地策略判断是否允许进入；产品创建本地 session；清理 URL 中的 login_ticket，避免泄露。

#### 调用 ticket/verify
- 产品后端调用认证中心校验 ticket。
- 请求字段：product_code（必填）、login_ticket（必填）、state（必填）、nonce（建议）、timestamp（建议）。
- 不建议由产品在校验时提交的字段：return_url、biz_context、invite_code、job_id/company_id/hr_id、product_user_mode。

#### 维护 unified_uid 与本地账号映射
- 产品需建立 unified_uid ↔ local_user_id 映射表。
- 推荐映射字段：id、product_code、unified_uid、local_user_id、local_tenant_id（可选）、bind_type（auto/manual/created/invite/enterprise）、bind_status（bound/pending/conflict/disabled）、bind_source（official_website_sso）、first_bind_time、last_login_time、created_at、updated_at。

#### 建立产品本地 Session
- 产品不能直接把 login_ticket 当作登录态，必须自行创建本地 session。
- 推荐 session 内容：local_user_id、unified_uid、local_tenant_id（可选）、role、permissions、login_source、login_time、session_expire_time。

#### 处理首次进入
- 按 unified_uid 查本地映射。若已有映射：直接建立本地 session。若无映射：按手机号/邮箱/企业标识查询本地用户。若唯一命中：自动绑定或提示确认绑定。若未命中：按产品策略创建本地账号或提示申请开通。若多账号冲突：进入人工处理。

#### 安全性
- product_access_key 必须仅保存在产品后端，不得写入前端代码、不得提交 Git、不得打印日志、按环境分开、泄露后支持轮换。
- 生产环境必须全链路 HTTPS。
- 所有 redirect_uri 必须统一白名单管理。
- 所有授权请求必须校验 state，防止 CSRF。
- access_token/refresh_token 禁止暴露于前端或 URL。

### 产品侧建议实现

#### 准入结果枚举
- 产品侧建议统一定义准入结果 code：ACCESS_GRANTED、NEED_BINDING_CONFIRM、NEED_ENTERPRISE_EMAIL、NEED_ENTERPRISE_CODE、NEED_INVITE_CODE、NEED_TRIAL_APPLY、NEED_CONTACT_ADMIN、NO_PRODUCT_PERMISSION、ACCOUNT_CONFLICT、LEGACY_LOGIN_REQUIRED、PRODUCT_NOT_OPEN_TO_PUBLIC、ACCOUNT_DISABLED、INTERNAL_ERROR。

### 产品侧可选实现

#### 登出回调接口
- 当用户从官网统一认证中心退出时，认证中心可通知已接入产品清理本地 session（首期不强制）。
- 认证中心 POST 请求到 product 的 logout_callback_url，包含 product_code、unified_uid、session_id、logout_time、reason。
- 产品侧处理：根据 unified_uid 查询本地 session；清理当前用户本地登录态；记录登出日志；返回处理结果。

#### 第三方身份绑定接口
- 用于微信小程序、企业微信、支付宝等第三方身份与 unified_uid 的绑定或解析（二期/按需）。
- 身份匹配优先级推荐：unionid > openid + app_id > phone > email。

## 产品准入模式

### C 端产品
- 面向个人用户，可自助注册或使用。
- 官网注册用户可尝试进入，产品侧按 unified_uid 查映射，无映射可自动创建本地账号。
- 新用户首次进入：可自动创建本地账号。老用户手机号唯一命中：可自动绑定。老用户邮箱唯一命中：可自动绑定或确认绑定。多账号命中：人工处理。邀请制产品：必须校验邀请码。无权限：提示申请开通或联系支持。

### B 端产品
- 面向企业客户，通常需企业租户、管理员开通、商务签约。
- 核心原则：官网注册/登录只代表完成统一身份认证，不代表自动开通 B 端产品权限。
- 产品侧必须判断：是否已有本地账号、是否属于企业租户、是否有产品权限、是否开通对应功能模块、是否需要企业管理员邀请、是否需要企业邮箱、是否需要企业代码、是否需要商务开通。
- 已有本地账号和权限：进入产品。有账号但无租户：提示选择企业或联系管理员。有租户但无产品授权：提示产品未开通。新企业客户：走申请试用/留资/商务开通。企业成员：由企业管理员邀请或产品侧授权。多企业身份：进入产品侧身份选择页。个人邮箱访问：可进入留资页。企业邮箱命中：产品侧判断是否属于已开通企业。

### B+C 混合产品
- 同时支持个人和企业用户。
- 个人使用：可创建/绑定个人空间。企业使用：需企业代码/企业邮箱/企业微信。已有企业账号：绑定 unified_uid 后进入。未开通企业：留资/申请试用。邀请制 C 端：校验产品邀请码。

### 邀请制产品（INVITE_ONLY）
- 邀请码由产品生成和校验。
- 认证中心只负责接收、保存、绑定到 login_ticket、返回给产品，不判断业务有效性。
- 无邀请码访问邀请制产品时，产品策略可定义：提示需要邀请码、展示申请入口、加入候补名单、分配受限角色、提示暂未开放。

## 接口定义

### 通用错误码
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

### 上下文预注册接口
- **说明**：用于产品深链、面试链接、专家邀请、小程序跳转等场景。产品可先把业务上下文注册到统一认证中心，认证中心返回 context_id。
- **请求方式**：POST /api/sso/context/register
- **请求头**：Content-Type: application/json, Authorization: Bearer {product_access_key}
- **请求示例**：
```json
{
  "product_code": "baicai",
  "scene": "interview_invite",
  "return_url": "/interview/detail",
  "biz_context": {
    "job_id": "J001",
    "company_id": "C001",
    "hr_id": "H001"
  },
  "expire_minutes": 30
}
```
- **请求字段**：product_code（必填）、scene（必填）、return_url（必填）、biz_context（可选）、expire_minutes（可选，默认30分钟）。
- **响应示例**：
```json
{
  "code": "SUCCESS",
  "message": "success",
  "data": {
    "context_id": "CTX_abc123",
    "login_url": "https://www.brgroup.com/login?product_code=baicai&context_id=CTX_abc123",
    "expires_at": "2026-05-06T10:30:00+08:00"
  }
}
```
- **设计约束**：context_id 短时有效；绑定 product_code；不能跨产品复用；biz_context 不承载敏感明文；复杂上下文建议用 context_id，不要全部放 URL；认证中心只保存和返回上下文，不解释产品业务含义。

### login_ticket 生成接口
- **说明**：用户在官网已登录后，官网向统一认证中心申请产品登录票据。该接口通常由官网服务端调用，不直接暴露给产品前端。
- **请求方式**：POST /api/sso/ticket/create
- **请求头**：Content-Type: application/json, Authorization: Bearer {website_access_key}
- **请求示例（普通官网产品入口）**：
```json
{
  "product_code": "baigong",
  "state": "STATE_xxx",
  "return_url": "/",
  "source": "official_website",
  "biz_context": {
    "scene": "homepage_product_card",
    "campaign": "homepage_baigong_card"
  }
}
```
- **请求示例（邀请码场景）**：
```json
{
  "product_code": "baigong",
  "state": "STATE_xxx",
  "return_url": "/",
  "source": "official_website",
  "biz_context": {
    "scene": "baigong_invite",
    "invite_code": "BG202604001",
    "invite_source": "baigong"
  }
}
```
- **请求示例（使用 context_id）**：
```json
{
  "product_code": "baicai",
  "state": "STATE_xxx",
  "context_id": "CTX_abc123",
  "source": "official_website"
}
```
- **请求字段**：product_code（必填）、state（必填）、return_url（可选）、source（可选）、campaign（可选）、biz_context（可选）、context_id（可选）。biz_context 与 context_id 可二选一；复杂业务场景推荐使用 context_id。
- **响应示例**：
```json
{
  "code": "SUCCESS",
  "message": "success",
  "data": {
    "login_ticket": "LTK_8f7a9c1e2b3d",
    "state": "STATE_xxx",
    "sso_entry_url": "https://baigong.xxx.com/sso/login",
    "expires_at": "2026-05-06T10:05:00+08:00"
  }
}
```

### 官网跳转产品入口
- **说明**：官网拿到 login_ticket 后，跳转至产品提供的 sso_entry_url。
- **请求方式**：GET {sso_entry_url}?login_ticket={login_ticket}&state={state}&source=official_website
- **请求参数**：login_ticket（必填）、state（必填）、source（可选）。
- 不建议在 URL 中直接携带完整 biz_context。return_url 和 biz_context 应在 login_ticket 生成阶段绑定，产品校验 ticket 后由认证中心返回。

### login_ticket 校验接口
- **说明**：产品后端使用 login_ticket 调用官网统一认证中心，换取可信用户身份信息。该接口必须由产品后端调用，不允许产品前端直接调用。
- **请求方式**：POST /api/sso/ticket/verify
- **请求头**：Content-Type: application/json, Authorization: Bearer {product_access_key}
- **请求示例**：
```json
{
  "product_code": "baigong",
  "login_ticket": "LTK_8f7a9c1e2b3d",
  "state": "STATE_xxx",
  "nonce": "N_xxx",
  "timestamp": 1770000000000
}
```
- **响应示例（成功）**：
```json
{
  "code": "SUCCESS",
  "message": "success",
  "data": {
    "verified": true,
    "ticket_status": "used",
    "account_status": "ACTIVE",
    "user_info": {
      "unified_uid": "U10000001",
      "user_type": "UNKNOWN",
      "phone": "138****8888",
      "phone_verified": true,
      "email": "user@example.com",
      "email_verified": true,
      "nickname": "张三",
      "avatar": "https://static.brgroup.com/avatar/default.png",
      "register_source": "official_website",
      "identity_contexts": [
        {
          "type": "personal",
          "default": true
        }
      ]
    },
    "product_context": {
      "product_code": "baigong",
      "product_user_mode": "INVITE_ONLY",
      "entry_scene": "homepage_product_entry"
    },
    "return_url": "/",
    "biz_context": {
      "scene": "baigong_invite",
      "invite_code": "BG202604001",
      "invite_source": "baigong"
    },
    "issued_at": "2026-05-06T10:00:00+08:00",
    "expires_at": "2026-05-06T10:05:00+08:00"
  }
}
```
- **响应示例（失败）**：
```json
{
  "code": "TICKET_EXPIRED",
  "message": "login_ticket 已过期",
  "data": {
    "verified": false
  }
}
```

### 查询产品进入状态接口
- **说明**：前端判断是否弹邀请码，后端查询用户首次接入状态。
- **请求方式**：GET /api/sso/product-entry/status?product_code={product_code}
- **认证**：Authorization: Bearer {session_token}（官网登录用户）
- **业务逻辑**：校验 session_token 获取 unified_uid；查询产品配置；如果 require_invite_code = false，action = CREATE_TICKET_DIRECTLY；如果 require_invite_code = true，查询 auth_product_user_access 是否存在 CONNECTED 记录，存在则 action = CREATE_TICKET_DIRECTLY，不存在则 action = SHOW_INVITE_DIALOG。
- **成功响应（需要弹邀请码）**：
```json
{
  "code": "SUCCESS",
  "data": {
    "product_code": "baigong",
    "product_name": "百工",
    "require_invite_code": true,
    "invite_required_for_current_user": true,
    "access_status": "NOT_CONNECTED",
    "action": "SHOW_INVITE_DIALOG",
    "sso_entry_url": "https://saibotan-pre.100credit.cn/login"
  }
}
```
- **成功响应（不需要弹邀请码）**：
```json
{
  "code": "SUCCESS",
  "data": {
    "product_code": "baigong",
    "product_name": "百工",
    "require_invite_code": true,
    "invite_required_for_current_user": false,
    "access_status": "CONNECTED",
    "action": "CREATE_TICKET_DIRECTLY",
    "sso_entry_url": "https://saibotan-pre.100credit.cn/login"
  }
}
```
- **错误码**：SESSION_INVALID、PRODUCT_INVALID、PRODUCT_DISABLED、PARAM_INVALID。

### 确认产品首次接入接口
- **说明**：产品后端在用户首次接入成功后，将状态回写至认证中心。
- **请求方式**：POST /api/sso/product-entry/confirm
- **认证**：Authorization: Bearer {product_access_key}（产品后端）
- **请求示例**：
```json
{
  "product_code": "baigong",
  "unified_uid": "{unified_uid}",
  "access_status": "CONNECTED",
  "bind_source": "INVITE_CODE"
}
```
- **业务逻辑**：校验 unified_uid 对应用户存在；校验 access_status = CONNECTED；Upsert auth_product_user_access：不存在则插入 first_connected_at=now, last_connected_at=now；已存在则更新 access_status=CONNECTED, last_connected_at=now（不覆盖 first_connected_at）。
- **成功响应**：
```json
{
  "code": "SUCCESS",
  "data": {
    "product_code": "baigong",
    "unified_uid": "{unified_uid}",
    "access_status": "CONNECTED"
  }
}
```
- **错误码**：PRODUCT_ACCESS_DENIED、PRODUCT_INVALID、PRODUCT_DISABLED、USER_NOT_FOUND、PARAM_INVALID。

## 数据库表

### auth_product_user_access
```sql
CREATE TABLE auth_product_user_access (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  product_code VARCHAR(64) NOT NULL,
  unified_uid VARCHAR(64) NOT NULL,
  access_status VARCHAR(32) NOT NULL COMMENT 'CONNECTED / REVOKED',
  bind_source VARCHAR(32) DEFAULT NULL,
  first_connected_at DATETIME(3),
  last_connected_at DATETIME(3),
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  is_deleted TINYINT NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_product_uid (product_code, unified_uid)
);
```
不存储：邀请码、local_user_id、local_tenant_id、权限。

## 原入口保留原则
- 首期不强制各产品关闭原登录入口。企业管理员已分配账号密码、企业用户已收藏后台链接、产品自有 App/小程序登录、邀请码登录、企业微信扫码、存量客户后台登录等场景均可保留。
- 官网统一认证中心主要承接新增链路（官网导流、活动、邀请、深链），不强制一次性替代所有产品既有入口。

## 接入流程
1. 产品完成登记表
2. 认证中心侧配置 product_code、sso_entry_url、allowed_redirect_domains
3. 认证中心侧提供联调环境 product_access_key（安全渠道交付）
4. 产品后端实现 sso_entry_url 接收逻辑和 ticket/verify 调用
5. 联调验证
6. 通过验收清单
7. 生产上线（生产密钥单独分发）

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

## 待澄清问题
- 无
