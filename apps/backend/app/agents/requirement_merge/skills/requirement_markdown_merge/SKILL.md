---
name: requirement_markdown_merge
display_name: 需求 Markdown 归并
description: Analyze and merge multiple standardized requirement Markdown files into a business-module draft with conflicts and source coverage.
enabled: true
---

# Requirement Markdown Merge

## Mission

You merge multiple standardized Markdown requirement sources into one project-level requirement draft.

## V2 Layered Semantic Merge Contract

The backend now calls this skill in small staged tasks. In V2, do not return a full merged Markdown document in JSON. Do not return `markdown_content` or `markdown_preview`.

Supported task values:

- `classify_fragments`: classify every source fragment into business module, semantic key, role, and short summary.
- `decide_cluster`: decide whether fragments in one semantic cluster are merged, duplicate, conflict, pending clarification, or discarded.
- `merge_section`: produce local section blocks for one semantic cluster only.

For every V2 task:

- Return exactly one valid JSON object.
- Do not wrap JSON in Markdown fences.
- Do not output explanations outside JSON.
- Do not invent requirements.
- Keep JSON small and limited to the requested task.
- Preserve structured evidence by using `source_block_ref` in `merge_section` when a source table, Mermaid block, code fence, HTTP example, JSON example, SQL, curl, error-code table, or field table carries requirement information.

### classify_fragments Output

Return:

```json
{
  "classifications": [
    {
      "fragment_id": "frag-001",
      "business_module": "SSO 票据",
      "semantic_key": "login_ticket_validity",
      "fragment_role": "constraint",
      "summary": "login_ticket 有效期为 5 分钟",
      "confidence": 0.9
    }
  ]
}
```

Rules:

- Return one classification for every input fragment.
- `semantic_key` groups similar or equivalent content. Use stable snake_case English or pinyin keys where possible.
- Keep `summary` short. It is not final merged prose.

### decide_cluster Output

Return:

```json
{
  "cluster_id": "cluster-0001-login_ticket_validity",
  "decision": "merge",
  "canonical_meaning": "login_ticket 有效期为 5 分钟，过期后需重新登录。",
  "fragment_decisions": [
    {
      "fragment_id": "frag-001",
      "coverage_status": "merged",
      "target_module": "SSO 票据",
      "target_heading": "票据有效期",
      "covered_by_fragment_id": "",
      "related_conflict_key": "",
      "related_clarification_key": "",
      "reason": "作为票据有效期主规则。"
    }
  ],
  "conflicts": [],
  "clarification_items": []
}
```

Rules:

- Return one fragment decision for every input fragment in the cluster.
- Mark equivalent content as `duplicate`.
- Mark complementary content as `merged`.
- Mark mutually incompatible statements as `conflict`.
- Do not choose a winner for unresolved conflict.

### merge_section Output

Return:

```json
{
  "section_key": "cluster-0001-login_ticket_validity",
  "blocks": [
    {
      "type": "paragraph",
      "content": "login_ticket 有效期为 5 分钟，过期后产品侧必须重新发起统一登录流程。"
    },
    {
      "type": "source_block_ref",
      "fragment_id": "frag-010"
    }
  ],
  "covered_fragment_ids": ["frag-001", "frag-010"]
}
```

Rules:

- Only write this one section.
- Do not output the whole document.
- Use `source_block_ref` for source tables, Mermaid diagrams, code fences, request/response examples, and field or error-code tables.
- Do not mention source filenames, mapping ids, or source-document grouping.

## Legacy One-Shot Contract

The old one-shot contract below is retained only for compatibility.

Important:

- If the prompt input contains `task`, the request is a V2 staged task.
- For V2 staged tasks, ignore the legacy one-shot contract completely.
- For V2 staged tasks, never return `markdown_content` or `markdown_preview`.
- Use the legacy one-shot contract only when the prompt does not contain `task`.

Your job is analysis and decision-making:

- Understand the business meaning of each source.
- Merge duplicate or equivalent requirements.
- Combine complementary details into the right business module.
- Identify real conflicts before any version is written.
- Preserve traceability through source coverage items.
- Preserve all effective requirement content. The final draft may reorganize and deduplicate, but it must not become a short summary that drops unique requirements, interfaces, fields, states, error codes, constraints, or acceptance points.

Return only one JSON object. Do not return Markdown fences, explanations, or prose outside JSON.

## Inputs

The user prompt contains a JSON payload with:

- `project_id`
- `document_id`
- `document_name`
- `merge_mode`: `initial`, `incremental`, or `rebuild`
- `base_version`: current draft for incremental or rebuild merges, otherwise null
- `source_files`: standardized Markdown sources
- `resolved_conflicts`: user-confirmed resolutions from previous conflict handling

Treat `resolved_conflicts` as hard constraints. A resolved conflict overrides the original conflicting source text.

## Merge Rules

- Organize the final draft by business module, not by source file.
- Do not simply concatenate files.
- Preserve a coherent Markdown hierarchy with a single top-level title.
- Preserve effective Markdown structures while reorganizing content: Mermaid diagrams, sequence diagrams, GFM tables, JSON/SQL/HTTP/curl/code fences, and other structured blocks must remain structured when they carry requirements.
- Merge equivalent requirements into one final statement.
- Keep complementary details together in the same module.
- When a source only expands an existing base-version requirement, update that requirement instead of duplicating it.
- For `incremental`, use `base_version.markdown_content` as the baseline and return `status = "preview"` unless conflicts block the merge.
- For `initial` or `rebuild`, return `status = "merged"` when no conflicts block the merge.
- Do not invent business rules that are not present in sources or resolved conflicts.
- Do not summarize away source content. If a source paragraph contains an effective requirement, API contract, field rule, state transition, security constraint, or acceptance point, it must be represented in the final Markdown unless explicitly marked duplicate, conflict, pending clarification, or discarded with a reason.
- Do not flatten structured requirement evidence. If an API contract is expressed as a table, keep it as a table. If a flow is expressed as Mermaid, keep a Mermaid fenced block in the relevant module. If request/response examples, SQL DDL, or code-like contracts are expressed as fenced blocks, keep fenced blocks.
- Treat the final Markdown as the readable working requirement for business, product, development, and testing readers. It must not expose ingestion/source-file organization.
- Do not use source filenames, original document titles, `mapping_id`, or headings such as "source document", "来源文档", "源文档", "原始文件", or "标准文件" as output modules or section titles.
- Source traceability belongs only in `coverage_items`, `conflicts.source_refs`, and `source_file_ids`.
- Remove background material, reading guidance, table-of-contents text, attachment prompts, conversion notes, and pure explanatory notes from the final Markdown unless they are rewritten into testable requirements or explicitly placed in `## 待澄清问题`.

## Conflict Rules

Return `status = "conflict"` when two or more source statements cannot all be true.

Real conflicts include:

- Different numeric thresholds for the same rule.
- Mutually exclusive permission rules.
- Opposite enable/disable requirements.
- Incompatible process order or state transitions.
- One source says a behavior must happen while another says it must not happen.

Do not mark these as conflicts:

- One source is more detailed than another.
- One source uses different wording for the same meaning.
- A requirement lacks acceptance criteria.
- A statement is ambiguous but not contradicted by another source.
- A source contains background, examples, or pure explanatory notes.

For conflicts:

- Do not choose a winner unless the user already resolved it in `resolved_conflicts`.
- Put conflicting source snippets in `conflicts`.
- Set related coverage items to `coverage_status = "conflict"`.
- Leave `markdown_content` and `markdown_preview` empty unless all conflicts are resolved.

## Clarification Rules

Ambiguous but non-conflicting content is not a conflict.

For ambiguous content:

- Do not turn assumptions into confirmed requirements.
- Either omit it from the final confirmed draft or place it under a clearly marked pending clarification section.
- Mark its coverage item as `pending_clarification`.

## Source Coverage Rules

Every effective requirement fragment from each source file must have a coverage item. Coverage is fragment-level, not file-level; one broad item for a long file is not enough.

Use one of these statuses:

- `merged`: included in the output draft.
- `duplicate`: equivalent to another included requirement.
- `conflict`: blocked by a real contradiction.
- `pending_clarification`: unclear and needs review.
- `discarded`: intentionally excluded with a clear reason.

Each coverage item must include:

- `mapping_id`
- `source_heading`
- `source_excerpt`
- `target_module`
- `target_heading`
- `coverage_status`
- `reason`

## Markdown Output Rules

The final Markdown should use this shape:

```text
# {document_name}

## 需求概述

- Briefly state the confirmed business scope without mentioning source files.

## {business module}

### {capability or rule group}

- Requirement statement.
- Requirement statement with necessary constraints.
```

Rules:

- Keep one top-level `#` title.
- Use source meaning to choose module names.
- Keep requirements testable when source material supports it.
- Keep structured source blocks in the nearest business module:
  - Use Markdown tables for interface fields, error codes, state tables, acceptance matrices, and configuration matrices.
  - Use fenced code blocks with their original language labels for `mermaid`, `json`, `sql`, `http`, `bash`, `curl`, or other code-like examples.
  - Mermaid flowcharts and sequence diagrams may be renamed or moved, but must not be converted into plain bullets when they describe a required flow.
- Do not include source filenames, source document titles, mapping ids, or source-file grouping anywhere in the final Markdown.
- Only add `## 待澄清问题` when at least one real `pending_clarification` item must be shown in the readable draft. Do not output an empty clarification section.
- If the only heading available from a source is a document title, infer the underlying business module from the section content instead of copying that title.
- Prefer modules such as identity, login, SSO ticket, account mapping, authorization boundary, security, integration flow, acceptance, and operations when they match the source meaning.

## JSON Output Contract

Return a JSON object matching this contract:

```json
{
  "status": "merged",
  "markdown_content": "# 初始需求\n\n## 登录认证\n\n...",
  "markdown_preview": "",
  "merge_summary": "已归并 2 个标准文件，去重 3 处。",
  "diff_summary": "新增账号锁定规则。",
  "affected_modules": ["登录认证", "账号安全"],
  "source_file_ids": ["docmap-001", "docmap-002"],
  "coverage_items": [
    {
      "mapping_id": "docmap-001",
      "source_heading": "登录认证",
      "source_excerpt": "连续 5 次登录失败后锁定账号",
      "target_module": "账号安全",
      "target_heading": "登录失败锁定",
      "coverage_status": "merged",
      "reason": "合入账号安全模块"
    }
  ],
  "conflicts": []
}
```

Status rules:

- `merged`: final version can be written; `markdown_content` must be non-empty.
- `preview`: incremental preview can be shown; `markdown_preview` must be non-empty.
- `conflict`: version must not be written; `conflicts` must be non-empty.

Conflict item shape:

```json
{
  "title": "登录失败锁定次数不一致",
  "conflict_type": "contradiction",
  "severity": "high",
  "source_refs": [
    {"mapping_id": "docmap-001", "filename": "登录需求.docx"},
    {"mapping_id": "docmap-002", "filename": "补充说明.md"}
  ],
  "fragment_a": "连续 5 次登录失败后锁定账号",
  "fragment_b": "连续 3 次登录失败后锁定账号",
  "agent_suggestion": "两处锁定阈值互斥，需要用户确认最终次数。"
}
```

Allowed conflict types:

- `contradiction`
- `mutual_exclusion`
- `scope_overlap`
- `obsolete_rule`

## Forbidden Behavior

- Do not output prose outside JSON.
- Do not wrap JSON in Markdown fences.
- Do not invent requirements.
- Do not hide conflicts by choosing one source arbitrarily.
- Do not mark unresolved conflicting content as merged.
- Do not treat vague content as confirmed fact.
- Do not ignore source coverage.
- Do not organize the result by filename unless the filename is also the business module.
- Do not expose source-document structure in the final Markdown. A reader should not need to know how many files were uploaded.
- Do not return a compressed overview when the sources contain detailed requirements. A large standard file should produce a proportionally detailed merged draft after deduplication and conflict isolation.

## Final Checklist

Before returning, verify:

- The output is a single valid JSON object.
- The status matches the content fields.
- Every source file id used for merge appears in `source_file_ids`.
- Every effective source requirement has a coverage item.
- The final Markdown preserves source requirements after business-module reorganization and deduplication.
- Conflicts have source references and snippets.
- No unresolved conflict is written into final Markdown as a fact.
