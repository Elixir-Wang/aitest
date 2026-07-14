# 工程结构

每个项目拥有独立的测试后端路径，结构如下：

```text
pytest_requests_project/
│
├── pytest.ini                              # pytest 配置
├── conftest.py                             # 根级 fixture
│
├── api/                                    # API 接口封装层
│   ├── __init__.py
│   ├── client.py                          # requests.Session 管理、认证注入
│   └── module_{module}.py                 # 按业务模块的 API 封装
│
├── testcases/                              # 测试用例层
│   ├── __init__.py
│   ├── conftest.py                        # 模块级 fixture
│   │
│   ├── user/                             # 用户模块
│   │   ├── __init__.py
│   │   └── login/                        # 登录功能
│   │       ├── __init__.py
│   │       ├── test_login.py
│   │       └── test_login.yaml
│   │
│   ├── order/                            # 订单模块
│   │   └── ...
│   │
│   └── product/                          # 商品模块
│       └── ...
│
├── utils/                                 # 工具层
│   ├── __init__.py
│   ├── data_loader.py                    # YAML 数据加载
│   ├── logger.py                         # 日志工具
│   └── assert_utils.py                   # 自定义断言
│
├── config/                                # 配置层
│   ├── __init__.py
│   └── settings.py                       # 环境变量配置
│
├── data/                                  # 公共测试数据
│   ├── __init__.py
│   ├── constants.py                      # 常量定义
│   └── common_users.yaml                 # 公共用户数据
│
├── fixtures/                              # 复杂 fixture
│   ├── __init__.py
│   ├── user_fixtures.py                  # 用户相关 fixture
│   └── db_fixtures.py                   # 数据库 fixture
│
├── reports/                               # 测试报告
│   ├── html/
│   └── logs/
│
├── pyproject.toml
└── requirements.txt
```

## 层级职责

| 层级 | 职责 | 生成时机 |
|------|------|---------|
| `pytest.ini` | pytest 配置 | 首次创建 |
| `conftest.py` | 根级 fixture（session 级别） | 首次创建 |
| `api/` | 封装 HTTP 请求逻辑，供测试用例调用 | 首次创建 client，后续增量更新 module |
| `testcases/` | 实际测试逻辑，数据驱动 | 首次创建所有，后续按需更新 |
| `utils/` | 通用工具函数 | 首次创建 |
| `config/` | 环境配置 | 首次创建 |
| `data/` | 公共测试数据（常量、用户等） | 首次创建 |
| `fixtures/` | 复杂 fixture（用户、数据库等） | 首次创建 |
| `reports/` | 测试报告输出目录 | 首次创建 |

## 文件命名规范

- **模块文件夹**: 小写下划线，如 `user/`、`order/`
- **功能文件夹**: 小写下划线，如 `login/`、`create_order/`
- **测试文件**: `test_{feature}.py`，如 `test_login.py`
- **数据文件**: `{feature}.yaml`，如 `login.yaml`
- **API 模块**: `module_{module}.py`，如 `module_user.py`

## 首次 vs 非首次

### 首次执行 (`is_first_time: true`)

创建完整的项目框架，包含所有层级文件。

### 非首次执行 (`is_first_time: false`)

| 场景 | AI 行为 |
|------|---------|
| 新增 endpoint | 创建 `api/module_xxx.py` + `testcases/{module}/{feature}/` |
| 新增用例 | 更新对应 `testcases/{module}/{feature}/test_xxx.yaml` |
| 修改用例 | 更新对应 YAML 文件中的用例数据 |
| 新增模块 | 创建新模块目录结构 |
