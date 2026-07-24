"""API 模块 - openapi"""
from api.client import ApiClient


class OpenapiAPI:
    def __init__(self, client: ApiClient = None):
        self._client = client

    @property
    def api(self):
        return self._client or ApiClient()

    def post_v1(self, request_data=None, test_data=None, **kwargs):
        """智能体数据分析"""
        return self.api.request(
            {"method": "POST", "path": "/openapi/v1/agent/analysis/", **(request_data or {}), **kwargs},
            test_data,
        )
