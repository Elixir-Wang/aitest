# apps/backend/app/agents/page_exploration/utils/url_normalize.py
"""URL 规范化: query 排序; hash 剥离; path lowercase; 主序 + 协议 + host 不区分将抛。"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


def normalize_for_compare(url: str) -> str:
    """query 排序、hash 去除、path 小写、其它原状。"""
    parts = urlsplit(url)
    # query 排序
    qsl = sorted(parse_qsl(parts.query, keep_blank_values=True))
    new_query = urlencode(qsl)
    new_path = parts.path.lower()
    # 去掉 fragment
    return urlunsplit((parts.scheme, parts.netloc, new_path, new_query, ""))


def urls_equal_modulo_hash(a: str, b: str) -> bool:
    return normalize_for_compare(a) == normalize_for_compare(b)
