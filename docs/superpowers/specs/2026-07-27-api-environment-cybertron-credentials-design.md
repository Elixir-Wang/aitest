# 接口环境塞伯坦凭据编辑设计

## 背景

接口环境使用“塞伯坦智能体”鉴权时，当前前端要求填写 `cybertron-robot-key`、`cybertron-robot-token` 和 `username`。编辑环境时，后端只返回凭据已保存标记，前端无法查看或直接编辑原值。

## 目标

- `cybertron-robot-key`、`cybertron-robot-token`、`username` 均为可选字段。
- 接口环境列表接口返回已解密的 `cybertron-robot-key` 和 `cybertron-robot-token`。
- 编辑环境时回填三个字段。
- key/token 默认隐藏，可通过输入框右侧的小眼睛切换明文显示。
- 保存空 key/token 时清除原有凭据，不保留旧值。

## 后端设计

### 返回模型

`ApiEnvironmentOut.auth_config` 保持现有结构，并在塞伯坦鉴权环境中返回：

- `cybertron_robot_key`: 解密后的字符串，未配置时为空字符串。
- `cybertron_robot_token`: 解密后的字符串，未配置时为空字符串。
- `username`: 字符串，未配置时为空字符串。

现有 `cybertron_robot_key_saved` 和 `cybertron_robot_token_saved` 标记可保留，以避免影响其他调用方。

### 保存语义

创建和更新均接受三个字段为空。更新时以请求值为准：

- 非空 key/token：加密后写入。
- 空 key/token：清空对应的加密存储值。
- 空 username：保存为空字符串。

### 权限与风险

沿用现有列表接口权限，不新增详情接口。因此具备接口环境列表查看权限的用户可以从浏览器网络响应中读取明文 key/token。这是已确认的方案边界。

## 前端设计

### 校验

移除塞伯坦鉴权对 key、token、username 的必填校验。环境名称、API Base URL、超时时间及 JSON 格式校验保持不变。

### 编辑回填

`formFromEnvironment` 从 `auth_config` 读取并回填：

- `cybertron_robot_key`
- `cybertron_robot_token`
- `username`

### 可见性切换

扩展现有文本字段组件，为密码类型字段提供可选的显示/隐藏按钮。仅 key/token 启用该能力，默认使用 `password` 类型；点击小眼睛后切换为 `text`，再次点击恢复隐藏，并提供可访问性标签。

## 验证

- 后端测试列表序列化返回解密后的 key/token。
- 后端测试更新为空时会清除原 key/token。
- 后端测试三个字段为空时可以创建和更新。
- 前端静态检查或测试验证编辑映射回填三个字段。
- 前端构建或类型检查验证小眼睛组件与页面类型正确。

## 非目标

- 不改变账号密码鉴权的必填规则。
- 不新增凭据详情接口。
- 不调整接口环境列表权限。
- 不改变运行日志、报告等位置的敏感字段脱敏规则。
