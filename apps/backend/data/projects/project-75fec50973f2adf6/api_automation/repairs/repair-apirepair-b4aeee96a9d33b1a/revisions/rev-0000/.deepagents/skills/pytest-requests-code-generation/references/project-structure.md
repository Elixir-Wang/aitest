# 工程结构

每个业务项目拥有一个独立的 `pytest_requests` 目录。DeepAgents 直接以该目录作为 filesystem root。

```text
pytest_requests/
├── AGENTS.md
├── pytest.ini
├── conftest.py
├── api/
│   ├── __init__.py
│   └── client.py
├── testcases/
│   ├── __init__.py
│   ├── conftest.py
│   └── <normalized-path>/<method>/
│       ├── test_api.py
│       └── cases.yaml
├── utils/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── assertions.py
│   └── assert_utils.py
├── support/
│   └── __init__.py
├── config/
│   └── __init__.py
└── data/
    └── __init__.py
```

## 层级职责

| 层级 | 职责 |
|---|---|
| `pytest.ini` | pytest 配置 |
| `conftest.py` | 根级 fixture 和运行时 client |
| `api/` | 共享 HTTP client 和 endpoint 封装 |
| `testcases/` | 数据驱动的 endpoint 测试 |
| `utils/` | YAML 加载和断言工具 |
| `support/` | 可复用的测试支持模块 |
| `config/` | 项目配置包 |
| `data/` | 公共测试数据包 |

## 增量规则

- Agent 先读取现有结构，再修改当前项目。
- endpoint 目录和文件由后端输入中的 `artifacts` 确定，Agent 不得重新推导路径。
- 新增 endpoint 不创建新的 pytest 项目。
- 未选中的 endpoint 文件必须保留。
- 修改后先收集变更测试，再收集整个项目。
