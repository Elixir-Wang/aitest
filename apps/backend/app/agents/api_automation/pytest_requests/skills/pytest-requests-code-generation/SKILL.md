---
name: pytest-requests-code-generation
description: 将单个接口及其已确认结构化用例转换为稳定的 pytest + Requests 逻辑文件集合
---

# pytest + Requests 代码生成

每次只处理输入中的一个 endpoint。根据 `is_first_time` 标志决定是初始化完整框架还是增量更新。

## 核心约束

- 只使用输入中的 endpoint、cases 和框架配置。
- 不接收或推导 `project_id`、数据库连接、用户权限和物理输出目录。
- 不生成输入中不存在的路径、字段、状态码、业务规则或断言。
- 不嵌入 base URL、token、cookie、密码和本机绝对路径。
- 环境鉴权由 `api/client.py` 统一注入；不得在正常 endpoint 用例中新增鉴权占位符。
- 普通环境变量占位符必须沿用输入用例中的 `${API_VAR_<UPPER_SNAKE_NAME>}`。
- 上传文件使用环境变量占位；下载响应不得使用 JSONPath 断言。
- 生成或更新套件后必须执行真实的 `pytest --collect-only` 验证。

## 首次 vs 非首次

### 首次执行 (`is_first_time: true`)

创建完整的项目框架，包含所有层级：

```
{project_name}/
├── api/                    # API 接口封装层
│   ├── __init__.py
│   ├── client.py           # requests.Session 管理
│   └── module_{module}.py  # 按业务模块的 API 封装
│
├── testcases/              # 测试用例层
│   ├── __init__.py
│   ├── conftest.py         # 全局 fixture
│   └── {module}/
│       └── {feature}/
│           ├── __init__.py
│           ├── test_xxx.py    # 测试代码
│           └── test_xxx.yaml  # 测试数据
│
├── utils/                  # 工具层
│   ├── __init__.py
│   ├── data_loader.py      # YAML 数据加载
│   ├── logger.py           # 日志
│   └── assert_utils.py     # 断言工具
│
├── config/                 # 配置层
│   ├── __init__.py
│   └── settings.py         # 环境配置
│
├── pytest.ini
├── pyproject.toml
└── requirements.txt
```

### 非首次执行 (`is_first_time: false`)

分析现有结构后增量更新：

| 操作 | AI 行为 |
|------|---------|
| 新增 endpoint | 创建 `api/module_xxx.py` + `testcases/{module}/{feature}/` |
| 新增用例 | 更新对应 `testcases/{module}/{feature}/test_xxx.yaml` |
| 修改用例 | 更新对应 YAML 文件中的用例数据 |
| 新增模块 | 创建新模块目录结构 |

## 输出

只返回逻辑文件 key、文件类型、语言和内容。文件 key 必须是相对路径，不包含项目目录。
