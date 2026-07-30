# API 场景可执行请求链路实施计划

1. 为 Binding 往返和 multipart 请求增加失败测试。
2. 保留运行时 Binding 的 required 与 transform。
3. 让 Requests 客户端消费 form 与 multipart_form。
4. 为 object ValueSource 增加解析和递归求值测试。
5. 实现 object ValueSource 的规范及运行时转换。
6. 为扩展 JSON/SSE Schema 投影增加失败测试。
7. 支持 x-json-schema 与 x-event-data-schema 投影。
8. 增加完整 SegmentCode 到 SSE 回归测试。
9. 运行编排、运行时和生成器相关测试。
