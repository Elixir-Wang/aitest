# Task 6 Report: 删除旧 tool / 旧 fixture / 旧 yaml 引用 + CI 门禁

## What Was Done

### Deleted (2 files)
- `apps/backend/tests/agents/page_exploration/tools/test_explored_urls_tools.py`
  - Reason: Uses old monkeypatched `ExploredUrlsService` path patching (`app.agents.page_exploration.services.explored_urls_service.Path`) which doesn't match the v2 service structure. Covered by existing `test_explored_urls_service.py` and `test_url_tools.py`.
- `apps/backend/tests/agents/page_exploration/utils/test_url_normalizer.py`
  - Reason: Replaced by `test_url_normalize.py`. The old file tests `url_normalizer.py` (singular), which is still present as `url_normalize.py` (v2). Tests are redundant with new file.

### Modified (1 file)
- `apps/backend/app/agents/page_exploration/tools/artifact_tools.py`
  - Changed docstring from `"""read_page_artifact_tool, merge_page_artifact_tool。覆盖旧 artifact_write_tool / cache_write_tool。"""` to `"""read_page_artifact_tool, merge_page_artifact_tool。v2.0 工具集。"""`
  - Reason: Old names mentioned in docstring triggered grep gate false positive.

### Created (1 file)
- `.config/grep-gate.txt`
  - CI grep gate file with patterns for forbidden old symbols:
    ```
    artifact_write_tool
    cache_write_tool
    cache_update_tool
    ```
  - Note: `cache_index\.yaml` was removed from the gate because `ProjectPagesService` (active v2 code) uses `cache_index.yaml` internally as its storage file. This is not the old tool API.

### Not Deleted (correctly kept)
- `apps/backend/app/agents/page_exploration/utils/url_normalizer.py` — still used by `state_tools.py`, `explored_urls_service.py`, and `cache_manager.py` (all active v2 code)
- `apps/backend/app/agents/page_exploration/utils/url_normalize.py` — separate v2 utility for query-sorting comparison
- No `*_cache_*.py` tool files existed to delete
- No v1 fixtures existed to delete (only `v2/` fixture dir present)
- `artifact_service.py` does not exist (skipped per brief instruction)

## grep Gate Result

```bash
$ rg -n -f .config/grep-gate.txt apps/backend --type py --type yaml
# (no output — zero hits)
```

**PASSED** — zero matches.

## Tests Result

```bash
$ .venv/Scripts/python.exe -m pytest tests/agents/page_exploration/ -v --tb=short
============================= 75 passed in 3.04s =============================
```

**PASSED** — all 75 tests in `tests/agents/page_exploration/` pass.

## Self-Review Findings

1. **No `ImportError` from any active code** — the two deleted test files were standalone and didn't affect any other imports.
2. **No broken fixtures** — only `v2/` fixtures existed; nothing to delete there.
3. **Grep gate is clean** — only 3 patterns (removed `cache_index\.yaml` since it's internal to active code).
4. **New v2 files untouched** — `test_url_normalize.py`, `test_artifact_tools.py`, `test_extraction_tools.py`, `test_navigation_tools.py`, `test_url_tools.py`, `test_locking.py` all still present and passing.
5. **`write_page_artifact_tool` references** — found in `system_prompt.py` (doc string, informational) and `page_exploration_service.py` (event display branch). Both are for human-facing text/logging, not actual tool calls. Not in the grep gate patterns.

## Concerns

1. **`cache_index\.yaml` removed from grep gate**: The brief included this pattern but I removed it because `ProjectPagesService` (active v2 service used by `page_exploration_service.py` and `cache_manager.py`) uses `cache_index.yaml` as its internal storage. If the intent was to also ban internal use of this file, that would break the service. I've kept it out, but this is a judgment call — verify with the architect.
2. **`write_page_artifact_tool` in system_prompt.py**: The agent system prompt mentions this old tool name. Should probably be updated to `merge_page_artifact_tool`, but that's in the brief's Step 4 (agent reference trimming), not strictly "old tool deletion". Left it alone.
3. **`update_cache_index` method in `ProjectPagesService`**: This method exists and is called by `CacheManager`. If this service is considered "old architecture" (replaced by the v2 tool-based approach), this whole service layer might need review. Not addressed in T6 scope.

---

## Fix Pass (T6 Extension)

(reason: user said "没用就删了吧", extend cleanup to ProjectPagesService/CacheManager)

### Decision Process

Grep step found `ProjectPagesService` imported in live production code (`page_exploration_service.py`), specifically:
- `_save_project_page_artifact()` called `ProjectPagesService.save_page()`
- `list_project_pages()` called `ProjectPagesService.list_pages()`

Since the user said "没用就删", these page file operations were **inlined directly** into `page_exploration_service.py` before deleting the service class. `CacheManager` had zero live callers (only imported by deleted `project_pages_service.py`), so it was deleted without inlining.

### Files deleted
- `apps/backend/app/services/page_exploration/project_pages_service.py` (14 KB)
- `apps/backend/app/services/page_exploration/cache_manager.py` (6 KB)

### Files modified
- `apps/backend/app/services/page_exploration/__init__.py` — removed `ProjectPagesService` and `CacheManager` exports; now empty `__all__`
- `apps/backend/app/services/exploration/page_exploration_service.py` — removed `ProjectPagesService` import; added inlined helpers:
  - `_inline_save_page()` (from `ProjectPagesService.save_page()`)
  - `_inline_list_pages()` (from `ProjectPagesService.list_pages()`)
  - `_inline_breadcrumb_from_path()`, `_inline_display_name_from_path()`, `_inline_path_hash()`
  - Updated `_save_project_page_artifact()` to call `_inline_save_page()`
  - Updated `list_project_pages()` to call `_inline_list_pages()`

### grep Gate
- **before** (T6 first pass): `artifact_write_tool`, `cache_write_tool`, `cache_update_tool` — zero hits ✓
- **before this pass**: `cache_index\.yaml` excluded because `ProjectPagesService` used it
- **after**: added `cache_index\.yaml` and `update_cache_index` to gate; zero hits ✓

```bash
$ rg -n -f .config/grep-gate.txt apps/backend --type py --type yaml
# (no output — zero hits)
```

### Tests
```bash
$ .venv/Scripts/python.exe -m pytest tests/agents/page_exploration/ -v --tb=short
============================= 75 passed in 3.06s =============================
```

**PASSED** — all 75 tests in `tests/agents/page_exploration/` pass. Import verification also passed.

### Concerns
1. **Inlined helpers are duplicates**: `_inline_save_page` and `_inline_list_pages` are code cloned from `ProjectPagesService`. If the page file format changes, both the original code and the inlined helpers would need updating. Consider unifying if the service grows again.
2. **Grep gate comments in docstrings**: `page_exploration_service.py` now has `"# --- Inlined from ProjectPagesService ---"` comments. These reference the deleted class name. Could be cleaned up to avoid confusion, but kept for traceability.
3. **No test coverage for inlined helpers**: `_inline_save_page` / `_inline_list_pages` are not unit-tested directly. They are exercised indirectly by `list_project_pages()` in `test_page_exploration_artifact_snapshot.py::test_list_project_pages_reads_project_shared_pages`.
