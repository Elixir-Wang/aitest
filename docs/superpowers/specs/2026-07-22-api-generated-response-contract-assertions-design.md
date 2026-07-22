# API 新生成用例响应契约断言设计

## 1. 背景

当前接口自动化用例生成链路已经完整保存 OpenAPI 响应定义，包括 HTTP 状态码、媒体类型、响应 Schema、字段描述和示例值。

但是，新生成用例的断言主要由模型自由生成。后端测试点规划器只确定测试点和 `oracle_status`，落库校验只检查测试点、请求方法、请求路径和已审批 Oracle，并未检查成功响应字段是否被断言。

因此，即使接口文档明确声明了以下响应结构，新生成用例仍可能只包含 `status_code`：

```json
{
  "code": "000000",
  "message": "ok",
  "data": {
    "user_cnt": 123,
    "question_cnt": 123
  }
}
```

这会导致测试只能发现 HTTP 状态异常，无法发现响应字段删除、重命名、层级变化或固定业务码错误。

## 2. 设计决策

新增一个由后端控制的“响应契约断言编译”阶段。

后端根据接口响应定义确定性生成每条新用例必须具备的最低断言集合。模型继续负责构造请求、生成测试说明以及补充业务断言，但不得删除、覆盖或弱化后端生成的契约断言。

最终断言由以下两部分组成：

```text
后端响应契约断言 + 模型补充断言
```

后端负责合并、去重、冲突检查和最终完整性校验。

## 3. 目标

- 新生成的成功用例不得只断言 HTTP 状态码。
- OpenAPI 已声明的 JSON 响应字段必须具有存在性断言。
- 文档明确且稳定的固定响应值必须具有等值断言。
- 精确业务值未知时允许使用存在性断言，不得因无法确定值而省略字段断言。
- `needs_confirmation` 只表示业务预期仍需确认，不得豁免已明确的响应契约。
- 二进制和非 JSON 响应使用适合其媒体类型的断言，不错误生成 JSONPath。
- 生成结果缺少最低契约断言时不得落库。
- 所有新增断言必须能够被生成的 pytest 执行器实际执行。

## 4. 非目标

- 不扫描、迁移或修改历史接口用例。
- 不为历史用例自动补齐响应断言。
- 不修改历史用例的 `oracle_status`。
- 不根据字段名称创造业务规则。
- 不把 OpenAPI 示例中的所有值都视为稳定等值契约。
- 不对时间戳、随机 ID、Token、动态 URL 或其他动态值生成固定等值断言。
- 不在本变更中实现完整 JSON Schema Validator。
- 不执行真实接口请求来推断响应结构。
- 不改变现有 Oracle 观察、提案和审批流程。

## 5. 适用范围

本规则只应用于本变更发布后创建的新接口自动化用例。

适用入口包括：

- 新建接口用例生成任务。
- 对指定接口重新发起并创建新用例的生成任务。
- 生成任务失败后重新执行且最终创建新用例的任务。

不适用于：

- 已经存在于 `api_test_cases` 的历史记录。
- 用户手工编辑但未重新生成的历史用例。
- 仅重新生成 pytest 脚本、不创建新用例的任务。
- Oracle 提案审批后对历史用例的更新。

如果现有生成流程在重新生成时采用“删除旧记录并创建新记录”的语义，则新创建的记录按新规则处理；系统不额外识别或迁移被替换的历史记录。

## 6. 事实等级

响应断言按照事实可靠性分为三层。

### 6.1 文档明确事实

必须生成，不允许模型删除：

- 明确声明的 HTTP 成功状态码。
- 明确声明的响应媒体类型。
- JSON Schema 中声明的响应字段路径。
- Schema 中通过 `const` 声明的固定值。
- 单值 `enum` 声明的固定值。
- 平台能够可靠识别的固定业务成功码。

### 6.2 Schema 可推导事实

默认生成结构断言：

- 对象属性存在。
- 嵌套对象属性存在。
- 数组字段存在。
- 明确声明的非空响应体。

本阶段不生成通用字段类型断言，因为当前 `ApiAssertion` 和 pytest 执行器没有字段类型断言类型。字段类型断言可作为后续独立增强，不阻塞本设计。

### 6.3 业务推断

允许模型补充，但必须标记推断来源：

- 文档未声明的错误状态码。
- 负向场景的业务错误码。
- 字段间业务关系。
- 数值范围和统计口径。
- 依赖特定测试数据的响应值。

业务推断不得替代或删除文档明确事实。

## 7. 响应选择规则

### 7.1 成功用例

成功用例根据其 `status_code` 断言选择对应的 OpenAPI response。

优先级如下：

1. 与用例 `status_code` 完全一致的响应定义。
2. 对应状态码范围定义，例如 `2XX`。
3. `default` 响应。

如果模型没有生成 `status_code`，后端从接口已声明的成功响应中选择：

1. 最小的显式 `2xx` 状态码。
2. `2XX` 范围响应。

后端随后补充对应的 `status_code` 断言。

如果接口没有声明任何成功响应，则生成任务失败并返回明确错误，不通过猜测创建成功契约。

### 7.2 负向、边界和安全用例

负向、边界和安全用例只使用与其预期状态码匹配的响应定义生成字段断言。

如果预期状态码是推断值且 OpenAPI 中不存在对应响应定义：

- 保留允许的推断 `status_code`；
- 不套用成功响应字段；
- 不虚构错误响应字段；
- 在 `generation_notes` 中记录待确认项。

如果错误响应 Schema 已明确，则同样生成错误响应字段存在性断言。

## 8. JSON 响应契约编译

### 8.1 基本规则

对于 `application/json` 以及以 `+json` 结尾的媒体类型：

- 生成 `content_type` 断言。
- 递归遍历响应 Schema 的 `properties`。
- 为每个声明的字段生成 `jsonpath_exists`。
- 为文档明确且稳定的固定值生成 `jsonpath_equals`。
- 对父对象和叶子字段都生成存在性断言。

示例 Schema：

```json
{
  "type": "object",
  "properties": {
    "code": {"type": "string", "example": "000000"},
    "message": {"type": "string"},
    "data": {
      "type": "object",
      "properties": {
        "user_cnt": {"type": "number"}
      }
    }
  }
}
```

最低断言：

```json
[
  {"type": "status_code", "path": "", "expected": 200},
  {"type": "content_type", "path": "", "expected": "application/json"},
  {"type": "jsonpath_exists", "path": "$.code", "expected": true},
  {"type": "jsonpath_exists", "path": "$.message", "expected": true},
  {"type": "jsonpath_exists", "path": "$.data", "expected": true},
  {"type": "jsonpath_exists", "path": "$.data.user_cnt", "expected": true}
]
```

### 8.2 字段是否 required

本设计采用“契约声明字段必须断言存在”的产品规则，而不是只处理 JSON Schema `required` 字段。

原因是接口文档页面已经将 `properties` 展示为响应字段清单，用户期望生成用例验证这些字段没有缺失。即使 OpenAPI 源未正确填写 `required`，字段也不得被生成器静默忽略。

因此：

- `properties` 中声明的字段均生成 `jsonpath_exists`。
- `required` 暂不改变存在性断言生成范围。
- 若未来需要区分必填字段和可选字段，应通过新的策略配置实现，不改变本次默认规则。

### 8.3 固定值识别

以下情况允许生成 `jsonpath_equals`：

- Schema 使用 `const`。
- Schema 使用仅包含一个值的 `enum`。
- 字段描述明确说明一个固定值表示成功，并且示例与描述一致。

例如：

```text
字段：code
描述：返回码，"000000" 表示成功
示例："000000"
```

成功用例生成：

```json
{"type": "jsonpath_equals", "path": "$.code", "expected": "000000"}
```

普通 `example`、`examples` 不能单独作为固定值依据。例如统计数量 `123` 只用于展示，不生成等值断言。

固定值识别必须由确定性规则完成，不调用模型二次判断。

### 8.4 动态字段

以下字段即使存在示例，也不得仅依据示例生成固定等值断言：

- 时间和日期。
- UUID、流水号和随机 ID。
- Token、Cookie、验证码和临时凭据。
- 文件 URL、下载地址和签名 URL。
- 请求相关的回显值。
- 统计数量、比例和计算结果。

动态字段仍生成 `jsonpath_exists`。

### 8.5 数组

对于数组字段：

- 为数组字段本身生成 `jsonpath_exists`。
- 默认不生成首元素路径，例如 `$.data.items[0].id`。
- 默认不要求数组非空。
- 只有 Schema 明确声明 `minItems >= 1` 时，才允许补充 `body_not_empty`。

本设计不对数组每个元素执行完整 Schema 校验。

### 8.6 additionalProperties

如果对象只有 `additionalProperties` 而没有明确 `properties`：

- 只断言该对象字段存在。
- 不虚构具体子字段。

### 8.7 组合 Schema

对于 `allOf`：

- 合并所有可确定的对象属性后生成断言。

对于 `oneOf` 和 `anyOf`：

- 只生成各分支共同存在且定义一致的字段断言。
- 不选择任意一个分支作为唯一真实结构。
- 无共同字段时只保留状态码、媒体类型和父级响应体断言。

### 8.8 `$ref`

优先复用 OpenAPI 导入阶段已经解析或展开的 Schema。

如果生成阶段仍收到无法解析的 `$ref`：

- 不静默跳过。
- 生成任务失败并指出无法解析的引用路径。
- 不通过模型猜测引用内容。

## 9. 非 JSON 响应

### 9.1 二进制下载

对于 `application/octet-stream`、文件下载和 `format: binary`：

- 生成 `status_code`。
- 生成 `content_type`。
- 生成 `body_not_empty`。
- 文档明确下载文件名响应头时，可生成 `header_exists` 或 `header_equals`。
- 禁止生成 JSONPath 断言。

### 9.2 文本和其他媒体类型

对于 `text/*`：

- 生成 `status_code`。
- 生成 `content_type`。
- 文档声明响应非空时生成 `body_not_empty`。

对于无法识别的媒体类型：

- 生成 `status_code`。
- 生成 `content_type`。
- 不猜测响应体结构。

## 10. 断言合并规则

### 10.1 合并顺序

```text
编译后端最低契约断言
→ 读取模型生成断言
→ 标准化
→ 去重
→ 冲突检测
→ 完整性校验
→ 落库
```

### 10.2 唯一键

断言使用以下逻辑键去重：

```text
type + normalized path
```

无路径断言使用空路径。

### 10.3 冲突处理

- 模型缺少后端断言：后端自动补齐。
- 模型生成相同断言：去重。
- 模型把存在性断言升级为文档明确的正确等值断言：保留等值断言，同时保留或省略同路径存在断言均可，由标准化逻辑统一处理。
- 模型给出与文档明确固定值冲突的等值断言：生成任务失败。
- 模型给出与目标响应不一致的状态码：生成任务失败。
- 模型对非 JSON 响应生成 JSONPath：生成任务失败。

后端不得通过静默覆盖冲突值掩盖模型错误。

## 11. `oracle_status` 语义

### 11.1 `confirmed`

表示断言来自明确接口契约或已审批 Oracle。

必须执行全部后端契约断言和审批断言。

### 11.2 `inferred`

表示部分业务预期来自合理推断。

必须执行：

- 所有文档明确的契约断言。
- 模型生成且通过冲突检查的推断断言。

推断依据必须写入 `generation_notes`。

### 11.3 `needs_confirmation`

表示未知业务结果进入观察模式，但不表示“完全无断言”。

仍必须执行：

- 请求构造和网络错误检查。
- 文档明确的 HTTP 状态码；如果状态码本身未知，则不强制推断状态码。
- 与已选择响应定义对应的媒体类型。
- 已明确响应 Schema 的字段存在性断言。
- 已明确的固定业务值。

只有缺少事实依据的业务等值断言可以暂不生成。

## 12. 生成链路

新生成用例的数据流调整为：

```text
OpenAPI 导入结果
→ 后端测试点规划
→ 为测试点选择目标响应
→ 编译最低响应契约断言
→ 将 endpoint、测试点和最低断言提供给模型
→ 模型生成请求和补充断言
→ 后端合并与冲突检查
→ 后端完整性校验
→ 新用例落库
```

最低契约断言应加入 `planned_test_points`，作为模型可见的只读事实。例如：

```json
{
  "key": "success.minimum_valid",
  "oracle_status": "confirmed",
  "required_assertions": [
    {"type": "status_code", "path": "", "expected": 200},
    {"type": "jsonpath_equals", "path": "$.code", "expected": "000000"},
    {"type": "jsonpath_exists", "path": "$.data.user_cnt", "expected": true}
  ]
}
```

`required_assertions` 与现有已审批 Oracle 的 `assertions` 分开：

- `required_assertions` 来自当前接口文档，可由接口文档变化重新计算。
- `assertions` 来自已审批 Oracle，必须原样保持。

## 13. 后端组件设计

新增模块：

```text
apps/backend/app/agents/api_automation/case_generation/response_contract.py
```

建议公开以下接口：

```python
compile_response_contract(
    endpoint: dict[str, Any],
    *,
    expected_status_code: int | None,
    coverage: str,
) -> list[ApiAssertion]
```

模块职责：

- 选择目标 response。
- 选择目标媒体类型。
- 编译状态码和媒体类型断言。
- 递归编译 JSON 字段断言。
- 识别确定性固定值。
- 处理数组、组合 Schema 和二进制响应。
- 标准化并去重断言。

模块不得负责：

- 构造请求数据。
- 判断业务测试点。
- 访问数据库。
- 调用模型。
- 修改历史用例。

## 14. 现有组件修改

### 14.1 测试点输入构建

修改：

```text
apps/backend/app/services/api_automation/service.py
```

在 `_build_generation_item_input()` 中：

- 继续调用 `plan_api_test_points()`。
- 为每个测试点计算 `required_assertions`。
- 已审批 Oracle 继续使用现有 `assertions` 和 `oracle_fact`。
- 把两类断言同时传给模型。

### 14.2 生成结果校验

修改：

```text
apps/backend/app/agents/api_automation/case_generation/validation.py
```

增加：

- 合并后断言必须覆盖全部 `required_assertions`。
- 报错必须列出缺失路径和断言类型。
- 检查状态码冲突。
- 检查固定值冲突。
- 检查媒体类型与 JSONPath 的兼容性。
- 已审批 Oracle 仍执行现有完全一致校验。

### 14.3 落库前标准化

修改：

```text
apps/backend/app/services/api_automation/service.py
```

在 `_persist_generation_item_cases()` 严格校验前：

- 将 `required_assertions` 合并到模型断言。
- 执行断言标准化和去重。
- 将合并后的最终断言保存到 `assertions_json`。

数据库结构不需要修改。

### 14.4 生成规则

修改：

```text
apps/backend/app/agents/api_automation/case_generation/skills/api-automation-case-generation/SKILL.md
apps/backend/app/agents/api_automation/case_generation/skills/api-automation-case-generation/references/assertion-guidelines.md
```

将“可以补充响应字段断言”改为“必须保留后端提供的最低契约断言”。

模型必须理解：

- `required_assertions` 是只读事实。
- 不确定具体值时使用存在性断言，不得删除字段断言。
- 可以新增断言，但不能修改后端断言。

### 14.5 pytest 执行器

确认并补齐生成 suite 中的公共断言工具：

```text
utils/assertions.py
utils/assert_utils.py
```

必须支持：

- `status_code`
- `content_type`
- `jsonpath_exists`
- `jsonpath_equals`
- `header_exists`
- `header_equals`
- `body_not_empty`
- `body_sha256`

JSONPath 执行失败信息必须包含：

- 用例 ID。
- 断言类型。
- JSONPath。
- 期望值。
- 实际值或字段缺失信息。

脚本生成后的 `pytest --collect-only` 仍不得发送真实接口请求。

## 15. 错误处理

新增或复用明确错误类型：

```text
API_RESPONSE_CONTRACT_NOT_FOUND
API_RESPONSE_SCHEMA_REF_UNRESOLVED
API_RESPONSE_ASSERTION_CONFLICT
API_RESPONSE_ASSERTION_INCOMPLETE
API_RESPONSE_ASSERTION_MEDIA_TYPE_MISMATCH
```

错误信息示例：

```text
测试点 success.minimum_valid 缺少响应契约断言：
jsonpath_exists $.data.normal_answer_rate
```

```text
测试点 success.minimum_valid 的 $.code 断言与接口文档冲突：
文档期望 "000000"，模型生成 "0"
```

生成子任务发生上述错误时必须原子失败，不保存该接口的部分用例。

## 16. 测试策略

### 16.1 响应契约编译单元测试

覆盖：

- 顶层对象字段。
- 多层嵌套对象字段。
- Schema 未声明 `required` 但声明 `properties`。
- `const` 固定值。
- 单值 `enum`。
- 描述和示例共同确认的固定成功码。
- 普通示例不生成等值断言。
- 动态字段只生成存在性断言。
- 数组字段存在但不默认要求非空。
- `minItems >= 1` 数组。
- `additionalProperties`。
- `allOf` 合并。
- `oneOf` 和 `anyOf` 共同字段。
- JSON、`+json`、文本和二进制媒体类型。
- 无法解析的 `$ref`。

### 16.2 合并与校验单元测试

覆盖：

- 模型漏断言时后端自动补齐。
- 相同断言去重。
- 固定值冲突时拒绝。
- 状态码冲突时拒绝。
- 二进制响应包含 JSONPath 时拒绝。
- 已审批 Oracle 不允许被修改。
- `needs_confirmation` 仍保留明确字段断言。

### 16.3 服务集成测试

使用 `POST /openapi/v1/agent/analysis/` 等价 fixture，验证新生成成功用例至少包含：

```text
status_code 200
content_type application/json
$.code == "000000"
$.message exists
$.data exists
$.data.user_cnt exists
$.data.question_cnt exists
$.data.answer_cnt exists
$.data.useful_cnt exists
$.data.useless_cnt exists
$.data.user_per_question_cnt exists
$.data.normal_answer_rate exists
$.data.useful_rate exists
$.data.useless_rate exists
```

同时验证统计值示例 `123` 不会被生成为固定等值断言。

### 16.4 pytest 生成脚本测试

- canonical 数据文件保留最终合并后的断言。
- `jsonpath_exists` 能正确发现字段缺失。
- `jsonpath_equals` 能正确报告实际值。
- 非 JSON 响应不会调用 `response.json()`。
- observation mode 不跳过明确契约断言。
- `pytest --collect-only` 通过且不发送网络请求。

## 17. 验收标准

1. 新生成的 JSON 成功用例不会只包含 `status_code`。
2. OpenAPI response `properties` 中声明的所有字段都有 `jsonpath_exists`，除非其位于无法确定的 `oneOf` 或 `anyOf` 独占分支。
3. 文档明确的固定业务成功码生成 `jsonpath_equals`。
4. 普通示例值和动态值不生成固定等值断言。
5. `needs_confirmation` 用例不会删除文档明确的响应字段断言。
6. 模型遗漏断言时，后端能自动补齐。
7. 模型断言与明确契约冲突时，生成子任务原子失败。
8. 二进制响应不生成 JSONPath。
9. 生成的 pytest 能执行所有新增断言类型。
10. 历史用例和历史断言保持不变。
11. 不新增数据库迁移。
12. 相关后端测试和 pytest 脚本生成测试全部通过。

## 18. 建议实施顺序

1. 为响应契约编译器编写失败测试。
2. 实现 `response_contract.py`。
3. 在生成输入中加入 `required_assertions`。
4. 实现断言合并、去重和冲突检测。
5. 加强生成结果完整性校验。
6. 更新生成 Skill 和断言规范。
7. 补齐 pytest 公共断言工具。
8. 增加服务集成和脚本生成回归测试。
9. 运行接口自动化相关测试集。

## 19. 最终原则

```text
允许未知业务值暂不做等值断言，
但不允许 OpenAPI 已声明的响应字段没有契约断言。
```

后端负责保证最低质量，模型负责提供增量智能；新生成用例的响应断言完整性不得依赖模型是否自觉遵守提示词。
