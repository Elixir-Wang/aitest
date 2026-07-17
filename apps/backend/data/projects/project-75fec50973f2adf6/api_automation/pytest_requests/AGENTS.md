# pytest_requests 项目规范

## 项目结构

```
pytest_requests/
├── AGENTS.md              # 本文件 - 项目规范
├── pytest.ini             # pytest 配置
├── pyproject.toml         # 项目元数据与依赖
├── conftest.py            # 根级 fixture（api_client session fixture）
├── api/                   # API 封装层
│   ├── __init__.py
│   ├── client.py          # 共享 HTTP 客户端（环境变量鉴权）
│   ├── module_*.py        # 按模块划分的 API 封装
├── testcases/             # 测试用例
│   ├── __init__.py
│   ├── conftest.py        # 测试模块级 fixture
│   ├── <module>/          # 按模块划分的测试目录
│       ├── test_*.py      # 测试代码
│       ├── test_*.yaml    # 测试数据（与测试文件同名）
├── utils/                 # 工具函数
│   ├── __init__.py
│   ├── data_loader.py     # YAML 测试数据加载
│   ├── assertions.py      # 断言工具（支持 status_code, jsonpath, schema 等）
│   ├── assert_utils.py    # 断言辅助函数
├── support/               # 支撑模块
│   ├── __init__.py
│   ├── client.py          # ApiClient 实现
│   ├── auth.py            # 鉴权头构建
│   ├── assertions.py      # 断言实现
│   ├── scenario.py        # 场景测试引擎
├── config/                # 配置模块
│   ├── __init__.py
├── data/                  # 测试数据目录
│   ├── __init__.py
```

## 核心规则

1. **不硬编码敏感信息**：base URL、Token、Cookie、密码必须通过环境变量注入。
2. **环境变量占位符**：使用 `${API_VAR_<UPPER_SNAKE_NAME>}` 格式。
3. **测试数据分离**：测试用例数据放在 YAML 文件中，与测试代码同目录。
4. **不发送真实请求**：pytest --collect-only 验证时不得发送真实 API 请求。
5. **保留未选中文件**：只处理当前选中的 endpoint，不删除其他文件。
