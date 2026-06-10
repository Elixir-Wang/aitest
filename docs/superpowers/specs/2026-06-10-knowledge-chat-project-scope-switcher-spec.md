# Knowledge Chat Project Scope Switcher Spec

## Background

The knowledge chat input currently has two low-value controls:

- The `+` button is labeled as adding context but has no behavior.
- The clock button only toggles local UI state and does not affect the backend request.

Project knowledge chat is currently routed through single-project endpoints:

- Frontend stream request: `/projects/{project_id}/knowledge/query/stream`
- Backend API router: `/projects/{project_id}/knowledge`
- Conversation persistence: `knowledge_conversations.project_id`
- Knowledge collection: requirements and explorations are loaded by one `project_id`

The global project switcher already supports two contexts:

- `全部项目`
- a specific project

The input-level scope selector should correspond to that global context instead of inventing unrelated behavior.

## Goal

Replace the unused input buttons with a project scope switcher for knowledge retrieval.

The switcher controls which project scope the next knowledge chat query uses:

- When the top-right global project context is `全部项目`, the input switcher defaults to `全部项目` and can switch to any active project.
- When the top-right global project context is a specific project, the input switcher is locked to that same project.

The model selector should be visually smaller and show only the model name by default.

## Non-Goals

- Do not implement image parsing, OCR, or file attachment behavior in this change.
- Do not create a separate project context system for the knowledge chat input.
- Do not silently map `全部项目` to the first active project.
- Do not keep fake controls that do not change request behavior.

## UX Design

### Input Controls

The input footer should contain:

1. Project scope switcher
2. Compact model selector
3. Send button

The clock button is removed.

The existing `+` button area becomes the project switcher. A folder/project icon may be used, followed by the selected scope label.

### Scope Behavior

When global context is `全部项目`:

- Input switcher default: `全部项目`
- Dropdown options: `全部项目` plus active projects
- User may select a specific project for the current knowledge chat
- Selecting a specific project limits retrieval and conversation history to that project
- Switching back to `全部项目` uses all active projects

When global context is a specific project:

- Input switcher value: that project
- Dropdown is disabled or contains only that project
- The user cannot broaden the input scope to `全部项目`
- The input should make the locked state clear through disabled styling and title text

When the global context changes:

- If global context becomes `全部项目`, reset input scope to `全部项目`
- If global context becomes a specific project, set input scope to that project and clear incompatible chat state

### Model Selector

The collapsed model selector shows only `model`.

The dropdown can still show:

- model name
- provider name
- selected checkmark

Loading and saving labels stay short, for example `加载中` and `保存中`.

## Data Flow

### Frontend State

Knowledge page derives global project context from `useProjectContextStore`.

Add local knowledge chat scope state:

- `knowledgeScope: "all" | "project"`
- `knowledgeProjectId: string | null`

The effective query scope is computed from global context:

- Global `project`: effective scope is always that project
- Global `all`: effective scope is the local input selection

Conversation state is keyed by effective scope:

- Specific project: use that project's conversations
- All projects: use all-project conversations, or no persisted conversations if the backend does not persist all-project conversations in the first implementation slice

### Backend Contract

The current single-project endpoint remains:

`POST /projects/{project_id}/knowledge/query/stream`

Add an all-project stream endpoint:

`POST /knowledge/query/stream`

Request body can reuse `KnowledgeQueryRequest`:

- `question`
- `include_requirements`
- `include_explorations`
- `conversation_id`

All-project query behavior:

- Load all active projects accessible to the actor
- For each project, collect final requirement versions and completed or partial explorations using the same collection rules as single-project search
- Include project name and project id in the source context so the model can identify which project each fact came from
- Source references returned to the frontend should include enough project identity for display

Single-project behavior remains unchanged.

## Conversation Design

Single-project conversations continue using the current project-scoped model.

All-project conversations should not be stored under a random real project. There are two acceptable implementation choices:

1. Add nullable or sentinel scope support to `knowledge_conversations`
2. Keep all-project chat ephemeral initially

Recommendation: use ephemeral all-project conversations for the first implementation if schema migration would enlarge the change too much. This keeps the project switcher honest without forcing conversation persistence into the first slice.

If all-project persistence is implemented, it should have explicit scope fields rather than overloading an existing project id.

## Source Display

For specific project queries, keep current source display.

For all-project queries, each source reference should show:

- source type: requirement or exploration
- project name
- source title
- location
- excerpt

This prevents answers from mixing facts across projects without visible attribution.

## Error Handling

When global context is a specific project but the project is archived or unavailable:

- Disable input
- Show a clear message asking the user to switch project context

When global context is `全部项目` but there are no active projects:

- Disable input
- Show the existing no-project style message

When all-project search finds no usable requirement versions or exploration runs:

- Return a structured error/answer explaining that no active project has queryable knowledge

When a user switches scope while a request is running:

- Disable scope switcher until the stream completes

## Testing

Frontend tests:

- Global `全部项目` defaults input switcher to `全部项目`
- Global `全部项目` allows selecting an active project
- Global project context locks the input switcher to that project
- Model selector collapsed label shows only model name
- Clock button is no longer rendered

Backend tests:

- Single-project query path remains compatible
- All-project query loads sources from multiple active projects
- All-project query does not use the first active project as a hidden fallback
- All-project source refs include project identity

Manual verification:

- Top-right `全部项目`, input `全部项目`: query searches across active projects
- Top-right `全部项目`, input specific project: query searches only that project
- Top-right specific project: input switcher is locked to the same project
- Existing project conversation open/delete behavior still works for specific project scope

## Open Implementation Decision

All-project conversation persistence should be decided before implementation:

- Use ephemeral all-project conversations for smaller first slice
- Or add explicit conversation scope persistence for complete history support

Recommended first slice: ephemeral all-project conversations, then add persistence later if it proves useful.
