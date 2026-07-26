# 设计方案

## 1. 方案总览

```text
Locust 运行数据、场景配置、性能目标、历史基线
                         ↓
              数据完整性和口径校验
                         ↓
        确定性分析器生成 MetricSnapshot v1
                         ↓
          AI 生成 Evidence-linked Diagnosis
                         ↓
             服务端 Schema 和引用校验
                         ↓
          ReportSnapshot v1（不可变事实版本）
                ↓                    ↓
        React 完整报告页         HTML/PDF 渲染器
                ↓
      证据化追问 / 现有修复复测 / 基线对比
```

设计原则：数值由代码计算，结论引用证据，展示由模板渲染，修改必须审批。

运行进入终态后先产生报告分析。报告完成不代表执行修复；只有诊断结果包含通过白名单校验的 `ProposedChange` 时，界面才展示“AI 修复并复测”。用户审批和预检成功后产生一个新的性能运行，新运行再次独立生成报告，不覆盖原报告。

## 2. 复用边界

### 2.1 现有能力

继续复用以下边界：

- `performance_runs`、运行统计、图表样本、失败、异常、事件和报告目录。
- `collect_performance_evidence` 的项目校验、证据收集、敏感信息脱敏和诊断约束。
- `performance_analysis_sessions` 的按运行版本、状态、模型和审计信息。
- `performance_report_analysis` 模型能力选择。
- `PerformanceDiagnosis` 的 observed、derived、inferred 证据分级。
- 现有 `apply-and-rerun` 的白名单变更、审批、单请求预检和复测链路。
- Locust 原始 HTML/CSV 报告列表和下载接口。

### 2.2 新增职责

- `metric_snapshot_service`：确定性指标、窗口、目标判定和基线差异。
- `report_service`：组合指标快照与已校验诊断、冻结报告快照并管理导出任务。
- `report_renderer`：从可信快照生成 HTML/PDF，不执行模型输出的标记。
- 完整报告页面：展示执行摘要、容量、诊断、场景明细、优化计划和附录。
- 报告问答：只读检索快照和证据，保存问题、回答和引用。

### 2.3 智能体和服务边界

第一阶段只保留一个负责压测结果归因的核心智能体：

```text
apps/backend/app/agents/performance_testing/
├── diagnosis/
│   ├── agent.py       # 受约束诊断智能体
│   ├── service.py     # 模型选择、调用和结构化输出
│   └── schemas.py     # finding、证据引用和建议契约，可按现有项目结构合并
└── script_generation/ # 现有 Locust 计划生成能力，保持不变
```

`diagnosis` 只读取脱敏证据和 `MetricSnapshot`，一次性输出 finding、根因候选、替代假设、置信度、优化建议及可修复候选。它不生成 HTML/PDF，不重新计算指标，不决定 verdict，也不执行修改。

报告组装和文件渲染是确定性应用服务，不属于智能体：

```text
apps/backend/app/services/performance_testing/
├── analysis_service.py         # 分析状态和任务编排
├── metric_snapshot_service.py  # 指标与 verdict 计算
├── report_service.py           # 组合并冻结 ReportSnapshot
├── report_renderer.py          # HTML/PDF 模板渲染
├── repair_service.py           # 现有审批后修复和复测
└── analysis_evidence.py        # 现有证据采集与脱敏
```

第一阶段 SHALL NOT 新增独立 `report_narration` 智能体。engineer、technical_manager 和 business_owner 三种视角由 `report_service` 使用同一份 `MetricSnapshot` 和结构化诊断进行模板编排。未来若叙事质量确实需要额外模型，可增加只读 narration 阶段，但其输出仍不得增加 finding、改变 verdict、修改数值或生成 HTML。

### 2.4 报告与修复关系

```text
运行终态
  → 确定性指标快照
  → diagnosis 智能体生成结构化诊断
  → 报告就绪
       ├─ 达标：查看或导出，结束
       ├─ 不达标且不可自动修复：展示人工建议，结束
       └─ 不达标且存在白名单修改：用户审批
                                      → 单请求预检
                                      → 应用修复
                                      → 新运行
                                      → 新报告
```

报告中的 `Recommendation` 是只读建议。只有通过现有目标类型、风险、当前版本和权限校验的候选，才能转换为 `ProposedChange`。转换结果继续使用现有 `apply-and-rerun`；报告服务不得直接调用配置仓库或启动运行。

## 3. 领域契约

### 3.1 分析创建请求

性能运行进入终态时，运行服务异步调用分析编排器创建默认报告分析。扩展现有接口并保持无请求体调用兼容，使其作为缺失报告补生成、失败重试或明确重新分析入口：

```http
POST /projects/{project_id}/performance-runs/{run_id}/ai-analysis
```

可选请求：

```json
{
  "audience": "engineer",
  "baseline_run_id": "perfrun-previous",
  "objectives": [
    {
      "metric": "p95_response_time_ms",
      "operator": "lte",
      "target": 500,
      "scope": "aggregate"
    },
    {
      "metric": "failure_rate",
      "operator": "lte",
      "target": 0.01,
      "scope": "aggregate"
    }
  ]
}
```

`audience` 允许 `engineer`、`technical_manager`、`business_owner`，默认 `engineer`。未提供 `objectives` 时优先读取性能测试已保存目标；没有目标时仍可分析，但总体结论不得是 `pass`。

`baseline_run_id` 必须属于同一项目和同一性能测试、已处于终态，并且能够按相同指标版本计算。当前前端无请求体的调用继续有效。

自动创建失败不得改变性能运行的终态结果。系统记录报告状态和错误，用户可以通过现有入口重试；同一运行同一来源指纹同时只允许一个活跃分析。

### 3.2 MetricSnapshot

所有数值和图表数据由确定性分析器生成：

```json
{
  "schema_version": 1,
  "calculator_version": "performance-metrics-v1",
  "run_id": "perfrun-current",
  "source_fingerprint": "sha256:...",
  "quality": {
    "status": "complete",
    "coverage": 0.98,
    "issues": [],
    "analyzable_windows": []
  },
  "phases": {
    "warmup": {},
    "steady": {},
    "rampdown": {}
  },
  "aggregate": {
    "request_count": 120000,
    "failure_rate": 0.004,
    "requests_per_second": 812.4,
    "p50_response_time_ms": 110,
    "p95_response_time_ms": 430,
    "p99_response_time_ms": 760
  },
  "capacity": {
    "stable_throughput": 812.4,
    "knee_point": null,
    "headroom_ratio": null
  },
  "objectives": [],
  "comparison": null,
  "series": [],
  "evidence_index": []
}
```

要求：

1. `source_fingerprint` 覆盖运行摘要、统计、图表样本、目标、阶段边界和基线 ID。
2. 分位数只能来自 Locust 已提供的可信统计或可证明正确的原始分布，不能从均值估算。
3. 稳态窗口必须由明确规则确定，并在快照中保存规则、起止时间和排除原因。
4. 只有负载变化和采样密度满足算法前提时才计算拐点；否则返回 `null` 和原因。
5. 基线比较只比较相同 `calculator_version`、指标定义、scope 和兼容负载阶段的数据。
6. 每个重要数值、目标判定和图表片段具有稳定 `evidence_id`。

### 3.3 数据质量

数据质量状态：

- `complete`：关键结果和阶段数据足以进行目标、容量和趋势分析。
- `partial`：可以生成部分结论，但缺失项必须影响对应章节和置信度。
- `invalid`：时间轴、统计或目标口径存在严重冲突，不能生成确定性总体结论。

质量问题至少覆盖：空运行、统计与汇总数量矛盾、时间戳异常、样本覆盖不足、缺失分位数、非终态输入、基线不兼容和阶段不可识别。

`invalid` 时分析会话可以生成“无法判断”报告，但不得调用 AI 编造替代结论，不得提供可应用修复。

### 3.4 报告快照

报告使用受约束结构，而不是模型生成的 Markdown 或 HTML：

```json
{
  "schema_version": 1,
  "verdict": "conditional_pass",
  "verdict_reasons": ["objective:p95:pass", "quality:partial"],
  "executive_summary": "...",
  "capacity_summary": "...",
  "findings": [
    {
      "id": "finding-1",
      "severity": "high",
      "title": "高负载阶段尾延迟明显上升",
      "statement": "...",
      "confidence": 0.86,
      "evidence_refs": ["metric:p99:steady", "series:latency:window-4"],
      "alternative_hypotheses": [],
      "missing_evidence": ["server_database_pool_metrics"]
    }
  ],
  "recommendations": [
    {
      "id": "recommendation-1",
      "priority": "P1",
      "action": "...",
      "expected_effect": "...",
      "cost": "medium",
      "verification": "...",
      "finding_refs": ["finding-1"]
    }
  ]
}
```

服务端必须验证：

- `evidence_refs` 全部存在于本次冻结的 `evidence_index`。
- observed 和 derived 文本中的关键数值能从引用证据解析或匹配。
- inferred 结论包含置信度，并且不得使用“已证明”“根因确定”等确定性措辞。
- `verdict` 由规则引擎根据目标和质量计算，模型无权返回或覆盖。
- `recommendations` 不直接成为可执行修改；可应用修改继续走现有 `ProposedChange` 和审批链路。
- 校验失败时拒绝本次模型输出，记录稳定错误并允许重新分析，不发布半可信报告。

### 3.5 总体结论规则

- `pass`：存在至少一个明确目标，所有阻断目标通过，数据质量为 `complete`。
- `conditional_pass`：所有阻断目标通过，但质量为 `partial`，或容量余量低于配置阈值。
- `fail`：任一阻断目标失败。
- `indeterminate`：没有性能目标、数据质量为 `invalid`，或关键目标无法计算。

报告必须同时展示结论、判定规则和未能判断的项目。不得将“没有观测到失败”等同于通过。

## 4. API 设计

### 4.1 获取分析

现有接口保持不变：

```http
GET /projects/{project_id}/performance-analysis/{analysis_id}
```

响应新增 `metric_snapshot`、`report_snapshot`、`audience`、`baseline_run_id`、`prompt_version`、`calculator_version` 和 `source_fingerprint`。为控制列表响应体积，运行分析列表只返回报告摘要；完整快照由单条详情接口返回。

### 4.2 切换角色视角

```http
GET /projects/{project_id}/performance-analysis/{analysis_id}/report?audience=technical_manager
```

角色视角只改变章节排序、摘要表达和信息密度，不重新计算指标，不改变 verdict、finding、evidence 或 recommendation 的事实字段。系统可以缓存角色化叙事，缓存键必须包含分析 ID、报告 Schema 版本、受众和提示版本。

### 4.3 报告导出

```http
POST /projects/{project_id}/performance-analysis/{analysis_id}/exports
```

```json
{
  "format": "pdf",
  "audience": "technical_manager"
}
```

返回 `202` 和导出任务。支持 `html`、`pdf`；导出完成后通过项目鉴权接口下载。文件名使用服务端生成的安全名称，禁止使用用户输入构造任意路径。导出文件记录分析版本、生成时间、指标版本和来源指纹。分析快照未完成、已失效或导出格式不支持时返回稳定错误。

### 4.4 报告追问

```http
POST /projects/{project_id}/performance-analysis/{analysis_id}/questions
```

```json
{
  "question": "为什么 850 TPS 后 P99 上升？",
  "audience": "engineer"
}
```

回答结构包含 `answer`、`evidence_refs`、`confidence`、`missing_evidence`。问答只能读取冻结快照和其证据；问题文本视为不可信数据，不得触发工具执行、配置修改、网络访问或报告事实变更。无足够证据时明确返回证据不足。

## 5. 分析状态和幂等性

将报告完成状态和修复审批状态解耦。分析主状态建议扩展为：

```text
collecting → analyzing → completed
                       ↘ failed
```

修复状态单独使用：

```text
not_applicable | available | waiting_approval | rejected
| preflighting | preflight_failed | rerunning | completed | apply_failed | superseded
```

迁移期间服务端可以兼容读取历史 `waiting_approval`，但新报告不得因为没有修复项而进入等待审批。详情同时暴露分析阶段：

```text
evidence_collection → metric_calculation → ai_diagnosis
→ report_validation → report_ready
```

- 同一运行可以创建多个 `analysis_version`，历史版本不可覆盖。
- 相同 `source_fingerprint`、目标、基线和提示版本允许复用已完成快照，但必须创建可审计的访问记录。
- 运行中的分析仍使用现有互斥限制。
- 报告已就绪但没有可应用修复时，`analysis_status=completed` 且 `repair_status=not_applicable`。
- 报告已就绪且存在白名单可修复项时，`analysis_status=completed` 且 `repair_status=available`；只有用户发起修复后才进入审批相关状态。
- 原始运行文件变化导致指纹变化时，旧报告显示“来源已变化”，但历史快照仍可只读访问。

## 6. 前端体验

### 6.1 入口

在现有 `locust-console.tsx` 中保留“AI 分析”按钮。分析完成后：

- 抽屉继续展示诊断摘要、证据、可应用修改和复测动作。
- 增加“查看完整报告”命令，进入运行下的报告页面。
- 原始报告区域继续提供 Locust HTML/CSV 下载，并与智能报告明确区分。

### 6.2 完整报告页

建议路由：

```text
/projects/{projectId}/performance-tests/{testId}/runs/{runId}/analysis/{analysisId}
```

页面按以下顺序组织：

1. 执行摘要：verdict、目标达成、最大稳定吞吐、首要风险和数据质量。
2. 容量结论：负载、TPS、P95/P99、错误率的同时间轴趋势和拐点。
3. 异常诊断：finding、置信度、证据引用、反向假设和缺失证据。
4. 场景明细：请求统计、失败分布、异常和阶段表现。
5. 优化计划：优先级、预期收益、成本、验证方法和现有审批动作。
6. 附录：环境、运行参数、指标口径、快照版本、原始证据和限制。

页面使用现有设计系统、Recharts 和 Lucide。图表由 `metric_snapshot.series` 渲染，AI 文本不能直接控制图表配置。桌面端支持报告目录定位，窄屏改为单列且图表、长路径和表格不得遮挡正文。

### 6.3 角色视角

- `engineer`：默认展示完整指标、证据、接口明细和验证步骤。
- `technical_manager`：优先展示发布结论、容量余量、风险等级、投入和收益。
- `business_owner`：优先展示业务目标、可承载量、体验影响和决策建议，隐藏非必要实现细节。

切换角色不得触发重新分析或改变结论；界面明确显示当前报告视角。

## 7. 存储和迁移

在 `performance_analysis_sessions` 增量增加或通过关联表保存：

- 分析创建参数和 `audience`。
- `baseline_run_id`。
- `metric_snapshot_json` 和 `metric_schema_version`。
- `report_snapshot_json` 和 `report_schema_version`。
- `calculator_version`、`prompt_version` 和 `source_fingerprint`。
- `analysis_stage` 和数据质量摘要。

大体积时间序列可保存为分析目录中的版本化 JSON 文件，数据库只保存摘要、路径、大小和 SHA-256。文件解析必须限制目录、大小、记录数和内容类型，禁止路径穿越。删除性能运行时继续沿用现有级联清理语义，并清理其智能报告、导出和问答记录。

导出任务和报告问答使用独立关联表，保存项目、分析、创建人、状态、错误、版本和时间戳。问答不写回报告快照。

## 8. 安全和可信性

- 创建、查看、导出、下载和追问都执行现有项目可见性检查。
- 基线运行必须校验同项目、同测试和终态，不接受任意运行 ID。
- 继续使用现有脱敏规则；导出和问答不得恢复脱敏前值。
- 模型输入中的运行数据、错误响应和用户问题都视为不可信内容，不能作为系统指令。
- 所有模型输出通过严格 Pydantic Schema、引用完整性和数值一致性校验。
- HTML 使用受控组件和文本转义渲染；PDF 从可信 HTML 模板生成，不执行模型内容。
- 报告显示模型、提示版本、计算器版本、分析时间、数据质量和限制。
- 记录分析、角色视图、导出、下载、追问、修复应用和复测的审计事件。

## 9. 失败和降级

- 无可分析数据：沿用 `PERFORMANCE_ANALYSIS_NO_EVIDENCE`，不创建空白报告。
- 数据部分缺失：生成 `partial` 报告，隐藏无法支持的图表并列出缺失证据。
- 数据无效：生成 `indeterminate` 的质量报告，不进行推测性归因。
- 模型不可用：保留确定性指标快照，完整报告页展示事实分析和“AI 诊断暂不可用”，允许重试 AI 阶段。
- 模型输出非法：拒绝输出并记录校验错误，不污染最近可信报告。
- 基线不兼容：当前运行仍可分析，但对比章节明确不可用。
- PDF 渲染失败：HTML 报告仍可查看和导出，PDF 任务返回可诊断错误。
- 来源文件变化：旧报告保留并显示失效提示，新分析使用新指纹创建版本。

## 10. 可观测性

记录以下指标：

- 各分析阶段耗时和失败率。
- 证据包、指标快照、模型输入和导出文件大小。
- 数据质量状态分布、基线兼容率和报告 verdict 分布。
- 模型 Schema 失败、证据引用失败和数值一致性失败次数。
- 报告打开、角色切换、HTML/PDF 导出和追问次数。

日志携带 `project_id`、`run_id`、`analysis_id`、`analysis_version`、`trace_id` 和版本字段，但不得记录密钥、Cookie、完整响应正文或用户敏感数据。

## 11. 验证策略

- 指标单元测试：稳态窗口、目标判定、百分位来源、错误率、拐点前提和空数据。
- 属性测试：相同输入产生相同快照；请求数、失败数和比例满足不变量。
- 合约测试：AI Schema、证据引用、数值一致性、verdict 不可覆盖和提示注入隔离。
- API 测试：权限、基线归属、兼容无请求体、分析互斥、导出和下载。
- 前端测试：摘要、完整报告、角色切换、缺失章节、失败降级和修复复测入口。
- 视觉测试：桌面和移动端的图表、表格、长文本、打印分页和 PDF 页面。
- 回归测试：现有 Locust 控制台、原始报告下载、AI 分析抽屉和 apply-and-rerun 行为保持兼容。
