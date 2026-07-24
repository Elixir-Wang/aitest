"""YAML 测试数据加载"""
from __future__ import annotations

import os
from pathlib import Path

import yaml


def load_cases(test_file: str, data_file: str) -> list[dict]:
    """加载与测试文件同目录的 YAML 数据文件。

    Args:
        test_file: __file__ 传入的测试文件路径
        data_file: YAML 文件名（如 test_agent.yaml）

    Returns:
        测试用例列表
    """
    yaml_path = Path(test_file).parent / data_file
    if not yaml_path.is_file():
        return []
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("cases", data.get("test_cases", [data]))
    return []


def load_yaml(path: str | Path) -> dict | list | None:
    """加载任意 YAML 文件"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
