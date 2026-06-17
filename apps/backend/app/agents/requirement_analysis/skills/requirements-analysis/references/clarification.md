# Requirement Clarification Reference

Use this reference after requirement understanding. The goal is to generate pending clarification content, not to solve the questions.

## Method 1: Reverse Use Case

For each affirmative requirement, generate reverse scenarios with "what if not", "who cannot", "when should not", and "what if it fails".

| Requirement Pattern | Reverse Scenario | Clarification Question Pattern |
|---|---|---|
| 用户可以... | 谁不能？什么时候不能？ | 未登录、权限不足、账号冻结时如何处理？ |
| 系统应... | 什么时候不应该？失败后呢？ | 触发条件、失败行为、恢复方式是什么？ |
| 支持...格式/类型 | 不支持的呢？ | 不支持格式如何提示？是否允许转换？ |
| ...后自动... | 什么条件下不自动？ | 依赖服务失败、超时、人工触发如何处理？ |
| 状态变为 X | 从哪些状态能变？哪些不能？ | 完整状态流转和冲突处理是什么？ |
| 通过后... | 不通过呢？ | 不通过状态、原因、重试或申诉规则是什么？ |
| 保存... | 不保存直接退出呢？ | 是否提示未保存？是否自动保存？ |
| 删除... | 误删了呢？ | 软删还是硬删？是否可恢复？ |
| 计算/生成... | 计算失败或超时呢？ | 是否有默认值、重试、错误提示？ |
| 发送通知... | 发送失败呢？ | 是否重试？失败是否可见？ |
| 导入/同步... | 部分成功或失败呢？ | 是否回滚？是否有失败明细？ |
| 查询/列表... | 无结果或超时呢？ | 空状态、分页、超时策略是什么？ |

## Method 2: Six-Dimension Scan

Scan every functional point with these six dimensions.

### 1. Trigger and Preconditions

Ask:

- Who can trigger it?
- When can it be triggered?
- What data, state, permission, or environment must already exist?

### 2. Boundaries and Constraints

Ask:

- Maximum and minimum quantity?
- Empty input allowed?
- Format, length, encoding, and file limits?
- Time limits, expiry, or timeout?
- Concurrent operation behavior?

### 3. Exceptions and Recovery

Ask:

- What happens after network failure, service failure, validation failure, or timeout?
- What exact feedback should the user receive?
- Can the user retry?
- Is partial success allowed?

### 4. State and Timing

Ask:

- Which states can enter this operation?
- Which states are produced by success, cancellation, rejection, timeout, or failure?
- Can the operation be reversed?
- What happens if the user exits midway?
- How are concurrent modifications resolved?

### 5. Permission and Isolation

Ask:

- Who can view, create, modify, delete, approve, export, or operate?
- Is data isolated by organization, tenant, project, or role?
- Do sensitive operations require confirmation or audit?

### 6. Data Lifecycle

Ask:

- What data is stored?
- How long is it retained?
- Is deletion logical or physical?
- Are history, versions, audit logs, or recovery needed?

## Merge and Prioritize

After generating questions:

1. Remove duplicates.
2. Merge similar questions under the same module or business object.
3. Prefer specific questions with impact over generic checklist wording.
4. Assign priority:
   - P0: Blocks scope, business rule, permission, state transition, data correctness, or implementation.
   - P1: Blocks consistent UX, exception handling, integration behavior, or testing.
   - P2: Improves completeness but can be decided during detailed design.
   - P3: Nice-to-have detail or future optimization.

## Output Format

Use this table:

| 优先级 | 模块/对象 | 澄清问题 | 影响 |
|---|---|---|---|

The `影响` column must explain why the question matters. Avoid writing only "需要确认".
