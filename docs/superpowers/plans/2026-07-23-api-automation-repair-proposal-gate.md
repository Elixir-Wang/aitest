# 接口自动化 AI 修复建议审批闸门 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有“先生成补丁再审批应用”改为“先审批结构化建议，再生成候选补丁，最后独立应用正式脚本”。

**Architecture:** 复用现有 Repair Session、Attempt、临时 workspace、revision 和正式回归能力。Diagnosis Agent 增加 `RepairProposal` 并在第一阶段停止；`approve` 只启动候选修复，新增 `apply` 完成正式套件替换，前端按 `available_actions` 显示两个独立人工闸门。

**Tech Stack:** FastAPI、SQLite、Pydantic v2、pytest、Next.js、React、TypeScript、Node `node:test`。

## Global Constraints

- 诊断阶段不得创建或修改候选 workspace。
- `interface_bug`、`contract_ambiguity`、`unknown` 不得批准修改测试脚本。
- `approve` 不得修改正式 suite 或创建正式 API Run。
- 只有 `ready_to_apply` 可以调用 `apply`。
- 不删除、跳过、`xfail` 或弱化失败断言来制造通过。
- 保留当前未提交的其他改动，不回滚或覆盖无关文件。

---

### Task 1: Persist structured proposal and new states

**Files:**
- Modify: `apps/backend/app/agents/api_automation/self_healing/schemas.py`
- Modify: `apps/backend/app/agents/api_automation/self_healing/diagnosis_agent.py`
- Modify: `apps/backend/app/repositories/api_automation_repo.py`
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/app/schemas/api_automation.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_diagnosis.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_repo.py`

**Interfaces:**
- Produces: `RepairProposal`, `FailureDiagnosis.proposal`, persisted `proposal_json`, serialized `proposal`.

- [ ] Add failing tests that validate proposal target/action/status-code fields and reject `script_repair_allowed=true` for interface, contract, and unknown targets.
- [ ] Add a repository round-trip test for `proposal_json` and the new Attempt states.
- [ ] Implement the Pydantic proposal model and diagnosis prompt/output contract.
- [ ] Add idempotent storage support and serialize proposal data.
- [ ] Run the focused diagnosis and repository tests.

### Task 2: Stop the first stage at proposal approval

**Files:**
- Modify: `apps/backend/app/services/api_automation/self_healing.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_service.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_validation.py`

**Interfaces:**
- Produces: `execute_repair_attempt(attempt_id)` ending in `waiting_approval` or `proposal_ready` without invoking `repair_failure`.
- Produces actions: `approve_proposal`, `reject_proposal`, `reanalyze`, `confirm_no_script_change`.

- [ ] Add a failing service test proving diagnosis completion does not create a candidate workspace or invoke the Repair Agent.
- [ ] Add tests proving non-script proposal targets cannot expose approval.
- [ ] Split diagnosis execution from candidate repair execution.
- [ ] Compute actions from status and `proposal.script_repair_allowed`.
- [ ] Run focused service and validation tests.

### Task 3: Separate approve, candidate validation, and apply

**Files:**
- Modify: `apps/backend/app/services/api_automation/self_healing.py`
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Modify: `apps/backend/app/schemas/api_automation.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_service.py`
- Test: `apps/backend/tests/test_api_automation_ai_repair_api.py`

**Interfaces:**
- `approve_repair_attempt(project_id, attempt_id, comment, actor)` returns an Attempt in `candidate_generating` and does not touch the formal suite.
- `execute_candidate_repair(attempt_id)` produces a validated workspace and ends in `ready_to_apply`.
- `apply_repair_attempt(project_id, attempt_id, comment, actor)` performs the existing deterministic suite replacement and creates the formal run.
- `discard_repair_attempt(project_id, attempt_id, comment, actor)` removes the candidate and records rejection.

- [ ] Add failing tests for approve-not-apply, ready-to-apply gating, baseline drift, and discard behavior.
- [ ] Move the existing workspace replacement code from `approve_repair_attempt` into `apply_repair_attempt`.
- [ ] Make approve transition state and run candidate repair asynchronously through the API route.
- [ ] Add `/apply` and `/discard` routes and request validation.
- [ ] Run focused API and service tests.

### Task 4: Implement two approval gates in the drawer

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-repair-progress.tsx`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-repair-drawer.tsx`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-repair-diff-dialog.tsx`
- Test: `apps/frontend/tests/api-automation-ai-repair-contract.test.mjs`

**Interfaces:**
- Consumes: Attempt `proposal`, new statuses, and backend `available_actions`.
- Produces: `applyApiRepairAttempt` and `discardApiRepairAttempt` client functions.

- [ ] Update the contract test to reject “批准并应用” in proposal state and require “批准并开始修复” plus “应用通过的测试脚本”.
- [ ] Add proposal fields to client types and add apply/discard requests.
- [ ] Update progress labels for proposal, candidate generation, candidate validation, and ready-to-apply.
- [ ] Render evidence, actual/expected status codes, risks, questions, and the no-script-change conclusion.
- [ ] Show Diff and formal apply actions only for `ready_to_apply`.
- [ ] Run the focused frontend contract test and Biome on changed files.

### Task 5: Verify the complete state flow

**Files:**
- Verify: `apps/backend/tests/test_api_automation_ai_repair_*.py`
- Verify: `apps/frontend/tests/api-automation-ai-repair-contract.test.mjs`

**Interfaces:**
- Verifies: diagnosis-only first stage, approval-triggered candidate repair, independent application, and frontend action gating.

- [ ] Run all backend AI repair tests.
- [ ] Run the frontend AI repair contract test.
- [ ] Run backend collection for the affected tests.
- [ ] Review the final diff for accidental edits to generated project data or unrelated modules.
