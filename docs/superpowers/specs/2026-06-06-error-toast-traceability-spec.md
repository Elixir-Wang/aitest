# 错误 Toast 入库与日志详情跳转 Spec

## 背景

右下角 toast 会自动消失。用户看到报错后，如果没有及时截图或复制，后续很难从界面找回具体错误。

当前系统已有：

- 后端 `wrap_api_response` 为每个 API 请求生成 `trace_id`，并通过 `x-trace-id` 返回给前端。
- 后端文件日志会携带 trace id。
- `operation_logs` 已有 `request_id` 字段，可作为 trace id 的业务可见入口。
- 前端 `ApiRequestError` 能从响应体或响应头提取 traceId。

本次产品规则：

```text
由 reportError 触发的错误 toast 必须写入日志模块。
点击 toast 的“查看详情”必须进入日志详情页，而不是前端抽屉。
```

## 目标

- 前端接口/运行错误通过受控接口写入 `operation_logs`。
- toast 的“查看详情”进入 `/settings/logs/{logId}`。
- 日志详情页展示脱敏后的错误摘要、页面上下文、接口路径、traceId/request_id。
- 后端业务日志默认带当前请求 trace id，方便从系统日志关联后端文件日志。
- 日志列表支持通过 traceId、taskId、objectId 搜索。

## 非目标

- 不把普通前端本地校验 toast 入库，例如“请选择项目”“请填写名称”。
- 不允许前端自由指定任意 `operation_logs` 字段。
- 不记录完整请求体、文件内容、prompt、模型响应、cookie、token、password、authorization、api_key 等敏感信息。
- 不开放匿名写系统日志入口；客户端错误上报需要有效登录态。

## 设计

### 后端

新增受控上报接口：

```text
POST /api/v1/operation-logs/client-errors
```

请求字段白名单：

```ts
{
  title: string;
  message: string;
  code?: string;
  status?: number;
  trace_id?: string;
  method?: string;
  path?: string;
  page_url?: string;
  action_label?: string;
  occurred_at?: string;
}
```

写入规则：

- `log_type="audit"`
- `module="frontend"`
- `action="client_error"`
- `object_type="client_error"`
- `object_id=trace_id`
- `result="failed"`
- `source="web"`
- `request_id=trace_id`
- `project_id` 从 `/projects/{projectId}` 路径推断，并由后端按当前用户权限校验。
- 所有文本进入 `operation_logs` 前继续走敏感信息脱敏。

响应：

```ts
{
  log_id: string | null;
  trace_id: string;
}
```

### 前端

`reportError()` 负责：

- 提取 `ApiRequestError` 中的 message/status/code/traceId。
- 调用 `POST /operation-logs/client-errors` 后台写入日志。
- 展示错误 toast。
- toast 的“查看详情”等待写入结果：
  - 成功：跳转 `/settings/logs/{logId}`。
  - 失败：降级跳转 `/settings/logs?keyword={traceId}`。

独立日志详情页：

```text
apps/frontend/src/app/(main)/settings/logs/[logId]/page.tsx
```

日志列表内原有行详情弹窗可保留，但 toast 不再打开本地最近错误抽屉。

## 验收

- 后端客户端错误上报能生成 `module=frontend/action=client_error/result=failed` 的日志。
- 日志详情中的 `request_id` 等于前端上报的 traceId。
- 敏感字段不以明文出现在 `summary`、`failure_reason`、`before`、`user_agent`。
- 项目路径错误能按权限挂到项目日志。
- toast 点击“查看详情”进入 `/settings/logs/{logId}`。
- 前端 typecheck 通过。
- 后端 traceability 测试通过。
