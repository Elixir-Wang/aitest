"""
项目级 conftest：共享 fixture 和 hooks。
"""
import pytest


def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line("markers", "smoke: 冒烟测试")
    config.addinivalue_line("markers", "regression: 回归测试")
    config.addinivalue_line("markers", "security: 安全测试")
    config.addinivalue_line("markers", "negative: 负面测试")
    config.addinivalue_line("markers", "boundary: 边界测试")
    config.addinivalue_line("markers", "positive: 正向测试")