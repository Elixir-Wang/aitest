"""
通用断言辅助函数：JSONPath 提取和检查。
"""
import json


def jsonpath_extract(obj, path: str):
    """
    从 JSON 对象中提取 JSONPath 值。
    支持简单路径如 $.code、$.data.user_cnt。
    """
    if not path.startswith("$"):
        raise ValueError(f"JSONPath 必须以 $ 开头: {path}")
    parts = path.lstrip("$.").split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                idx = int(part)
                current = current[idx]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def jsonpath_exists(obj, path: str) -> bool:
    """检查 JSONPath 路径是否存在"""
    return jsonpath_extract(obj, path) is not None