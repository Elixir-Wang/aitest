# 请求映射

## 参数映射规则

| 参数来源 | 映射目标 | 示例 |
|----------|----------|------|
| path 参数 | URL 路径变量 | `/users/{id}` → `requests.get(f"/users/{user_id}")` |
| query 参数 | `params` | `?page=1&size=10` → `params={"page": 1, "size": 10}` |
| body 参数 | `json=` | POST body → `json=payload` |
| files 参数 | `data=` (multipart) | 文件上传 → `files={"file": open(...)}` |

## API 模块写法

```python
# api/module_user.py
from .client import get_session

class UserAPI:
    def __init__(self, session=None):
        self.session = session or get_session()

    def post_login(self, data: dict) -> requests.Response:
        """登录"""
        return self.session.post("/api/v1/login", json=data)

    def get_profile(self, user_id: int) -> requests.Response:
        """获取用户信息"""
        return self.session.get(f"/api/v1/users/{user_id}")
```

## 测试用例写法

```python
# testcases/user/login/test_login.py
import pytest
from api.module_user import UserAPI
from utils.data_loader import load_yaml
from utils.assert_utils import assert_response

TEST_DATA = load_yaml(__file__, "test_login.yaml")

@pytest.mark.parametrize("case", TEST_DATA["cases"])
def test_login(case):
    api = UserAPI()
    resp = api.post_login(data=case["request"])
    if case.get("oracle_status") in {"inferred", "needs_confirmation"}:
        from utils.observations import record_observation
        record_observation(case, resp)
    assert_response(resp, case["assertions"])
```

## YAML 数据格式

```yaml
# testcases/user/login/test_login.yaml
cases:
  - name: 正常登录
    request:
      username: "test_user"
      password: "password123"
    assertions:
      status_code: 200
      body:
        code: 0
        message: "success"

  - name: 密码错误
    request:
      username: "test_user"
      password: "wrong_password"
    assertions:
      status_code: 401
      body:
        code: 401
        message: "invalid credentials"
```
