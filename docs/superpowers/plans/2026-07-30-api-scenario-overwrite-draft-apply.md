# API 场景 AI 计划覆盖草稿实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“应用到草稿”改为用户确认后的完整覆盖操作，不再因场景 revision、更新时间或草稿 hash 变化阻断应用。

**Architecture:** AI 计划仍保持 preview、过期和服务端结构校验。应用接口只验证权限、计划状态、过期时间、确认语义和计划有效性，然后使用计划节点完整替换当前场景草稿步骤。草稿变化信息可以保留为审计数据，但不参与应用决策。

**Tech Stack:** FastAPI、Pydantic、SQLite、React/TypeScript、Node test、pytest。

## Global Constraints

- “应用到草稿”表示完整覆盖，不进行自动合并。
- 不检查 `scenario.revision`、`scenario_updated_at` 或 `scenario_draft_hash`。
- 继续阻止不存在、过期、已处理和服务端校验失败的计划。
- 应用失败时不得留下部分步骤。
- 不修改与接口场景编排无关的现有未提交文件。

---

### Task 1: 收紧覆盖草稿请求契约

**Files:**
- Modify: `apps/backend/app/schemas/api_automation.py:487`
- Modify: `apps/frontend/src/lib/api-client.ts:2236`
- Test: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Consumes: `plan_id` URL 参数和 `scenario_id` 请求字段。
- Produces: `ApiScenarioAiPlanApplyIn(scenario_id, confirmation="overwrite_draft")`。

- [ ] **Step 1: 写失败测试，证明应用请求不再需要 expected_revision**

```python
def test_ai_plan_apply_payload_uses_explicit_overwrite_confirmation() -> None:
    payload = ApiScenarioAiPlanApplyIn(
        scenario_id="apiscn-1",
        confirmation="overwrite_draft",
    )
    assert payload.scenario_id == "apiscn-1"
    assert payload.confirmation == "overwrite_draft"
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `rtk pytest -q tests/test_api_scenario_ai_orchestration.py -k overwrite_confirmation`

Expected: FAIL，因为当前模型仍要求 `expected_revision`。

- [ ] **Step 3: 修改后端请求模型**

```python
class ApiScenarioAiPlanApplyIn(_StrippedModel):
    scenario_id: str = Field(min_length=1, max_length=100)
    confirmation: Literal["overwrite_draft"]
```

- [ ] **Step 4: 修改前端请求类型**

```typescript
payload: {
  scenario_id: string;
  confirmation: "overwrite_draft";
}
```

- [ ] **Step 5: 运行模型和前端契约测试**

Run: `rtk pytest -q tests/test_api_scenario_ai_orchestration.py -k overwrite_confirmation`

Run: `rtk node --test tests/api-scenario-model.test.mjs`

Expected: 全部 PASS。

### Task 2: 将应用行为改为无冲突完整覆盖

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py:2505`
- Test: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Consumes: 已持久化且有效的 preview plan。
- Produces: 当前场景草稿，其步骤完整等于 AI 计划节点转换结果。

- [ ] **Step 1: 写失败测试，生成计划后修改场景名称仍可应用**

```python
with connect() as db:
    db.execute(
        "UPDATE api_scenarios SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        ("用户修改后的名称", scenario_id),
    )

applied = service.apply_api_scenario_ai_plan(
    "project-1",
    plan["plan_id"],
    ApiScenarioAiPlanApplyIn(
        scenario_id=scenario_id,
        confirmation="overwrite_draft",
    ),
    ACTOR,
)

assert applied["steps"]
```

- [ ] **Step 2: 写失败测试，生成计划后增加草稿步骤仍被计划完整覆盖**

```python
service.create_api_scenario_step(
    "project-1",
    scenario_id,
    ApiScenarioStepIn(
        step_type="api_request",
        endpoint_id="apiend-1",
        name="用户临时步骤",
    ),
    ACTOR,
)

applied = service.apply_api_scenario_ai_plan(...)

assert [step["id"] for step in applied["steps"]] == [node["id"] for node in plan["nodes"]]
```

- [ ] **Step 3: 运行测试确认 RED**

Run: `rtk pytest -q tests/test_api_scenario_ai_orchestration.py -k "changed_name or overwrite_changed_steps"`

Expected: 当前实现返回 `API_SCENARIO_REVISION_CONFLICT` 或 `API_SCENARIO_DRAFT_CONFLICT`。

- [ ] **Step 4: 删除 revision 和草稿指纹阻断逻辑**

从 `apply_api_scenario_ai_plan` 删除：

```python
if int(scenario["revision"]) != payload.expected_revision:
    ...

if (
    request_data.get("scenario_updated_at") != scenario["updated_at"]
    or request_data.get("scenario_draft_hash") != _scenario_draft_hash(db, scenario)
):
    ...

if plan.get("expected_revision") != payload.expected_revision:
    ...
```

保留：

```python
if not plan.get("validation", {}).get("valid"):
    raise api_error(409, "API_SCENARIO_AI_PLAN_INVALID", "AI 编排计划未通过服务端校验。")
```

- [ ] **Step 5: 验证当前场景步骤被完整替换**

Run: `rtk pytest -q tests/test_api_scenario_ai_orchestration.py -k "changed_name or overwrite_changed_steps"`

Expected: PASS，并且应用结果中不存在用户临时步骤。

### Task 3: 保留必要安全门槛

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py:2505`
- Test: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Consumes: plan 状态、过期时间和 validation。
- Produces: 明确且稳定的错误码。

- [ ] **Step 1: 补充参数化测试**

```python
@pytest.mark.parametrize(
    ("condition", "error_code"),
    [
        ("expired", "API_SCENARIO_AI_PLAN_EXPIRED"),
        ("applied", "API_SCENARIO_AI_PLAN_NOT_APPLICABLE"),
        ("invalid", "API_SCENARIO_AI_PLAN_INVALID"),
    ],
)
def test_overwrite_draft_keeps_plan_safety_gates(condition, error_code):
    ...
```

- [ ] **Step 2: 运行测试确认现有安全门槛仍通过**

Run: `rtk pytest -q tests/test_api_scenario_ai_orchestration.py -k overwrite_draft_keeps_plan_safety_gates`

Expected: PASS。

- [ ] **Step 3: 确认应用仍通过现有步骤准备逻辑验证 endpoint 和 Binding**

保持调用：

```python
steps = [_ai_plan_node_to_step(node, index) for index, node in enumerate(plan.get("nodes", []))]
result = replace_api_scenario_steps(
    project_id,
    payload.scenario_id,
    ApiScenarioStepsReplaceIn(steps=steps),
    actor,
)
```

不得绕过 `_prepare_scenario_step` 或接口资产归属校验。

### Task 4: 更新前端应用语义

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/api-automation/use-api-scenario-editor.ts:404`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`
- Modify: `apps/frontend/src/lib/api-client.ts:2236`
- Test: `apps/frontend/tests/api-scenario-ai-generation-drawer-contract.test.mjs`

**Interfaces:**
- Consumes: 当前 AI preview plan。
- Produces: 显式覆盖请求和用户可理解的覆盖提示。

- [ ] **Step 1: 写失败契约测试**

```javascript
assert.match(source, /confirmation:\s*"overwrite_draft"/);
assert.doesNotMatch(source, /expected_revision:\s*aiPlan\.expected_revision/);
assert.match(drawerSource, /覆盖当前草稿/);
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `rtk node --test tests/api-scenario-ai-generation-drawer-contract.test.mjs`

Expected: FAIL，当前仍提交 `expected_revision` 和 `apply_preview`。

- [ ] **Step 3: 修改应用请求**

```typescript
async function applyAiPlan() {
  if (!aiPlan || !scenario) return;
  const applied = await applyApiScenarioAiPlan(projectId, aiPlan.plan_id, {
    scenario_id: scenario.id,
    confirmation: "overwrite_draft",
  });
  ...
}
```

- [ ] **Step 4: 更新按钮和确认提示**

按钮文案：

```text
覆盖当前草稿
```

提示文案：

```text
应用后将使用 AI 编排结果完整替换当前草稿步骤，当前草稿中的步骤修改不会保留。
```

- [ ] **Step 5: 运行前端测试与 lint**

Run: `rtk node --test tests/api-scenario-ai-generation-drawer-contract.test.mjs tests/api-scenario-model.test.mjs`

Run: `rtk npm run lint -- src/lib/api-client.ts src/components/ai-testing/api-automation/use-api-scenario-editor.ts src/components/ai-testing/api-automation/api-scenario-editor.tsx`

Expected: 测试 PASS；lint 无新增 error。

### Task 5: 完整回归验证

**Files:**
- Verify only.

**Interfaces:**
- Consumes: 完成后的后端和前端实现。
- Produces: 可发布的覆盖草稿行为。

- [ ] **Step 1: 运行后端编排专项测试**

Run: `rtk pytest -q tests/test_api_scenario_ai_orchestration.py tests/test_api_automation_scenario_runtime.py tests/test_api_automation_scenarios_tasks.py`

Expected: 全部 PASS。

- [ ] **Step 2: 运行前端场景专项测试**

Run: `rtk node --test tests/api-scenario-ai-generation-drawer-contract.test.mjs tests/api-scenario-model.test.mjs`

Expected: 全部 PASS。

- [ ] **Step 3: 手工验收**

1. 生成 AI 编排计划。
2. 在草稿中新增或调整一个步骤。
3. 点击“覆盖当前草稿”。
4. 确认应用成功，没有 revision/hash 冲突提示。
5. 确认草稿步骤完整等于 AI 计划步骤。
6. 再次应用同一计划，确认仍提示计划已处理。

## Self-Review

- 覆盖了后端请求模型、应用逻辑、前端请求、用户提示和回归测试。
- 不包含自动合并、冲突解决或历史恢复等超出需求的能力。
- `overwrite_draft` 在后端和前端保持同一命名。
- 保留过期、状态和计划有效性检查。
