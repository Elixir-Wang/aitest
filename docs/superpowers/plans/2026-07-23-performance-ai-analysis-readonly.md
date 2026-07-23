# 性能压测 AI 只读诊断闭环实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Locust 控制台中增加手动触发的 AI 分析抽屉，异步收集压测证据并生成可审阅的结构化根因诊断，但本期不修改任何性能配置、Locust 脚本或平台源码。

**Architecture:** 新增独立的性能分析服务、仓储和结构化诊断 Agent。分析任务在后台执行，结果持久化到 SQLite；前端通过现有 API 客户端创建并轮询分析会话，在右侧 Drawer 中展示进度、事实证据、推断、缺失信息和只读建议。配置应用、预检重跑和源码补丁留给后续独立计划。

**Tech Stack:** FastAPI、Pydantic、SQLite、现有数据库连接/迁移机制、现有 Agent 模型选择器、React、TypeScript、现有 Drawer/Button/Badge 组件、pytest、现有前端 contract tests。

## Global Constraints

- 本期只读：AI 不得修改性能测试、Locust 脚本、平台源码或数据库业务数据。
- 分析必须由用户手动触发，运行中的 Locust 任务不能启动分析。
- 所有认证信息、Token、Password、Secret 和敏感 Header 值必须脱敏后才进入 Agent 输入、日志和前端响应。
- Agent 输出必须通过 Pydantic 结构化校验；输出无法校验时分析失败，不能猜测或降级为自动修改。
- 前端按钮权限和状态由后端 `available_actions` 决定，前端不得自行推断可执行操作。
- 本期不提供“应用修改”“重新压测”或源码修复按钮，只提供诊断结果和“重新分析”。
- 保留当前工作区已有改动，不回滚或覆盖无关文件。

---

## 文件与边界地图

### 新增后端文件

- `apps/backend/app/schemas/performance_analysis.py`：分析会话、证据、诊断和 Agent 输出模型。
- `apps/backend/app/repositories/performance_analysis_repo.py`：分析会话的 SQLite 读写和序列化。
- `apps/backend/app/services/performance_testing/analysis_evidence.py`：运行、配置、OpenAPI 和历史运行证据收集与脱敏。
- `apps/backend/app/services/performance_testing/analysis_service.py`：创建、查询、后台执行和状态转换。
- `apps/backend/app/agents/performance_testing/diagnosis/__init__.py`：诊断 Agent 导出接口。
- `apps/backend/app/agents/performance_testing/diagnosis/schemas.py`：诊断 Agent 领域模型和枚举。
- `apps/backend/app/agents/performance_testing/diagnosis/agent.py`：只读结构化 Agent 构造。
- `apps/backend/app/agents/performance_testing/diagnosis/service.py`：模型调用、输出校验和失败处理。
- `apps/frontend/src/components/ai-testing/performance-testing/performance-ai-analysis-drawer.tsx`：抽屉容器与轮询协调。
- `apps/frontend/src/components/ai-testing/performance-testing/performance-ai-analysis-progress.tsx`：阶段进度。
- `apps/frontend/src/components/ai-testing/performance-testing/performance-ai-evidence-list.tsx`：证据展示。
- `apps/frontend/src/components/ai-testing/performance-testing/performance-ai-config-diff.tsx`：只读配置建议 Diff。

### 修改后端文件

- `apps/backend/app/api/v1/performance_runs.py`：增加创建、查询和重新分析路由。
- `apps/backend/app/api/v1/__init__.py` 或实际路由注册文件：挂载性能分析路由（以仓库实际注册位置为准）。
- `apps/backend/app/seed/seeds.py` 或实际 SQLite 初始化入口：增加分析表和索引的幂等建表迁移。
- `apps/backend/app/services/performance_testing/__init__.py`：导出分析服务（若现有模块需要）。
- `apps/backend/tests/test_performance_run_api.py`：API 权限、状态和错误码测试。
- `apps/backend/tests/test_performance_analysis.py`：证据收集、脱敏、状态机和 Agent 输出测试。
- `apps/backend/tests/test_performance_analysis_repo.py`：仓储序列化和并发约束测试。

### 修改前端文件

- `apps/frontend/src/components/ai-testing/performance-testing/locust-console.tsx`：增加 AI 分析按钮和抽屉挂载。
- `apps/frontend/src/lib/api-client.ts` 或现有性能 API 文件：增加分析 API 类型和请求函数（以实际调用组织为准）。
- `apps/frontend/tests/performance-run-detail-contract.test.mjs`：增加入口、抽屉和状态文案 contract 断言。
- `apps/frontend/tests/performance-testing-contract.test.mjs`：增加 API 分析动作和只读边界断言。

### 后续计划明确不在本期修改

- 配置白名单应用器和 `apply-and-rerun` API；
- 单请求预检；
- 失败响应体增强；
- 隔离源码修复 Agent、Diff 应用和二次审批。

---

## Task 1: 建立分析领域模型和数据库表

**Files:**
- Create: `apps/backend/app/schemas/performance_analysis.py`
- Create: `apps/backend/app/repositories/performance_analysis_repo.py`
- Modify: `apps/backend/app/seed/seeds.py` 或实际数据库初始化文件
- Test: `apps/backend/tests/test_performance_analysis_repo.py`

**Interfaces:**
- Produces `PerformanceAnalysisStatus`、`PerformanceAnalysisCategory`、`EvidenceLevel`。
- Produces `create_analysis_session(...)`、`find_analysis_session(...)`、`update_analysis_session(...)`、`list_analysis_sessions(...)`。
- Produces JSON-serializable `PerformanceAnalysisOut`，供 API 和前端共用。

- [ ] **Step 1: 写仓储失败测试**

覆盖：创建和读取会话、JSON 字段序列化、分析版本递增、活动状态查询、同一运行活动任务唯一约束。

运行：

```powershell
rtk pytest apps/backend/tests/test_performance_analysis_repo.py -q
```

预期：FAIL，因为表和仓储函数尚未存在。

- [ ] **Step 2: 实现 Pydantic 领域模型**

定义：

- `DiagnosisEvidence`：来源、事实级别、标题、详情、引用；
- `ProposedChange`：本期只允许展示，不提供应用接口；
- `PerformanceDiagnosis`：分类、置信度、直接原因、根因、证据、缺失证据和操作能力；
- `PerformanceAnalysisSessionOut`：会话状态、阶段、诊断和 `available_actions`。

所有字符串和列表字段提供安全默认值；`confidence` 限制在 `0..1`。

- [ ] **Step 3: 增加幂等建表迁移**

创建 `performance_analysis_sessions`，增加：

- `(run_id, status)` 活动任务查询索引；
- `(project_id, created_at)` 历史查询索引；
- JSON 字段使用现有仓库的序列化约定。

迁移必须重复执行安全，不修改既有性能表。

- [ ] **Step 4: 实现仓储并通过测试**

实现事务边界和活动任务竞争检查。不要把 Agent 调用放入仓储层。

运行：

```powershell
rtk pytest apps/backend/tests/test_performance_analysis_repo.py -q
```

预期：PASS。

---

## Task 2: 实现证据收集和脱敏

**Files:**
- Create: `apps/backend/app/services/performance_testing/analysis_evidence.py`
- Test: `apps/backend/tests/test_performance_analysis.py`

**Interfaces:**
- Consumes `project_id`、`run_id` 和当前用户权限上下文。
- Produces `PerformanceEvidenceBundle`，包含运行、配置、接口定义、历史运行和来源引用。
- Produces `redact_sensitive_value(...)` 和递归 Header/JSON 脱敏函数。

- [ ] **Step 1: 写脱敏失败测试**

覆盖：

- `Authorization`、`cybertron-robot-key`、`cybertron-robot-token`；
- `password`、`secret`、`token`、`api_key` 等递归字段；
- Header 名保留、Header 值隐藏；
- 长请求体和响应体截断；
- 二进制响应只保留类型和长度。

运行：

```powershell
rtk pytest apps/backend/tests/test_performance_analysis.py -q -k redact
```

预期：FAIL。

- [ ] **Step 2: 实现脱敏和长度限制**

集中实现，不在各个采集器里复制规则。默认宁可隐藏也不能泄露。

- [ ] **Step 3: 写运行证据采集测试**

使用临时数据库和临时运行目录，验证能收集：

- 最新统计；
- 失败 CSV；
- 异常 CSV；
- `locust-events.jsonl`；
- 生成 Locust 脚本；
- runtime 配置脱敏结果；
- 运行开始/结束时间和摘要。

- [ ] **Step 4: 实现跨层证据收集**

复用现有性能运行仓储、脚本仓储、OpenAPI endpoint 查询和运行目录解析，不创造第二套运行数据格式。

每条证据标记：

```text
source: locust_events | performance_config | openapi | historical_run | git
level: observed | derived | inferred
reference: 文件路径、数据库对象或字段路径
```

- [ ] **Step 5: 处理缺失证据并通过测试**

单个日志文件缺失不能让整个收集失败；应记录 `missing_evidence` 并继续收集其他证据。运行：

```powershell
rtk pytest apps/backend/tests/test_performance_analysis.py -q
```

预期：PASS。

---

## Task 3: 增加只读诊断 Agent

**Files:**
- Create: `apps/backend/app/agents/performance_testing/diagnosis/__init__.py`
- Create: `apps/backend/app/agents/performance_testing/diagnosis/schemas.py`
- Create: `apps/backend/app/agents/performance_testing/diagnosis/agent.py`
- Create: `apps/backend/app/agents/performance_testing/diagnosis/service.py`
- Test: `apps/backend/tests/test_performance_analysis.py`

**Interfaces:**
- Consumes `PerformanceEvidenceBundle`。
- Produces validated `PerformanceDiagnosis`。
- Never receives writable filesystem access or raw database handles。
- Never returns arbitrary JSON Patch。

- [ ] **Step 1: 写 Agent 输出校验测试**

覆盖：

- 合法 `performance_config` 诊断；
- `external_service` 不产生自动操作；
- `insufficient_evidence` 必须包含缺失证据；
- 置信度越界失败；
- 缺少必填根因字段失败；
- `platform_code` 必须标记二次审批。

- [ ] **Step 2: 定义结构化输出模型**

复用现有 performance script generation 的 Agent/model selection 方式，但使用独立诊断模型，禁止复用脚本计划模型承载诊断结果。

- [ ] **Step 3: 实现只读 Agent 构造**

系统提示必须明确：

- 只能基于输入证据；
- 区分 observed、derived、inferred；
- 无证据时输出 `insufficient_evidence`；
- 不得输出密钥；
- 不得执行修改；
- 不得把 HTTP 200 直接等同于业务成功。

- [ ] **Step 4: 实现模型调用和失败封装**

复用 `apps/backend/app/agents/model_selection.py` 的模型选择，不在诊断模块新增 Provider 配置。模型调用异常、超时和结构化解析异常统一转换为稳定业务错误，并保留后端日志 trace ID。

- [ ] **Step 5: 使用 stub 模型通过测试**

Agent 测试不能依赖真实模型调用，使用固定结构化响应和异常 stub。运行：

```powershell
rtk pytest apps/backend/tests/test_performance_analysis.py -q -k agent
```

预期：PASS。

---

## Task 4: 实现异步分析服务和 API

**Files:**
- Create: `apps/backend/app/services/performance_testing/analysis_service.py`
- Modify: `apps/backend/app/api/v1/performance_runs.py`
- Modify: 实际 API router 注册文件
- Test: `apps/backend/tests/test_performance_run_api.py`

**Interfaces:**
- `create_analysis(project_id, run_id, actor) -> AnalysisSessionOut`
- `get_analysis(project_id, analysis_id, actor) -> AnalysisSessionOut`
- `list_run_analyses(project_id, run_id, actor) -> list[AnalysisSessionOut]`
- `reject_analysis(project_id, analysis_id, comment, actor) -> AnalysisSessionOut`

- [ ] **Step 1: 写 API 合约测试**

覆盖：

- 已停止运行可以创建分析并返回 `202`；
- 活动运行返回 `409 PERFORMANCE_ANALYSIS_RUN_ACTIVE`；
- 没有运行证据返回 `400 PERFORMANCE_ANALYSIS_NO_EVIDENCE`；
- 同一运行已有活动分析返回 `409 PERFORMANCE_ANALYSIS_ALREADY_RUNNING`；
- 跨项目 run/analysis 返回 `404` 或项目权限错误；
- 非管理员可以查看但不能获得本期不存在的修改动作；
- `available_actions` 与后端状态一致。

运行：

```powershell
rtk pytest apps/backend/tests/test_performance_run_api.py -q -k analysis
```

预期：FAIL。

- [ ] **Step 2: 实现创建和查询路由**

增加：

```http
POST /projects/{project_id}/performance-runs/{run_id}/ai-analysis
GET  /projects/{project_id}/performance-analysis/{analysis_id}
GET  /projects/{project_id}/performance-runs/{run_id}/ai-analysis
POST /projects/{project_id}/performance-analysis/{analysis_id}/reject
```

创建接口只负责权限、状态和会话创建，快速返回，不在 HTTP 请求中等待模型。

- [ ] **Step 3: 实现后台任务适配层**

遵循仓库已有后台 runner/worker 方式。分析任务执行：

1. `collecting`；
2. `analyzing`；
3. 保存结构化诊断；
4. 设置 `waiting_approval`；
5. 异常设置 `failed` 并保存错误摘要。

如果项目当前没有统一任务队列，第一版使用已有后台执行机制，不新增 Celery/Redis 依赖。

- [ ] **Step 4: 实现状态转换和幂等**

所有状态转换集中在 service，不允许 API handler 直接写状态。任务重试不能创建第二个活动会话。

- [ ] **Step 5: 通过后端 API 测试**

运行：

```powershell
rtk pytest apps/backend/tests/test_performance_run_api.py -q -k analysis
rtk pytest apps/backend/tests/test_performance_analysis.py -q
```

预期：PASS。

---

## Task 5: 增加前端 API 类型和 AI 分析抽屉

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts` 或现有性能 API 文件
- Create: `apps/frontend/src/components/ai-testing/performance-testing/performance-ai-analysis-drawer.tsx`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/performance-ai-analysis-progress.tsx`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/performance-ai-evidence-list.tsx`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/performance-ai-config-diff.tsx`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/locust-console.tsx`
- Test: `apps/frontend/tests/performance-run-detail-contract.test.mjs`
- Test: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- API types mirror backend `PerformanceAnalysisOut` exactly。
- Drawer consumes `projectId`、`runId`、`open` and `onOpenChange`。
- Drawer owns analysis polling and emits only `onAnalysisCreated`/`onClosed` style UI events。

- [ ] **Step 1: 写前端 contract 测试**

断言：

- 页面存在“AI 分析”按钮；
- 已停止运行才显示可用入口；
- 调用创建和查询分析 API；
- 右侧 Drawer 文案、阶段状态和“重新分析”存在；
- 本期不存在应用修改、自动重跑和源码审批按钮。

运行：

```powershell
rtk node apps/frontend/tests/performance-testing-contract.test.mjs
rtk node apps/frontend/tests/performance-run-detail-contract.test.mjs
```

预期：FAIL。

- [ ] **Step 2: 增加 API 类型和函数**

增加创建、查询、列表和驳回函数。错误响应保留业务错误码和 trace ID，不能统一替换成通用错误文本。

- [ ] **Step 3: 实现抽屉骨架和进度状态**

复用 `apps/frontend/src/components/ui/drawer.tsx`。抽屉关闭不取消后台任务；活动状态每 2 秒轮询，终态停止轮询；组件卸载清理计时器。

- [ ] **Step 4: 实现诊断摘要和证据列表**

展示分类、置信度、直接原因、根因、已证实证据、推断证据和缺失证据。敏感字段由后端处理，前端不再尝试恢复或显示原始值。

- [ ] **Step 5: 实现只读配置 Diff**

使用字段级 before/after 展示建议，明确显示“本期只读，不会修改配置”。不添加应用按钮，避免 UI 暗示本期支持自动修复。

- [ ] **Step 6: 接入 Locust 控制台**

在现有“重新压测”左侧增加“AI 分析”按钮。运行中禁用；已停止后传入当前项目和运行 ID 打开抽屉。

- [ ] **Step 7: 通过前端测试**

运行：

```powershell
rtk node apps/frontend/tests/performance-testing-contract.test.mjs
rtk node apps/frontend/tests/performance-run-detail-contract.test.mjs
```

预期：PASS。

---

## Task 6: 集成验证和可观测性

**Files:**
- Modify: `apps/backend/app/services/performance_testing/locust_runtime.py`（仅如现有字段不足时，先保持本期最小变更）
- Modify: `apps/backend/app/services/performance_testing/analysis_evidence.py`
- Modify: `apps/backend/tests/test_performance_analysis.py`
- Modify: `apps/frontend/tests/performance-run-detail-contract.test.mjs`

- [ ] **Step 1: 固定历史 404 场景夹具**

用本次已确认的模式构造 fixture：全部请求 404、请求体为空、OpenAPI 要求 `start_date`/`end_date`，但本期 Agent 只生成建议，不应用修复。

- [ ] **Step 2: 验证事实和推断分离**

断言诊断结果至少包含：

- 观测到的状态码分布；
- 请求体为空这一配置事实；
- 缺失响应体或目标服务日志时的缺失证据；
- 不把目标服务路由根因写成已证实结论。

- [ ] **Step 3: 验证敏感信息不泄露**

对 Agent 输入、数据库 JSON、API 响应和前端渲染快照执行敏感字段断言。

- [ ] **Step 4: 验证页面轮询生命周期**

覆盖打开、关闭、重新打开、分析成功、分析失败、网络失败和页面卸载场景。

- [ ] **Step 5: 运行第一期完整测试集**

```powershell
rtk pytest apps/backend/tests/test_performance_analysis.py apps/backend/tests/test_performance_analysis_repo.py apps/backend/tests/test_performance_run_api.py -q
rtk node apps/frontend/tests/performance-testing-contract.test.mjs
rtk node apps/frontend/tests/performance-run-detail-contract.test.mjs
```

需要确认新增测试通过，且没有修改无关测试或已有失败被掩盖。

---

## 后续独立计划

第一期只读闭环完成并稳定后，再分别创建以下实施计划：

1. **配置修复与单请求预检**：白名单应用器、字段 Diff 审批、预检和自动重跑。
2. **失败响应证据增强**：Locust 最终 URL、脱敏请求摘要、响应体摘要、业务规则失败详情。
3. **源码修复与二次审批**：隔离工作区、受控工具、Diff、基线检测、回滚和正式应用。

每个后续计划必须先基于第一期实际 API 和数据结构复核接口，不提前假设尚未实现的字段。

