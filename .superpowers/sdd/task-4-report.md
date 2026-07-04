# Task 4 Report: PageArtifactValidator

## What Implemented

Created `apps/backend/app/services/page_exploration/page_artifact_validator.py` with:

- `ValidationIssue(code, message, rejected_state_title=None)`
- `ValidationResult(issues)` with `.ok` property
- `PageArtifactValidator` class with:
  - `MAX_DEPTH = 16` (class-level constant)
  - `compute_depth(obs, parent_depth)` — returns 1 for root, `parent_depth + 1` otherwise
  - `validate_observation(obs, existing_tree, parent_depth)` — validates depth, root rules, triggered_by, from_state resolution, parent equality, element_key resolution

## Tests

Created `apps/backend/tests/agents/page_exploration/test_page_artifact_validator.py` with 8 tests.

### RED (Step 2)

```
ModuleNotFoundError: No module named 'app.services.page_exploration.page_artifact_validator'
```

### GREEN (Step 4, after fix)

```
tests/agents/page_exploration/test_page_artifact_validator.py::test_root_observation_passes PASSED
tests/agents/page_exploration/test_page_artifact_validator.py::test_from_state_must_equal_parent PASSED
tests/agents/page_exploration/test_page_artifact_validator.py::test_cross_grandparent_rejected PASSED
tests/agents/page_exploration/test_page_artifact_validator.py::test_depth_exceeds_limit_rejected PASSED
tests/agents/page_exploration/test_page_artifact_validator.py::test_element_key_unresolved_rejected PASSED
tests/agents/page_exploration/test_page_artifact_validator.py::test_compute_depth_root PASSED
tests/agents/page_exploration/test_page_artifact_validator.py::test_compute_depth_child PASSED
tests/agents/page_exploration/test_page_artifact_validator.py::test_compute_depth_grandchild PASSED
============================== 8 passed in 0.15s ==============================
```

## Files Changed

| File | Change |
|------|--------|
| `apps/backend/app/services/page_exploration/page_artifact_validator.py` | Created (118 lines) |
| `apps/backend/tests/agents/page_exploration/test_page_artifact_validator.py` | Created (159 lines) |

## Self-Review

- [x] 8/8 tests pass with clean output
- [x] Commit message matches exactly: `feat(page_exploration): validation 层 + depth 护栏 + 跨祖父级拒绝`
- [x] `MAX_DEPTH = 16` is a module-level class constant (not method-local)
- [x] All reason codes match spec exactly: `depth_exceeds_safety_limit`, `root_must_have_no_triggered_by`, `missing_triggered_by`, `triggered_by_from_state_unresolved`, `triggered_by_from_state_not_parent`, `triggered_by_element_key_unresolved`
- [x] `compute_depth` returns 1 for root, `parent_depth + 1` for non-root

## Concerns

- **Test fix**: `test_depth_exceeds_limit_rejected` originally used `_root_obs()` which always returns depth=1 per spec, so it could never exceed 16. Changed to `_child_obs()` so depth = 20 + 1 = 21 > 16. This is a brief bug — the test code in the plan was incorrect. The fix is semantically correct and all other tests match the brief exactly.
