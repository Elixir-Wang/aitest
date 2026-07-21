# Locust 性能测试项目结构

每个业务项目拥有一个独立的 `performance_testing` 目录，参考 `api_automation` 的分层架构。

## 完整项目结构

```text
performance_testing/
├── AGENTS.md                    # 项目规范
├── locust.conf                  # Locust 默认配置
├── locustfile.py                # 主入口（CI + 交互）
├── locust/
│   ├── __init__.py
│   ├── users/
│   │   ├── __init__.py
│   │   ├── anonymous_user.py    # 匿名浏览用户
│   │   ├── auth_user.py        # 认证用户
│   │   └── crud_user.py        # CRUD 流程用户
│   ├── shapes/
│   │   ├── __init__.py
│   │   ├── step_load.py        # 步进负载形状
│   │   ├── spike_load.py       # 峰值负载形状
│   │   └── soak_load.py        # 浸泡负载形状
│   ├── tasks/
│   │   ├── __init__.py
│   │   └── endpoints.py        # 端点任务定义
│   └── hooks/
│       ├── __init__.py
│       └── thresholds.py       # 阈值检查钩子
├── data/
│   ├── __init__.py
│   ├── users.csv               # 测试用户数据
│   └── payloads.json           # 请求载荷数据
├── support/
│   ├── __init__.py
│   ├── auth.py                 # 认证辅助
│   └── config.py               # 配置加载
└── runs/                       # 运行记录（自动生成）
    └── perfrun-xxxxxxxx/
        ├── locustfile.py       # 生成的脚本
        ├── runtime.json        # 运行时配置
        ├── stdout.log          # 运行日志
        └── stderr.log          # 错误日志
```

## 与 api_automation 对比

| 层级 | api_automation (pytest) | performance_testing (Locust) |
|------|-------------------------|------------------------------|
| 入口 | `conftest.py` | `locustfile.py` |
| 客户端 | `api/client.py` | 内置 `self.client` |
| 测试用例 | `testcases/` | `locust/users/` |
| 数据驱动 | `data/` + `cases.yaml` | `data/` + JSON/CSV |
| 工具函数 | `utils/` | `support/` |
| 断言 | `support/assertions.py` | `locust/hooks/thresholds.py` |

## 层级职责

| 目录 | 职责 |
|------|------|
| `locustfile.py` | 主入口，导入用户类和形状 |
| `locust/users/` | 用户行为类（HttpUser 子类） |
| `locust/shapes/` | 负载形状（LoadTestShape 子类） |
| `locust/tasks/` | 端点任务定义 |
| `locust/hooks/` | 事件钩子（阈值检查） |
| `data/` | 测试数据（用户、载荷） |
| `support/` | 认证辅助、配置加载 |
| `runs/` | 运行记录和报告 |

## 命名规范

| 文件/目录 | 命名方式 | 示例 |
|-----------|----------|------|
| 用户类 | `<行为>_user.py` | `auth_user.py`, `crud_user.py` |
| 形状类 | `<类型>_load.py` | `step_load.py`, `spike_load.py` |
| 钩子文件 | `thresholds.py` | 阈值检查 |
| 数据文件 | 语义命名 | `users.csv`, `products.json` |

## 增量规则

1. Agent 先读取现有结构，再修改当前项目。
2. locustfile.py 作为统一入口，导入所有用户类和形状。
3. 新增端点不创建新的 Locust 项目。
4. 未选中的用户类文件必须保留。
5. 敏感信息使用环境变量，不硬编码。
