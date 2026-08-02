## ADDED Requirements

### Requirement: Actual pytest parameter iteration discovery

系统 SHALL 以 pytest 实际收集到的测试项作为 UI 自动化参数实例事实源，并为无参数用例创建一个默认实例。

#### Scenario: Parameterized case is collected

- **WHEN** pytest 将目标自动化用例收集为多个带 `callspec.params` 的测试项
- **THEN** 系统 SHALL 为每个实际测试项创建一个参数实例
- **AND** SHALL 保存脱敏后的参数快照、收集顺序和运行内稳定实例 ID
- **AND** SHALL NOT 根据 YAML 在平台侧重新计算参数组合

#### Scenario: Case has no parameters

- **WHEN** pytest 只收集到一个不带 `callspec.params` 的目标测试项
- **THEN** 系统 SHALL 创建一个默认参数实例
- **AND** 运行详情 SHALL NOT 要求用户选择参数后才能查看步骤

#### Scenario: Multiple parameter markers form a product

- **WHEN** 现有 renderer 生成多个 `@pytest.mark.parametrize`
- **THEN** 系统 SHALL 展示 pytest 实际产生的笛卡尔积实例
- **AND** 本能力 SHALL NOT 改变当前参数组合语义

### Requirement: Explicit business-step execution identity

系统 SHALL 让新生成的每个自动化动作显式关联来源业务步骤，并在执行结果中区分业务步骤与技术动作。

#### Scenario: Multiple operations implement one business step

- **GIVEN** 一个业务步骤需要 fill、click 和 wait 等多个技术动作
- **WHEN** renderer 生成测试代码
- **THEN** 这些动作 SHALL 关联同一个 `business_step_id`
- **AND** 运行详情 SHALL 默认显示一个业务步骤结果
- **AND** 用户展开后 MAY 查看技术动作明细

#### Scenario: Assertion belongs to a checkpoint step

- **GIVEN** 自动化计划中的断言声明 `after_step_id`
- **WHEN** renderer 生成该业务步骤
- **THEN** 断言 SHALL 在对应业务步骤上下文中执行
- **AND** 断言失败 SHALL 将该业务步骤标记为失败

#### Scenario: Historical plan lacks business mapping

- **GIVEN** 历史 `AutomationPlan v1` 只包含 `source_step_id`
- **WHEN** 系统执行该资产
- **THEN** 资产 SHALL 保持可执行
- **AND** 系统 SHALL 将每个来源动作降级显示为独立步骤
- **AND** SHALL NOT 通过字符串前缀猜测业务步骤归属

### Requirement: Incremental step lifecycle collection

系统 SHALL 在 pytest 子进程中采集参数实例和业务步骤的开始、结束、失败、跳过与取消事件。

#### Scenario: Business step passes

- **WHEN** 业务步骤上下文中的所有动作和断言正常完成
- **THEN** 系统 SHALL 记录步骤开始时间、结束时间、耗时和 `passed` 状态

#### Scenario: Business step fails

- **WHEN** 业务步骤中的动作或断言抛出异常
- **THEN** 系统 SHALL 将该步骤记录为 `failed`
- **AND** SHALL 保存经过脱敏和截断的异常类型、消息及 traceback 摘要
- **AND** SHALL 尝试保存该步骤的失败截图
- **AND** SHALL 重新抛出异常以保持 pytest 原始失败语义

#### Scenario: Failure occurs before a business step starts

- **WHEN** fixture、浏览器启动或 setup 在进入任何业务步骤前失败
- **THEN** 系统 SHALL 将参数实例标记为 `infrastructure_error`
- **AND** SHALL NOT 伪造一个业务步骤失败结果

#### Scenario: Run is stopped

- **WHEN** 用户停止正在执行的 UI 自动化运行
- **THEN** 当前运行步骤和参数实例 SHALL 收敛为 `cancelled`
- **AND** 尚未开始的实例 SHALL NOT 被标记为业务失败

### Requirement: Durable run detail artifacts

系统 SHALL 在当前运行目录保存版本化增量事件和终态结构化详情，并保持现有 SQLite 运行记录为汇总边界。

#### Scenario: Events are emitted during execution

- **WHEN** 参数实例或步骤状态发生变化
- **THEN** pytest 子进程 SHALL 向 `events.jsonl` 追加一个完整、带递增 sequence 的版本化事件
- **AND** 每个事件 SHALL 受字段长度和单行大小限制

#### Scenario: Execution completes

- **WHEN** pytest 子进程退出
- **THEN** runner SHALL 使用确定性 reducer 生成 `result-detail.json`
- **AND** `result_json` SHALL 保存运行汇总和详情可用标记
- **AND** SHALL NOT 在 SQLite 中复制完整步骤数组

#### Scenario: Event stream ends with a partial line

- **WHEN** 进程被强制终止导致 JSONL 最后一行不完整
- **THEN** reducer SHALL 忽略该无效尾行
- **AND** SHALL 保留此前有效事件
- **AND** SHALL 将详情标记为不完整

#### Scenario: Run is deleted

- **WHEN** 用户删除一个已完成运行
- **THEN** 事件、终态详情、步骤证据和清单 SHALL 随现有运行目录一起删除

### Requirement: Deterministic execution status aggregation

系统 SHALL 使用统一规则从步骤和 pytest item 结果聚合参数实例与运行状态。

#### Scenario: All iterations pass

- **WHEN** 所有实际收集到的参数实例均完成且通过
- **THEN** 运行汇总 SHALL 标记全部实例通过
- **AND** 既有执行运行状态 SHALL 收敛为 `passed`

#### Scenario: A step fails in one iteration

- **WHEN** 一个参数实例的业务步骤失败
- **THEN** 该参数实例 SHALL 标记为 `failed`
- **AND** 后续未开始步骤 SHALL 标记为 `skipped`
- **AND** 其他参数实例的结果 SHALL 独立保存

#### Scenario: Current implementation has no retries

- **WHEN** 系统记录参数实例结果
- **THEN** `attempt` SHALL 固定为 1
- **AND** UI SHALL NOT 展示不存在的重试入口或重试后通过状态

### Requirement: Scoped result and event APIs

系统 SHALL 提供项目和运行范围内的结构化详情、增量事件和步骤证据只读接口。

#### Scenario: Client loads completed details

- **WHEN** 已授权用户请求已完成运行的详情
- **THEN** API SHALL 返回参数实例汇总、步骤结果、错误摘要和证据引用
- **AND** SHALL 从终态详情文件读取稳定结果

#### Scenario: Client polls a running execution

- **WHEN** 客户端携带最后消费的 cursor 请求运行事件
- **THEN** API SHALL 只返回 cursor 之后的有序事件
- **AND** SHALL 返回 `next_cursor` 和 `has_more`
- **AND** SHALL 对单次返回数量和总响应大小设限

#### Scenario: Client requests a step artifact

- **WHEN** 客户端使用服务端生成的 artifact ID 请求步骤截图
- **THEN** API SHALL 验证用户项目权限、运行归属、清单记录和运行目录包含关系
- **AND** SHALL NOT 接受客户端文件路径

#### Scenario: Historical run has no structured detail

- **WHEN** 历史运行不存在事件或终态详情文件
- **THEN** API SHALL 返回稳定的 `detail_available=false`
- **AND** 现有日志、全局截图和实时画面接口 SHALL 保持可用

### Requirement: Parameter-first run detail interface

系统 SHALL 在 UI 自动化运行详情中使用参数实例列表和单实例步骤详情展示结构化结果。

#### Scenario: Parameterized run is viewed

- **WHEN** 一个运行包含多个参数实例
- **THEN** 页面 SHALL 展示参数实例总数、通过、失败、运行中和取消汇总
- **AND** 左侧 SHALL 展示可筛选的参数实例列表
- **AND** 右侧 SHALL 展示当前选择实例的业务步骤状态、耗时和失败证据

#### Scenario: Non-parameterized run is viewed

- **WHEN** 一个运行只有默认参数实例
- **THEN** 页面 SHALL 隐藏参数实例选择栏
- **AND** SHALL 直接展示业务步骤详情

#### Scenario: A step fails

- **WHEN** 所选参数实例包含失败步骤
- **THEN** 页面 SHALL 默认展开第一个失败步骤
- **AND** SHALL 展示错误摘要、失败截图、断言和技术动作
- **AND** 原始 stdout/stderr SHALL 保留在次级日志区域

#### Scenario: User inspects another iteration during execution

- **GIVEN** 页面正在接收运行事件
- **WHEN** 用户手动选择一个非当前运行实例
- **THEN** 页面 SHALL 保持用户选择
- **AND** SHALL NOT 因新步骤事件强制切回当前实例

### Requirement: Sensitive execution data protection

系统 SHALL 在持久化和返回参数、异常及步骤证据引用前应用敏感信息保护。

#### Scenario: Parameter is sensitive

- **WHEN** 参数名或参数元数据表明其包含 password、secret、token、cookie 或 authorization 信息
- **THEN** 事件、详情、日志摘要和前端响应中的参数值 SHALL 显示为 `***`
- **AND** 运行目录和 artifact ID SHALL NOT 包含原始值

#### Scenario: Failure message contains credentials

- **WHEN** 异常消息或 traceback 包含现有脱敏规则识别的凭证
- **THEN** 持久化事件和 API 响应 SHALL 使用脱敏值
- **AND** SHALL NOT 因结构化步骤采集削弱现有 stdout/stderr 脱敏行为

#### Scenario: Successful step completes

- **WHEN** 一个业务步骤通过
- **THEN** 系统 SHALL 默认不生成步骤截图
- **AND** SHALL NOT 保存页面 DOM、Cookie、Storage State 或输入框完整内容
