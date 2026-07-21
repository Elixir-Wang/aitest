---
name: performance-script-generation
description: 根据白名单接口、负载配置和数据规则生成 Locust 性能测试脚本。自动创建 HttpUser 类、任务权重、认证流程、负载形状和阈值检查。
---

# 性能测试脚本生成专家

根据白名单接口、负载配置和数据规则，生成完整的 Locust 性能测试脚本。

## 事实边界

1. 只使用输入中提供的接口、方法、路径和负载配置。
2. 不新增任何输入中没有的接口、请求头、导入或文件能力。
3. 只生成可被 Locust 直接执行的脚本。
4. 不将认证密钥、Cookie 或其他敏感凭证写入输出。
5. 保持输入中的方法、路径、负载配置和测试数据边界不变。

## 输出目标

生成完整的 `locustfile.py`，包含：

1. **HttpUser 类**：定义模拟用户行为
2. **Task 任务**：使用 `@task` 装饰器定义测试任务
3. **等待时间**：`wait_time = between(min, max)` 模拟真实用户间隔
4. **认证流程**：`on_start()` 方法处理登录和 token 获取
5. **负载形状**：可选的 `LoadTestShape` 类定义复杂负载模式
6. **阈值检查**：可选的事件钩子验证 SLA

## 工作流程

1. 解析白名单接口列表，识别端点、方法、路径和预期负载
2. 根据接口特点选择合适的用户类型（匿名、认证、CRUD）
3. 设计任务权重，反映真实业务流量分布
4. 生成 locustfile.py 文件
5. 如需复杂负载模式，添加自定义 LoadTestShape

## 用户类型选择

| 用户类型 | 适用场景 | 关键特征 |
|----------|----------|----------|
| **匿名用户** | 公开接口测试 | 无认证，仅浏览 |
| **认证用户** | 需要登录的接口 | on_start 获取 token，后续请求携带 |
| **CRUD 用户** | 完整业务流程 | 创建→读取→更新→删除，保留资源 ID |
| **混合用户** | 复杂系统 | 组合多种行为模式 |

## 输出结构

```python
from locust import HttpUser, task, between

class PerformanceUser(HttpUser):
    """性能测试用户"""
    wait_time = between(1, 5)  # 任务间隔（秒）

    def on_start(self):
        """初始化（如登录）"""
        pass

    @task(<weight>)  # 权重，越大概率被执行
    def test_endpoint(self):
        """测试指定端点"""
        self.client.get("/api/endpoint")

    def on_stop(self):
        """清理（如登出）"""
        pass
```

## 项目结构规范

使用 `references/project-structure.md` 中的项目结构规范生成 Locust 项目：

- 每个项目独立的 `performance_testing/` 目录
- 模块化用户类（anonymous/auth/crud）
- 分离的负载形状文件
- 数据文件与脚本分离
- 运行记录在 `runs/` 目录

## 详细模式参考

使用 `references/locust-patterns.md` 中的模式生成：

- 基础 HttpUser 类
- 认证用户（Bearer Token / Cookie）
- CRUD 完整流程
- 自定义负载形状（Step / Spike / Soak）
- 数据驱动模式
- 阈值检查事件钩子
- FastHttpUser 高性能模式

## 执行指南

使用 `references/execution-guide.md` 运行生成的脚本：

- 本地交互模式：`locust -f locustfile.py --host http://api.example.com`
- 无头 CI 模式：`locust --headless --users 50 --spawn-rate 10 -t 2m`
- 分布式模式：master + worker 架构
- 结果分析：p95/p99 延迟、错误率、吞吐量

## 脚本生成约束

- 不新增接口路径
- 不新增请求头（除认证必需）
- 不新增导入依赖
- 不写死敏感凭证（使用环境变量）
- 保持任务权重合理（高频操作权重高）
- 等待时间模拟真实用户行为

## 输出格式

直接输出完整的 `locustfile.py` 文件内容，包含所有必要的类、方法和配置。不输出 Markdown 包裹的解释文字。
