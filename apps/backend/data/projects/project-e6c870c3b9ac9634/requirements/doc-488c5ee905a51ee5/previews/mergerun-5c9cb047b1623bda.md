# 官网登录sso

## 需求概述
本文档为官网统一登录认证授权中心（br-auth-center）的建设需求，旨在实现统一注册、统一登录、统一认证、统一授权、统一身份标识、单点登录（SSO）、单点登出（SLO）以及官网统一入口能力。认证中心负责身份层统一，各产品保留自身账号体系、权限体系、本地Session及业务权限。

## 用户身份模型
### Unified UID
- 所有用户在统一认证中心内拥有唯一身份标识（Unified UID）。
- Unified UID作为跨产品身份锚点，各产品通过映射关系关联本地账号（Unified UID ↔ Local User ID）。

### 用户类型
- C端用户：个人用户统一注册与登录。
- B端用户：企业管理员、企业成员。
- B+C混合身份用户：支持同一用户在统一身份下承载多身份场景。
- INVITE_ONLY（邀请制/灰度用户）：通过邀请码准入。

## 登录与SSO
### 官网登录
- 用户在官网完成统一注册或登录后，建立统一身份状态。
- 登录一次后，可访问已接入产品，官网进入产品无需重复登录。

### SSO票据链路
- 官网服务端调用ticket/create生成login_ticket（一次性、短时效5分钟）。
- 官网跳转至产品sso_entry_url，携带login_ticket + state。
- 产品后端调用认证中心/api/sso/ticket/verify，校验ticket并换取UserInfo（含unified_uid、user_type、脱敏手机号/邮箱、account_status、注册来源）。
- 认证中心返回UserInfo、account_status、return_url、biz_context。
- 产品侧查询本地映射（unified_uid ↔ local_user_id），处理绑定/创建/权限判断，建立本地Session（JWT/Cookie）。

### 产品接入模式
- C端产品：用户可自动创建本地账号进入。
- B端产品：需查询本地账号及B端权限，无权限引导申请/联系管理员。
- B+C混合产品：根据biz_context判断分流至个人或企业空间。
- INVITE_ONLY：通过biz_context透传邀请码，产品后端自行校验。

## 登出机制
### 本地登出
- 仅退出当前产品，不影响官网及其他产品登录状态。
- 各产品实现本地登出。

### 全局登出（SLO）
- 退出统一认证中心，同时清理官网及接入产品登录状态。
- 首期不强制，后续增强。

## 首次绑定机制
- 用户首次通过官网进入产品时：
  - 已存在本地账号则绑定本地账号。
  - 不存在本地账号则创建本地账号。
  - 存在冲突则进入冲突处理流程。

## 业务上下文透传
### context/register
- 产品后端可预注册业务上下文（如邀请码、推荐码、场景标记），认证中心返回context_id。
- 用户登录后，认证中心在ticket/verify响应中原样透传biz_context。
- 认证中心不解析biz_context的业务含义。

## 安全规范
- redirect_uri必须统一白名单管理。
- 所有授权请求必须校验state，防止CSRF。
- access_token/refresh_token禁止暴露于前端或URL。
- client_secret / product_access_key仅允许服务端保存，不入前端、不入URL、不入日志。
- 生产环境必须全链路HTTPS。
- 日志必须脱敏处理，不记录敏感信息。
- 使用nonce防重放，每次ticket/verify生成新的随机nonce。
- 限流保护：5类接口按分钟桶限流（HTTP 429）。

## 产品接入要求
- 产品需支持统一认证中心登录、官网免二次登录、Unified UID映射、首次绑定、本地登出、全局登出、满足统一安全规范。
- 产品必须提供sso_entry_url接收login_ticket+state。
- 产品必须调用ticket/verify换取UserInfo。
- 产品必须维护unified_uid ↔ local_user_id映射。
- 产品必须建立本地Session（JWT/Cookie）。
- 产品必须保护product_access_key。

## 非建设范围
- 本项目不包含：统一产品业务权限、统一租户体系、统一角色体系、统一菜单体系、统一账号库合并。
- 认证中心不创建产品本地账号、不维护UID ↔ 本地账号映射、不建立产品Session、不校验邀请码/推荐码有效性、不校验企业邮箱/企业代码、不维护租户/组织/角色/权限、不判断产品使用权限。
- 首期不实现OAuth2/OIDC、全局登出不强制、第三方登录不实现。

## 待澄清问题
- 全局登出（SLO）的具体实现方式和触发条件需要进一步明确。
- 冲突处理流程的具体规则和策略（如账号冲突时如何解决）需要补充。
- B端产品权限判断的细化规则（如“有账号无权限”的引导文案和流程）需要确认。
- 首期是否支持第三方登录（如微信、QQ等）尚未明确。
- 联调环境的具体地址和product_access_key交付细节需后续沟通。