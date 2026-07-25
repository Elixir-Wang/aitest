# Tasks

## 1. 建立请求体编辑模型

- [ ] 扩展前端调试表单状态，分离 `bodyValues`、`bodyFiles` 和 `rawBodyText`。
- [ ] 增加 Content-Type 标准化和请求体编辑器分发函数。
- [ ] 增加从完整 Schema 初始化字段状态的逻辑，不再过滤可选字段。
- [ ] 复用现有 Schema 行解析能力，补充字段级 Schema 元数据读取。
- [ ] 为 Content-Type 分发、字段初始化和类型转换增加可测试的纯函数边界。

## 2. 实现结构化请求体编辑器

- [ ] 新增 multipart/urlencoded 请求体字段列表组件。
- [ ] 实现字符串、数字、布尔、枚举、对象、数组和 binary 字段控件映射。
- [ ] 实现字段名称、类型、必填标识、描述、约束和示例展示。
- [ ] 实现文件选择、文件摘要、清除和重新选择交互。
- [ ] 实现必填字段、数字、布尔和局部 JSON 的发送前校验。
- [ ] 保持 JSON 和原始文本请求体使用文本编辑器。

## 3. 扩展前端调试 API 调用

- [ ] 无文件请求继续使用现有 JSON 调试 Payload。
- [ ] 有文件请求使用 `FormData`，写入 `payload` JSON 和 `file::<field>` 文件 part。
- [ ] 避免 API Client 对 FormData 手工设置 JSON Content-Type。
- [ ] 确保关闭弹窗或切换接口时释放文件状态。
- [ ] 在发送按钮旁保持现有忙碌状态和错误提示行为。

## 4. 扩展后端调试请求协议

- [ ] 为调试路由增加 JSON 与 multipart 两种内部请求解析路径。
- [ ] 将 multipart `payload` 解析并校验为统一调试输入模型。
- [ ] 从 `file::<field>` part 恢复目标字段名、文件名、MIME 类型和文件流。
- [ ] 增加单文件和单次请求总大小限制，并返回稳定错误码。
- [ ] 保证临时文件和流在请求结束后关闭，不写入长期项目存储。

## 5. 按目标 Content-Type 构造请求

- [ ] 重构调试请求构造结果，显式区分 `json_body`、`form_body`、`files` 和 `raw_body`。
- [ ] JSON 请求使用 `requests.request(json=...)`。
- [ ] urlencoded 请求使用 `requests.request(data=...)`。
- [ ] multipart 请求使用 `requests.request(data=..., files=...)`。
- [ ] multipart 请求移除手工 Content-Type，让 Requests 自动生成 boundary。
- [ ] 扩展公开请求摘要，安全展示文件元数据且不返回文件内容。

## 6. 验证和交付

- [ ] 增加后端 JSON、urlencoded、multipart 和文件限制单元测试。
- [ ] 增加敏感 Header、文件内容和异常消息脱敏测试。
- [ ] 验证 `/openapi/v1/chatflow/offline_upload_file/` 展示完整字段且可上传文件。
- [ ] 验证只有 Schema `required` 字段显示并执行硬性必填校验。
- [ ] 运行接口调试相关 pytest。
- [ ] 运行前端 Biome 检查和 Next.js 构建。
- [ ] 使用浏览器验证弹窗布局、文件选择、错误状态和发送结果。
