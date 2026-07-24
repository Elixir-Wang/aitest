"""testcases 模块级 fixture"""
import pytest


@pytest.fixture
def user_credentials():
    """用户凭证 fixture"""
    return {
        "username": "test_user",
        "password": "test_password",
    }


@pytest.fixture
def admin_credentials():
    """管理员凭证 fixture"""
    return {
        "username": "admin",
        "password": "admin_password",
    }
