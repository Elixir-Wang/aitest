# 需求理解

## 1. 需求背景

第三方渠道服务当前已有 Python 版本（包括 gateway 和 worker），现已使用 Go 重构。需要将 Go 版本逐步上线，并保证上线过程中的流量迁移平稳、异常时可快速回退。

关键约束：
- Go gateway 和 Python gateway 对第三方 webhook 的处理方式不同。
- Go gateway 和 Python gateway 写入 RabbitMQ 的消息结构不同。
- 因此 Go worker 不能直接消费 Python gateway 写入的队列消息，Python worker 也不能直接消费 Go gateway 写入的队列消息。

基于该约束，本次上线不采用 worker 层混合消费，也不采用同一队列竞争消费，而采用 gateway 与 worker 成对灰度的方式。

## 2. 目标与价值

本次上线目标：
1. 支持 Go gateway + Go worker 独立承接第三方渠道流量。
2. 保证 Python 链路和 Go 链路互相隔离，避免队列消息格式混用。
3. 根据第三方平台 webhook 配置能力选择不同灰度方式。
4. 支持异常时快速切回 Python 链路。
5. 保证迁移期间消息不丢失、不重复回复、可观测、可排查。

## 3. 用户角色与使用场景

| 用户角色 | 使用场景 | 用户目标 | 已知约束 |
|---------|---------|---------|---------|
| 运维/发布工程师 | 灰度上线 Go 版本服务 | 逐步将第三方渠道流量从 Python 链路迁移到 Go 链路，保证平稳过渡 | 两套 gateway 写入 MQ 的消息结构不一致，不能混用 |
| 运维/发布工程师 | 异常回退 | 发现异常时快速将流量切回 Python 链路 | 优先切入口流量，而非搬运队列存量消息 |
| 第三方平台 | 发送 webhook 消息 | 将消息发送到配置的 gateway URL | 根据平台能力，可配置到机器人级别或渠道级别 |
| 客服/业务运营 | 观察迁移过程 | 确认消息正常处理，无丢失或重复 | 原文未说明运营侧是否有专属监控面板 |

## 4. 功能范围

**包含的功能**：
1. Go gateway 独立接收第三方渠道 webhook 请求
2. Go gateway 将消息写入独立 Go 队列
3. Go worker 独立消费 Go 队列消息并处理
4. Python gateway 继续处理未迁移渠道的流量
5. Python worker 继续消费 Python 队列消息
6. A 类平台支持按机器人维度灰度迁移和回退
7. B 类平台支持按渠道维度整体切换和回退
8. 队列完全隔离：Go 队列与 Python 队列独立命名、独立 retry queue 和 DLQ
9. 回退时优先切入口流量，Go worker 继续处理存量消息

**不包含的功能**：
1. 不采用 worker 层混合消费
2. 不采用同一队列竞争消费
3. 不允许 Go gateway 写入 Python 队列
4. 不允许 Python gateway 写入 Go 队列
5. 不允许 Go worker 消费 Python 队列
6. 不允许 Python worker 消费 Go 队列
7. 不允许 Go 队列消息直接搬到 Python 队列
8. 不允许 Python 队列消息直接搬到 Go 队列
9. 原文未说明是否包含自动化灰度发布平台或工具

## 5. 业务流程

### A 类平台（支持按机器人配置 webhook）灰度迁移流程

1. 运维工程师确认 Go gateway 和 Go worker 已部署就绪
2. 运维工程师确认 Go 队列已创建（独立命名，如 cyber_telegram_go）
3. 运维工程师确认路由配置正确：Go gateway 只写 Go 队列，Go worker 只消费 Go 队列
4. 运维工程师在第三方平台将目标机器人的 webhook URL 从 Python gateway 改为 Go gateway
5. 第三方平台将 webhook 请求发送到 Go gateway
6. Go gateway 处理请求并写入 Go 队列
7. Go worker 从 Go 队列消费消息并处理
8. 运维工程师观察迁移是否正常
9. 如异常，执行回退流程（见下方回退流程）

### B 类平台（不支持按机器人配置 webhook）灰度迁移流程

1. 运维工程师确认 Go gateway 和 Go worker 已部署就绪
2. 运维工程师确认 Go 队列已创建
3. 运维工程师确认路由配置正确
4. 运维工程师在第三方平台将该渠道的 webhook URL 从 Python gateway 改为 Go gateway
5. 第三方平台将 webhook 请求发送到 Go gateway
6. Go gateway 处理请求并写入 Go 队列
7. Go worker 从 Go 队列消费消息并处理
8. 运维工程师观察迁移是否正常
9. 如异常，执行回退流程

### A 类平台回退流程

**场景一：Go worker 正常，仅需回退某个机器人**
1. 运维工程师在第三方平台将异常机器人的 webhook 改回 Python gateway URL
2. Go gateway 不再接收该机器人新流量
3. Go worker 继续处理 Go queue 中该机器人已入队消息
4. 运维工程师观察 Go queue ready / unacked 清零

**场景二：Go worker 本身异常**
1. webhook 立即切回 Python gateway
2. 暂停 Go worker
3. 保留 Go queue / Go DLQ
4. 评估修复后重放或人工补偿

### B 类平台回退流程

**场景一：Go worker 可以继续处理**
1. 将该渠道 webhook 从 Go gateway URL 改回 Python gateway URL
2. Go gateway 不再接收该渠道新流量
3. Python gateway 恢复接收该渠道流量
4. Python worker 继续消费 Python 队列
5. Go worker 处理 Go 队列存量消息

**场景二：Go worker 不可用**
1. 入口立即切回 Python
2. 暂停 Go worker
3. 保留 Go queue / Go DLQ
4. 根据原始 webhook、业务日志或转换脚本评估补偿

## 6. 状态流转

原文未定义业务对象（如机器人、渠道、迁移任务）的明确状态机。文档主要描述的是运维操作流程而非业务对象状态流转。

**可推断的运维操作状态**（原文未明确定义状态机）：

| 当前状态 | 触发条件/动作 | 执行角色 | 下一状态 | 可观察结果 |
|---------|-------------|---------|---------|-----------|
| Python 链路运行中 | 将 webhook 改为 Go gateway URL | 运维工程师 | 灰度迁移中 | 流量开始进入 Go 链路 |
| 灰度迁移中 | 观察正常 | 运维工程师 | Go 链路运行中 | 消息正常处理 |
| 灰度迁移中 | 发现异常，执行回退 | 运维工程师 | Python 链路运行中 | 流量切回 Python 链路 |
| Go 链路运行中 | 发现异常，执行回退 | 运维工程师 | Python 链路运行中 | 流量切回 Python 链路 |
| Go 链路运行中 | Go worker 处理完 Go queue 存量消息 | 运维工程师 | 迁移完成 | Go queue ready/unacked 清零 |

原文未说明：
- 迁移完成后 Go 链路和 Python 链路的最终状态（是否下线 Python 链路）
- 灰度迁移中 Go worker 异常时 Go queue 中存量消息的处理状态
- 回退后 Go queue 中存量消息的最终处理时限

## 7. 业务规则

| 规则类型 | 触发条件 | 判断逻辑 | 处理结果 |
|---------|---------|---------|---------|
| 链路隔离规则 | 任何消息写入或消费 | Go gateway 只能写 Go 队列，Python gateway 只能写 Python 队列 | 禁止跨语言混用 |
| 队列隔离规则 | 队列创建或消费 | Go 队列和 Python 队列独立命名、独立 retry queue 和 DLQ | 队列完全隔离 |
| 消费隔离规则 | worker 启动 | Go worker 只消费 Go 队列，Python worker 只消费 Python 队列 | 禁止跨语言消费 |
| 灰度粒度规则 | A 类平台迁移 | 支持按机器人维度灰度 | 可单机器人迁移和回退 |
| 灰度粒度规则 | B 类平台迁移 | 不支持按机器人灰度 | 必须渠道级整体切换 |
| 回退优先级规则 | 异常回退 | 优先将新流量切回 Python gateway | 不优先搬运 Go 队列消息 |
| 回退后存量处理规则 | 回退后 Go worker 正常 | Go worker 继续处理 Go queue 存量消息 | 等待 Go queue ready/unacked 清零 |
| 回退后存量处理规则 | 回退后 Go worker 不可用 | 暂停 Go worker，保留 Go queue / Go DLQ | 人工评估重放或补偿 |
| 队列命名规则 | 创建 Go 队列 | 在原 Python 队列名后加 `_go` 后缀 | 如 cyber_telegram → cyber_telegram_go |
| 多渠道迁移规则 | 同时迁移多个渠道 | 每个渠道单独配置 Go 队列，不共用 | 如 CHANNEL_GATEWAY_ENABLED_PLATFORMS=telegram,lark |

## 8. 页面与交互

原文未说明具体的页面和交互设计。本文档为灰度上线评审方案，不涉及用户界面。

**已知的配置项**（非页面，属于配置管理）：
- `CHANNEL_GATEWAY_ENABLED_PLATFORMS`：配置 Go gateway 启用的平台列表
- `CHANNEL_GATEWAY_TELEGRAM_QUEUE`：配置 Telegram 渠道的 Go 队列名
- `MQ_QUEUE_NAME_TELEGRAM`：Python 链路使用的原队列名

**已知的操作**（非页面，属于运维操作）：
- 在第三方平台修改 webhook URL
- 修改服务配置并重启/重载
- 观察队列指标（ready / unacked）

原文未说明：
- 是否有灰度管理后台或控制面板
- 是否有迁移进度可视化界面
- 是否有异常告警和通知页面

## 9. 数据与系统交互

### 已知数据

**队列数据**：
- Python 队列：原队列名（如 cyber_telegram），消息结构为 Python gateway 写入格式
- Go 队列：原队列名 + `_go` 后缀（如 cyber_telegram_go），消息结构为 Go gateway 写入格式
- 两套队列的消息结构不一致，不能混用

**配置数据**：
- `CHANNEL_GATEWAY_ENABLED_PLATFORMS`：Go gateway 启用的平台列表
- `CHANNEL_GATEWAY_{PLATFORM}_QUEUE`：各平台 Go 队列名
- `MQ_QUEUE_NAME_{PLATFORM}`：Python 链路队列名

### 系统交互

```text
第三方平台 webhook
       |
       v
  [Python gateway] 或 [Go gateway]  (根据 webhook URL 配置)
       |                    |
       v                    v
  Python queue         Go queue
       |                    |
       v                    v
  Python worker         Go worker
```

**交互说明**：
1. 第三方平台 → gateway：通过 webhook URL 发送 HTTP 请求
2. gateway → queue：将处理后的消息写入 RabbitMQ 队列
3. worker → queue：从 RabbitMQ 队列消费消息

### 系统边界

| 系统/组件 | 职责 | 已知约束 |
|----------|------|---------|
| 第三方平台 | 发送 webhook 请求 | 根据平台能力，可配置到机器人级别或渠道级别 |
| Python gateway | 接收 webhook，写入 Python 队列 | 只写 Python 队列 |
| Go gateway | 接收 webhook，写入 Go 队列 | 只写 Go 队列 |
| Python queue | 存储 Python gateway 写入的消息 | 消息结构为 Python 格式 |
| Go queue | 存储 Go gateway 写入的消息 | 消息结构为 Go 格式，独立 retry queue 和 DLQ |
| Python worker | 消费 Python 队列消息 | 只消费 Python 队列 |
| Go worker | 消费 Go 队列消息 | 只消费 Go 队列 |

原文未说明：
- webhook 请求的格式和字段
- gateway 处理 webhook 的具体逻辑
- worker 处理消息的具体逻辑
- 消息丢失或重复的检测机制
- 监控和告警系统的对接方式
