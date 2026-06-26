"""
Test Cache Manager
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from app.services.page_exploration.cache_manager import CacheManager
from app.services.page_exploration.project_pages_service import ProjectPagesService
from app.agents.page_exploration.utils.url_normalizer import URLNormalizer


@pytest.fixture
def temp_data_dir():
    """创建临时数据目录"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def cache_manager(temp_data_dir):
    """创建CacheManager实例"""
    pages_service = ProjectPagesService(
        project_id="test-project",
        base_dir=temp_data_dir
    )

    url_normalizer = URLNormalizer(
        domain_mapping={
            'test': 'https://test.example.com',
            'prod': 'https://prod.example.com'
        }
    )

    return CacheManager(pages_service, url_normalizer), pages_service


def test_filter_cached_pages_all_uncached(cache_manager):
    """测试全部未缓存的情况"""
    manager, pages_service = cache_manager

    urls = [
        'https://test.example.com/page1',
        'https://test.example.com/page2',
        'https://test.example.com/page3'
    ]

    result = manager.filter_cached_pages(urls)

    assert len(result['to_explore']) == 3
    assert len(result['cached']) == 0


def test_filter_cached_pages_some_cached(cache_manager):
    """测试部分缓存的情况"""
    manager, pages_service = cache_manager

    # 先保存一个页面到缓存
    pages_service.save_page(
        page_id="page-page1",
        page_data={'title': 'Page 1', 'states': [], 'quality': {}, 'metadata': {}},
        run_id="run-001",
        url="https://test.example.com/page1",
        normalized_path="/page1",
        env="test"
    )

    pages_service.update_cache_index(
        normalized_path="/page1",
        page_id="page-page1",
        run_id="run-001",
        page_signature={'title': 'Page 1'},
        env_urls={'test': 'https://test.example.com/page1'}
    )

    # 测试过滤
    urls = [
        'https://test.example.com/page1',  # 已缓存
        'https://test.example.com/page2',  # 未缓存
        'https://test.example.com/page3'   # 未缓存
    ]

    result = manager.filter_cached_pages(urls)

    assert len(result['to_explore']) == 2
    assert len(result['cached']) == 1
    assert result['cached'][0]['normalized_path'] == '/page1'


def test_update_cache_after_exploration(cache_manager):
    """测试探索后更新缓存"""
    manager, pages_service = cache_manager

    # 先保存页面
    pages_service.save_page(
        page_id="page-page1",
        page_data={'title': 'Page 1', 'states': [], 'quality': {}, 'metadata': {}},
        run_id="run-001",
        url="https://test.example.com/page1",
        normalized_path="/page1",
        env="test"
    )

    # 更新缓存
    success = manager.update_cache_after_exploration(
        url="https://test.example.com/page1",
        page_id="page-page1",
        run_id="run-001",
        page_signature={'title': 'Page 1', 'element_count': 10}
    )

    assert success is True

    # 验证缓存已更新
    cache_result = pages_service.check_cache("/page1")
    assert cache_result['cache_hit'] is True


def test_get_cache_stats(cache_manager):
    """测试获取缓存统计"""
    manager, pages_service = cache_manager

    # 保存几个页面
    for i in range(3):
        pages_service.save_page(
            page_id=f"page-{i}",
            page_data={'title': f'Page {i}', 'states': [], 'quality': {}, 'metadata': {}},
            run_id="run-001",
            url=f"https://test.example.com/page{i}",
            normalized_path=f"/page{i}",
            env="test"
        )

    # 获取统计
    stats = manager.get_cache_stats()

    assert stats['total_pages'] == 3
    assert stats['cache_size_mb'] > 0
