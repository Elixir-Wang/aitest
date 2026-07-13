# 请求数据规则

- 不输出环境中的敏感明文。
- Header 默认只写本用例额外需要的 header；环境默认 header 由运行时注入。
- 环境摘要已配置鉴权时，正常用例的 `request.headers` 不得重复输出鉴权 header 或鉴权变量占位符。
- `request.path` 保持 OpenAPI 路径模板；路径参数的具体值放入 `test_data`。
- query/body/files 只填接口定义中存在的字段。
- 对 required 字段，没有样例、默认值、枚举或历史用例可参考时，不要编造业务值。
- `multipart/form-data` 文件字段放入 `request.files`，普通表单字段放入 `request.body`。
- 文件路径使用 `${API_UPLOAD_FILE_PATH}` 一类环境变量，不输出本机绝对路径。
- 多文件字段使用文件描述对象数组；每个对象可包含 `path`、`filename`、`content_type`。
- `query`、`body` 和 `files` 不得加入接口定义中未声明的字段；除非文档明确说明额外字段行为并提供稳定预期，不生成额外字段用例。
