import pytest

from support.client import ApiClient


@pytest.fixture(scope="session")
def api_client():
    return ApiClient.from_environment()


