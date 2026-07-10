# Page YAML Overlay State Design

## Goal

Persist overlays as nested page states for later POM generation. Root page elements
and overlay elements must never share the same state. Every overlay must record how
it was opened and must contain reusable, verified locators scoped to its container.

## Existing Problem

The current snapshot write path stores locator-rich elements, but flattens AX-only
Dialog and Popover controls into `states[0].elements`. This loses ownership and
allows a root button and overlay button with the same name to appear equivalent.

The repository already has nested-state semantics in `PageArtifactWriter`:
`children`, `triggered_by.from_state`, and `triggered_by.element_key`. The change
must reuse that model while retaining the locator and verification fields produced
by the current snapshot write path.

## Artifact Shape

```yaml
page:
  id: page-agentStore
  normalized_path: /agentStore

states:
  - id: page-agentStore__root__001
    type: root
    elements:
      - id: create-agent
        name: 创建智能体
        role: button
        action_type: click
        locators:
          - code: getByRole('button', { name: '创建智能体' })
            verification:
              checked: true
              unique: true
              visible: true
              match_count: 1

    children:
      - id: page-agentStore__dialog__001
        type: dialog
        triggered_by:
          from_state: page-agentStore__root__001
          element_key: create-agent
          action: click
          url_changed: false
          observed_url: https://www.cybotstar.cn/agentStore

        container:
          role: dialog
          name: 创建智能体
          locators:
            - code: getByRole('dialog', { name: '创建智能体' })
              verification:
                checked: true
                unique: true
                visible: true
                match_count: 1

        elements:
          - id: submit-create
            name: 创建
            role: button
            action_type: click
            locators:
              - code: getByRole('dialog', { name: '创建智能体' }).getByRole('button', { name: '创建' })
                verification:
                  checked: true
                  unique: true
                  visible: true
                  match_count: 1
        children: []
```

Supported overlay state types are `dialog`, `popover`, `menu`, and `drawer`.
Nested overlays use the currently active overlay state as their parent.

## Collection And Write Flow

1. A snapshot with `interaction_scope=page` writes only root-page elements.
2. A successful click records the source state ID, source element key, and the
   internal `parent_state_id` used by the state writer. `parent_state_id` is not
   persisted because `children` and `triggered_by.from_state` already encode it.
3. A following snapshot with `interaction_scope=overlay` creates or updates one
   child state beneath that source state.
4. The child receives `triggered_by` from the recorded click. Cross-level parent
   references remain invalid.
5. Overlay elements are written only to the child state. They are never copied
   into a root or ancestor state's `elements`.
6. Closing the overlay restores the parent state; a later page snapshot updates
   that parent rather than creating an overlay-free sibling state.

## Runtime Interaction Scope

Opening an overlay changes both artifact ownership and live action resolution.

1. After a click, the runner compares the before and after states and detects the
   highest active Dialog, Popover, Menu, or Drawer.
2. When an overlay is active, `interaction_scope` becomes `overlay` and the runner
   exposes only elements owned by that overlay state.
3. Subsequent click, fill, press, and scoped-query operations resolve visible
   matches inside the active overlay before considering the page.
4. A same-name element outside the overlay is not a candidate. If the active
   overlay itself contains multiple matching elements, the action fails with
   `locator_not_unique`; the runner never chooses the first match silently.
5. Page-level fallback is forbidden while an overlay remains active. A failed
   overlay lookup returns a scoped failure instead of operating on a same-name
   page element.
6. When the overlay closes, the runner restores its direct parent state and page
   elements become eligible again. Nested overlays restore one parent level at a
   time.

The transient `action_locator` may execute the currently observed element, but the
state transition and ownership rules do not depend on that locator. This keeps
runtime safety and persisted POM locators as separate contracts.

## Locator Contract

`action_locator` remains transient and is never persisted.

The overlay `container.locators` and every child element locator are verified as a
complete chain. A persisted POM locator must satisfy `count == 1` and
`visible == true` at observation time.

Candidate order:

1. Semantic container plus semantic element.
2. Stable container attribute (`data-testid`, `data-test`, stable ID, or explicit
   domain attribute) plus semantic element.
3. Stable attribute CSS for the complete target.
4. Structural CSS only as a low-confidence fallback with
   `needs_confirmation: true`.

XPath and transient action references are not persisted. If no reusable container
locator can be verified, the overlay state is retained for topology, but its
container and affected element locators are marked low confidence instead of being
presented as POM-ready.

## State Identity

An overlay state is matched by:

- direct parent state ID;
- `triggered_by.element_key`;
- overlay type;
- overlay container semantic identity when available.

DOM signatures remain supporting evidence, not the sole identity, because values,
timestamps, and validation messages can change without creating a new logical
overlay.

## Existing Artifacts

Do not heuristically migrate flattened YAML because AX-only elements may lack
enough ownership evidence. Re-exploring an affected page rebuilds its states using
the new ownership rules. Future writes must not reintroduce overlay elements into
root states.

## Error Handling

- Overlay snapshot without a recorded trigger: retain it in the raw diagnostic
  event only; do not write an orphan into the POM-ready page YAML.
- Trigger element missing from the parent: reject the parent link and preserve the
  observation for diagnostics.
- Multiple verified overlay containers: do not choose the first; mark the state
  ambiguous and require another observation or a stronger container selector.
- Multiple same-name elements inside one overlay: retain each element, but only
  locators verified unique within that overlay can be POM-ready.

## Verification

Focused contract tests must prove:

- root and overlay elements are stored in different states;
- `triggered_by` points to the direct parent and opening element;
- page and overlay buttons with the same name receive different complete locators;
- nested overlays preserve parent-child order;
- transient `action_locator` never appears in YAML;
- structural CSS cannot be promoted to a high-confidence primary locator;
- re-observing the same logical overlay merges it instead of duplicating it.
- actions prefer the active overlay when the page has a same-name element;
- a missing overlay target never falls back to a same-name page element;
- closing and nesting overlays restore the correct direct parent scope.

## Scope

This change affects page exploration snapshots, state association, locator
generation, YAML persistence, and focused artifact contract tests. POM code
generation itself is not changed; it consumes the improved state tree and locators.
