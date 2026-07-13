---
name: pytest-requests-code-generation
description: 将单个接口及其已确认结构化用例转换为稳定的 pytest + Requests 逻辑文件集合
---

# pytest + Requests 代码生成

每次只处理输入中的一个 endpoint。一个 endpoint 对应一个测试模块和一个数据文件，每条用例必须通过 `pytest.mark.parametrize` 独立执行和报告。

每个 endpoint 独占一个 `endpoints/<endpoint-key>/` 目录，其中固定包含：

```text
endpoints/<endpoint-key>/
├── test_api.py
└── cases.json
```

## 约束

- 只使用输入中的 endpoint、cases 和框架配置。
- 不接收或推导 `project_id`、数据库连接、用户权限和物理输出目录。
- 不生成输入中不存在的路径、字段、状态码、业务规则或断言。
- 不嵌入 base URL、token、cookie、密码和本机绝对路径。
- 环境鉴权由根级 `support/auth.py` 和执行器统一注入；不得在正常 endpoint 用例中新增鉴权占位符，也不得把环境鉴权值复制进 `cases.json`。
- 普通环境变量占位符必须沿用输入用例中的 `${API_VAR_<UPPER_SNAKE_NAME>}`，不得改写成执行器未导出的裸变量名。
- 当前执行器通过请求级空字符串覆盖环境默认鉴权头；不得将这种请求改写为真正删除 header，或把“header 为空”改名为“header 缺失”。
- 上传文件使用环境变量占位；下载响应不得使用 JSONPath 断言。
- 共享 client、auth 和 assertions 行为保持稳定，最终代码由确定性渲染器输出。
- endpoint key 必须包含稳定 endpoint ID；method 和 path 只承担可读性。
- `test_api.py` 必须读取同目录的 `cases.json`，不能跨顶层 `tests/` 和 `data/` 目录配对。
- `pytest.ini` 必须将套件根目录加入 `pythonpath`，确保 `conftest.py` 和测试模块能够导入 `support` 包。
- 生成或更新套件后必须执行真实的 `pytest --collect-only` 验证；不能只检查文件存在或模板字符串。

## 输出

只返回逻辑文件 key、文件类型、语言和内容。文件 key 必须是相对路径，不包含项目目录。
