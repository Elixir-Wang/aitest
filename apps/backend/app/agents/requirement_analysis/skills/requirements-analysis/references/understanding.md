# Requirement Understanding Reference

Use this reference to convert raw requirements into a structured understanding. Record only what the source states or what can be safely inferred from it.

## Analysis Steps

### 1. Background

Identify:

- Why this requirement exists.
- Current pain points or operational problems.
- Business impact if the problem remains unsolved.
- Triggering event, policy, customer request, or product goal.

### 2. Goals and Value

Identify:

- Business goal.
- User value.
- System or operational value.
- Measurable outcome if the source provides one.

Do not create success metrics that the source does not provide. If a metric is useful but missing, add it to pending clarification.

### 3. Users and Scenarios

Identify:

- Primary users.
- Secondary users or affected roles.
- Main usage scenarios.
- Secondary or edge scenarios described by the source.

Use this format when useful:

| 用户角色 | 场景 | 用户目标 | 已知约束 |
|---|---|---|---|

### 4. Functional Scope

Split the scope into:

- Included capabilities.
- Explicitly excluded capabilities.
- Related existing capabilities affected by the requirement.

If exclusions are not stated, do not infer them. Add missing boundary definitions to pending clarification.

### 5. Business Flow

Describe the user and system flow from start to finish:

1. Entry point.
2. User action.
3. System processing.
4. User feedback.
5. Completion result.

For branches, describe the condition that creates the branch and the expected result.

### 6. State Transitions

Identify core business objects that change state, such as orders, tasks, requests, files, approvals, users, or jobs.

For each object, capture:

| 状态 | 触发条件 | 可执行操作 | 下一状态 |
|---|---|---|---|

If the requirement implies a state but does not define the full lifecycle, add pending clarification.

### 7. Business Rules

Extract rules from the source:

- Validation rules.
- Matching rules.
- Calculation rules.
- Permission rules.
- Limit rules.
- Conflict rules.
- Time rules.

Use this format:

| 规则类型 | 触发条件 | 判断逻辑 | 处理结果 |
|---|---|---|---|

### 8. Page and Interaction Understanding

Identify UI or interaction needs:

- Pages.
- Dialogs.
- Forms.
- Lists.
- Detail views.
- Confirmations.
- Feedback messages.
- Download or export actions.

Do not design full UX unless asked. Capture what the requirement implies.

### 9. Data and System Interaction

Identify:

- Input data.
- Output data.
- Stored data.
- Data sources.
- Data destinations.
- External systems or internal modules involved.

When APIs are not explicitly defined, describe required capabilities instead of inventing endpoint names.
