# 生成原则

- P0/P1：核心成功路径、认证/授权、资金/数据写入、关键查询。
- P2：常见异常、缺少必填参数、格式错误、业务状态不满足。
- P3：低频边界、兼容性或非核心错误分支。
- OpenAPI 有 `example`、`examples`、`default`、`enum` 时可以据此构造 ready 请求。
- OpenAPI 只有 schema 没有业务可用值时，优先标记 needs_input。
- 对 GET/DELETE 优先使用 query/path 参数；对 POST/PUT/PATCH 优先使用 request body。
- 对链路型场景，只在输入提供足够上下文时生成 scenario 覆盖。
