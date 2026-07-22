# 断言规范

- 每条用例必须包含 `status_code` 断言。
- 负向用例若与成功响应同为 HTTP 200，必须同时断言文档明确的固定业务错误码；没有固定错误码时不得生成该负向用例。
- 对 JSON 成功响应，OpenAPI Schema 的 `properties` 中声明的字段必须生成 `jsonpath_exists`；当 schema 明确且不为 nullable 时，还必须生成 `jsonpath_type`，类型使用 `string`、`number`、`boolean`、`object`、`array` 或 `null`。后端提供的 `required_assertions` 必须原样保留。
- 文档明确字段值时，才使用 `jsonpath_equals`。
- 不要对时间戳、随机 ID、token 等动态值做固定等值断言。
- 响应 schema 明确关键字段时，使用关键字段存在断言表达结构校验。
- 下载响应可使用 `content_type`、`header_exists`、`header_equals`、`body_not_empty`。
- 只有文档提供固定 SHA-256 时才使用 `body_sha256`。
- 二进制响应不得使用 JSONPath 断言。
