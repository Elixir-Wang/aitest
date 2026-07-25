# 改进接口调试请求体编辑与 multipart 文件上传

## 背景

当前接口调试弹窗将所有请求体统一展示为 JSON 文本框。对于 OpenAPI 声明为 `multipart/form-data` 的接口，前端仅根据 Schema 生成必填字段示例，导致可选字段不展示、二进制字段退化为字符串，同时后端仍通过 `json=` 或原始 `data=` 发送请求，无法构造包含 boundary 和真实文件内容的 multipart 请求。

以 `/openapi/v1/chatflow/offline_upload_file/` 为例，接口资产已保存完整的请求体 Schema，但调试弹窗只显示 `username`、`flow_uuid`、`tenant_name` 三个必填字段，未展示 `mode`、`extra_params`、`file` 等可选字段，也无法选择和上传文件。

## 目标

- 根据请求体 Content-Type 选择正确的编辑器和发送协议。
- 将 `multipart/form-data` 和 `application/x-www-form-urlencoded` 请求体展示为 Schema 驱动的字段表单。
- 展示 Schema 中的全部字段，并准确呈现类型、必填状态、描述、示例和约束。
- 将 `type: string, format: binary` 字段渲染为文件选择控件。
- 使后端调试代理能够使用 `data=` 与 `files=` 发送真实 multipart 请求。
- 保持现有 JSON、原始文本、Header、Path、Query 和环境认证调试行为兼容。

## 非目标

- 不根据字段中文描述自动推断条件必填业务规则。
- 不修改导入 OpenAPI 文档的 Schema 语义，也不为缺失的 Schema 创造字段。
- 不实现大文件分片上传、断点续传或文件资产长期存储。
- 不重构接口资产详情页、接口场景编辑器或自动化脚本生成链路。
- 第一版不提供复杂对象表单设计器；复杂对象和数组继续使用局部 JSON 编辑能力。

## 预期收益

- 用户可以直接按接口文档填写字段，不再手工编辑 multipart JSON 占位内容。
- 文件上传接口可以在调试弹窗中真实发送并查看响应。
- 请求体展示与 OpenAPI Schema 保持一致，避免必填字段过滤造成的信息丢失。
- Content-Type 与实际请求编码方式一致，减少因伪 multipart 请求导致的误判。

## 影响范围

- 前端接口调试弹窗的状态模型、请求体渲染和调试 API 调用。
- 前后端内部接口调试请求契约。
- 后端调试代理构造 `requests.request` 参数的逻辑。
- 接口调试单元测试、前端静态检查和关键交互回归验证。
