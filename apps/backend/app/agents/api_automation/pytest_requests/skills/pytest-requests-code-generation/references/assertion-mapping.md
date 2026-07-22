# 断言映射

## 支持的断言类型

| 断言类型 | 用法 | 示例 |
|----------|------|------|
| status_code | `status_code: int` | `status_code: 200` |
| jsonpath_equals | `{"type":"jsonpath_equals","path":"$.code","expected":"000000"}` | 固定业务码 |
| jsonpath_exists | `{"type":"jsonpath_exists","path":"$.data.user_id","expected":true}` | 响应字段存在 |
| jsonpath_type | `{"type":"jsonpath_type","path":"$.data.user_id","expected":"string"}` | JSON 字段类型 |
| body_not_empty | `{"type":"body_not_empty","path":"$.data.items","expected":true}` | 响应体或数组非空 |
| header_exists | `{"type":"header_exists","path":"Content-Disposition","expected":true}` | Header 存在 |
| header_equals | `{"type":"header_equals","path":"Content-Type","expected":"application/json"}` | Header 等值 |
| content_type | `{"type":"content_type","path":"","expected":"application/json"}` | 响应媒体类型 |

## 断言工具

```python
# utils/assert_utils.py
import json
import re

def assert_response(response, assertions: list[dict]):
    """统一断言入口"""
    for rule in assertions:
        kind = rule["type"]
        path = rule.get("path", "")
        expected = rule.get("expected")
        if kind == "status_code":
            assert response.status_code == expected
        elif kind == "content_type":
            assert expected in response.headers.get("Content-Type", "")
        elif kind in {"jsonpath_exists", "jsonpath_equals", "jsonpath_type", "body_not_empty"}:
            body = response.json()
            exists, actual = get_json_path(body, path)
            assert exists, f"{kind}: JSONPath missing: {path}"
            if kind == "jsonpath_equals":
                assert actual == expected, f"{path}: expected {expected}, got {actual}"
            elif kind == "jsonpath_type":
                actual_type = "boolean" if isinstance(actual, bool) else "number" if isinstance(actual, (int, float)) else "string" if isinstance(actual, str) else "array" if isinstance(actual, list) else "object" if isinstance(actual, dict) else "null" if actual is None else type(actual).__name__
                assert actual_type == expected, f"{path}: expected type {expected}, got {actual_type}"
            elif kind == "body_not_empty":
                assert actual, f"{path} should not be empty"
        elif kind == "header_exists":
            assert path in response.headers
        elif kind == "header_equals":
            assert response.headers.get(path) == expected


def get_json_path(data: dict, path: str):
    """支持 $.foo.bar 形式的对象路径。"""
    keys = path.removeprefix("$.").split(".") if path else []
    value = data
    for key in keys:
        if isinstance(value, dict):
            if key not in value:
                return False, None
            value = value[key]
        else:
            return False, None
    return True, value
```

## YAML 断言示例

```yaml
cases:
  - name: 正常登录
    assertions:
      - type: status_code
        path: ""
        expected: 200
      - type: jsonpath_equals
        path: $.code
        expected: "000000"
      - type: jsonpath_exists
        path: $.data.user_id
        expected: true
      - type: jsonpath_type
        path: $.data.user_id
        expected: string
```
