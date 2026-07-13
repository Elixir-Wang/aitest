# 工程结构

```text
pytest_requests/
├── pyproject.toml
├── uv.lock
├── pytest.ini
├── conftest.py
├── README.md
├── support/
│   ├── __init__.py
│   ├── client.py
│   ├── auth.py
│   └── assertions.py
└── endpoints/
    └── <endpoint-key>/
        ├── test_api.py
        └── cases.json
```

根配置、fixture 和 `support/` 由项目内所有接口共享。每个 endpoint 只拥有自己的 `endpoints/<endpoint-key>/` 目录，测试代码通过相邻路径读取 `cases.json`。
