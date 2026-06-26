"""
Dynamic Prompts for Page Exploration
"""

from typing import Dict, Any

USER_PROMPT_TEMPLATE = """
## 探索任务
**目标**: {target}
**范围**: 允许 {include_paths}，禁止 {exclude_paths}

## 当前状态
**页面**: {current_url}
**进度**: 已探索 {pages_explored} 页

{snapshot_info}

请识别场景并决策下一步操作。
"""


def format_snapshot_diff(diff: Dict[str, Any]) -> str:
    """格式化快照差异"""
    if diff['type'] == 'initial':
        return f"## 页面快照（初始）\n{format_elements(diff['snapshot']['elements'])}"

    parts = ["## 页面变化"]

    if diff.get('added'):
        parts.append(f"\n### 新增元素 ({len(diff['added'])}个)")
        parts.append(format_elements(diff['added']))

    if diff.get('removed'):
        parts.append(f"\n### 删除元素 ({len(diff['removed'])}个)")
        parts.append(format_elements(diff['removed']))

    if diff.get('modified'):
        parts.append(f"\n### 修改元素 ({len(diff['modified'])}个)")
        parts.append(format_elements(diff['modified']))

    return "\n".join(parts)


def format_elements(elements: list) -> str:
    """格式化元素列表"""
    lines = []
    for elem in elements[:10]:  # 最多显示10个
        lines.append(f"- {elem.get('name')} ({elem.get('role')})")

    if len(elements) > 10:
        lines.append(f"... 还有 {len(elements) - 10} 个元素")

    return "\n".join(lines)


def build_exploration_prompt(
    target: str,
    include_paths: list,
    exclude_paths: list,
    current_url: str,
    pages_explored: int,
    snapshot_diff: Dict[str, Any]
) -> str:
    """构建探索prompt"""

    snapshot_info = format_snapshot_diff(snapshot_diff)

    return USER_PROMPT_TEMPLATE.format(
        target=target,
        include_paths=", ".join(include_paths),
        exclude_paths=", ".join(exclude_paths),
        current_url=current_url,
        pages_explored=pages_explored,
        snapshot_info=snapshot_info
    )
