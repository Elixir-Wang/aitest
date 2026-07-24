"""
加载 YAML 测试用例数据。
"""
import os
import yaml


def load_cases(data_file: str) -> list:
    """
    从 YAML 文件加载测试用例列表。
    返回 list[dict]，每个 dict 包含 id, title, request, assertions 等字段。
    """
    if not os.path.exists(data_file):
        raise FileNotFoundError(f"数据文件不存在: {data_file}")
    with open(data_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    # 兼容 dict 格式
    cases = data.get("cases", data.get("test_cases", []))
    return cases
