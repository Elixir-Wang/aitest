"""
搜索工具 - 在辅助文档中搜索相关内容

实现简单的关键词匹配 + 上下文提取
"""

from langchain.tools import tool
from typing import List, Dict


@tool
def search_auxiliary_docs(query: str) -> str:
    """
    在辅助文档中搜索相关内容

    Args:
        query: 搜索关键词（如："验证码有效期"、"审批超时时间"）

    Returns:
        找到的相关段落（包含文档名和内容）
    """
    # 全局变量（会在调用时注入）
    auxiliary_documents = getattr(search_auxiliary_docs, "_auxiliary_documents", [])

    if not auxiliary_documents:
        return "未提供辅助文档"

    results = []
    for doc in auxiliary_documents:
        # 简单的关键词匹配
        content = doc.get("markdown_content", "")
        filename = doc.get("filename", "未命名文档")

        if query.lower() in content.lower():
            # 提取包含关键词的段落（带上下文）
            lines = content.split("\n")
            matched_sections = []

            for i, line in enumerate(lines):
                if query.lower() in line.lower():
                    # 提取前后3行作为上下文
                    start = max(0, i - 3)
                    end = min(len(lines), i + 4)
                    context = "\n".join(lines[start:end])

                    # 避免重复（如果多次匹配在相近位置）
                    if context not in matched_sections:
                        matched_sections.append(context)

            if matched_sections:
                # 每个文档最多返回前2个匹配段落
                for section in matched_sections[:2]:
                    results.append(
                        f"【文档: {filename}】\n{section}\n---"
                    )

    if not results:
        return "未找到相关内容"

    # 最多返回3个结果（避免 token 过多）
    return "\n\n".join(results[:3])


# 用于注入辅助文档的全局变量
search_auxiliary_docs._auxiliary_documents = []


__all__ = ["search_auxiliary_docs"]
