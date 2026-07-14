"""API 模块封装 - v1"""
from api.client import ApiClient


class V1API:
    """V1 模块 API"""

    def __init__(self, client: ApiClient | None = None):
        self.client = client

    @property
    def api(self):
        if self.client is None:
            from api.client import get_client
            return get_client()
        return self.client

    def post_agent(self, **kwargs) -> object:
        """智能体数据分析"""
        return self.api.post("/openapi/v1/agent/analysis/", **kwargs)
