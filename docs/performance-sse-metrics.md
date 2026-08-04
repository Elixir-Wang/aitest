# 性能测试 SSE 指标

## 配置与生成

单接口和接口场景性能测试都支持 `transport=http` 和 `transport=sse`。场景 SSE 需要选择一个接口请求步骤作为目标步骤，Locust 只对该步骤消费事件流，其余场景步骤保持原传输行为。历史配置缺少 `transport` 时按 HTTP 执行。SSE 配置包含最大流时长、可选结束规则和一组首次命中指标；指标 ID 在单个测试内唯一。

创建单接口 SSE 性能测试时，可以使用当前尚未保存的 Path、Query、Header 和 Body 参数运行一次真实接口探测。创建场景 SSE 性能测试时，系统按当前保存场景快照执行目标步骤之前的步骤和输出绑定，再探测选定的 SSE 步骤；场景已有的 JSON Pointer/JSONPath 提取器以及 JSON、表单、multipart、Cookie 和 Header 请求编码会原样复用。AI 只生成 `PerformanceSseConfig` 声明式候选，不生成 Python。候选必须在真实样本上通过相同匹配器回放并由用户应用，脚本生成阶段不会再次调用模型。AI 不可用或输出无效时，系统使用真实事件结构生成确定性候选并显示警告。

## 匹配语义

- 事件按照 SSE 空行帧边界提交，多行 `data:` 使用换行连接。
- 注释行被忽略；缺少 `event:` 时事件名为空字符串。
- `data_json` 路径只支持根 `$`、对象字段、数组下标和 `[*]`。
- 操作符支持 `exists`、`non_empty`、`equals`、`contains` 和受限 `matches`。
- 每条规则只记录同一请求中的第一次命中，正式耗时使用客户端 `time.perf_counter()`。
- 命中指标后仍继续消费流，直到结束规则、正常 EOF、超时或协议失败。

常见规则示例：

```json
{
  "id": "first_answer",
  "name": "首次回答时间",
  "match": {
    "event_name": "message",
    "source": "data_json",
    "path": "$.data.event_type",
    "operator": "equals",
    "expected": "answer"
  },
  "occurrence": "first",
  "missing_policy": "fail_request"
}
```

OpenAI 风格首内容可使用 `$.choices[*].delta.content` 加 `non_empty`；首次工具调用可使用 `$.choices[*].delta.tool_calls[*]` 加 `exists`。

## 缺失与目标

- `record_null`：记录缺失，不增加 HTTP 失败数。
- `fail_request`：指标缺失时将该请求标记为失败。
- `ignore`：不把缺失计入业务失败。

缺失值不会按 `0 ms` 进入平均值或分位数。性能目标支持按指标 ID 设置 P95/P99 上限；没有命中样本或分位数不可计算时，目标状态为 `not_evaluated`，总体结论不会误判为通过。

## 采集、报告与安全

SSE 时间样本写入独立的版本化 JSONL 文件，不通过 Locust 自定义请求事件混入 HTTP CSV。系统从原始时间样本计算平均值、P50、P95 和 P99，并公开请求数、命中数、缺失数、失败数、JSON 解析错误、流超时和结束规则未命中数。

单帧、单流、事件数量、探测样本和测量文件均有固定上限。测量文件达到 64 MiB 后停止追加并标记截断；摘要返回 SHA-256。运行目录删除或历史清理时，样本文件随目录一并清理。

完整 SSE 正文、认证信息、Cookie、Token 和工具参数不会进入 AI 分析证据。报告只读取聚合时间指标和脱敏质量摘要。不同 SSE 规则或计算器版本产生不同来源指纹，不应直接作为同口径基线比较。
