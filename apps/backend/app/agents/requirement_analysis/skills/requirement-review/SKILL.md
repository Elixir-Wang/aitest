---
name: requirement-review
description: Review a primary requirement document for defects. Use to find missing rules, ambiguity, conflicts, weak acceptance criteria, poor testability, traceability gaps, feasibility risks, and issues that should become clarification questions.
---

# Requirement Review

Review only the primary requirement. Treat supporting documents as evidence, not scope.

Check these dimensions:

- Completeness: missing business rules, roles, fields, states, constraints, dependencies, exception paths, or acceptance criteria.
- Clarity: vague terms, subjective wording, undefined terms, unclear actor/action/object, or multiple possible interpretations.
- Consistency: conflicting rules, inconsistent terminology, incompatible priorities, or scope contradictions.
- Testability: missing pass/fail criteria, unobservable outcomes, missing inputs, missing expected results, or unmeasurable non-functional requirements.
- Traceability: requirement intent cannot be linked to a business goal, source excerpt, downstream design, or test.
- Feasibility: unrealistic performance, security, timeline, integration, data, or permission assumptions.

Classify severity:

- blocker: blocks design, implementation, or test design.
- major: likely causes rework or wrong tests.
- minor: improves clarity but does not block execution.

Do not invent missing facts. Missing facts become questions or gaps.
Do not copy supporting document content unless it answers a primary-requirement problem and has a direct evidence excerpt.
