# Exploration Goal Field Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clarify exploration task semantics by keeping `探索范围` as the coverage boundary and renaming user-facing `描述` to `探索目标`.

**Architecture:** Keep the existing backend storage/API field `description` for compatibility. Change only user-facing copy, placeholders, summaries, and docs so the product concept becomes `探索目标`, while the runner continues to use `scope` and `forbidden_paths` exactly as it does today.

**Tech Stack:** Next.js/React frontend, FastAPI/Pydantic backend API contract, Markdown PRD/spec docs, Biome lint.

---

## File Structure

- Modify: `docs/00-产品文档/00-04-AI测试系统-站点探索PRD.md`
  - Clarify the three exploration input concepts: `探索范围`, `探索目标`, `禁止路径`.
- Modify: `apps/frontend/src/components/ai-testing/exploration-workspace.tsx`
  - Rename the exploration task form label from `描述` to `探索目标`.
  - Replace the placeholder with a concrete target example.
  - Keep payload field name as `description`.
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
  - Rename the edit dialog label from `描述` to `探索目标`.
  - Add `探索目标` to the right-side input summary.
  - Replace placeholder copy with the same concrete target pattern.
- Verify only: `apps/backend/app/schemas/exploration.py`
  - Confirm `description` remains the API compatibility field. Do not rename in this plan.

---

### Task 1: Document The Field Semantics

**Files:**
- Modify: `docs/00-产品文档/00-04-AI测试系统-站点探索PRD.md`

- [ ] **Step 1: Update the站点配置字段表**

Find the current rows:

```markdown
| 探索范围 | 菜单范围、URL 白名单、URL 黑名单 |
| 禁止路径 | 不允许探索的危险路径，如删除、支付、外发 |
```

Replace them with:

```markdown
| 探索范围 | 本次探索覆盖边界，例如全站、指定菜单、指定 URL、指定模块或 `范围包含：入口页、目录导航、正文链接` |
| 探索目标 | 本次探索需要验证和记录什么，例如遍历页面元素、检查链接跳转、识别 401/403/登录页/无权限页、统计标题和 URL |
| 禁止路径 | 不允许点击或进入的危险路径/按钮关键词，如删除、支付、外发、批量通知、确认发布 |
```

- [ ] **Step 2: Add concept rules after the table**

Add this paragraph immediately below the table:

```markdown
字段语义：

- 探索范围回答“去哪里探索”，用于限定模块、页面、URL 或菜单边界。
- 探索目标回答“探索时要验证什么”，用于说明要点击、检查、统计和记录的事实。
- 禁止路径回答“哪些不能碰”，用于保护删除、支付、外发、发布等危险动作。
- 探索目标不是禁止规则；任何必须跳过的动作都必须写入禁止路径。
```

- [ ] **Step 3: Run a doc grep check**

Run:

```powershell
rtk rg -n "探索目标|探索范围|禁止路径" docs/00-产品文档/00-04-AI测试系统-站点探索PRD.md
```

Expected:

```text
The output includes all three concepts and no longer leaves the task-level field described only as generic 描述.
```

---

### Task 2: Rename The Create/Edit Exploration Form Copy

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/exploration-workspace.tsx`

- [ ] **Step 1: Change dialog description**

Find:

```tsx
<DialogDescription>选择环境并配置探索范围、禁止路径和任务说明。</DialogDescription>
```

Replace with:

```tsx
<DialogDescription>选择环境并配置探索范围、探索目标和禁止路径。</DialogDescription>
```

- [ ] **Step 2: Change the field label**

Find:

```tsx
<FieldLabel htmlFor="exploration-description">描述</FieldLabel>
```

Replace with:

```tsx
<FieldLabel htmlFor="exploration-description">探索目标</FieldLabel>
```

- [ ] **Step 3: Change the placeholder**

Find:

```tsx
placeholder="本次探索目标、角色说明、验证码处理方式或人工注意事项"
```

Replace with:

```tsx
placeholder="例如：探索各页面所有可见元素，点击正文链接、按钮、侧边栏锚点和顶部入口，检查是否出现 401/403、跳转登录页、无权限页或异常页，并记录标题、URL、复现步骤和证据。"
```

- [ ] **Step 4: Keep API payload unchanged**

Confirm this code remains unchanged:

```tsx
const payload = {
  environment_id: explorationForm.environmentId,
  title: explorationForm.title,
  scope: explorationForm.scope,
  forbidden_paths: explorationForm.forbiddenPaths,
  description: explorationForm.description,
};
```

Expected:

```text
The UI says 探索目标, but the backend still receives description.
```

---

### Task 3: Rename The Detail Page Copy And Show Exploration Goal

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] **Step 1: Add exploration goal to the input summary**

Find:

```tsx
<InfoRow label="探索范围" value={run?.scope || "-"} />
<InfoRow label="禁止路径" value={run?.forbidden_paths || "-"} />
```

Replace with:

```tsx
<InfoRow label="探索范围" value={run?.scope || "-"} />
<InfoRow label="探索目标" value={run?.description || "-"} />
<InfoRow label="禁止路径" value={run?.forbidden_paths || "-"} />
```

- [ ] **Step 2: Change edit dialog description**

Find:

```tsx
<DialogDescription>调整任务名称、关联环境、探索范围、禁止路径和任务说明。</DialogDescription>
```

Replace with:

```tsx
<DialogDescription>调整任务名称、关联环境、探索范围、探索目标和禁止路径。</DialogDescription>
```

- [ ] **Step 3: Change edit field label**

Find:

```tsx
<FieldLabel htmlFor="exploration-description">描述</FieldLabel>
```

Replace with:

```tsx
<FieldLabel htmlFor="exploration-description">探索目标</FieldLabel>
```

- [ ] **Step 4: Change edit placeholder**

Find:

```tsx
placeholder="本次探索目标、角色说明、验证码处理方式或人工注意事项"
```

Replace with:

```tsx
placeholder="例如：探索各页面所有可见元素，点击正文链接、按钮、侧边栏锚点和顶部入口，检查是否出现 401/403、跳转登录页、无权限页或异常页，并记录标题、URL、复现步骤和证据。"
```

---

### Task 4: Verify Contract Compatibility

**Files:**
- Verify: `apps/backend/app/schemas/exploration.py`
- Verify: `apps/backend/app/services/exploration_service.py`
- Verify: `apps/backend/app/services/site_exploration_orchestrator.py`

- [ ] **Step 1: Confirm API field remains description**

Run:

```powershell
rtk rg -n "description: str|description=payload.description|description: explorationForm.description|run.description" apps/backend apps/frontend/src/components/ai-testing/exploration-workspace.tsx "apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx"
```

Expected:

```text
Backend schemas and services still use description, and frontend payloads still send description.
```

- [ ] **Step 2: Confirm runner behavior remains unchanged**

Run:

```powershell
rtk rg -n "forbidden_paths|forbiddenInput|isForbidden|scope" apps/backend/app/services/site_exploration_orchestrator.py apps/backend/runners/playwright/site-explorer.mjs
```

Expected:

```text
Only forbidden_paths is passed into the runner as skip keywords. Description/exploration target is not consumed by the runner in this plan.
```

---

### Task 5: Lint And Manual UI Verification

**Files:**
- Verify: `apps/frontend/src/components/ai-testing/exploration-workspace.tsx`
- Verify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] **Step 1: Run targeted lint**

Run:

```powershell
cd apps/frontend
rtk npx biome lint "src/components/ai-testing/exploration-workspace.tsx" "src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx"
```

Expected:

```text
Checked 2 files. No fixes applied.
```

- [ ] **Step 2: Run text regression search**

Run:

```powershell
rtk rg -n "任务说明|htmlFor=\"exploration-description\">描述|本次探索目标、角色说明" apps/frontend/src/components/ai-testing/exploration-workspace.tsx "apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx"
```

Expected:

```text
No output.
```

- [ ] **Step 3: Browser verify the create dialog**

Open the exploration list page and click `新建探索任务`.

Expected:

```text
The dialog says 配置探索范围、探索目标和禁止路径.
The third textarea label is 探索目标.
The placeholder uses the 401/403/login/no-permission example.
```

- [ ] **Step 4: Browser verify the detail page**

Open an existing exploration task detail page.

Expected:

```text
The right-side 输入摘要 includes 关联环境, 探索范围, 探索目标, 禁止路径.
The edit dialog uses 探索目标 instead of 描述.
```

---

## Self-Review

- Spec coverage: Covers the requested semantic split: `探索范围` remains range, `描述` becomes user-facing `探索目标`, and `禁止路径` remains safety skip rules.
- Placeholder scan: No TBD/TODO placeholders remain.
- Type consistency: No backend field rename is planned; `description` remains the compatibility field in API, database, and payloads.
- Scope check: This is one bounded UI/product-copy change. No database migration or runner behavior change belongs in this plan.

## Execution Choice

Plan complete and saved to `docs/superpowers/plans/2026-05-28-exploration-goal-field-rename.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints.
