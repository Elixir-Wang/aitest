# 段落映射

## 覆盖统计

| 指标 | 数量 |
| --- | ---: |
| 来源文件数 | 2 |
| 来源片段数 | 27 |
| 已合入 | 22 |
| 重复去重 | 0 |
| 明显冲突 | 0 |
| 待澄清 | 0 |
| 不可测试 | 5 |
| 已丢弃 | 0 |
| 未覆盖 | 0 |

## 映射明细

| 来源文件 | 来源标题 | 来源摘要 | 状态 | 目标章节 | 原因 |
| --- | --- | --- | --- | --- | --- |
| docmap-9f4edfb55707e6fa | 1. 项目概述 | 新版百融官网升级后，将承担百系产品统一入口职能。当前百系产品存在独立登录入口、独立账号体系、独立认证方式... | merged | 需求概述 / 需求概述 | 合并到需求概述，作为背景目标。 |
| docmap-9f4edfb55707e6fa | 4. 用户模型 | C端用户、B端用户、B+C混合身份用户 | merged | 用户身份模型 / 用户类型 | 并入用户身份模型模块。 |
| docmap-9f4edfb55707e6fa | 6.1 Unified UID | 所有用户在统一认证中心内拥有唯一身份标识（Unified UID）。 | merged | 用户身份模型 / Unified UID | 合并到Unified UID模块。 |
| docmap-9f4edfb55707e6fa | 6.2 本地账号映射 | 统一认证中心不直接替代各产品本地账号体系，各产品通过Unified UID与本地账号建立映射关系。 | merged | 用户身份模型 / Unified UID | 合并到Unified UID模块，与源文档2重复描述，但保留作为补充。 |
| docmap-9f4edfb55707e6fa | 6.3 首次绑定机制 | 用户首次通过官网进入产品时：已存在本地账号则绑定本地账号；不存在本地账号则创建本地账号；存在冲突则进入冲突处理流程。 | merged | 首次绑定机制 / 首次绑定机制 | 合并到首次绑定机制模块。 |
| docmap-9f4edfb55707e6fa | 7.1 官网登录 | 用户在官网完成统一注册或登录后，建立统一身份状态。 | merged | 登录与SSO / 官网登录 | 合并到登录与SSO模块。 |
| docmap-9f4edfb55707e6fa | 7.2 官网进入产品 | 官网 → 统一认证中心 → 产品侧 → 本地 Session。目标：官网登录后进入产品免二次登录。 | merged | 登录与SSO / SSO票据链路 | 合并到SSO票据链路模块。 |
| docmap-9f4edfb55707e6fa | 7.3 产品直接访问 | 产品 → 统一认证中心 → 登录 → 回跳产品 | merged | 登录与SSO / SSO票据链路 | 合并到SSO票据链路模块。 |
| docmap-9f4edfb55707e6fa | 9.1 本地登出 | 仅退出当前产品，不影响官网及其他产品登录状态。 | merged | 登出机制 / 本地登出 | 合并到登出机制模块。 |
| docmap-9f4edfb55707e6fa | 9.2 全局登出 | 退出统一认证中心，同时清理官网及接入产品登录状态。 | merged | 登出机制 / 全局登出 | 合并到登出机制模块。 |
| docmap-9f4edfb55707e6fa | 10. 安全规范 | 所有redirect_uri必须统一白名单管理；所有授权请求必须校验state；access_token/refresh_token禁止暴露于前端或URL；client_secret仅允许服务端保存；生产环境必须全链路HTTPS；日志必须脱敏处理。 | merged | 安全规范 / 安全规范 | 合并到安全规范模块。 |
| docmap-9f4edfb55707e6fa | 12. 产品接入要求 | 接入产品需满足：支持统一认证中心登录、支持官网免二次登录、支持Unified UID映射、支持首次绑定、支持本地登出、支持全局登出、满足统一安全规范。 | merged | 产品接入要求 / 产品接入要求 | 合并到产品接入要求模块。 |
| docmap-9f4edfb55707e6fa | 13. 非建设范围 | 本项目不包含：统一产品业务权限、统一租户体系、统一角色体系、统一菜单体系、统一账号库合并。 | merged | 非建设范围 / 非建设范围 | 合并到非建设范围模块。 |
| docmap-9f4edfb55707e6fa | 14. 验收标准 | 官网统一注册登录完成；官网进入产品免二次登录；Unified UID生效；首次绑定流程可用；SSO生效；SLO生效。 | not_testable | 非建设范围 / 非建设范围 | 验收标准是测试项，非需求定义，不在正文中展示。 |
| docmap-5c83926b8ca192c7 | 二、首期目标 | 官网统一身份入口、统一UID、SSO票据链路、biz_context透传、安全加固 | merged | 需求概述 / 需求概述 | 合并到需求概述。 |
| docmap-5c83926b8ca192c7 | 三、接入范围 | 用户从新版官网入口点击进入百系产品；用户在官网完成注册/登录后，由官网引导跳转到产品；产品希望通过新增导流入口接入官网统一登录也可支持（可选）；产品通过预注册邀请链接/推荐链接业务上下文（可选）；产品的深链场景选择通过官网认证中心完成身份核验（可选）。 | merged | 登录与SSO / SSO票据链路 | 合并到SSO票据链路模块。 |
| docmap-5c83926b8ca192c7 | 五、核心链路 | 用户访问新版官网 → 用户完成官网登录 → [可选] 产品后端预注册 context_id → 用户点击产品入口，官网服务端调用 ticket/create 生成 login_ticket → 官网跳转至产品 sso_entry_url，携带 login_ticket + state → 产品后端调用认证中心 /api/sso/ticket/verify → 认证中心返回 UserInfo + account_status + return_url + biz_context → 产品侧：查询本地映射 → 老用户绑定/新用户处理/B端权限判断 → 产品侧：建立本地 Session → 用户进入产品 | merged | 登录与SSO / SSO票据链路 | 合并到SSO票据链路模块。 |
| docmap-5c83926b8ca192c7 | 六、产品侧要做什么 | 提供sso_entry_url、调用ticket/verify、维护unified_uid ↔ local_user_id映射、建立产品本地Session、处理return_url跳转、处理biz_context、处理B端权限判断、处理老用户绑定、调用context/register、保护product_access_key | merged | 产品接入要求 / 产品接入要求 | 合并到产品接入要求模块。 |
| docmap-5c83926b8ca192c7 | 七、认证中心提供什么 | 注册/登录、统一UID、login_ticket、ticket校验、UserInfo、biz_context透传、account_status、context/register、限流保护、nonce防重放、审计日志 | merged | 登录与SSO / SSO票据链路 | 合并到SSO票据链路模块，与源文档1互补。 |
| docmap-5c83926b8ca192c7 | 八、认证中心不做什么 | 创建产品本地账号、维护UID↔本地账号映射、建立产品Session、校验邀请码/推荐码有效性、校验企业邮箱/企业代码、维护租户/组织/角色/权限、判断产品使用权限、实现OAuth2/OIDC、全局登出、第三方登录 | merged | 非建设范围 / 非建设范围 | 合并到非建设范围模块。 |
| docmap-5c83926b8ca192c7 | 九、产品接入模式分类 | C/B/B+C/INVITE_ONLY四种模式及其推荐策略 | merged | 用户身份模型 / 用户类型 | 合并到用户身份模型模块。 |
| docmap-5c83926b8ca192c7 | 十、原产品登录入口保留原则 | 首期不要求迁移，原入口可继续保留。官网统一认证中心主要承接新增链路。 | merged | 非建设范围 / 非建设范围 | 合并到非建设范围模块。 |
| docmap-5c83926b8ca192c7 | 十三、安全要求 | product_access_key仅后端；login_ticket不作登录态；nonce每次唯一；HTTPS调用认证中心；产品建立本地Session | merged | 安全规范 / 安全规范 | 合并到安全规范模块。 |
| docmap-5c83926b8ca192c7 | 十四、验收标准 | 正向链路：context/register → login → ticket/create → ticket/verify → 建立 Session → return_url 跳转；异常链路：票据重用、state不符、nonce重放、product_access_key无效；审计日志无敏感明文 | not_testable | 非建设范围 / 非建设范围 | 验收标准是测试项，非需求定义，不在正文中展示。 |
| docmap-5c83926b8ca192c7 | 文档定位 | 本文档是总览/首读材料。不替代接口契约和开发指南。正式开发请继续阅读后续专项文档。 | not_testable |  | 文档定位说明，非需求。 |
| docmap-5c83926b8ca192c7 | 阅读建议 | 请至钉钉文档查看附件《产品接入配置表》。 | not_testable |  | 阅读建议和附件链接，非需求。 |
| docmap-5c83926b8ca192c7 | 十五、当前统一认证中心已自测验证了的能力 | 手机号/邮箱注册登录、context/register、ticket/create（带context_id）、ticket/verify、mock-product-server完整E2E链路、nonce防重放、限流、审计日志脱敏、Actuator最小暴露、product_access_key认证均已验证 | not_testable |  | 测试状态描述，非需求。 |
