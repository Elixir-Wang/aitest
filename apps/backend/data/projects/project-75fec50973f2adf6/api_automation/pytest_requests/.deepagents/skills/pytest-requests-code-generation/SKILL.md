---
name: pytest-requests-code-generation
description: 在当前业务项目的 pytest_requests 目录中生成或更新 pytest + Requests 接口测试
---

# pytest + Requests 项目生成

你直接操作当前项目的 pytest_requests 根目录。先读取现有文件，再决定创建或修改哪些文件；不要创建第二个测试项目。

## 核心约束

- 只使用输入中的 endpoint、cases 和现有项目文件作为事实来源。
- 只处理当前请求选中的 endpoint，保留未选中的 endpoint 文件。
- 先确保公共框架完整，再生成接口测试文件。
- 不生成输入中不存在的路径、字段、状态码、业务规则或断言。
- 不嵌入 base URL、token、cookie、密码和本机绝对路径。
- 环境鉴权由共享 client 和运行时环境变量注入。
- 普通环境变量占位符沿用 `${API_VAR_<UPPER_SNAKE_NAME>}`。
- 上传文件使用环境变量占位；下载响应不得使用 JSONPath 断言。
- 修改后必须调用 `run_pytest_collection` 验证，不得发送真实 API 请求。
- collection 失败时读取 traceback 和相关文件，修复后重试。

## Oracle 执行与观察证据

- 数据文件必须保留后端提供的 `case_id`、`test_point_key` 和 `oracle_status`，不得自行推断、合并或改名。
- `confirmed` 用例正常发送请求并执行全部断言。
- `inferred` 用例正常发送请求并执行当前推断断言，同时记录实际响应供失败后校准。
- `needs_confirmation` 用例正常发送请求，不执行尚无事实依据的强 Oracle 断言，但请求构造、网络异常和响应解析错误仍按测试失败处理。
- `inferred` 和 `needs_confirmation` 都必须将脱敏观察证据追加到环境变量 `API_OBSERVATION_RESULT_PATH` 指定的 JSON 文件。
- 每条观察至少包含 `case_id`、`test_point_key`、`status_code`、`response_headers` 和 `response_body`；禁止写入请求 Header、请求 Cookie、认证配置或环境变量值。
- 响应 Header 必须移除 `authorization`、`cookie`、`set-cookie`、`x-api-key`、`api-key`、`cybertron-robot-key`、`cybertron-robot-token` 等敏感字段。
- 响应 Body 必须递归脱敏名称包含 `token`、`password`、`secret`、`cookie`、`authorization`、`api_key`、`apikey` 的字段；二进制、流式或不可解析响应只记录受限长度的类型和摘要，不保存原始内容。
- 共享 observation 工具必须使用标准库文件锁实现跨进程互斥：Windows 使用 `msvcrt`，POSIX 使用 `fcntl`；锁内重新读取现有 `observations`、按 `case_id + test_point_key` 合并、写临时文件并用原子替换提交，禁止直接覆盖其他测试已写入的记录。
- 未设置 `API_OBSERVATION_RESULT_PATH` 时不得写入本地默认路径，也不得影响测试执行结果。

## 必需公共文件

```text
AGENTS.md
pytest.ini
pyproject.toml
conftest.py
api/__init__.py
api/client.py
testcases/__init__.py
testcases/conftest.py
utils/__init__.py
utils/data_loader.py
utils/assertions.py
utils/assert_utils.py
support/__init__.py
config/__init__.py
data/__init__.py
```

## 接口文件规则

- 每个 endpoint 使用后端提供的 `artifacts.directory`、`artifacts.test_file` 和 `artifacts.data_file` 维护文件归属。
- `artifacts.test_file` 和 `artifacts.data_file` 是唯一合法输出文件，不得自行改名或改目录。
- 测试代码与相邻 YAML 数据文件放在后端指定的同一 endpoint 目录。
- 新增 endpoint 只新增对应模块和数据文件。
- 更新 endpoint 只修改对应 endpoint 文件，除非 collection 暴露了必要的共享依赖修复。
- 整个项目 collection 成功后才报告生成成功。
