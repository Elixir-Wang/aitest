"""
测试用例级 conftest：提供接口测试共享 fixture。
"""
import pytest
from api.client import ApiClient


@pytest.fixture(scope="session")
def api_client():
    """共享 API 客户端实例"""
    return ApiClient()


@pytest.fixture
def default_headers():
    """默认请求头，可在测试中覆盖"""
    return {}


@pytest.fixture
def api_request(api_client):
    """便捷 fixture 用于发送请求"""
    def _request(method, path, **kwargs):
        return api_client.request(method, path, **kwargs)
    return _request