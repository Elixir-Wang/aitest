# Document Editor LLM Task Cleanup Spec

## Background

The model assignment refactor moved `document_editor` from an Agent SDK capability to a plain OpenAI SDK LLM task. The active runtime entrypoint is now `app.llm_tasks.document_editor.edit_document`, and `document_editor` is listed as `kind="llm_task"` in the unified AI capability registry.

However, the old `app/agents/document_editor` package still exists and still contains an AgentDefinition, runner, prompt builder, and skill file. This conflicts with the new architecture and can make the same capability appear to have two execution models.

The new `app/llm_tasks/document_editor.py` file also retains a small amount of compatibility-oriented code from the old Agent runner style.

## Goals

- Keep `document_editor` as a plain LLM task backed by the OpenAI SDK.
- Remove the old `app/agents/document_editor` package and its skill file.
- Simplify the active LLM task implementation so it does not carry Agent-runner compatibility code.
- Preserve business guardrails that are still useful for document editing safety.

## Non-Goals

- Do not remove or redesign the whole legacy `app/agents` framework in this change.
- Do not move other business agents to `app/ai_agents`.
- Do not change the public document-editor API route or response schema.
- Do not add frontend behavior in this cleanup.

## Design

`app.llm_tasks.document_editor.edit_document` remains the only document editing execution entrypoint. It resolves the `document_editor` model assignment, requires an OpenAI provider because the task depends on structured output parsing, builds an OpenAI SDK client, and calls `client.responses.parse(..., text_format=DocumentEditOutput)`.

The function should not accept unused request metadata. If actor metadata is needed later for audit or tracing, it should be added with a concrete storage or trace target instead of keeping an inert parameter.

Input validation remains as a lightweight whitespace guard because the Pydantic schema's `min_length=1` accepts whitespace-only strings. Output validation also keeps whitespace checks and the existing abnormal-shrink guard because those are runtime safety checks beyond the schema contract.

The old `app/agents/document_editor` package is removed. Architecture tests should explicitly fail if `document_editor` reappears under either the new `app/ai_agents` package or the older `app/agents` framework.

## Acceptance Criteria

- `app/agents/document_editor` no longer exists.
- `app/llm_tasks/document_editor.py` has no unused `actor_id` parameter.
- `app/llm_tasks/document_editor.py` no longer uses a compatibility coercion helper for parsed output.
- `document_editor` remains present in AI capabilities as `kind="llm_task"`.
- `document_editor` remains absent from agent capability lists.
- Backend tests pass.
