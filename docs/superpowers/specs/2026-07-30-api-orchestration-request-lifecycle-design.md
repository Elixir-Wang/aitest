# 接口编排请求生命周期设计

- 日期：2026-07-30
- 状态：设计已确认，待实现
- 范围：接口编排节点的请求配置、前置处理、响应处理、断言和执行控制

## 1. 目标

将接口编排节点统一设计为可执行请求单元，覆盖 Postman 常用的 Header、Body、前置和后置处理能力，同时保留现有接口资产、场景变量、响应提取和断言能力。

本次只解决请求生命周期和节点配置结构，不重做画布、场景版本、运行中心等无关模块。

## 2. 设计原则

1. 接口资产提供默认定义，场景节点保存实际执行配置。
2. 配置按照请求生命周期组织，不继续堆叠平级配置项。
3. 所有参数值统一支持固定值、环境变量、场景变量、前置步骤输出、密钥和动态表达式。
4. Body 默认使用接口 Schema 表单，复杂场景允许切换 JSON 或原始文本编辑。
5. 前置处理负责准备数据，响应处理负责提取和转换数据，断言只负责判断结果。
6. 配置必须可以静态检查，运行结果必须可以解释失败原因。

## 3. 页面结构

保留现有三栏布局：

```text
左侧：节点工具箱
中间：画布 / 列表
右侧：当前节点配置
```

右侧配置固定为五个主 Tab：

```text
请求 | 前置处理 | 响应处理 | 断言 | 执行控制
```

节点头部展示：

- HTTP 方法、节点名称和请求路径。
- 接口资产及资产版本。
- 节点配置状态。
- 查看接口资产、单独运行、复制、禁用和删除操作。

画布节点只展示摘要：

```text
POST 创建订单
/api/orders
✓ 输入数量  ✓ 输出数量  ✓ 断言数量
```

## 4. 请求配置

### 4.1 配置分组

请求 Tab 包含：

```text
URL / Params
Authorization
Headers
Body
Cookies
```

### 4.2 Params

Path 和 Query 参数使用表格编辑。每一行包含：

- 参数名
- 参数值
- 值来源
- 启用状态
- 删除操作

允许覆盖接口资产参数，也允许添加接口资产未声明的 Query 参数。

### 4.3 Authorization

支持：

- 无鉴权
- Bearer Token
- Basic Auth
- API Key
- 继承环境鉴权
- 使用接口资产默认鉴权

鉴权配置独立于普通 Header，最终请求组装时生成对应 Header。

### 4.4 Headers

Header 使用可编辑表格，每行包含：

- 启用状态
- Key
- Value
- 值来源
- 敏感字段标记
- 删除操作

支持添加接口资产未声明的 Header。当前节点配置优先级高于接口资产、环境和项目默认 Header。

### 4.5 Body

支持以下类型：

```text
None
JSON
Form URL Encoded
Multipart Form
Raw Text
Binary
```

JSON 默认使用 Schema 表单，并支持切换 JSON 编辑模式。JSON 编辑模式必须支持格式化、语法校验和变量高亮。

变量替换必须保留字段类型。例如数字和布尔值不得被错误转换为字符串。

### 4.6 Cookies

Cookies 使用与 Headers 相同的表格模型，支持固定值和变量引用。

## 5. 前置处理

前置处理 Tab 仅包含两种能力：

### 5.1 变量动作

支持设置、覆盖和删除变量，并支持动态值生成。

首期动态能力包含：

- UUID
- 当前时间戳
- 日期格式化
- 随机整数
- 环境变量读取

### 5.2 前置脚本

脚本用于签名、复杂参数计算和动态请求准备。脚本只能访问受控上下文：

```text
env
scenario
step
request
variables
setVariable()
getVariable()
deleteVariable()
log()
```

脚本执行必须具备语法检查、超时限制、错误行定位和日志输出。不允许访问文件系统、操作系统命令或任意外部模块。

## 6. 响应处理

### 6.1 响应提取

响应提取规则包含：

- 输出变量名
- 来源
- 表达式
- 是否必填

来源支持：

```text
状态码
响应 Header
响应 Body
响应时间
响应 Cookie
```

表达式首期支持 JSONPath、正则表达式和 Header Key。

输出变量使用稳定的步骤 ID 保存，界面展示为：

```text
步骤名称.变量名
```

### 6.2 后置脚本

后置脚本用于复杂响应转换和变量计算，脚本上下文额外提供：

```text
response
```

后置脚本在响应提取之后执行，脚本异常进入节点错误信息，并根据失败策略决定是否继续场景。

## 7. 断言

断言使用规则行配置：

```text
来源 + 表达式 + 运算符 + 期望值 + 严重级别
```

首期来源支持：

- 状态码
- 响应 Header
- 响应 Body
- 响应时间

首期运算符支持：

- 等于
- 不等于
- 包含
- 存在
- 大于
- 小于
- 匹配正则
- JSON Schema 校验

严重级别支持：

```text
失败
警告
```

断言失败必须记录实际值、期望值和定位信息。

## 8. 执行控制

执行控制 Tab 仅包含：

- 是否启用
- 执行条件
- 超时时间
- 重试次数
- 重试间隔
- 失败策略

失败策略支持：

```text
停止场景
继续执行
标记失败但继续
```

## 9. 值来源模型

参数值不能只保存模板字符串，必须保存结构化来源：

```typescript
type ValueSource =
  | { type: "literal"; value: unknown }
  | { type: "environment"; name: string }
  | { type: "scenario"; name: string }
  | { type: "step_output"; stepId: string; outputName: string }
  | { type: "secret"; name: string }
  | { type: "dynamic"; expression: string }
  | { type: "expression"; expression: string };
```

结构化来源用于变量校验、引用跳转、依赖分析和步骤改名保护。界面可以继续展示为 `{{登录.token}}`。

## 10. 节点数据模型

```typescript
type ApiScenarioStep = {
  id: string;
  name: string;
  type: "request" | "condition" | "wait" | "loop";
  enabled: boolean;

  request: {
    endpointAssetId: string;
    endpointVersion?: string;
    method: string;
    url: string;
    pathParams: RequestField[];
    queryParams: RequestField[];
    authorization?: AuthorizationConfig;
    headers: HeaderField[];
    cookies: RequestField[];
    body?: BodyConfig;
  };

  preRequest?: {
    actions: VariableAction[];
    script?: ScriptConfig;
  };

  responseProcessing?: {
    extractors: ResponseExtractor[];
    script?: ScriptConfig;
  };

  assertions: Assertion[];

  execution: {
    condition?: Expression;
    timeoutMs: number;
    retryCount: number;
    retryIntervalMs: number;
    failurePolicy: "stop" | "continue" | "fail_and_continue";
  };
};
```

## 11. 运行时顺序

运行时必须严格按照以下顺序执行：

```text
加载环境、场景和前序步骤变量
→ 执行前置变量动作
→ 执行前置脚本
→ 解析 URL、Params、Authorization、Headers、Body、Cookies
→ 发送请求
→ 保存脱敏后的响应快照
→ 执行响应提取
→ 执行后置脚本
→ 执行断言
→ 根据执行控制决定下一步
```

运行记录至少包含：

- 最终请求摘要
- 脱敏后的响应摘要
- 提取变量
- 断言结果
- 脚本日志
- 错误信息
- 耗时

敏感字段必须脱敏展示和持久化。

## 12. 配置校验

阻断错误：

- 必填参数为空。
- Body 无法解析。
- 变量引用不存在。
- 输出变量重名。
- 断言表达式无效。
- 脚本语法错误。
- 接口资产不存在。

警告：

- 没有断言。
- 使用敏感字段但未标记。
- 当前节点覆盖了环境或资产 Header。
- 节点没有响应提取。

点击检查结果必须定位到具体节点、Tab 和字段。

## 13. 实施边界

首期实现：

1. 请求配置重构。
2. Header 表格编辑。
3. Body 多模式编辑。
4. 前置变量动作和脚本入口。
5. 响应提取和后置脚本入口。
6. 结构化变量引用。
7. 单节点运行和请求预览。
8. 配置静态校验。

首期不实现：

- Postman 全量兼容。
- 新的流程节点类型。
- 多人实时协作。
- 插件系统。
- 模板市场。

## 14. 验收标准

- 用户可以在一个节点中配置 URL、Header、Body、鉴权和 Cookies。
- 用户可以通过变量选择器引用环境变量、场景变量和前序步骤输出。
- 用户可以配置前置动作、前置脚本、响应提取和后置脚本。
- 用户可以配置状态码、Header、Body 和响应时间断言。
- 用户可以单独运行节点并查看脱敏后的最终请求、响应和断言结果。
- 配置检查可以阻止无效 JSON、未定义变量和脚本语法错误。
- 接口资产更新不会静默覆盖场景节点配置。
- 现有画布、场景变量、版本和运行能力保持兼容。
