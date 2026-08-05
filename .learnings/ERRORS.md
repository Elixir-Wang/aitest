## [ERR-20260723-001] apply_patch_windows_pipe

**Logged**: 2026-07-23T00:00:00+08:00
**Priority**: low
**Status**: pending
**Area**: config

### Summary
Directly piping a patch here-string to the Windows apply_patch wrapper returned access denied.

### Error
```text
Access is denied.
```

### Context
- The wrapper is present but cannot be launched from this shell environment.
- Equivalent edits are being applied through the persistent file API.

### Suggested Fix
Use a working apply_patch executable or allow the Codex wrapper to launch.

### Metadata
- Reproducible: yes
- Related Files: none

---

## [ERR-20260801-001] self-review regex used unescaped question marks

**Logged**: 2026-08-01T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
A placeholder scan command failed because the regex alternation included `???` without escaping the question marks.

### Resolution
Use fixed-string searches or escape regex metacharacters when scanning documentation for literal placeholder text.

---

## [ERR-20260801-001] apply_patch context omitted adjacent class spacing

**Logged**: 2026-08-01T10:30:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
A combined patch failed because the schema insertion context assumed two blank lines before `ApiScenarioAiPlanNode`, while the current file had one.

### Resolution
Read the exact narrow target range and apply schema, table, and migration changes as separate patches.

---

## [ERR-20260728-003] frontend-biome-preexisting-formatting

**Logged**: 2026-07-28T00:00:00+08:00
**Priority**: low
**Status**: open
**Area**: frontend

### Summary
Targeted Biome checking reports formatting differences in the existing API scenario model and test files; this change did not modify those frontend files.

### Error
```text
Checked 2 files ... Found 2 errors.
```

### Context
- `node --test tests/api-scenario-model.test.mjs` passes.
- `npx biome check src/components/ai-testing/api-automation/api-scenario-model.mjs tests/api-scenario-model.test.mjs` fails on formatting only.
- The files already had unrelated working-tree modifications before this task.

### Suggested Fix
Review and format the frontend files in a separate cleanup change; do not mix unrelated formatting into the V2 backend fix.

### Metadata
- Reproducible: yes
- Related Files: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-model.mjs`, `apps/frontend/tests/api-scenario-model.test.mjs`

---

## [ERR-20260728-002] nonexistent-backend-test-path

**Logged**: 2026-07-28T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: testing

### Summary
A backend verification command referenced `apps/backend/tests/test_api_automation.py`, which is not present in the repository.

### Error
```text
ERROR: file or directory not found: apps/backend/tests/test_api_automation.py
```

### Suggested Fix
Enumerate test files with `rg --files apps/backend/tests` before composing the test command.

### Metadata
- Reproducible: yes
- Related Files: `apps/backend/tests`

---

## [ERR-20260728-001] assumed-design-spec-filename

**Logged**: 2026-07-28T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
Repository design-document inspection assumed a filename from a plan listing without verifying that the corresponding spec file existed.

### Error
```text
Get-Content: Cannot find path 'docs/superpowers/specs/2026-07-14-api-orchestration-editor-redesign-spec.md'
because it does not exist.
```

### Context
- The plan directory contained `2026-07-14-api-orchestration-editor-redesign.md`.
- The spec directory did not contain a matching `-spec.md` file.

### Suggested Fix
Enumerate the target directory with `Get-ChildItem` or `rg --files` before opening a guessed documentation path.

### Metadata
- Reproducible: yes
- Related Files: `docs/superpowers/specs`

---

## [ERR-20260728-001] rtk-windows-shell-proxy-compatibility

**Logged**: 2026-07-28T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
On Windows, `rtk` could not resolve Unix commands, and wrapping PowerShell through `rtk proxy` expanded the outer shell variables before the inner command ran.

### Error
```text
Failed to resolve 'sed' via PATH
The term '=apps/frontend/...' is not recognized
```

### Context
- Commands used `rtk sed`, `rtk ls`, and `rtk proxy pwsh -Command`.
- The workspace shell is PowerShell on Windows.

### Suggested Fix
Use `rtk` directly for supported cross-platform tools such as `rg`, `git`, and `npm`; use native PowerShell cmdlets directly for file slicing and directory inspection.

### Metadata
- Reproducible: yes
- Related Files: none

---

## [ERR-20260723-002] powershell-combined-regex-quoting

**Logged**: 2026-07-23T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
A combined PowerShell verification command used nested quotes in an `rg` regular expression and failed before running any checks.

### Error
```text
The string is missing the terminator: '.
```

### Context
- The command combined status discovery, Biome, Node tests, and TypeScript validation.
- A regex containing both single and double quotes made the PowerShell command fragile.

### Suggested Fix
Split verification into simple commands, or pass complex regular expressions as separate safely quoted arguments.

### Metadata
- Reproducible: yes
- Related Files: `apps/backend/app/services/ui_automation/service.py`

---

## [ERR-20260723-UIA-001] windows-short-long-path-relative-to

**Logged**: 2026-07-23T00:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: filesystem

### Summary
Windows 临时目录可能同时出现 8.3 短路径和规范长路径，直接使用 `Path.relative_to()` 会把同一目录误判为不相关路径。

### Error
```text
ValueError: '<long path>' is not in the subpath of '<8.3 short path>'
```

### Suggested Fix
持久化 suite 相对路径时先统一规范路径表示，或使用经过根目录安全校验的相对路径辅助函数；测试脚本不要直接对短路径根调用 `relative_to()`。

### Metadata
- Reproducible: yes
- Related Files: `apps/backend/app/agents/ui_automation/pytest_playwright/suite.py`

---

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
## [ERR-20260723-001] biome-parenthesized-path-on-windows

**Logged**: 2026-07-23T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
Running Biome through `cmd.exe` and `rtk` preserved literal quotes around a path containing parentheses, so Biome received an invalid Windows filename.

### Error
```text
文件名、目录名或卷标语法不正确。 (os error 123)
No files were processed in the specified paths.
```

### Context
- Command: `rtk npx biome check "src/app/(main)/test-cases/page.tsx"`
- Workspace: `apps/frontend`
- The diagnostic path contained literal quote characters.

### Suggested Fix
Run the configured directory-level `npm run check`, or invoke Biome through a shell that does not preserve the quotes in the argument.

### Metadata
- Reproducible: yes
- Related Files: `apps/frontend/src/app/(main)/test-cases/page.tsx`

---

## [ERR-20260730-001] sqlite-debug-query-selected-secret-columns

**Logged**: 2026-07-30T17:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: security

### Summary
An ad hoc SQLite diagnostic query selected every column from model provider records, which included plaintext credential fields unrelated to the debugging task.

### Error
```text
The query used SELECT * against a configuration table containing secret columns.
```

### Context
- The goal was only to identify the model assigned to `performance_report_analysis`.
- Selecting all columns exposed unrelated credential values in command output.

### Suggested Fix
For configuration diagnostics, explicitly select only required non-secret columns such as `id`, `provider`, `model`, `status`, and assignment identifiers. Never use `SELECT *` on tables that may contain credentials.

### Metadata
- Reproducible: yes
- Related Files: `apps/backend/data/ai_testing.db`

---
## 2026-07-30 - Windows `start` title quoting failed

**Status**: resolved
**Area**: tooling

### Summary
Starting the frontend with `cmd.exe start` misparsed the quoted window title as a filesystem path.

### Error
```text
The system cannot find the file \frontend-dev\.
```

### Context
- The command nested quoted `cmd.exe /c` arguments inside the shell tool.
- The task only needed a hidden background process for visual verification.

### Suggested Fix
Prefer a detached Node child process or PowerShell `Start-Process -WindowStyle Hidden` when available instead of nested `cmd.exe start` quoting.

### Metadata
- Reproducible: yes
- Related Files: `apps/frontend/package.json`

## [ERR-20260730-001] PowerShell symbol lookup returned multiple matches

**Logged**: 2026-07-30T19:15:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
Subtracting a line offset from `Select-String.LineNumber` failed because multiple matches returned an array.

### Error
`Method invocation failed because [System.Object[]] does not contain a method named op_Subtraction.`

### Resolution
Use `rg -n` with an exact symbol and select a single match before calculating line offsets.

---

## [ERR-20260730-002] apply_patch context used an inaccurate test name

**Logged**: 2026-07-30T19:15:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
A patch failed because the expected test function name did not match the repository.

### Resolution
Locate the exact insertion point with `rg -n '^def test_generated_scenario_runtime'` before applying the patch.

---

## [ERR-20260730-003] apply_patch context assumed stale scenario serializer

**Logged**: 2026-07-30T20:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
A patch failed because the current uncommitted `toScenarioStepInput` implementation used fallback expressions that differed from the previously inspected context.

### Resolution
Read the exact narrow function range immediately before patching files with concurrent uncommitted changes, then apply smaller patches.

---
## [ERR-20260803-001] rtk_read_command_misuse

**Logged**: 2026-08-03T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
Attempted to invoke Unix `cat` through RTK and later used unsupported `rtk read --line` options on Windows.

### Error
```text
Binary 'cat' not found on PATH
Binary 'read' not found on PATH
```

### Resolution
Use `rtk read <file> -m <lines>` for whole-file reads and `rtk grep <pattern> <path> -A/-B` for focused context.

---

## [ERR-20260803-002] unix-sed-unavailable

**Logged**: 2026-08-03T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The Windows workspace does not provide `sed`.

### Error
`rtk: program not found`

### Resolution
Use Node filesystem reads for line ranges instead of assuming Unix utilities.

### Metadata
- Source: error
- Tags: windows, shell, sed

---

## [ERR-20260804-001] powershell-path-and-special-directory-quoting

**Logged**: 2026-08-04T10:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The shell could not resolve `powershell.exe` by name, and an unquoted Next.js path containing `(main)` was parsed as a PowerShell expression.

### Error
`program not found` and `The term 'main' is not recognized`.

### Resolution
Invoke Windows PowerShell by absolute path and single-quote repository paths containing parentheses before passing them to RTK commands.

### Metadata
- Source: error
- Tags: windows, powershell, paths, rtk

---

## [ERR-20260804-002] backend-test-missing-websocket

**Logged**: 2026-08-04T10:20:00+08:00
**Priority**: medium
**Status**: open
**Area**: testing

### Summary
The focused UI automation API test collection fails before test execution because the active Python environment lacks the `websocket` module imported by `app.services.ui_automation.live_view`.

### Error
`ModuleNotFoundError: No module named 'websocket'`

### Next Action
Use the repository's configured backend runtime or install the declared dependency before rerunning API tests. Do not change production imports solely to bypass the missing test dependency.

### Metadata
- Source: error
- Tags: backend, pytest, dependency, websocket

---

## [ERR-20260805-001] windows-shell-resolution-and-inline-python-quoting

**Logged**: 2026-08-05T16:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The shell could not resolve `powershell.exe` by name, Unix `tail` was unavailable, and an inline Python SQLite query was corrupted by nested PowerShell quoting.

### Error
```text
program not found
Binary 'tail' not found on PATH
SyntaxError while parsing the inline Python command
```

### Resolution
Invoke Windows PowerShell by absolute path, use `rtk proxy` for PowerShell-native file operations, and pass quote-sensitive Python commands directly as `rtk` argument arrays instead of nesting them inside `powershell -Command`.

### Metadata
- Source: error
- Tags: windows, powershell, rtk, python, quoting
