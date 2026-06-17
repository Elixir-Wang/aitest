---
name: requirements-analysis
description: Understand product or business requirements and generate structured requirement understanding plus clarification questions. Use when Codex is asked to analyze a requirement, read a PRD, turn raw demand into a requirement analysis, identify unclear requirement points, produce pending clarification content, or replace a generic requirement-analysis framework with an actionable requirements-understanding workflow.
---

# Requirements Analysis

## Purpose

Use this skill to transform raw requirements into two outputs:

1. A structured requirement understanding that explains what is known.
2. A pending clarification list that exposes what is ambiguous, missing, or contradictory.

Do not include quality assurance content here. Keep risk analysis, test strategy, acceptance criteria, rollout checks, and monitoring requirements for the final requirement or a separate quality-assurance skill.

## Workflow

1. Read the provided requirement source completely before analyzing it.
2. Extract explicit facts only. Mark uncertain inferences as inference, not conclusion.
3. Build the requirement understanding using `references/understanding.md`.
4. Generate pending clarification content using `references/clarification.md`.
5. Merge duplicate clarification questions and group them by module or business object.
6. Prioritize clarification questions by delivery impact:
   - P0: Blocks scope, business rule, permission, state transition, data correctness, or implementation.
   - P1: Blocks consistent UX, exception handling, integration behavior, or testing.
   - P2: Improves completeness but can be decided during detailed design.
   - P3: Nice-to-have detail or future optimization.
7. Output the analysis in Chinese unless the user requests another language.

## Required Output

Use this structure by default:

```markdown
## 需求理解

### 1. 需求背景
### 2. 目标与价值
### 3. 用户角色与使用场景
### 4. 功能范围
### 5. 业务流程
### 6. 状态流转
### 7. 业务规则
### 8. 页面与交互
### 9. 数据与系统交互

## 待澄清内容

| 优先级 | 模块/对象 | 澄清问题 | 影响 |
|---|---|---|---|
```

If the source requirement is too thin for a section, write `原文未说明` and move the gap into pending clarification.

## Boundaries

- Do not invent business rules, APIs, fields, states, or limits.
- Do not create implementation interfaces unless the source requirement already defines them.
- Do not include quality risks, test cases, acceptance criteria, or release checks in this skill output.
- Do not treat assumptions as confirmed facts.
- Prefer concrete questions over generic questions.

## Resources

- Read `references/understanding.md` when building the requirement understanding.
- Read `references/clarification.md` when generating pending clarification content.
