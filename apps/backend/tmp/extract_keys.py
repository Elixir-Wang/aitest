#!/usr/bin/env python3
"""
从大型 JSON 工具结果文件中提取 key 信息
输出每个 JSON 对象的顶层 key，以及嵌套对象/数组的 key 统计
"""
import json
import os
import sys
from pathlib import Path

LARGE_RESULTS_DIR = "/large_tool_results"
MAX_OUTPUT_BYTES = 50_000  # 单文件输出上限（避免再次被截断）


def collect_keys(obj, prefix="", depth=0, max_depth=10):
    """
    递归收集 JSON 中所有 key 路径
    返回: [(key_path, type, sample_value_str), ...]
    """
    results = []
    if depth > max_depth:
        return results

    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                results.append((path, "object", f"{{...}} (keys: {list(v.keys())[:5]}{'...' if len(v) > 5 else ''})"))
                results.extend(collect_keys(v, path, depth + 1, max_depth))
            elif isinstance(v, list):
                sample = v[0] if v else None
                sample_type = type(sample).__name__ if sample is not None else "empty"
                results.append((path, f"array[{len(v)}]", f"items: {sample_type}"))
                # 对数组前 3 项展开（避免大数组爆炸）
                for i, item in enumerate(v[:3]):
                    if isinstance(item, dict):
                        results.append((f"{path}[{i}]", "object", f"{{...}} (keys: {list(item.keys())[:5]}{'...' if len(item) > 5 else ''})"))
                        results.extend(collect_keys(item, f"{path}[{i}]", depth + 1, max_depth))
                    elif isinstance(item, list):
                        results.append((f"{path}[{i}]", f"array[{len(item)}]", ""))
                        results.extend(collect_keys(item, f"{path}[{i}]", depth + 1, max_depth))
                    else:
                        results.append((f"{path}[{i}]", type(item).__name__, repr(item)[:80]))
            else:
                val_str = repr(v)
                if len(val_str) > 80:
                    val_str = val_str[:80] + "..."
                results.append((path, type(v).__name__, val_str))
    return results


def summarize_file(filepath):
    """摘要一个 JSON 文件的 key 信息"""
    size = os.path.getsize(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    # 跳过空文件
    if not raw.strip():
        return f"文件: {filepath}\n状态: 空文件\n"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return f"文件: {filepath}\n状态: JSON 解析失败 - {e}\n原始大小: {size} 字节\n"

    lines = []
    lines.append(f"文件: {filepath}")
    lines.append(f"大小: {size} 字节")
    lines.append(f"顶层类型: {type(data).__name__}")

    if isinstance(data, dict):
        lines.append(f"顶层 keys ({len(data)}): {list(data.keys())}")
        lines.append("")
        keys = collect_keys(data, max_depth=4)
        # 按顶层 key 分组
        top_keys = list(data.keys())
        lines.append("=" * 80)
        lines.append("详细 key 路径（按顶层 key 分组，深度 ≤ 4）")
        lines.append("=" * 80)
        for top in top_keys:
            sub = [k for k in keys if k[0] == top or k[0].startswith(top + ".") or k[0].startswith(top + "[")]
            lines.append(f"\n[{top}] - 嵌套 keys 数量: {len(sub)}")
            for path, typ, sample in sub[:50]:  # 每个顶层 key 最多展示 50 条
                lines.append(f"  {path}  ::  {typ}  ::  {sample}")
            if len(sub) > 50:
                lines.append(f"  ... 还有 {len(sub) - 50} 条")
    elif isinstance(data, list):
        lines.append(f"数组长度: {len(data)}")
        if data:
            first = data[0]
            if isinstance(first, dict):
                lines.append(f"首项 keys: {list(first.keys())}")
            else:
                lines.append(f"首项类型: {type(first).__name__}")

    output = "\n".join(lines)
    if len(output) > MAX_OUTPUT_BYTES:
        output = output[:MAX_OUTPUT_BYTES] + f"\n\n... (输出超过 {MAX_OUTPUT_BYTES} 字节，已截断)"
    return output


def main():
    if not os.path.isdir(LARGE_RESULTS_DIR):
        print(f"目录不存在: {LARGE_RESULTS_DIR}")
        sys.exit(1)

    files = sorted(Path(LARGE_RESULTS_DIR).iterdir())
    if not files:
        print(f"目录为空: {LARGE_RESULTS_DIR}")
        sys.exit(0)

    print("=" * 80)
    print(f"扫描目录: {LARGE_RESULTS_DIR}（共 {len(files)} 个文件）")
    print("=" * 80)
    print()

    for f in files:
        if f.is_file():
            try:
                print(summarize_file(str(f)))
            except Exception as e:
                print(f"文件: {f}\n处理失败: {e}\n")
            print("\n" + "#" * 80 + "\n")


if __name__ == "__main__":
    main()
