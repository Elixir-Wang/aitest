---
comet_change: improve-api-endpoint-debug-request-body-editor
role: technical-design
canonical_spec: openspec
---

# 接口调试请求体编辑与 multipart 文件上传设计

## 问题陈述

接口资产已经保存完整的 OpenAPI 请求体 Schema，但接口调试弹窗使用单一 JSON 文本框承载所有请求体。初始化逻辑在 Schema 存在 `required` 时只生成必填字段示例，导致可选字段从调试视图中消失；binary 字段没有 File 状态承载能力；后端仅支持 `json_body` 和 `raw_body`，无法通过 Requests 的 `files=` 发送真实 multipart 请求。

因此，本次改造必须同时覆盖展示模型和发送协议。只修改 UI 会产生“看起来可以上传、实际仍发送伪 multipart JSON”的不完整功能。

## 已确认方案

- 以 Content-Type 为策略分发边界，不对具体接口路径做特判。
- JSON 保留文本编辑器；multipart 和 urlencoded 使用 Schema 字段表单；其他类型降级为原始文本。
- 表单展示全部 `schema.properties`，`schema.required` 只控制必填标识和校验。
- binary 字段使用浏览器 File 对象保存，并通过平台内部 FormData 调试协议传输。
- 后端统一恢复调试模型，并按目标 Content-Type 选择 `json`、`data`、`files` 或原始 `data`。
- multipart Content-Type 由 Requests 自动生成 boundary。
- 条件必填只接受标准 Schema 规则，不解析中文描述猜测业务。

## 主要代码边界

前端主要涉及：

- `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx`
- `apps/frontend/src/lib/api-client.ts`
- 可按现有组件组织方式抽取新的请求体编辑组件，但不得引入新的表单框架。

后端主要涉及：

- `apps/backend/app/api/v1/api_automation.py`
- `apps/backend/app/schemas/api_automation.py`
- `apps/backend/app/services/api_automation/service.py`
- `apps/backend/tests/test_api_automation_endpoint_debug.py`

## 数据流

1. 用户打开调试弹窗。
2. 前端从接口资产读取 Content-Type 和完整 Schema。
3. 前端初始化普通字段、文件字段或原始文本状态。
4. 用户填写字段并触发客户端 Schema 校验。
5. 无文件时复用 JSON 调试协议；有文件时创建内部 FormData。
6. 后端解析并规范化为统一调试输入。
7. 后端按目标 Content-Type 构造 Requests 参数。
8. 后端返回脱敏后的请求摘要、响应状态、耗时、Header 和响应体。

## 发布边界

本变更不需要数据库迁移，不修改接口资产结构，不修改 OpenAPI 导入规则。发布可以采用前后端同版本上线；如果需要分阶段发布，应先发布兼容 multipart 内部协议的后端，再发布启用文件控件的前端。

## 验收重点

- 离线上传文件接口展示完整的 13 个 Schema 字段。
- 仅 `username`、`flow_uuid`、`tenant_name` 按当前 Schema 标记为必填。
- `file` 字段能够选择真实文件。
- 后端捕获的目标请求同时包含普通 `data` 和 `files`。
- multipart Header 包含 HTTP 客户端生成的 boundary。
- JSON 接口调试、环境认证和敏感 Header 脱敏无回归。

## 规格来源

详细需求、场景和实施任务以以下 OpenSpec 文件为准：

- `openspec/changes/improve-api-endpoint-debug-request-body-editor/proposal.md`
- `openspec/changes/improve-api-endpoint-debug-request-body-editor/design.md`
- `openspec/changes/improve-api-endpoint-debug-request-body-editor/specs/api-endpoint-debug-request-body/spec.md`
- `openspec/changes/improve-api-endpoint-debug-request-body-editor/tasks.md`
