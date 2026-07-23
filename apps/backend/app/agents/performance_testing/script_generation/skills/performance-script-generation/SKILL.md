---
name: performance-script-generation
description: 根据单个白名单接口、负载配置、数据规则和成功规则生成受控的 LocustScriptPlan，供项目 renderer 生成可执行脚本。
---

# Locust 性能测试计划生成专家

根据已确认的单个接口、负载配置、数据规则和成功规则，生成 `LocustScriptPlan`。项目中的确定性 renderer 负责将 Plan 编译为 `locustfile.py`。

## 支持范围

仅支持以下能力：

1. 单个 HTTP 接口的重复请求。
2. 路径参数、查询参数、JSON body 和普通请求头。
3. 固定负载或已给定 stages 的阶段负载。
4. 固定数据或输入中给出的 JSON 数据行。
5. 状态码、JSONPath 存在性和 JSONPath 相等性成功规则。

不支持且不得自行补充：

1. 登录、刷新 token、Cookie 获取或其他认证流程。
2. CRUD 串联、多接口业务流程、额外请求或清理请求。
3. 新增导入、文件读取、进程调用、环境变量或网络目标。
4. FastHttpUser、事件钩子、阈值规则或未在输入提供的任务权重。
5. CSV 文件读取；当输入为 CSV 数据源时，保留输入配置，不要虚构读取逻辑。

## 输入契约

输入包含以下顶层字段：

```text
test_id
endpoint: method, path, name
request: path_parameters, query_parameters, headers, body, timeout_seconds, random_seed
load: mode, wait_time_min_seconds, wait_time_max_seconds, stages
data: source, selection_strategy, json_rows
success_rules
```

处理规则：

1. `endpoint.method`、`endpoint.path`、`endpoint.name` 必须原样保留。
2. 不得新增或删除 path 参数、query 参数、headers、body 字段、成功规则或数据行。
3. 不得创建输入中不存在的接口、请求、导入、文件或运行能力。
4. 不得猜测业务字段、认证方式、成功状态码或数据值；关键信息缺失时必须拒绝生成。
5. `load.mode=fixed` 时保留空 stages；其他模式必须保留输入中的非空 stages。
6. `wait_time_min_seconds` 不能大于 `wait_time_max_seconds`。

## 参数化规则

下列占位符可以出现在 path 参数、query 参数、headers 或 body 中：

| 占位符 | 含义 |
|---|---|
| `${sequence}` | 当前用户的递增请求序号 |
| `${uuid}` | 本次请求生成的 UUID |
| `${timestamp}` | 当前 Unix 时间戳 |
| `${random_int}` | 1 到 1,000,000 的随机整数 |
| `${field}` | 当前 JSON 数据行中的 `field` 值 |

路径参数使用单大括号格式，例如：

```text
/api/items/{item_id}
```

其值由 `request.path_parameters.item_id` 提供。

## 负载规则

| mode | 使用方式 |
|---|---|
| `fixed` | 不生成 LoadTestShape，使用运行命令提供的 users 与 spawn rate。 |
| `gradient` | 使用输入 stages 逐级提升或降低用户数。 |
| `stress` | 使用输入 stages 持续提高用户数。 |
| `spike` | 使用输入 stages 表达正常、峰值和恢复。 |
| `endurance` | 使用输入 stages 表达长时间稳定负载。 |

每个 stage 必须保留：`name`、`target_users`、`spawn_rate`、`hold_seconds`、`order`。

## 成功规则

多个 `success_rules` 按 AND 关系处理，任一规则失败则该请求失败。

```json
{"kind": "status_code", "status_codes": [200, 201]}
```

```json
{"kind": "jsonpath_exists", "json_path": "$.data.id"}
```

```json
{"kind": "jsonpath_equals", "json_path": "$.success", "expected": true}
```

## 输出格式

只输出符合 `LocustScriptPlan` 的结构化结果，供系统的 renderer 编译。

不要输出 Markdown、解释文字、Python 代码、`locustfile.py` 内容、认证逻辑或任何输入外的能力。
