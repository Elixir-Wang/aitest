# 负载测试执行指南

## Locust 执行方式

### 本地交互模式

```bash
locust -f locustfile.py --host http://localhost:5000
```

然后打开 http://localhost:8089 配置用户数和启动速率。

### 无头模式（CI/CD）

```bash
locust \
  -f locustfile.py \
  --headless \
  --users 50 \
  --spawn-rate 10 \
  --run-time 2m \
  --host http://localhost:5000 \
  --csv reports/results \
  --html reports/report.html \
  --exit-code-on-error 1
```

## 测试类型

| 类型 | 目的 | 用户数 | 持续时间 | 使用场景 |
|------|------|--------|----------|----------|
| **Smoke** | 验证脚本可用 | 1–5 | 1 min | 每个 PR |
| **Load** | 验证 SLA 下的性能 | 50–200 | 5–15 min | 预发布 |
| **Stress** | 找到破环点 | 递增到 500+ | 10–20 min | 发布里程碑 |
| **Soak** | 发现内存泄漏/性能衰减 | 50–100 | 1–4 hours | 季度 |
| **Spike** | 测试突发流量 | 0→500→0 | 5 min | 活动准备 |

## 常见参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `-f` | locustfile 路径 | `-f tests/load/locustfile.py` |
| `--host` | 目标主机 | `--host http://api.example.com` |
| `--users` | 并发用户数 | `--users 100` |
| `--spawn-rate` | 用户生成速率（每秒） | `--spawn-rate 10` |
| `--run-time` | 测试持续时间 | `--run-time 5m` |
| `--headless` | 无头模式（无 Web UI） | `--headless` |
| `--csv` | CSV 结果输出路径 | `--csv reports/results` |
| `--html` | HTML 报告路径 | `--html reports/report.html` |
| `--exit-code-on-error` | 失败时退出码非零 | `--exit-code-on-error 1` |

## 分布式模式

### Master 节点

```bash
locust -f locustfile.py --master --host http://api.example.com
```

### Worker 节点

```bash
locust -f locustfile.py --worker --master-host <master-ip>
```

### 启动分布式测试

```bash
# 在 master 机器上
locust -f locustfile.py --master

# 在多台 worker 机器上
locust -f locustfile.py --worker --master-host <master-ip>
```

## 阈值检查

### 通过事件钩子检查

```python
from locust import events

@events.quitting.add_listener
def check_thresholds(environment, **kwargs):
    stats = environment.stats

    # 检查错误率
    if stats.total.fail_ratio > 0.05:
        print(f"ERROR: Fail rate {stats.total.fail_ratio:.2%} exceeds 5% threshold")

    # 检查响应时间
    if stats.total.avg_response_time > 500:
        print(f"ERROR: Avg response time {stats.total.avg_response_time}ms exceeds 500ms")

    # 检查 p95
    p95 = stats.total.get_response_time_percentile(0.95)
    if p95 > 1000:
        print(f"ERROR: p95 response time {p95}ms exceeds 1000ms")
```

## 结果分析

### 关键指标

| 指标 | 说明 | SLA 示例 |
|------|------|----------|
| `RPS` | 每秒请求数 | > 100 rps |
| `Avg` | 平均响应时间 | < 200ms |
| `p95` | 95 百分位响应时间 | < 500ms |
| `p99` | 99 百分位响应时间 | < 1000ms |
| `Fail %` | 失败率 | < 1% |

### Web UI 指标解读

- **Aggregated**：所有请求汇总
- **Requests**：总请求数
- **Fails**：失败请求数
- **Median**：中位数响应时间
- **Average**：平均响应时间
- **p90/p95/p99**：百分位数
- **Min/Max**：最小/最大响应时间
- **Content Size**：响应体大小

## 结果分析检查清单

| # | 检查项 | 失败时行动 |
|---|--------|-----------|
| 1 | p95 延迟在阈值内 | 分析慢查询，优化索引或缓存 |
| 2 | 错误率在阈值内 | 检查错误日志，定位失败端点 |
| 3 | 吞吐量达标 | 水平扩容或优化瓶颈 |
| 4 | 无内存持续增长 | 检查泄漏，连接池耗尽 |
| 5 | 延迟一致性 | 检查连接池、缓存、索引 |
| 6 | 极限时优雅降级 | 验证限流、熔断器 |
