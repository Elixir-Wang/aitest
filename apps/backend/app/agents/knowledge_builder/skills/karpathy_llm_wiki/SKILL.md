---
name: karpathy_llm_wiki
description: Build a navigable Karpathy llm-wiki from confirmed sources instead of query-time chunk retrieval.
---

# Karpathy llm-wiki

Use this skill when generating or updating a project knowledge base.

## Core Rules

- Treat raw sources as immutable evidence and the wiki as a compiled artifact.
- Do not use vector retrieval or ad-hoc chunks as the final knowledge shape.
- Start from `index.md`, then create module pages and supporting maps.
- Preserve source traceability for every important claim.
- Keep blockers, conflicts, and unconfirmed facts in `build/` or `quality/`; do not index them as confirmed knowledge.

## Required Wiki Structure

Generate pages equivalent to:

- `AGENTS.md`: schema, allowed sources, citation rules, update rules.
- `index.md`: page inventory with summaries and source counts.
- `log.md`: generation log.
- `00-项目总览.md`: project scope, roles, workflows, core objects.
- `01-模块索引.md`: modules, relationships, entry pages, key objects.
- `modules/*.md`: confirmed module knowledge.
- `maps/source-reference-matrix.md`: claim-to-source matrix.
- `maps/module-source-map.md`: module-to-source map.
- `maps/page-requirement-map.md`: explored pages mapped to requirements.
- `quality/lint-report.md`: missing citations, empty modules, blockers, stale claims.
- `quality/stale-claims.md`: deprecated or superseded claims.
- `testing/test-focus.md`: confirmed test focus by module.
- `testing/risk-paths.md`: high-risk flows and regression paths.
- `testing/state-flows.md`: state transitions and assertable outcomes.
- `build/build-summary.md`: build inputs, output summary, status.
- `build/update-plan.md`: suggested next update steps.
- `build/build-blockers.md`: unresolved blockers.
- `build/conflict-check.md`: source conflicts and required human confirmation.
- `build/changelog.md`: changes in this build.

## Page Contract

Each module page should include:

- Frontmatter with `module_key`, `module_name`, `status`, `source_count`.
- Summary.
- Confirmed requirement facts.
- Confirmed page facts.
- Merged business knowledge.
- Test focus.
- Source references.

## Output Contract

Return JSON only. Include pages with `page_id`, `title`, `relative_path`, `page_type`, `markdown_content`, `summary`, and `source_refs`.
