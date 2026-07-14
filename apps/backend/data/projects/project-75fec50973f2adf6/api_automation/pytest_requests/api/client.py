"""API 客户端封装"""
import os
import re
from typing import Any

import requests


class ApiClient:
    """基于 requests.Session 的 API 客户端"""

    def __init__(self, base_url: str = "", timeout: int = 30):
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.timeout = timeout
        self.session = requests.Session()
        self._setup_auth()

    def _setup_auth(self) -> None:
        """设置认证信息"""
        bearer = os.environ.get("API_AUTH_BEARER", "")
        if bearer:
            self.session.headers["Authorization"] = f"Bearer {bearer}"

        # 支持自定义 header
        for key, value in os.environ.items():
            if key.startswith("API_HEADER_") and value:
                header_name = key.removeprefix("API_HEADER_").replace("_", "-")
                self.session.headers[header_name] = value

    def request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None,
        data: Any = None,
        headers: dict | None = None,
        **kwargs,
    ) -> requests.Response:
        """发送 HTTP 请求

        Args:
            method: HTTP 方法
            path: 请求路径
            params: URL 参数
            json: JSON body
            data: form data
            headers: 请求头

        Returns:
            requests.Response 对象
        """
        url = f"{self.base_url}{path}"
        merged_headers = {**(headers or {})}

        return self.session.request(
            method=method.upper(),
            url=url,
            params=params,
            json=json,
            data=data,
            headers=merged_headers or None,
            timeout=kwargs.get("timeout", self.timeout),
        )

    def get(self, path: str, **kwargs) -> requests.Response:
        """GET 请求"""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        """POST 请求"""
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        """PUT 请求"""
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        """DELETE 请求"""
        return self.request("DELETE", path, **kwargs)

    def patch(self, path: str, **kwargs) -> requests.Response:
        """PATCH 请求"""
        return self.request("PATCH", path, **kwargs)


# 全局客户端实例
_client: ApiClient | None = None


def get_client() -> ApiClient:
    """获取全局客户端实例"""
    global _client
    if _client is None:
        base_url = os.environ.get("API_BASE_URL", "")
        if not base_url:
            raise RuntimeError("API_BASE_URL environment variable is required")
        _client = ApiClient(base_url=base_url)
    return _client
