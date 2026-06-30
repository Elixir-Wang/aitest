"""URL 归一化工具"""

from urllib.parse import urlparse, unquote


def normalize_url(url: str) -> str:
    """
    归一化 URL 到统一格式

    规则:
    1. 提取 path（域名后面的部分）
    2. 去除 query 参数（?后面的）
    3. 去除 fragment（#后面的）
    4. URL 解码（%20 → 空格）
    5. 去除尾部斜杠（保留根路径的"/"）
    6. 转小写
    """
    parsed = urlparse(url)
    path = unquote(parsed.path)
    path = path.rstrip('/') or '/'
    return path.lower()


class URLNormalizer:
    """Compatibility wrapper for services that need normalization plus env labels."""

    def __init__(self, domain_mapping: dict[str, str] | None = None):
        self.domain_mapping = domain_mapping or {}

    def normalize(self, url: str) -> str:
        return normalize_url(url)

    def get_environment(self, url: str) -> str:
        hostname = urlparse(url).hostname or ""
        for env, base_url in self.domain_mapping.items():
            if hostname == (urlparse(base_url).hostname or ""):
                return env
        return "default"
