# pytest-requests 自动化测试项目

## 项目结构

```
pytest_requests/
├── AGENTS.md              # 项目说明
├── pytest.ini             # pytest 配置
├── conftest.py            # 项目级 conftest（共享 fixture）
├── api/
│   ├── __init__.py
│   └── client.py          # 封装 requests.Session，从环境变量读取 base URL 和鉴权
├── testcases/
│   ├── __init__.py
│   ├── conftest.py        # 测试用例级 conftest（接口测试 fixture）
│   └── openapi/v1/agent/analysis/post/
│       ├── test_api.py    # 接口测试文件
│       └── cases.yaml     # 测试用例数据（只读，由后端写入）
├── utils/
│   ├── __init__.py
│   ├── data_loader.py     # 加载 YAML 用例数据
│   ├── assertions.py      # 断言工具（pytest 封装）
│   ├── assert_utils.py    # 通用断言辅助函数
│   └── observations.py    # 观察证据记录（跨进程安全）
├── support/
│   └── __init__.py
├── config/
│   └── __init__.py
└── data/
    └── __init__.py
```

## 规则

- base URL、Token、Cookie、密码通过环境变量注入，不写入源代码。
- 每个 endpoint 的测试文件和数据文件由 artifacts 指定，不得自行改名。
- 数据文件只读，不得覆盖或修改。
- `inferred` / `needs_confirmation` 用例必须记录观察证据。