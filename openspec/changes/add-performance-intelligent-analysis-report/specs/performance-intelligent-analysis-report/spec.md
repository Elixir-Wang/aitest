# Performance Intelligent Analysis Report Specification

## ADDED Requirements

### Requirement: Terminal run analysis

系统 SHALL 在当前项目的性能运行进入终态后异步创建智能报告分析，同时保持现有无请求体 AI 分析调用作为补生成和重试入口。

#### Scenario: Run enters a terminal status

- **GIVEN** 性能运行包含可分析证据
- **WHEN** 运行进入 completed、stopped、failed 或 cancelled 终态
- **THEN** 系统 SHALL 异步创建默认报告分析
- **AND** 报告失败 SHALL NOT 改变性能运行的终态结果
- **AND** 同一来源指纹 SHALL NOT 同时创建多个活跃分析

#### Scenario: Completed run has analyzable evidence

- **GIVEN** 性能运行属于当前项目并已结束
- **AND** 运行包含请求统计、失败、异常、事件或可解析报告证据
- **WHEN** 用户启动智能分析
- **THEN** 系统 SHALL 创建新的分析版本
- **AND** SHALL 异步生成确定性指标快照和智能报告

#### Scenario: Existing client sends no request body

- **GIVEN** 现有客户端按原协议调用 AI 分析接口
- **WHEN** 请求未包含 audience、baseline 或 objectives
- **THEN** 系统 SHALL 使用默认工程师视角和性能测试已有目标
- **AND** SHALL NOT 因新增参数破坏现有调用

#### Scenario: Automatic report creation previously failed

- **GIVEN** 运行终态后的自动报告创建或分析失败
- **WHEN** 用户通过现有 AI 分析入口重试
- **THEN** 系统 SHALL 创建或恢复一个可审计的分析版本
- **AND** SHALL NOT 直接进入修复执行

#### Scenario: Run is still active

- **WHEN** 用户对非终态运行启动智能分析
- **THEN** 系统 SHALL 返回稳定的冲突错误
- **AND** SHALL NOT 创建分析会话

### Requirement: Deterministic metric snapshot

系统 SHALL 使用版本化确定性代码计算报告中的指标、目标判定和图表序列，并 SHALL NOT 使用模型计算或改写数值。

#### Scenario: Same source is analyzed repeatedly

- **GIVEN** 来源运行、性能目标、基线和计算器版本均未变化
- **WHEN** 系统重复生成指标快照
- **THEN** 两次快照中的事实指标和目标判定 SHALL 一致
- **AND** 快照 SHALL 包含相同来源指纹

#### Scenario: Percentile distribution is unavailable

- **GIVEN** 输入只有平均响应时间而没有可信分位数或原始分布
- **WHEN** 系统计算延迟指标
- **THEN** 系统 SHALL 将对应分位数标记为不可用
- **AND** SHALL NOT 根据平均值估算 P95 或 P99

#### Scenario: AI output conflicts with calculated metric

- **GIVEN** 模型输出的数值与指标快照不一致
- **WHEN** 服务端校验模型输出
- **THEN** 系统 SHALL 拒绝该模型输出
- **AND** SHALL 保留确定性指标快照和可诊断错误

### Requirement: Data quality assessment

系统 SHALL 在智能诊断前评估数据完整性、时间轴、采样覆盖、指标一致性和分析窗口，并将质量状态及问题展示在报告中。

#### Scenario: Evidence is partially missing

- **GIVEN** 核心运行结果可分析但部分分位数或阶段样本缺失
- **WHEN** 系统生成报告
- **THEN** 数据质量 SHALL 为 partial
- **AND** 报告 SHALL 隐藏或标记不受支持的结论
- **AND** SHALL 列出具体缺失证据

#### Scenario: Evidence is invalid

- **GIVEN** 运行汇总和统计严重矛盾或时间轴无效
- **WHEN** 系统生成分析结果
- **THEN** 总体结论 SHALL 为 indeterminate
- **AND** 系统 SHALL NOT 执行推测性根因归因
- **AND** SHALL NOT 提供可应用修改

### Requirement: Performance objective verdict

系统 SHALL 根据明确目标、确定性指标和数据质量计算总体结论，而不是让模型决定通过状态。

#### Scenario: All blocking objectives pass with complete data

- **GIVEN** 至少存在一个阻断性能目标
- **AND** 所有阻断目标均通过
- **AND** 数据质量为 complete
- **WHEN** 系统生成总体结论
- **THEN** 结论 SHALL 为 pass，除非容量余量规则要求 conditional_pass

#### Scenario: A blocking objective fails

- **GIVEN** 任一阻断性能目标未达标
- **WHEN** 系统生成总体结论
- **THEN** 结论 SHALL 为 fail
- **AND** 报告 SHALL 引用失败目标及对应指标证据

#### Scenario: No objective is configured

- **GIVEN** 性能测试和分析请求都没有性能目标
- **WHEN** 系统生成报告
- **THEN** 结论 SHALL 为 indeterminate
- **AND** SHALL NOT 将没有观测到错误表述为通过

### Requirement: Capacity and phase analysis

系统 SHALL 按明确规则识别压测阶段，并且仅在数据满足算法前提时计算稳态容量、容量余量和性能拐点。

#### Scenario: Stable phase is identifiable

- **GIVEN** 运行包含足够的负载和结果时间序列
- **WHEN** 系统识别 warmup、steady 和 rampdown
- **THEN** 快照 SHALL 保存各阶段起止时间、识别规则和排除区间
- **AND** 容量指标 SHALL 说明其使用的阶段窗口

#### Scenario: Knee point prerequisites are not met

- **GIVEN** 运行负载固定或采样密度不足以识别拐点
- **WHEN** 系统执行容量分析
- **THEN** knee point SHALL 为空
- **AND** 报告 SHALL 展示不可计算原因
- **AND** SHALL NOT 猜测容量拐点

### Requirement: Compatible historical baseline

系统 SHALL 只允许使用同项目、同一性能测试、已进入终态且指标口径兼容的运行作为比较基线。

#### Scenario: Compatible baseline is selected

- **GIVEN** 基线和当前运行属于同一项目及同一性能测试
- **AND** 两者的计算器版本和指标 scope 兼容
- **WHEN** 用户生成带基线的报告
- **THEN** 系统 SHALL 展示绝对差异和相对差异
- **AND** SHALL 标明基线运行及比较口径

#### Scenario: Baseline belongs to another project

- **WHEN** 用户提交其他项目的运行作为基线
- **THEN** 系统 SHALL 拒绝该基线
- **AND** SHALL NOT 泄露基线是否存在或其任何数据

#### Scenario: Baseline is incompatible

- **GIVEN** 基线属于同一测试但指标口径不兼容
- **WHEN** 系统生成当前报告
- **THEN** 当前运行分析 SHALL 继续
- **AND** 对比章节 SHALL 明确标记不可比较及原因

### Requirement: Evidence-linked AI diagnosis

系统 SHALL 要求每个 AI finding 引用当前冻结快照中的有效证据，并区分观察、推导和推测。

#### Scenario: Finding references valid evidence

- **GIVEN** AI finding 引用了当前报告 evidence index 中存在的证据
- **WHEN** 服务端验证结构化诊断
- **THEN** 系统 SHALL 保留该引用
- **AND** 用户 SHALL 能从 finding 定位到对应指标或时间窗口

#### Scenario: Finding references unknown evidence

- **WHEN** AI finding 引用未知、其他运行或已失效的 evidence ID
- **THEN** 系统 SHALL 拒绝该模型输出
- **AND** SHALL NOT 发布包含悬空引用的报告

#### Scenario: Inferred diagnosis is presented

- **GIVEN** 某诊断仅由相关性支持
- **WHEN** 报告展示该诊断
- **THEN** 系统 SHALL 将其标记为 inferred 并展示置信度
- **AND** SHALL 展示验证方法或缺失证据
- **AND** SHALL NOT 将相关性表述为已证实因果关系

### Requirement: Single diagnosis agent boundary

系统 SHALL 复用现有 performance testing diagnosis 智能体生成结构化诊断，并 SHALL 使用确定性服务完成报告组合、角色编排和 HTML/PDF 渲染。

#### Scenario: Diagnosis is used by report and repair

- **GIVEN** diagnosis 智能体已经生成通过校验的 finding、证据引用和建议
- **WHEN** 系统构建报告并判断修复候选
- **THEN** 报告和修复候选 SHALL 复用同一份结构化诊断
- **AND** 系统 SHALL NOT 为报告重复调用另一个原始数据诊断智能体

#### Scenario: Report file is rendered

- **WHEN** 系统生成 HTML 或 PDF 报告
- **THEN** 普通 report service 和受控 renderer SHALL 从冻结快照渲染文件
- **AND** diagnosis 智能体 SHALL NOT 生成 HTML、JavaScript、图表配置或 PDF 内容

#### Scenario: Audience view is changed in the first release

- **WHEN** 用户切换报告角色视角
- **THEN** report service SHALL 通过模板重新编排同一份结构化诊断
- **AND** 系统 SHALL NOT 调用独立 report narration 智能体

### Requirement: Role-based report views

系统 SHALL 基于同一冻结事实快照提供 engineer、technical_manager 和 business_owner 三种报告视角，角色切换只能改变表达和章节优先级。

#### Scenario: User switches audience

- **GIVEN** 智能报告已经完成
- **WHEN** 用户从工程师视角切换到业务负责人视角
- **THEN** 页面 SHALL 调整摘要、章节顺序和信息密度
- **AND** verdict、指标值、finding、证据和建议事实 SHALL 保持不变
- **AND** 系统 SHALL NOT 重新运行指标计算

#### Scenario: Unknown audience is requested

- **WHEN** 请求包含未支持的 audience
- **THEN** 系统 SHALL 返回稳定的参数错误
- **AND** SHALL NOT 静默映射到其他角色

### Requirement: Complete report experience

系统 SHALL 提供完整报告页面，包含执行摘要、容量结论、异常诊断、场景明细、优化计划和附录，并保留现有快速诊断抽屉。

#### Scenario: Report is ready

- **GIVEN** 报告快照校验完成
- **WHEN** 用户从 Locust 控制台或 AI 分析抽屉打开完整报告
- **THEN** 系统 SHALL 展示总体结论、目标、质量、图表、finding、建议和版本信息
- **AND** 图表 SHALL 只由确定性 series 数据渲染

#### Scenario: AI diagnosis fails after metrics complete

- **GIVEN** 确定性指标快照已生成
- **AND** 模型调用失败或模型输出未通过校验
- **WHEN** 用户查看完整报告
- **THEN** 系统 SHALL 展示事实指标和数据质量
- **AND** SHALL 明确标记 AI 诊断暂不可用
- **AND** SHALL 提供只重试 AI 阶段的能力

#### Scenario: Narrow viewport

- **WHEN** 用户在窄屏查看报告
- **THEN** 章节、图表、长路径和表格 SHALL 重排或受控滚动
- **AND** SHALL NOT 相互遮挡或超出主要操作区域

### Requirement: Report center archive

系统 SHALL 将性能智能分析报告统一归档到报告中心，并基于冻结分析快照提供只读索引，不得复制或重新生成报告正文。

#### Scenario: User opens the performance report center

- **GIVEN** 当前用户可见项目中存在性能分析记录
- **WHEN** 用户打开报告中心的性能页签
- **THEN** 系统 SHALL 展示项目、报告名称、分析版本、总体结论、数据质量、生成状态和更新时间
- **AND** 用户 SHALL 能进入对应冻结分析报告详情

#### Scenario: Report belongs to an invisible project

- **GIVEN** 某性能报告所属项目不在当前用户项目范围内
- **WHEN** 用户查询全部项目报告或指定该项目
- **THEN** 系统 SHALL NOT 在列表中返回该报告
- **AND** 指定不可见项目 SHALL 返回与项目不可见一致的错误

#### Scenario: Analysis is still running or failed

- **WHEN** 性能分析处于 collecting、analyzing 或 failed 状态
- **THEN** 报告中心 SHALL 展示对应生成状态
- **AND** SHALL NOT 将其误标记为已生成报告

### Requirement: Safe report export

系统 SHALL 使用受控模板从冻结快照生成 HTML 和 PDF，不得执行模型生成的标记、脚本或图表配置。

#### Scenario: PDF export succeeds

- **GIVEN** 用户有权查看当前分析
- **WHEN** 用户请求 PDF 导出
- **THEN** 系统 SHALL 创建异步导出任务
- **AND** PDF SHALL 标明分析版本、指标版本、来源指纹和生成时间
- **AND** 下载接口 SHALL 再次执行项目权限校验

#### Scenario: Model text contains markup

- **GIVEN** finding 或回答文本包含 HTML 或脚本样式内容
- **WHEN** 系统渲染 HTML 或 PDF
- **THEN** 内容 SHALL 作为不可信文本转义或清洗
- **AND** SHALL NOT 执行其中的脚本、事件处理器或外部资源加载

#### Scenario: PDF renderer fails

- **WHEN** PDF 渲染任务失败
- **THEN** 系统 SHALL 记录稳定、可诊断的任务错误
- **AND** 已完成的 HTML 报告和分析快照 SHALL 保持可用

### Requirement: Evidence-grounded report questions

系统 SHALL 支持用户围绕报告追问，并将回答限制在当前冻结快照和证据范围内。

#### Scenario: Question is supported by evidence

- **WHEN** 用户询问某项延迟变化的原因
- **AND** 当前报告存在相关证据
- **THEN** 回答 SHALL 包含有效 evidence refs 和置信度
- **AND** 用户 SHALL 能定位引用证据

#### Scenario: Question cannot be answered

- **WHEN** 当前快照没有回答问题所需的服务端日志或资源指标
- **THEN** 系统 SHALL 明确说明证据不足
- **AND** SHALL 列出需要补充的证据
- **AND** SHALL NOT 编造外部系统行为

#### Scenario: Question contains instructions

- **GIVEN** 用户问题或运行证据包含要求执行命令、访问网络或忽略系统规则的文本
- **WHEN** 问答智能体处理该内容
- **THEN** 系统 SHALL 将其视为不可信数据
- **AND** SHALL NOT 执行工具、修改配置或改变报告事实

### Requirement: Repair and rerun compatibility

系统 SHALL 在报告完成后，仅对通过白名单校验的可修复项提供 AI 修复，并继续使用现有人工审批、单请求预检和自动复测链路。

#### Scenario: Report has no applicable repair

- **GIVEN** 报告已经完成
- **AND** 没有通过白名单校验的 ProposedChange
- **WHEN** 用户查看报告或诊断抽屉
- **THEN** 分析状态 SHALL 为 completed
- **AND** 修复状态 SHALL 为 not_applicable
- **AND** 系统 SHALL NOT 展示 AI 修复执行动作

#### Scenario: Report includes an applicable configuration change

- **GIVEN** 诊断类别允许现有 apply-and-rerun
- **WHEN** 用户从报告发起修复
- **THEN** 系统 SHALL 跳转或调用现有审批流程
- **AND** SHALL 要求用户选择变更并明确确认
- **AND** SHALL NOT 从 recommendation 文本直接执行修改

#### Scenario: User approves an applicable repair

- **GIVEN** 报告包含通过白名单校验的 ProposedChange
- **WHEN** 用户选择变更并明确批准修复
- **THEN** 系统 SHALL 先执行现有单请求预检
- **AND** 预检通过后 SHALL 创建修复后的新性能运行
- **AND** 新运行进入终态后 SHALL 生成独立的新报告
- **AND** 原报告 SHALL 保持不可变

#### Scenario: Diagnosis concerns external service or insufficient evidence

- **WHEN** finding 属于 external_service 或 insufficient_evidence
- **THEN** 系统 SHALL NOT 展示自动应用动作
- **AND** SHALL 提供验证建议或缺失证据说明

### Requirement: Report auditability and retention

系统 SHALL 保存分析版本、来源指纹、计算器版本、提示版本、创建人、角色视图、导出和追问审计信息，并保持历史报告不可变。

#### Scenario: Source files change after report generation

- **GIVEN** 报告生成后原始运行文件发生变化
- **WHEN** 用户查看历史报告
- **THEN** 系统 SHALL 保留原冻结快照
- **AND** SHALL 标记当前来源与报告指纹不一致
- **AND** 新分析 SHALL 创建新的分析版本而不是覆盖旧报告

#### Scenario: Performance run is deleted

- **WHEN** 用户按现有流程删除性能运行
- **THEN** 系统 SHALL 清理关联智能报告、导出和问答记录
- **AND** SHALL NOT 影响其他运行的分析和报告
