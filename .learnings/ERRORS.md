# Errors

## [ERR-20260713-001] uv-run-pytest

**Logged**: 2026-07-13T15:50:00+08:00
**Priority**: medium
**Status**: pending
**Area**: tests

### Summary
`uv run pytest` attempted to repair the active backend virtual environment and failed on a locked `websockets` binary.

### Error
```text
Failed to install websockets-15.0.1: failed to rename speedups.cp313-win_amd64.pyd: access denied (os error 5)
```

### Context
- Command: `rtk uv run pytest tests/agents/page_exploration/tools/test_runtime_identity.py -q`
- Workspace: `apps/backend`
- The backend virtual environment may be in use by a running process.

### Suggested Fix
Run tests with the existing `.venv/Scripts/python.exe -m pytest` instead of allowing `uv run` to synchronize an active environment.

### Metadata
- Reproducible: unknown
- Related Files: `apps/backend/.venv`

---

## [ERR-20260713-002] nested-powershell-variable-expansion

**Logged**: 2026-07-13T16:20:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
Nested `pwsh -Command` invocation expanded `$` variables in the outer shell and produced an invalid inner PowerShell command.

### Error
```text
ParserError: Missing type name after '['.
```

### Context
- Attempted to pass `$p`, `$c`, and `$c[100..125]` through an outer double-quoted PowerShell command.
- The outer shell removed the variable names before the inner `pwsh` parsed the script.

### Suggested Fix
Avoid nested PowerShell for simple reads. When nesting is required, use an encoded command, a script file, or escape `$` variables explicitly.

### Metadata
- Reproducible: yes
- Related Files: none

---
