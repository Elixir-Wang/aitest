"""
Test for Project Pages Service
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from app.services.page_exploration.project_pages_service import ProjectPagesService


@pytest.fixture
def temp_data_dir():
    """创建临时数据目录"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def pages_service(temp_data_dir):
    """创建ProjectPagesService实例"""
    return ProjectPagesService(
        project_id="test-project",
        base_dir=temp_data_dir
    )


def test_save_and_get_page(pages_service):
    """测试保存和读取页面"""
    page_id = "page-workspace-agents"
    page_data = {
        'title': '智能体工作台',
        'structure_summary': '发现创建智能体入口。',
        'states': [
            {
                'id': 'default',
                'elements': [
                    {
                        'id': 'create_btn',
                        'name': '创建智能体',
                        'locators': [
                            {
                                'code': "getByRole('button', { name: '创建智能体' })",
                                'validation': {'is_unique': True}
                            }
                        ]
                    }
                ]
            }
        ],
        'quality': {'locator_coverage': 0.95},
        'metadata': {}
    }

    # 保存页面
    success = pages_service.save_page(
        page_id=page_id,
        page_data=page_data,
        run_id="run-001",
        url="https://test.example.com/workspace/agents",
        normalized_path="/workspace/agents",
        env="test"
    )

    assert success

    # 读取页面
    loaded_page = pages_service.get_page(page_id)

    assert loaded_page is not None
    assert loaded_page['page']['id'] == page_id
    assert loaded_page['page']['title'] == '智能体工作台'
    assert loaded_page['page']['normalized_path'] == '/workspace/agents'
    assert loaded_page['page']['structure_summary'] == '发现创建智能体入口。'
    assert 'test' in loaded_page['page']['env_urls']
    assert len(loaded_page['states']) == 1


def test_update_page_with_new_env(pages_service):
    """测试更新页面增加新环境"""
    page_id = "page-workspace-agents"
    page_data = {
        'title': '智能体工作台',
        'states': [],
        'quality': {},
        'metadata': {}
    }

    # 首次保存（测试环境）
    pages_service.save_page(
        page_id=page_id,
        page_data=page_data,
        run_id="run-001",
        url="https://test.example.com/workspace/agents",
        normalized_path="/workspace/agents",
        env="test"
    )

    # 更新（生产环境）
    pages_service.save_page(
        page_id=page_id,
        page_data=page_data,
        run_id="run-002",
        url="https://prod.example.com/workspace/agents",
        normalized_path="/workspace/agents",
        env="prod"
    )

    # 验证两个环境都存在
    loaded_page = pages_service.get_page(page_id)
    env_urls = loaded_page['page']['env_urls']

    assert 'test' in env_urls
    assert 'prod' in env_urls
    assert env_urls['test'] == "https://test.example.com/workspace/agents"
    assert env_urls['prod'] == "https://prod.example.com/workspace/agents"


def test_cache_check_miss(pages_service):
    """测试缓存未命中"""
    result = pages_service.check_cache("/workspace/agents")

    assert result['cache_hit'] is False


def test_cache_check_hit(pages_service):
    """测试缓存命中"""
    page_id = "page-workspace-agents"
    normalized_path = "/workspace/agents"

    # 保存页面
    pages_service.save_page(
        page_id=page_id,
        page_data={'title': '智能体工作台', 'states': [], 'quality': {}, 'metadata': {}},
        run_id="run-001",
        url="https://test.example.com/workspace/agents",
        normalized_path=normalized_path,
        env="test"
    )

    # 更新缓存索引
    pages_service.update_cache_index(
        normalized_path=normalized_path,
        page_id=page_id,
        run_id="run-001",
        page_signature={'title': '智能体工作台', 'element_count': 15},
        env_urls={'test': 'https://test.example.com/workspace/agents'}
    )

    # 缓存检查
    result = pages_service.check_cache(normalized_path)

    assert result['cache_hit'] is True
    assert result['page_id'] == page_id
    assert 'last_explored_at' in result


def test_find_page_by_path(pages_service):
    """测试根据路径查找页面"""
    page_id = "page-workspace-agents"
    normalized_path = "/workspace/agents"

    # 保存页面和缓存
    pages_service.save_page(
        page_id=page_id,
        page_data={'title': '智能体工作台', 'states': [], 'quality': {}, 'metadata': {}},
        run_id="run-001",
        url="https://test.example.com/workspace/agents",
        normalized_path=normalized_path,
        env="test"
    )

    pages_service.update_cache_index(
        normalized_path=normalized_path,
        page_id=page_id,
        run_id="run-001",
        page_signature={'title': '智能体工作台'},
        env_urls={'test': 'https://test.example.com/workspace/agents'}
    )

    # 查找页面
    found_page_id = pages_service.find_page_by_path(normalized_path)

    assert found_page_id == page_id


def test_find_element(pages_service):
    """测试查找元素"""
    page_id = "page-workspace-agents"
    page_data = {
        'title': '智能体工作台',
        'states': [
            {
                'id': 'default',
                'elements': [
                    {
                        'id': 'create_btn',
                        'name': '创建智能体',
                        'locators': [
                            {'code': "getByRole('button', { name: '创建智能体' })"}
                        ]
                    },
                    {
                        'id': 'search_input',
                        'name': '搜索智能体',
                        'locators': [
                            {'code': "getByLabel('搜索智能体')"}
                        ]
                    }
                ]
            }
        ],
        'quality': {},
        'metadata': {}
    }

    # 保存页面
    pages_service.save_page(
        page_id=page_id,
        page_data=page_data,
        run_id="run-001",
        url="https://test.example.com/workspace/agents",
        normalized_path="/workspace/agents",
        env="test"
    )

    # 查找元素
    element = pages_service.find_element(page_id, "创建智能体", "default")

    assert element is not None
    assert element['id'] == 'create_btn'
    assert element['name'] == '创建智能体'
    assert len(element['locators']) == 1

    # 查找不存在的元素
    not_found = pages_service.find_element(page_id, "不存在的按钮", "default")
    assert not_found is None


def test_list_pages(pages_service):
    """测试列出所有页面"""
    # 保存多个页面
    for i in range(3):
        pages_service.save_page(
            page_id=f"page-{i}",
            page_data={'title': f'页面{i}', 'structure_summary': f'页面{i}摘要', 'states': [], 'quality': {}, 'metadata': {}},
            run_id="run-001",
            url=f"https://test.example.com/page-{i}",
            normalized_path=f"/page-{i}",
            env="test"
        )

    # 列出页面
    pages = pages_service.list_pages()

    assert len(pages) == 3
    assert all('page_id' in p for p in pages)
    assert all('normalized_path' in p for p in pages)
    assert all('structure_summary' in p for p in pages)
