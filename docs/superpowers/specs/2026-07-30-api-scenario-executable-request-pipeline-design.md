# API 场景可执行请求链路修复设计

## 目标

让 AI 根据任意自然语言和接口资产生成的场景计划，在应用后保持语义一致，并能由 pytest + Requests 运行时正确发送 JSON、表单、multipart 和 SSE 请求。

## 根因

- 规范 Binding 转换为运行时 Binding 时丢失 `required` 和 `transform`。
- 规范 multipart 目标被转换为 `request.multipart_form`，生成的 Requests 客户端却不读取该字段。
- 当前 ValueSource 只能提供单值，无法由多个输入安全构造需要 JSON 序列化的 multipart 字符串字段。
- 资产投影忽略 `x-json-schema` 与 `x-event-data-schema`。
- 服务端校验只检查图结构，没有检查计划是否受当前运行时能力支持。

## 设计

### Binding 往返一致性

`binding_to_runtime` 必须保留 `required` 和非空 `transform`。预览、持久化快照和执行阶段使用相同转换语义。

### 请求适配

运行时请求客户端统一支持：

- `request.body` 作为 JSON 或 raw body；
- `request.form` 作为 urlencoded 表单；
- `request.multipart_form` 作为 multipart 文本字段，并转换为 Requests 的 `(field, (None, value))` parts；
- `request.files` 作为 multipart 文件字段；
- multipart 文本和文件字段统一通过 Requests `files=` 发送，并移除手工 `Content-Type`，确保即使没有文件也会生成 multipart boundary。

### 结构化对象来源

在现有 ValueSource 判别联合上兼容增加 `object`：

```json
{
  "type": "object",
  "properties": {
    "question": {"type": "user_input", "name": "question"},
    "stream": {"type": "literal", "value": true}
  }
}
```

对象属性仍由受控 ValueSource 递归组成，不接受脚本或模板表达式。对象来源配合 `json_encode` 生成 multipart 中的 JSON 字符串。

### 扩展 Schema 投影

- `x-json-schema` 投影为字符串字段的嵌套编码 JSON 槽位。
- `x-event-data-schema` 投影为 SSE `data:` JSON 槽位。
- 标准 OpenAPI Schema 优先，扩展字段仅在对应协议位置生效。

### 验证

新增阻断校验：

- transform 无法被运行时保留；
- Binding 目标不受当前运行时支持；
- `json_encode` 的来源已经是字符串；
- 必填用户输入未被任何 Binding 或控制节点引用。

## 验收场景

固定回归场景为“生成 SegmentCode，再发起 Multi-Agent SSE 对话”：

1. 第一步提取 `/data/segment_code`。
2. 第二步 multipart 收到 `segment_code`、`message_source`、`username`、`data`。
3. `data` 由动态输入构造并只 JSON 编码一次。
4. 应用计划后 `transform` 保持不变。
5. Requests 调用参数中 multipart 文本字段位于 `data=`。
