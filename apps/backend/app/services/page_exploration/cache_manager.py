"""
Cache Manager - 纯编程逻辑，无LLM

管理探索缓存，过滤已缓存的页面
"""

from pathlib import Path
from typing import List, Dict, Any
import logging

from app.agents.page_exploration.utils.url_normalizer import URLNormalizer
from app.services.page_exploration.project_pages_service import ProjectPagesService

logger = logging.getLogger(__name__)


class CacheManager:
    """
    缓存管理器

    纯编程逻辑，不依赖LLM。
    负责过滤已缓存的页面，避免重复探索。
    """

    def __init__(self, pages_service: ProjectPagesService, url_normalizer: URLNormalizer):
        """
        初始化缓存管理器

        Args:
            pages_service: 项目级pages服务
            url_normalizer: URL归一化器
        """
        self.pages_service = pages_service
        self.normalizer = url_normalizer

    def filter_cached_pages(self, urls: List[str]) -> Dict[str, List]:
        """
        过滤已缓存的页面（纯编程逻辑，0次LLM调用）

        Args:
            urls: 待检查的URL列表

        Returns:
            {
                'to_explore': [...],  # 需要探索的URL
                'cached': [...]       # 已缓存的页面信息
            }
        """
        to_explore = []
        cached = []

        for url in urls:
            # 1. 归一化URL（编程逻辑）
            normalized_path = self.normalizer.normalize(url)

            # 2. 检查缓存（编程逻辑）
            cache_result = self.pages_service.check_cache(normalized_path)

            # 3. 判断是否有效（编程逻辑）
            if cache_result['cache_hit'] and self._is_cache_valid(cache_result):
                # 缓存命中且有效 - 编程决策，跳过探索
                cached.append({
                    'url': url,
                    'normalized_path': normalized_path,
                    'page_id': cache_result['page_id'],
                    'page_file': cache_result['page_file'],
                    'last_explored_at': cache_result.get('last_explored_at'),
                    'reason': 'cache_hit'
                })
                logger.info(f"✓ 缓存命中: {normalized_path}, 跳过探索")
            else:
                # 缓存未命中或无效 - 编程决策，加入探索列表
                to_explore.append(url)
                reason = 'cache_miss' if not cache_result['cache_hit'] else 'cache_invalid'
                logger.info(f"✗ 缓存状态: {reason}, {normalized_path}, 需要探索")

        logger.info(f"缓存过滤完成: 总计 {len(urls)} 页, 缓存命中 {len(cached)} 页, 需探索 {len(to_explore)} 页")

        return {
            'to_explore': to_explore,
            'cached': cached
        }

    def _is_cache_valid(self, cache_result: Dict[str, Any]) -> bool:
        """
        判断缓存是否有效（纯编程逻辑）

        Args:
            cache_result: 缓存检查结果

        Returns:
            True if 缓存有效
        """
        # 规则1: 必须有page_file
        if 'page_file' not in cache_result:
            return False

        # 规则2: 文件必须存在
        page_file = Path(cache_result['page_file'])
        if not page_file.exists():
            logger.warning(f"缓存文件不存在: {page_file}")
            return False

        # 规则3: 文件大小不能为0
        if page_file.stat().st_size == 0:
            logger.warning(f"缓存文件为空: {page_file}")
            return False

        # 规则4: （可选）检查缓存时间
        # 这里可以添加时间检查逻辑
        # 例如：如果缓存超过7天，标记为无效
        # last_explored = cache_result.get('last_explored_at')
        # if is_too_old(last_explored, max_age_days=7):
        #     return False

        return True

    def update_cache_after_exploration(
        self,
        url: str,
        page_id: str,
        run_id: str,
        page_signature: Dict[str, Any]
    ) -> bool:
        """
        探索完成后更新缓存索引（编程逻辑）

        Args:
            url: 页面URL
            page_id: 页面ID
            run_id: 运行ID
            page_signature: 页面签名

        Returns:
            是否更新成功
        """
        # 归一化URL
        normalized_path = self.normalizer.normalize(url)

        # 获取环境标识
        env = self.normalizer.get_environment(url)

        # 更新缓存索引
        success = self.pages_service.update_cache_index(
            normalized_path=normalized_path,
            page_id=page_id,
            run_id=run_id,
            page_signature=page_signature,
            env_urls={env: url}
        )

        if success:
            logger.info(f"✓ 缓存索引已更新: {normalized_path}")
        else:
            logger.error(f"✗ 缓存索引更新失败: {normalized_path}")

        return success

    def get_cache_stats(self) -> Dict[str, int]:
        """
        获取缓存统计信息

        Returns:
            {
                'total_pages': 总页面数,
                'cache_size_mb': 缓存大小(MB)
            }
        """
        pages = self.pages_service.list_pages()

        total_size = 0
        for page in pages:
            page_file = Path(page['file'])
            if page_file.exists():
                total_size += page_file.stat().st_size

        return {
            'total_pages': len(pages),
            'cache_size_mb': round(total_size / (1024 * 1024), 2)
        }
