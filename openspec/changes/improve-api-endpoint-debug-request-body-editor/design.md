# 设计方案

## 总体方案

采用“Content-Type 分发器 + Schema 字段编辑器 + 后端协议适配器”的方案。接口调试弹窗先读取当前接口 `request_body.content` 的媒体类型和 Schema，再选择对应编辑器；发送时将统一的调试表单状态转换为目标请求所需的 `json`、`data`、`files` 或原始文本。

```text
OpenAPI request_body
        │
        ▼
Content-Type 分发器
        │
        ├─ application/json ─────────────► JSON 编辑器
        ├─ multipart/form-data ──────────► 字段表单 + 文件控件
        ├─ application/x-www-form-urlencoded ► 字段表单
        └─ text/* / 其他 ────────────────► 原始文本框
        │
        ▼
EndpointDebugForm
        │
        ▼
内部调试请求编码
        │
        ▼
后端 requests.request(json/data/files)
```

## 关键设计决策

### 1. 按 Content-Type 分发，而不是针对单个接口特判

新增请求体编辑器边界，根据媒体类型选择渲染和序列化策略。不得通过接口路径、接口名称或字段名称识别文件上传接口。

媒体类型匹配忽略大小写和参数，例如 `multipart/form-data; charset=utf-8` 按 `multipart/form-data` 处理。

### 2. 表单字段来源于完整 Schema

结构化表单直接遍历 `schema.properties`，不得复用“只生成必填示例”的过滤逻辑。`schema.required` 只决定必填标识和发送前校验，不决定字段是否展示。

字段控件映射：

| Schema | 控件 |
|---|---|
| `string` | 文本输入框 |
| `integer` / `number` | 数字输入框 |
| `boolean` | 开关或布尔下拉框 |
| `enum` | 下拉选择器 |
| `string` + `binary` | 文件选择控件 |
| `object` / `array` | 局部 JSON 编辑器 |

每个字段展示名称、类型、必填状态、描述、约束和示例。空值字段保留在编辑状态中，但发送时默认忽略未填写的可选字段。

### 3. 分离普通值、文件和原始文本状态

调试表单状态调整为：

```ts
type EndpointDebugForm = {
  environmentId: string;
  pathParams: Record<string, string>;
  queryParams: Record<string, string>;
  headers: Record<string, string>;
  bodyValues: Record<string, unknown>;
  bodyFiles: Record<string, File | null>;
  rawBodyText: string;
};
```

`application/json` 可以继续使用 `rawBodyText`，以保持现有用户编辑体验；结构化表单使用 `bodyValues`，二进制字段使用 `bodyFiles`。

初始化时：

- 优先采用字段级 `example`。
- 其次采用字段级 `default`。
- 没有示例或默认值时使用空值，不再自动填充 `0`、`false` 或空字符串作为已提交值。
- 文件字段始终初始化为 `null`。

### 4. 内部调试接口支持文件传输

无文件的调试请求继续使用现有 JSON 协议，降低回归风险。存在文件时，前端调用平台调试接口使用 `FormData`：

- `payload`：JSON 字符串，包含环境 ID、Path、Query、Headers、普通请求体字段和目标 Content-Type。
- 文件 part：字段名使用稳定前缀 `file::<schema-field-name>`。
- 每个文件保留原始文件名和浏览器提供的 MIME 类型。

后端调试路由解析 `payload` 和动态文件 part，恢复为内部请求模型。文件只在当前请求生命周期内存在，不写入项目文件区。

后端目标请求参数映射：

| 目标 Content-Type | `requests.request` 参数 |
|---|---|
| `application/json` | `json=body` |
| `multipart/form-data` | `data=body_values`, `files=files` |
| `application/x-www-form-urlencoded` | `data=body_values` |
| 原始文本 | `data=raw_body` |

发送 multipart 时不得手工设置 `Content-Type`，由 `requests` 自动生成包含 boundary 的 Header。用户显式填写的 multipart Content-Type 应在发送前移除或拒绝，以防止 boundary 不匹配。

### 5. 保持调试结果可观察性

调试结果中的请求摘要继续脱敏敏感 Header，并增加以下信息：

- `content_type`：最终请求类型。
- `body`：普通表单字段或 JSON 内容。
- `files`：仅返回字段名、文件名、MIME 类型和大小，不返回文件内容。

文件内容、认证 Token 和密码不得出现在响应、日志或异常消息中。

## 前端交互设计

multipart 请求体区域采用左右布局：

- 左侧约 40%：字段元信息。
- 右侧约 60%：输入控件。
- 字段之间使用分隔线，长描述允许换行。
- 文件字段支持点击选择，首版可复用原生文件输入，不强制引入新的上传组件。
- 必填字段为空时，在字段附近显示校验错误，并阻止发送。
- 可选字段为空时不发送该字段。
- 选择文件后展示文件名和大小，并允许清除或重新选择。

JSON 请求仍使用现有文本编辑区域，避免本次改造扩大到完整 JSON 表单设计器。

## 校验规则

- 只对 OpenAPI `schema.required` 声明的字段执行硬性必填校验。
- 数字和布尔字段在前端转换为对应类型，转换失败时阻止发送。
- JSON 局部字段必须能够解析为合法 JSON。
- 文件字段只有在选择文件后才发送。
- 不从“mode 为 1 时必填”等自然语言描述中自动创建规则。
- 后端再次校验调试 Payload 结构、文件字段名和请求体 Content-Type。

## 错误处理

- Schema 不存在或无法识别时，降级为原始文本编辑器，不阻断接口调试。
- 文件读取或 multipart 解析失败时返回明确的调试参数错误，不向目标服务发送请求。
- 目标请求失败继续返回当前统一的调试错误结果。
- 文件超过调试限制时在平台后端发送前拒绝。首版建议单文件上限 20 MB、单次请求总文件上限 50 MB，并将限制集中配置。
- 同名多文件字段若 Schema 未声明数组，首版只接受一个文件并提示用户。

## 兼容与迁移

- 不变更接口资产数据库结构。
- 不变更现有 OpenAPI 导入和 `$ref` 解析逻辑。
- JSON 调试请求保持原接口契约和行为。
- 前端只在存在文件时切换到 multipart 内部调试协议。
- 后端保留原 JSON 调试入口处理，新增 multipart 解析分支，便于渐进发布和回滚。

## 风险与取舍

- 内部调试接口使用 multipart 后，不能继续完全依赖 Pydantic JSON Body 自动解析，需要显式解析并复用统一校验函数。
- 文件只保存在内存或临时流中可以减少数据残留，但大文件会增加后端内存压力，因此必须设置限制。
- Schema 描述中的条件必填无法可靠自动执行；本次选择尊重标准 OpenAPI 结构，避免基于中文文案猜测业务。
- 暂不把 JSON 请求体也改造成结构化表单，以控制影响范围并保留熟悉的调试体验。

## 测试策略

- 前端字段映射：全部属性展示、必填标识、binary 文件控件、enum、数字、布尔和复杂 JSON 字段。
- 前端初始化：可选字段不再丢失，示例和默认值正确应用。
- 前端提交：必填校验、空可选字段过滤、文件 FormData 编码、JSON 兼容。
- 后端请求构造：JSON 使用 `json=`，urlencoded 使用 `data=`，multipart 使用 `data=` 与 `files=`。
- 后端 Header：multipart 不手工设置 Content-Type，显式错误 Header 被处理。
- 安全：请求摘要不包含文件内容和敏感 Header。
- 回归：Path、Query、Header、环境认证、响应展示和错误处理保持原行为。
