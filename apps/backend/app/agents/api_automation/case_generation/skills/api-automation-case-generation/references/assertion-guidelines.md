# 断言规范

- 每条用例必须包含 `status_code` 断言。
- 文档明确响应字段时，可以补充 `jsonpath_exists`。
- 文档明确字段值时，才使用 `jsonpath_equals`。
- 不要对时间戳、随机 ID、token 等动态值做固定等值断言。
- 响应 schema 明确关键字段时，使用关键字段存在断言表达结构校验。
- 下载响应可使用 `content_type`、`header_exists`、`header_equals`、`body_not_empty`。
- 只有文档提供固定 SHA-256 时才使用 `body_sha256`。
- 二进制响应不得使用 JSONPath 断言。
