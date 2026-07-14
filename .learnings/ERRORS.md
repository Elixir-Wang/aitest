# Errors

## [ERR-20260714-006] rtk-pytest-interpreter-mismatch

**Logged**: 2026-07-14T16:20:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
`rtk pytest` used the system Python interpreter instead of the backend `.venv`, causing project dependency import failures.

### Error
```text
ModuleNotFoundError: No module named 'langchain_deepseek'
```

### Context
- The backend project dependencies are installed in `apps/backend/.venv`.
- The focused generator tests passed when run with `.venv\Scripts\python.exe -m pytest`.

### Suggested Fix
Use `rtk proxy .\\.venv\\Scripts\\python.exe -m pytest ...` for backend tests when `rtk pytest` resolves the wrong interpreter.

### Metadata
- Reproducible: yes
- Related Files: `apps/backend/pyproject.toml`

---

## [ERR-20260714-005] rtk-tree-missing-on-windows

**Logged**: 2026-07-14T16:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
`rtk tree` delegated to an unavailable native `tree` binary in the Windows workspace.

### Error
```text
rtk: tree command not found. Install it first.
```

### Context
- Attempted to inspect the API automation package hierarchy with `rtk tree`.
- The workspace provides PowerShell and `rg`, but no native `tree` executable.

### Suggested Fix
Use `rtk find <path>` for compact file discovery or wrap `Get-ChildItem` with `rtk proxy pwsh -NoProfile -Command` when hierarchy details are required.

### Metadata
- Reproducible: yes
- Related Files: `C:\Users\hongbao.wang\.codex\RTK.md`

---

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

## [ERR-20260714-004] incorrect-skill-root-expansion

**Logged**: 2026-07-14T10:30:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
Expanded the `self-improvement` skill from the wrong skill root and attempted to read a nonexistent path.

### Error
```text
Cannot find path 'C:\Users\hongbao.wang\.codex\skills\.system\self-improving-agent\SKILL.md'
```

### Context
- The skill entry uses root alias `r0`, which maps directly to `C:\Users\hongbao.wang\.codex\skills`.
- The `.system` directory was incorrectly inserted while expanding the path.

### Suggested Fix
Expand skill paths strictly from the root alias table before reading `SKILL.md`.

### Metadata
- Reproducible: yes
- Related Files: none

---

## [ERR-20260714-003] windows-shell-and-rtk-command-resolution

**Logged**: 2026-07-14T10:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The workspace exposes `pwsh` but not `powershell.exe`, and `rtk cat` cannot resolve a Unix `cat` binary on this Windows PATH.

### Error
```text
program not found
rtk: Failed to resolve 'cat' via PATH
```

### Context
- Initial repository inspection used `powershell.exe -Command` and failed before execution.
- Reading files with `rtk cat` also failed because `cat` is unavailable.

### Suggested Fix
Use `pwsh -NoProfile -Command` as the shell and wrap PowerShell-native reads with `rtk proxy pwsh -NoProfile -Command`.

### Metadata
- Reproducible: yes
- Related Files: `C:\Users\hongbao.wang\.codex\RTK.md`

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
