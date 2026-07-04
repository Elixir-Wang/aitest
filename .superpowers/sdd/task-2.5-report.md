# Task 2.5 Report: `url_normalize`

## What Implemented

- `normalize_for_compare(url: str) -> str`: 使用 `urllib.parse` 解析 URL，query 参数按字母排序，hash fragment 剥离，path 小写，其余部分（scheme、netloc）保持不变
- `urls_equal_modulo_hash(a: str, b: str) -> bool`: 对两个 URL 调用 `normalize_for_compare` 后比较

## Tests

### RED (before implementation)

```
ERROR collecting test_url_normalize.py
ModuleNotFoundError: No module named 'app.agents.page_exploration.utils.url_normalize'
```

### GREEN (after implementation)

```
============================= test session starts =============================
platform win32 -- Python 3.13.7, pytest-9.0.1, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: D:\project\test_project\apps\backend
configfile: pyproject.toml
plugins: anyio-4.13.0, langsmith-0.8.8
collecting ... collected 6 items

test_url_normalize.py::test_normalize_query_order_independent PASSED [ 16%]
test_url_normalize.py::test_normalize_drops_hash PASSED               [ 33%]
test_url_normalize.py::test_normalize_keeps_fragment PASSED            [ 50%]
test_url_normalize.py::test_normalize_lowercase_path PASSED            [ 66%]
test_url_normalize.py::test_urls_equal_modulo_hash_true PASSED         [ 83%]
test_url_normalize.py::test_urls_equal_modulo_hash_false PASSED        [100%]

============================== 6 passed in 0.08s ==============================
```

## Files Changed

| File | Action |
|------|--------|
| `apps/backend/app/agents/page_exploration/utils/url_normalize.py` | Created |
| `apps/backend/tests/agents/page_exploration/utils/test_url_normalize.py` | Created |

## Self-Review

- [x] 6/6 tests pass with clean output
- [x] Commit message matches exactly: `feat(page_exploration): url_normalize (query 排序 + hash 剥离)`
- [x] Implementation is pure-function (no side effects, no global state)
- [x] Uses only `urllib.parse` as required

## Commit SHA

```
eb5f94f11 - feat(page_exploration): url_normalize (query 排序 + hash 剥离)
```

## Concerns

None. Implementation is straightforward and matches the brief exactly.
