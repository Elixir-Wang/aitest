# 断言映射

## 支持的断言类型

| 断言类型 | 用法 | 示例 |
|----------|------|------|
| status_code | `status_code: int` | `status_code: 200` |
| body 字段等值 | `body.field: value` | `body.code: 0` |
| body 字段存在 | `body.field_exists: path` | `body.user_id_exists: true` |
| body 非空 | `body_not_empty: [path1, path2]` | `body_not_empty: ["data.items"]` |
| header 存在 | `header_exists: Header-Name` | `header_exists: Content-Type` |
| header 等值 | `header.Header-Name: value` | `header.Content-Type: application/json` |
| content_type | `content_type: text` | `content_type: application/json` |
| response_time | `response_time_lt: ms` | `response_time_lt: 500` |

## 断言工具

```python
# utils/assert_utils.py
import json
import re

def assert_response(response, assertions: dict):
    """统一断言入口"""
    if "status_code" in assertions:
        assert response.status_code == assertions["status_code"]

    if "content_type" in assertions:
        assert assertions["content_type"] in response.headers.get("Content-Type", "")

    if "body" in assertions:
        body = response.json()
        for key, expected in assertions["body"].items():
            actual = get_nested_value(body, key)
            assert actual == expected, f"body.{key}: expected {expected}, got {actual}"

    if "body_not_empty" in assertions:
        body = response.json()
        for path in assertions["body_not_empty"]:
            value = get_nested_value(body, path)
            assert value, f"body.{path} should not be empty"

    if "header" in assertions:
        for key, expected in assertions["header"].items():
            assert response.headers.get(key) == expected

    if "response_time_lt" in assertions:
        assert response.elapsed.total_seconds() * 1000 < assertions["response_time_lt"]


def get_nested_value(data: dict, path: str):
    """支持点号路径的嵌套取值"""
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value
```

## YAML 断言示例

```yaml
cases:
  - name: 正常登录
    request:
      username: "test"
      password: "123"
    assertions:
      status_code: 200
      body:
        code: 0
        message: "success"
        data.token_exists: true
      header:
        Content-Type: application/json

  - name: 响应时间要求
    assertions:
      status_code: 200
      response_time_lt: 500
```
