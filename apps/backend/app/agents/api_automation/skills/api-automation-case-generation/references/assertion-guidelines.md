# 断言规范

- 每条用例必须包含 `status_code` 断言。
- 文档明确响应字段时，可以补充 `jsonpath_exists`。
- 文档明确字段值时，才使用 `jsonpath_equals`。
- 不要对时间戳、随机 ID、token 等动态值做固定等值断言。
- 响应 schema 明确关键字段时，可以使用 `schema_contains` 表示结构断言。
