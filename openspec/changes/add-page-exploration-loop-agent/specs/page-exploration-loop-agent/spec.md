# Page Exploration Loop Agent Specification

## ADDED Requirements

### Requirement: Independent Loop agent boundary
The system SHALL provide a Loop exploration Agent under `apps/backend/app/agents/page_exploration_loop/` as an independent package. The Loop package MUST NOT change the existing `apps/backend/app/agents/page_exploration/` Agent, prompts, state implementation, or `goal`/`autonomous` semantics.

#### Scenario: Existing exploration modes remain compatible
- **WHEN** a run is created with `goal` or `autonomous`
- **THEN** the existing execution path and output behavior are used
- **AND** no Loop-specific frontier, state table, or merge policy changes that run's behavior.

#### Scenario: Loop mode selects the independent package
- **WHEN** a run is created with `exploration_mode = "loop"`
- **THEN** the service invokes the Loop package and its explicit orchestrator
- **AND** the existing page exploration Agent is not used as the Loop controller.

### Requirement: Explicit exploration loop
The Loop mode SHALL maintain a durable frontier of page states and candidate actions. The system MUST select, observe, decide, execute, verify, persist, and expand in a bounded loop.

#### Scenario: Frontier drives the next action
- **WHEN** the current state has pending candidate actions
- **THEN** the scheduler selects a frontier item according to deterministic priority and budget rules
- **AND** the Agent receives only the selected state and valid candidates for local decision.

#### Scenario: Empty frontier completes exploration
- **WHEN** the frontier is empty
- **AND** no pending verification or cleanup remains
- **THEN** the Loop run proceeds to final coverage, merge, and report generation.

#### Scenario: Budget stops exploration
- **WHEN** `max_pages`, `max_actions`, or `timeout_minutes` is reached
- **THEN** the system stops adding work
- **AND** records a structured stop reason
- **AND** retains all artifacts generated before the stop.

### Requirement: Stable state and action identity
The system SHALL deduplicate pages, states, elements, and transitions using stable identities that do not depend on transient observation IDs, DOM IDs, timestamps, or random values.

#### Scenario: Re-observing the same state is idempotent
- **WHEN** two observations produce the same normalized URL, title, interactive structure, overlay signature, and relevant selection state
- **THEN** they resolve to one state identity
- **AND** the second observation updates last-seen metadata without creating a duplicate state.

#### Scenario: Previously verified action is not repeated indefinitely
- **WHEN** a state and element action has already been verified
- **THEN** the scheduler marks that frontier item complete
- **AND** it does not re-enqueue the same item unless the state identity materially changes.

### Requirement: Constrained Agent decision
The Loop Agent SHALL return a structured action decision referencing a server-provided candidate. It MUST NOT return arbitrary locators, write project artifacts, or declare global completion.

#### Scenario: Invalid candidate reference is rejected
- **WHEN** the Agent returns an element key that is not in the current candidate set
- **THEN** the system rejects the decision
- **AND** records an `invalid_decision` failure
- **AND** does not execute a browser action.

#### Scenario: High-risk action requests approval
- **WHEN** the selected action is classified as `high` or `destructive`
- **AND** the run policy does not authorize automatic execution
- **THEN** the system creates a human-confirmation blocker
- **AND** does not execute the action until approval is recorded.

### Requirement: Action verification loop
Every executed click, fill, navigate, or equivalent action SHALL have a post-action verification result independent of the browser tool's transport success flag.

#### Scenario: Verified action creates a transition
- **WHEN** the expected URL, overlay, Toast, form value, or state change is observed
- **THEN** the action is marked `verified`
- **AND** the system records before-state, after-state, action, evidence, and transition.

#### Scenario: No-effect action is bounded
- **WHEN** an action reports transport success but no expected state change is observed
- **THEN** the system performs at most one directed re-observation
- **AND** marks the action `no_effect` if no change is found
- **AND** does not retry indefinitely.

#### Scenario: Tool failure is classified
- **WHEN** a browser action fails
- **THEN** the system records the structured failure type and recovery attempt
- **AND** retries the same state/element/action at most the configured limit
- **AND** marks it `blocked` or `failed` after the limit.

### Requirement: Project artifact generation
A completed, partial, blocked, or cancelled Loop run SHALL retain project-scoped page, state, element, interaction, edge, event, and report artifacts using the existing page exploration storage root and artifact registration contract.

#### Scenario: Loop run writes auditable artifacts
- **WHEN** a Loop action or state is processed
- **THEN** the run writes a structured transition/event record
- **AND** the record contains only redacted values, stable identities, and evidence references.

#### Scenario: Partial run retains useful output
- **WHEN** the run stops because of timeout, cancellation, budget, or blocker
- **THEN** artifacts collected before the stop remain available
- **AND** the report includes the stop reason, pending frontier, blockers, and cleanup status.

### Requirement: Baseline and deterministic merge
Before a Loop run changes project artifacts, the system SHALL capture an immutable baseline. Completion SHALL merge Loop deltas into existing project artifacts by stable identity without silently overwriting incompatible facts.

#### Scenario: New fact is added
- **WHEN** a Loop delta contains a page, element, state, interaction, or edge absent from the baseline
- **THEN** the fact is added to the project artifact
- **AND** the merge summary increments `added`.

#### Scenario: Duplicate fact is idempotent
- **WHEN** a Loop delta fact is identical to an existing stable fact
- **THEN** no duplicate fact is written
- **AND** the merge summary increments `duplicate`.

#### Scenario: Compatible fact is updated
- **WHEN** the stable identity matches and non-conflicting metadata adds information
- **THEN** the project artifact is updated deterministically
- **AND** the merge summary increments `updated`.

#### Scenario: Conflicting fact is preserved for review
- **WHEN** the stable identity matches but key identity or semantic fields conflict
- **THEN** the existing project fact is not overwritten
- **AND** baseline, delta, and conflict details are written under the run's `conflicts` directory
- **AND** the run cannot be reported as fully completed.

#### Scenario: Repeating merge is safe
- **WHEN** the same Loop run is merged more than once
- **THEN** the result is identical to a single merge
- **AND** no duplicate facts, edges, or merge-history entries are created.

### Requirement: Recovery and cancellation
The Loop state SHALL be checkpointed sufficiently to resume after process interruption, user stop, or transient browser failure.

#### Scenario: Interrupted run resumes frontier
- **WHEN** a running Loop task is recovered
- **THEN** the system loads the latest valid checkpoint
- **AND** resumes from pending frontier items and unresolved cleanup
- **AND** does not re-execute verified destructive actions.

#### Scenario: User cancellation is terminal for the current attempt
- **WHEN** the user stops a Loop run
- **THEN** the scheduler stops scheduling new actions
- **AND** records `user_cancelled`
- **AND** runs the configured cleanup path before final report registration.

### Requirement: Coverage and completion reporting
The system SHALL report page, state, element, transition, action, pending, blocker, and cleanup coverage separately. It MUST NOT claim full website exploration solely because URL count or model todo state is complete.

#### Scenario: Coverage is computed from persisted facts
- **WHEN** the Loop run reaches finalization
- **THEN** coverage is computed from persisted frontier, states, elements, transitions, verification records, and cleanup records
- **AND** the report includes all remaining pending and blocked items.

#### Scenario: Cleanup failure prevents full completion
- **WHEN** Loop-created test data remains unverified or undeleted
- **THEN** the final result is partial or blocked
- **AND** the report explicitly identifies cleanup pending items.

### Requirement: Existing security and scope controls apply
Loop exploration SHALL enforce environment ownership, login strategy, include scope, forbidden paths, sensitive-data redaction, and existing run cancellation/authentication boundaries.

#### Scenario: Forbidden path is discovered
- **WHEN** a candidate URL matches a forbidden path
- **THEN** the system records a scope blocker
- **AND** does not navigate to that URL.

#### Scenario: Sensitive value is observed
- **WHEN** a snapshot or action contains a password, token, cookie, secret, or personal sensitive value
- **THEN** the stored artifact contains redacted metadata or a redaction marker
- **AND** the raw sensitive value is not written to project artifacts or timeline summaries.
