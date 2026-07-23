# 设计方案

## 1. 方案总览

```text
业务目标 → AI 规划器 → Plan JSON → 服务端校验 → 画布预览
                                      ↓
                              用户应用到草稿
                                      ↓
                         现有检查 → 发布 → 运行
```

AI 只负责提出计划，服务端负责事实校验，现有场景运行器负责确定性执行。三者通过版本化的 `ScenarioPlan` 契约连接。

## 2. 领域边界

### 2.1 接口资产

AI 只能使用当前项目的 `ApiAutomationEndpoint`。检索结果至少包含 `endpoint_id`、方法、路径、请求参数 Schema、响应 Schema、鉴权要求、标签、资产状态和资产版本。提示词上下文中必须脱敏密钥、Cookie 和环境变量值。

### 2.2 场景步骤

继续复用 `ApiAutomationScenarioStep`：

- `api_request`
- `condition`
- `wait`
- `poll`
- `assign`

AI 计划中的节点必须可以无损转换为现有步骤配置。节点 ID 使用稳定 ID，显示名称变化不得破坏变量引用。

### 2.3 图扩展点

第一阶段仍按 `step_order` 执行；计划可携带可选图信息：

```json
{
  "graph_version": 1,
  "edges": [
    {
      "source": "step_login",
      "target": "step_create_order",
      "condition": "success"
    }
  ]
}
```

边用于表达依赖和预览，不改变第一阶段的线性执行语义。若后续启用 DAG 执行，必须新增独立执行版本，不得根据画布位置推断顺序。

## 3. AI 规划接口

### 3.1 生成计划

```http
POST /projects/{project_id}/api-scenarios/ai-plan
```

请求：

```json
{
  "goal": "创建订单并验证订单状态",
  "source_scope": {
    "endpoint_ids": [],
    "tags": ["订单", "认证"]
  },
  "constraints": {
    "environment_id": "env_test",
    "max_steps": 8,
    "allow_write": true,
    "require_cleanup": true
  },
  "scenario_id": null
}
```

请求规则：

1. `goal` 必填，长度和 token 数量受限。
2. `source_scope.endpoint_ids` 为空时，只检索当前项目可见资产。
3. `allow_write=false` 时，计划不得包含被标记为写操作的资产。
4. `scenario_id` 存在时，AI 可在当前场景上提出增量修改，但不能自动覆盖草稿。

响应：

```json
{
  "plan_id": "plan_123",
  "plan_version": 1,
  "graph_version": 1,
  "scenario_name": "创建订单并验证状态",
  "nodes": [],
  "edges": [],
  "assumptions": [],
  "warnings": [],
  "unresolved_items": [],
  "confidence": 0.91,
  "validation": {
    "valid": true,
    "errors": [],
    "warnings": []
  },
  "expires_at": "2026-07-24T12:00:00Z"
}
```

`validation.valid=false` 的计划只能查看和编辑，不能应用到草稿。

### 3.2 应用计划

```http
POST /projects/{project_id}/api-scenarios/ai-plans/{plan_id}/apply
```

请求包含 `scenario_id`、`expected_revision` 和用户确认信息。服务端重新加载计划、接口资产和场景版本后再次校验，再调用现有步骤替换逻辑写入草稿。计划过期、接口资产变化或场景版本冲突时返回 `409`，不得静默覆盖。

第一阶段不新增前端直写步骤的旁路；应用动作最终复用现有 `replace_api_scenario_steps` 语义。

## 4. Plan JSON 约束

### 4.1 节点

```json
{
  "id": "step_login",
  "type": "api_request",
  "endpoint_id": "endpoint_login",
  "name": "用户登录",
  "request_overrides": {},
  "bindings": [],
  "extractors": [],
  "assertions": [],
  "control_config": {},
  "on_failure": "stop",
  "enabled": true
}
```

`api_request` 和 `poll` 必须有属于当前项目的 `endpoint_id`；工具节点不得携带接口 ID。计划不可包含任意脚本或未注册的节点类型。

### 4.2 变量绑定

持久化引用使用稳定 ID：

```json
{
  "target": "header.Authorization",
  "source": "step_login.token"
}
```

服务端必须拒绝引用后续步骤、未知步骤、未知输出和跨项目变量。变量选择器在前端显示可读名称，提交时使用稳定引用。

### 4.3 响应提取与断言

响应提取规则必须有唯一输出名；JSONPath、Header 和状态码来源必须符合现有步骤契约。接口步骤默认至少生成一条状态码或 Schema 断言；没有断言时返回警告，发布校验按当前项目规则决定是否阻止。

## 5. 服务端校验顺序

1. 认证和项目可见性检查。
2. 计划 JSON Schema 校验。
3. 节点类型、节点数量和边数量限制。
4. 所有 `endpoint_id` 的项目归属、资产状态和版本检查。
5. 步骤顺序、重复 ID、变量输出唯一性检查。
6. 绑定来源可达性和基础类型检查。
7. 条件表达式、提取器和断言格式检查。
8. 环检测、孤立节点和不可达节点检查；第一阶段只允许增强线性结构。
9. 写操作、敏感字段、未解决项和资产差异生成 warnings/errors。

应用、保存、发布前必须重复校验，不能只信任生成接口返回的结果。

## 6. 前端体验

在现有 [api-scenario-editor.tsx](/Users/wanghongbao/project/test_project/apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx) 和 [api-scenario-canvas.tsx](/Users/wanghongbao/project/test_project/apps/frontend/src/components/ai-testing/api-automation/api-scenario-canvas.tsx) 中增加：

- 顶部“AI 编排”入口。
- 业务目标、接口范围、环境和约束输入抽屉。
- 计划预览态，不污染当前草稿。
- 节点级 AI 标记、假设、警告和未解决项。
- “应用到草稿”“重新规划局部链路”“放弃计划”操作。
- 计划应用前的差异预览和场景版本冲突提示。
- 计划应用后继续使用现有检查、保存、发布和运行按钮。

运行结果沿用现有步骤级结果，并在画布上按 `step_id` 高亮；AI 计划本身不参与运行时决策。

## 7. 安全、审计和可观测性

- 规划上下文使用项目权限过滤和敏感字段脱敏。
- 服务端拒绝任意 URL、跨项目资产和未经注册的工具调用。
- 写操作计划必须显示风险，并要求用户确认。
- 计划生成、应用、放弃、冲突和校验失败写入审计日志。
- 记录 `plan_id`、`plan_version`、模型标识、提示版本、资产版本、确认人和最终场景修订号。
- 日志和运行快照不得记录密钥、Authorization、Cookie 原文。

## 8. 失败处理

- 模型超时或不可用：保留当前草稿，提示用户重试，不修改场景。
- 返回非法 JSON：服务端拒绝并记录可诊断错误。
- 校验失败：显示具体节点和字段，不允许应用。
- 资产在生成后发生变化：应用时返回 `409`，要求重新规划或人工确认。
- 并发编辑冲突：比较 `expected_revision`，禁止最后写入覆盖。

## 9. 验证策略

- 后端：Plan Schema、资产归属、变量依赖、写操作限制、版本冲突和审计测试。
- 执行兼容：AI 应用后的场景必须通过现有校验、发布、执行和版本恢复测试。
- 前端：计划生成、预览、应用、放弃、局部重规划和错误定位测试。
- 合约：验证计划不能含任意 URL、未知 endpoint、后续变量引用和未注册节点。
- 安全：验证脱敏、权限隔离、审计字段和写操作确认。
- 性能：在 100 个步骤以内完成计划校验和画布渲染，不阻塞编辑器。
