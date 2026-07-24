"""
封装 requests.Session，从环境变量读取 base URL 和鉴权信息。
"""
import os
import requests


class ApiClient:
    """API 客户端，从环境变量读取配置"""

    def __init__(self):
        self.base_url = os.environ.get("API_BASE_URL", "").rstrip("/")
        self.session = requests.Session()
        self._setup_auth()

    def _setup_auth(self):
        """从环境变量读取鉴权 header"""
        robot_key = os.environ.get("API_CYBERTRON_ROBOT_KEY", "")
        robot_token = os.environ.get("API_CYBERTRON_ROBOT_TOKEN", "")
        username = os.environ.get("API_CYBERTRON_USERNAME", "")
        if robot_key:
            self.session.headers["cybertron-robot-key"] = robot_key
        if robot_token:
            self.session.headers["cybertron-robot-token"] = robot_token
        if username:
            self.session.headers["username"] = username

    def request(self, method, path, **kwargs):
        """发送 HTTP 请求"""
        url = f"{self.base_url}{path}"
        return self.session.request(method.upper(), url, **kwargs)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)

    def patch(self, path, **kwargs):
        return self.request("PATCH", path, **kwargs)
